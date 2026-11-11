---
name: report-skill-bug
description: 当用户使用某个 SKILL 完成某件事后发现问题（输出错误、流程缺陷、结果不符合预期），想把问题、建议的解决方案、测试用例文件及期望输出整理成 GitHub issue 提交到该 SKILL 的 git 仓库时使用；也用于把测试用例归档到本地并按规则维护 config.md。用户说"报个 bug"、"反馈问题"、"给这个 skill 提 issue"、"把测试用例上传到仓库 issue"、"这个 skill 有问题"、"帮我给刚才那个 skill 提个 issue"时触发。
---

# SKILL Bug Report

用户在用某个 SKILL 做事时踩到坑，想把坑和证据报到该 SKILL 的仓库。这个 SKILL 把这件事标准化成一条可重复的流水线：

- 认出"上面使用的这个 SKILL"是哪个、它的云端仓库在哪
- 把测试用例归档到本地（规则统一记在 `config.md`，首次遇到某个仓库时询问用户并记录）
- 把测试用例文件真正传进 issue（`gh` 不支持 issue 附件，走浏览器上传）
- 创建一个结构完整、可复现的 issue，并返回 issue URL

## 开始前

1. 读本 skill 目录下的 `config.md`，了解已记录的测试用例归档规则。若 `config.md` 不存在，把同目录的 `config.example.md` 复制为 `config.md` 后再读（`config.md` 是本地文件，已被 `.gitignore` 忽略）。
2. 检查素材是否齐全。缺什么问什么，一次只问一个：
   - **发现的问题**：症状、在什么输入/操作下出现
   - **建议的解决方案**：没有也可以写"暂无建议"
   - **测试用例文件**：用户提供的文件路径；没有就询问
   - **这份文件应该输出的测试结果建议**：即期望输出
3. 进入下面的流程。

## 第 1 步：确定目标 SKILL

"上面使用的这个 SKILL"指当前对话里刚被使用或加载过的 SKILL。定位依据，按可靠性排序：

1. 对话中最近的 `<skill_content name="...">` 块、"加载/使用了 xxx 技能"的记录——排除 report-skill-bug 自己
2. 用户消息里明确点名的 skill
3. 对话里出现过多个候选、无法判断时，列出候选让用户选

如果用户说的 skill 名与目录名对不上（例如名字是展示名），用 `ls ~/.agents/skills/`、`ls ~/.claude/skills/` 搜索 SKILL.md 中的 `name:` 字段。

## 第 2 步：定位 skill 路径与云端仓库

```bash
python3 "<report-skill-bug 目录>/scripts/locate_target.py" --skill "<skill 名或路径>"
```

脚本输出 JSON，关键字段：

| 字段 | 含义 |
|---|---|
| `skill_path` | skill 目录（已解析 symlink） |
| `local_maintained` | 是否本地维护（上层存在 `.git`） |
| `git_remote` / `issue_repo` | 本地仓库的 remote 与 GitHub `owner/repo` |
| `upstream` | 非本地维护时的来源（来自 `.skill-lock.json`、插件市场记录、SKILL.md 里的仓库链接） |
| `candidates` / `warnings` | 候选路径与诊断信息 |

按 `local_maintained` 分流：

- **本地维护**（用户自己的 skill 仓库）：用 `issue_repo` 作为 issue 目标，直接提交。
- **非本地维护**：先看 `upstream` 是否给出仓库。有，就在最终确认时告诉用户"该 skill 来自 `<repo>`，issue 将提到这里"；没有，就问用户目标仓库。用户也不知道时，降级为输出 issue 草稿。
- **没有 GitHub remote**：生成 issue 草稿，说明去哪里提交。

判断"本地维护"的标准是 skill 路径向上能找到 `.git`——这样 issue 一定提在用户能直接改代码的仓库里，修复闭环最短。

## 第 3 步：归档测试用例

按 `config.md` 中该仓库的规则归档：

