# -*- coding: utf-8 -*-
"""tc-subdir-testcase 探针：在多 skill 仓库沙箱里验证 issue_kit.py 的用例库定位行为。

沙箱 = 临时目录 + `git init`，只有子目录里有用例库，仓库根没有 test-case/：
  s1 context 不带 --project          → exists=False，列出 candidates=skills/demo，不劝建骨架
  s2 map-upsert 不带 --project       → rc=2，且不会凭空建出 <repo>/test-case
  s3 map-check 不带 --project        → rc=2
  s4 context --project skills/demo   → exists=True，用例数 1，清单被识别
  s5 map-upsert --project skills/demo→ rc=0，映射写进 skills/demo/test-case/
  s6 map-check --project skills/demo → rc=0（case_ids 真对上、数据目录存在）
  s7 map-upsert --project 无清单层   → rc=0（把记录写进那个空用例库）
  s8 map-check 同一层                → rc=1 + [WARN]（清单缺失不再假绿）

输出写到 <数据根>/tc-subdir-testcase/output.txt，只有布尔值与相对路径，跨机器稳定。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CASE_ID = "tc-subdir-testcase"
DATA_ENV = "TESTCASE_DATA"

HERE = Path(__file__).resolve()
CASE_ROOT = HERE.parents[2]          # <skill>/test-case
PROJECT_ROOT = HERE.parents[3]       # <skill>
KIT = PROJECT_ROOT / "scripts" / "issue_kit.py"


def data_root() -> Path:
    env = os.environ.get(DATA_ENV)
    if env:
        return Path(env).expanduser().resolve()
    cfg = CASE_ROOT / "config.local.json"
    if cfg.is_file():
        value = json.loads(cfg.read_text(encoding="utf-8")).get("data_root")
        if value:
            return Path(value).expanduser().resolve()
    return (CASE_ROOT / ".data").resolve()


def build_sandbox(base: Path) -> Path:
    repo = base / "repo"
    demo = repo / "skills" / "demo" / "test-case"
    (demo / "runners").mkdir(parents=True)
    (demo / "manifest.yaml").write_text(
        "version: 1\ncases:\n  - id: tc-a1\n    title: demo\n", encoding="utf-8")
    (demo / "config.local.yaml").write_text(
        f"data_root: {(base / 'data').as_posix()}\n", encoding="utf-8")
    (base / "data" / "tc-a1").mkdir(parents=True)
    other = repo / "skills" / "other" / "test-case"
    other.mkdir(parents=True)
    (other / "README.md").write_text("no manifest here\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", "."], cwd=str(repo), check=True,
                   capture_output=True)
    return repo


def run(repo: Path, *args: str) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, str(KIT), *args], cwd=str(repo),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def as_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="issue-kit-probe-"))
    try:
        repo = build_sandbox(base)
        lines: list[str] = []

        rc, out, _err = run(repo, "context")
        tc = as_json(out).get("test_case") or {}
        cands = tc.get("candidates") or []
        first = cands[0] if cands else {}
        warn = " ".join(tc.get("warnings") or [])
        lines.append(
            f"[s1] context 无 --project        rc={rc} exists={tc.get('exists')} "
            f"candidates={len(cands)} project={first.get('project', '-')} "
            f"case_count={first.get('case_count', '-')} 劝建骨架={'setup-test-case' in warn}")

        rc, _out, err = run(repo, "map-upsert", "--issue", "7",
                            "--case-id", "tc-a1", "--data-dir", "tc-a1")
        lines.append(
            f"[s2] map-upsert 无 --project     rc={rc} "
            f"建了根目录={(repo / 'test-case').exists()} 提示候选={'--project' in err}")

        rc, _out, _err = run(repo, "map-check")
        lines.append(f"[s3] map-check 无 --project      rc={rc}")

        rc, out, _err = run(repo, "--project", "skills/demo", "context")
        tc = as_json(out).get("test_case") or {}
        manifest = (tc.get("manifest") or "-").replace("\\", "/").split("/")[-1]
        lines.append(
            f"[s4] context --project demo      rc={rc} exists={tc.get('exists')} "
            f"case_count={tc.get('case_count')} manifest={manifest}")

        rc, _out, _err = run(repo, "--project", "skills/demo", "map-upsert", "--issue", "7",
                             "--case-id", "tc-a1", "--data-dir", "tc-a1")
        written = (repo / "skills" / "demo" / "test-case" / "issues.yaml").is_file()
        lines.append(f"[s5] map-upsert --project demo   rc={rc} 映射落位={written}")

        rc, _out, _err = run(repo, "--project", "skills/demo", "map-check")
        lines.append(f"[s6] map-check --project demo    rc={rc}")

        rc, _out, _err = run(repo, "--project", "skills/other", "map-upsert", "--issue", "8",
                             "--case-id", "tc-x9", "--data-dir", "tc-x9")
        lines.append(f"[s7] map-upsert --project other  rc={rc}")

        rc, out, _err = run(repo, "--project", "skills/other", "map-check")
        lines.append(f"[s8] map-check --project other   rc={rc} 有 WARN={'[WARN]' in out}")

        empty = base / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "--quiet", "."], cwd=str(empty), check=True,
                       capture_output=True)
        rc, out, _err = run(empty, "context")
        tc = as_json(out).get("test_case") or {}
        warn = " ".join(tc.get("warnings") or [])
        lines.append(
            f"[s9] context 空仓库              rc={rc} exists={tc.get('exists')} "
            f"candidates={len(tc.get('candidates') or [])} 劝建骨架={'setup-test-case' in warn}")

        text = "\n".join(lines) + "\n"
        target = data_root() / CASE_ID / "output.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(text, end="")
        print(f"→ {target}")
        return 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
