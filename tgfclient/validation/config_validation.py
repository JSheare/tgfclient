"""A module containing the pydantic model used to validate the tgfclient application's config file"""
import logging
import pydantic
import re
from typing import Any, Annotated


def is_valid_log_level(value: Any) -> int:
    if not isinstance(value, str):
        raise ValueError('input should be a string corresponding to a log level.')

    level_mappings = logging.getLevelNamesMapping()
    value = value.upper()
    if value not in level_mappings:
        raise ValueError('input should be a string corresponding to a log level.')

    return level_mappings[value]


def is_valid_websocket_scheme(value: str) -> str:
    if not (value == 'ws' or value == 'wss'):
        raise ValueError('input must be a valid websocket scheme.')

    return value


def is_valid_host(value: str) -> str:
    valid = False
    # Checking if the value is a valid hostname
    if re.match(r'^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*'
                r'[A-Za-z0-9])$', value):
        valid = True

    # Checking if the value is a valid IPv4 address
    if not valid and re.match(r'^(((?!25?[6-9])[12]\d|[1-9])?\d\.?\b){4}$', value):
        valid = True

    if not valid:
        raise ValueError('input must be a valid host.')

    return value


def is_valid_port(value: int) -> int:
    if not 0 <= value <= 65535:
        raise ValueError('input should be a valid TCP port.')

    return value


def is_valid_directory_path(value: str) -> str:
    value.replace('\\', '/')
    if value != '' and value[-1] == '/':
        value = value[:-1]

    if value != '' and not re.match(r'^((/[a-zA-Z0-9 _-]+)+|/)$', value):
        raise ValueError('input should be a valid absolute directory path.')

    return value


def is_valid_instrument_name(value: str) -> str:
    if not value.isalnum():
        raise ValueError('input should consist of only letters and numbers.')

    value = value.upper()
    return value


class ClientModel(pydantic.BaseModel):
    log_level: Annotated[int, pydantic.BeforeValidator(is_valid_log_level)]
    ws_scheme: Annotated[str, pydantic.AfterValidator(is_valid_websocket_scheme)]
    dispatcher_host: Annotated[str, pydantic.AfterValidator(is_valid_host)]
    dispatcher_port: Annotated[int, pydantic.AfterValidator(is_valid_port)]
    instrument_data_directory: Annotated[str, pydantic.AfterValidator(is_valid_directory_path)]
    instrument_name: Annotated[str, pydantic.AfterValidator(is_valid_instrument_name)]
    instrument_password: str
    data_host: Annotated[str, pydantic.AfterValidator(is_valid_host)]
    data_host_public_key: pydantic.Base64Bytes
    data_port: Annotated[int, pydantic.AfterValidator(is_valid_port)]
    data_user: str
    data_password: str
    data_timeout_sec: pydantic.PositiveInt