- **已有规则**：按规则把测试用例**复制**到目标位置（复制，不移动，用户的原文件保持原地）。目录不存在就创建。
- **没有规则**：问用户三件事——存放位置、命名规则、是否提交 git；用户回答后写入 `config.md`，再归档。
- **测试用例只存在于对话描述里、没有实体文件**：先按规则在归档位置生成一个 `.md` 文件，内容包含输入样例和期望输出。
- **非本地维护的 skill**：如果 `config.md` 已有该仓库（或该 skill 所属上游仓库）的规则就归档；没有且用户没给规则，就跳过归档，保留原文件并在结果里说明——不要硬造一个位置。

写入 `config.md` 时保持记录稳定：仓库规则（路径、命名、是否提交 git）写清楚；备注只写登记日期和规则出处，不要把一次性 issue 链接写进配置。

## 第 4 步：上传测试用例附件

`gh` 没有上传 issue 附件的命令（cli/cli#14194 至今 open），所以用 DSH 的 browser_* 工具：在 GitHub 网页编辑器的 textarea 上派发 paste 事件，GitHub 会异步把文件传到 `https://github.com/user-attachments/files/...` 并插入 markdown 链接。

完整操作、JS 代码和排错见 `references/browser-upload.md`。主流程：

1. `browser_tabs` 确认浏览器可用；打开目标仓库 `https://github.com/<owner>/<repo>/issues/new`
2. `browser_evaluate` 把文件内容转 base64 构造 `File`，用 `DataTransfer` + `ClipboardEvent('paste')` 注入编辑器
3. 等上传完成（几秒），从 textarea 读出 `user-attachments` 链接
4. 关闭测试标签页

限制与注意事项：

- 单文件建议不超过 1MB；base64 通过 evaluate 注入，参数过长会失败或变慢
- 浏览器必须已登录 GitHub，且当前窗口在 DSH 扩展所在的 Chrome profile 下
- 上传验证标准：textarea 中出现 `https://github.com/user-attachments/` 链接，而不是"上传中"占位
- 如果 `browser_tabs` 返回 0 个标签页，先按 `references/browser-upload.md` 的排错节处理（最常见原因是 Chrome 当前窗口不在扩展所在的 profile），不要直接断定浏览器不可用
- 可选但推荐：上传后下载该链接、核对大小/哈希与本地文件一致，作为附件完整性的证据

## 第 5 步：创建 issue

用 `references/issue-template.md` 组装正文。标题格式：

```
[<skill-name>] <一句话问题摘要>
```

创建前向用户确认四项：目标仓库、标题、正文、附件链接。如果用户在本轮已经明确说过"直接提交/已确认"，就跳过重复确认。确认后：

```bash
gh issue create --repo <owner/repo> \
  --title "[<skill-name>] <问题摘要>" \
  --body-file <临时正文文件>.md
```

创建后验证返回的 issue URL 可访问，再把 URL 输出给用户。

issue 的语言跟随目标仓库：用户自己的仓库用中文；给上游开源仓库提 issue 时用其常用语言（通常是英文），避免因为语言问题被忽略。

## 降级方案

| 情况 | 做法 |
|---|---|
| 浏览器桥接不可用 | `gh gist create <file>` 上传测试用例得到 gist 链接；或把文本类用例直接贴进 issue 正文并说明 |
| 无法确定仓库或无权限 | 输出完整 issue 草稿（标题 + 正文 + 附件说明），告诉用户去哪里提交 |
| 文件过大（> 1MB） | 先压缩或裁剪测试用例；仍不行则用 gist |
| upstream 是第三方仓库且用户未确认 | 只输出草稿，不向别人的仓库提 issue |

## 原则

- 报告真实观察到的问题。不确定的地方标注"待确认"，不要编造复现步骤或期望输出。
- 一个 issue 只装一个问题；多个问题拆成多个 issue。
- 测试用例是证据：优先用用户提供的真实文件；自己构造时在 issue 中注明"用例由 AI 根据描述构造"。
- 期望输出要具体到"这个文件经过该 SKILL 处理后应该得到什么结果"，而不是"应该正常工作"。
- 不谎报成功：上传后必须看到链接、创建后必须看到 issue URL 才能报告完成。
