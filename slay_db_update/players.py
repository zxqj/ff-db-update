# python
from pathlib import Path
from box import Box, BoxList
from nba_api.stats.endpoints.playerindex import PlayerIndex
from nba_api.stats.endpoints.commonplayerinfo import CommonPlayerInfo
from nba_api.stats.library.parameters import Active
from sleeper_wrapper import Players
# new imports for SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .dal_utils import DalUtils
from .players_repo import PlayerRepository
from .models import Player as PlayerModel
import yaml
from slay_db_update.utils import get_nba_stats_result, timed

p = Path()

def get_nbaorg_players():
    l = get_nba_stats_result(PlayerIndex(active_nullable=Active.active_player), "PlayerIndex")
    return BoxList(l)

def get_sleeper_players():
    sleeperjson = Players().get_all_players(league='nba')
    sleeperbox = Box(**sleeperjson)
    return BoxList([player for player in sleeperbox.values()])

def _get_db_session(config_path=None):
    # read connection string from config.yaml in project root
    cfg_path = config_path or Path(__file__).resolve().parents[2] / 'config.yaml'
    if not cfg_path.exists():
        raise RuntimeError(f"config.yaml not found at expected path: {cfg_path}")
    cfg = yaml.safe_load(cfg_path.read_text())
    conn = cfg.get('database') or cfg.get('connection_string') or cfg.get('connection')
    if conn is None:
        raise RuntimeError("database connection string not found in config.yaml")
    engine = create_engine(conn)
    Session = sessionmaker(bind=engine)
    return Session()

dal_utils = DalUtils()
# python
def update(db_conn=None, logger_factory=None):
    # Initialize logger via factory if provided; be defensive so this function
    # can be called without a logger_factory in tests or ad-hoc runs.
    logger = logger_factory(__name__) if logger_factory else None


    sleeper_players = timed("Sleeper API get-all-players request", logger)(get_sleeper_players)

    sleeper_count = sum(1 for _ in sleeper_players) if hasattr(sleeper_players, "__iter__") else 0
    if logger:
        logger.info("sleeper returned %d players", sleeper_count)

    nbaorg_players = get_nbaorg_players()

    nbaorg_count = sum(1 for _ in nbaorg_players) if hasattr(nbaorg_players, "__iter__") else 0
    if logger:
        logger.info("nbaorg returned %d players", nbaorg_count)

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

    def make_entity(box, require_sleeper_not_null=False):
        d = box.to_dict() if hasattr(box, "to_dict") else dict(box)
        person_id = d.get("person_id") or d.get("id")
        if person_id is None:
            return None
        person_id = to_int(person_id)
        sleeper_id = d.get("sleeper_id")
        if require_sleeper_not_null and sleeper_id is None:
            return None
        # sleeper_id is no longer stored on Player; return PlayerModel instance and
        # let caller create mapping rows for sleeper_player_ids separately
        p = PlayerModel(
            id=person_id,
            last_name=d.get("player_last_name") if d.get("player_last_name") is not None else d.get("PLAYER_LAST_NAME"),
            first_name=d.get("player_first_name") if d.get("player_first_name") is not None else d.get("PLAYER_FIRST_NAME"),
            player_slug=d.get("player_slug") if d.get("player_slug") is not None else d.get("PLAYER_SLUG"),
            team_id=to_int(d.get("team_id") or d.get("TEAM_ID")),
            team_slug=d.get("team_slug") if d.get("team_slug") is not None else d.get("TEAM_SLUG"),
            is_defunct=to_bool(d.get("is_defunct") if "is_defunct" in d else d.get("IS_DEFUNCT")),
            team_city=d.get("team_city") if d.get("team_city") is not None else d.get("TEAM_CITY"),
            team_name=d.get("team_name") if d.get("team_name") is not None else d.get("TEAM_NAME"),
            team_abbreviation=d.get("team_abbreviation") if d.get("team_abbreviation") is not None else d.get("TEAM_ABBREVIATION"),
            jersey_number=d.get("jersey_numbe   r") if d.get("jersey_number") is not None else d.get("JERSEY_NUMBER"),
            position=d.get("position") if d.get("position") is not None else d.get("POSITION"),
            height=d.get("height") if d.get("height") is not None else d.get("HEIGHT"),
            weight=(d.get("weight") if d.get("weight") is not None else d.get("WEIGHT")),
            college=d.get("college") if d.get("college") is not None else d.get("COLLEGE"),
            country=d.get("country") if d.get("country") is not None else d.get("COUNTRY"),
            draft_year=to_int(d.get("draft_year") or d.get("DRAFT_YEAR")),
            draft_round=to_int(d.get("draft_round") or d.get("DRAFT_ROUND")),
            draft_number=to_int(d.get("draft_number") or d.get("DRAFT_NUMBER")),
            roster_status=d.get("roster_status") if d.get("roster_status") is not None else d.get("ROSTER_STATUS"),
            pts=to_float(d.get("pts") or d.get("PTS")),
            reb=to_float(d.get("reb") or d.get("REB")),
            ast=to_float(d.get("ast") or d.get("AST")),
            stats_timeframe=d.get("stats_timeframe") if d.get("stats_timeframe") is not None else d.get("STATS_TIMEFRAME"),
            from_year=to_int(d.get("from_year") or d.get("FROM_YEAR")),
            to_year=to_int(d.get("to_year") or d.get("TO_YEAR")),
        )
        return p

    players_entities = [e for e in (make_entity(b, require_sleeper_not_null=True) for b in in_both) if e is not None]
    unrecognized_entities = [e for e in (make_entity(b, require_sleeper_not_null=False) for b in not_in_sleeper) if e is not None]

    # Build sleeper mappings: (player_id, sleeper_id) from in_both entries
    sleeper_mappings = []
    for b in in_both:
        d = b.to_dict() if hasattr(b, 'to_dict') else dict(b)
        pid = to_int(d.get('person_id') or d.get('id'))
        sid = to_int(d.get('sleeper_id') or d.get('player_id'))
        if pid is not None and sid is not None:
            sleeper_mappings.append({'player_id': pid, 'sleeper_id': sid})

    # persist
    session = _get_db_session()
    repo = PlayerRepository(session)

    inserted_players = 0
    inserted_unrecognized = 0
    inserted_sleeper_mappings = 0
    try:
        # bulk upsert into players table (accepts model instances)
        inserted_players = repo.bulk_upsert(PlayerModel, players_entities)

        # bulk upsert into unrecognized_players table (table name string)
        inserted_unrecognized = repo.bulk_upsert('unrecognized_players', unrecognized_entities)

        # bulk insert sleeper mappings into sleeper_player_ids table
        if sleeper_mappings:
            inserted_sleeper_mappings = repo.bulk_upsert('sleeper_player_ids', sleeper_mappings)
    except Exception as e:
        if logger:
            logger.error("error inserting players (bulk upsert): %s", str(e))
        else:
            print("error inserting players:", str(e))
    finally:
        session.close()

    # log only the numbers of newly-inserted players
    if logger:
        logger.info("inserted %d new players, %d unrecognized players, and %d sleeper mappings", inserted_players, inserted_unrecognized, inserted_sleeper_mappings)
    else:
        # fallback for environments without a logger
        print(inserted_players)
        print(inserted_unrecognized)
        print(inserted_sleeper_mappings)

    return inserted_players, inserted_unrecognized, inserted_sleeper_mappings
