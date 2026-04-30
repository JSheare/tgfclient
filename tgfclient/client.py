"""A module containing classes that implement the tgfclient application's main functionality."""
from __future__ import annotations

import datetime
import json
import logging
import re
import paramiko
import pathlib
import platformdirs
import psutil
import time
import websockets
from dataclasses import dataclass
from enum import IntEnum
from stat import S_ISDIR, S_ISREG
from types import SimpleNamespace
from typing import Dict, List, Set, Tuple
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

import tgfclient.config.parameters as params
from tgfclient.helpers.helper_funcs import read_json_file, write_json_file
from tgfclient.startup.configure_logging import configure_logging
from tgfclient.startup.read_config import read_config
from tgfclient.validation.config_validation import ClientModel


class Measurements:
    """A helper class that keeps track of data transfer rate measurements for the application."""
    def __init__(self, measured_rates: List[float], timestamps: List[datetime.datetime]) -> None:
        self.measured_rates = measured_rates
        self.timestamps = timestamps

    def __len__(self):
        return len(self.measured_rates)

    @classmethod
    def from_json_dict(cls, json_dict: Dict[str, List[float | str]]) -> Measurements:
        """Converts a JSON-serializable dictionary back into a Measurements instance."""
        measured_rates = json_dict['measured_rates'].copy()
        timestamps = []
        for i in range(len(json_dict['timestamps'])):
            timestamps.append(datetime.datetime.fromisoformat(json_dict['timestamps'][i]))

        return cls(measured_rates, timestamps)

    def to_json_dict(self) -> Dict[str, List[float | str]]:
        """Returns the Measurements instance as a JSON-serializable dictionary."""
        raw_measurements = dict()
        raw_measurements['measured_rates'] = self.measured_rates.copy()
        raw_timestamps = []
        for i in range(len(self.timestamps)):
            raw_timestamps.append(self.timestamps[i].isoformat())

        raw_measurements['timestamps'] = raw_timestamps
        return raw_measurements

    def add_measurement(self, measured_rate: float) -> None:
        self.measured_rates.append(measured_rate)
        self.timestamps.append(datetime.datetime.now(datetime.UTC))

    def remove_measurement(self) -> None:
        self.measured_rates.pop(0)
        self.timestamps.pop(0)


@dataclass
class Day:
    """A helper class that keeps track of day directory info for the application."""
    day: str
    path: str
    size: int


class IDStatusCode(IntEnum):
    """An integer enum class containing status codes used by tgfserver's instrument dispatcher service."""
    OK = 0
    UNAUTHORIZED = 1
    INVALID_OPERATION = 2
    NO_TIME_AVAILABLE = 3
    TRANSFER_TOO_LARGE = 4


