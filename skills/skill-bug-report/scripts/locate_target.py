#!/usr/bin/env python3
"""定位目标 SKILL 的路径、维护方式与 GitHub issue 仓库。

用法：
  python3 locate_target.py --skill pdf-to-md
  python3 locate_target.py --skill /path/to/some-skill

输出 JSON（stdout）：
  {
    "query": "pdf-to-md",
    "skill_path": "/Users/chen/Project/all-file-to-md/skills/pdf-to-md",
    "skill_md": "/Users/chen/Project/all-file-to-md/skills/pdf-to-md/SKILL.md",
    "local_maintained": true,
    "git_root": "/Users/chen/Project/all-file-to-md",
    "git_remote": "git@github.com:neilChenXie/all-file-to-md.git",
    "issue_repo": "neilChenXie/all-file-to-md",
    "upstream": null,
    "candidates": [...],
    "warnings": [...]
  }

非本地维护（无 .git）时，upstream 会尽量从安装记录 / 市场配置 / SKILL.md 中查找来源，
找不到则为 null。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")


def real(path):
    return os.path.realpath(os.path.expanduser(path))


def run(cmd, cwd=None, timeout=10):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def git_root_of(path):
    cur = real(path)
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def git_remote(git_root):
    url = run(["git", "-C", git_root, "remote", "get-url", "origin"])
    if url:
        return url
    remotes = run(["git", "-C", git_root, "remote"])
    if remotes:
        first = remotes.splitlines()[0].strip()
        if first:
            return run(["git", "-C", git_root, "remote", "get-url", first])
    return None


def github_repo_from_url(url):
    if not url:
        return None
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?$", url.strip())
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}"


def scan_skill_md_links(skill_path):
    links = []
    md_path = os.path.join(skill_path, "SKILL.md")
    if os.path.exists(md_path):
        try:
            text = open(md_path, encoding="utf-8", errors="ignore").read()
            links = re.findall(r"https?://github\.com/[^\s)<>\"'`]+", text)
        except Exception:
            links = []
    seen = []
    for link in links:
        link = link.rstrip(".,;")
        if link not in seen:
            seen.append(link)
    return seen


def skill_lock_source(name):
    data = read_json(os.path.join(HOME, ".agents", ".skill-lock.json"))
    entry = ((data or {}).get("skills") or {}).get(name)
    if not entry:
        return None
    source_url = entry.get("sourceUrl") or ""
    return {
        "kind": "npx-skills-lock",
        "source": entry.get("source"),
        "sourceUrl": source_url,
        "repo": github_repo_from_url(source_url),
    }


def claude_plugin_sources(name):
    results = []
    installed = read_json(
        os.path.join(HOME, ".claude", "plugins", "installed_plugins.json")
    ) or {}
    markets = read_json(
        os.path.join(HOME, ".claude", "plugins", "known_marketplaces.json")
    ) or {}
    for plugin_key, entries in (installed.get("plugins") or {}).items():
        marketplace = plugin_key.split("@", 1)[-1] if "@" in plugin_key else ""
        for entry in entries or []:
            install_path = (entry or {}).get("installPath")
            if not install_path or not os.path.isdir(install_path):
                continue
            has_skill = any(
                os.path.isdir(os.path.join(install_path, sub, name))
                for sub in ("skills", "")
            )
            if not has_skill:
                continue
            source = (markets.get(marketplace) or {}).get("source") or {}
            results.append(
                {
                    "kind": "claude-plugin",
                    "plugin": plugin_key,
                    "marketplace": marketplace,
                    "repo": source.get("repo"),
                    "installPath": install_path,
                }
            )
    return results


def candidate_paths(name):
    candidates = [
        os.path.join(HOME, ".agents", "skills", name),
        os.path.join(HOME, ".claude", "skills", name),
    ]
    # 从当前目录向上逐层查找 <dir>/skills/<name>（覆盖在仓库子目录中执行的情况）
    cur = os.getcwd()
    for _ in range(8):
        candidates.append(os.path.join(cur, "skills", name))
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    base = os.getcwd()
    for root, dirs, _files in os.walk(base):
        depth = root[len(base):].count(os.sep)
        if depth > 4:
            dirs[:] = []
            continue
        if os.path.basename(root) == "skills" and name in dirs:
            candidates.append(os.path.join(root, name))
    found, seen = [], set()
    for candidate in candidates:
        resolved = real(candidate)
        if resolved not in seen and os.path.isdir(resolved):
            seen.add(resolved)
            found.append(resolved)
    return found


def main():
    parser = argparse.ArgumentParser(description="定位目标 SKILL 与 GitHub issue 仓库")
    parser.add_argument("--skill", required=True, help="skill 名称或路径")
    args = parser.parse_args()

    query = args.skill.strip()
    warnings = []

    if os.path.exists(real(query)):
        skill_path = real(query)
        candidates = [skill_path]
    else:
        candidates = candidate_paths(query)
        if not candidates:
            print(
                json.dumps(
                    {
                        "query": query,
                        "error": "skill not found",
                        "candidates": [],
                        "warnings": [
                            "常见目录与当前工作区中都未找到该 skill，"
                            "请让用户提供 skill 名称或路径"
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2
        skill_path = candidates[0]
        if len(candidates) > 1:
            warnings.append(
                "存在多个同名候选，已取第一个；如需其他路径请用 --skill 显式指定"
            )

    skill_md = os.path.join(skill_path, "SKILL.md")
    if not os.path.exists(skill_md):
        warnings.append("该目录下没有 SKILL.md，可能不是 skill 目录")

    git_root = git_root_of(skill_path)
    local_maintained = git_root is not None
    remote = git_remote(git_root) if git_root else None
    issue_repo = github_repo_from_url(remote)

    upstream = None
    if not local_maintained:
        entries = []
        lock_entry = skill_lock_source(query)
        if lock_entry:
            entries.append(lock_entry)
        entries.extend(claude_plugin_sources(query))
        for link in scan_skill_md_links(skill_path):
            entries.append(
                {
                    "kind": "skill-md-link",
                    "sourceUrl": link,
                    "repo": github_repo_from_url(link),
                }
            )
        if entries:
            upstream = entries
            if not any(e.get("repo") for e in entries):
                warnings.append("找到来源线索但没有解析出 GitHub owner/repo")
            else:
                warnings.append("非本地维护：请向用户确认 issue 是否提交到 upstream 仓库")

    if local_maintained and not issue_repo:
        warnings.append(
            "本地仓库没有可解析的 GitHub remote，无法自动创建 issue，建议输出草稿"
        )

    result = {
        "query": query,
        "skill_path": skill_path,
        "skill_md": skill_md,
        "local_maintained": local_maintained,
        "git_root": git_root,
        "git_remote": remote,
        "issue_repo": issue_repo,
        "upstream": upstream,
        "candidates": candidates,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
