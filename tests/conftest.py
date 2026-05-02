from __future__ import annotations

from collections.abc import Iterator

import pytest

from spectate.observations.watcher import _REGISTRY


@pytest.fixture(autouse=True)
def _isolate_watcher_registry() -> Iterator[None]:
    snapshot = list(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.extend(snapshot)
