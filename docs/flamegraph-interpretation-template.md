# Flamegraph Interpretation Template

Use this template when interpreting a `py-spy record` flamegraph, speedscope profile, or raw sample output for a user.

## Key Reading Rules

Before making claims, remember these rules:

- Width matters: a wider frame means more samples were observed in that stack.
- Height is call depth, not cost by itself.
- Left-to-right order is not chronological time.
- Color is usually for visual grouping and does not mean hot/cold unless the renderer explicitly says so.
- A single short profile is evidence, not proof. Use confidence levels.
- Compare nearby frames by percentage / sample count, not by visual impression alone.
- Check whether the profile included subprocesses, native stacks, idle frames, or GIL-only samples.

## Report Template

```md
# py-spy Flamegraph Analysis

## 1. Capture Context

- Target: <service / command / PID>
- Environment: <host / Docker / Kubernetes / CI / local>
- Command used: `<py-spy command>`
- Duration: <seconds>
- Sampling rate: <samples/sec>
- Format: <flamegraph / speedscope / raw / chrometrace>
- Subprocesses included: <yes / no / unknown>
- Native stacks included: <yes / no / unknown>
- GIL-only mode: <yes / no / unknown>
- Confidence: <low / medium / high>

## 2. Executive Summary

One or two sentences describing the main finding.

Example:

> Most samples are concentrated under `json.dumps -> encoder.iterencode`, so this capture suggests the request path is CPU-bound on JSON serialization rather than blocked on network or database I/O.

## 3. Main Hotspots

| Rank | Stack / Function | Approx. Share | Category | Evidence | Interpretation |
|---:|---|---:|---|---|---|
| 1 | `<module.function>` | `<% or samples>` | CPU / IO / lock / native / unknown | `<wide frame / repeated stack>` | `<what it likely means>` |
| 2 | `<module.function>` | `<% or samples>` | `<category>` | `<evidence>` | `<interpretation>` |
| 3 | `<module.function>` | `<% or samples>` | `<category>` | `<evidence>` | `<interpretation>` |

## 4. Stack Walkthrough

### Hot path 1

```text
<root>
  -> <framework entry>
  -> <application function>
  -> <hot function>
```

Interpretation:

- What this path is doing:
- Why it is expensive:
- Whether it is expected:
- Whether it is user code or dependency code:

### Hot path 2

```text
<root>
  -> ...
```

Interpretation:

- ...

## 5. Bottleneck Classification

Choose the most likely classification and explain why.

- CPU-bound Python code:
  - wide frames in pure Python functions
  - stable hot functions across samples
  - likely fix: algorithm, caching, batching, avoiding repeated work

- Native extension / C library time:
  - frames point into Cython, NumPy, compression, regex, crypto, JSON, image processing, or native stack if `--native` was enabled
  - likely fix: inspect native call, input size, vectorization, symbols, or library behavior

- Lock contention:
  - stacks repeatedly show lock acquire / wait / queue behavior
  - likely fix: reduce critical section, avoid global lock, inspect thread model

- I/O or external wait:
  - frames show socket, database client, HTTP client, file read/write, subprocess wait, or event loop wait
  - likely fix: latency tracing, timeout settings, connection pool, query analysis

- GIL-related contention:
  - many Python threads but only one hot path making progress, or `--gil` profile points to a narrow section
  - likely fix: multiprocessing, native release of GIL, async model review, reduce shared Python CPU work

- Idle / inconclusive:
  - samples are mostly idle, sleeping, polling, or spread thinly
  - likely fix: capture during active load, increase duration, include subprocesses, or use `dump`

## 6. What Not To Conclude

List things that the profile does not prove.

Examples:

- This single 30-second capture does not prove the issue happens all day.
- This flamegraph does not show wall-clock latency per request unless the sampled process was executing that request path.
- Without `--subprocesses`, worker child processes may be missing.
- Without `--native`, native extension details may be hidden.
- Without application traces, database or network latency attribution may be incomplete.

## 7. Recommended Next Steps

Prioritize safe, specific next actions.

1. <small code or config inspection>
2. <repeat profile under known load / include subprocesses / use speedscope>
3. <add application-level timing around suspected function>
4. <optimize or test one suspected hotspot>

## 8. Suggested Follow-up Commands

```bash
# Longer capture if the first profile is noisy
py-spy record -o profile-60s.svg --duration 60 --pid <PID>

# Include subprocesses for worker pools
py-spy record --subprocesses -o profile-workers.svg --duration 60 --pid <PID>

# Speedscope output for easier interactive inspection
py-spy record --format speedscope -o profile.speedscope.json --duration 60 --pid <PID>

# Stack dump for hang / deadlock suspicion
py-spy dump --pid <PID> > py-spy-dump.txt
```

Do not suggest `sudo`, `ptrace_scope` changes, Docker `SYS_PTRACE`, Kubernetes security context changes, or `--locals` unless the user explicitly confirms the risk.
```

## Quick Interpretation Patterns

### Wide user function

Likely meaning: application code is doing repeated or expensive CPU work.

Check:

- input size
- loops
- repeated serialization/deserialization
- regex behavior
- cache misses
- unnecessary conversions

### Wide framework function

Likely meaning: framework overhead, middleware, routing, template rendering, validation, or dependency behavior.

Check:

- whether user code below the framework frame is actually the root cause
- middleware count
- logging / tracing hooks
- request parsing / response rendering

### Wide JSON / serialization stack

Likely meaning: response/request payload transformation is expensive.

Check:

- payload size
- repeated `json.dumps` / `json.loads`
- pydantic / dataclass conversion
- avoid serializing unused fields

### Wide database client stack

Likely meaning: query, result fetching, ORM hydration, or waiting on DB.

Check:

- SQL query timing
- result size
- N+1 queries
- connection pool saturation
- ORM object construction cost

### Wide logging stack

Likely meaning: excessive logging, formatting, synchronous handlers, or slow log sink.

Check:

- log level
- repeated string formatting
- JSON logging cost
- blocking file/network handlers

### Spread-out stacks

Likely meaning: no single hotspot or capture is noisy.

Check:

- longer duration
- capture under stronger load
- use speedscope
- compare multiple profiles

## Final Answer Shape

When responding to the user, prefer this compact structure:

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
