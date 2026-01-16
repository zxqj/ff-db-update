from sqlalchemy import delete

from slay_db_update.conf import Config

session = Config.get().get_session()
def test_gsr():
    delete()
