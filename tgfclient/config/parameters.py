"""A module containing parameters used by various parts of the tgfclient application."""
import datetime
import platformdirs


APPLICATION_NAME = 'tgfclient'
INVALID_TIME = datetime.datetime.fromtimestamp(0, datetime.UTC)
USER_CONFIG_PATH = str(platformdirs.user_config_path('tgfclient', appauthor=False))
CONFIG_FILE = 'tgfclient.ini'
LOG_PATH = str(platformdirs.user_log_path('tgfclient', appauthor=False))
MAX_LOG_SIZE_BYTES = 10000000
MAX_LOG_ROLLOVERS = 5
RUNTIME_PATH = str(platformdirs.user_runtime_path('tgfclient', appauthor=False))
PID_FILE = 'tgfclient.pid'
DATA_PATH = str(platformdirs.user_data_path('tgfclient', appauthor=False))
MEASUREMENTS_FILE = 'measurements.json'
MAX_MEASUREMENTS = 28
DAYS_FILE = 'days.json'
TRANSFER_FILE = 'TRANSFER_MARKER.file'
