import click
from .cli_tools import loudspeaker, wrap_module_with_decorator
from .players import update
loud_sh = wrap_module_with_decorator('sh', loudspeaker)

@click.group()
@click.version_option()
def cli():
    ""


@cli.command(name="players")
def players():
    update()
