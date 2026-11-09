# ai-correction-journal 本地配置（示例模板）

> 本文件是模板，不含任何本机信息。首次使用 ai-correction-journal 时，把它复制为同目录下的 `config.md`（`config.md` 已列入仓库 `.gitignore`，不会提交）。
>
> 首次使用时，AI 必须先与用户确认「错题本根目录」，再把实际值写入 `config.md`；之后每次直接读该值，不再重复询问。

## 配置项

```yaml
# 错题本根目录：错题文件、INDEX.md、RULES.md 的存放位置
# 支持 ~ 与绝对路径；目录不存在时自动创建
错题本根目录: ~/.agents/ai-correction-journal
```

## 字段说明

| 配置项 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| 错题本根目录 | 是 | `~/.agents/ai-correction-journal` | 所有错题记录、`INDEX.md`、`RULES.md` 的存放目录；`~` 展开为当前用户主目录；目录不存在时自动创建 |

---

（首次使用：确认或修改上面的 `错题本根目录` 后保存为 `config.md`，并按该路径创建目录与 `INDEX.md`、`RULES.md` 骨架。）