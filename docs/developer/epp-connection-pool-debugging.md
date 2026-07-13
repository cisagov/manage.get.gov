# Debugging the EPP Connection Pool

The registrar keeps a small pool of logged-in EPP connections per worker process
(`src/epplibwrapper/utility/pool.py`, wired up in `src/epplibwrapper/client.py`).
This guide maps the pool's log messages to what they mean and where they come from,
so you can troubleshoot without reading the whole implementation first.

## Connection lifecycle in one minute

Every pooled connection is in exactly one of two places: **checked out** (a request
is using it) or **in the idle queue**. A request borrows a connection through the
`connection()` context manager and returns it when done. Idle connections wait in a
LIFO queue, so the most recently used (warmest) connection is reused first.

A background maintenance thread (`epp-pool-maintenance`) periodically:

- **pings** idle connections with an EPP `Hello` so silently dropped sockets are
  found and replaced before a request touches them (`EPP_POOL_HEARTBEAT_INTERVAL`), and
- **retires** connections that have gone too long without doing real command work
  (`EPP_POOL_RECYCLE_SECONDS`), then replenishes the pool with fresh connections.

Vocabulary used in the code and logs:

- **borrow / return** — a request takes a connection / gives it back.
- **discard** — the connection is presumed dead: close the socket only (no `Logout`,
  which would just fail and add noise).
- **retire** — the connection is believed healthy but no longer wanted: graceful
  `Logout` + close.

## Reading `stats()`

Most pool log lines embed a stats snapshot:

```
{'size': 10, 'connections created': 10, 'idle': 7, 'in use': 3}
```

- `size` — the configured maximum (`EPP_CONNECTION_POOL_SIZE`).
- `connections created` — connections currently in existence (checked out + idle).
- `idle` — connections waiting in the queue right now.
- `in use` — `connections created - idle`, i.e. checked out right now.

Persistent `connections created` well below `size`, together with the
"Replenish hit an error" line, means the registry is refusing or failing new
connections — look at registry availability and login errors.

## Log line → meaning → where in code

| Log line (grep for) | Level | Meaning | Where |
|---|---|---|---|
| `Discarding stale pooled EPP connection; will replace` | INFO | A borrowed connection failed its `Hello` health check; it was closed and the borrow loop got a different/fresh one. The caller never saw the dead connection. Occasional occurrences are normal housekeeping; continuous back-to-back occurrences warrant investigation. | `pool.py` `_borrow` |
| `Heartbeat replaced a dead idle EPP connection` | INFO | The maintenance pass pinged an idle connection, got no valid answer, and discarded it; the replenish step builds its replacement. | `pool.py` `_maintain_idle_connections` |
| `Retiring long-idle EPP connection` | INFO | A connection went longer than `EPP_POOL_RECYCLE_SECONDS` without real command traffic and was gracefully logged out and closed; the replenish step rebuilds it. | `pool.py` `_maintain_idle_connections` |
| `Replenish hit an error & failed to build a connection` | INFO | A top-up connection build (connect + login) failed; the pool defers the rest to the next pass instead of retrying immediately. Persistent occurrences mean the registry is down or refusing logins. | `pool.py` `_replenish` |
| `EPP pool heartbeat pass failed` | WARNING | The whole maintenance pass hit an unexpected error. The thread survives and runs again next interval. Once is fine; repeated back-to-back occurrences warrant investigation. | `pool.py` `_maintenance_loop` |
| `failed: all pooled EPP connections are busy` | ERROR | `PoolExhausted`: every connection stayed checked out for the entire `EPP_POOL_BORROW_TIMEOUT` wait. This is a capacity signal, not a socket problem — check the embedded stats (`in use` == `size`, `idle` == 0). | `client.py` `_send` |
| `failed to execute due to a connection error` | ERROR | `TransportError` mid-command. The pool has already discarded that connection; the retry loop in `send()` will use a different or fresh one. | `client.py` `_send` |
| `failed to execute due to a registry login error` | ERROR | The registry rejected the login while a new connection was being built for this command. | `client.py` `_send` / `_create_connection` |
| `failed to execute due to some syntax error` | ERROR | Malformed command or unparseable response (`ValueError` / `ParsingError`) — a code problem, not infrastructure. Retrying won't help. | `client.py` `_send` |
| `failed to execute due to an unknown error` | ERROR | Catch-all: something other than the categorized failures above. Read the attached traceback. | `client.py` `_send` |
| `failed and will be retried` | INFO | `send()` caught a retryable `RegistryError` and is retrying (up to 3 attempts with a short backoff). | `client.py` `send` |
| `registry client initialized` | INFO | The wrapper (and its pool) constructed successfully at worker startup. | `client.py` module level |
| `Unable to configure epplib` | WARNING | The wrapper failed to construct at startup; the registrar cannot contact the registry from this worker. | `client.py` module level |

