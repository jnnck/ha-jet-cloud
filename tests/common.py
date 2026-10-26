"""Shared test helpers."""

import json
from pathlib import Path

from custom_components.jet_cloud.api import DEFAULT_HOST

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def url(path: str) -> str:
    return f"{DEFAULT_HOST}{path}"


