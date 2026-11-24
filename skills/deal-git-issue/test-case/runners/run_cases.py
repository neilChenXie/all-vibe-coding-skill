# -*- coding: utf-8 -*-
"""用例校验器：样本在库外，断言在库内。

用法（在项目根执行）：
  python test-case/runners/run_cases.py                    # 校验全部用例
  python test-case/runners/run_cases.py --case <id>        # 只校验一个
  python test-case/runners/run_cases.py --run              # 先执行 case 里的 run 命令再校验
  python test-case/runners/run_cases.py --data-root <路径> # 临时指定样本根
  python test-case/runners/run_cases.py --strict           # 连 output.sha256 以外的字段也严格比（默认已全比）

退出码：0 = 全部通过或跳过；1 = 有失败项。
样本缺失、产物缺失、断言未生成，一律记为 SKIP，不算失败——这样没挂样本的机器和 CI 也能跑。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import case_lib as L  # noqa: E402

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def check_case(case: dict, root: Path, do_run: bool) -> tuple[str, list[str]]:
    cid = case.get("id", "<未命名>")
    notes: list[str] = []

    inp = case.get("input")
    if inp:
        src = (root / inp).resolve()
        if not src.exists():
            return SKIP, [f"样本未挂载：{src}"]
        if case.get("sha256") and L.sha256_file(src) != case["sha256"]:
            return FAIL, ["样本指纹变了（sha256 与 manifest 不一致，断言可能已失效）"]
        if case.get("bytes") and src.stat().st_size != case["bytes"]:
            return FAIL, [f"样本大小变了：{src.stat().st_size} ≠ {case['bytes']}"]

    run = case.get("run")
    if do_run and run:
        proc = subprocess.run(run, shell=True, cwd=str(L.PROJECT_ROOT),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-5:]
            return FAIL, [f"run 命令退出码 {proc.returncode}"] + tail

    out = case.get("output")
    if not out:
        return SKIP, ["manifest 里没有 output，无法比对"]
    target = (root / out).resolve()
    if not target.exists():
        return SKIP, [f"产物未生成：{target}"]

    exp = L.load_assert(case)
    if exp is None:
        return SKIP, [f"断言快照未生成（跑 make_assert.py --case {cid}）"]

    actual = L.snapshot(target)
    diffs = L.diff(exp.get("output", {}), actual)
    if diffs:
        return FAIL, diffs
    notes.append(f"{actual['type']} / {actual.get('files', 1)} 个文件 / sha256 {actual['sha256'][:12]}…")
    return PASS, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 test-case 用例")
    ap.add_argument("--case", help="只跑指定 id")
    ap.add_argument("--data-root", help="样本根，覆盖环境变量与 config.local.json")
    ap.add_argument("--manifest", help="manifest.json 路径")
    ap.add_argument("--run", action="store_true", help="先执行 case.run 再校验")
    ap.add_argument("--strict", action="store_true", help="保留参数，当前默认即全字段比对")
    args = ap.parse_args()

    manifest = L.load_manifest(args.manifest)
    root = L.resolve_data_root(args.data_root)
    cases = manifest.get("cases") or []
    if args.case:
        cases = [c for c in cases if c.get("id") == args.case]
        if not cases:
            raise SystemExit(f"manifest 里没有用例：{args.case}")

    print(f"项目  : {manifest.get('project', L.PROJECT_ROOT.name)}")
    print(f"数据根: {root}")
    print(f"用例数: {len(cases)}" + ("（含 --run）" if args.run else ""))
    print("-" * 70)

    stats = {PASS: 0, FAIL: 0, SKIP: 0}
    for case in cases:
        status, notes = check_case(case, root, args.run)
        stats[status] += 1
        print(f"[{status}] {case.get('id')}  {case.get('title', '')}")
        for note in notes:
            print(f"       · {note}")

    print("-" * 70)
    print(f"PASS {stats[PASS]} | FAIL {stats[FAIL]} | SKIP {stats[SKIP]}")
    if stats[FAIL]:
        print("提示：失败不一定是代码退步——先确认样本没被替换、基线是否需要刷新。")
    return 1 if stats[FAIL] else 0


if __name__ == "__main__":
    raise SystemExit(main())