class DispatcherSession:
    """A class that implements an instrument-dispatcher-client exchange.

    Parameters
    ---------
    logger : logging.Logger
        The application's logger.

    Attributes
    ----------
    _session : SimpleNamespace
        A SimpleNamespace that keeps track of session info.

    """
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._session = SimpleNamespace()

    def _authenticated(self):
        """A helper function that returns True if the session has been authenticated with the server."""
        return hasattr(self._session, 'authenticated') and self._session.authenticated

    def authenticate(self, ws: websockets.sync.client.ClientConnection, instrument: str,
                     password: str) -> Tuple[bool, bool]:
        """A function that implements the authentication operation.

        Parameters
        ----------
        ws : websockets.sync.client.ClientConnection
            The websocket connection with the server.
        instrument : str
            The name of the instrument that the client represents.
        password : str
            The instrument's password.

        Returns
        -------
        Tuple[bool, bool]
            A bool indicating whether authentication was successful, and a bool indicating whether the interaction
            is over.

        """

        self._logger.debug('Sending authentication message to server.')
        message = {'type': 'authentication',
                   'payload': {'instrument': instrument, 'password': password}}
        ws.send(json.dumps(message))
        response = json.loads(ws.recv())
        if response['status'] == IDStatusCode.OK:
            self._logger.debug('Received successful authentication message from server.')
            self._session.authenticated = True
            return True, False
        else:
            self._logger.debug(f'Received unsuccessful authentication message from server. '
                               f'Reason: {response["payload"]["reason"]}.')
            self._session.authenticated = False
            return False, True

    def check_in(self, ws: websockets.sync.client.ClientConnection, storage_frac: float,
                 gps: bool) -> Tuple[bool, bool]:
        """A function that implements the check in operation.

        Parameters
        ----------
        ws : websockets.sync.client.ClientConnection
            The websocket connection with the server.
        storage_frac : float
            The storage usage fraction for the disk where data is located.
        gps : bool
            A flag indicating whether the GPS system is working.

        Returns
        -------
        Tuple[bool, bool]
            A bool indicating whether the check in was successful, and a bool indicating whether the interaction is
            over.

        """

        self._logger.debug('Sending check in message to server.')
        # Checking that we authenticated first
        if not self._authenticated():
            raise RuntimeError("failed to authenticate with sever before checking in.")

        message = {'type': 'check_in',
                   'payload': {'storage_frac': storage_frac, 'gps': gps}}
        ws.send(json.dumps(message))
        response = json.loads(ws.recv())
        if response['status'] == IDStatusCode.OK:
            self._logger.debug('Received successful check in message from server.')
            self._session.checked_in = True
            return True, False
        else:
            self._logger.debug(f'Received unsuccessful check in message from server. '
                               f'Reason: {response["payload"]["reason"]}.')
            self._session.checked_in = False
            return False, True

    def negotiate(self, ws: websockets.sync.client.ClientConnection, total_bytes: int,
                  measurements: Measurements) -> Tuple[bool, bool, datetime.datetime]:
        """A function that implements the file transfer negotiation operation.

        Parameters
        ----------
        ws : websockets.sync.client.ClientConnection
            The websocket connection with the server.
        total_bytes : int
            The total number of bytes to be transferred.
        measurements : Measurements
            The client's measured data transfer rates.

        Returns
        -------
        Tuple[bool, bool, datetime.datetime]
            A bool indicating whether the negotiation offer was accepted, a bool indicating whether the interaction
            is over, and a callback time. If the negotiation offer wasn't accepted, the returned time will be the
            Unix Epoch.

        """

        self._logger.debug(f'Sending file transfer negotiation message to server ({total_bytes} bytes to transfer).')
        # Checking that we authenticated first
        if not self._authenticated():
            raise RuntimeError('failed to authenticate with server before negotiating file transfer.')

        # Checking that we checked in first
        if not (hasattr(self._session, 'checked_in') and self._session.checked_in):
            raise RuntimeError('failed to check in with server before negotiating file transfer.')

        message = {'type': 'negotiation',
                   'payload': {'total_bytes': total_bytes,
                               'measured_rates': measurements.measured_rates,
                               'timestamps': measurements.timestamps}}
        ws.send(json.dumps(message))
        response = json.loads(ws.recv())
        if response['status'] == IDStatusCode.OK:
            self._logger.debug('Received successful file transfer negotiation message from server.')
            return True, True, response['payload']['callback_time']
        else:
            self._logger.debug(f'Received unsuccessful file transfer negotiation message from server. '
                               f'Reason: {response["payload"]["reason"]}.')
            if response['status'] == IDStatusCode.TRANSFER_TOO_LARGE:
                return False, False, datetime.datetime.fromtimestamp(0, datetime.UTC)
            else:
                return False, True, datetime.datetime.fromtimestamp(0, datetime.UTC)

    def callback(self, ws: websockets.sync.client.ClientConnection
                 ) -> Tuple[bool, bool, datetime.datetime, datetime.datetime, str]:
        """A function implementing the callback operation.

        Parameters
        ----------
        ws : websockets.sync.client.ClientConnection
            The websocket connection with the server.

        Returns
        -------
        Tuple[bool, bool, datetime.datetime, datetime, str]
            A bool indicating whether scheduling was successful, a bool indicating whether the interaction is over, a
            scheduled start time, a scheduled end time, and the path on the data computer where data goes. If
            scheduling was unsuccessful, then the start and end times will be the Unix Epoch and the path will be empty.

        """

        self._logger.debug(f'Sending callback message to server.')
        # Checking that we authenticated first
        if not self._authenticated():
            raise RuntimeError('failed to authenticate with server before negotiating file transfer.')

        message = {'type': 'callback',
                   'payload': {}}
        ws.send(json.dumps(message))
        response = json.loads(ws.recv())
        if response['status'] == IDStatusCode.OK:
            self._logger.debug('Received successful callback message from server.')
            payload = response['payload']
            return (True, True,
                    datetime.datetime.fromisoformat(payload['start_time']),
                    datetime.datetime.fromisoformat(payload['end_time']),
                    payload['path'])
        else:
            self._logger.debug(f'Received unsuccessful callback message from server. '
                               f'Reason: {response["payload"]["reason"]}.')
            invalid_time = datetime.datetime.fromtimestamp(0, datetime.UTC)
            return False, False, invalid_time, invalid_time, ''


