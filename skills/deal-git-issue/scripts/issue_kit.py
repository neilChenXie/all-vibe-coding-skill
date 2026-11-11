# -*- coding: utf-8 -*-
"""deal-git-issue 辅助脚本：汇总 issue 上下文、维护 issue ↔ 测试用例映射。

子命令
  context     输出项目 / 远程 / 平台 / CLI / test-case 配置的 JSON 汇总
  map-list    打印 test-case/issues.yaml 全部记录
  map-get     查一条记录（不存在时退出码 1）
  map-upsert  新增或更新一条记录（只改传入的字段）
  map-check   校验映射引用的用例是否都在清单里、数据目录是否存在

只依赖标准库；装了 PyYAML 就用它解析，否则用内置最小解析器（只认本脚本写出的格式）。
退出码：0 正常；1 查询/校验失败；2 参数或环境错误。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DATA_ENV = "TESTCASE_DATA"
CONFIG_NAMES = ("config.local.yaml", "config.local.yml", "config.local.json",
                "config.yaml", "config.yml", "config.json")
MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "manifest.json")
MAP_NAME = "issues.yaml"
STATES = ("working", "done", "dropped")
PLATFORM_CLI = {"github": "gh", "gitlab": "glab"}
CLI_TOKEN_ENV = {"github": ("GITHUB_TOKEN", "GH_TOKEN"), "gitlab": ("GITLAB_TOKEN", "GLAB_TOKEN")}


# ------------------------------------------------------------------ 基础

def run(cmd: list[str], cwd: Path | None = None, timeout: int = 15) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)


def project_root() -> Path:
    code, out = run(["git", "rev-parse", "--show-toplevel"])
    if code == 0 and out.strip():
        return Path(out.strip().splitlines()[0]).resolve()
    return Path.cwd().resolve()


def git_remote(root: Path) -> str | None:
    code, out = run(["git", "remote", "get-url", "origin"], cwd=root)
    if code == 0 and out.strip():
        return out.strip().splitlines()[0]
    code, out = run(["git", "config", "--get", "remote.origin.url"], cwd=root)
    if code == 0 and out.strip():
        return out.strip().splitlines()[0]
    return None


def parse_remote(url: str | None) -> tuple[str | None, str | None, str]:
    """返回 (host, owner/repo, platform)。"""
    if not url:
        return None, None, "unknown"
    u = url.strip()
    if u.startswith("git@") or (":" in u and "://" not in u):
        m = re.match(r"^[^@]*@?([^:]+):(.+)$", u)
        host, path = (m.group(1), m.group(2)) if m else (None, u)
    else:
        m = re.match(r"^\w+://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", u)
        host, path = (m.group(1), m.group(2)) if m else (None, u)
    if path.endswith(".git"):
        path = path[:-4]
    slug = "/".join(path.strip("/").split("/")[-2:]) if path else None
    platform = "unknown"
    if host:
        h = host.lower()
        if "github" in h:
            platform = "github"
        elif "gitlab" in h:
            platform = "gitlab"
        elif "gitee" in h:
            platform = "gitee"
        elif "coding" in h:
            platform = "coding"
        else:
            platform = h
    return host, slug, platform


# ------------------------------------------------------------------ YAML

def _scalar(v: str):
    v = v.strip()
    if v and v[0] not in "\"'[" and " #" in v:
        v = v.split(" #", 1)[0].strip()
    if not v:
        return ""
    if v[0] in "\"'" and v[-1] == v[0] and len(v) > 1:
        try:
            return json.loads(v) if v[0] == '"' else v[1:-1]
        except json.JSONDecodeError:
            return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    low = v.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    try:
        return float(v)
    except ValueError:
        return v


def _mini_flat_yaml(text: str) -> dict:
    """最小 YAML 解析：只认顶层的 `key: value`，够 config.local.yaml 用。"""
    data: dict = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip()) != 0:
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        data[k.strip()] = _scalar(v)
    return data


def _case_ids_mini(text: str) -> list[str]:
    """从 YAML 文本里抠出 cases[].id——只在没有 PyYAML 时兜底。"""
    ids: list[str] = []
    case_indent = None
    item_indent = None
    item: dict | None = None

    def flush() -> None:
        nonlocal item
        if isinstance(item, dict):
            cid = item.get("id")
            if cid not in (None, ""):
                ids.append(str(cid))
        item = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()

        if case_indent is None:
            if re.fullmatch(r"cases:", body):
                case_indent = indent
            continue
        if indent <= case_indent:
            flush()
            break

        if body.startswith("- "):
            if item_indent is None:
                item_indent = indent
            if indent == item_indent:
                flush()
                item = {}
                rest = body[2:].strip()
                if ":" in rest:
                    k, v = rest.split(":", 1)
                    item[k.strip()] = _scalar(v)
            continue

        if item is not None and ":" in body and indent == (item_indent or 0) + 2:
            k, v = body.split(":", 1)
            item.setdefault(k.strip(), _scalar(v))
    flush()
    return ids


def _entries_mini(text: str, section: str) -> list[dict]:
    """抠出 `issues:` 下的记录列表——只在没有 PyYAML 时兜底。"""
    items: list[dict] = []
    sec_indent = None
    item_indent = None
    item: dict | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()

        if sec_indent is None:
            if re.fullmatch(rf"{re.escape(section)}:.*", body):
                sec_indent = indent
                if body.rstrip().endswith("[]"):
                    return []
            continue
        if indent <= sec_indent:
            break

        if body.startswith("- "):
            if item_indent is None:
                item_indent = indent
            if indent == item_indent:
                item = {}
                items.append(item)
                rest = body[2:].strip()
                if ":" in rest:
                    k, v = rest.split(":", 1)
                    item[k.strip()] = _scalar(v)
            continue

        if item is not None and ":" in body and indent == (item_indent or 0) + 2:
            k, v = body.split(":", 1)
            item.setdefault(k.strip(), _scalar(v))
    return items


def yaml_load_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _mini_flat_yaml(text)


def yaml_load_text(path: Path) -> dict:
    return yaml_load_file(path)


def case_ids_from_file(path: Path) -> list[str]:
    """尽量稳地取出用例 id 列表；没有 PyYAML 时走最小解析，只保证 id 正确。"""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        return [str(c.get("id")) for c in (data.get("cases") or [])
                if isinstance(c, dict) and c.get("id")]
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        return [str(c.get("id")) for c in (data.get("cases") or [])
                if isinstance(c, dict) and c.get("id")]
    except ImportError:
        return _case_ids_mini(text)


# ------------------------------------------------------------------ test-case 发现

def discover_test_case(root: Path) -> dict:
    info: dict = {"dir": str(root / "test-case"), "exists": (root / "test-case").is_dir(),
                  "warnings": []}
    tc = root / "test-case"
    if not tc.is_dir():
        info["warnings"].append("项目内没有 test-case/，应先运行 setup-test-case 建骨架")
        return info

    cfg_path, cfg = None, {}
    for name in CONFIG_NAMES:
        p = tc / name
        if p.is_file():
            try:
                cfg = yaml_load_text(p)
                cfg_path = p
                break
            except Exception as exc:  # noqa: BLE001
                info["warnings"].append(f"{name} 解析失败：{exc}")
    if cfg_path:
        info["config_file"] = str(cfg_path)
        info["config_tracked_hint"] = not cfg_path.name.startswith("config.local")
    else:
        info["warnings"].append("未找到 test-case/config.local.yaml（或 .json），样本根无法确定")

    data_root, source = None, None
    for key in ("data_root", "dataRoot", "root", "cases_root"):
        if isinstance(cfg, dict) and cfg.get(key):
            data_root, source = str(cfg[key]), f"config:{cfg_path.name}"
            break
    if not data_root and os.environ.get(DATA_ENV):
        data_root, source = os.environ[DATA_ENV], f"env:{DATA_ENV}"
    if not data_root:
        data_root, source = str(tc / ".data"), "default:test-case/.data"
    dr = Path(data_root).expanduser()
    info.update({"data_root": str(dr), "data_root_source": source,
                 "data_root_exists": dr.is_dir()})
    try:
        dr.resolve().relative_to(root.resolve())
        info["warnings"].append("数据根落在项目目录内，样本有可能进 git")
    except (ValueError, OSError):
        pass

    for name in MANIFEST_NAMES:
        p = tc / name
        if p.is_file():
            try:
                ids = case_ids_from_file(p)
                info.update({"manifest": str(p), "manifest_format": p.suffix.lstrip("."),
                             "case_count": len(ids), "case_ids": ids})
            except Exception as exc:  # noqa: BLE001
                info["warnings"].append(f"{name} 解析失败：{exc}")
            break
    else:
        info.setdefault("manifest", None)
        info["warnings"].append("未找到 manifest.yaml / manifest.json，用例清单缺失")

    runner = tc / "runners" / "run_cases.py"
    info["runner"] = str(runner) if runner.is_file() else None
    if not runner.is_file():
        info["warnings"].append("未找到 test-case/runners/run_cases.py，改完无法自动校验")
    return info


# ------------------------------------------------------------------ 映射文件

def map_path(root: Path) -> Path:
    return root / "test-case" / MAP_NAME


def load_map(root: Path) -> list[dict]:
    p = map_path(root)
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        entries = data.get("issues") if isinstance(data, dict) else None
    except ImportError:
        entries = _entries_mini(text, "issues")
    return [e for e in (entries or []) if isinstance(e, dict)]


def _q(value) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def dump_map(root: Path, entries: list[dict]) -> Path:
    p = map_path(root)
    lines = [
        "# issue ↔ 测试用例映射，由 deal-git-issue 维护。",
        "# 一条 issue 一条记录，按处理顺序排列（最早在上）；字段含义见 SKILL.md。",
        "version: 1",
        "issues:",
    ]
    if not entries:
        lines[-1] = "issues: []"
    for e in entries:
        ids = e.get("case_ids") or []
        ids_txt = "[" + ", ".join(_q(i) for i in ids) + "]"
        lines.append(f"  - issue: {int(e.get('issue'))}")
        for key in ("url", "title", "platform"):
            if e.get(key):
                lines.append(f"    {key}: {_q(e.get(key))}")
        lines.append(f"    state: {_q(e.get('state') or 'working')}")
        lines.append(f"    case_ids: {ids_txt}")
        for key in ("data_dir", "notes"):
            if e.get(key):
                lines.append(f"    {key}: {_q(e.get(key))}")
        lines.append(f"    updated: {_q(e.get('updated'))}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# ------------------------------------------------------------------ 子命令

def cmd_context(args) -> int:
    root = Path(args.project).resolve() if args.project else project_root()
    url = git_remote(root)
    host, slug, platform = parse_remote(url)
    cli_name = PLATFORM_CLI.get(platform)
    cli: dict = {"name": cli_name, "available": False, "authed": None}
    if cli_name:
        exe = shutil.which(cli_name)
        cli["available"] = bool(exe)
        if exe:
            code, out = run([exe, "auth", "status"])
            cli["authed"] = code == 0
            if code != 0:
                cli["auth_hint"] = out.strip().splitlines()[:3]
    tokens = [t for t in CLI_TOKEN_ENV.get(platform, ()) if os.environ.get(t)]
    tc = discover_test_case(root)
    try:
        import yaml  # noqa: F401
        pyyaml = True
    except ImportError:
        pyyaml = False
        tc.setdefault("warnings", []).append(
            "未安装 PyYAML：YAML 只做最小解析（能取对用例 id，但读不到嵌套字段）")
    entries = load_map(root)
    out = {
        "project_root": str(root),
        "project_name": root.name,
        "remote": url,
        "host": host,
        "platform": platform,
        "repo_slug": slug,
        "cli": cli,
        "token_env": tokens,
        "test_case": tc,
        "issues_map": {
            "file": str(map_path(root)),
            "exists": map_path(root).is_file(),
            "entry_count": len(entries),
            "working": [e.get("issue") for e in entries if e.get("state") == "working"],
            "done": [e.get("issue") for e in entries if e.get("state") == "done"],
        },
        "today": __import__("datetime").date.today().isoformat(),
    }
    if not url:
        out.setdefault("warnings", []).append("没有 git remote，无法定位云仓库")
    if not slug:
        out.setdefault("warnings", []).append("remote 解析不出 owner/repo")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_map_list(args) -> int:
    root = Path(args.project).resolve() if args.project else project_root()
    entries = load_map(root)
    if not entries:
        print(f"{map_path(root)} 里没有记录")
        return 0
    for e in entries:
        ids = ", ".join(e.get("case_ids") or []) or "-"
        print(f"#{e.get('issue')}  [{e.get('state')}]  {e.get('title')}  用例: {ids}")
    return 0


def cmd_map_get(args) -> int:
    root = Path(args.project).resolve() if args.project else project_root()
    for e in load_map(root):
        if str(e.get("issue")) == str(args.issue):
            print(json.dumps(e, ensure_ascii=False, indent=2))
            return 0
    print(f"没有 #{args.issue} 的记录", file=sys.stderr)
    return 1


def cmd_map_upsert(args) -> int:
    root = Path(args.project).resolve() if args.project else project_root()
    entries = load_map(root)
    target = None
    for e in entries:
        if str(e.get("issue")) == str(args.issue):
            target = e
            break
    created = target is None
    if created:
        target = {"issue": int(args.issue)}
        entries.append(target)
        entries.sort(key=lambda x: int(x.get("issue") or 0))

    if args.state and args.state not in STATES:
        print(f"state 只能是 {STATES}", file=sys.stderr)
        return 2
    for field in ("url", "title", "platform", "state", "data_dir", "notes"):
        value = getattr(args, field, None)
        if value is not None:
            target[field] = value
    if args.case_id:
        ids = list(target.get("case_ids") or [])
        for cid in args.case_id:
            if cid not in ids:
                ids.append(cid)
        target["case_ids"] = ids
    if args.clear_case_ids:
        target["case_ids"] = []
    target.setdefault("state", "working")
    target.setdefault("case_ids", [])
    target["updated"] = args.updated or __import__("datetime").date.today().isoformat()

    p = dump_map(root, entries)
    print(f"{'新增' if created else '更新'} #{args.issue} → {p}")
    print(json.dumps(target, ensure_ascii=False, indent=2))
    return 0


def cmd_map_check(args) -> int:
    root = Path(args.project).resolve() if args.project else project_root()
    entries = load_map(root)
    if not entries:
        print("没有记录，跳过校验")
        return 0
    tc = discover_test_case(root)
    known = set(tc.get("case_ids") or [])
    has_manifest = tc.get("manifest") is not None
    data_root = Path(tc.get("data_root") or ".")
    if not has_manifest:
        print("[跳过] 找不到用例清单，只校验数据目录；case_ids 无法核对")
    problems = 0
    for e in entries:
        if e.get("state") == "dropped":
            continue
        issues: list[str] = []
        ids = e.get("case_ids") or []
        if not ids:
            issues.append("没有登记用例 id")
        for cid in ids:
            if has_manifest and cid not in known:
                issues.append(f"用例 {cid} 不在清单里")
        dd = e.get("data_dir")
        if dd and not (data_root / dd).exists():
            issues.append(f"数据目录不存在：{data_root / dd}")
        tag = "OK  " if not issues else "问题"
        print(f"[{tag}] #{e.get('issue')} [{e.get('state')}] " + "; ".join(issues))
        problems += len(issues)
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="deal-git-issue 辅助脚本")
    ap.add_argument("--project", help="项目根，默认用 git 仓库根")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("context", help="输出上下文 JSON").set_defaults(func=cmd_context)
    sub.add_parser("map-list", help="列出映射记录").set_defaults(func=cmd_map_list)

    g = sub.add_parser("map-get", help="查一条映射")
    g.add_argument("--issue", required=True)
    g.set_defaults(func=cmd_map_get)

    u = sub.add_parser("map-upsert", help="新增或更新映射")
    u.add_argument("--issue", required=True, type=int)
    u.add_argument("--url")
    u.add_argument("--title")
    u.add_argument("--platform")
    u.add_argument("--state")
    u.add_argument("--case-id", action="append", dest="case_id")
    u.add_argument("--clear-case-ids", action="store_true")
    u.add_argument("--data-dir", dest="data_dir")
    u.add_argument("--notes")
    u.add_argument("--updated")
    u.set_defaults(func=cmd_map_upsert)

    sub.add_parser("map-check", help="校验映射与清单一致性").set_defaults(func=cmd_map_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
