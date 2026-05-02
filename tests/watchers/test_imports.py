from __future__ import annotations

from pathlib import Path

import pytest

from spectate.observations import UNRESOLVED
from spectate.watchers.imports_ import ImportsWatcher


@pytest.fixture
def watcher() -> ImportsWatcher:
    return ImportsWatcher()


def _write(tmp_path: Path, src: str) -> Path:
    p = tmp_path / "sample.py"
    p.write_text(src, encoding="utf-8")
    return p


def _params(obs_iter) -> list[str]:
    return [o.parameter for o in obs_iter]


# ---------------------------------------------------------------------------
# Positive samples (8): all detection forms, including dotted/literal dynamic.
# ---------------------------------------------------------------------------


def test_simple_import(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "import requests\n")
    obs = list(watcher.observe(p))
    assert _params(obs) == ["requests"]
    assert obs[0].category == "imports"
    assert obs[0].file == p
    assert obs[0].line == 1


def test_dotted_import_emits_top_level(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "import a.b.c\n")
    assert _params(watcher.observe(p)) == ["a"]


def test_multi_alias_import(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "import os, sys, json\n")
    assert sorted(_params(watcher.observe(p))) == ["json", "os", "sys"]


def test_from_import(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "from requests import get\n")
    assert _params(watcher.observe(p)) == ["requests"]


def test_from_dotted_import(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "from google.cloud import storage\n")
    assert _params(watcher.observe(p)) == ["google"]


def test_dunder_import_literal(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "m = __import__('numpy')\n")
    assert _params(watcher.observe(p)) == ["numpy"]


def test_importlib_import_module_literal(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "import importlib\nm = importlib.import_module('pandas')\n")
    params = _params(watcher.observe(p))
    assert "pandas" in params
    assert "importlib" in params  # the `import importlib` line itself


def test_dunder_import_dotted_literal(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "__import__('a.b.c')\n")
    assert _params(watcher.observe(p)) == ["a"]


# ---------------------------------------------------------------------------
# Stdlib vs third-party (5): tag correctness.
# ---------------------------------------------------------------------------


def test_stdlib_tagged(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "import os\n")
    obs = list(watcher.observe(p))
    assert obs[0].tags == ("stdlib",)


def test_third_party_untagged(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "import requests\n")
    obs = list(watcher.observe(p))
    assert obs[0].tags == ()


def test_stdlib_from_import(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "from pathlib import Path\n")
    obs = list(watcher.observe(p))
    assert obs[0].tags == ("stdlib",)


def test_mixed_stdlib_and_third_party(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "import os\nimport requests\nimport json\nimport pandas\n")
    obs = sorted(watcher.observe(p), key=lambda o: o.parameter)
    by = {o.parameter: o.tags for o in obs}
    assert by["os"] == ("stdlib",)
    assert by["json"] == ("stdlib",)
    assert by["requests"] == ()
    assert by["pandas"] == ()


def test_dotted_stdlib_top_level_tagged(watcher: ImportsWatcher, tmp_path: Path) -> None:
    # collections.abc → top-level `collections`, which is stdlib.
    p = _write(tmp_path, "from collections.abc import Iterable\n")
    obs = list(watcher.observe(p))
    assert obs[0].parameter == "collections"
    assert obs[0].tags == ("stdlib",)


# ---------------------------------------------------------------------------
# Negative samples (3): no imports.
# ---------------------------------------------------------------------------


def test_empty_file(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "")
    assert list(watcher.observe(p)) == []


def test_no_imports_only_code(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "x = 1\ndef f():\n    return x + 1\n")
    assert list(watcher.observe(p)) == []


def test_string_containing_import_keyword(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "s = 'import requests'\n")
    assert list(watcher.observe(p)) == []


# ---------------------------------------------------------------------------
# Unresolved (3): dynamic args.
# ---------------------------------------------------------------------------


def test_dynamic_dunder_import(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "name = 'requests'\nm = __import__(name)\n")
    obs = [o for o in watcher.observe(p) if o.is_unresolved]
    assert len(obs) == 1
    assert obs[0].parameter == UNRESOLVED
    assert obs[0].tags == ()


def test_dynamic_importlib_import_module(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "import importlib\nname = 'numpy'\nm = importlib.import_module(name)\n",
    )
    obs = [o for o in watcher.observe(p) if o.is_unresolved]
    assert len(obs) == 1
    assert obs[0].parameter == UNRESOLVED
    assert obs[0].tags == ()


def test_dynamic_importlib_with_expression(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "import importlib\nm = importlib.import_module('a' + 'b')\n",
    )
    obs = [o for o in watcher.observe(p) if o.is_unresolved]
    assert len(obs) == 1
    assert obs[0].parameter == UNRESOLVED


# ---------------------------------------------------------------------------
# Relative imports (2): skipped.
# ---------------------------------------------------------------------------


def test_relative_import_bare(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "from . import sibling\n")
    assert list(watcher.observe(p)) == []


def test_relative_import_with_module(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "from .subpkg import thing\nfrom ..pkg import other\n")
    assert list(watcher.observe(p)) == []


# ---------------------------------------------------------------------------
# Misc behavior.
# ---------------------------------------------------------------------------


def test_future_import_skipped(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "from __future__ import annotations\n")
    assert list(watcher.observe(p)) == []


def test_watcher_name() -> None:
    assert ImportsWatcher.name == "imports"


def test_registered_on_import() -> None:
    from spectate.observations import all_watchers

    assert any(w.name == "imports" for w in all_watchers())


def test_syntax_error_returns_empty(watcher: ImportsWatcher, tmp_path: Path) -> None:
    p = _write(tmp_path, "def f(:\n")
    assert list(watcher.observe(p)) == []
