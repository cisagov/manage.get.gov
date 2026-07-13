# 32. Reintroduce an EPP Connection Pool (standard library, thread-based)

Date: 2026-07-10

## Status

Under Review

## Context

[ADR 23](./0023-use-geventconnpool.md) adopted the third-party [`geventconnpool`](https://github.com/rasky/geventconnpool)
library to maintain a pool of logged-in EPP connections to the registry, so that commands could
reuse existing connections instead of paying a new TLS handshake and EPP login on every send.

That pool was later removed (February 2024). At the time, the gunicorn worker class had been
changed to `gevent` with 3 workers per instance. Because each worker process held its own
long-lived EPP client, the deployment immediately established 3 registry connections (one per
worker), and the dedicated connection pool was deemed unneeded — the per-worker singleton client, guarded by a semaphore, appeared to provide enough connectivity. Removing the pool also removed the dependency on `geventconnpool`, which had been unmaintained since 2021 and was a known risk(see the Consequences section of ADR 23).

Since then, operational experience and load testing have shown the limits of the singleton-client
design: with one connection per worker, every EPP command on a worker is serialized behind a
single lock, so a burst of registry-bound requests queues up and response times climb. During
load testing, reintroducing a connection pool rapidly helped the system respond to an influx of
EPP messages — multiple commands per worker can be in flight at once, each on its own connection.

## Decision

Reintroduce an EPP connection pool, but written in-house on Python standard library primitives
(`queue.LifoQueue`, `threading.Lock`, `threading.Thread`) rather than readopting `geventconnpool`
(this is option 2 from ADR 23, "write our own connection pool logic").

Key properties of the new pool (`src/epplibwrapper/utility/pool.py`):

- **Fixed maximum size per worker**, configured via the `EPP_CONNECTION_POOL_SIZE` environment
  variable (see the EPP connection pool region of `src/registrar/config/settings.py`).
- **Thread-based, not gevent-based.** Under gunicorn's `gevent` worker class the standard library
  primitives are monkey-patched and cooperate with greenlets; under a `gthread` worker they are
  natively thread-safe. The pool works under either worker class with no code changes.
- **Background maintenance thread** that periodically pings idle connections (EPP `Hello`) and
  retires connections that have gone too long without doing real work, replacing them with fresh
  ones.
- **Per-connection blast radius.** A transport failure discards only the affected connection;
  there is no whole-pool restart path.

## Consequences

- Multiple EPP commands can be serviced concurrently per worker (up to the pool size), which
  removes the single-connection serialization that made bursts of registry traffic slow.
- We own the pool code and its testing burden — the tradeoff accepted in ADR 23's option 2. The
  pool is deliberately small and self-contained to keep that burden manageable, and unlike
  `geventconnpool` it has no third-party maintenance risk.
- Pool sizing must be coordinated across environments that share registry credentials, since they
  share the registry's connection allowance; sizes are set per environment via environment
  variables rather than in code.
- Troubleshooting guidance for the pool's log messages lives in
  `docs/developer/epp-connection-pool-debugging.md`.
