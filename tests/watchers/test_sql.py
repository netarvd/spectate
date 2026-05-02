from __future__ import annotations

from pathlib import Path

import pytest

from spectate.observations import UNRESOLVED
from spectate.watchers.sql import SqlWatcher


def _write(tmp_path: Path, source: str, name: str = "mod.py") -> Path:
    p = tmp_path / name
    p.write_text(source, encoding="utf-8")
    return p


def _observe(tmp_path: Path, source: str) -> list:
    return list(SqlWatcher().observe(_write(tmp_path, source)))


def _facts(observations) -> set[tuple[str, str]]:
    return {(o.category, o.parameter) for o in observations}


# --- SQL fixtures ----------------------------------------------------------


def test_select_single_table(tmp_path: Path) -> None:
    src = """
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("SELECT id FROM users WHERE id = 1")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.read", "users")}


def test_select_with_join(tmp_path: Path) -> None:
    src = """
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("SELECT u.id FROM users u JOIN orders o ON o.uid = u.id")
"""
    assert _facts(_observe(tmp_path, src)) == {
        ("db.read", "users"),
        ("db.read", "orders"),
    }


def test_select_with_cte(tmp_path: Path) -> None:
    src = """
import psycopg2
cur = psycopg2.connect("").cursor()
cur.execute("WITH recent AS (SELECT id FROM customers) SELECT * FROM recent JOIN orders ON 1=1")
"""
    facts = _facts(_observe(tmp_path, src))
    assert ("db.read", "customers") in facts
    assert ("db.read", "orders") in facts


def test_insert(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").execute("INSERT INTO accounts (id, name) VALUES (1, 'a')")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.write", "accounts")}


def test_update(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").execute("UPDATE users SET name = 'x' WHERE id = 1")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.write", "users")}


def test_delete(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").execute("DELETE FROM sessions WHERE expired = 1")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.write", "sessions")}


def test_insert_select(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").execute(
    "INSERT INTO archive (id) SELECT id FROM events WHERE old = 1"
)
"""
    facts = _facts(_observe(tmp_path, src))
    assert ("db.write", "archive") in facts
    assert ("db.read", "events") in facts


def test_create_table_is_write(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").execute("CREATE TABLE Audit (id INT)")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.write", "audit")}


def test_schema_prefix_stripped(tmp_path: Path) -> None:
    src = """
import psycopg2
psycopg2.connect("").cursor().execute("SELECT * FROM public.users")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.read", "users")}


def test_quoted_identifiers_lowercased(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").execute('SELECT * FROM "Users"')
"""
    assert _facts(_observe(tmp_path, src)) == {("db.read", "users")}


