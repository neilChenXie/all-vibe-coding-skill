# skill-bug-report 本地配置

> 本文件由 skill-bug-report 维护，用于记录**用户本地维护的 SKILL 仓库**的测试用例存放位置与命名规则。
>
> 规则：某个仓库首次被用于报 bug、且 `config.md` 中还没有它的记录时，先问用户三个问题——测试用例存放在哪、怎么命名、是否提交到 git——然后把答案追加到本文件，再按规则归档。
>
> 本文件包含本机绝对路径。如果不希望它被提交到公开仓库，可以把 `config.md` 加入仓库的 `.gitignore`，或改名为 `config.local.md` 并在 SKILL.md 中同步说明。

## 记录格式

每个仓库一节，例如：

```md
## 仓库：<owner>/<repo>
- 本地路径：/absolute/path/to/repo
- 测试用例存放位置：/absolute/path/to/repo/test-case/<skill-name>/
- 命名规则：<YYYYMMDD>-<序号>-<简述>.<ext>
- 是否提交 git：否（test-case/ 已列入 .gitignore）
- 备注：
```

---

## 仓库：neilChenXie/all-vibe-coding-skill
- 本地路径：/Users/chen/Project/all-vibe-coding-skill
- 测试用例存放位置：/Users/chen/Project/all-vibe-coding-skill/test-case/<skill-name>/
- 命名规则：<YYYY-MM-DD>-<skill-name>-<简述>.md（日期 + 描述）
- 是否提交 git：否（`test-case/` 已列入 .gitignore）
- 备注：2026-11-09 登记。测试用例归档到 `test-case/` 下按 skill 名建子目录，文件名用「日期 + 描述」，该目录不提交 git。

## 仓库：neilChenXie/all-file-to-md
- 本地路径：/Users/chen/Project/all-file-to-md
- 测试用例存放位置：/Users/chen/Project/all-file-to-md/test-case/<skill-name>/
- 命名规则：<YYYY-MM-DD>-<skill-name>-<简述>.md（日期 + 描述）
- 是否提交 git：否（`test-case/` 已列入该仓库 .gitignore，`git check-ignore` 实测生效）
- 备注：2026-11-09 登记。测试用例归档到仓库根目录 `test-case/` 下、按 skill 名建子目录，文件名用「日期 + 描述」，不提交 git。
