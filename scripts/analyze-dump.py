#!/usr/bin/env python3
"""Analyze `py-spy dump` text and emit a Markdown triage report.

This parser is intentionally heuristic. It does not need py-spy internals and does
not require third-party packages. It groups repeated frames, classifies common wait
patterns, and generates a safe next-step report.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

THREAD_HEADER_RE = re.compile(r"^(Thread|Process)\s+.*", re.IGNORECASE)
FRAME_RE = re.compile(r"^\s*(?:File\s+\"(?P<file>[^\"]+)\",\s+line\s+(?P<line>\d+),\s+in\s+(?P<func>.+)|(?P<raw>.+))$")

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "lock / synchronization wait",
        (
            "threading.py",
            "lock",
            "rlock",
            "semaphore",
            "condition",
            "queue.py",
            "wait",
            "acquire",
        ),
    ),
    (
        "async / event loop wait",
        (
            "asyncio",
            "selectors.py",
            "select.py",
            "epoll",
            "poll",
            "run_forever",
            "run_until_complete",
            "uvloop",
        ),
    ),
    (
        "network / HTTP I/O",
        (
            "socket",
            "ssl.py",
            "urllib",
            "urllib3",
            "requests",
            "httpx",
            "aiohttp",
            "grpc",
            "botocore",
        ),
    ),
    (
        "database / ORM",
        (
            "sqlalchemy",
            "django/db",
            "django.db",
            "psycopg",
            "asyncpg",
            "pymysql",
            "sqlite",
            "redis",
            "execute",
            "fetchone",
            "fetchall",
            "cursor",
        ),
    ),
    (
        "sleep / timer",
        (
            "time.sleep",
            "sleep",
            "timer",
            "sched.py",
        ),
    ),
    (
        "logging",
        (
            "logging",
            "loguru",
            "structlog",
        ),
    ),
    (
        "serialization / parsing",
        (
            "json",
            "pydantic",
            "pickle",
            "yaml",
            "xml",
            "html.parser",
            "regex",
            "re.py",
        ),
    ),
]

@dataclass
class ThreadDump:
    header: str
    frames: list[str] = field(default_factory=list)

    @property
    def leaf(self) -> str:
        return self.frames[-1] if self.frames else "<no frames>"

    @property
    def stack_text(self) -> str:
        return "\n".join(self.frames)


def normalize_frame(line: str) -> str | None:
    line = line.rstrip()
    if not line.strip():
        return None
    match = FRAME_RE.match(line)
    if not match:
        return None
    if match.group("file"):
        file = match.group("file") or ""
        lineno = match.group("line") or ""
        func = (match.group("func") or "").strip()
        return f"{file}:{lineno} in {func}"
    raw = (match.group("raw") or "").strip()
    if raw.startswith(("Thread ", "Process ")):
        return None
    return raw or None


def parse_dump(path: Path) -> list[ThreadDump]:
    threads: list[ThreadDump] = []
    current: ThreadDump | None = None

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip()
        if THREAD_HEADER_RE.match(line):
            current = ThreadDump(header=line.strip())
            threads.append(current)
            continue
        if current is None:
            continue
        frame = normalize_frame(line)
        if frame:
            current.frames.append(frame)

    # Fallback: some py-spy outputs are stack-only snippets without thread headers.
    if not threads:
        fallback = ThreadDump(header="Thread unknown")
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            frame = normalize_frame(raw_line)
            if frame:
                fallback.frames.append(frame)
        if fallback.frames:
            threads.append(fallback)

    return threads


def classify_text(text: str) -> str:
    lower = text.lower()
    for category, needles in CATEGORY_RULES:
        if any(needle in lower for needle in needles):
            return category
    if ".py:" in lower or lower.startswith(("/", "src/", "app/")):
        return "application Python code"
    return "unknown / inspect manually"


def confidence(threads: list[ThreadDump], leaf_counts: Counter[str]) -> str:
    if not threads:
        return "low"
    if leaf_counts and leaf_counts.most_common(1)[0][1] >= max(2, len(threads) // 2):
        return "medium"
    if len(threads) >= 3:
        return "medium"
    return "low"


def render_report(path: Path, threads: list[ThreadDump], top_n: int) -> str:
    leaf_counts = Counter(thread.leaf for thread in threads)
    category_counts = Counter(classify_text(thread.stack_text) for thread in threads)
    conf = confidence(threads, leaf_counts)

    lines: list[str] = []
    lines.append("# py-spy Dump Analysis")
    lines.append("")
    lines.append("## 1. Capture Context")
    lines.append("")
    lines.append(f"- Input file: `{path}`")
    lines.append(f"- Parsed threads/process sections: {len(threads)}")
    lines.append(f"- Confidence: {conf}")
    lines.append("")

    lines.append("## 2. Executive Summary")
    lines.append("")
    if threads:
        category, count = category_counts.most_common(1)[0]
        lines.append(
            f"The dump most strongly suggests **{category}** in {count}/{len(threads)} parsed thread sections. "
            "This is a heuristic stack-dump triage result and should be verified with context."
        )
    else:
        lines.append("No thread stacks were parsed. Confirm the input is text output from `py-spy dump`.")
    lines.append("")

    lines.append("## 3. Repeated Leaf Frames")
    lines.append("")
    lines.append("| Rank | Leaf frame | Count | Category |")
    lines.append("|---:|---|---:|---|")
    if leaf_counts:
        for idx, (leaf, count) in enumerate(leaf_counts.most_common(top_n), start=1):
            escaped = leaf.replace("|", "\\|")
            lines.append(f"| {idx} | `{escaped}` | {count} | {classify_text(leaf)} |")
    else:
        lines.append("| - | - | - | No frames parsed. |")
    lines.append("")

    lines.append("## 4. Category Summary")
    lines.append("")
    if category_counts:
        for category, count in category_counts.most_common():
            lines.append(f"- **{category}**: {count} thread section(s)")
    else:
        lines.append("- Inconclusive")
    lines.append("")

    lines.append("## 5. Representative Threads")
    lines.append("")
    for idx, thread in enumerate(threads[:top_n], start=1):
        lines.append(f"### Thread {idx}")
        lines.append("")
        lines.append(f"- Header: `{thread.header}`")
        lines.append(f"- Category: {classify_text(thread.stack_text)}")
        lines.append(f"- Leaf: `{thread.leaf}`")
        if thread.frames:
            lines.append("")
            lines.append("```text")
            for frame in thread.frames[-8:]:
                lines.append(frame)
            lines.append("```")
        lines.append("")

    lines.append("## 6. What This May Mean")
    lines.append("")
    lines.append("- Many threads at the same lock/wait frame can indicate contention or a bottlenecked queue.")
    lines.append("- Network, DB, or HTTP frames often indicate external latency or connection-pool pressure.")
    lines.append("- Event-loop wait frames can be normal when idle; confirm the dump was captured during the issue.")
    lines.append("- Sleep frames may be normal background workers unless they explain the user-visible symptom.")
    lines.append("- A single dump is a snapshot, not proof of a persistent bottleneck.")
    lines.append("")

    lines.append("## 7. Recommended Next Steps")
    lines.append("")
    if category_counts:
        top_category = category_counts.most_common(1)[0][0]
        if "lock" in top_category:
            lines.append("1. Inspect the lock/queue owner and reduce critical sections.")
            lines.append("2. Capture another dump during the same symptom and compare repeated leaf frames.")
        elif "database" in top_category:
            lines.append("1. Check SQL timing, query count, and connection pool saturation.")
            lines.append("2. Capture request-level timing around DB calls.")
        elif "network" in top_category:
            lines.append("1. Check upstream latency, retries, DNS/TLS behavior, and timeout settings.")
            lines.append("2. Correlate with application logs or tracing.")
        elif "async" in top_category:
            lines.append("1. Confirm whether the service was idle or under load during the dump.")
            lines.append("2. Look for blocking synchronous calls inside async request paths.")
        else:
            lines.append("1. Inspect the repeated leaf frames and their callers.")
            lines.append("2. If CPU is high, collect a flamegraph and run `analyze-flamegraph`.")
    else:
        lines.append("1. Re-run `py-spy dump --pid <PID> > py-spy-dump.txt` during the incident.")
        lines.append("2. Confirm the target PID belongs to the Python process of interest.")
    lines.append("")

    lines.append("## 8. Safe Follow-up Commands")
    lines.append("")
    lines.append("```bash")
    lines.append("py-spy dump --pid <PID> > py-spy-dump.txt")
    lines.append("./py-spy-helper.sh analyze-dump py-spy-dump.txt dump-analysis.md")
    lines.append("py-spy record -o profile.svg --duration 30 --pid <PID>")
    lines.append("```")
    lines.append("")
    lines.append("Do not use `py-spy dump --locals` unless the user explicitly confirms the risk of exposing secrets.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Analyze py-spy dump text and emit Markdown.")
    parser.add_argument("input", type=Path, help="Input text file from py-spy dump")
    parser.add_argument("-o", "--output", type=Path, help="Output Markdown report path")
    parser.add_argument("--top", type=int, default=10, help="Number of repeated frames / threads to include")
    args = parser.parse_args(argv)

    if args.top <= 0:
        parser.error("--top must be positive")
    if not args.input.exists():
        parser.error(f"input does not exist: {args.input}")

    threads = parse_dump(args.input)
    report = render_report(args.input, threads, args.top)

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote analysis: {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
