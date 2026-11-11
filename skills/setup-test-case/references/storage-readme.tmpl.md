# {{PROJECT_NAME}} —— 测试样本库

- 对应项目：`{{PROJECT_ROOT}}`
- 项目内用例清单：`{{PROJECT_ROOT}}/test-case/manifest.json`
- 建立时间：{{CREATED_AT}}

这个目录**不进版本库**，存放本项目的原始样本与产物。

---

## 1. 这里放什么

| 放这里 | 不放这里 |
| --- | --- |
| 原始输入样本（文档、图片包、数据包、录制响应） | 代码、脚本、断言基线 |
| 由样本跑出来的产物 | 可入仓的脱敏小样本（那些放项目内 `test-case/fixtures/`） |

判断标准很简单：**只有当它大到不该进 git，或不能公开时，才放这里。** 一份能公开、几百 KB 的样例，应该做成 `fixtures/` 进仓库，这样别人克隆下来就能跑。

## 2. 与项目的关系

项目内 `test-case/manifest.json` 里每条用例的 `input` / `output` 都是**相对本目录**的路径；`assert` 则相对项目内 `test-case/`：

```json
{
  "id": "example-case",
  "input": "example-case/input.bin",
  "output": "example-case/output/",
  "assert": "expected/example-case.assert.json"
}
```

本目录的绝对路径记在项目的 `test-case/config.local.json`，或通过环境变量 `TESTCASE_DATA` 提供。**不要**把绝对路径写进 `manifest.json`。

## 3. 目录约定

按用例 id 建一级目录，一个用例一个目录，输入与产物都在里面：

```
{{DATA_ROOT}}/
├─ README.md                 # 本文件
├─ example-case/
│  ├─ input.bin              # 原始样本
│  └─ output/                # 跑出来的产物（可随时重生成）
└─ another-case/
   ├─ input.bin
   └─ output/
```

同一条用例的多份样本用后缀区分：`input.bin`、`input-mini.bin`、`input-broken.bin`，并在 `manifest.json` 的 `notes` 里说明各自考什么。

## 4. 命名

- 目录与 `manifest.json` 的 `id` **完全一致**，不要另起别名；
- 全小写、`kebab-case`，不用空格与中文；
- 一个用例若同时有输入与参考答案，参考答案命名 `<样本名> + .expected.<扩展名>`，放在同一目录。

## 5. 归档流程

新增一个用例时，按顺序做，缺一步后面就会对不上：

1. **放样本**：在本目录建 `<id>/`，样本放进去；
2. **登记**：在项目 `test-case/manifest.json` 的 `cases` 里加条目，写 `input` / `output` / `assert`；
3. **算指纹**：`sha256` 与 `bytes` 可以直接用 `runners/case_lib.py` 的 `sha256_file()` 算，也可以留空——留空意味着"样本换了不会被发现"，重要样本建议填；
4. **生成产物**：跑一次转换/处理，把结果落到 `output`;
5. **生成基线**：`python test-case/runners/make_assert.py --case <id>`；
6. **回填 README**：如果这个用例值得别人知道，在下面「当前用例」表里加一行。

## 6. 体量管理

- 单份样本超过 500 MB 时，考虑拆分或先裁剪出最小可复现片段；
- `output/` 目录随时可删——它由样本重跑生成，不需要备份；
- 长期不用的用例：先从 `manifest.json` 移除，再删目录，避免留下没人认领的样本。

## 7. 保密

- 本目录默认视为**含敏感信息**：客户名、真实业务数据、内部系统截图都要按需脱敏或替换为合成数据；
- 要对外分享的样本，做一份脱敏版放进项目内 `test-case/fixtures/`，原版留在这里；
- 不要把本目录整个压缩后发出去，也不要放进公开网盘。

## 8. 当前用例

| id | 考什么 | 体量 | 备注 |
| --- | --- | --- | --- |
| （示例）example-case | 最小可跑通的样例 | 1.2 MB | 合成数据，无真实信息 |

> 这张表靠人工维护，和 `manifest.json` 不是自动同步的。它的作用是让人一眼看到"这个项目有哪些样本"，不必去翻 JSON。
