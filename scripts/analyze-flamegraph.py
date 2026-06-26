#!/usr/bin/env python3
"""Analyze a py-spy / inferno SVG flamegraph and emit a Markdown report.

This is intentionally lightweight and dependency-free. It extracts frame titles from
SVG <title> elements such as:

    package.module.func (123 samples, 12.34%)

The output is a starting point for agent review, not a final performance verdict.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

TITLE_RE = re.compile(
    r"^(?P<name>.*)\s+\((?P<samples>[0-9,]+)\s+samples?,\s+(?P<percent>[0-9.]+)%\)$"
)

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "JSON / serialization",
        (
            "json.",
            "json/",
            "orjson",
            "ujson",
            "simplejson",
            "pydantic",
            "dataclasses",
            "marshal",
            "pickle",
            "msgpack",
            "yaml",
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
            "mysql",
            "sqlite",
            "mongo",
            "redis",
            "cursor",
            "execute",
            "fetchall",
            "fetchone",
        ),
    ),
    (
        "HTTP / network I/O",
        (
            "requests/",
            "requests.",
            "urllib",
            "httpx",
            "aiohttp",
            "socket",
            "ssl.py",
            "grpc",
            "botocore",
            "urllib3",
        ),
    ),
    (
        "logging",
        (
            "logging/",
            "logging.",
            "logger",
            "loguru",
            "structlog",
        ),
    ),
    (
        "regex / parsing",
        (
            "re.py",
            "sre_",
            "regex",
            "parse",
            "parser",
            "lxml",
            "html.parser",
            "xml/",
        ),
    ),
    (
        "compression / crypto",
        (
            "gzip",
            "zlib",
            "bz2",
            "lzma",
            "zipfile",
            "hashlib",
            "hmac",
            "cryptography",
            "openssl",
        ),
    ),
    (
        "async / event loop wait",
        (
            "asyncio",
            "selectors.py",
            "select.",
            "epoll",
            "poll",
            "uvloop",
            "run_forever",
            "run_until_complete",
        ),
    ),
    (
        "lock / synchronization",
        (
            "threading.py",
            "lock",
            "rlock",
            "semaphore",
            "condition",
            "queue.py",
            "wait",
        ),
    ),
    (
        "native / numeric",
        (
            "numpy",
            "pandas",
            "scipy",
            "torch",
            "tensorflow",
            "sklearn",
            "cython",
            "<native>",
        ),
    ),
]

@dataclass(frozen=True)
class Frame:
    name: str
    samples: int
    percent: float


def parse_svg_titles(path: Path) -> list[Frame]:
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        # Some SVGs contain script/style content that can still be scanned safely.
        return parse_svg_titles_by_regex(path)

    root = tree.getroot()
    frames: list[Frame] = []
    for elem in root.iter():
        if elem.tag.endswith("title") and elem.text:
            frame = parse_title(elem.text)
            if frame:
                frames.append(frame)
    return dedupe_frames(frames)


def parse_svg_titles_by_regex(path: Path) -> list[Frame]:
    text = path.read_text(encoding="utf-8", errors="replace")
    titles = re.findall(r"<title>(.*?)</title>", text, flags=re.DOTALL | re.IGNORECASE)
    frames = [frame for title in titles if (frame := parse_title(html.unescape(title.strip())))]
    return dedupe_frames(frames)


def parse_title(title: str) -> Frame | None:
    title = " ".join(title.strip().split())
    match = TITLE_RE.match(title)
    if not match:
        return None
    name = match.group("name").strip()
    samples = int(match.group("samples").replace(",", ""))
    percent = float(match.group("percent"))
    if not name or name.lower() in {"all", "root"}:
        return None
    return Frame(name=name, samples=samples, percent=percent)


def dedupe_frames(frames: Iterable[Frame]) -> list[Frame]:
    # A flamegraph can contain repeated labels. Keep the largest observed entry per name.
    best: dict[str, Frame] = {}
    for frame in frames:
        old = best.get(frame.name)
        if old is None or (frame.samples, frame.percent) > (old.samples, old.percent):
            best[frame.name] = frame
    return sorted(best.values(), key=lambda f: (f.percent, f.samples), reverse=True)


def classify(name: str) -> str:
    lower = name.lower()
    for category, needles in CATEGORY_RULES:
        if any(needle in lower for needle in needles):
            return category
    if lower.startswith(("/", "src/", "app/")) or ".py:" in lower:
        return "application Python code"
    return "unknown / inspect manually"


def confidence(frames: list[Frame]) -> str:
    if not frames:
        return "low"
    if frames[0].percent >= 30:
        return "high"
    if frames[0].percent >= 10:
        return "medium"
    return "low"


def render_report(path: Path, frames: list[Frame], top_n: int) -> str:
    selected = frames[:top_n]
    conf = confidence(frames)

    lines: list[str] = []
    lines.append("# py-spy Flamegraph Analysis")
    lines.append("")
    lines.append("## 1. Capture Context")
    lines.append("")
    lines.append(f"- Input file: `{path}`")
    lines.append("- Format: SVG flamegraph")
    lines.append("- Subprocesses included: unknown")
    lines.append("- Native stacks included: unknown")
    lines.append("- GIL-only mode: unknown")
    lines.append(f"- Parsed frames: {len(frames)}")
    lines.append(f"- Confidence: {conf}")
    lines.append("")

    lines.append("## 2. Executive Summary")
    lines.append("")
    if selected:
        top = selected[0]
        lines.append(
            f"The widest parsed frame is `{top.name}` at about {top.percent:.2f}% "
            f"({top.samples} samples), categorized as **{classify(top.name)}**."
        )
    else:
        lines.append(
            "No py-spy/inferno-style frame titles were parsed. The SVG may use a different format, "
            "or the file may not be a flamegraph SVG."
        )
    lines.append("")

    lines.append("## 3. Main Hotspots")
    lines.append("")
    lines.append("| Rank | Stack / Function | Approx. Share | Samples | Category | Interpretation |")
    lines.append("|---:|---|---:|---:|---|---|")
    if selected:
        for idx, frame in enumerate(selected, start=1):
            category = classify(frame.name)
            escaped_name = frame.name.replace("|", "\\|")
            lines.append(
                f"| {idx} | `{escaped_name}` | {frame.percent:.2f}% | {frame.samples} | "
                f"{category} | Inspect this frame and its callers/callees in the SVG before changing code. |"
            )
    else:
        lines.append("| - | - | - | - | - | No frames parsed. |")
    lines.append("")

    lines.append("## 4. Bottleneck Classification")
    lines.append("")
    categories: dict[str, float] = {}
    for frame in selected:
        categories[classify(frame.name)] = categories.get(classify(frame.name), 0.0) + frame.percent
    if categories:
        for category, pct in sorted(categories.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"- **{category}**: about {pct:.2f}% across the top {len(selected)} parsed frames.")
    else:
        lines.append("- Inconclusive: no parseable frames.")
    lines.append("")

    lines.append("## 5. What Not To Conclude")
    lines.append("")
    lines.append("- This automated pass only reads SVG frame titles; it does not understand full request context.")
    lines.append("- A single capture does not prove the issue is constant over time.")
    lines.append("- If `--subprocesses` was not used, worker child processes may be missing.")
    lines.append("- If `--native` was not used, native extension details may be hidden.")
    lines.append("- Percentages are sample percentages, not direct wall-clock latency per request.")
    lines.append("")

    lines.append("## 6. Recommended Next Steps")
    lines.append("")
    if selected:
        lines.append(f"1. Open the SVG and inspect callers/callees around `{selected[0].name}`.")
        lines.append("2. Compare this report with application logs or request-level timing.")
        lines.append("3. Re-run with `--duration 60` if the capture is noisy or the top frame is below 10%.")
        lines.append("4. Re-run with `--subprocesses` for gunicorn, celery, uvicorn workers, or multiprocessing.")
    else:
        lines.append("1. Confirm the input is an SVG generated by `py-spy record`.")
        lines.append("2. Try generating a fresh SVG: `py-spy record -o profile.svg --duration 30 --pid <PID>`.")
    lines.append("")

    lines.append("## 7. Safe Follow-up Commands")
    lines.append("")
    lines.append("```bash")
    lines.append("py-spy record -o profile-60s.svg --duration 60 --pid <PID>")
    lines.append("py-spy record --subprocesses -o profile-workers.svg --duration 60 --pid <PID>")
    lines.append("py-spy record --format speedscope -o profile.speedscope.json --duration 60 --pid <PID>")
    lines.append("py-spy dump --pid <PID> > py-spy-dump.txt")
    lines.append("```")
    lines.append("")
    lines.append(
        "Do not add `sudo`, change `ptrace_scope`, add Docker/Kubernetes capabilities, "
        "or use `--locals` unless the user explicitly confirms the risk."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Analyze a py-spy SVG flamegraph and emit Markdown.")
    parser.add_argument("input", type=Path, help="Input SVG flamegraph generated by py-spy record")
    parser.add_argument("-o", "--output", type=Path, help="Output Markdown report path")
    parser.add_argument("--top", type=int, default=10, help="Number of hotspots to include, default: 10")
    args = parser.parse_args(argv)

    if args.top <= 0:
        parser.error("--top must be positive")
    if not args.input.exists():
        parser.error(f"input does not exist: {args.input}")

    frames = parse_svg_titles(args.input)
    report = render_report(args.input, frames, args.top)

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote analysis: {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
