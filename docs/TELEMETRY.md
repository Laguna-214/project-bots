# Read-only utilization telemetry

`project_bots.telemetry.collect_metrics()` samples Linux `/proc/stat` CPU deltas
and AMD DRM sysfs GPU busy/VRAM counters. `ComputeService.health()['utilization']`
exposes these observations after a reviewed source rollout. The current installed
services were not restarted or updated; do not assume their API has this field.

Each result has an observation time and sample interval. Missing, unreadable,
invalid or nonadvancing sensors report unavailable/partial with null values, not
fake idle/healthy data. This is **utilization, not trusted security coverage**, model
identity, token throughput, GPU offload evidence, sandbox isolation or a watchdog.
It never calls `SecurityService.observe` or enables execution.

## Actual compute observation

On Nov 3, existing strict-key SSH as `pbcompute@10.0.50.56` executed the source
sensor function **in memory only**. It installed no files, started no model/VM,
and changed no service or host policy. Observation timestamp: `1793712716.8167493`.

- CPU sample: available, busy `0.0%` during the 0.05-second sampling window.
- AMD `card2`: sensors available, GPU busy `0%`.
- VRAM total: `17163091968` bytes; used: `6247198720` bytes.

These readings show sensor availability and aggregate host device allocation,
not which model/process allocated it or how quickly it generates tokens. No
production concurrency was increased. Keep concurrency conservative until the
required four-real-agent/one-loaded-model benchmark and context/permission
isolation acceptance runs under actual security coverage.

## Tests

Two fixture tests demonstrate CPU-delta arithmetic, AMD metrics and truthful
unavailable results. They were observed failing before the module existed and
passing afterward. The actual SSH read above is separate from those fixtures.
No alternate sensor service, root privilege, user-health assertion or agent
self-reporting endpoint was introduced.
