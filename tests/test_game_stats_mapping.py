import pytest
from datetime import date

from slay_db_update.NBAStatsModel import LeagueGameFinderResults, TeamAbbreviation, Outcome
from slay_db_update.game_stats import GameStats
from automapper import mapper


def make_sample_league_result() -> LeagueGameFinderResults:
    return LeagueGameFinderResults(
        season_id="22022",
        player_id=12345,
        player_name="Doe, John",
        team_id=1610612737,
        team_abbreviation=TeamAbbreviation.ATL,
        team_name="Atlanta Hawks",
        game_id='987654321',
        game_date="2022-10-19",
        matchup="ATL vs BOS",
        wl=Outcome.WIN,
        min=36,
        pts=25.0,
        fgm=9.0,
        fga=18.0,
        fg_pct=0.5,
        fg3m=2.0,
        fg3a=6.0,
        fg3_pct=0.333,
        ftm=5.0,
        fta=6.0,
        ft_pct=0.833,
        oreb=1.0,
        dreb=7.0,
        reb=8.0,
        ast=6.0,
        stl=1.0,
        blk=0.0,
        tov=2.0,
        pf=3.0,
        plus_minus=5.0,
    )


def test_league_result_maps_to_game_stats():
    league = make_sample_league_result()
    # map using py-automapper mapper.to(GameStats).map
    gs = mapper.to(GameStats).map(league)
    print(gs)
    assert gs is not None

    assert isinstance(gs, GameStats)
    assert gs.player_id == 12345
    #assert gs.game_id == str(987654321)
    assert gs.season_id == "22022"
    assert gs.pts == 25
    assert gs.fgm == 9
    assert gs.reb == 8
    assert gs.team_name == "Atlanta Hawks"
    # game_date should be left as string or converted depending on mapper config; accept either
    assert str(gs.game_date).startswith("2022")

