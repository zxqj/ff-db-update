from slay_db_update.api_cli.nba_season import NBASeason
from datetime import datetime, date
def test_nbaseason():
    assert NBASeason(datetime(2026, 1, 13, 3, 37, 22, 123509)) == 2025

    assert NBASeason(datetime(2025,10,1, 3, 37, 22, 123509)) == 2025

    assert NBASeason(date(2026, 1, 13)) == 2025

    assert NBASeason(date(2025,10,1)) == 2025

    assert NBASeason("2025-26") == 2025

    assert NBASeason("25-26") == 2025

    assert NBASeason("2025") == 2025

    assert NBASeason("2026-01-13T3:37:22") == 2025

    assert NBASeason("2025-10-01T3:37:22") == 2025

    assert NBASeason("10/01/2025") == 2025

    assert NBASeason("January 13, 2026") == 2025

    assert str(NBASeason("2025")) == "2025-26"