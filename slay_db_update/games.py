import json
from datetime import date
from datetime import datetime
from typing import Optional

from automapper import mapper
from nba_api.stats.endpoints.leaguegamefinder import LeagueGameFinder
from nba_api.stats.library.parameters import LeagueIDNullable, PlayerOrTeamAbbreviation
from nba_api.stats.library.parameters import SeasonTypePlayoffs

from . import NBAStatsAPI
from .NBAStatsModel import LeagueGameFinderResults
from .configuration import Config
from .game_stats import GameStats
# new imports for repository access
from .game_stats_repo import GameStatsRepository
from .nba_season import NBASeason


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


def game_finder_args(**kwargs):
    return dict(**kwargs,
                league_id_nullable=LeagueIDNullable.nba,
                player_or_team_abbreviation=PlayerOrTeamAbbreviation.player)

def game_filter(result: LeagueGameFinderResults) -> bool:
    return result.season_type() is not SeasonTypePlayoffs.preseason

mapper.add(LeagueGameFinderResults, GameStats,
                   fields_mapping={"team_code": "LeagueGameFinderResults.team_abbreviation"})
def pull_full(logger, from_season: NBASeason, game_repository: GameStatsRepository, date_from = None):
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

    season = from_season
    while season <= NBASeason():
        args = game_finder_args(season_nullable=season)

        if date_from is not None:
            args['date_from_nullable'] = date_from.isoformat()
        # After 2011, the full season began having more than 30,000 player-games, and
        # that is the maximum number the API will return, so we break it up into regular, playoffs
        # and playin after that
        if season <= 2011:
            games: list[LeagueGameFinderResults] = [*NBAStatsAPI.invoke_endpoint(LeagueGameFinder, LeagueGameFinderResults, logger, **args)]
            logger.info(f"Found {len(games)} games for season {season}")
            game_repository.insert([mapper.map(game) for game in games])
        else:
            for season_type in [SeasonTypePlayoffs.regular, SeasonTypePlayoffs.playin, SeasonTypePlayoffs.playoffs]:
                games: list[LeagueGameFinderResults] = [*NBAStatsAPI.invoke_endpoint(LeagueGameFinder, LeagueGameFinderResults, logger, **args)]
                logger.info(f"Found {len(games)} games for season {season} and type {season_type}")
                game_repository.insert([mapper.map(game) for game in games])

        Config.get().get_session().commit()

        # if we have more seasons to go, the rest are full seasons, or a season we're in the middle of
        date_from = None
        season = season + 1


def update(db_conn=None, logger_factory=None):
    """Download and insert player game logs for all players in the DB.

    Expects a transactional psycopg2 connection passed in via `db_conn`.
    """
    if db_conn is None:
        raise RuntimeError("games update requires a transactional db_conn")

    logger = logger_factory(__name__)

    # gather players from the players table using SQLAlchemy repository
    conf = Config.get()
    session = conf.get_session()
    gs_repo = GameStatsRepository(session)
    newest_date: Optional[date] = gs_repo.get_newest_game_date()
    season = NBASeason(Config.get().start_year) if newest_date is None else NBASeason(newest_date.year)
    pull_full(logger, season, gs_repo, newest_date)
