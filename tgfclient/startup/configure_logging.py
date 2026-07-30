"""A module containing a function that sets up logging for the tgfclient application."""
import logging
import pathlib
import platformdirs
from logging import handlers

import tgfclient.config.parameters as params


def configure_logging(log_level: int) -> None:
    """A function that performs logging setup for the application.

    Parameters
    ----------
    log_level : int
        The level to set logging at as an integer.

    """

    logging.captureWarnings(True)
    # Configuring a handler on the root logger so that everything goes to the same log file.
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    log_directory = pathlib.Path(platformdirs.user_log_path(params.APPLICATION_NAME, appauthor=False))
    if not log_directory.is_dir():
        log_directory.mkdir(parents=True)

    handler = logging.handlers.RotatingFileHandler(
        filename=f'{log_directory}/{params.APPLICATION_NAME}.txt',
        encoding='utf-8',
        maxBytes=params.MAX_LOG_SIZE_BYTES,
        backupCount=params.MAX_LOG_ROLLOVERS)
    handler.setFormatter(logging.Formatter("{asctime} - {levelname} - {name} - {message}",
                                           style="{",
                                           datefmt="%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(handler)
