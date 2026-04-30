"""A module containing parameters used by various parts of the tgfclient application."""
import datetime


INVALID_TIME = datetime.datetime.fromtimestamp(0, datetime.UTC)
APP_NAME = 'tgfclient'
CONFIG_FILE = 'tgfclient.ini'
MAX_LOG_SIZE_BYTES = 10000000
MAX_LOG_ROLLOVERS = 5
MEASUREMENTS_FILE = 'measurements.json'
MAX_MEASUREMENTS = 10
DAYS_FILE = 'days.json'
TRANSFER_FILE = 'TRANSFER_MARKER.file'
