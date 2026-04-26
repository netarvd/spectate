"""Filesystem Watcher.

Detects ``fs.read`` and ``fs.write`` effects per ADR-0001 by static AST
analysis. Emits one Observation per call site; modes that both read and
write (``r+``, ``w+``, ``a+``) emit two.

Path extraction follows ADR-0001 decisions #3 and #6:
- no expansion (no ``~``, no env vars)
- no normalization beyond stripping trailing slashes

Resolvable composites:
- ``os.path.join("/tmp", "x")`` when every segment is a string literal
- ``Path("/tmp") / "x"`` when every segment of the chain is a literal

Any non-literal segment yields the unresolved sentinel.
"""

from __future__ import annotations

import ast
import posixpath
from collections.abc import Iterable
from pathlib import Path

from spectate.observations import UNRESOLVED, Observation, register_watcher

_READ = "fs.read"
_WRITE = "fs.write"

_OS_WRITE_FUNCS = frozenset({"remove", "unlink", "makedirs", "mkdir", "rename", "replace"})
_SHUTIL_WRITE_FUNCS = frozenset({"copy", "copy2", "copyfile", "copytree", "move", "rmtree"})
_PATH_READ_METHODS = frozenset({"read_text", "read_bytes"})
_PATH_WRITE_METHODS = frozenset({"write_text", "write_bytes"})


def _strip_trailing_slash(path: str) -> str:
    if len(path) > 1 and path.endswith(("/", "\\")):
        return path.rstrip("/\\") or path[0]
    return path


def _classify_mode(mode: str) -> tuple[bool, bool]:
    """Return (is_read, is_write) for an ``open()`` mode string.

    Modes containing ``+`` always both read and write. ``r``/no flag is
    read-only; ``w``/``a``/``x`` are write-only.
    """
    has_plus = "+" in mode
    is_write = has_plus or any(c in mode for c in ("w", "a", "x"))
    is_read = has_plus or ("r" in mode) or (not is_write)
    return is_read, is_write


