# python
from pathlib import Path
from box import Box, BoxList
from nba_api.stats.endpoints.playerindex import PlayerIndex
from nba_api.stats.endpoints.commonplayerinfo import CommonPlayerInfo
from nba_api.stats.library.parameters import Active
from sleeper_wrapper import Players
from psycopg2.extras import execute_values
import time

from datetime import datetime

from slay_db_update.utils import get_nba_stats_result

p = Path()


def get_nbaorg_players():
    l = get_nba_stats_result(PlayerIndex(active_nullable=Active.active_player), "PlayerIndex")
    return BoxList(l)

def get_sleeper_players():
    sleeperjson = Players().get_all_players(league='nba')
    sleeperbox = Box(**sleeperjson)
    return BoxList([player for player in sleeperbox.values()])

# python
def update(db_conn=None, logger_factory=None):
    # Initialize logger via factory if provided; be defensive so this function
    # can be called without a logger_factory in tests or ad-hoc runs.
    logger = logger_factory(__name__) if logger_factory else None
    print(logger)

    # Sleeper API call with timing and logging
    start = time.perf_counter()
    if logger:
        logger.debug("requesting sleeper players")
    sleeper_players = get_sleeper_players()
    elapsed = time.perf_counter() - start
    if logger:
        try:
            sleeper_count = len(sleeper_players)
        except Exception:
            # fallback for iterable without len
            sleeper_count = sum(1 for _ in sleeper_players) if hasattr(sleeper_players, "__iter__") else 0
        logger.info("sleeper returned %d players in %.3f seconds", sleeper_count, elapsed)

    # NBA.org API call with timing and logging
    start = time.perf_counter()
    if logger:
        logger.debug("requesting nbaorg players")
    nbaorg_players = get_nbaorg_players()
    elapsed = time.perf_counter() - start
    if logger:
        try:
            nbaorg_count = len(nbaorg_players)
        except Exception:
            nbaorg_count = sum(1 for _ in nbaorg_players) if hasattr(nbaorg_players, "__iter__") else 0
        logger.info("nbaorg returned %d players in %.3f seconds", nbaorg_count, elapsed)

    double_count = 0
    not_in_sleeper = []
    in_both = []
    for nbaorg_player in nbaorg_players:
        fn_match = lambda sleeper_player: nbaorg_player.player_first_name.lower() == sleeper_player.first_name.lower()
        ln_match = lambda sleeper_player: nbaorg_player.player_last_name.lower() == sleeper_player.last_name.lower()

        matches = [*filter(lambda x: fn_match(x) and ln_match(x), sleeper_players)]
        if len(matches) > 0:
            if len(matches) == 1:
                in_both.append(Box(sleeper_id=matches[0].player_id, **nbaorg_player))
            else:
                double_count += 1
                player_info = get_nba_stats_result(CommonPlayerInfo(player_id=nbaorg_player.person_id), "CommonPlayerInfo")[0]
                birthdate = player_info.birthdate.split("T")[0]
                matched_any = False
                for match in matches:
                    if hasattr(match, "birth_date") and match.birth_date is not None and birthdate == match.birth_date.lower():
                        in_both.append(Box(sleeper_id=match.player_id, **nbaorg_player))
                        matched_any = True
                if not matched_any:
                    not_in_sleeper.append(nbaorg_player)
        else:
            not_in_sleeper.append(nbaorg_player)

    # helpers to coerce types
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

    def to_bool(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("1", "true", "t", "yes", "y"):
            return True
        if s in ("0", "false", "f", "no", "n"):
            return False
        return None

    # prepare rows for DB (store person_id and sleeper_id as INTEGER and expand fields)
    fields = [
        "person_id",
        "sleeper_id",
        "player_last_name",
        "player_first_name",
        "player_slug",
        "team_id",
        "team_slug",
        "is_defunct",
        "team_city",
        "team_name",
        "team_abbreviation",
        "jersey_number",
        "position",
        "height",
        "weight",
        "college",
        "country",
        "draft_year",
        "draft_round",
        "draft_number",
        "roster_status",
        "pts",
        "reb",
        "ast",
        "stats_timeframe",
        "from_year",
        "to_year",
    ]

    def make_rows(boxes, require_sleeper_not_null=False):
        rows = []
        for b in boxes:
            d = b.to_dict() if hasattr(b, "to_dict") else dict(b)
            person_id = d.get("person_id")
            if person_id is None:
                continue
            person_id = to_int(person_id)
            sleeper_id = d.get("sleeper_id")
            if require_sleeper_not_null and sleeper_id is None:
                continue
            sleeper_int = to_int(sleeper_id) if sleeper_id is not None else None

            row = [
                person_id,
                sleeper_int,
                d.get("player_last_name") if d.get("player_last_name") is not None else d.get("PLAYER_LAST_NAME"),
                d.get("player_first_name") if d.get("player_first_name") is not None else d.get("PLAYER_FIRST_NAME"),
                d.get("player_slug") if d.get("player_slug") is not None else d.get("PLAYER_SLUG"),
                to_int(d.get("team_id") or d.get("TEAM_ID")),
                d.get("team_slug") if d.get("team_slug") is not None else d.get("TEAM_SLUG"),
                to_bool(d.get("is_defunct") if "is_defunct" in d else d.get("IS_DEFUNCT")),
                d.get("team_city") if d.get("team_city") is not None else d.get("TEAM_CITY"),
                d.get("team_name") if d.get("team_name") is not None else d.get("TEAM_NAME"),
                d.get("team_abbreviation") if d.get("team_abbreviation") is not None else d.get("TEAM_ABBREVIATION"),
                to_int(d.get("jersey_number") or d.get("JERSEY_NUMBER")),
                d.get("position") if d.get("position") is not None else d.get("POSITION"),
                d.get("height") if d.get("height") is not None else d.get("HEIGHT"),
                to_int(d.get("weight") or d.get("WEIGHT")),
                d.get("college") if d.get("college") is not None else d.get("COLLEGE"),
                d.get("country") if d.get("country") is not None else d.get("COUNTRY"),
                to_int(d.get("draft_year") or d.get("DRAFT_YEAR")),
                to_int(d.get("draft_round") or d.get("DRAFT_ROUND")),
                to_int(d.get("draft_number") or d.get("DRAFT_NUMBER")),
                d.get("roster_status") if d.get("roster_status") is not None else d.get("ROSTER_STATUS"),
                to_float(d.get("pts") or d.get("PTS")),
                to_float(d.get("reb") or d.get("REB")),
                to_float(d.get("ast") or d.get("AST")),
                d.get("stats_timeframe") if d.get("stats_timeframe") is not None else d.get("STATS_TIMEFRAME"),
                to_int(d.get("from_year") or d.get("FROM_YEAR")),
                to_int(d.get("to_year") or d.get("TO_YEAR")),
                datetime.utcnow(),
            ]
            rows.append(tuple(row))
        return rows

    players_rows = make_rows(in_both, require_sleeper_not_null=True)
    unrecognized_rows = make_rows(not_in_sleeper, require_sleeper_not_null=False)

    try:

        cur = db_conn.cursor()

        # create tables with individual columns for each field (lowercase)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            person_id INTEGER PRIMARY KEY,
            sleeper_id INTEGER NOT NULL,
            player_last_name TEXT,
            player_first_name TEXT,
            player_slug TEXT,
            team_id INTEGER,
            team_slug TEXT,
            is_defunct BOOLEAN,
            team_city TEXT,
            team_name TEXT,
            team_abbreviation TEXT,
            jersey_number INTEGER,
            position TEXT,
            height TEXT,
            weight INTEGER,
            college TEXT,
            country TEXT,
            draft_year INTEGER,
            draft_round INTEGER,
            draft_number INTEGER,
            roster_status TEXT,
            pts REAL,
            reb REAL,
            ast REAL,
            stats_timeframe TEXT,
            from_year INTEGER,
            to_year INTEGER,
            date_inserted TIMESTAMPTZ NOT NULL
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS "unrecognized_players" (
            person_id INTEGER PRIMARY KEY,
            sleeper_id INTEGER,
            player_last_name TEXT,
            player_first_name TEXT,
            player_slug TEXT,
            team_id INTEGER,
            team_slug TEXT,
            is_defunct BOOLEAN,
            team_city TEXT,
            team_name TEXT,
            team_abbreviation TEXT,
            jersey_number INTEGER,
            position TEXT,
            height TEXT,
            weight INTEGER,
            college TEXT,
            country TEXT,
            draft_year INTEGER,
            draft_round INTEGER,
            draft_number INTEGER,
            roster_status TEXT,
            pts REAL,
            reb REAL,
            ast REAL,
            stats_timeframe TEXT,
            from_year INTEGER,
            to_year INTEGER,
            date_inserted TIMESTAMPTZ NOT NULL
        )
        """)

        inserted_players = 0
        inserted_unrecognized = 0

        if players_rows:
            insert_sql = f"""
            INSERT INTO players ({', '.join(fields)}, date_inserted)
            VALUES %s
            ON CONFLICT (person_id) DO NOTHING
            RETURNING person_id
            """
            execute_values(cur, insert_sql, players_rows, page_size=100)
            returned = cur.fetchall()
            inserted_players = len(returned)


        if unrecognized_rows:
            insert_sql_unrec = f"""
            INSERT INTO "unrecognized_players" ({', '.join(fields)}, date_inserted)
            VALUES %s
            ON CONFLICT (person_id) DO NOTHING
            RETURNING person_id
            """
            execute_values(cur, insert_sql_unrec, unrecognized_rows, page_size=100)
            returned_unrec = cur.fetchall()
            inserted_unrecognized = len(returned_unrec)
    except Exception as e:
        logger.error("error inserting players: %s", str(e))
    finally:
        pass
    # log only the numbers of newly-inserted players
    if logger:
        logger.info("inserted %d new players and %d unrecognized players", inserted_players, inserted_unrecognized)
    else:
        # fallback for environments without a logger
        print(inserted_players)
        print(inserted_unrecognized)

    return inserted_players, inserted_unrecognized
