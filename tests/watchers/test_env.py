from __future__ import annotations

from pathlib import Path

import pytest

from spectate.observations.observation import UNRESOLVED
from spectate.watchers.env import EnvWatcher


def _write(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "sample.py"
    p.write_text(source, encoding="utf-8")
    return p


def _observe(tmp_path: Path, source: str):
    return list(EnvWatcher().observe(_write(tmp_path, source)))


def test_name():
    assert EnvWatcher().name == "env"


# --- Positive samples (6) -----------------------------------------------------


def test_environ_subscript(tmp_path):
    obs = _observe(tmp_path, "import os\nos.environ['DATABASE_URL']\n")
    assert len(obs) == 1
    assert obs[0].category == "env.read"
    assert obs[0].parameter == "DATABASE_URL"
    assert obs[0].line == 2


def test_environ_get_no_default(tmp_path):
    obs = _observe(tmp_path, "import os\nos.environ.get('API_KEY')\n")
    assert [(o.parameter, o.line) for o in obs] == [("API_KEY", 2)]


def test_environ_get_with_default(tmp_path):
    obs = _observe(tmp_path, "import os\nos.environ.get('LOG_LEVEL', 'INFO')\n")
    assert [(o.parameter, o.line) for o in obs] == [("LOG_LEVEL", 2)]


def test_getenv_no_default(tmp_path):
    obs = _observe(tmp_path, "import os\nos.getenv('HOME')\n")
    assert [(o.parameter, o.line) for o in obs] == [("HOME", 2)]


def test_getenv_with_default(tmp_path):
    obs = _observe(tmp_path, "import os\nos.getenv('PORT', '8080')\n")
    assert [(o.parameter, o.line) for o in obs] == [("PORT", 2)]


def test_case_sensitive(tmp_path):
    obs = _observe(tmp_path, "import os\nos.environ['MyVar']\n")
    assert obs[0].parameter == "MyVar"


# --- Negative samples (3) -----------------------------------------------------


def test_no_env_access(tmp_path):
    src = "x = 1\ny = x + 2\nprint(y)\n"
    assert _observe(tmp_path, src) == []


def test_string_mention_only(tmp_path):
    src = '''msg = "we read os.environ in production"\nprint(msg)\n'''
    assert _observe(tmp_path, src) == []


def test_comment_mention_only(tmp_path):
    src = "# os.environ['SECRET'] would go here\nx = 1\n"
    assert _observe(tmp_path, src) == []


# --- Unresolved cases (3) -----------------------------------------------------


def test_dynamic_subscript_key(tmp_path):
    src = "import os\nname = 'X'\nos.environ[name]\n"
    obs = _observe(tmp_path, src)
    assert len(obs) == 1
    assert obs[0].parameter == UNRESOLVED
    assert obs[0].line == 3


def test_iteration_over_environ(tmp_path):
    src = "import os\nfor k, v in os.environ.items():\n    print(k, v)\n"
    obs = _observe(tmp_path, src)
    assert obs
    assert all(o.parameter == UNRESOLVED for o in obs)


def test_dict_comprehension_over_environ(tmp_path):
    src = "import os\nd = {k: v for k, v in os.environ.items()}\n"
    obs = _observe(tmp_path, src)
    assert obs
    assert all(o.parameter == UNRESOLVED for o in obs)


# --- Extra coverage for surfaced decisions ------------------------------------


def test_getenv_dynamic_var(tmp_path):
    obs = _observe(tmp_path, "import os\nname = 'X'\nos.getenv(name)\n")
    assert obs[0].parameter == UNRESOLVED


def test_setdefault_emits_read(tmp_path):
    obs = _observe(tmp_path, "import os\nos.environ.setdefault('LANG', 'C')\n")
    assert [(o.parameter, o.line) for o in obs] == [("LANG", 2)]


def test_load_dotenv_not_an_env_read(tmp_path):
    src = "from dotenv import load_dotenv\nload_dotenv()\n"
    assert _observe(tmp_path, src) == []


def test_for_loop_over_environ(tmp_path):
    src = "import os\nfor k in os.environ:\n    print(k)\n"
    obs = _observe(tmp_path, src)
    assert obs
    assert all(o.parameter == UNRESOLVED for o in obs)


def test_syntax_error_returns_empty(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("def (\n", encoding="utf-8")
    assert list(EnvWatcher().observe(p)) == []


def test_multiple_accesses_distinct_lines(tmp_path):
    src = (
        "import os\n"
        "a = os.environ['A']\n"
        "b = os.getenv('B')\n"
        "c = os.environ.get('C', 'x')\n"
    )
    obs = _observe(tmp_path, src)
    assert [(o.parameter, o.line) for o in obs] == [
        ("A", 2),
        ("B", 3),
        ("C", 4),
    ]


@pytest.mark.parametrize(
    "src",
    [
        "import os\nos.environ['X']\n",
        "import os\nos.getenv('X')\n",
    ],
)
def test_observation_carries_path(tmp_path, src):
    p = _write(tmp_path, src)
    obs = list(EnvWatcher().observe(p))
    assert obs[0].file == p
