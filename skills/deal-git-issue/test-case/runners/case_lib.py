# -*- coding: utf-8 -*-
"""test-case 骨架的公共库：数据根解析、指纹计算、通用快照。

只依赖标准库——任何语言的项目都能直接跑，不需要装 PyYAML 之类的东西。
由 setup-test-case 生成，一般不需要手改。
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent.parent      # 项目内的 <project>/test-case/
PROJECT_ROOT = CASE_DIR.parent                          # 项目根
DATA_ENV = "TESTCASE_DATA"                              # 环境变量名
SNAPSHOT_FILE_CAP = 2000                                # 目录快照最多统计多少个文件


# ---------------------------------------------------------------- 指纹

def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _text_metrics(data: bytes) -> dict | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text:
        return {"lines": 0, "chars": 0}
    lines = text.count("\n") + (0 if text.endswith("\n") else 1)
    return {"lines": lines, "chars": len(text)}


def snapshot(path) -> dict:
    """把文件或目录压成可比的指纹，不保留正文内容。"""
    p = Path(path)
    if p.is_file():
        data = p.read_bytes()
        snap = {"type": "file", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        text = _text_metrics(data)
        if text:
            snap.update(text)
        return snap

    if p.is_dir():
        files = sorted(x for x in p.rglob("*") if x.is_file())
        truncated = len(files) > SNAPSHOT_FILE_CAP
        files = files[:SNAPSHOT_FILE_CAP]
        entries, total = [], 0
        for f in files:
            size = f.stat().st_size
            total += size
            entries.append({"path": f.relative_to(p).as_posix(),
                            "bytes": size,
                            "sha256": sha256_file(f)})
        joined = "\n".join(f"{e['path']}:{e['sha256']}" for e in entries)
        snap = {"type": "dir", "files": len(entries), "bytes": total,
                "sha256": hashlib.sha256(joined.encode("utf-8")).hexdigest()}
        if truncated:
            snap["truncated"] = True
        return snap

    return {"type": "missing"}


# ---------------------------------------------------------------- 数据根

def resolve_data_root(cli: str | None = None) -> Path:
    """优先级：命令行 > 环境变量 > config.local.json > test-case/.data"""
    if cli:
        return Path(cli).expanduser().resolve()
    env = os.environ.get(DATA_ENV)
    if env:
        return Path(env).expanduser().resolve()
    local = CASE_DIR / "config.local.json"
    if local.exists():
        cfg = json.loads(local.read_text(encoding="utf-8"))
        if cfg.get("data_root"):
            return Path(cfg["data_root"]).expanduser().resolve()
    return (CASE_DIR / ".data").resolve()


# ---------------------------------------------------------------- 读写

def load_manifest(path=None) -> dict:
    p = Path(path) if path else CASE_DIR / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_assert(case: dict) -> dict | None:
    rel = case.get("assert")
    if not rel:
        return None
    p = CASE_DIR / rel
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def dump_json(obj, path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 比对

def diff(expect, actual, prefix: str = "output") -> list[str]:
    """逐字段比对两个快照，返回人类可读的差异列表。"""
    out: list[str] = []

    def walk(a, b, path: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for k in a:
                if k not in b:
                    out.append(f"{path}.{k} 缺失")
                else:
                    walk(a[k], b[k], f"{path}.{k}")
        elif a != b:
            out.append(f"{path}: 期望 {a!r} / 实际 {b!r}")

    walk(expect, actual, prefix)
    return out
