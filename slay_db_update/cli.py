import click
from .cli_tools import loudspeaker, wrap_module_with_decorator
from .players import update, get_nba_stats_result
import functools
import yaml
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from typing import Any, Callable
from datetime import datetime
from nba_api.stats.endpoints.playergamelogs import PlayerGameLogs

loud_sh = wrap_module_with_decorator('sh', loudspeaker)


def _read_dsn() -> str:
    """Read the `dsn` value from the project root `config.yaml`.
    Returns the DSN string or raises a RuntimeError if not found.
    """
    # config.yaml lives at the project root (two levels up from this file)
    possible_paths = [
        Path(__file__).resolve().parents[1] / "config.yaml",
        Path.cwd() / "config.yaml",
    ]
    for p in possible_paths:
        if p.exists():
            with p.open() as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict) and "dsn" in data:
                    return data["dsn"]
    raise RuntimeError("dsn not found in config.yaml")


def script_executor(script_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that logs script execution to the `script_executions` table.

    Behavior:
    - Creates two DB connections using the DSN from config.yaml: one for logging
      (log_conn) and one for the transactional work (app_conn).
    - Inserts a row into script_executions with status 'running' and start_time = now().
    - Passes the transactional connection to the wrapped function via the keyword
      argument `db_conn` (unless already provided).
    - On success commits the transaction and updates the row to status 'completed' and sets end_time.
    - On exception rolls back the transaction, updates the row to status 'failed' and records the error_message,
      then re-raises the exception.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            dsn = _read_dsn()
            # Create separate connections so logging always commits independently
            log_conn = psycopg2.connect(dsn)
            app_conn = psycopg2.connect(dsn)
            try:
                log_cur = log_conn.cursor()
                # Insert running record and capture start_time
                log_cur.execute(
                    "INSERT INTO script_executions (name, start_time, status, comments) VALUES (%s, now(), %s, %s) RETURNING start_time",
                    (script_name, 'running', None),
                )
                start_time = log_cur.fetchone()[0]
                log_conn.commit()

                try:
                    # Begin transactional work for wrapped function
                    app_conn.autocommit = False
                    if 'db_conn' not in kwargs:
                        kwargs['db_conn'] = app_conn
                    result = func(*args, **kwargs)
                    # If the wrapped function completed, commit
                    app_conn.commit()

                    # Update logging row to completed
                    log_cur.execute(
                        "UPDATE script_executions SET end_time = now(), status = %s WHERE name = %s AND start_time = %s",
                        ('completed', script_name, start_time),
                    )
                    log_conn.commit()
                    return result
                except Exception as exc:
                    # Rollback transactional work
                    app_conn.rollback()
                    # Record failure and the error message (truncate if necessary)
                    err_text = str(exc)
                    if len(err_text) > 2000:
                        err_text = err_text[:2000]
                    log_cur.execute(
                        "UPDATE script_executions SET end_time = now(), status = %s, error_message = %s WHERE name = %s AND start_time = %s",
                        ('failed', err_text, script_name, start_time),
                    )
                    log_conn.commit()
                    raise
            finally:
                try:
                    log_conn.close()
                except Exception:
                    pass
                try:
                    app_conn.close()
                except Exception:
                    pass

        return wrapper

    return decorator


@click.group()
@click.version_option()
def cli():
    """
    """


@cli.command(name="players")
def players():
    update()


@cli.command(name="games")
@script_executor("games")
def games(db_conn=None):
    """Download and insert player game logs for all players in the DB.

    - Finds all person_id values from `players` and `unrecognized players` (if present)
    - For each player, determines the latest game_date already in `player_games`
      and requests newer games from the `PlayerGameLogs` endpoint.
    - Inserts rows into `player_games` with ON CONFLICT DO NOTHING.
    """
    if db_conn is None:
        raise RuntimeError("games command requires a transactional db_conn (provided by decorator)")

    cur = db_conn.cursor()

    # gather player ids from players and unrecognized players (if that table exists)
    player_ids = set()
    try:
        cur.execute('SELECT person_id FROM players')
        rows = cur.fetchall()
        for (pid,) in rows:
            if pid is not None:
                player_ids.add(int(pid))
    except Exception:
        # if players table doesn't exist or other error, re-raise
        raise

    # try to include unrecognized players table if present
    try:
        cur.execute('SELECT person_id FROM "unrecognized players"')
        rows = cur.fetchall()
        for (pid,) in rows:
            if pid is not None:
                player_ids.add(int(pid))
    except Exception:
        # ignore if table doesn't exist
        pass

    if not player_ids:
        click.echo("no players found in database")
        return

    total_inserted = 0

    # helper coercions
    def to_int(v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except Exception:
            return None

    def to_float(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except Exception:
            return None

    # columns in player_games (excluding date_inserted)
    columns = [
        'season_year', 'player_id', 'player_name', 'team_id', 'team_abbreviation', 'team_name',
        'game_id', 'game_date', 'matchup', 'wl', 'min', 'fgm', 'fga', 'fg_pct', 'fg3m', 'fg3a', 'fg3_pct',
        'ftm', 'fta', 'ft_pct', 'oreb', 'dreb', 'reb', 'ast', 'tov', 'stl', 'blk', 'blka', 'pf', 'pfd', 'pts',
        'plus_minus', 'nba_fantasy_pts', 'dd2', 'td3', 'gp_rank', 'w_rank', 'l_rank', 'w_pct_rank', 'min_rank',
        'fgm_rank', 'fga_rank', 'fg_pct_rank', 'fg3m_rank', 'fg3a_rank', 'fg3_pct_rank', 'ftm_rank', 'fta_rank',
        'ft_pct_rank', 'oreb_rank', 'dreb_rank', 'reb_rank', 'ast_rank', 'tov_rank', 'stl_rank', 'blk_rank',
        'blka_rank', 'pf_rank', 'pfd_rank', 'pts_rank', 'plus_minus_rank', 'nba_fantasy_pts_rank', 'dd2_rank',
        'td3_rank'
    ]

    insert_sql = f"""
    INSERT INTO player_games ({', '.join(columns)}, date_inserted)
    VALUES %s
    ON CONFLICT (player_id, game_id) DO NOTHING
    RETURNING player_id
    """

    for pid in sorted(player_ids):
        # find most recent game_date for this player
        cur.execute('SELECT MAX(game_date) FROM player_games WHERE player_id = %s', (pid,))
        last_row = cur.fetchone()
        last_date = last_row[0] if last_row is not None else None
        date_from = ''
        if last_date is not None:
            # pass ISO date string
            date_from = last_date.isoformat()

        # request player game logs
        try:
            endpoint = PlayerGameLogs(player_id_nullable=pid, date_from_nullable=date_from)
            games = get_nba_stats_result(endpoint, 'PlayerGameLogs')
        except Exception:
            # if the API call fails for this player, skip and continue
            continue

        if not games:
            continue

        rows_to_insert = []
        for g in games:
            # g is a dict-like mapping with lowercase keys
            season_year = g.get('season_year')
            player_id = to_int(g.get('player_id'))
            player_name = g.get('player_name')
            team_id = to_int(g.get('team_id'))
            team_abbreviation = g.get('team_abbreviation')
            team_name = g.get('team_name')
            game_id = g.get('game_id')
            game_date = g.get('game_date')
            matchup = g.get('matchup')
            wl = g.get('wl')
            min_ = g.get('min')
            fgm = to_int(g.get('fgm'))
            fga = to_int(g.get('fga'))
            fg_pct = to_float(g.get('fg_pct'))
            fg3m = to_int(g.get('fg3m'))
            fg3a = to_int(g.get('fg3a'))
            fg3_pct = to_float(g.get('fg3_pct'))
            ftm = to_int(g.get('ftm'))
            fta = to_int(g.get('fta'))
            ft_pct = to_float(g.get('ft_pct'))
            oreb = to_int(g.get('oreb'))
            dreb = to_int(g.get('dreb'))
            reb = to_int(g.get('reb'))
            ast = to_int(g.get('ast'))
            tov = to_int(g.get('tov'))
            stl = to_int(g.get('stl'))
            blk = to_int(g.get('blk'))
            blka = to_int(g.get('blka'))
            pf = to_int(g.get('pf'))
            pfd = to_int(g.get('pfd'))
            pts = to_int(g.get('pts'))
            plus_minus = to_float(g.get('plus_minus'))
            nba_fantasy_pts = to_float(g.get('nba_fantasy_pts'))
            dd2 = to_int(g.get('dd2'))
            td3 = to_int(g.get('td3'))
            gp_rank = to_int(g.get('gp_rank'))
            w_rank = to_int(g.get('w_rank'))
            l_rank = to_int(g.get('l_rank'))
            w_pct_rank = to_float(g.get('w_pct_rank'))
            min_rank = to_int(g.get('min_rank'))
            fgm_rank = to_int(g.get('fgm_rank'))
            fga_rank = to_int(g.get('fga_rank'))
            fg_pct_rank = to_float(g.get('fg_pct_rank'))
            fg3m_rank = to_int(g.get('fg3m_rank'))
            fg3a_rank = to_int(g.get('fg3a_rank'))
            fg3_pct_rank = to_float(g.get('fg3_pct_rank'))
            ftm_rank = to_int(g.get('ftm_rank'))
            fta_rank = to_int(g.get('fta_rank'))
            ft_pct_rank = to_float(g.get('ft_pct_rank'))
            oreb_rank = to_int(g.get('oreb_rank'))
            dreb_rank = to_int(g.get('dreb_rank'))
            reb_rank = to_int(g.get('reb_rank'))
            ast_rank = to_int(g.get('ast_rank'))
            tov_rank = to_int(g.get('tov_rank'))
            stl_rank = to_int(g.get('stl_rank'))
            blk_rank = to_int(g.get('blk_rank'))
            blka_rank = to_int(g.get('blka_rank'))
            pf_rank = to_int(g.get('pf_rank'))
            pfd_rank = to_int(g.get('pfd_rank'))
            pts_rank = to_int(g.get('pts_rank'))
            plus_minus_rank = to_float(g.get('plus_minus_rank'))
            nba_fantasy_pts_rank = to_float(g.get('nba_fantasy_pts_rank'))
            dd2_rank = to_int(g.get('dd2_rank'))
            td3_rank = to_int(g.get('td3_rank'))

            row = (
                season_year, player_id, player_name, team_id, team_abbreviation, team_name,
                game_id, game_date, matchup, wl, min_, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                ftm, fta, ft_pct, oreb, dreb, reb, ast, tov, stl, blk, blka, pf, pfd, pts,
                plus_minus, nba_fantasy_pts, dd2, td3, gp_rank, w_rank, l_rank, w_pct_rank, min_rank,
                fgm_rank, fga_rank, fg_pct_rank, fg3m_rank, fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank,
                ft_pct_rank, oreb_rank, dreb_rank, reb_rank, ast_rank, tov_rank, stl_rank, blk_rank,
                blka_rank, pf_rank, pfd_rank, pts_rank, plus_minus_rank, nba_fantasy_pts_rank, dd2_rank,
                td3_rank, datetime.utcnow()
            )
            rows_to_insert.append(row)

        if rows_to_insert:
            try:
                execute_values(cur, insert_sql, rows_to_insert, page_size=100)
                # fetch returned rows to count inserts
                try:
                    returned = cur.fetchall()
                    total_inserted += len(returned)
                except Exception:
                    # if RETURNING wasn't supported for some reason, fallback to rowcount
                    total_inserted += cur.rowcount if cur.rowcount > 0 else 0
                # commit after each player to keep work small
                db_conn.commit()
            except Exception:
                # rollback on failure for this player's batch and continue
                db_conn.rollback()
                continue

    click.echo(str(total_inserted))
