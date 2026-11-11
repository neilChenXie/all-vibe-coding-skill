# test-case —— 样本在库外，断言在库内

本项目：**{{PROJECT_NAME}}**（slug：`{{PROJECT_SLUG}}`）
建立时间：{{CREATED_AT}}
样本库：由 `config.local.json` 的 `data_root` 决定（本机路径，不入仓）

---

## 1. 这套结构解决什么

测试用例里最重的通常是**样本**：几十 MB 的文档、图片包、数据库快照、录制的响应体。它们有两个特点——大、常常涉密。直接进 git 会让仓库迅速膨胀，也可能把不该外传的内容带出去。

所以这里把一件事拆成两半：

| 放哪 | 放什么 | 进 git 吗 |
| --- | --- | --- |
| **本目录**（项目内） | 用例清单 `manifest.json`、断言基线 `expected/`、可入仓的小样本 `fixtures/`、运行器 `runners/` | 进 |
| **样本库**（库外） | 原始大样本、跑出来的产物 | 不进 |

仓库里留下的是**怎么验**，样本留在本机。换一台机器，只要把样本库放回去（或用环境变量指过去），`run_cases.py` 就能照常跑；没有样本时它会全部记为 SKIP，不会把 CI 弄红。

## 2. 目录结构

```
test-case/
├─ README.md            # 本文件：框架逻辑、归档与执行规则
├─ manifest.json        # 用例清单：路径 + 指纹 + 断言指向
├─ config.example.json  # 样本根示例
├─ config.local.json    # 本机真实样本根（不入仓）
├─ .gitignore           # 拦截样本与大文件
├─ expected/            # 断言基线，一个用例一个 *.assert.json
├─ fixtures/            # 可入仓的脱敏小样本（见 fixtures/README.md）
└─ runners/
   ├─ case_lib.py       # 指纹计算、样本根解析、快照比对
   ├─ run_cases.py      # 执行校验：PASS / FAIL / SKIP
   ├─ make_assert.py    # 生成或刷新基线
   └─ pre-commit        # 大文件拦截钩子
```

## 3. 样本根怎么定

按优先级从高到低，取第一个命中的：

| 顺序 | 来源 | 用法 |
| --- | --- | --- |
| 1 | 命令行 `--data-root <路径>` | 临时切换，CI 里最常用 |
| 2 | 环境变量 `TESTCASE_DATA` | 换机器时一行 export 即可 |
| 3 | `config.local.json` 的 `data_root` | 本机固定路径，不入仓 |
| 4 | `test-case/.data` | 兜底目录，不存在就等于没有样本 |

`manifest.json` 里的 `input` / `output` **一律写相对路径**，绝对路径只出现在 `config.local.json` 里。这样仓库可以整体迁移，换机器只改一处。

## 4. 一个用例由哪些字段组成

| 字段 | 必填 | 含义 |
| --- | --- | --- |
| `id` | 是 | 用例标识，建议 `kebab-case`，与样本目录同名 |
| `title` | 否 | 一句话说明这个用例考什么 |
| `input` | 是 | 输入样本，相对样本根 |
| `sha256` / `bytes` | 否 | 输入指纹；写了就先校验，样本被换掉会直接 FAIL |
| `run` | 否 | 生成产物的命令，配合 `--run` 使用；不写就用现成产物比对 |
| `output` | 是 | 产物路径，相对样本根；可以是文件也可以是目录 |
| `assert` | 是 | 断言基线，相对本目录，惯例是 `expected/<id>.assert.json` |
| `notes` | 否 | 备注，比如样本来源、是否脱敏 |

`cases` 为空时校验器什么都不做，属于正常状态——先把骨架搭好，再往里加用例。

## 5. 新增一个用例（五步）

```bash
# 1. 把样本放进样本库（路径与 manifest 里的 input 对齐）
#    <样本根>/<id>/输入文件

# 2. 在 manifest.json 的 cases 里加一条（字段见上一节）

# 3. 产出结果：写了 run 就可以让校验器代跑，否则手动生成到 output 指向的位置
python test-case/runners/run_cases.py --case <id> --run

# 4. 用当前产物生成基线
python test-case/runners/make_assert.py --case <id>

# 5. 再跑一次，确认 PASS
python test-case/runners/run_cases.py --case <id>
```

第 4 步是"拍快照"，所以**只在确认产物正确之后做**。反过来，为了让测试变绿去刷基线，等于把测试废掉。

## 6. 执行

```bash
python test-case/runners/run_cases.py                 # 全部用例
python test-case/runners/run_cases.py --case <id>     # 单条
python test-case/runners/run_cases.py --run           # 先跑 case.run 再比对
python test-case/runners/run_cases.py --data-root D:/path/to/data
```

| 退出码 | 含义 |
| --- | --- |
| 0 | 全部 PASS，或有 SKIP（样本没挂载、断言未生成） |
| 1 | 有 FAIL：样本被替换、产物结构变了、或 run 命令本身失败 |

CI 里只需加一条 `python test-case/runners/run_cases.py`。没挂样本的机器会自动 SKIP，不会误报。

## 7. 什么时候该刷新基线

应该刷：

- 需求变了，产物的正确形态随之改变；
- 升级了依赖导致输出格式变化，且已人工确认新格式是对的；
- 样本本身更新了（此时记得同步改 manifest 里的 `sha256` / `bytes`）。

不该刷：

- 测试红了但没查清原因；
- 想绕过 FAIL 让 CI 变绿。

## 8. 断言快照里有什么

`expected/<id>.assert.json` 只存**计数与哈希**，不含正文：

| 产物类型 | 记录内容 |
| --- | --- |
| 文件 | `bytes`、`sha256`；若可作 UTF-8 解码，再加 `lines`、`chars` |
| 目录 | 文件数、总字节、每个文件的相对路径 + `size` + `sha256`，以及这些内容的汇总哈希 |

这样基线文件通常只有几 KB，公开出去也泄漏不出样本内容。缺点是它只回答"结构变没变"，不回答"内容对不对"——需要逐字比对时，把参考答案也放进样本库，作为 `output` 的一部分一起做指纹。

目录快照默认最多统计 2000 个文件，超出会带 `truncated: true`。

## 9. 什么能进仓库

能进：

- `manifest.json`、`expected/`、`runners/`、`README.md`、`config.example.json`；
- `fixtures/` 下**已脱敏**的小样本（单份建议 < 2 MB）。

不能进：

- 任何真实业务样本、含个人或客户信息的文件、跑出来的大体量产物。

两道保险：`.gitignore` 拦扩展名，`runners/pre-commit` 拦大小。安装钩子：

```bash
cp test-case/runners/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## 10. 与样本库的关系

样本库里有一份配套的 `README.md`，写的是"样本怎么放、怎么命名、怎么清理"。两边分工：

- **这里**管"怎么验"：用例定义、断言、执行；
- **样本库**管"东西放哪"：目录层级、命名、体量、保密。

新增样本时两边要同步：样本进库 → 清单登记 → 基线生成。

样本库的具体位置不写进本文件——它因人而异，统一记在 `config.local.json`（不入仓），或用环境变量 `TESTCASE_DATA` 指定。
