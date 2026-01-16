from dataclasses import dataclass
from typing import Self, Type, TypeVar, Generator


class NamedResultType:
    @classmethod
    def result_type_name(cls: Type[Self]) -> str:
        return cls.__name__

    @classmethod
    def from_tuple(cls: Type[Self], data: tuple) -> Self:
        return cls(*data)


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
            if rs["name"] == t.result_type_name():
                return NBAStatsAPIResultSet(**rs)
        raise ValueError(f"ResultSet {t.result_type_name()} not found in response")