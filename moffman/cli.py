# -*- coding: utf-8 -*-
"""
.. module: moffman.cli
   :synopsis: CLI interface
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import sys
import pkg_resources
import asyncio
import logging
import click
from onacol import ConfigManager, ConfigValidationError

from .moffman import MultiOfficeManager


DEFAULT_CONFIG_FILE = pkg_resources.resource_filename(
    "moffman", "default_config.yaml")


logger = logging.getLogger("moffman")


def global_exception_handler(loop, context):
    msg = f"{context.get('message', '')} : {context.get('exception', '')} @ " \
          f"{context.get('future','')}"
    logger.error("Exception caught at global level: %s", msg)


@click.command(context_settings=dict(
    ignore_unknown_options=True,
    allow_extra_args=True
))
@click.option("--config", type=click.Path(exists=True), default=None,
              help="Path to the configuration file.")
@click.option("--get-config-template", type=click.File("w"), default=None,
              help="Write default configuration template to the file.")
@click.pass_context
def main(ctx, config, get_config_template):
    """Console script for moffman."""
    # Instantiate config_manager
    config_manager = ConfigManager(
        DEFAULT_CONFIG_FILE,
        env_var_prefix="moffman",
        optional_files=[config] if config else []
    )

    # Generate configuration for the --get-config-template option
    # Then finish the application
    if get_config_template:
        config_manager.generate_config_example(get_config_template)
        sys.exit(0)

    # Load (implicit) environment variables
    config_manager.config_from_env_vars()

    # Parse all extra command line options
    config_manager.config_from_cli_args(ctx.args)

    # Validate the config
    try:
        config_manager.validate()
    except ConfigValidationError as cve:
        click.secho("<----------------Configuration problem---------------->",
                    fg='red')
        # Logging is not yet configured at this point.
        click.secho(str(cve), fg='red', err=True)
        sys.exit(1)
    # Asyncio loop setup
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(global_exception_handler)

    logging.basicConfig(level=getattr(
        logging, config_manager.config['general']['log_level']),
        format="%(asctime)s.%(msecs)03d [%(name)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout)

    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("sockjs").setLevel(logging.WARNING)

    click.secho("Running moffman application ..", fg='green')

    # Setup your main classes here
    _moffman = MultiOfficeManager(config_manager.config, loop=loop)

    try:
        # Start your app here
        _moffman.start()

        loop.run_forever()
    except KeyboardInterrupt:
        click.secho("<--------------- Shutting down ------------------->",
                    fg='red')
    except Exception as e:
        logger.exception(e)
    finally:
        try:
            # Stop and cleanup your app here
            _moffman.stop()

            loop.run_until_complete(asyncio.sleep(1.0))
            loop.close()
        except Exception as e:
            logger.exception("Error occured during shutdown : %s", e)
        click.secho("<--------------- Stopped ------------------->", fg='red')

    sys.exit(0)


if __name__ == "__main__":
    main()  # pragma: no cover
