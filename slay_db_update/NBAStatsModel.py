from dataclasses import dataclass
from enum import StrEnum, IntEnum, auto
from typing import Self, Type, TypeAlias, TypeVar, Generator, Optional

from nba_api.stats.library.parameters import SeasonTypePlayoffs


class TeamAbbreviation(IntEnum):
    ATL = 1610612737
    BKN = auto()
    BOS = auto()
    CHA = auto()
    CHI = auto()
    CLE = auto()
    DAL = auto()
    DEN = auto()
    DET = auto()
    GSW = auto()
    HOU = auto()
    IND = auto()
    LAC = auto()
    LAL = auto()
    MEM = auto()
    MIA = auto()
    MIL = auto()
    MIN = auto()
    NOP = auto()
    NYK = auto()
    OKC = auto()
    ORL = auto()
    PHI = auto()
    PHX = auto()
    POR = auto()
    SAC = auto()
    SAS = auto()
    TOR = auto()
    UTA = auto()
    WAS = auto()

    @classmethod
    def from_str(cls: Type[Self], label: str) -> Self:
        label = label.upper()
        if label in cls.__members__:
            return cls[label]
        raise ValueError(f"{label} is not a valid TeamAbbreviation")

class Outcome(StrEnum):
    WIN = "W"
    LOSS = "L"

class NamedResultType:
    @classmethod
    def result_type_name(cls: Type[Self]) -> str:
        return cls.__name__

    @classmethod
    def from_tuple(cls: Type[Self], data: tuple) -> Self:
        return cls(*data)

@dataclass
class LeagueGameFinderResults(NamedResultType):
    season_id: str
    player_id: int
    player_name: str
    team_id: int
    team_abbreviation: TeamAbbreviation
    team_name: str
    game_id: str
    game_date: str
    matchup: str
    wl: Outcome
    min: int
    pts: float
    fgm: float
    fga: float
    fg_pct: float
    fg3m: float
    fg3a: float
    fg3_pct: float
    ftm: float
    fta: float
    ft_pct: float
    oreb: float
    dreb: float
    reb: float
    ast: float
    stl: float
    blk: float
    tov: float
    pf: float
    plus_minus: float

    def season_type(self) -> SeasonTypePlayoffs:
        code = int(self.season_id[:1])
        code_map: list[Optional[SeasonTypePlayoffs]] = [
            None,
            SeasonTypePlayoffs.preseason,
            SeasonTypePlayoffs.regular,
            None,
            SeasonTypePlayoffs.playoffs,
            SeasonTypePlayoffs.playin
        ]
        stp = code_map[code]
        if stp is None:
            raise ValueError(f"Invalid season type code: {code} in season_id: {self.season_id}")
        return stp



    TupleType: TypeAlias = tuple[str, int, str, int, TeamAbbreviation, str, int, str, str, Outcome,
        int, float, float, float, float, float, float, float, float, float, float, float, float,
        float, float, float, float, float, float]

@dataclass
class NBAStatsAPIResultSet:
    name: str
    headers: list[str]
    rowSet: list[list]

    def generator(self, t: Type[NamedResultType]) -> Generator[NamedResultType]:
        for row in self.rowSet:
            args = {k.lower(): v for k, v in zip(self.headers, row)}
            yield t(**args)



NRTDescendant = TypeVar('NRTDescendant', bound=NamedResultType)
@dataclass
class NBAStatsAPIResponse:
    resource: str
    parameters: dict
    resultSets: list[NBAStatsAPIResultSet]

    def get_result_set(self, t: Type[NRTDescendant]) -> NBAStatsAPIResultSet:
        for rs in self.resultSets:
            print(rs)
            print(rs["name"])
            print(t.result_type_name())
            if rs["name"] == t.result_type_name():
                return NBAStatsAPIResultSet(**rs)
        raise ValueError(f"ResultSet {t.result_type_name()} not found in response")