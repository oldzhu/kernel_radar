#!/usr/bin/env python3

import argparse
import dataclasses
import datetime as dt
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _read_text_url(url: str, timeout_seconds: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "kernel_radar/0.1 (+local)"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_rfc3339(ts: str) -> Optional[dt.datetime]:
    # Atom uses RFC3339. Examples:
    # 2025-01-03T10:22:33Z
    # 2025-01-03T10:22:33+00:00
    ts = ts.strip()
    if not ts:
        return None
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(ts)
    except ValueError:
        return None


@dataclasses.dataclass(frozen=True)
class FeedItem:
    area: str
    list_name: str
    title: str
    link: str
    author: str
    published: dt.datetime


def _atom_items(atom_xml: str) -> Iterable[Tuple[str, str, str, str]]:
    # Yields (title, link, author, updated/published)
    root = ET.fromstring(atom_xml)
    # Atom namespace handling
    ns = {}
    if root.tag.startswith("{") and "}" in root.tag:
        ns_uri = root.tag.split("}", 1)[0][1:]
        ns = {"a": ns_uri}
        entry_path = "a:entry"
        title_path = "a:title"
        link_path = "a:link"
        author_path = "a:author/a:name"
        updated_path = "a:updated"
        published_path = "a:published"
    else:
        entry_path = "entry"
        title_path = "title"
        link_path = "link"
        author_path = "author/name"
        updated_path = "updated"
        published_path = "published"

    for entry in root.findall(entry_path, ns):
        title = (entry.findtext(title_path, default="", namespaces=ns) or "").strip()
        author = (entry.findtext(author_path, default="", namespaces=ns) or "").strip()

        link = ""
        for ln in entry.findall(link_path, ns):
            href = ln.attrib.get("href", "")
            rel = ln.attrib.get("rel", "")
            if rel in ("alternate", "") and href:
                link = href
                break
        if not link:
            # fallback: sometimes single link exists
            ln = entry.find(link_path, ns)
            if ln is not None:
                link = ln.attrib.get("href", "")

        ts = (
            entry.findtext(published_path, default="", namespaces=ns)
            or entry.findtext(updated_path, default="", namespaces=ns)
            or ""
        )
        yield title, link, author, ts


def _load_yaml_minimal(path: Path) -> Dict:
    # Minimal YAML loader to avoid external deps.
    # Supports only the subset used by config.example.yaml.
    # If you want full YAML, install pyyaml and replace this.
    try:
        import yaml  # type: ignore

        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ModuleNotFoundError:
        pass

    # Fallback: accept JSON only.
    if path.suffix.lower() in (".json",):
        return json.loads(path.read_text(encoding="utf-8"))

    raise SystemExit(
        "PyYAML is not installed. Install it with: pip install pyyaml\n"
        "Or use a JSON config instead of YAML."
    )


def _compile_any(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p, flags=re.IGNORECASE) for p in patterns]


def _matches_any(text: str, patterns: List[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _load_state(path: Path) -> Dict:
    if not path.exists():
        return {"seen_links": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"seen_links": []}


def _save_state(path: Path, state: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _render_markdown(now: dt.datetime, since_hours: int, items_by_area: Dict[str, List[FeedItem]]) -> str:
    lines: List[str] = []
    lines.append(f"# Kernel radar digest")
    lines.append("")
    lines.append(f"Generated: {now.isoformat()}")
    lines.append(f"Window: last {since_hours}h")
    lines.append("")

    total = sum(len(v) for v in items_by_area.values())
    lines.append(f"Total items: {total}")
    lines.append("")

    for area, items in items_by_area.items():
        if not items:
            continue
        lines.append(f"## {area} ({len(items)})")
        lines.append("")
        for it in sorted(items, key=lambda x: x.published, reverse=True):
            when = it.published.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
            title = it.title.replace("\n", " ").strip()
            lines.append(f"- {when} [{it.list_name}] {title}")
            lines.append(f"  - {it.link}")
            if it.author:
                lines.append(f"  - {it.author}")
        lines.append("")

    return "\n".join(lines)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to config.yaml")
    ap.add_argument("--since-hours", type=int, default=24)
    ap.add_argument("--out", default="-", help="Output file (default stdout)")
    ap.add_argument("--include-seen", action="store_true", help="Do not dedupe using state")
    args = ap.parse_args(argv)

    config_path = Path(args.config)
    cfg = _load_yaml_minimal(config_path)

    state_file = Path(cfg.get("state_file", "kernel_radar/state.json"))
    state = _load_state(state_file)
    seen_links = set(state.get("seen_links", []))

    include_re = _compile_any(cfg.get("filters", {}).get("include_subject_regex", []))
    exclude_re = _compile_any(cfg.get("filters", {}).get("exclude_subject_regex", []))

    now = _utcnow()
    since = now - dt.timedelta(hours=args.since_hours)

    items_by_area: Dict[str, List[FeedItem]] = {k: [] for k in (cfg.get("areas") or {}).keys()}

    for area_name, area_cfg in (cfg.get("areas") or {}).items():
        keywords = [k.lower() for k in (area_cfg.get("keywords") or [])]
        lists = area_cfg.get("lists") or []

        for lst in lists:
            list_name = lst.get("name") or "unknown"
            atom_url = lst.get("atom")
            if not atom_url:
                continue

            try:
                xml_text = _read_text_url(atom_url)
            except Exception as e:
                print(f"WARN: failed to fetch {atom_url}: {e}", file=sys.stderr)
                continue

            for title, link, author, ts in _atom_items(xml_text):
                if not link or not title:
                    continue

                published = _parse_rfc3339(ts) or now
                if published.tzinfo is None:
                    published = published.replace(tzinfo=dt.timezone.utc)

                if published < since:
                    continue

                subj = title
                subj_l = subj.lower()

                # subject filters
                if include_re and not _matches_any(subj, include_re):
                    continue
                if exclude_re and _matches_any(subj, exclude_re):
                    continue

                # area keyword match
                if keywords and not any(k in subj_l for k in keywords):
                    continue

                if not args.include_seen and link in seen_links:
                    continue

                items_by_area.setdefault(area_name, []).append(
                    FeedItem(
                        area=area_name,
                        list_name=list_name,
                        title=subj,
                        link=link,
                        author=author,
                        published=published,
                    )
                )

    # apply limits
    limits = cfg.get("limits", {}) or {}
    max_per_area = int(limits.get("max_items_per_area", 40))
    max_total = int(limits.get("max_total_items", 200))

    trimmed: Dict[str, List[FeedItem]] = {}
    all_items: List[FeedItem] = []
    for area, items in items_by_area.items():
        items_sorted = sorted(items, key=lambda x: x.published, reverse=True)
        items_sorted = items_sorted[:max_per_area]
        trimmed[area] = items_sorted
        all_items.extend(items_sorted)

    # enforce global cap
    all_items = sorted(all_items, key=lambda x: x.published, reverse=True)[:max_total]
    keep_links = {it.link for it in all_items}
    for area in list(trimmed.keys()):
        trimmed[area] = [it for it in trimmed[area] if it.link in keep_links]

    out_text = _render_markdown(now=now, since_hours=args.since_hours, items_by_area=trimmed)

    if args.out == "-":
        print(out_text)
    else:
        Path(args.out).write_text(out_text, encoding="utf-8")

    # update state
    if not args.include_seen:
        new_seen = set(seen_links)
        for area_items in trimmed.values():
            for it in area_items:
                new_seen.add(it.link)
        state["seen_links"] = sorted(new_seen)
        _save_state(state_file, state)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
