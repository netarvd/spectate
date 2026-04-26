# Effect Taxonomy v1

This document defines the v1 effect categories that Watchers emit and that the Spec uses. It is the contract shared by every component downstream — getting it right here matters more than getting any single Watcher right.

## Categories

### `network.outbound(host)`

- **Captures:** the destination hostname of an outbound network call.
- **Sources detected:** literal URL strings passed to `requests.{get,post,put,patch,delete,head}`, equivalents on `httpx`, `urllib.request.urlopen`, raw `socket.connect((host, port))` with literal host.
- **Normalized form:** lowercase hostname, no scheme, no port, no path. `https://API.Example.com:8080/v1/users` → `api.example.com`.
- **Spec match:** glob over hostname. `api.example.com` matches `api.example.com`; `*.example.com` matches `api.example.com`; `*` matches all.
- **Example Observation:** `network.outbound(api.example.com)`
- **Known limits:** literal URLs only. Variables, f-strings with non-literal hosts, dynamically-built URLs are not detected — they emit the unresolved sentinel (see below).

### `fs.read(path-glob)` and `fs.write(path-glob)`

- **Captures:** filesystem read or write touch points.
- **Sources detected:**
  - read: `open(path, 'r'|'rb'|...)`, `pathlib.Path.read_*`, `pathlib.Path.open('r'|...)`
  - write: `open(path, 'w'|'wb'|'a'|'x'|...)`, `pathlib.Path.write_*`, `pathlib.Path.open('w'|...)`, `shutil.copy*`, `shutil.move`, `shutil.rmtree`, `os.remove`, `os.unlink`, `os.makedirs`, `os.mkdir`
- **Normalized form:** the path as written. Absolute stays absolute, relative stays relative. Trailing slashes stripped. No tilde or env-var expansion at v1 (decision #3).
- **Spec match:** gitignore-style globs. `**` matches any number of segments. `/var/log/**` matches `/var/log/.cache/state.bin`.
- **Example Observations:** `fs.write(/tmp/cache.bin)`, `fs.read(./config.yaml)`
- **Known limits:** literal paths only. Dynamic path construction emits the unresolved sentinel.

### `subprocess(binary)`

- **Captures:** spawning of a child process.
- **Sources detected:** `subprocess.{run, Popen, call, check_call, check_output}`, `os.system`, `os.exec*`.
- **Normalized form:** the invoked binary, basename only. `/usr/bin/git` → `git`. For shell commands (`os.system("git pull")`) the first token is captured.
- **Spec match:** exact binary name; `*` matches all.
- **Example Observations:** `subprocess(git)`, `subprocess(curl)`
- **Known limits:** doesn't track arguments. `subprocess(rm)` is the same regardless of what's removed.

### `imports(package)`

- **Captures:** Python import statements.
- **Sources detected:** `import x`, `import x.y` (top-level `x` captured), `from x import y` (top-level `x` captured), `__import__('x')`, `importlib.import_module('x')` with literal arg.
- **Normalized form:** top-level package name only. `requests.adapters` → `requests`.
- **Stdlib handling:** by default, stdlib imports are auto-allowed and don't appear in the Bulletin. A config flag (`stdlib_auto_allow`, default `true`) can disable this, in which case stdlib imports flow through the same Spec slots as third-party packages and carry a `[stdlib]` tag in the Bulletin for visual filtering.
- **Spec match:** exact package name. No globs at v1 (decision #4).
- **Example Observations:** `imports(requests)`, `imports(os) [stdlib]`
- **Known limits:** dynamic imports with non-literal arg emit the unresolved sentinel.

### `env.read(var)`

- **Captures:** reading an environment variable.
- **Sources detected:** `os.environ['X']`, `os.environ.get('X', ...)`, `os.getenv('X', ...)`.
- **Normalized form:** the literal variable name as written. Case-sensitive (matches OS behavior on Linux/macOS).
- **Spec match:** exact variable name. No globs at v1.
- **Example Observation:** `env.read(OPENAI_API_KEY)`
- **Known limits:** dynamic lookups (`os.environ[some_var]`) emit the unresolved sentinel.

### `db.read(table)` and `db.write(table)`

- **Captures:** SQL operations on database tables.
- **Sources detected:** SQL string literals passed to execute methods on `sqlite3`, `psycopg2`, `asyncpg` connections and cursors. Parsed with `sqlglot`.
- **Operation classification:**
  - read: `SELECT`
  - write: `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `REPLACE`, `TRUNCATE`, `DROP`, `CREATE`, `ALTER`
- **Normalized form:** lowercase, unquoted table name. `"Users"` → `users`. No schema prefix at v1.
- **Spec match:** exact table name. No globs at v1.
- **Example Observations:** `db.read(users)`, `db.write(audit_log)`
- **Known limits:** raw SQL only. ORM-mediated queries (SQLAlchemy, Django ORM) are not detected; this is documented as out of scope for the static layer until runtime instrumentation lands.

## The unresolved sentinel

When a Watcher detects an effect but cannot statically determine its parameter (variable, dynamic dispatch, computed value), it emits an Observation with `*` as the parameter — for example `network.outbound(*)` or `fs.write(*)`.

**Default behavior:** Spec patterns are not evaluated against unresolved Observations. Instead they appear in the Bulletin under a distinct severity: `unresolved` — *"this effect happened, but Spectate cannot tell you what it touched."* This keeps the contract honest: Spectate never pretends to see what it can't see, and never silently passes effects it couldn't identify.

**Configurable.** A config flag (`unresolved_handling`, default `surface`) controls behavior:

- `surface` *(default)* — emit as `unresolved` severity in the Bulletin.
- `flag` — treat as `added-unspecified` violations.
- `drop` — silently exclude from the Bulletin (use only when you've audited the code paths and accept the loss of signal).

## Out of scope for v1

Deliberately not in v1. Candidates after the MVP demo lands.

- Outbound calls via WebSockets, gRPC, raw HTTP/2 client libraries.
- Inbound network surface (servers binding ports, listening sockets).
- File descriptor / socket fd-based IO.
- Memory-mapped files, shared memory.
- IPC: signals, pipes, message queues.
- Threading / multiprocessing primitives.
- Time / randomness as effects.
- Logging output destinations.
- ORM-mediated database access (deferred to runtime instrumentation).
