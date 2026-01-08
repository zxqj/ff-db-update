from datetime import datetime, timezone

import json

from src.nba_api.stats.endpoints import LeagueGameFinder
from .configuration import _get_db_session
from .nba_season import NBASeason
from nba_api.stats.library.parameters import SeasonTypeAllStar, SeasonTypePlayoffs
from sqlalchemy import func

# new imports for repository access
from .players_repo import PlayerRepository
from .game_stats_repo import GameStatsRepository
from .game_stats import GameStats
import NBAStatsAPI

def json_dump(o):
    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError("Type not serializable")
    return json.dumps(o, default=serialize_datetime)

def get_date_season(date):
    year = date.year
    month = date.month
    if month >= 10:
        return f"{year}-{str(year+1)[2:]}"
    else:
        return f"{year-1}-{str(year)[2:]}"

def get_all_games_bulk_import(logger, from_season: NBASeason):
    """
    When making multiple consecutive requests to the API, sometimes it stop responding.
    The initial import of data will have to be done with care to minimize the number of
    requests and potentially throttle them.  The maximum number rows returned in a request
    is 30000.  This is enough to accommodate all players' games (playoffs, regular season,
    pre-season, play-in, all-star) for a single season, up until the year 2011.

    The season id is given in the format xYYYY where YYYY is the beginning year of the
    season and x is a code that indicates the part of season:
    1 - Pre Season
    2 - Regular Season
    3 - All Star
    4 - Playoffs
    5 - Play In
    """
    args = dict(league_id_nullable='00', player_or_team_abbreviation='P', season_nullable=str(from_season)
    pass


def get_all_games(logger, season_type = None, player=None, date_from=None):
    """Return all games for a player (mapping with 'id') starting from a date.

    `player` may be a mapping with keys 'id' and 'draft_year' or None.
    """
    l = []
    # start_season = NBASeason(draft_year) if date_from is None else NBASeason(date_from)

    args = dict(league_id_nullable='00', player_or_team_abbreviation='P')

    if season_type is not None:
        args['season_type_nullable'] = season_type
    if date_from is not None:
        args['date_from_nullable'] = date_from
    if player is not None:
        # player may be mapping or object with id attribute
        try:
            pid = player.get('id') if isinstance(player, dict) else getattr(player, 'id', None)
        except Exception:
            pid = None
        if pid is not None:
            args['player_id_nullable'] = pid
    for game in NBAStatsAPI.invoke_endpoint(LeagueGameFinder, logger, **args):
        # attempt to set season_type; allow mapping or object
        if season_type is not SeasonTypePlayoffs.preseason and (game.season_type() is not SeasonTypePlayoffs.preseason):
            l.append(game)
    return l

def update(db_conn=None, logger_factory=None):
    """Download and insert player game logs for all players in the DB.

    Expects a transactional psycopg2 connection passed in via `db_conn`.
    """
    if db_conn is None:
        raise RuntimeError("games update requires a transactional db_conn")

    logger = logger_factory(__name__)

    # gather players from the players table using SQLAlchemy repository
    session = _get_db_session()
    repo = PlayerRepository(session)
    gs_repo = GameStatsRepository(session)
    players = repo.fetchAll()

    if not players:
        if logger:
            logger.debug("no players found in database")
        session.close()
        return 0

    total_inserted = 0
    logger.info(f"There are indeed {len(players)} players")

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

    def parse_date(s):
        if s is None:
            return None
        if isinstance(s, datetime):
            return s.date()
        try:
            # try ISO formats first
            return datetime.fromisoformat(s).date()
        except Exception:
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

    for player in sorted(players, key=lambda p: p.id):
        # find most recent game_date for this player using SQLAlchemy session
        last_date = session.query(func.max(GameStats.game_date)).filter(GameStats.player_id == player.id).scalar()
        date_from = None
        if last_date is not None:
            # pass ISO date string
            date_from = last_date.isoformat()

        # request player game logs
        try:
            logger.info("get all games for player %s", player.id)
            games = get_all_games(logger, player={'id': player.id, 'draft_year': player.draft_year}, date_from=date_from)
        except Exception:
            logger.warning("failed to retrieve games for player %s", player.id, exc_info=True)
            continue

        if not games:
            if logger:
                logger.debug("no games returned for player %s", player.id)
            continue

        gs_list = []
        for g in games:
            # g is a dict-like mapping with lowercase keys or a Box; use .get if available
            def gget(key):
                try:
                    return g.get(key)
                except Exception:
                    try:
                        return getattr(g, key)
                    except Exception:
                        # try upper-case header
                        try:
                            return g.get(key.upper())
                        except Exception:
                            return None

            season_id = gget('season_id')
            player_id = to_int(gget('player_id') or gget('playerid') or gget('player_id'))
            game_id = gget('game_id') or gget('gameid') or gget('game_id')
            game_date = parse_date(gget('game_date'))
            matchup = gget('matchup')
            wl = gget('wl')
            min_ = gget('min')
            fgm = to_int(gget('fgm'))
            fga = to_int(gget('fga'))
            fg_pct = to_float(gget('fg_pct'))
            fg3m = to_int(gget('fg3m'))
            fg3a = to_int(gget('fg3a'))
            fg3_pct = to_float(gget('fg3_pct'))
            ftm = to_int(gget('ftm'))
            fta = to_int(gget('fta'))
            ft_pct = to_float(gget('ft_pct'))
            oreb = to_int(gget('oreb'))
            dreb = to_int(gget('dreb'))
            reb = to_int(gget('reb'))
            ast = to_int(gget('ast'))
            tov = to_int(gget('tov'))
            stl = to_int(gget('stl'))
            blk = to_int(gget('blk'))
            pf = to_int(gget('pf'))
            pts = to_int(gget('pts'))
            plus_minus = to_float(gget('plus_minus'))

            gs = GameStats()
            gs.season_id = season_id
            gs.player_id = player_id
            gs.game_id = str(game_id) if game_id is not None else None
            gs.game_date = game_date
            gs.matchup = matchup
            gs.wl = wl
            gs.min = str(min_) if min_ is not None else None
            gs.fgm = fgm
            gs.fga = fga
            gs.fg_pct = fg_pct
            gs.fg3m = fg3m
            gs.fg3a = fg3a
            gs.fg3_pct = fg3_pct
            gs.ftm = ftm
            gs.fta = fta
            gs.ft_pct = ft_pct
            gs.oreb = oreb
            gs.dreb = dreb
            gs.reb = reb
            gs.ast = ast
            gs.tov = tov
            gs.stl = stl
            gs.blk = blk
            gs.pf = pf
            gs.pts = pts
            gs.plus_minus = plus_minus

            gs_list.append(gs)

        if gs_list:
            try:
                inserted_count = gs_repo.add(gs_list)
                total_inserted += inserted_count
                if logger:
                    logger.info("inserted %d new games for player %s", inserted_count, player.id)
            except Exception as exc:
                if logger:
                    logger.exception("failed to insert games for player %s: %s", player.id, exc)
                # continue to next player on error
                continue
    session.close()
    return total_inserted