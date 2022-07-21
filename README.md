# stemquests

Python Requests and Stem helper for making HTTP requests over Tor.

# Purpose

A Tor proxy and the Python [requests](https://pypi.org/project/requests/) package are difficult to work with. This package attempts to fix this issue by creating a module (TorInstance) that allows starting new Tor proxy processes using stem, then generating requests Sessions to send requests with.

# Usage

Simply import TorInstance, create the object, then call tor.get_session() to get a new requests session!

```
from stemquests import TorInstance

tor = TorInstance()
session = tor.get_session()

print(session.get('https://check.torproject.org').text)
```
