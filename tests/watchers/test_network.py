from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

import pytest

from spectate.observations import UNRESOLVED, Observation, clear_registry
from spectate.watchers.network import NetworkWatcher, _normalize_host


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterable[None]:
    clear_registry()
    yield
    clear_registry()


def _write(tmp_path: Path, source: str) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(source)
    return f


def _observe(tmp_path: Path, source: str) -> list[Observation]:
    return list(NetworkWatcher().observe(_write(tmp_path, source)))


# ---------------------------------------------------------------------------
# Positive samples (10): literal URL is detected and host is normalized.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected_host"),
    [
        (
            "import requests\nrequests.get('https://api.example.com/v1/users')\n",
            "api.example.com",
        ),
        (
            "import requests\nrequests.post(url='https://API.Example.com/x')\n",
            "api.example.com",
        ),
        (
            "import requests\nrequests.put('https://api.example.com:8080/v1')\n",
            "api.example.com",
        ),
        (
            "import requests\nrequests.delete('http://example.org/path')\n",
            "example.org",
        ),
        (
            "import httpx\nhttpx.get('https://www.python.org/')\n",
            "www.python.org",
        ),
        (
            "import httpx\nhttpx.patch('https://EXAMPLE.com/foo')\n",
            "example.com",
        ),
        (
            "import httpx\nhttpx.Client().get('https://api.foo.io/health')\n",
            "api.foo.io",
        ),
        (
            "import httpx\nhttpx.AsyncClient().post('https://svc.bar.net/op')\n",
            "svc.bar.net",
        ),
        (
            "from urllib.request import urlopen\nurlopen('https://docs.python.org/3/')\n",
            "docs.python.org",
        ),
        (
            "import socket\ns = socket.socket()\ns.connect(('cache.internal', 6379))\n",
            "cache.internal",
        ),
    ],
)
def test_positive_literal_calls(tmp_path: Path, source: str, expected_host: str) -> None:
    observations = _observe(tmp_path, source)
    assert len(observations) == 1
    obs = observations[0]
    assert obs.category == "network.outbound"
    assert obs.parameter == expected_host
    assert obs.line >= 1


# ---------------------------------------------------------------------------
# Negative samples (5): nothing is emitted.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "x = 1\ny = x + 2\n",
        "# requests.get('https://nope.example.com')\n",
        "url = 'https://example.com'\n",
        "def get(url):\n    return url\nget('https://example.com')\n",
        "class Thing:\n    def connect(self, addr):\n        pass\nThing().connect(('a', 1))\n",
    ],
)
def test_negative_no_emission(tmp_path: Path, source: str) -> None:
    assert _observe(tmp_path, source) == []


# ---------------------------------------------------------------------------
# Unresolved samples (3): structurally a network call but host is non-literal.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import requests\nURL = build()\nrequests.get(URL)\n",
        "import httpx\nhost = compute()\nhttpx.get(f'https://{host}/path')\n",
        "from urllib.request import urlopen\nu = make_url()\nurlopen(u)\n",
    ],
)
def test_unresolved_dynamic_arguments(tmp_path: Path, source: str) -> None:
    observations = _observe(tmp_path, source)
    assert len(observations) == 1
    assert observations[0].parameter == UNRESOLVED


def test_session_via_variable_is_unresolved(tmp_path: Path) -> None:
    source = "import requests\ns = requests.Session()\ns.get('https://api.example.com/users')\n"
    observations = _observe(tmp_path, source)
    assert len(observations) == 1
    assert observations[0].parameter == UNRESOLVED


# ---------------------------------------------------------------------------
# Hostname normalization round-trip.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://api.example.com/v1/users", "api.example.com"),
        ("https://API.Example.com:8080/v1", "api.example.com"),
        ("http://example.org", "example.org"),
        ("https://sub.domain.example.io/", "sub.domain.example.io"),
        ("https://x.y.z:443/path?q=1#frag", "x.y.z"),
    ],
)
def test_normalize_host_matches_urlparse(url: str, expected: str) -> None:
    assert _normalize_host(url) == expected
    assert urlparse(url).hostname is not None
    assert _normalize_host(url) == urlparse(url).hostname.lower()


def test_normalize_host_returns_unresolved_for_garbage() -> None:
    assert _normalize_host("not a url with spaces") == UNRESOLVED


def test_observe_handles_syntax_error(tmp_path: Path) -> None:
    f = tmp_path / "bad.py"
    f.write_text("def broken(:\n")
    assert list(NetworkWatcher().observe(f)) == []


def test_module_registers_watcher() -> None:
    import importlib

    import spectate.watchers.network as mod
    from spectate.observations import all_watchers

    clear_registry()
    importlib.reload(mod)
    names = [w.name for w in all_watchers()]
    assert "network" in names


def test_emits_per_call_site(tmp_path: Path) -> None:
    source = (
        "import requests\n"
        "requests.get('https://a.example.com/')\n"
        "requests.post('https://b.example.com/')\n"
    )
    observations = _observe(tmp_path, source)
    assert [o.parameter for o in observations] == ["a.example.com", "b.example.com"]
    assert observations[0].line == 2
    assert observations[1].line == 3
