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
from .game_stats_repo import GameStatsRepository, GameStatsQuery
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

class GamesUpdater:
    def __init__(self):
        self.game_repository: GameStatsRepository = GameStatsRepository()
        self.logger = Config.get().get_logger(__name__)

    def pull(self, args):
        games: list[LeagueGameFinderResults] = [*NBAStatsAPI.invoke_endpoint(LeagueGameFinder, LeagueGameFinderResults, self.logger, **args)]
        self.logger.info(f"Found {len(games)} games")
        self.game_repository.insert([mapper.map(game) for game in games])
        Config.get().get_session().commit()

    def pull_from_season(self, from_season: NBASeason):
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
            self.logger.info(f"self.pulling games for season {season}")
            # After 2011, the full season began having more than 30,000 player-games, and
            # that is the maximum number the API will return, so we break it up into regular, playoffs
            # and playin after that
            if season <= 2011:
                self.pull(args)
            else:
                for season_type in [SeasonTypePlayoffs.regular, SeasonTypePlayoffs.playoffs]:
                    args['season_type_nullable'] = season_type
                    self.pull(args)

            Config.get().get_session().commit()

            # if we have more seasons to go, the rest are full seasons, or a season we're in the middle of
            date_from = None
            season = season + 1

    def pull_from_date(self, date_from: date):
        """
        Pull all games from the given date forward until today.
        """

        season_str = get_date_season(date_from)
        season = NBASeason(season_str)
        args = game_finder_args(season_nullable=season,
                                date_from_nullable=date_from.isoformat())
        self.game_repository.remove(GameStatsQuery(date_from=date_from))
        if season <= NBASeason(2011):
            self.pull(args)
        else:
            for season_type in [SeasonTypePlayoffs.regular, SeasonTypePlayoffs.playoffs]:
                args['season_type_nullable'] = season_type
                self.pull(args)
        Config.get().get_session().commit()
        season = season + 1
        if season <= NBASeason():
            self.pull_from_season(season)
        Config.get().get_session().commit()


    def update(self):
        """Download and insert player game logs for all players in the DB.

        Expects a transactional psycopg2 connection passed in via `db_conn`.
        """


        # gather players from the players table using SQLAlchemy repository
        newest_date: Optional[date] = self.game_repository.get_newest_game_date()
        if newest_date is not None:
            self.logger.info(f"Newest game date in DB: {newest_date.isoformat()}")
            self.pull_from_date(newest_date)
        else:
            season = NBASeason(Config.get().start_year)
            self.pull_from_season(season)
