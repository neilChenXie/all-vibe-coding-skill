# issue 远端操作速查

先跑 `python "<本 skill 目录>/scripts/issue_kit.py" context`，拿到 `platform`、`repo_slug`、`cli`、`token_env` 四个字段，再按下表选一套命令。**不要猜平台**，以 `context` 的输出为准。

| context 输出 | 用哪套 |
| --- | --- |
| `platform: github` 且 `cli.available: true` | `gh` |
| `platform: gitlab` 且 `cli.available: true` | `glab` |
| CLI 不可用但 `token_env` 非空 | REST |
| CLI 不可用且无 token | 降级：让用户在网页上看，把 issue 正文贴进来 |

## 标签名

默认 `status:working`，与 `SKILL.md` 保持一致。想换就全局改名，不要一次任务换一个。

## GitHub + gh

```bash
# 列出 open issue（按 number 升序排序后再挑）
gh issue list --repo <owner/repo> --state open --limit 200 \
  --json number,title,labels,createdAt

# 读单条（要正文时加 --json body）
gh issue view <number> --repo <owner/repo> --json number,title,body,labels,state,url

# 标签是否存在（已存在就不要重复创建）
gh label list --repo <owner/repo> --search "status:working" --json name

# 不存在时创建；存在时这条会以非 0 退出，属正常
gh label create "status:working" --repo <owner/repo> \
  --color "FBCA04" --description "已有人开始处理"

# 打标签
gh issue edit <number> --repo <owner/repo> --add-label "status:working"
```

## GitLab + glab

```bash
glab issue list -R <owner/repo> --per-page 100 -O json
glab issue view <iid> -R <owner/repo>
glab label list -R <owner/repo>
glab label create -R <owner/repo> -n "status:working" -c "#FBCA04" -d "已有人开始处理"
glab issue update <iid> -R <owner/repo> -l "status:working"
```

`glab issue list` 默认只列 open；要连 closed 一起看时加 `-A`。

## 无 CLI：REST

**Windows 上 `curl` 是 `Invoke-WebRequest` 的别名，必须写 `curl.exe`**，否则参数会被 PowerShell 吃掉。

GitHub（`GITHUB_TOKEN` 或 `GH_TOKEN`）：

```bash
# 列表
curl.exe -s -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner/repo>/issues?state=open&per_page=100"

# 创建标签（已存在返回 422，忽略即可）
curl.exe -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner/repo>/labels" \
  -d '{"name":"status:working","color":"FBCA04"}'

# 打标签（注意：issues 列表里 PR 也会出现，带 pull_request 字段的要跳过）
curl.exe -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner/repo>/issues/<number>/labels" \
  -d '{"labels":["status:working"]}'
```

GitLab（`GITLAB_TOKEN`）：

```bash
# 项目路径要 urlencode，owner/repo → owner%2Frepo
curl.exe -s -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/projects/owner%2Frepo/issues?state=opened&per_page=100"

curl.exe -s -X PUT -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/projects/owner%2Frepo/issues/<iid>" \
  -d "labels=status:working"
```

GitLab 打标签是覆盖式：原有 labels 会丢，先 PUT 前把现存的 `labels` 一起带上。

## 失败怎么办

| 情况 | 处理 |
| --- | --- |
| 标签创建失败（无权限 / 仓库禁用了 label） | 跳过标记，在回报里写明"未能标记 working"，继续往下走 |
| 打标签失败 | 同上，不要重试三次以上，也不要用评论代替（用户选的是只打 label） |
| 列表为空 | 不要编造 issue；停下来告诉用户"当前没有 open issue" |
| 令牌过期 | 让用户 `gh auth login` 或更新环境变量，不要尝试内置账号 |

## 权限边界

- 只读 issue 内容 + 增删 `status:working` 这一个标签。不评论、不指派、不关闭、不改里程碑。
- 用户明确要求时才执行 `gh issue close` 或加其它标签。
