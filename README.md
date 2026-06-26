# py-spy Skill

A portable Skill for agent-assisted Python performance diagnosis with [`py-spy`](https://github.com/benfred/py-spy).

This repository does **not** vendor or modify `py-spy`. It provides a lightweight workflow for agents such as Claude Code, Codex, or other coding assistants to choose safe `py-spy` commands, collect short profiles, and interpret results.

## What this Skill is for

Use this Skill when diagnosing Python runtime problems such as:

- high CPU usage
- slow requests
- stuck or hanging Python processes
- gunicorn / uvicorn / celery worker issues
- multiprocessing subprocess profiling
- flamegraph or stack dump collection
- structured flamegraph interpretation reports

## What this Skill is not for

- It is not a fork of `py-spy`.
- It is not a replacement for `py-spy` documentation.
- It does not automatically run privileged commands.
- It does not automatically change `ptrace_scope`, Docker capabilities, or Kubernetes security context.

## Prerequisites

Install `py-spy` first:

```bash
pip install py-spy
```

Alternative installation methods include downloading upstream releases or using `cargo install py-spy`.

## Quick Start

After cloning this repository:

```bash
chmod +x py-spy-helper.sh scripts/smoke-py-spy-skill.sh
bash scripts/smoke-py-spy-skill.sh
```

Check your environment:

```bash
./py-spy-helper.sh doctor
```

Record a short flamegraph from an existing Python process:

```bash
./py-spy-helper.sh record-pid <PID> profile.svg 30
```

Dump current Python stack traces:

```bash
./py-spy-helper.sh dump-pid <PID> stack.txt
```

Open a live top-like view:

```bash
./py-spy-helper.sh top-pid <PID>
```

Record a Python command launched by `py-spy`:

```bash
./py-spy-helper.sh record-cmd profile.svg -- python app.py
```

## Flamegraph Interpretation

Use [`docs/flamegraph-interpretation-template.md`](docs/flamegraph-interpretation-template.md) when turning a flamegraph, speedscope profile, raw sample output, or screenshot into a user-facing diagnosis.

The template emphasizes:

- width means sample frequency, not chronological order
- height is stack depth, not cost by itself
- confidence levels for short captures
- bottleneck classification: CPU, I/O, lock, native, GIL, idle, or inconclusive
- safe next steps before privileged profiling changes

## Safety Model

This Skill defaults to read-only diagnostics:

- no automatic `sudo`
- no automatic `/proc/sys/kernel/yama/ptrace_scope` edits
- no automatic Docker or Kubernetes capability changes
- no default `--locals`, because local variables may expose secrets
- short default recording duration to reduce production risk

If privileged access is needed, the agent should explain why and ask the user to confirm before suggesting an elevated command.

## Install in Claude Code

Manual install example:

```bash
mkdir -p ~/.claude/skills
cp -r /path/to/py-spy-skill ~/.claude/skills/py-spy
chmod +x ~/.claude/skills/py-spy/py-spy-helper.sh
chmod +x ~/.claude/skills/py-spy/scripts/smoke-py-spy-skill.sh
```

Then start a new Claude Code session and ask:

```text
Use the py-spy skill to diagnose this Python process.
```

## Install in Codex

From a Codex session, when a skill installer is available:

```text
Use $skill-installer to install the skill from https://github.com/luojiyin1987/py-spy-skill with path . and name py-spy.
```

Manual install:

```bash
SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_DIR"
cp -r /path/to/py-spy-skill "$SKILLS_DIR/py-spy"
chmod +x "$SKILLS_DIR/py-spy/py-spy-helper.sh"
chmod +x "$SKILLS_DIR/py-spy/scripts/smoke-py-spy-skill.sh"
```

## Attribution

This Skill is built around the upstream `py-spy` CLI by Ben Frederickson and contributors:

https://github.com/benfred/py-spy

`py-spy` itself is licensed by its upstream project. This repository only contains Skill instructions and helper scripts.
