#!/usr/bin/env python3
"""Check src/data/courses.json against the course and module directories.

The course catalogue (/learning/courses, plugins/course-catalogue) lists only
the courses in src/data/courses.json. When an upstream sync adds a course,
it would silently be missing from the catalogue; when one is removed, its
entry would point nowhere. This fails CI in both cases, and on unknown groups
or levels, so the hand-maintained file stays in step with docs/.

Usage: python3 scripts/check-course-catalogue.py [--docs docs]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVELS = {"beginner", "intermediate", "advanced"}


def subdirs(path: Path) -> set:
    return {d.name for d in path.iterdir() if d.is_dir()} if path.is_dir() else set()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--docs", default=str(ROOT / "docs"))
    ap.add_argument("--data", default=str(ROOT / "src" / "data" / "courses.json"))
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    learning = Path(args.docs) / "learning"
    errors = []

    for kind in ("courses", "modules"):
        on_disk = subdirs(learning / kind)
        slugs = [e["slug"] for e in data.get(kind, [])]
        for slug in sorted({s for s in slugs if slugs.count(s) > 1}):
            errors.append(f"{kind}: '{slug}' is listed more than once")
        for slug in sorted(on_disk - set(slugs)):
            errors.append(f"{kind}: docs/learning/{kind}/{slug}/ has no entry in courses.json — add one (group, hours from IBM's catalogue, level)")
        for slug in sorted(set(slugs) - on_disk):
            errors.append(f"{kind}: '{slug}' is in courses.json but docs/learning/{kind}/{slug}/ does not exist")

    groups = set(data.get("groups", []))
    for c in data.get("courses", []):
        if c.get("group") not in groups:
            errors.append(f"courses: '{c['slug']}' has unknown group {c.get('group')!r} (groups: {sorted(groups)})")
        if c.get("level") is not None and c["level"] not in LEVELS:
            errors.append(f"courses: '{c['slug']}' has unknown level {c['level']!r} (levels: {sorted(LEVELS)})")
        hours = c.get("hours")
        if hours is not None and not (isinstance(hours, (int, float)) and hours > 0):
            errors.append(f"courses: '{c['slug']}' has invalid hours {hours!r} (a number, or null when unsourced)")
    course_slugs = {c["slug"] for c in data.get("courses", [])}
    for b in data.get("beginnerChoices", []):
        if b.get("slug") not in course_slugs:
            errors.append(f"beginnerChoices: '{b.get('slug')}' is not a listed course")

    if errors:
        print("Course catalogue check FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"Course catalogue OK: {len(data['courses'])} courses, {len(data.get('modules', []))} modules match docs/learning/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
