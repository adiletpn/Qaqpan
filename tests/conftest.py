"""Tests never call the network: an empty key wins over the developer's local .env."""

import os

os.environ["XKIRO_API_KEY"] = ""


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def daytime(monkeypatch):
    """Risk has a «night» signal (Almaty time): tests must not depend on when they run."""
    from datetime import datetime

    from api import risk
    monkeypatch.setattr(risk, "local_now", lambda: datetime(2026, 11, 20, 14, 0, tzinfo=risk.ALMATY))
