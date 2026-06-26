# Cookbook: High CPU Python Process

Use this cookbook when the symptom is high CPU usage in a Python process or worker.

## Symptoms

- CPU usage is high during the incident.
- Requests or jobs are slow while CPU is high.
- The process is still making progress, but latency is poor.
- A worker pool may have one or more hot workers.

If the process is stuck but CPU is low, prefer `py-spy dump` and `analyze-dump` instead.

## Minimal Safe Workflow

### 1. Identify the target PID

```bash
pgrep -af 'python|gunicorn|uvicorn|celery'
```

Make sure the PID belongs to the target application. Do not profile unrelated processes.

### 2. Quick live view

```bash
py-spy top --pid <PID>
```

Use this to check whether one function is obviously hot right now.

### 3. Short flamegraph capture

```bash
py-spy record -o profile.svg --duration 30 --pid <PID>
```

Or through the helper:

```bash
./py-spy-helper.sh record-pid <PID> profile.svg 30
```

### 4. First-pass analysis

```bash
./py-spy-helper.sh analyze-flamegraph profile.svg profile-analysis.md 10
```

Then inspect both `profile.svg` and `profile-analysis.md` before drawing conclusions.

## Worker Pools

For gunicorn, celery, multiprocessing, or uvicorn worker models, profiling only the master process can miss the real hotspot.

Use one of these approaches:

```bash
# Include child processes
py-spy record --subprocesses -o profile-workers.svg --duration 60 --pid <MASTER_PID>

# Or profile the hot worker directly
py-spy record -o profile-worker.svg --duration 60 --pid <WORKER_PID>
```

Helper form:

```bash
PY_SPY_SUBPROCESSES=1 ./py-spy-helper.sh record-pid <MASTER_PID> profile-workers.svg 60
```

## How to Read the Result

Look for the widest user-relevant frames.

Common patterns:

- wide user function: algorithm, loop, repeated work, missing cache
- wide `json` / `pydantic`: serialization or validation cost
- wide ORM / `fetch` frames: query result size, ORM hydration, N+1 queries
- wide logging frames: excessive or synchronous logging
- wide regex / parser frames: expensive matching or parsing
- wide compression / crypto frames: payload or encryption cost
- wide native numeric frames: NumPy, pandas, crypto, compression, ML workload

## Common Misreads

- Wide frame means many samples, not necessarily wall-clock latency for one request.
- Frame height is call depth, not cost.
- Left-to-right order is not a timeline.
- Color usually does not mean hot/cold.
- One 30-second capture is a hypothesis, not proof.
- If `--subprocesses` was missing, worker children may be absent.
- If `--native` was missing, native extension details may be hidden.

## Next Steps by Finding

### CPU-bound user code

- inspect the loop or algorithm
- check input size
- add small timing around the suspected function
- test caching, batching, or avoiding repeated work

### JSON / serialization

- measure payload size
- avoid serializing unused fields
- reduce repeated conversions
- compare serializer choices carefully

### Database / ORM

- enable SQL timing
- inspect query count
- check result size
- run `EXPLAIN` for slow queries
- look for ORM object hydration cost

### Logging

- lower log level during hot path
- avoid expensive string formatting before log-level checks
- check synchronous handlers
- check JSON logging overhead

### Native / numeric

- consider `--native` if supported
- check input size and vectorization
- inspect library-level behavior
- compare with a smaller reproducible input

## Safe Follow-up Commands

```bash
# Longer capture
py-spy record -o profile-60s.svg --duration 60 --pid <PID>

# Speedscope output
py-spy record --format speedscope -o profile.speedscope.json --duration 60 --pid <PID>

# Include workers
py-spy record --subprocesses -o profile-workers.svg --duration 60 --pid <MASTER_PID>
```

## Dangerous / Confirm First

Ask for explicit confirmation before suggesting or using:

- `sudo py-spy ...`
- changing `/proc/sys/kernel/yama/ptrace_scope`
- Docker `--cap-add SYS_PTRACE`
- Kubernetes `securityContext.capabilities.add: [SYS_PTRACE]`
- `py-spy dump --locals`
- very long production captures

## Final Report Shape

```md
结论：CPU 热点集中在 `<function>`，疑似 <具体原因>。

证据：
- `<function>` 占约 <percent>% samples。
- 该栈位于 <user code / dependency / framework>。

置信度：<low / medium / high>

下一步：
1. <inspect or add timing around the function>
2. <repeat profile / include workers / verify optimization>
```
