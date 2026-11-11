# -*- coding: utf-8 -*-
"""生成 / 刷新断言基线：把当前产物压成指纹写进 expected/<id>.assert.json。

用法（在项目根执行）：
  python test-case/runners/make_assert.py --case <id>
  python test-case/runners/make_assert.py --all
  python test-case/runners/make_assert.py --case <id> --data-root <路径>

基线只存计数与哈希，不含正文，可安全入仓。
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import case_lib as L  # noqa: E402


def build(case: dict, root: Path) -> dict:
    cid = case["id"]
    out = case.get("output")
    if not out:
        raise SystemExit(f"{cid}: manifest 里没有 output")
    target = (root / out).resolve()
    if not target.exists():
        raise SystemExit(f"{cid}: 产物不存在 {target}")

    src = (root / case["input"]).resolve() if case.get("input") else None
    return {
        "id": cid,
        "title": case.get("title", ""),
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": "test-case/runners/make_assert.py",
        "input": {
            "path": case.get("input"),
            "sha256": L.sha256_file(src) if src and src.is_file() else None,
            "bytes": src.stat().st_size if src and src.is_file() else None,
        },
        "output": L.snapshot(target),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 test-case 断言基线")
    ap.add_argument("--case", help="用例 id")
    ap.add_argument("--all", action="store_true", help="处理 manifest 里全部用例")
    ap.add_argument("--data-root", help="样本根，覆盖环境变量与 config.local.json")
    ap.add_argument("--manifest", help="manifest.json 路径")
    args = ap.parse_args()

    if not args.case and not args.all:
        raise SystemExit("请指定 --case <id> 或 --all")

    manifest = L.load_manifest(args.manifest)
    root = L.resolve_data_root(args.data_root)
    cases = manifest.get("cases") or []
    if args.case:
        cases = [c for c in cases if c.get("id") == args.case]
        if not cases:
            raise SystemExit(f"manifest 里没有用例：{args.case}")

    for case in cases:
        snap = build(case, root)
        rel = case.get("assert") or f"expected/{case['id']}.assert.json"
        L.dump_json(snap, L.CASE_DIR / rel)
        o = snap["output"]
        print(f"[OK] {case['id']} -> {rel}")
        print(f"     {o['type']} / {o.get('files', 1)} 个文件 / {o['bytes']} 字节 / sha256 {o['sha256'][:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
