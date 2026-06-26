# Cookbook: Hanging or Stuck Python Process

Use this cookbook when a Python service, request, job, or worker appears stuck, stops making progress, or has low CPU usage but poor latency.

This scenario is different from high CPU. Start with stack dumps instead of flamegraphs.

## Symptoms

- Request never returns or takes much longer than normal.
- Background job appears stuck.
- Worker is alive but not making progress.
- CPU usage is low or moderate, not clearly saturated.
- Many threads or workers appear idle, waiting, or blocked.
- Logs stop at a certain step and no exception is shown.

If CPU is high during the incident, use [`high-cpu.md`](high-cpu.md) instead.

## Minimal Safe Workflow

### 1. Identify the target PID

```bash
pgrep -af 'python|gunicorn|uvicorn|celery'
```

Make sure the PID belongs to the target application. Do not profile unrelated processes.

### 2. Capture a stack dump

```bash
py-spy dump --pid <PID> > py-spy-dump.txt
```

Helper form:

```bash
./py-spy-helper.sh dump-pid <PID> py-spy-dump.txt
```

### 3. Analyze the dump

```bash
./py-spy-helper.sh analyze-dump py-spy-dump.txt dump-analysis.md 10
```

Read both the original dump and the generated analysis before making a conclusion.

### 4. Capture a second dump if needed

If the symptom continues, capture another dump after 5-15 seconds:

```bash
py-spy dump --pid <PID> > py-spy-dump-2.txt
./py-spy-helper.sh analyze-dump py-spy-dump-2.txt dump-analysis-2.md 10
```

If the same leaf frames repeat across dumps, confidence increases that the process is genuinely stuck or waiting there.

## Worker Pools

For gunicorn, celery, multiprocessing, or uvicorn worker models, decide whether to inspect the master process or a specific worker.

The master process may look idle while one worker is stuck. Prefer profiling the actual worker PID when possible:

```bash
py-spy dump --pid <WORKER_PID> > worker-dump.txt
./py-spy-helper.sh analyze-dump worker-dump.txt worker-dump-analysis.md 10
```

If unsure, list child processes:

```bash
pgrep -P <MASTER_PID> -af .
```

## How to Read the Dump

Focus on repeated leaf frames and thread categories.

Common patterns:

- repeated `threading.py`, `queue.py`, `wait`, `acquire`: possible lock contention, queue wait, or worker starvation
- repeated `socket`, `ssl.py`, `requests`, `urllib3`, `httpx`, `aiohttp`: network or upstream service wait
- repeated `sqlalchemy`, `psycopg`, `asyncpg`, `cursor`, `execute`, `fetch`: database wait, connection pool pressure, or slow query
- repeated `asyncio`, `selectors.py`, `epoll`, `poll`: event loop wait; may be normal if idle, suspicious if request is stuck
- repeated `time.sleep` or timer frames: intentional sleep, backoff, scheduler wait, or retry loop
- repeated logging frames: synchronous logging sink, blocked handler, or excessive logging
- repeated application frames: user code path may be blocked inside a loop, wait, or external call

## Common Misreads

- A stack dump is a snapshot, not proof by itself.
- Event loop wait can be normal if the service was idle when captured.
- Sleeping threads can be normal background workers.
- The main thread is not always the request-handling thread in worker models.
- A single worker may be stuck while the master process looks healthy.
- `dump` output without `--locals` intentionally avoids exposing local variables and secrets.

## Next Steps by Finding

### Lock / synchronization wait

- identify which lock, queue, or condition variable is involved
- inspect the code path that holds the lock
- reduce critical sections
- check for missing `notify`, dead worker, or queue backpressure
- capture another dump to see whether the same wait repeats

### Database / ORM wait

- check SQL timing and slow query logs
- inspect query count and result size
- check connection pool saturation
- verify transaction boundaries
- use request-level timing around DB calls

### Network / HTTP I/O wait

- check upstream service latency
- check retries and backoff behavior
- verify timeout settings
- inspect DNS/TLS/connect timing if available
- correlate with application logs or tracing

### Async event loop wait

- confirm the dump was captured during the slow request, not idle time
- look for blocking synchronous calls inside async handlers
- check event loop lag metrics if available
- compare multiple dumps under load

### Sleep / timer

- identify whether sleep is intentional backoff, polling, rate limiting, or scheduler wait
- check retry loop conditions
- check whether the process is waiting for external state that never changes

### Repeated application frame

- inspect the function around the repeated leaf frame
- look for unbounded loops, blocking calls, missing timeout, or queue waits
- add narrow timing logs around the suspected section

## When to Use Flamegraph Too

Use a flamegraph after dump analysis if:

- CPU is also high
- the process is not stuck but slow
- dump shows active user code rather than waiting
- you need sample percentages rather than one stack snapshot

```bash
py-spy record -o profile.svg --duration 30 --pid <PID>
./py-spy-helper.sh analyze-flamegraph profile.svg profile-analysis.md 10
```

## Dangerous / Confirm First

Ask for explicit confirmation before suggesting or using:

- `sudo py-spy ...`
- changing `/proc/sys/kernel/yama/ptrace_scope`
- Docker `--cap-add SYS_PTRACE`
- Kubernetes `securityContext.capabilities.add: [SYS_PTRACE]`
- `py-spy dump --locals`
- repeated or long production captures

`py-spy dump --locals` can expose passwords, tokens, database connection strings, request bodies, or other secrets.

## Final Report Shape

```md
结论：进程疑似卡在 <lock / DB / network / event loop / sleep / application code>，置信度 <low / medium / high>。

证据：
- 重复 leaf frame：`<frame>` 出现 <count> 次。
- dump 分类显示 <category>。
- 采集时症状是 <request stuck / worker not progressing / low CPU slow>。

下一步：
1. <safe verification step, e.g. capture second dump or inspect specific function>
2. <focused follow-up, e.g. DB timing / upstream latency / lock owner inspection>
```
