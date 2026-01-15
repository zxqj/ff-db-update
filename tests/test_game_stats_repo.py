from pandas.core.interchange.dataframe_protocol import DataFrame
from sqlalchemy import delete
from sqlalchemy.sql.dml import DMLWhereBase

from slay_db_update.configuration import Config
from slay_db_update.game_stats import GameStats

session = Config.get().get_session()
def test_gsr():
    delete()
