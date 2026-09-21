"""Structural ports implemented by the lookup runtime adapter."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.domain.lookup import LookupResponse


class LookupPort(Protocol):
    def try_lookup(self, query: str) -> LookupResponse | None: ...


LookupProvider = Callable[[], LookupPort]

__all__ = [
    "LookupPort",
    "LookupProvider",
]
