"""Helper function to check if Tor is working.

Uses a request session to HTTP GET check.torproject.org,
checks if the response contains the string "Congratulations. This browser is configured to use Tor.".

Usage:
tor = TorInstance()
session = tor.create_requests_session()
if not check_tor(session):
    print("Tor is not working.")
    sys.exit(1)
"""

import requests


def check_tor(session: requests.Session) -> bool:
    """Check if Tor is working.

    Args:
        session (requests.Session): Requests session to check.

    Returns:
        bool: True if Tor is working, False otherwise.
    """
    with session.get("https://check.torproject.org") as tor_check:
        return "Congratulations. This browser is configured to use Tor." in tor_check.text
