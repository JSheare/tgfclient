"""A module containing the top level main function of the tgfclient application."""
import argparse
import configparser
import os
import pathlib
import psutil
import pydantic
import sys
from contextlib import contextmanager
from typing import Any, Generator

# Adds parent directory to sys.path. Necessary to make the imports below work when running this file as a script
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import tgfclient.config.parameters as params
from tgfclient.client import Client
from tgfclient.startup.read_config import read_config
from tgfclient.validation.config_validation import ClientModel


def test_config() -> None:
    """A function that parses and validates the application's config file and prints feedback about the process."""
    try:
        ClientModel(**dict(read_config().items(params.APPLICATION_NAME)))
        print('All config file options successfully validated.')
    except configparser.NoSectionError:
        print(f'Encountered error when parsing config file: no section for the application exists.')
    except pydantic.ValidationError as ex:
        print(f'Encountered error(s) when validating config file:')
        for error in ex.errors():
            loc = '.'.join([s for s in error['loc'] if isinstance(s, str)])
            if error['type'] == 'missing':
                print(f"Missing required field: {loc}.")
            else:
                print(f"Invalid input '{error['input']}' at {loc}. {error['msg']}")


def running_pid() -> int:
    """A function that returns the pid of the application, or -1 if it isn't currently running."""
    try:
        with (open(f'{params.RUNTIME_PATH}/{params.PID_FILE}', 'r')
              as file):
            # Checking to see if the pid in the file is still active
            pid = int(file.readline())
            if psutil.pid_exists(pid):
                return pid

        return -1
    except (OSError, FileNotFoundError, ValueError):
        return -1


@contextmanager
def pid_manager() -> Generator[None, Any, None]:
    """A generator responsible for creating and deleting the application's pid file."""
    # Making the file
    directory = pathlib.Path(params.RUNTIME_PATH)
    if not directory.is_dir():
        directory.mkdir(parents=True)

    with open(f'{directory}/{params.PID_FILE}', 'w') as file:
        file.write(str(os.getpid()))

    yield

    # Deleting the file
    try:
        os.remove(f'{directory}/{params.PID_FILE}')
    except Exception:
        pass


def main() -> None:
    """A function that serves as the top level call for the tgfclient application."""
    parser = argparse.ArgumentParser(prog=params.APPLICATION_NAME,
                                     description='A client application for the instruments of the UCSC TGF group')
    parser.add_argument('--setup', help='run the set up process for the application', action='store_true')
    parser.add_argument('--test-config', help='test that the config file contains valid options', action='store_true')

    args = parser.parse_args()

    # Handling any arguments
    has_args = False
    if args.setup:
        read_config()
        print(f'Made/updated config file at {params.USER_CONFIG_PATH}.')
        has_args = True

    if args.test_config:
        test_config()
        has_args = True

    if not has_args and running_pid() == -1:
        # Running the application
        try:
            client = Client()
        except pydantic.ValidationError:
            print(f'Encountered error(s) when validating config file. Use --test-config flag for details.')
            return
        except configparser.NoSectionError:
            print(f'Encountered error when parsing config file: no section for the application exists.')
            return
        except Exception as ex:
            print('Fatal exception encountered during startup.')
            print(f'{type(ex).__name__}: {ex}')
            return

        with pid_manager():
            client.main()


if __name__ == '__main__':
    main()
