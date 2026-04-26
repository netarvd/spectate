from __future__ import annotations

from pathlib import Path

import pytest

from spectate.observations.observation import UNRESOLVED
from spectate.watchers.subprocess_ import SubprocessWatcher


@pytest.fixture
def watcher() -> SubprocessWatcher:
    return SubprocessWatcher()


def _write(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "sample.py"
    p.write_text(source)
    return p


def _params(watcher: SubprocessWatcher, path: Path) -> list[str]:
    return [obs.parameter for obs in watcher.observe(path)]


def test_name(watcher: SubprocessWatcher) -> None:
    assert watcher.name == "subprocess"


# ---- positive: list-style ---------------------------------------------------


def test_subprocess_run_list(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import subprocess\nsubprocess.run(['git', 'clone', 'x'])\n")
    assert _params(watcher, path) == ["git"]


def test_subprocess_popen_list(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import subprocess\nsubprocess.Popen(['/usr/bin/ls', '-la'])\n")
    obs = list(watcher.observe(path))
    assert [o.parameter for o in obs] == ["ls"]
    assert obs[0].file == path
    assert obs[0].line == 2


def test_subprocess_check_call_list(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import subprocess\nsubprocess.check_call(['rm', '-rf', '/tmp/x'])\n")
    assert _params(watcher, path) == ["rm"]


def test_subprocess_check_output_list(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import subprocess\nsubprocess.check_output(['curl', 'https://x'])\n")
    assert _params(watcher, path) == ["curl"]


# ---- positive: shell-string -------------------------------------------------


def test_subprocess_call_shell_string(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "import subprocess\nsubprocess.call('git pull origin main', shell=True)\n",
    )
    assert _params(watcher, path) == ["git"]


def test_os_system_shell_string(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import os\nos.system('/usr/local/bin/git pull')\n")
    assert _params(watcher, path) == ["git"]


def test_os_execvp_basename(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import os\nos.execvp('/usr/bin/python3', ['python3', '-V'])\n")
    assert _params(watcher, path) == ["python3"]


def test_os_popen(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import os\nos.popen('ls -la')\n")
    assert _params(watcher, path) == ["ls"]


# ---- negative: should produce no observations -------------------------------


def test_unrelated_call(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "print('hello')\nfoo.bar(['git', 'pull'])\n")
    assert _params(watcher, path) == []


def test_subprocess_attr_lookup_no_call(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import subprocess\nx = subprocess.PIPE\n")
    assert _params(watcher, path) == []


def test_user_defined_run(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "class Thing:\n    def run(self, args): pass\nThing().run(['git'])\n",
    )
    assert _params(watcher, path) == []


# ---- unresolved -------------------------------------------------------------


def test_unresolved_variable_args(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(tmp_path, "import subprocess\nargs = ['git']\nsubprocess.run(args)\n")
    assert _params(watcher, path) == [UNRESOLVED]


def test_unresolved_computed_shell_string(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "import os\ncmd = 'git ' + 'pull'\nos.system(cmd)\n",
    )
    assert _params(watcher, path) == [UNRESOLVED]


def test_unresolved_computed_first_element(watcher: SubprocessWatcher, tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "import subprocess\nbinary = 'git'\nsubprocess.run([binary, 'pull'])\n",
    )
    assert _params(watcher, path) == [UNRESOLVED]


# ---- edge cases surfaced in PR ----------------------------------------------


def test_shell_true_with_list_takes_element_zero(
    watcher: SubprocessWatcher, tmp_path: Path
) -> None:
    """Decision: with shell=True and a list, take element[0] (sh), not the inner cmd."""
    path = _write(
        tmp_path,
        "import subprocess\nsubprocess.run(['sh', '-c', 'git pull'], shell=True)\n",
    )
    assert _params(watcher, path) == ["sh"]


def test_registered_on_import() -> None:
    import importlib

    import spectate.watchers.subprocess_ as subprocess_module
    from spectate.observations import all_watchers

    importlib.reload(subprocess_module)
    assert any(w.name == "subprocess" for w in all_watchers())
