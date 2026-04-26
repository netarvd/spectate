from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from spectate.observations.observation import UNRESOLVED, Observation
from spectate.observations.watcher import register_watcher

_SUBPROCESS_FUNCS = frozenset({"run", "Popen", "call", "check_call", "check_output", "popen"})
_OS_EXEC_FUNCS = frozenset(
    {
        "system",
        "popen",
        "execv",
        "execvp",
        "execve",
        "execvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
    }
)


class SubprocessWatcher:
    name = "subprocess"

    def observe(self, path: Path) -> Iterable[Observation]:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        observations: list[Observation] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            module, func = _resolve_call_target(node.func)
            if module is None or func is None:
                continue
            if module == "subprocess" and func in _SUBPROCESS_FUNCS:
                binary = _extract_binary(node, shell_default=False)
            elif module == "os" and func in _OS_EXEC_FUNCS:
                binary = _extract_os_binary(node, func)
            else:
                continue
            observations.append(
                Observation(
                    category="subprocess",
                    parameter=binary,
                    file=path,
                    line=node.lineno,
                )
            )
        return observations


def _resolve_call_target(func: ast.expr) -> tuple[str | None, str | None]:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id, func.attr
    return None, None


def _extract_os_binary(node: ast.Call, func: str) -> str:
    if not node.args:
        return UNRESOLVED
    first = node.args[0]
    if func in {"system", "popen"}:
        return _binary_from_shell_string(first)
    return _basename_of(first)


def _extract_binary(node: ast.Call, shell_default: bool) -> str:
    shell = shell_default
    for kw in node.keywords:
        if kw.arg == "shell" and isinstance(kw.value, ast.Constant):
            shell = bool(kw.value.value)
    if not node.args:
        return UNRESOLVED
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        if shell:
            return _binary_from_shell_string(first)
        return _basename(first.value)
    if isinstance(first, ast.List | ast.Tuple):
        if not first.elts:
            return UNRESOLVED
        return _basename_of(first.elts[0])
    return UNRESOLVED


def _binary_from_shell_string(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        tokens = node.value.strip().split()
        if not tokens:
            return UNRESOLVED
        return _basename(tokens[0])
    return UNRESOLVED


def _basename_of(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _basename(node.value)
    return UNRESOLVED


def _basename(value: str) -> str:
    name = Path(value).name
    return name or UNRESOLVED


register_watcher(SubprocessWatcher())
