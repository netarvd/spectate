from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from spectate.observations.observation import UNRESOLVED, Observation
from spectate.observations.watcher import register_watcher

_CATEGORY = "env.read"


def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class EnvWatcher:
    name = "env"

    def observe(self, path: Path) -> Iterable[Observation]:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        observations: list[Observation] = []

        def emit(parameter: str, line: int) -> None:
            observations.append(
                Observation(
                    category=_CATEGORY,
                    parameter=parameter,
                    file=path,
                    line=line,
                )
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and _is_os_environ(node.value):
                literal = _literal_str(node.slice)
                emit(literal if literal is not None else UNRESOLVED, node.lineno)
                continue

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                func = node.func
                if func.attr in {"get", "setdefault"} and _is_os_environ(func.value) and node.args:
                    literal = _literal_str(node.args[0])
                    emit(literal if literal is not None else UNRESOLVED, node.lineno)
                    continue

                if (
                    func.attr == "getenv"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "os"
                ):
                    if node.args:
                        literal = _literal_str(node.args[0])
                        emit(literal if literal is not None else UNRESOLVED, node.lineno)
                    else:
                        emit(UNRESOLVED, node.lineno)
                    continue

                if func.attr in {"keys", "values", "items"} and _is_os_environ(func.value):
                    emit(UNRESOLVED, node.lineno)
                    continue

            if isinstance(node, ast.For) and _is_os_environ(node.iter):
                emit(UNRESOLVED, node.lineno)
                continue

            if isinstance(node, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp):
                for gen in node.generators:
                    if _is_os_environ(gen.iter):
                        emit(UNRESOLVED, node.lineno)

        return observations


register_watcher(EnvWatcher())
