"""A module containing the top level main function of the tgfclient application."""
import argparse
import configparser
import os
import platformdirs
import pydantic
import sys

# Adds parent directory to sys.path. Necessary to make the imports below work when running this file as a script
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import tgfclient.config.parameters as params
from tgfclient.client import Client
from tgfclient.startup.read_config import read_config
from tgfclient.validation.config_validation import ClientModel


def main() -> None:
    """A function that serves as the top level call for the tgfclient application."""
    parser = argparse.ArgumentParser(prog=params.APPLICATION_NAME,
                                     description='A client application for the instruments of the UCSC TGF group')
    parser.add_argument('--setup', help='run the set up process for the application', action='store_true')
    parser.add_argument('--test_config', help='test that the config file contains valid options', action='store_true')
    args = parser.parse_args()
    # Handling any arguments
    if args.setup:
        read_config()
        print(f'Made/updated config file at {platformdirs.user_config_path(params.APPLICATION_NAME, appauthor=False)}.')
        return
    if args.test_config:
        try:
            ClientModel(**dict(read_config().items(params.APPLICATION_NAME)))
            print('All config file options successfully validated.')
            return
        except pydantic.ValidationError as ex:
            print(f'Encountered error(s) when validating config file:')
            missing_fields = 0
            for error in ex.errors():
                if error['type'] == '':
                    missing_fields += 1
                else:
                    print(f"Invalid input '{error['input']}'. {error['msg']}")

            if missing_fields > 0:
                print(f'{missing_fields} missing fields.')

            return
        except configparser.NoSectionError:
            print(f'Encountered error when parsing config file: no section for the application exists.')
            return

    # Running the application
    try:
        client = Client()
    except pydantic.ValidationError:
        print(f'Encountered error(s) when validating config file. Use --test_config flag for details.')
        return
    except configparser.NoSectionError:
        print(f'Encountered error when parsing config file: no section for the application exists.')
        return
    except Exception as ex:
        print('Fatal exception encountered during startup.')
        print(f'{type(ex).__name__}: {ex}')
        return

    client.main()


if __name__ == '__main__':
    main()
