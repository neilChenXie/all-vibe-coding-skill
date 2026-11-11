---
name: deal-git-issue
description: 当用户想"把 git 云仓库里的一条 issue 从头处理到尾"时使用：自动从远端挑一条未处理 issue 并只打上 working 标签，读 test-case/config.local.yaml 定位测试用例位置，把 issue 与用例的对应关系写进 test-case/issues.yaml，调用 systematic-improve 定下优化方案并实施，最后把用例回填进 test-case/（样本、清单、断言）并跑校验。触发词：处理 issue、领一个 issue、按 issue 优化、把这条 issue 修掉、issue 转测试用例、issue 闭环、deal-git-issue。
---

# deal-git-issue

一条 issue 走完全程：**选中 → 标记 → 对应用例 → 定方案 → 实施 → 用例入库**。

```
第1步 预检        第2步 选 issue     第3步 打 label
（本地能不能干）    （远端拿一条）      （status:working）
      ↓                 ↓                  ↓
第6步 用例入库    第5步 定方案并实施   第4步 确认用例对应
（回填 + 校验）    （systematic-improve）（写 issues.yaml）
```

每一步都有明确的结束标志；任一步达不到，停下来如实说明，不要带着缺口往下走。

## 第 1 步：本地预检

先预检再打标签：本地缺配置时就把 issue 标成 working，等于白占坑，别人看到也不会再碰。

```bash
python "<本 skill 目录>/scripts/issue_kit.py" context
```

输出 JSON，只用它回答四个问题，不要整段复述给用户：

| 字段 | 用途 |
| --- | --- |
| `platform` / `repo_slug` / `cli` / `token_env` | 决定用哪套 issue 命令，见 `references/issue-cli.md` |
| `test_case.config_file` / `data_root` / `data_root_source` | 测试用例位置，后续所有路径都以它为准 |
| `test_case.manifest` / `manifest_format` / `case_ids` | 清单在哪、什么格式、已有哪些用例 |
| `issues_map` | 哪些 issue 已在处理（`working`）、哪些已闭环（`done`） |

停下来的条件（满足任一就停，不要自行脑补补齐）：

- `test_case.exists: false` → 项目没有 `test-case/`，先让用户跑 `setup-test-case`。
- `test_case.data_root_source` 是 `default:test-case/.data` → 只是兜底值，`config.local.yaml` 没配好，先让用户确认数据根。
- `repo_slug` 为空 → 定位不到云仓库，问用户 issue 在哪个仓库。

`test_case.warnings` 里有内容时，挑与本次相关的念给用户（例如"数据根落在项目内，样本可能进 git"），不要全量转述。

## 第 2 步：自动选中一条 issue

**不需要用户挑**，按下面的顺序取第一条，取到即开工：

1. 拉 open issue 列表（命令见 `references/issue-cli.md`），按 `number` 升序排；
2. 跳过带 `status:working` 标签的；
3. 跳过 `issues_map.working` / `issues_map.done` 里已登记的编号；
4. 跳过 `pull_request` 字段非空的（GitHub 的 issues 接口会混进 PR）；
5. 剩下的第一条就是本次要处理的 issue。

例外：用户在本次对话里已指定编号或链接，直接用它，不重新挑选。

选中后**不做二次确认**，但必须先打印三行，让用户有机会打断：

```
选中 issue #42  已处理中: #38, #40 跳过
标题：带合并单元格的 PDF 转 md 后表格列数错乱
要点：<正文里 1~2 句最能说明问题的话，不要大段粘贴>
```

列表为空、或挑不出符合条件的一条 → 停，告诉用户"没有可处理的 open issue"，并把 `working`/`done` 里未被关闭的编号列出来，建议先收尾。

## 第 3 步：标记 working

只做一件事：给这条 issue 打上 `status:working` 标签。标签不存在就先创建，再打。

- 不指派、不评论、不建分支、不改里程碑——用户明确选的就是"仅打 label"。
- 打标签失败（无权限、仓库禁用标签）时：如实写"未能标记 working"，继续往下走，**不要**用评论代替，也不要反复重试。

## 第 4 步：确认 issue 与测试用例的对应关系

按下面顺序找，找到即停：

1. `issues.yaml` 里该 issue 已有记录 → 沿用其 `case_ids`；
2. 清单里 `case_ids` 或标题与 issue 关键词明显对得上 → 取该用例（可能多条）；
3. 数据根里有目录名能对上 → 取该目录对应的用例 id；
4. 都没有 → 这是**新用例**，按既有命名约定起一个 id（kebab-case，与样本目录同名），不要复用别的用例 id。

