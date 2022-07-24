
import requests

from .check_tor import check_tor
from .tor_instance import TorConnectionError, TorInstance

# Disable warnings for requests
requests.packages.urllib3.disable_warnings() # pylint: disable=no-member