def test_multi_statement(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").executescript_dummy = None
sqlite3.connect("").execute("INSERT INTO log (m) VALUES ('x'); SELECT * FROM stats;")
"""
    facts = _facts(_observe(tmp_path, src))
    assert ("db.write", "log") in facts
    assert ("db.read", "stats") in facts


# --- Negative samples ------------------------------------------------------


def test_no_db_imports_yields_nothing(tmp_path: Path) -> None:
    src = """
class Thing:
    def execute(self, sql):
        pass

Thing().execute("SELECT * FROM users")
"""
    assert _observe(tmp_path, src) == []


def test_no_db_imports_subprocess_like(tmp_path: Path) -> None:
    src = """
import subprocess
proc = subprocess.Popen(["ls"])
# Hypothetical .execute call on something unrelated
class X:
    def execute(self, q): ...
X().execute("SELECT 1 FROM t")
"""
    assert _observe(tmp_path, src) == []


def test_no_db_imports_only_imports_other(tmp_path: Path) -> None:
    src = """
import json
import os
data = json.dumps({"sql": "SELECT * FROM users"})
"""
    assert _observe(tmp_path, src) == []


# --- Unresolved cases ------------------------------------------------------


def test_unresolved_variable_sql(tmp_path: Path) -> None:
    src = """
import sqlite3
q = "SELECT * FROM users"
sqlite3.connect("").execute(q)
"""
    obs = _observe(tmp_path, src)
    assert len(obs) == 1
    assert obs[0].parameter == UNRESOLVED
    assert obs[0].category == "db.read"
    assert any("non-literal" in t for t in obs[0].tags)


def test_unresolved_fstring_with_variable(tmp_path: Path) -> None:
    src = """
import sqlite3
table = "users"
sqlite3.connect("").execute(f"SELECT * FROM {table}")
"""
    obs = _observe(tmp_path, src)
    assert len(obs) == 1
    assert obs[0].parameter == UNRESOLVED
    assert any("non-literal" in t for t in obs[0].tags)


def test_unresolved_malformed_sql(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").execute("SELEKT FRUM stuff !!! @@")
"""
    obs = _observe(tmp_path, src)
    assert len(obs) >= 1
    assert all(o.parameter == UNRESOLVED for o in obs)
    assert any("parse-error" in t or "unsupported" in t for o in obs for t in o.tags)


# --- Known false-positive cases (documented trade-off) ---------------------


def test_false_positive_non_db_execute_in_db_file(tmp_path: Path) -> None:
    """A `.execute()` on a non-DB object in a file that imports sqlite3
    is still flagged. This is the documented cost of the import heuristic."""
    src = """
import sqlite3

class Job:
    def execute(self, command):
        return command

Job().execute("SELECT * FROM tasks")
"""
    facts = _facts(_observe(tmp_path, src))
    assert ("db.read", "tasks") in facts


def test_false_positive_executor_in_db_file(tmp_path: Path) -> None:
    src = """
import sqlite3
from concurrent.futures import ThreadPoolExecutor

pool = ThreadPoolExecutor()
pool.execute("UPDATE counters SET n = n + 1")
"""
    facts = _facts(_observe(tmp_path, src))
    assert ("db.write", "counters") in facts


# --- Module-level metadata -------------------------------------------------


def test_watcher_name() -> None:
    assert SqlWatcher().name == "sql"


def test_watcher_registered() -> None:
    import importlib

    import spectate.watchers.sql as sql_mod
    from spectate.observations import all_watchers, clear_registry

    clear_registry()
    importlib.reload(sql_mod)
    assert any(w.name == "sql" for w in all_watchers())


def test_unreadable_file_returns_empty(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.py"
    assert list(SqlWatcher().observe(missing)) == []


def test_syntax_error_returns_empty(tmp_path: Path) -> None:
    src = "import sqlite3\ndef ::\n"
    assert _observe(tmp_path, src) == []


@pytest.mark.parametrize(
    "stmt, expected",
    [
        ("DROP TABLE foo", ("db.write", "foo")),
        ("TRUNCATE TABLE foo", ("db.write", "foo")),
        ("ALTER TABLE foo ADD COLUMN x INT", ("db.write", "foo")),
    ],
)
def test_ddl_classified_as_write(tmp_path: Path, stmt: str, expected) -> None:
    src = f"""
import sqlite3
sqlite3.connect("").execute({stmt!r})
"""
    facts = _facts(_observe(tmp_path, src))
    assert expected in facts


def test_executemany_detected(tmp_path: Path) -> None:
    src = """
import sqlite3
sqlite3.connect("").executemany("INSERT INTO logs (m) VALUES (?)", [("a",)])
"""
    assert _facts(_observe(tmp_path, src)) == {("db.write", "logs")}


def test_asyncpg_detected(tmp_path: Path) -> None:
    src = """
import asyncpg
async def f(conn):
    await conn.execute("DELETE FROM jobs WHERE done = TRUE")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.write", "jobs")}


def test_from_import_of_db_driver(tmp_path: Path) -> None:
    src = """
from sqlite3 import connect
connect(":memory:").execute("SELECT * FROM widgets")
"""
    assert _facts(_observe(tmp_path, src)) == {("db.read", "widgets")}
