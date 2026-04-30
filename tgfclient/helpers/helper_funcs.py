"""A module containing helper functions used by various parts of the tgfclient application."""
import json
from typing import Any


def read_json_file(file: str) -> Any:
    """A function that reads the given JSON file and returns it as the appropriate data structure.

    Parameters
    ----------
    file : str
        The file to be read.

    Returns
    -------
    Any
        The json file's contents.

    """

    with open(file, 'r') as f:
        result = json.load(f)

    return result


def write_json_file(data: Any, file: str) -> None:
        """A function that writes the given dictionary as JSON to the given file.

        Parameters
        ----------
        data : Any
            The JSON-serializable data to be written.

        file : str
            The name of the file to write the dictionary to as JSON.

        """

        with open(file, 'w') as f:
            json.dump(data, f)
