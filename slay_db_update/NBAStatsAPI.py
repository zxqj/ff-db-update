from json import JSONDecodeError
from typing import TypeVar, Iterable, Type, TypeVarTuple, Generator

from nba_api.stats.endpoints._base import Endpoint

from slay_db_update.NBAStatsModel import NBAStatsAPIResponse, NBAStatsAPIResultSet
from slay_db_update.utils import timed

T = TypeVar('T')


U = TypeVar('U', bound=Endpoint)
V = TypeVar('V')
def get_nba_stats_result[U, V](endpoint: U, t: Type[V]) -> Generator[V]:
    stats_resp = NBAStatsAPIResponse(**endpoint.get_dict())
    result_set: NBAStatsAPIResultSet = stats_resp.get_result_set(t)
    return result_set.generator(t)

E = TypeVar('E', bound=Endpoint)
ResultSetType = TypeVar('ResultSetType')
def invoke_endpoint(class_ref: Type[E], t: Type[ResultSetType], logger, **kwargs) -> Generator[ResultSetType]:
    name = class_ref.__name__
    def f(**_kwargs):
        # Avoid printing huge kwargs directly; just show the names
        try:
            return class_ref(**_kwargs)
        except JSONDecodeError as e:
            argstr = ",".join([f"{k}: {str(v)[:100]}" for k, v in kwargs.items()])
            raise RuntimeError(f"JSON decode error invoking {name} with args {argstr}") from e

    invoker = timed(name, logger)(f)
    return get_nba_stats_result(invoker(**kwargs), t)
