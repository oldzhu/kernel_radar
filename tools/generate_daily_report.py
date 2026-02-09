#!/usr/bin/env python3
"""Generate a bilingual daily report for latest commits by area."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DEFAULT_AREAS = [
    ("Scheduler", ["kernel/sched"]),
    ("Cgroup", ["kernel/cgroup", "include/linux/cgroup"]),
    ("Namespace", ["kernel/ns", "kernel/nsproxy.c", "include/linux/ns"]),
    ("GPU (DRM)", ["drivers/gpu/drm"]),
    ("AMD GPU (DRM)", ["drivers/gpu/drm/amd"]),
    ("NVIDIA GPU (DRM nouveau)", ["drivers/gpu/drm/nouveau"]),
]

ZH_AREA = {
    "Scheduler": "调度器",
    "Cgroup": "Cgroup",
    "Namespace": "命名空间",
    "GPU (DRM)": "GPU（DRM）",
    "AMD GPU (DRM)": "AMD GPU（DRM）",
    "NVIDIA GPU (DRM nouveau)": "NVIDIA GPU（DRM nouveau）",
}


def run_git(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, encoding="utf-8", errors="replace")


def get_branch(repo: Path, branch: str | None) -> str:
    if branch:
        return branch
    return run_git(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"]).strip()


def git_log(repo: Path, branch: str, paths: list[str], count: int, no_merges: bool) -> list[dict[str, str]]:
    cmd = [
        "git",
        "-C",
        str(repo),
        "log",
        branch,
        f"-n{count}",
        "--date=short",
        "--pretty=format:%h%x1f%ad%x1f%an%x1f%s",
    ]
    if no_merges:
        cmd.append("--no-merges")
    cmd += ["--"] + paths
    out = run_git(cmd)
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        short, date, author, subject = parts
        rows.append({
            "short": short,
            "date": date,
            "author": author,
            "subject": subject,
        })
    return rows


def render_en(date: str, branch: str, no_merges: bool, count: int, repo: Path) -> str:
    lines: list[str] = []
    lines.append(f"# {date} Daily Report (Latest {count} commits by area)")
    lines.append("")
    lines.append(f"[简体中文]({date}-daily-report.zh-CN.md)")
    lines.append("")
    merges = "no merges" if no_merges else "including merges"
    lines.append(f"Scope: upstream Linux ({branch}), path-based area filters, {merges}.")
    lines.append("")
    for area, paths in DEFAULT_AREAS:
        lines.append(f"## {area}")
        commits = git_log(repo, branch, paths, count, no_merges)
        if not commits:
            lines.append("")
            lines.append("- No commits found in the last range for this area.")
            lines.append("")
            continue
        lines.append("")
        for c in commits:
            lines.append(f"- {c['short']} {c['subject']} (by {c['author']}, {c['date']})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_zh(date: str, branch: str, no_merges: bool, count: int, repo: Path) -> str:
    lines: list[str] = []
    lines.append(f"# {date} 每日报告（各领域最新 {count} 条提交）")
    lines.append("")
    lines.append(f"[English]({date}-daily-report.md)")
    lines.append("")
    merges = "不含 merge" if no_merges else "包含 merge"
    lines.append(f"范围：上游 Linux（{branch}），基于路径的领域过滤，{merges}。")
    lines.append("")
    for area, paths in DEFAULT_AREAS:
        lines.append(f"## {ZH_AREA.get(area, area)}")
        commits = git_log(repo, branch, paths, count, no_merges)
        if not commits:
            lines.append("")
            lines.append("- 该领域在该范围内未找到提交。")
            lines.append("")
            continue
        lines.append("")
        for c in commits:
            lines.append(f"- {c['short']} {c['subject']}（{c['author']}，{c['date']}）")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bilingual daily report for latest commits by area.")
    parser.add_argument("--repo", default="/home/oldzhu/mylinux/linux", help="Path to upstream Linux repo")
    parser.add_argument("--output-dir", default="/home/oldzhu/mylinux/kernel_radar/docs", help="Output docs directory")
    parser.add_argument("--date", required=True, help="Report date, e.g. 2026-02-09")
    parser.add_argument("--branch", default=None, help="Git branch to scan (default: current)")
    parser.add_argument("--count", type=int, default=5, help="Number of commits per area")
    parser.add_argument("--no-merges", action="store_true", help="Exclude merge commits")
    args = parser.parse_args()

    repo = Path(args.repo)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    branch = get_branch(repo, args.branch)

    en_path = out_dir / f"{args.date}-daily-report.md"
    zh_path = out_dir / f"{args.date}-daily-report.zh-CN.md"

    en_path.write_text(render_en(args.date, branch, args.no_merges, args.count, repo), encoding="utf-8")
    zh_path.write_text(render_zh(args.date, branch, args.no_merges, args.count, repo), encoding="utf-8")

    print(f"Wrote: {en_path}")
    print(f"Wrote: {zh_path}")


if __name__ == "__main__":
    main()
