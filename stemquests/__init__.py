
import requests

from .check_tor import *
from .tor_instance import *

logger = logging.getLogger(__name__)

# Disable warnings for requests
requests.packages.urllib3.disable_warnings() # pylint: disable=no-member
