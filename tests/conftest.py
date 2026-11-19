"""Tests never call the network: an empty key wins over the developer's local .env."""

import os

os.environ["XKIRO_API_KEY"] = ""