At DEBUG level the pool also logs each borrow attempt, failed creations, retire/close
details, and the pre-`PoolExhausted` wait — useful when reproducing an issue locally
or on a sandbox with `DJANGO_LOG_LEVEL=DEBUG`.

## Connection pool environment variables

All settings live in the "EPP connection Pool" region of
`src/registrar/config/settings.py` and are environment-variable overridable per
environment:

| Setting | Default | What it does |
|---|---|---|
| `EPP_CONNECTION_POOL_SIZE` | 1 | Max connections per worker process. Environments that share registry credentials also share the registry's connection allowance, so keep non-production sizes small. |
| `EPP_POOL_BORROW_TIMEOUT` | 20 | Seconds a request waits for a connection before `PoolExhausted`. |
| `EPP_POOL_IDLE_PING_SECONDS` | 60 | A connection idle longer than this must answer a `Hello` before reuse. |
| `EPP_POOL_HEARTBEAT_INTERVAL` | 120 | Cadence of the background maintenance pass. 0 disables pinging. |
| `EPP_POOL_RECYCLE_SECONDS` | 600 | Max time since a connection's last real (non-`Hello`) command before it is retired and replaced. 0 disables recycling. |

### Changing environment variables in a running sandbox

1. Target the sandbox in question: `cf target -s {sandbox-name}`
2. Use the set-env Cloud Foundry command to set the variable (`{var}` below) and new value (`{new val}` below)
```bash
cf set-env getgov-{sandbox-name} {var} {new val}
cf restart getgov-{sandbox-name}
```

Example:
```bash
cf set-env getgov-ab EPP_POOL_HEARTBEAT_INTERVAL 60
cf restart getgov-ab
```
Note: this setting persists across redeploys until you change it again or remove it. In Cloud Foundry code unset with `cf unset-env getgov-{sandbox-name} {var}` OR you can choose to update the manifest following the instructions below.

### Changing environment variables in a manifest
Only do this if you want the change to persist long term AND you are setting it to a NON-default value.

The manifest yaml files in our codebase are designed to hold any environment-specific settings that can be public facing. If any of the above variables are missing from the sandbox's yaml file then it will just go with the default. Thus, if you wish to configure an environment to be anything other than the default, simply add that variable(s) to the correct yaml and then redeploy.

1. change the .yaml file by adding the environment variable in the `applications`.`env` section. See [here](https://github.com/cisagov/manage.get.gov/blob/824a9ae88e1008b0ee596e5bbcc06125411a866c/ops/manifests/manifest-stable.yaml#L37) for an example.
2. for a sandbox: open a PR — `deploy-sandbox.yaml` deploys the PR branch (including its manifest) automatically on every push, no merge needed (only for the branch initials listed in that workflow)
3. for development/staging/stable: merge the PR — those environments deploy from their own workflows after merge

Now it will permanently stay like this unless overridden by `cf set-env`