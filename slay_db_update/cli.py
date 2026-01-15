import click
from .jobs import job_runner
from .players import update as players_update
from .games import GamesUpdater

@click.group()
@click.version_option()
def cli():
    """
    """


@cli.command(name="players")
@job_runner("players")
def players(*args, **kwargs):
    players_update(*args, **kwargs)


@cli.command(name="games")
@job_runner("player_games")
def games(*args, **kwargs):
    """Wrapper command that calls the `games_update` function in `games.py`.

    The real work is implemented in `slay_db_update.games.update(db_conn)` so it can
    be imported and tested independently from the CLI. The decorator supplies the
    transactional `db_conn` argument.
    """

    inserted = GamesUpdater().update()
    click.echo(str(inserted))
