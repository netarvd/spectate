# Each Watcher module registers itself on import via register_watcher().
# Add new Watcher imports here in alphabetical order.
from spectate.watchers.env import EnvWatcher  # noqa: F401
from spectate.watchers.fs import FsWatcher  # noqa: F401
from spectate.watchers.imports_ import ImportsWatcher  # noqa: F401
from spectate.watchers.network import NetworkWatcher  # noqa: F401
from spectate.watchers.sql import SqlWatcher  # noqa: F401
from spectate.watchers.subprocess_ import SubprocessWatcher  # noqa: F401
