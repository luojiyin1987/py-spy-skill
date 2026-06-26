---
name: py-spy
description: Diagnose Python performance problems with py-spy using safe profiling workflows, stack dumps, and flamegraph interpretation.
---

# py-spy Python Profiling Skill

Use this skill when the user needs to diagnose Python runtime behavior with `py-spy`, especially:

- high CPU usage
- slow Python requests or jobs
- stuck or hanging Python processes
- gunicorn, uvicorn, celery, multiprocessing, or worker-pool issues
- generating flamegraphs, speedscope profiles, or stack dumps
- interpreting `py-spy top`, `record`, or `dump` output

This skill wraps the upstream `py-spy` CLI. It does not modify `py-spy` source code.

## Default Workflow

1. Clarify the target process only when necessary:
   - existing process PID
   - command to launch under `py-spy`
   - container / Kubernetes / host context
   - whether subprocesses matter
2. Start with the least invasive diagnostic:
   - `dump` for hangs or deadlocks
   - `top` for live CPU hotspots
   - short `record` for flamegraph evidence
3. Prefer short recordings first, usually 15-60 seconds.
4. Save artifacts with clear names, for example:
   - `py-spy-profile.svg`
   - `py-spy-profile.speedscope.json`
   - `py-spy-dump.txt`
5. Interpret the result for the user:
   - hottest function or stack
   - likely bottleneck category: CPU-bound, IO wait, lock contention, idle, native extension, or GIL-related
   - confidence level
   - next recommended diagnostic step

## Command Selection

### Check environment

```bash
./py-spy-helper.sh doctor
```

### Live CPU view

Use when the user asks "what is using CPU right now?"

```bash
py-spy top --pid <PID>
```

Helper form:

```bash
./py-spy-helper.sh top-pid <PID>
```

### Flamegraph for an existing process

Use when the user needs evidence that can be inspected later.

```bash
py-spy record -o profile.svg --duration 30 --pid <PID>
```

Helper form:

```bash
./py-spy-helper.sh record-pid <PID> profile.svg 30
```

### Stack dump for a stuck process

Use when the process is hanging, deadlocked, or not making progress.

```bash
py-spy dump --pid <PID>
```

Helper form:

```bash
./py-spy-helper.sh dump-pid <PID> stack.txt
```

### Launch a command under py-spy

Use when attaching to an existing process is blocked by permissions.

```bash
py-spy record -o profile.svg --duration 30 -- python app.py
```

Helper form:

```bash
./py-spy-helper.sh record-cmd profile.svg -- python app.py
```

### Include subprocesses

Use for gunicorn, celery, multiprocessing, or worker pools.

```bash
py-spy record --subprocesses -o profile.svg --duration 30 --pid <PID>
```

The helper supports this via an environment variable:

```bash
PY_SPY_SUBPROCESSES=1 ./py-spy-helper.sh record-pid <PID> profile.svg 30
```

## Safety Rules

Always follow these rules:

- Do not automatically run `sudo`.
- Do not automatically change `/proc/sys/kernel/yama/ptrace_scope`.
- Do not automatically add Docker `SYS_PTRACE` capability.
- Do not automatically modify Kubernetes `securityContext`.
- Do not use `py-spy dump --locals` unless the user explicitly confirms, because local variables may contain secrets.
- Do not profile unrelated processes. Make sure the PID belongs to the target Python application.
- Prefer short recording durations before longer production captures.
- Explain any privileged or security-sensitive operation before suggesting it.

When a privileged command is necessary, present it as a suggestion and ask for explicit confirmation before the user runs it.

## Interpreting Output

### Flamegraph

Look for wide frames. A wide frame means many samples were observed in that call path. Explain:

- which stack dominates
- whether the hotspot is user code, framework code, serialization, database client, regex, compression, JSON, logging, or native extension
- whether the result suggests CPU-bound work or waiting around external resources

### `top`

Use `top` as a quick live signal. Explain:

- top function names
- approximate CPU distribution
- whether samples are stable or moving around
- whether a longer `record` run is needed

### `dump`

Use `dump` for hangs. Explain:

- what each thread is doing
- whether threads are sleeping, blocked, waiting on locks, or busy in Python code
- whether the main thread appears stuck
- whether subprocess profiling is needed

## Common Troubleshooting

### Permission denied attaching to PID

Explain that attaching to an existing process may require elevated privileges or ptrace permission. Do not run elevated commands automatically.

Safer alternatives:

- launch the command under `py-spy` instead of attaching
- profile from the host when the process is inside a container
- ask the user to confirm before changing ptrace, Docker, or Kubernetes settings

### Docker

If py-spy runs inside a container and cannot read process memory, Docker may need `SYS_PTRACE`. Do not modify container config automatically.

### Kubernetes

If profiling inside Kubernetes, an ephemeral container or security context may be needed. Explain the tradeoff and ask for confirmation before suggesting changes.

### Native extensions

For C, C++, Cython, NumPy, or other native-heavy workloads, suggest `--native` only when it is supported on the platform and symbols are available.

## Dependencies

- `py-spy`
- Python application to profile
- Optional: `speedscope` viewer for `.speedscope.json` files

## Notes

- Helper script: `py-spy-helper.sh`
- Smoke test: `scripts/smoke-py-spy-skill.sh`
- Upstream project: https://github.com/benfred/py-spy
