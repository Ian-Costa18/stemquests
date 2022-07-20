"""A class to start Tor processes with stem and create requests sessions with Tor.

Usage:
    from tor_requests import TorInstance

    tor = TorInstance()
    session = tor.get_session()

    print(session.get('https://check.torproject.org').text)
"""

import atexit
import logging
import subprocess
from time import sleep
from typing import Dict, Tuple

import psutil
import requests
import stem.process

from . import logger
from .check_tor import check_tor


class TorConnectionError(Exception):
    """Exception raised when Tor connection fails."""


# TODO: Maybe make this a subclass of requests.Session? How would it get a new requests session though?
class TorInstance(object):
    """
    Create a Tor process and requests sessions to connect to it.
    TorInstance.base_session can be used to make requests.
    TorInstance.get_session() can be used to get a new session.

    Args:
        socks_port (int): Port to run Tor on. Defaults to 9051.
        tor_path (str), optional: Path to Tor executable. Defaults to getting Tor from path.
        stem_config (Dict), optional: The arguments to run stem.process.launch_tor_with_config with. Defaults to None.
        |  tor_path and socks_port are optional if this is set.
        |  stem_config["tor_cmd"] is the same as and overwrites tor_path argument.
        |  stem_config["config"]["SocksPort"] is the same as and overwrites socks_port argument.
        kill_old_tor (bool): Whether or not to kill old Tor processes (True=Kill). Defaults to True.
        start_tor (bool): Whether or not to start Tor (True=Start). Defaults to True.
    Raises:
        AssertionError: If Tor is not working.
    """
    def __init__(self, socks_port: int=9051, tor_path: str=None, stem_config: Dict=None, kill_old_tor: bool=True):
        stem_config = {} if stem_config is None else stem_config
        self.tor_path = tor_path if stem_config.get("tor_cmd") is None else stem_config["tor_cmd"]
        self.port = socks_port if stem_config.get("config") is None\
                               or stem_config["config"].get("SocksPort") is None\
                               else int(stem_config["config"]["SocksPort"])
        # Initialize the current session number and current sessions dict
        self.current_session_number = 0
        self.current_sessions = {}

        # Add arguments to the stem_config
        if tor_path:
            stem_config["tor_cmd"] = self.tor_path
        if stem_config.get("config") is None:
            stem_config["config"] = {"SocksPort": str(self.port)}
        elif stem_config["config"].get("SocksPort") is None:
            stem_config["config"]["SocksPort"] = str(self.port)
        elif stem_config["config"]["SocksPort"] is not str:
            stem_config["config"]["SocksPort"] = str(stem_config["config"]["SocksPort"])

        self.tor_process = self._start_tor(stem_config, kill_old_tor)
        self.base_session = self._get_base_session()

    def _start_tor(self, stem_config: Dict, kill_old_tor: bool) -> subprocess.Popen:
        """
        Start the Tor process.

        Args:
            stem_config (Dict): The arguments to run stem.process.launch_tor_with_config with.
            kill_old_tor (bool): Whether or not to kill old Tor processes (True=Kill).

        Raises:
            OSError: Error if Tor is already running. Only raised if kill_old_tor is False.

        Returns:
            subprocess.Popen:  Tor process.
        """
        tor_launched, times_tried = False, 0
        while not tor_launched:
            try:
                # Only log config if logger is set to debug
                if logger.getEffectiveLevel() == logging.DEBUG:
                    logger.debug("Launching Tor on port %d with config: %s", self.port, str(stem_config))
                else:
                    logger.info("Launching Tor on port %d.", self.port)
                # Launch Tor with the specified configuration
                tor_process = stem.process.launch_tor_with_config(**stem_config)
                atexit.register(tor_process.kill) # Kill Tor on program exit
                logger.info("Successfully launched Tor on port %d.", self.port)
                tor_launched = True
                return tor_process
            except OSError as error:
                # Check to see if we can kill the old Tor process
                if not kill_old_tor:
                    # If not, log and raise the error
                    logger.error("Failed to start Tor (Tor is likely already running on this port): %s", error)
                    raise error

                # Search for the old Tor process and kill it
                for proc in psutil.process_iter():
                    # Check whether the process is Tor
                    if proc.name() in ["tor.exe", "tor"]:
                        proc.kill()
                logger.debug("Killed already running Tor process")
                times_tried += 1
                continue

    def stop_tor(self, tor_process: subprocess.Popen=None) -> bool:
        """
        Stop the Tor process. Checks to see if Tor is running and kills it if it is.

        Args:
            tor_process (subprocess.Popen): The Tor process to stop. Defaults to self.tor_process.

        Returns:
            bool: True if successful, False if the process is not alive.
        """
        tor_process = tor_process or self.tor_process
        if tor_process.is_alive():
            tor_process.kill()
            return True
        return False

    def _get_base_session(self, parent_session: requests.Session=None, max_tries: int=5) -> requests.Session:
        """
        Start a base session for the TorInstance. This ensures Tor is working and gives us a constant session to use for various requests.

        Args:
            max_tries (int): Maximum number of times to try to get a base session. Defaults to 5.

        Returns:
            requests.Session: The base session.
        """
        # Setup the default Tor session
        base_session = parent_session or requests.Session()
        base_session.proxies = {"http": f"socks5h://tor{self.current_session_number}:tor{self.current_session_number}@localhost:{self.port}",
                                "https": f"socks5h://tor{self.current_session_number}:tor{self.current_session_number}@localhost:{self.port}"}
        # Ensure Tor is working
        if not check_tor(base_session):
            if max_tries <= 0:
                err_msg = "Tor is not working for base session. Please check your Tor configuration and/or internet connection."
                logger.error(err_msg)
                raise TorConnectionError(err_msg)
            logger.error("Tor is not working for base session, retrying in 5 seconds...")
            sleep(5)
            self._get_base_session(base_session, max_tries=max_tries - 1)

        logger.info("Successfully started Tor base session!")
        # Increment the current session number
        self.current_sessions[self.current_session_number] = base_session
        self.current_session_number += 1

        return base_session

    def get_session(self, *args, **kwargs) -> requests.Session:
        """Alais for get_session_with_number()[0]. See TorInstance.get_session_with_number() for more information."""
        return self.get_session_with_number(*args, **kwargs)[0]

    def get_session_with_number(self, parent_session: requests.Session=None, max_tries: int=5) -> Tuple[requests.Session, int]:
        """
        Create a requests session with the specified configuration. Returns a tuple of the session and the current session number.

        Args:
            parent_session (requests.Session): The parent session to use.
            num_tries (int): The number of tries to create a new session, set to negative to allow more tries.

        Returns:
            requests.Session: A requests session with the specified proxy configuration.
            int: Session number.
        """
        # Initialize the parent session
        session = parent_session or self.base_session
        credentials = f'tor{self.current_session_number}'
        # Setup requests
        session.proxies = {"http": f"socks5h://{credentials}:{credentials}@localhost:{self.port}",
                          "https": f"socks5h://{credentials}:{credentials}@localhost:{self.port}"}
        self.current_sessions[self.current_session_number] = session
        if not check_tor(session):
            if max_tries <= 0:
                err_msg = f"Failed to connect to Tor on session #{self.current_session_number}, too many retrys."
                logger.error(err_msg)
                self.current_session_number += 1
                raise TorConnectionError(err_msg)
            logger.error("Tor is not working for new session (#%d), retrying in 5 seconds...", self.current_session_number)
            sleep(5)
            return self.get_session_with_number(session, max_tries=max_tries - 1)
        logger.info("Tor works for session #%d!", self.current_session_number)
        self.current_session_number += 1
        return session, self.current_session_number
