# Python Performance Bottleneck Decision Tree

Use this decision tree before choosing a profiling command or interpreting a result. The goal is to avoid treating every performance problem as a CPU flamegraph problem.

## First Questions

Collect only the context needed to choose the next safe diagnostic step:

- What is slow: startup, one API request, a background job, a worker, or the whole service?
- Is CPU high while the problem happens?
- Is the process stuck or still making progress?
- Is the target a single process or a worker pool?
- Is the app running on host, Docker, Kubernetes, CI, or local dev?
- Was the profile captured during real load or an idle period?
- Are subprocesses relevant: gunicorn, uvicorn workers, celery, multiprocessing?

## Decision Tree

```text
Start
 |
 |-- Process is hung / request never returns?
 |     |
 |     |-- yes -> py-spy dump -> analyze-dump
 |     |          Look for lock wait, event loop wait, blocking I/O, repeated stacks.
 |     |
 |     |-- no  -> continue
 |
 |-- CPU is high during the issue?
 |     |
 |     |-- yes -> py-spy top or short record
 |     |          Then analyze-flamegraph.
 |     |
 |     |-- no  -> continue
 |
 |-- Slow request/job but CPU is not high?
 |     |
 |     |-- likely I/O / DB / external service / queue wait
 |     |-- use app timing, logs, traces, DB slow query logs, py-spy dump if stuck
 |
 |-- Worker pool / subprocess model?
 |     |
 |     |-- yes -> record with --subprocesses or target the worker PID directly
 |     |
 |     |-- no  -> single PID profiling is usually enough
 |
 |-- Native-heavy workload?
 |     |
 |     |-- yes -> consider --native if platform supports it and symbols help
 |     |
 |     |-- no  -> normal Python stacks are usually enough
```

## Bottleneck Types

| Type | Typical Signal | Recommended py-spy Action | Non-py-spy Follow-up |
|---|---|---|---|
| CPU-bound Python | High CPU, wide user-code frames | `record`, `top`, `analyze-flamegraph` | inspect algorithm, cache, batching |
| Serialization | wide `json`, `pydantic`, `pickle`, `yaml` frames | `record`, `analyze-flamegraph` | check payload size and conversions |
| Database / ORM | `execute`, `fetch`, ORM hydration frames | `record`, sometimes `dump` | SQL logs, `EXPLAIN`, query count |
| Network / HTTP I/O | socket, HTTP client, SSL, retry frames | `dump` or app tracing | timeout, retries, upstream latency |
| Lock contention | `threading`, `queue`, `lock`, `wait` frames | `dump`, `analyze-dump` | reduce critical sections |
| Async event loop wait | `asyncio`, `select`, `poll`, event loop frames | `dump`, `record` under load | event loop lag, blocking calls |
| Native extension | NumPy, pandas, crypto, compression, Cython | `record --native` if appropriate | symbols, native profiler, input size |
| Idle / noisy capture | scattered frames, low top percentage | longer `record`, capture under load | reproduce with stable workload |
| Memory / GC | CPU not high, latency grows over time | py-spy may be insufficient | tracemalloc, memray, GC logs |

## Command Mapping

### High CPU now

```bash
py-spy top --pid <PID>
py-spy record -o profile.svg --duration 30 --pid <PID>
./py-spy-helper.sh analyze-flamegraph profile.svg profile-analysis.md 10
```

### Hung or stuck process

```bash
py-spy dump --pid <PID> > py-spy-dump.txt
./py-spy-helper.sh analyze-dump py-spy-dump.txt dump-analysis.md
```

### Worker pool

```bash
py-spy record --subprocesses -o profile-workers.svg --duration 60 --pid <MASTER_PID>
```

Or profile the specific worker PID directly.

### Native-heavy workload

```bash
py-spy record --native -o profile-native.svg --duration 60 --pid <PID>
```

Use `--native` only when it is useful and supported. It may require symbols for good output.

## Safety Boundary

Do not automatically run or suggest these as immediate commands:

- `sudo py-spy ...`
- changing `/proc/sys/kernel/yama/ptrace_scope`
- adding Docker `SYS_PTRACE`
- modifying Kubernetes `securityContext`
- `py-spy dump --locals`

If one is needed, explain why, explain the risk, and ask the user for explicit confirmation.

## Output Guidance

A good final diagnosis should include:

```md
结论：<main bottleneck hypothesis>

证据：
- <py-spy evidence>
- <context evidence>

类型：<CPU / I/O / DB / lock / native / memory / inconclusive>
置信度：<low / medium / high>

下一步：
1. <safe verification step>
2. <one focused fix or deeper measurement>
```
