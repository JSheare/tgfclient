# Tgfclient
## A client application for the instruments of the UCSC TGF group.
### To install the application, run the following pip command:

    pip install tgfclient@git+https://github.com/JSheare/tgfclient

After installation, it's recommended that the following commands be executed before using the application:
- This command will make the user config file:

        tgfclient --setup

- And this command will validate the config file and report any issues. Run it after filling the file out:

        tgfclient --test_config

For a full list of application commands, use the help flag:

    tgfclient -h

And finally, to run the application, use the following command:

    tgfclient

## Config File Options:
- log_level: the application's log level.
- ws_scheme: the websocket scheme that the application will use when communicating with the server. Don't change this
  without good reason.
- dispatcher_host: the address of the server.
- dispatcher_port: the port user by the server's Instrument Dispatcher service.
- instrument_data_directory: the directory where data is located.
- instrument_name: the name of the instrument that the application will authenticate with the server as.
- instrument_password: the instrument's dispatcher password.
- data_host: the address of the data computer.
- data_host_public_key: the SSH public Ed25519 key of the data computer (used by the application for SFTP).
- data_port: the port that the data computer uses for SSH connections.
- data_user: the data computer user that the application will log in to the data computer as.
- data_password: the password for the data computer user.
- data_timeout_sec: the amount of time to wait for an SSH session to be established with the data computer.

On Linux, the user config file can be found at ~/.config/tgfclient/tgfclient.ini.

On Windows, the user config file can be found at C:/Users/your_user/AppData/Local/tgfclient/tgfclient.ini.