import click

from slay_db_update.repo.game_stats_repo import GameStatsRepository
from slay_db_update.conf.job_tracker import track_job
from slay_db_update.core.players_updater import update as players_update
from slay_db_update.core.game_stats_updater import GameStatsUpdater
import warnings
from sqlalchemy import exc as sa_exc

@click.group()
@click.version_option()
def cli():
    """
    """


@cli.command(name="players")
@track_job("players")
def players():
    players_update()


@cli.command(name="games")
@track_job("player_games")
def games():
    """Wrapper command that calls the `games_update` function in `game_stats_updater.py`.

    The real work is implemented in `slay_db_update.games.update(db_conn)` so it can
    be imported and tested independently from the CLI. The decorator supplies the
    transactional `db_conn` argument.
    """
    with warnings.catch_warnings():
        # warning shows up during bulk insert, regarding there being no auto_increment on
        # either column defined as primary key in the GameStats sqlalchemy model.  Ignore it.
        warnings.simplefilter("ignore", category=sa_exc.SAWarning)
        GameStatsUpdater().update()


@cli.command(name="dupes")
def dupes():
    gsr = GameStatsRepository()
    click.echo(gsr.duplicates())