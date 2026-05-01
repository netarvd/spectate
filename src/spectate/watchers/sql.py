"""SqlWatcher — emits `db.read(table)` and `db.write(table)` Observations per ADR-0001.

Detection model:
- A file is treated as "DB code" iff it imports `sqlite3`, `psycopg2`, `psycopg`, or
  `asyncpg` at any level. In such a file, every `.execute(...)` and `.executemany(...)`
  call site is a candidate SQL site. This is intentionally coarse — see PR notes.
- Literal string SQL is parsed with `sqlglot.parse(...)`; each statement is classified
  by node type and tables are emitted as reads or writes.
- Non-literal SQL (variable, computed f-string) and parse failures emit a single
  unresolved `db.read(*)` Observation per call site.

Limits:
- Schema prefixes are stripped at v1 (`public.users` → `users`).
- ORM-mediated SQL (SQLAlchemy, Django ORM, etc.) is out of scope.
- The import-based heuristic produces false positives on non-DB `.execute` methods
  in files that also touch a DB driver.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

import sqlglot
from sqlglot import exp

from spectate.observations import UNRESOLVED, Observation, register_watcher

_DB_MODULES = frozenset({"sqlite3", "psycopg2", "psycopg", "asyncpg"})
_EXECUTE_METHODS = frozenset({"execute", "executemany"})

_WRITE_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
)


class SqlWatcher:
    name = "sql"

    def observe(self, path: Path) -> Iterable[Observation]:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ()
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return ()
        if not _file_imports_db_driver(tree):
            return ()
        return tuple(_emit(tree, path))


def _file_imports_db_driver(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _DB_MODULES:
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in _DB_MODULES:
                return True
    return False


def _emit(tree: ast.Module, path: Path) -> Iterator[Observation]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _EXECUTE_METHODS:
            continue
        if not node.args:
            continue
        sql_node = node.args[0]
        line = node.lineno
        sql = _literal_string(sql_node)
        if sql is None:
            yield Observation(
                category="db.read",
                parameter=UNRESOLVED,
                file=path,
                line=line,
                tags=("unresolved:non-literal",),
            )
            continue
        yield from _classify_sql(sql, path, line)


def _literal_string(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                return None
        return "".join(parts)
    return None


def _classify_sql(sql: str, path: Path, line: int) -> Iterator[Observation]:
    try:
        statements = sqlglot.parse(sql)
    except sqlglot.errors.ParseError:
        yield Observation(
            category="db.read",
            parameter=UNRESOLVED,
            file=path,
            line=line,
            tags=("unresolved:parse-error",),
        )
        return
    emitted = False
    for stmt in statements:
        if not isinstance(stmt, exp.Expression):
            continue
        for obs in _classify_statement(stmt, path, line):
            emitted = True
            yield obs
    if not emitted:
        yield Observation(
            category="db.read",
            parameter=UNRESOLVED,
            file=path,
            line=line,
            tags=("unresolved:no-tables",),
        )


def _classify_statement(stmt: exp.Expression, path: Path, line: int) -> Iterator[Observation]:
    if isinstance(stmt, exp.Command):
        yield Observation(
            category="db.write",
            parameter=UNRESOLVED,
            file=path,
            line=line,
            tags=("unresolved:unsupported-statement",),
        )
        return

    write_targets: list[str] = []
    read_sources: list[str] = []

    if isinstance(stmt, exp.Insert):
        target = _unwrap_schema(stmt.this)
        if target is not None:
            write_targets.append(target)
        if stmt.expression is not None:
            read_sources.extend(_collect_table_names(stmt.expression))
    elif isinstance(stmt, (exp.Update, exp.Delete, exp.Merge)):
        target = _table_name(stmt.this)
        if target is not None:
            write_targets.append(target)
        for key, value in stmt.args.items():
            if key == "this" or value is None:
                continue
            if isinstance(value, exp.Expression):
                read_sources.extend(_collect_table_names(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, exp.Expression):
                        read_sources.extend(_collect_table_names(item))
    elif isinstance(stmt, _WRITE_NODES):
        write_targets.extend(_collect_table_names(stmt))
    elif isinstance(stmt, exp.Select):
        read_sources.extend(_collect_table_names(stmt))
    else:
        # Unknown statement type — treat as unresolved write so it surfaces.
        yield Observation(
            category="db.write",
            parameter=UNRESOLVED,
            file=path,
            line=line,
            tags=(f"unresolved:unhandled-{type(stmt).__name__.lower()}",),
        )
        return

    seen: set[tuple[str, str]] = set()
    for table in write_targets:
        write_key = ("db.write", table)
        if write_key in seen:
            continue
        seen.add(write_key)
        yield Observation(category="db.write", parameter=table, file=path, line=line)
    for table in read_sources:
        if ("db.write", table) in seen:
            continue
        read_key = ("db.read", table)
        if read_key in seen:
            continue
        seen.add(read_key)
        yield Observation(category="db.read", parameter=table, file=path, line=line)


def _collect_table_names(node: exp.Expression) -> list[str]:
    names: list[str] = []
    for table in node.find_all(exp.Table):
        name = _table_name(table)
        if name is not None:
            names.append(name)
    return names


def _unwrap_schema(node: exp.Expression | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, exp.Schema):
        return _table_name(node.this)
    return _table_name(node)


def _table_name(node: exp.Expression | None) -> str | None:
    if isinstance(node, exp.Table):
        return node.name.lower() if node.name else None
    return None


register_watcher(SqlWatcher())
