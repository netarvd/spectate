"""ImportsWatcher — emit `imports(package)` Observations per ADR-0001.

Detects:
    - `import x`, `import x.y.z`              → top-level `x`
    - `from x import y`, `from x.y import z`  → top-level `x`
    - `__import__('x')` (literal arg)         → `x`
    - `importlib.import_module('x')` (literal) → `x`

Dynamic `__import__(var)` / `importlib.import_module(expr)` emit the
unresolved sentinel.

Skipped (not effect-bearing third-party touchpoints):
    - Relative imports (`from . import x`, `from .y import z`).
    - `from __future__ import ...` — compiler directive, never an effect.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from pathlib import Path

from spectate.observations import UNRESOLVED, Observation, register_watcher

_STDLIB: frozenset[str] = frozenset(sys.stdlib_module_names)


def _top_level(dotted: str) -> str:
    return dotted.split(".", 1)[0]


def _tags_for(pkg: str) -> tuple[str, ...]:
    return ("stdlib",) if pkg in _STDLIB else ()


class ImportsWatcher:
    name = "imports"

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

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = _top_level(alias.name)
                    if not pkg:
                        continue
                    observations.append(
                        Observation(
                            category="imports",
                            parameter=pkg,
                            file=path,
                            line=node.lineno,
                            tags=_tags_for(pkg),
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                # Relative import (level > 0) → internal, skip.
                if node.level and node.level > 0:
                    continue
                if node.module is None:
                    continue
                # __future__ is a compiler directive, not an effect.
                if node.module == "__future__":
                    continue
                pkg = _top_level(node.module)
                if not pkg:
                    continue
                observations.append(
                    Observation(
                        category="imports",
                        parameter=pkg,
                        file=path,
                        line=node.lineno,
                        tags=_tags_for(pkg),
                    )
                )

            elif isinstance(node, ast.Call):
                target = self._dynamic_target(node)
                if target is None:
                    continue
                if not node.args:
                    continue
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    pkg = _top_level(first.value)
                    if not pkg:
                        continue
                    observations.append(
                        Observation(
                            category="imports",
                            parameter=pkg,
                            file=path,
                            line=node.lineno,
                            tags=_tags_for(pkg),
                        )
                    )
                else:
                    observations.append(
                        Observation(
                            category="imports",
                            parameter=UNRESOLVED,
                            file=path,
                            line=node.lineno,
                        )
                    )

        return observations

    @staticmethod
    def _dynamic_target(node: ast.Call) -> str | None:
        """Return a marker if this Call is __import__ or importlib.import_module."""
        func = node.func
        if isinstance(func, ast.Name) and func.id == "__import__":
            return "__import__"
        if isinstance(func, ast.Attribute) and func.attr == "import_module":
            value = func.value
            if isinstance(value, ast.Name) and value.id == "importlib":
                return "importlib.import_module"
        return None


register_watcher(ImportsWatcher())