class _Aliases:
    def __init__(self) -> None:
        self.os: set[str] = {"os"}
        self.os_path: set[str] = {"os.path"}
        self.shutil: set[str] = {"shutil"}
        self.path_ctor: set[str] = {"Path", "pathlib.Path"}
        # `from os import remove as rm` -> {"rm": "remove"}
        self.os_direct: dict[str, str] = {}
        # `from shutil import copy as cp` -> {"cp": "copy"}
        self.shutil_direct: dict[str, str] = {}
        # `from os.path import join as j` -> {"j"}
        self.ospath_join: set[str] = {"join"}  # bare `join(...)` we still don't infer
        # We only count `os.path.join` / `aliased_ospath.join` as resolvable.

    def visit(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name
                    if alias.name == "os":
                        self.os.add(local)
                    elif alias.name == "os.path":
                        self.os_path.add(local)
                    elif alias.name == "shutil":
                        self.shutil.add(local)
                    elif alias.name == "pathlib":
                        # pathlib.Path constructor still detected via attr chain
                        pass
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "pathlib":
                    for alias in node.names:
                        if alias.name == "Path":
                            self.path_ctor.add(alias.asname or "Path")
                elif module == "os":
                    for alias in node.names:
                        local = alias.asname or alias.name
                        self.os_direct[local] = alias.name
                elif module == "shutil":
                    for alias in node.names:
                        local = alias.asname or alias.name
                        self.shutil_direct[local] = alias.name


def _attr_dotted(node: ast.AST) -> str | None:
    """Return the dotted name for an Attribute/Name chain, or None."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _is_path_ctor_call(node: ast.AST, aliases: _Aliases) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = _attr_dotted(node.func)
    return name in aliases.path_ctor


def _is_path_expr(node: ast.AST, aliases: _Aliases) -> bool:
    """Heuristic: True if `node` plausibly evaluates to a pathlib.Path.

    Covers: ``Path(...)``, ``Path(...) / x``, ``(Path(...) / x).parent``, etc.
    """
    if _is_path_ctor_call(node, aliases):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _is_path_expr(node.left, aliases) or _is_path_expr(node.right, aliases)
    if isinstance(node, ast.Attribute):
        return _is_path_expr(node.value, aliases)
    if isinstance(node, ast.Call):
        # method call on a Path receiver, e.g. p.with_suffix(".x")
        return isinstance(node.func, ast.Attribute) and _is_path_expr(node.func.value, aliases)
    return False


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _resolve_ospath_join(call: ast.Call) -> str | None:
    parts: list[str] = []
    for arg in call.args:
        s = _literal_str(arg)
        if s is None:
            return None
        parts.append(s)
    if not parts:
        return None
    return posixpath.join(*parts)


def _resolve_path_chain(node: ast.AST, aliases: _Aliases) -> str | None:
    """Resolve ``Path("a") / "b" / "c"`` to a string when all segments are literals."""
    if isinstance(node, ast.Call) and _is_path_ctor_call(node, aliases):
        if len(node.args) == 1:
            return _literal_str(node.args[0])
        if len(node.args) == 0:
            return "."
        # Multi-arg Path("a", "b") — also resolvable if all literal
        parts = []
        for a in node.args:
            s = _literal_str(a)
            if s is None:
                return None
            parts.append(s)
        return posixpath.join(*parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _resolve_path_chain(node.left, aliases)
        if left is None:
            return None
        right = _literal_str(node.right)
        if right is None:
            # The right operand could itself be a chain like `Path("x") / "y"`,
            # but in practice the lhs is the Path; if rhs is a chain we treat it
            # as unresolved to keep semantics simple.
            return None
        return posixpath.join(left, right)
    return None


def _extract_path(node: ast.AST | None, aliases: _Aliases) -> str:
    """Return the literal string path or the unresolved sentinel."""
    if node is None:
        return UNRESOLVED
    s = _literal_str(node)
    if s is not None:
        return _strip_trailing_slash(s)
    if isinstance(node, ast.Call):
        # os.path.join(...) (any aliased os.path)
        func_name = _attr_dotted(node.func)
        if func_name is not None:
            head, _, tail = func_name.rpartition(".")
            if tail == "join" and head in aliases.os_path:
                joined = _resolve_ospath_join(node)
                if joined is not None:
                    return _strip_trailing_slash(joined)
                return UNRESOLVED
        # Path(...) constructor
        if _is_path_ctor_call(node, aliases):
            chain = _resolve_path_chain(node, aliases)
            if chain is not None:
                return _strip_trailing_slash(chain)
            return UNRESOLVED
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        chain = _resolve_path_chain(node, aliases)
        if chain is not None:
            return _strip_trailing_slash(chain)
        return UNRESOLVED
    return UNRESOLVED


def _open_mode(call: ast.Call) -> str:
    if len(call.args) >= 2:
        m = _literal_str(call.args[1])
        if m is not None:
            return m
        return ""  # unknown but present — treat as default 'r'
    for kw in call.keywords:
        if kw.arg == "mode":
            m = _literal_str(kw.value)
            if m is not None:
                return m
            return ""
    return "r"


class _FsVisitor(ast.NodeVisitor):
    def __init__(self, source_path: Path, aliases: _Aliases) -> None:
        self.source_path = source_path
        self.aliases = aliases
        self.observations: list[Observation] = []

    def _emit(self, category: str, parameter: str, line: int) -> None:
        self.observations.append(
            Observation(
                category=category,
                parameter=parameter,
                file=self.source_path,
                line=line,
            )
        )

    def _emit_modes(self, mode: str, path: str, line: int) -> None:
        is_read, is_write = _classify_mode(mode or "r")
        if is_read:
            self._emit(_READ, path, line)
        if is_write:
            self._emit(_WRITE, path, line)

    def visit_Call(self, node: ast.Call) -> None:
        self._handle_call(node)
        self.generic_visit(node)

    def _handle_call(self, node: ast.Call) -> None:
        func = node.func

        # Bare open(...)
        if isinstance(func, ast.Name) and func.id == "open":
            path_arg = node.args[0] if node.args else None
            path = _extract_path(path_arg, self.aliases)
            mode = _open_mode(node)
            self._emit_modes(mode, path, node.lineno)
            return

        if isinstance(func, ast.Attribute):
            method = func.attr
            receiver = func.value
            dotted = _attr_dotted(func)

            # os.<func>(path) and from-os aliases
            if dotted is not None:
                head, _, tail = dotted.rpartition(".")
                if head in self.aliases.os and tail in _OS_WRITE_FUNCS:
                    self._emit(
                        _WRITE,
                        _extract_path(node.args[0] if node.args else None, self.aliases),
                        node.lineno,
                    )
                    return
                if head in self.aliases.shutil and tail in _SHUTIL_WRITE_FUNCS:
                    self._emit(
                        _WRITE,
                        _extract_path(node.args[0] if node.args else None, self.aliases),
                        node.lineno,
                    )
                    # copy/copy2/copyfile/copytree/move read the source — but per
                    # ADR-0001 we report them as fs.write only (the destination is
                    # the side-effecting concern). Source reads are not emitted to
                    # avoid double-counting; raise as a decision if needed.
                    return

            # Path(...).read_text() / write_text() / read_bytes() / write_bytes() / open(...)
            if _is_path_expr(receiver, self.aliases):
                path = _extract_path(receiver, self.aliases)
                if method in _PATH_READ_METHODS:
                    self._emit(_READ, path, node.lineno)
                    return
                if method in _PATH_WRITE_METHODS:
                    self._emit(_WRITE, path, node.lineno)
                    return
                if method == "open":
                    mode = "r"
                    if node.args:
                        m = _literal_str(node.args[0])
                        mode = m if m is not None else ""
                    else:
                        for kw in node.keywords:
                            if kw.arg == "mode":
                                m = _literal_str(kw.value)
                                mode = m if m is not None else ""
                                break
                    self._emit_modes(mode, path, node.lineno)
                    return

        # `from os import remove` -> remove("foo")
        if isinstance(func, ast.Name):
            if func.id in self.aliases.os_direct:
                real = self.aliases.os_direct[func.id]
                if real in _OS_WRITE_FUNCS:
                    self._emit(
                        _WRITE,
                        _extract_path(node.args[0] if node.args else None, self.aliases),
                        node.lineno,
                    )
                    return
            if func.id in self.aliases.shutil_direct:
                real = self.aliases.shutil_direct[func.id]
                if real in _SHUTIL_WRITE_FUNCS:
                    self._emit(
                        _WRITE,
                        _extract_path(node.args[0] if node.args else None, self.aliases),
                        node.lineno,
                    )
                    return


class FsWatcher:
    """Static fs.read / fs.write detector."""

    name = "fs"

    def observe(self, path: Path) -> Iterable[Observation]:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ()
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return ()
        aliases = _Aliases()
        aliases.visit(tree)
        visitor = _FsVisitor(path, aliases)
        visitor.visit(tree)
        return tuple(visitor.observations)


register_watcher(FsWatcher())