class Client:
    """A class that implements the application's main functionality.

    Attributes
    ----------
    _config : ClientModel
        A pydantic model containing the application's config options.
    _logger : logging.Logger
        The application's logger.
    _measurements : Measurements
        The application's measured data transfer rates.
    _days_transferred : Set[str]
        The application's record of days that have already been transferred.

    """

    def __init__(self) -> None:
        self._config = ClientModel(**dict(read_config().items(params.APP_NAME)))
        self._logger = logging.getLogger(params.APP_NAME)
        self._logger.setLevel(self._config.log_level)
        self._measurements = self._read_measurements()
        self._days_transferred = self._read_days_transferred()

    def _configure_module_loggers(self) -> None:
        """A helper function that configures the loggers of the modules used by the class."""
        logging.getLogger('websockets.client').setLevel(self._config.log_level)
        logging.getLogger('paramiko').setLevel(self._config.log_level)

    @staticmethod
    def _read_measurements() -> Measurements:
        """A helper function that reads the measured data transfer rates from a file."""
        measurements_file = (f'{platformdirs.user_data_path(params.APP_NAME, appauthor=False)}/'
                             f'{params.MEASUREMENTS_FILE}')
        if pathlib.Path(measurements_file).is_file():
            raw_measurements = read_json_file(measurements_file)

            return Measurements.from_json_dict(raw_measurements)

        return Measurements([], [])

    def _write_measurements(self) -> None:
        """A helper function that writes the measured data transfer rates to a file."""
        path = pathlib.Path(platformdirs.user_data_path(params.APP_NAME, appauthor=False))
        if not path.is_dir():
            path.mkdir(parents=True)

        measurements_file = f'{path}/{params.MEASUREMENTS_FILE}'
        write_json_file(self._measurements.to_json_dict(), measurements_file)

    @staticmethod
    def _read_days_transferred() -> Set[str]:
        """A helper function that reads the record of already transferred days from a file."""
        days_file = f'{platformdirs.user_data_path(params.APP_NAME, appauthor=False)}/{params.DAYS_FILE}'
        if pathlib.Path(days_file).is_file():
            return set(read_json_file(days_file))

        return set()

    def _write_days_transferred(self) -> None:
        """A helper function that writes the record of already transferred days to a file."""
        path = pathlib.Path(platformdirs.user_data_path(params.APP_NAME, appauthor=False))
        if not path.is_dir():
            path.mkdir(parents=True)

        days_file = f'{path}/{params.DAYS_FILE}'
        write_json_file(list(self._days_transferred), days_file)

    def _get_new_days(self) -> Dict[str, Day]:
        """A helper function that returns a dictionary containing information about days that need to be transferred."""
        new_days = dict()
        all_days = set()
        # Getting a list of all day the day directories that currently exist
        day_dirs = [str(d) for d in
                    pathlib.Path(self._config.instrument_data_directory).rglob('[0-9][0-9][0-9][0-9][0-9][0-9]')]

        # Checking each day directory
        for day_dir in day_dirs:
            day = day_dir[-6:]
            all_days.add(day)

            # Adding days that are new and not empty to the set
            if day not in self._days_transferred:
                total_size = 0
                for item in pathlib.Path(day_dir).glob(f'{day_dir}/*'):
                    if item.is_file():
                        total_size += item.stat().st_size

                if total_size > 0:
                    new_days[day] = Day(day, day_dir, total_size)

        # Updating days transferred to include only existing days
        self._days_transferred = all_days.intersection(self._days_transferred)
        self._write_days_transferred()

        return new_days

    @staticmethod
    def _get_storage_usage(path: str) -> float:
        """A helper function that returns the storage usage fraction for the disk where data is located."""
        return psutil.disk_usage(path).percent * 0.01

    @staticmethod
    def _get_gps_status() -> bool:
        """A helper function that returns the status of the GPS system as a bool."""
        return True

    def _first_interaction(self, new_days) -> datetime.datetime:
        """A function that implements the application's first interaction with the server. During this interaction, the
        application authenticates, checks in, and attempts to negotiate a spot on the file transfer waitlist.

        Parameters
        ----------
        new_days : Dict[str, Day]
            A dictionary containing information about days that need to be transferred.

        Returns
        -------
        datetime.datetime
            The time to call back at for a scheduled file transfer time. If a waitlist spot couldn't be negotiated, then
            Unix Epoch will be returned.

        """

        try:
            with (connect(f'{self._config.ws_scheme}://{self._config.dispatcher_host}:{self._config.dispatcher_port}')
                  as ws):
                session = DispatcherSession(self._logger)
                try:
                    # Authenticating with the server
                    success, stop = session.authenticate(ws, self._config.instrument_name,
                                                         self._config.instrument_password)
                    if not success:
                        self._logger.info(f'Failed to authenticate with server.')
                        return params.INVALID_TIME

                    # Checking in with the server
                    success, stop = session.check_in(ws,
                                                     self._get_storage_usage(self._config.instrument_data_directory),
                                                     self._get_gps_status())
                    if not success:
                        self._logger.info(f'Failed to check in with server.')
                        return params.INVALID_TIME

                    # Attempting to get on the transfer scheduling waitlist
                    # Calculating the total number of bytes to transfer and making an ordered list of days in case we
                    # need to remove some later
                    total_bytes = 0
                    ordered_days = []
                    for day in new_days:
                        total_bytes += new_days[day].size
                        ordered_days.append(day)

                    ordered_days.sort()
                    while True:
                        success, stop, callback_time = session.negotiate(ws, total_bytes, self._measurements)
                        if success:
                            self._logger.info('Successfully registered on scheduling waitlist.')
                            return callback_time
                        else:
                            if stop:
                                self._logger.info('Failed to register on scheduling waitlist. No time available.')
                                return params.INVALID_TIME

                            # Removing the most recent day from the total
                            day = ordered_days[-1]
                            self._logger.debug(f'Removing {day} from transfer list.')
                            total_bytes -= new_days[day]
                            new_days.pop(day)
                            ordered_days.pop()

                            if len(new_days) == 0:
                                self._logger.info('Failed to register on scheduling waitlist. No days left to '
                                                  'transfer.')

                except KeyError:
                    self._logger.error('Server sent an improperly formed message that could not be interpreted.')
                    ws.close(code=1003, reason='Improperly formed message')
                except Exception:
                    self._logger.exception('Encountered an exception when interacting with server:')
                    ws.close(code=1001)

        except WebSocketException:
            self._logger.exception('Encountered a websocket exception when interacting with server:')
        except ConnectionRefusedError:
            self._logger.error('Failed to connect to server.')
        except TimeoutError:
            self._logger.error('Connection with server timed out.')

        return params.INVALID_TIME

    def _second_interaction(self) -> Tuple[datetime.datetime, datetime.datetime, str]:
        """A function that implements the application's second interaction with the server. During this interaction, the
        application authenticates and attempts to retrieve its scheduled file transfer time.

        Returns
        -------
        Tuple[datetime.datetime, datetime.datetime, str]
            The start time of the scheduled file transfer, the end time of the scheduled file transfer, and the
            path on the data computer where data should go. If scheduling was unsuccessful, then start and end times
            will be the Unix Epoch and the path will be empty.

        """

        try:
            with (connect(f'{self._config.ws_scheme}://{self._config.dispatcher_host}:{self._config.dispatcher_port}')
                  as ws):
                session = DispatcherSession(self._logger)
                try:
                    success, stop = session.authenticate(ws, self._config.instrument_name,
                                                         self._config.instrument_password)
                    if not success:
                        self._logger.info(f'Failed to authenticate with server.')
                        return params.INVALID_TIME, params.INVALID_TIME, ''

                    success, stop, start_time, end_time, path = session.callback(ws)
                    if not success:
                        self._logger.info('Failed to secure a transfer time slot.')
                    else:
                        self._logger.info(f'Secured a transfer time slot from {start_time} to {end_time}.')
                        return start_time, end_time, path

                except KeyError:
                    self._logger.error('Server sent an improperly formed message that could not be interpreted.')
                    ws.close(code=1003, reason='Improperly formed message')
                except Exception:
                    self._logger.exception('Encountered an exception when interacting with server:')
                    ws.close(code=1001)

        except WebSocketException:
            self._logger.exception('Encountered a websocket exception when interacting with server:')
        except ConnectionRefusedError:
            self._logger.error('Failed to connect to server.')
        except TimeoutError:
            self._logger.error('Connection with server timed out.')

        return params.INVALID_TIME, params.INVALID_TIME, ''

    @staticmethod
    def _is_already_transferred(sftp: paramiko.SFTPClient, remote_path: str) -> bool:
        """A helper function that returns True if a day has already been transferred to the data computer."""
        items = sftp.listdir_attr(remote_path)
        if len(items) == 0:
            return False

        for item in items:
            if S_ISREG(item.st_mode) and item.filename == params.TRANSFER_FILE:
                return False

        return True

    def _remove_already_transferred(self, sftp: paramiko.SFTPClient, remote_path: str,
                                    new_days: Dict[str, Day]) -> None:
        """A helper function that removes already-transferred days from the transfer info."""
        # Getting a list of days present on the data computer
        remote_days = dict()
        for item in sftp.listdir_attr(remote_path):
            if S_ISDIR(item.st_mode) and re.match(r'^[0-9]{6}$', item.filename):
                remote_days[item.filename] = f'{remote_path}/{item.filename}'

        overlap = set(new_days).intersection(remote_days)
        if len(overlap) > 0:
            for day in overlap:
                # Removing days that have already been transferred
                if self._is_already_transferred(sftp, remote_days[day]):
                    self._logger.debug(f'{day} was already transferred. Removing from transfer list.')
                    new_days.pop(day)
                    self._days_transferred.add(day)
                    self._write_days_transferred()

    def _transfer_day(self, sftp: paramiko.SFTPClient, end_time: datetime.datetime, day: Day,
                      remote_path: str) -> float:
        """A helper function that transfers a single day to the data computer."""
        remote_dir = f'{remote_path}/{day.day}'
        files = [f for f in pathlib.Path(day.path).iterdir() if f.is_file()]
        files_transferred = 0
        total_bytes = 0
        sftp.mkdir(remote_dir)
        # Making the transfer marker file
        with sftp.open(f'{remote_dir}/{params.TRANSFER_FILE}', 'w'):
            pass

        partial = False
        # Transferring each file one by one
        for file in files:
            self._logger.debug(f"Transferring '{file}'.")
            sftp.put(str(file), remote_dir)
            files_transferred += 1
            total_bytes += file.stat().st_size
            # Ending the transfer if we go past the end of the time slot
            if end_time <= datetime.datetime.now(datetime.UTC):
                partial = True
                break

        if not partial:
            # Deleting the transfer marker file
            sftp.remove(f'{remote_dir}/{params.TRANSFER_FILE}')

            # Recording the day as transferred
            self._days_transferred.add(day.day)
            self._write_days_transferred()

        self._logger.info(f'Successfully transferred {files_transferred}/{len(files)} files.')
        return total_bytes

    def _transfer_data(self, new_days: Dict[str, Day], end_time: datetime.datetime, remote_path: str) -> None:
        """A function that transfers all new days' data to the data computer.

        Parameters
        ----------
        new_days : Dict[str, Day]
            A dictionary containing information about days that need to be transferred.
        end_time : datetime.datetime
            The end time of the scheduled file transfer.
        remote_path : str
            The path on the data computer where data should go.

        """

        start = datetime.datetime.now(datetime.UTC)
        total_bytes = 0
        try:
            with paramiko.SSHClient() as session:
                session.connect(self._config.data_host, self._config.data_port, username=self._config.data_user,
                                password=self._config.data_password, timeout=self._config.data_timeout_sec)
                with session.open_sftp() as sftp:
                    # Checking for days that have already been transferred and removing them
                    self._remove_already_transferred(sftp, remote_path, new_days)
                    # Transferring the remaining days. Sorting to prioritize older days
                    for day in sorted(new_days):
                        self._logger.info(f'Transferring {day}.')
                        total_bytes += self._transfer_day(sftp, end_time, new_days[day], remote_path)
                        if end_time <= datetime.datetime.now(datetime.UTC):
                            self._logger.info('Stopping transfer. End time exceeded.')
                            break

        except Exception:
            self._logger.exception('Encountered an exception during SFTP session with data computer:')

        if total_bytes > 0:
            # Calculating the transfer rate and recording it
            transfer_rate = total_bytes / (datetime.datetime.now(datetime.UTC) - start).total_seconds()
            self._measurements.add_measurement(transfer_rate)
            self._write_measurements()


    def main(self) -> None:
        """A function that implements the application's main functionality."""
        configure_logging(self._config.log_level)
        self._configure_module_loggers()
        self._logger.info('Starting new client session.')
        try:
            # Getting a list of days to transfer
            new_days = self._get_new_days()

            if len(new_days) == 0:
                self._logger.info('No new data to transfer.')
                self._logger.info('Client session concluded.')
                return

            # Checking in with the server and attempting to register on the data transfer scheduling waitlist
            callback_time = self._first_interaction(new_days)

            # Waiting for callback time if we were successfully waitlisted
            if callback_time == params.INVALID_TIME:
                self._logger.info('Client session concluded.')
                return
            else:
                wait_time = (callback_time - datetime.datetime.now(datetime.UTC)).total_seconds()
                if wait_time > 0:
                    self._logger.debug('Waiting until callback time.')
                    time.sleep(wait_time)

            # Calling back and getting start time, end time, and data path
            start_time, end_time, remote_path = self._second_interaction()

            # Waiting until the transfer time if we were successfully scheduled
            if start_time == params.INVALID_TIME:
                self._logger.info('Client session concluded.')
                return
            else:
                wait_time = (start_time - datetime.datetime.now(datetime.UTC)).total_seconds()
                if wait_time > 0:
                    self._logger.debug('Waiting until transfer time.')
                    time.sleep(wait_time)

            # Transferring the data over SFTP
            self._transfer_data(new_days, end_time, remote_path)

            self._logger.info('Client session concluded.')
        except Exception:
            self._logger.exception('Encountered a fatal exception:')
            self._logger.info('Client session concluded.')