判断依据不足（例如 issue 描述太泛、候选有用例多条）时，把候选列出来问用户，一次只问一个问题；不要猜。

确定后立刻落盘，让中断也能恢复：

```bash
python "<本 skill 目录>/scripts/issue_kit.py" map-upsert \
  --issue <编号> --url "<issue 链接>" --title "<原标题>" \
  --platform <platform> --state working \
  --case-id <用例id> --data-dir <相对数据根的目录>
```

再向用户说明一句对应关系（"issue #42 ↔ 用例 `tc-merge-cells`"），然后进入第 5 步。

## 第 5 步：调用 systematic-improve 定方案并实施

用 `use_skill` 加载 `systematic-improve`，按它的流程执行。把下面三样作为它的「步骤一：全局了解项目情况」的输入材料，不要让它重新摸索：

- 本 issue 的正文与讨论；
- 第 4 步确定的用例对应关系；
- `test-case/README.md` 里的用例规则（新增/刷新基线的纪律）。

两处衔接要求：

- **目标由 issue 给定**：不要把"要做什么"再问一遍；但 issue 没写清边界、验收标准、影响范围时，仍按 systematic-improve 的方式一次一问地澄清。
- **实施路径必须由用户选**：直接改 / 先出实施计划 / 先出设计文档，三选一，不要替用户决定。

systematic-improve 未安装时，按同样的骨架自行执行：了解项目 → 澄清目标 → 确认方案 → 确认思路 → 用户选实施路径 → 实施。此时要显式告诉用户"systematic-improve 未安装，已用等价流程替代"。

实施完成后回到本流程第 6 步，不要就此结束。

## 第 6 步：用例入库并回填

把这次修复的证据沉淀进 `test-case/`，四件事都要做：

1. **样本落位**：`<data_root>/<case-id>/input.<ext>`、`output.<ext>`，路径相对数据根；大文件先裁到最小可复现片段。
2. **登记清单**：在 `test_case.manifest` 里加条目（或扩充已有条目）。**照抄既有条目的字段结构**，不要新造字段；路径一律相对书写。
3. **生成断言**：有 `test-case/runners/make_assert.py` 就用它，没有就按既有断言文件结构手工补；基线必须取自**修复后**的产物。
4. **跑校验**：`python test-case/runners/run_cases.py --case <id>`，要看到 `PASS 1 | FAIL 0 | SKIP 0`。`SKIP 样本未挂载` 不算通过。

然后回填映射并自检：

```bash
python "<本 skill 目录>/scripts/issue_kit.py" map-upsert \
  --issue <编号> --state done --case-id <用例id> --data-dir <相对目录>

python "<本 skill 目录>/scripts/issue_kit.py" map-check
```

`map-check` 退出码非 0 就按提示补，不要带着不一致收工。

字段细节、两种清单格式的写法、断言与命名规则见 `references/test-case-mapping.md`。

**不自动关闭 issue**：远端状态由用户决定。回报里可以说明"issue 仍是 open + working 标签，需要我关闭或换标签就说一声"。

## 中断与回滚

| 中断点 | 必须做的事 |
| --- | --- |
| 第 3 步之后失败 | 说明失败原因；用户确认放弃时，把 `status:working` 标签摘掉（`gh issue edit --remove-label`），避免占坑 |
| 第 4 步之后失败 | 把 `issues.yaml` 里该条改成 `state: dropped`，在 `notes` 写一句原因 |
| 第 6 步校验不过 | 不要改成 `done`，保持 `working`，把失败输出贴给用户 |

任何情况下都不要谎报完成：没有跑出 PASS、没有 `map-check` 通过，就不能说"已闭环"。

## 回报

只报这五条，不要堆文件清单：

1. 处理了哪条 issue（编号 + 标题 + 链接）；
2. working 标记是否成功，标签名是什么；
3. issue ↔ 用例的对应关系（id 与数据目录）；
4. 方案怎么定的、实施路径是谁选的、改了哪些文件；
5. 用例入库结果：清单条目位置、断言文件、`run_cases.py` 的实际输出行、`map-check` 的退出码。

## 边界

- **只动一条 issue**：一次任务只处理一条，不顺带做别的。
- **只加一个 label**：远端只改 `status:working`，不评论、不指派、不关闭。
- **不改清单格式**：项目原本用 YAML 就用 YAML，原本 JSON 就用 JSON；不迁移、不重排既有条目。
- **不搬样本**：发现大样本位置不对，只提示，等用户确认后再动。
- **不猜用户意图**：issue 与该用哪条用例对不上、验收标准不明确时，问，不要自行认定。
- **不为了变绿改断言**：校验失败先查基线是否过期、样本是否放对。
