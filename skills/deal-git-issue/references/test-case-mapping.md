# issue ↔ 测试用例映射规范

## 一、`test-case/issues.yaml`

由 `scripts/issue_kit.py` 写入，格式固定，**不要手改格式**（脚本用 Edit 之外的方式整文件重写，手改的缩进会被冲掉）。字段含义如下：

| 字段 | 说明 |
| --- | --- |
| `issue` | issue 编号，整数，唯一键 |
| `url` | issue 链接，原样照抄 |
| `title` | issue 原题，不翻译、不改写 |
| `platform` | `github` / `gitlab` / 其它 host |
| `state` | `working`（在处理）/ `done`（已闭环）/ `dropped`（放弃，需在 `notes` 写原因） |
| `case_ids` | 对应用例 id 列表，必须能在 `manifest.yaml`/`manifest.json` 里找到 |
| `data_dir` | 用例样本目录，**相对数据根**，不写绝对路径 |
| `updated` | 最后更新日期 `YYYY-MM-DD` |
| `notes` | 一句话备注，可在建映射时先留空 |

写入时机只有两处：

1. 第 4 步建立对应关系后 → `state: working`，`case_ids` 可先留空或填候选；
2. 第 6 步用例入库、校验通过后 → `state: done` 并补齐 `case_ids` 与 `data_dir`。

中间失败（放弃、方案被否）→ `state: dropped` 并在 `notes` 写原因，不要直接删记录。

## 二、清单条目（manifest）

先确认清单是 YAML 还是 JSON（`context` 输出的 `manifest_format`），**沿用既有格式，不改清单类型**。

YAML 形态：

```yaml
cases:
  - id: tc-merge-cells
    title: 合并单元格的表格列数应与源文件一致
    issue: 42                          # 该项目有这层约定时才加，否则不要新造字段
    input: cases/tc-merge-cells/input.pdf
    output: cases/tc-merge-cells/output.md
    assert: expected/tc-merge-cells.json
```

JSON 形态：

```json
{
  "cases": [
    {
      "id": "tc-merge-cells",
      "title": "合并单元格的表格列数应与源文件一致",
      "input": "cases/tc-merge-cells/input.pdf",
      "output": "cases/tc-merge-cells/output.md",
      "assert": "expected/tc-merge-cells.json"
    }
  ]
}
```

硬规则：

- **照抄既有条目的字段结构**：项目里已有的条目含哪些字段，新条目就含哪些；缺字段去读 `test-case/README.md`，不要凭想象补。
- `id` 用 kebab-case，与样本目录名一致。
- `input` / `output` / `assert` 一律**相对数据根**或相对 `test-case/` 书写，禁止绝对路径。
- 一个 issue 通常对应一条用例；issue 里含多个独立缺陷时拆多条，`case_ids` 里都列上。
- 已有同名语义的用例时**扩充旧条目**（补输入或收紧断言），不要新建近似重复的用例。

## 三、样本落位

```
<data_root>/<case-id>/input.<ext>      # 复现输入
<data_root>/<case-id>/output.<ext>     # 期望产物（跑完与被测程序产出比对）
```

- 数据根来自 `test-case/config.local.yaml` 的 `data_root`（`context` 输出的 `test_case.data_root`）。
- 样本一律不进 git；`fixtures/` 只放脱敏小样本。
- 大文件先裁到最小可复现片段；单份上限遵循项目 README。

## 四、断言基线

- 有 `test-case/runners/make_assert.py` → `python test-case/runners/make_assert.py --case <id>`，不要手写哈希。
- 没有该脚本 → 按既有断言文件的字段结构手工补，并在回报里说明"基线为手工生成"。基线必须来自**修复后**的产物，不能拿修复前的产物当基线。

## 五、验证

```bash
python test-case/runners/run_cases.py --case <id>
```

- 期望 `PASS 1 | FAIL 0 | SKIP 0`。
- 结果是 `SKIP 样本未挂载` → 样本没放进数据根，不算通过，必须补上再跑。
- 结果是 `FAIL` → 先看差异是否来自基线过期，不要为了变绿去改断言。
- 项目没有 `run_cases.py` 时，用项目自己的测试命令验证，并在回报里写清用了哪条命令。

## 六、一致性检查

```bash
python "<本 skill 目录>/scripts/issue_kit.py" map-check
```

退出码 0 表示所有记录的 `case_ids` 都在清单里、`data_dir` 都真实存在。非 0 就按提示补齐，不要放着不管。
