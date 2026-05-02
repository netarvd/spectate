"""NetworkWatcher — emits `network.outbound(host)` Observations per ADR-0001.

Detects literal-URL calls into:
- `requests.{get,post,put,patch,delete,head,options}`
- `httpx.{get,post,put,patch,delete,head,options}` and inline
  `httpx.{Client,AsyncClient}().<method>(...)` calls
- `urllib.request.urlopen(url)`
- `socket.socket(...).connect((host, port))` and `socket.connect((host, port))`

Resolution policy:
- The host is extracted from a string `Constant` argument (literal URL or host)
  and normalized via `urllib.parse.urlparse` to lowercase hostname only — no
  scheme, port, or path.
- Anything non-literal (variable, f-string with computed parts) yields the
  unresolved sentinel.
- Calls dispatched through a *variable* receiver (e.g. `s = requests.Session();
  s.get(URL)`) are emitted as unresolved — tracking session-typed variables
  requires data flow, which lives above the Watcher layer.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path
from urllib.parse import urlparse

from spectate.observations import UNRESOLVED, Observation, register_watcher

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})
_HTTPX_CLIENT_NAMES = frozenset({"Client", "AsyncClient"})
_URL_LIB_MODULES = frozenset({"requests", "httpx"})


class NetworkWatcher:
    name = "network"

    def observe(self, path: Path) -> Iterable[Observation]:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ()
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return ()
        return tuple(_Visitor(path).visit_module(tree))


_SESSION_FACTORIES = frozenset(
    {
        "requests.Session",
        "requests.session",
        "httpx.Client",
        "httpx.AsyncClient",
    }
)
_SOCKET_FACTORIES = frozenset({"socket.socket", "socket.create_connection"})


class _Visitor:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        self.session_vars: set[str] = set()
        self.socket_vars: set[str] = set()

    def visit_module(self, tree: ast.Module) -> Iterator[Observation]:
        self._collect_imports(tree)
        self._collect_assignments(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                obs = self._inspect_call(node)
                if obs is not None:
                    yield obs

    def _collect_assignments(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            module_path = self._module_for(node.value.func)
            if module_path is None:
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if module_path in _SESSION_FACTORIES:
                    self.session_vars.add(target.id)
                elif module_path in _SOCKET_FACTORIES:
                    self.socket_vars.add(target.id)

    def _collect_imports(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    self.aliases[bound] = alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    bound = alias.asname or alias.name
                    self.aliases[bound] = f"{module}.{alias.name}" if module else alias.name

    def _inspect_call(self, call: ast.Call) -> Observation | None:
        target = self._classify(call.func)
        if target is None:
            return None
        kind, url_arg_index, kwarg_name, force_unresolved = target
        if force_unresolved:
            host = UNRESOLVED
        else:
            url_node = self._extract_arg(call, url_arg_index, kwarg_name)
            host = self._resolve_host(url_node, kind)
        return Observation(
            category="network.outbound",
            parameter=host,
            file=self.path,
            line=call.lineno,
        )

    def _classify(self, func: ast.expr) -> tuple[str, int, str, bool] | None:
        if isinstance(func, ast.Attribute):
            attr = func.attr
            if attr in _HTTP_METHODS:
                module = self._module_for(func.value)
                if module in _URL_LIB_MODULES:
                    return ("url", 0, "url", False)
                if self._is_inline_httpx_client(func.value):
                    return ("url", 0, "url", False)
                if self._is_variable_receiver_likely_session(func):
                    return ("url", 0, "url", True)
                return None

            if attr == "urlopen":
                module = self._module_for(func.value)
                if module in {"urllib.request", "urllib"}:
                    return ("url", 0, "url", False)
                return None

            if attr == "connect":
                module = self._module_for(func.value)
                if module == "socket":
                    return ("socket", 0, "address", False)
                if self._is_inline_socket(func.value):
                    return ("socket", 0, "address", False)
                if self._is_variable_receiver_likely_socket(func):
                    return ("socket", 0, "address", False)
                return None

        elif isinstance(func, ast.Name):
            origin = self.aliases.get(func.id)
            if origin == "urllib.request.urlopen":
                return ("url", 0, "url", False)
        return None

    def _is_variable_receiver_likely_session(self, func: ast.Attribute) -> bool:
        if not isinstance(func.value, ast.Name):
            return False
        return func.value.id in self.session_vars

    def _is_variable_receiver_likely_socket(self, func: ast.Attribute) -> bool:
        if not isinstance(func.value, ast.Name):
            return False
        return func.value.id in self.socket_vars

    def _is_inline_httpx_client(self, value: ast.expr) -> bool:
        if not isinstance(value, ast.Call):
            return False
        if not isinstance(value.func, ast.Attribute):
            return False
        return (
            self._module_for(value.func.value) == "httpx" and value.func.attr in _HTTPX_CLIENT_NAMES
        )

    def _is_inline_socket(self, value: ast.expr) -> bool:
        if not isinstance(value, ast.Call):
            return False
        return self._module_for(value.func) == "socket"

    def _module_for(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self._module_for(node.value)
            if base is None:
                return None
            return f"{base}.{node.attr}"
        if isinstance(node, ast.Call):
            return self._module_for(node.func)
        return None

    def _extract_arg(self, call: ast.Call, index: int, kwarg_name: str) -> ast.expr | None:
        if len(call.args) > index:
            return call.args[index]
        for kw in call.keywords:
            if kw.arg == kwarg_name:
                return kw.value
        return None

    def _resolve_host(self, node: ast.expr | None, kind: str) -> str:
        if node is None:
            return UNRESOLVED
        if kind == "socket":
            return self._resolve_socket_host(node)
        return self._resolve_url_host(node)

    def _resolve_url_host(self, node: ast.expr) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return _normalize_host(node.value)
        return UNRESOLVED

    def _resolve_socket_host(self, node: ast.expr) -> str:
        if isinstance(node, ast.Tuple) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value.lower()
        return UNRESOLVED


def _normalize_host(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname
    if host:
        return host.lower()
    stripped = url.strip()
    if stripped and "://" not in stripped and "/" not in stripped and " " not in stripped:
        return stripped.lower()
    return UNRESOLVED


register_watcher(NetworkWatcher())
