from typing import Optional, List, Union, Tuple, Callable, Any
from dataclasses import dataclass
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .game_stats import GameStats
from .NBAStatsModel import LeagueGameFinderResult
from automapper import Mapper

_NUMERIC_COLS = [
    "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct",
    "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "pts", "plus_minus"
]

@dataclass
class GameStatsQuery:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    player: Optional[int] = None
    season: Optional[str] = None

    regular_season: bool = True
    playoffs: bool = True
    playin: bool = True
    all_star: bool = True
    pre_season: bool = True

    last_n: Optional[int] = None
    # team: tuple(team_identifier, aggregation_function)
    team: Optional[Tuple[Any, Callable]] = None


class GameStatsRepository:
    def __init__(self, session: Session):
        self.session = session
        self._mapper = Mapper()
        # configure a simple mapping
        self._mapper.create_map(LeagueGameFinderResult, GameStats)

    def _to_model(self, league_obj: LeagueGameFinderResult) -> GameStats:
        return self._mapper.map(league_obj, GameStats)

    def add(self, gs_or_list: Union[GameStats, List[GameStats]]) -> int:
        """
        Insert one or many GameStats. Creates new records where not found.
        Returns number of newly-inserted rows.
        """
        inserted = 0
        if isinstance(gs_or_list, list):
            for gs in gs_or_list:
                exists = self.session.query(GameStats).filter_by(player_id=gs.player_id, game_id=gs.game_id).one_or_none()
                if exists is None:
                    self.session.add(gs)
                    inserted += 1
                else:
                    # update existing fields
                    for col in gs.__table__.columns:
                        if col.name in ("player_id", "game_id", "date_inserted"):
                            continue
                        setattr(exists, col.name, getattr(gs, col.name))
            self.session.commit()
            return inserted
        else:
            gs = gs_or_list
            exists = self.session.query(GameStats).filter_by(player_id=gs.player_id, game_id=gs.game_id).one_or_none()
            if exists is None:
                self.session.add(gs)
                self.session.commit()
                return 1
            else:
                for col in gs.__table__.columns:
                    if col.name in ("player_id", "game_id", "date_inserted"):
                        continue
                    setattr(exists, col.name, getattr(gs, col.name))
                self.session.commit()
                return 0

    def get(self, player_id: int, game_id: Union[int, str]) -> Optional[GameStats]:
        return self.session.query(GameStats).filter_by(player_id=player_id, game_id=str(game_id)).one_or_none()

    def search(self, gsq: GameStatsQuery) -> List[GameStats]:
        q = self.session.query(GameStats)
        if gsq.player is not None:
            q = q.filter(GameStats.player_id == gsq.player)
        if gsq.season:
            q = q.filter(GameStats.season_id == gsq.season)
        if gsq.date_from:
            q = q.filter(GameStats.game_date >= gsq.date_from)
        if gsq.date_to:
            q = q.filter(GameStats.game_date <= gsq.date_to)

        # season type filter stub: only apply if season_type column exists
        season_types = []
        if gsq.regular_season:
            season_types.append("Regular Season")
        if gsq.playoffs:
            season_types.append("Playoffs")
        if gsq.playin:
            season_types.append("PlayIn")
        if gsq.all_star:
            season_types.append("All Star")
        if gsq.pre_season:
            season_types.append("Pre Season")
        if hasattr(GameStats, 'season_type') and season_types:
            q = q.filter(getattr(GameStats, 'season_type').in_(season_types))

        # team aggregation
        if gsq.team:
            team_ident, agg_fn = gsq.team
            aggs = [agg_fn(getattr(GameStats, c)).label(c) for c in _NUMERIC_COLS]
            stmt = select(GameStats.team_id.label('team_id'), GameStats.team_name.label('team_name'), *aggs).select_from(GameStats)
            # apply filters to stmt
            # ...keep it simple: re-run the where clauses
            if gsq.player is not None:
                stmt = stmt.where(GameStats.player_id == gsq.player)
            if gsq.season:
                stmt = stmt.where(GameStats.season_id == gsq.season)
            if gsq.date_from:
                stmt = stmt.where(GameStats.game_date >= gsq.date_from)
            if gsq.date_to:
                stmt = stmt.where(GameStats.game_date <= gsq.date_to)
            stmt = stmt.group_by(GameStats.team_id, GameStats.team_name)
            rows = self.session.execute(stmt).all()
            results: List[GameStats] = []
            for r in rows:
                gs = GameStats()
                gs.team_id = r.team_id
                gs.team_name = r.team_name
                for c in _NUMERIC_COLS:
                    setattr(gs, c, getattr(r, c))
                results.append(gs)
            return results

        q = q.order_by(GameStats.game_date.desc())
        if gsq.last_n:
            q = q.limit(gsq.last_n)
        return q.all()

    def map_from_league_result(self, league_obj: LeagueGameFinderResult) -> GameStats:
        return self._to_model(league_obj)

