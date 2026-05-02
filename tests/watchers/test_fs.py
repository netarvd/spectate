from __future__ import annotations

from pathlib import Path

from spectate.observations import UNRESOLVED, Observation
from spectate.watchers.fs import FsWatcher


def _run(tmp_path: Path, source: str) -> list[Observation]:
    f = tmp_path / "sample.py"
    f.write_text(source, encoding="utf-8")
    return sorted(FsWatcher().observe(f))


def _params(obs: list[Observation], category: str) -> list[str]:
    return [o.parameter for o in obs if o.category == category]


# ---------------------------------------------------------------------------
# Positive samples (>= 10), covering each entry point + mode classification
# ---------------------------------------------------------------------------


def test_open_default_mode_is_read(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("data.txt")\n')
    assert _params(obs, "fs.read") == ["data.txt"]
    assert _params(obs, "fs.write") == []


def test_open_explicit_r(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("a.txt", "r")\n')
    assert _params(obs, "fs.read") == ["a.txt"]


def test_open_rb(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("img.bin", "rb")\n')
    assert _params(obs, "fs.read") == ["img.bin"]


def test_open_rt(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("notes.md", "rt")\n')
    assert _params(obs, "fs.read") == ["notes.md"]


def test_open_w(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("out.txt", "w")\n')
    assert _params(obs, "fs.write") == ["out.txt"]


def test_open_wb(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("out.bin", "wb")\n')
    assert _params(obs, "fs.write") == ["out.bin"]


def test_open_a_append(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("log.txt", "a")\n')
    assert _params(obs, "fs.write") == ["log.txt"]


def test_open_x_exclusive(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("new.txt", "x")\n')
    assert _params(obs, "fs.write") == ["new.txt"]


def test_open_a_plus_emits_both(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("log.txt", "a+")\n')
    assert _params(obs, "fs.read") == ["log.txt"]
    assert _params(obs, "fs.write") == ["log.txt"]


def test_open_r_plus_emits_both(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("rw.bin", "r+")\n')
    assert _params(obs, "fs.read") == ["rw.bin"]
    assert _params(obs, "fs.write") == ["rw.bin"]


def test_open_w_plus_emits_both(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("rw.bin", "w+")\n')
    assert _params(obs, "fs.read") == ["rw.bin"]
    assert _params(obs, "fs.write") == ["rw.bin"]


def test_open_mode_kwarg(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'open("k.txt", mode="w")\n')
    assert _params(obs, "fs.write") == ["k.txt"]


def test_pathlib_read_text(tmp_path: Path) -> None:
    src = "from pathlib import Path\nPath('cfg.yaml').read_text()\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.read") == ["cfg.yaml"]


def test_pathlib_read_bytes(tmp_path: Path) -> None:
    src = "from pathlib import Path\nPath('blob').read_bytes()\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.read") == ["blob"]


def test_pathlib_write_text(tmp_path: Path) -> None:
    src = "from pathlib import Path\nPath('out.txt').write_text('x')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["out.txt"]


def test_pathlib_write_bytes(tmp_path: Path) -> None:
    src = "from pathlib import Path\nPath('out.bin').write_bytes(b'x')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["out.bin"]


def test_pathlib_open_w(tmp_path: Path) -> None:
    src = "from pathlib import Path\nPath('o.txt').open('w')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["o.txt"]


def test_pathlib_open_default_is_read(tmp_path: Path) -> None:
    src = "from pathlib import Path\nPath('o.txt').open()\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.read") == ["o.txt"]


def test_shutil_copy(tmp_path: Path) -> None:
    src = "import shutil\nshutil.copy('a', 'b')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["a"]


def test_shutil_rmtree(tmp_path: Path) -> None:
    src = "import shutil\nshutil.rmtree('build')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["build"]


def test_shutil_move(tmp_path: Path) -> None:
    src = "import shutil\nshutil.move('a.txt', 'b.txt')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["a.txt"]


def test_os_remove(tmp_path: Path) -> None:
    src = "import os\nos.remove('stale.txt')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["stale.txt"]


def test_os_unlink(tmp_path: Path) -> None:
    src = "import os\nos.unlink('stale.txt')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["stale.txt"]


def test_os_makedirs(tmp_path: Path) -> None:
    src = "import os\nos.makedirs('build/out')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["build/out"]


def test_os_rename(tmp_path: Path) -> None:
    src = "import os\nos.rename('a', 'b')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["a"]


def test_pathlib_chain_all_literals_resolves(tmp_path: Path) -> None:
    src = "from pathlib import Path\nopen(Path('/tmp') / 'cache.bin')\n"
    obs = _run(tmp_path, src)
    assert "/tmp/cache.bin" in _params(obs, "fs.read")


def test_ospath_join_all_literals_resolves(tmp_path: Path) -> None:
    src = "import os.path\nopen(os.path.join('/tmp', 'a.txt'))\n"
    obs = _run(tmp_path, src)
    assert "/tmp/a.txt" in _params(obs, "fs.read")


def test_trailing_slash_stripped(tmp_path: Path) -> None:
    src = "import os\nos.makedirs('build/')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.write") == ["build"]


# ---------------------------------------------------------------------------
# Negative samples (5)
# ---------------------------------------------------------------------------


def test_no_fs_calls(tmp_path: Path) -> None:
    obs = _run(tmp_path, "x = 1 + 2\nprint(x)\n")
    assert obs == []


def test_unrelated_method_named_open(tmp_path: Path) -> None:
    src = "class S:\n    def open(self): pass\nS().open()\n"
    obs = _run(tmp_path, src)
    assert obs == []


def test_string_with_open_word(tmp_path: Path) -> None:
    obs = _run(tmp_path, 's = "open(x)"\n')
    assert obs == []


def test_dict_lookup_not_fs(tmp_path: Path) -> None:
    obs = _run(tmp_path, 'd = {"path": "x"}\nv = d["path"]\n')
    assert obs == []


def test_subprocess_call_not_fs(tmp_path: Path) -> None:
    src = "import subprocess\nsubprocess.run(['ls', '-l'])\n"
    obs = _run(tmp_path, src)
    assert obs == []


# ---------------------------------------------------------------------------
# Unresolved (3)
# ---------------------------------------------------------------------------


def test_unresolved_variable_path(tmp_path: Path) -> None:
    src = "p = compute()\nopen(p, 'r')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.read") == [UNRESOLVED]


def test_unresolved_ospath_join_with_variable(tmp_path: Path) -> None:
    src = "import os.path\nbase = compute()\nopen(os.path.join(base, 'x.txt'))\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.read") == [UNRESOLVED]


def test_unresolved_pathlib_chain_with_variable(tmp_path: Path) -> None:
    src = "from pathlib import Path\nbase = compute()\nopen(Path(base) / 'foo')\n"
    obs = _run(tmp_path, src)
    assert _params(obs, "fs.read") == [UNRESOLVED]


# ---------------------------------------------------------------------------
# Watcher contract
# ---------------------------------------------------------------------------


def test_watcher_name() -> None:
    assert FsWatcher().name == "fs"


def test_watcher_handles_syntax_error(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (\n", encoding="utf-8")
    assert tuple(FsWatcher().observe(f)) == ()


def test_watcher_handles_missing_file(tmp_path: Path) -> None:
    assert tuple(FsWatcher().observe(tmp_path / "nope.py")) == ()


def test_observation_includes_file_and_line(tmp_path: Path) -> None:
    src = "\n\nopen('data.txt')\n"
    f = tmp_path / "x.py"
    f.write_text(src, encoding="utf-8")
    obs = list(FsWatcher().observe(f))
    assert len(obs) == 1
    assert obs[0].file == f
    assert obs[0].line == 3


def test_registered_on_import() -> None:
    # Force a re-import so register_watcher() runs against the freshly
    # cleared registry installed by the autouse fixture.
    import importlib
    import sys

    sys.modules.pop("spectate.watchers.fs", None)
    importlib.import_module("spectate.watchers.fs")

    from spectate.observations import all_watchers

    names = {w.name for w in all_watchers()}
    assert "fs" in names
