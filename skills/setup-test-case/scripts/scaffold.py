# -*- coding: utf-8 -*-
"""生成 test-case 骨架：项目内骨架 + 库外样本目录。

用法：
  python scripts/scaffold.py \
      --project D:/code/my-app \
      --slug my-app \
      --name "My App" \
      --data-root D:/test-case-data/github.com/me/my-app \
      [--force] [--dry-run]

做的事：
  1. 在 <project>/test-case/ 下生成 manifest.json、runners/、expected/、fixtures/、.gitignore、README.md
  2. 在 <data-root>/ 下生成样本库 README.md
  3. 把 data_root 的绝对路径写进 config.local.json（该文件不入仓）

两侧的 README.md 都描述「框架逻辑」：怎么归档、怎么执行。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

REF_DIR = Path(__file__).resolve().parent.parent / "references"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# 模板 -> 目标（相对 test-case/）
RENDER = {
    "project-readme.tmpl.md": "README.md",
    "manifest.tmpl.json": "manifest.json",
    "config.example.json": "config.example.json",
    "gitignore.tmpl": ".gitignore",
    "fixtures-readme.tmpl.md": "fixtures/README.md",
}
# 原样拷贝 -> 目标
COPY = {
    "case_lib.py": "runners/case_lib.py",
    "run_cases.py": "runners/run_cases.py",
    "make_assert.py": "runners/make_assert.py",
    "pre-commit": "runners/pre-commit",
}
JSON_FILES = {"manifest.json", "config.example.json"}


def render(text: str, ctx: dict) -> str:
    for key, value in ctx.items():
        text = text.replace("{{%s}}" % key, str(value))
    return text


def write(path: Path, content: str, dry: bool) -> None:
    if dry:
        print(f"  [dry] {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"  [new] {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 test-case 骨架")
    ap.add_argument("--project", required=True, help="项目根目录")
    ap.add_argument("--slug", required=True, help="项目标识，小写 kebab-case")
    ap.add_argument("--name", help="项目显示名，缺省用 slug")
    ap.add_argument("--data-root", required=True, help="本项目在样本库中的目录（绝对路径）")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    ap.add_argument("--dry-run", action="store_true", help="只打印将写哪些文件")
    ap.add_argument("--allow-inside", action="store_true", help="允许样本库放在项目目录内（不推荐）")
    args = ap.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在：{project}")
    if not SLUG_RE.match(args.slug):
        raise SystemExit(f"slug 只允许小写字母、数字、点、连字符：{args.slug}")

    case_dir = project / "test-case"
    data_root = Path(args.data_root).expanduser().resolve()

    if data_root == project or project in data_root.parents:
        if not args.allow_inside:
            raise SystemExit(
                f"样本库不能放在项目目录内：{data_root}\n"
                f"样本进 git 就失去意义了。换一个库外路径，或加 --allow-inside 强行继续。"
            )

    if case_dir.exists() and any(case_dir.iterdir()) and not args.force:
        existing = sorted(p.name for p in case_dir.iterdir())[:8]
        raise SystemExit(
            f"{case_dir} 已存在且非空（{', '.join(existing)}…）。\n"
            f"确认要覆盖请加 --force；只想补文件请手动处理。"
        )

    ctx = {
        "PROJECT_NAME": args.name or args.slug,
        "PROJECT_SLUG": args.slug,
        "PROJECT_ROOT": project.as_posix(),
        "DATA_ROOT": data_root.as_posix(),
        "CREATED_AT": datetime.date.today().isoformat(),
    }

    print(f"项目    : {project}")
    print(f"样本库  : {data_root}")
    print(f"骨架目录: {case_dir}")
    print("-" * 60)

    # 1) 项目内骨架
    for tmpl, rel in RENDER.items():
        src = REF_DIR / tmpl
        if not src.exists():
            raise SystemExit(f"模板缺失：{src}")
        text = render(src.read_text(encoding="utf-8"), ctx)
        if rel in JSON_FILES:
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"渲染后的 {rel} 不是合法 JSON：{exc}")
        write(case_dir / rel, text, args.dry_run)

    for name, rel in COPY.items():
        src = REF_DIR / name
        if not src.exists():
            raise SystemExit(f"模板缺失：{src}")
        target = case_dir / rel
        if args.dry_run:
            print(f"  [dry] {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        if name == "pre-commit":
            mode = target.stat().st_mode
            target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  [new] {target}")

    # 2) config.local.json —— 唯一写绝对路径的地方
    local_cfg = {"data_root": data_root.as_posix()}
    write(case_dir / "config.local.json",
          json.dumps(local_cfg, ensure_ascii=False, indent=2) + "\n", args.dry_run)

    # 3) 样本库目录 + README
    if not args.dry_run:
        data_root.mkdir(parents=True, exist_ok=True)
    storage_readme = render((REF_DIR / "storage-readme.tmpl.md").read_text(encoding="utf-8"), ctx)
    write(data_root / "README.md", storage_readme, args.dry_run)

    # 4) expected/ 先建空目录，便于编辑器识别
    if not args.dry_run:
        (case_dir / "expected").mkdir(parents=True, exist_ok=True)

    print("-" * 60)
    print("完成。接下来：")
    print(f"  1) 把样本放进 {data_root}/<用例id>/")
    print(f"  2) 在 {case_dir / 'manifest.json'} 的 cases 里登记")
    print(f"  3) python {(case_dir / 'runners' / 'run_cases.py').as_posix()}")
    print("两侧 README 已写明归档与执行规则，新增用例前先读一遍。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
