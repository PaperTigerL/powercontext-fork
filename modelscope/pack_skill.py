#!/usr/bin/env python3
"""Package the Skill directory into a zip that the ModelScope Skills Center accepts.

The platform rule this script enforces:

* the archive root contains exactly one ``SKILL.md``;
* ``SKILL.md`` carries ``name`` and ``description`` in its YAML frontmatter
  (``version`` is required when publishing through the ``ms`` CLI);
* ``name`` matches the directory name and uses lowercase letters, digits and
  hyphens only;
* the archive is at most 5 MB.

Usage::

    python pack_skill.py
    python pack_skill.py --skill-dir financial-evidence-page-finder --out dist/
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

__all__ = ["main"]

MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def parse_frontmatter(text: str) -> dict:
    """Read the YAML frontmatter of a Markdown file without a YAML dependency."""

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return {}

    data: dict[str, str] = {}
    key: str | None = None
    buffer: list[str] = []
    for line in lines[1:end]:
        if line[:1] in (" ", "\t"):
            if key is not None:
                buffer.append(line.strip())
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        if key is not None:
            data[key] = " ".join(part for part in buffer if part).strip()
            key = None
            buffer = []
        name, value = match.group(1), match.group(2).strip()
        if value in (">-", ">", "|", "|-"):
            key = name
            buffer = []
        else:
            data[name] = value
    if key is not None:
        data[key] = " ".join(part for part in buffer if part).strip()
    return data


def check_skill(skill_dir: Path) -> list[str]:
    """Return the list of problems that would make the platform reject the package."""

    problems: list[str] = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [f"{skill_dir / 'SKILL.md'} 不存在"]

    found = list(skill_dir.rglob("SKILL.md"))
    if len(found) > 1:
        problems.append(f"归档中出现了 {len(found)} 个 SKILL.md，必须只有 1 个：{[str(p) for p in found]}")
    for extra in found:
        if extra.parent != skill_dir:
            problems.append(f"SKILL.md 必须位于归档根目录，当前在 {extra}")

    meta = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
    if not meta:
        problems.append("SKILL.md 缺少 YAML frontmatter")
        return problems
    for field in ("name", "description"):
        if not meta.get(field):
            problems.append(f"SKILL.md frontmatter 缺少 {field}")
    if "version" not in meta:
        problems.append("SKILL.md frontmatter 缺少 version（使用 ms CLI 发布时必填）")

    name = meta.get("name", "")
    if name and not SKILL_NAME_RE.match(name):
        problems.append(f"name 只能使用小写字母、数字和连字符：{name}")
    if len(name) > MAX_NAME_LENGTH:
        problems.append(f"name 超过 {MAX_NAME_LENGTH} 字符")
    if name and name != skill_dir.name:
        problems.append(f"name ({name}) 与目录名 ({skill_dir.name}) 不一致")
    description = meta.get("description", "")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        problems.append(f"description 超过 {MAX_DESCRIPTION_LENGTH} 字符（当前 {len(description)}）")
    return problems


def collect_files(skill_dir: Path) -> list[Path]:
    """All files that belong in the archive, in a stable order."""

    files: list[Path] = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(skill_dir).parts):
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


def build(skill_dir: Path, out: Path) -> int:
    """Write the archive and return its size in bytes."""

    files = collect_files(skill_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(skill_dir).as_posix())
    return out.stat().st_size


def main(argv: list[str] | None = None) -> int:
    default_dir = Path(__file__).resolve().parent / "financial-evidence-page-finder"
    parser = argparse.ArgumentParser(
        prog="pack_skill.py",
        description="把 Skill 目录打包成符合魔搭社区要求的 zip，并校验前置元数据。",
    )
    parser.add_argument("--skill-dir", default=str(default_dir), help="Skill 目录，默认取同级 financial-evidence-page-finder")
    parser.add_argument("--out", default="", help="输出目录，默认写到当前目录；以 .zip 结尾时视为归档文件路径")
    parser.add_argument("--check-only", action="store_true", help="只校验，不打包")
    args = parser.parse_args(argv)

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        print(f"error: Skill 目录不存在: {skill_dir}", file=sys.stderr)
        return 2

    problems = check_skill(skill_dir)
    if problems:
        print("打包前置校验未通过：", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"前置校验通过: {skill_dir.name}")

    if args.check_only:
        return 0

    out = Path(args.out) if args.out else Path.cwd()
    # '--out' names a directory; the archive is written inside it as
    # '<skill_name>.zip'.  A path ending in .zip is treated as the archive itself.
    if out.suffix.lower() == ".zip":
        archive_path = out
    else:
        archive_path = out / f"{skill_dir.name}.zip"
    try:
        size = build(skill_dir, archive_path)
    except OSError as exc:
        print(f"error: 无法写入 {archive_path}: {exc}", file=sys.stderr)
        return 2
    if size > MAX_ARCHIVE_BYTES:
        print(f"error: 归档 {size} 字节，超过平台上限 {MAX_ARCHIVE_BYTES} 字节", file=sys.stderr)
        return 1
    print(f"已生成 {archive_path}（{size} 字节，{len(collect_files(skill_dir))} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
