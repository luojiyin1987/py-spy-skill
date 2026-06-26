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
- extracting first-pass hotspot reports from py-spy SVG flamegraphs

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

### First-pass flamegraph analysis

Use after generating an SVG flamegraph with `py-spy record`. This extracts frame titles from the SVG, sorts by sample percentage, applies coarse categories, and writes a Markdown report.

```bash
./py-spy-helper.sh analyze-flamegraph profile.svg profile-analysis.md 10
```

Treat the generated report as triage input. The agent must still inspect the flamegraph context and apply the interpretation template before giving final advice.

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

When the user provides a flamegraph, speedscope profile, raw sample output, or screenshot of a flamegraph, use `docs/flamegraph-interpretation-template.md` as the report structure.

For SVG flamegraphs, first run this when the file is available in the workspace:

```bash
./py-spy-helper.sh analyze-flamegraph <INPUT.svg> <OUTPUT.md> 10
```

Then combine the generated report with visual inspection of the flamegraph.

Core reading rules:

- Width matters: a wider frame means more samples were observed in that stack.
- Height is call depth, not cost by itself.
- Left-to-right order is not chronological time.
- Color is usually for visual grouping and does not mean hot/cold unless the renderer explicitly says so.
- A single short profile is evidence, not proof. Use confidence levels.
- Check whether the profile included subprocesses, native stacks, idle frames, or GIL-only samples.

Minimum answer shape:

```md
结论：<one-sentence main finding>

最热路径：
`<root> -> <function> -> <hotspot>`

判断：这是 <CPU / IO / lock / native / GIL / inconclusive> 问题，置信度 <low / medium / high>。

证据：
- <evidence 1>
- <evidence 2>

下一步：
1. <safe next step>
2. <optional deeper profile>
```

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
- `python3`
- Python application to profile
- Optional: `speedscope` viewer for `.speedscope.json` files

## Notes

- Helper script: `py-spy-helper.sh`
- Flamegraph analyzer: `scripts/analyze-flamegraph.py`
- Flamegraph template: `docs/flamegraph-interpretation-template.md`
- Smoke test: `scripts/smoke-py-spy-skill.sh`
- Upstream project: https://github.com/benfred/py-spy
