# Database backup and recovery

The administrator-local `project-bots backup` and `restore` commands operate on
SQLite database files. They never start workers, contact a model server, or replace
an existing destination. Worker disks/snapshots, model blobs, environment secrets,
network policy and external audit storage are **not included**. Database backups
contain private messages and evidence; protect them as sensitive data.

## Create a consistent database backup

Create a dedicated caller-owned directory with mode 0700 first. Both source and
destination parent directories must be private; source must be a caller-owned
private regular file. Symlink sources/destinations and existing destinations are
refused. The SQLite online backup API includes committed WAL state; copying only
the raw live `.db` file is not a substitute.

```sh
project-bots backup --database /absolute/private/platform.db \
  --output /absolute/private-backups/platform-unique-name.db
```

The command validates integrity and foreign keys, copies to a 0600 staging file,
validates the copy and publishes it without overwriting an existing file. It
returns a metadata-only JSON receipt. Concurrent callers targeting the same path
cannot overwrite the winner. A backup is not encryption, an immutable audit log,
a full-machine snapshot or a guarantee against a compromised administrator.

## Restore to a new offline path

```sh
project-bots restore --backup /absolute/private-backups/platform-unique-name.db \
  --database /absolute/private-recovery/recovered.db
```

Restore validates a recognized Project Bots SQLite database and writes a NEW
private path only. It does not alter a running server, existing database, original
workers, or service configuration. Keep the existing database and logs until the
incident is resolved. Review the recovered data, schema/application compatibility,
identities, revoked credentials, stop latch and unresolved executions before any
activation. Backups may predate revocations/containment: **never treat old tokens,
monitor-health receipts or execution reports as fresh authorization**. Existing
application schema migrations occur when the backend opens the recovered copy.

Before activating a recovered database, stop the backend through your normal
administrator-controlled service procedure, retain independent worker network
containment, rotate affected credentials outside workers, and ensure monitoring
and enforcement are operating. Only then configure the intended recovered database
path and restart the backend. Explicit administrator authorization is required
before restoring worker execution. Do not activate a second backend against the
same live workers during recovery. These are administrator procedures, not an
implemented automatic disaster-recovery orchestrator.

## Executed coverage

`python3 -m unittest discover -s tests -p test_backup.py -v` passes three CLI tests:
committed-WAL/schema preservation; actual installed commands from a temporary HOME
without the source path in PYTHONPATH; refusal of overwrites, symlinks, corrupt
input and nonprivate directories/files without changing unrelated permissions or
files. These tests use disposable databases, not a production restore or VM disk
recovery. Full disaster recovery and native-client synchronization remain separate
acceptance gates.
