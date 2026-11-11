# 通过浏览器上传测试用例到 GitHub Issue

## 为什么不用 ghost / gh

`gh`（GitHub CLI）目前没有给 issue 添加附件的命令。相关功能请求 [cli/cli#14194](https://github.com/cli/cli/issues/14194) 仍然处于 open 状态，`gh issue create` 只接受 `--body` / `--body-file` 文本。GitHub 的 issue 附件实际是由网页编辑器上传到 `https://github.com/user-attachments/files/...` 的，上传接口没有公开的 REST API。

所以方案是：**用 DSH 的 browser_* 工具打开 GitHub 网页编辑器，把文件"粘贴"进去，让 GitHub 完成上传，拿到 `user-attachments` 链接，再用 `gh issue create` 把链接写进正文。**

已经在 Chromium + DSH Browser Control 扩展上实测通过。

## 操作步骤

### 1. 确认浏览器可用

先调用 `browser_tabs`（action: list）。如果返回 `count: 0` 或报 "No current window"，见下面的排错。

### 2. 打开目标仓库的新建 issue 页面

```
https://github.com/<owner>/<repo>/issues/new
```

用 `browser_navigate` 打开；如果页面已经是编辑状态（GitHub 会记住上次未提交的草稿），直接复用即可。页面加载后调用一次 `browser_read` 或 `browser_snapshot` 确认已登录（右上角能看到自己的用户名）。

### 3. 上传文件

把测试用例文件转成 base64，然后调用 `browser_evaluate`。**注意**：`browser_evaluate` 有较短的执行超时，所以不要在里面 `await` 等待上传；只负责派发 paste 事件，另起一次调用读取结果。

```js
(() => {
  // 替换这三个值：BASE64 内容、文件名、MIME 类型
  const b64 = 'BASE64_PLACEHOLDER';
  const name = 'test-case.md';
  const mime = 'text/markdown';

  const bin = atob(b64);
  const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
  const file = new File([bytes], name, { type: mime });
  const dt = new DataTransfer();
  dt.items.add(file);

  const ta = document.querySelector('textarea');
  if (!ta) return { ok: false, reason: 'no textarea found' };
  ta.focus();
  const evt = new ClipboardEvent('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(evt, 'clipboardData', { value: dt });
  ta.dispatchEvent(evt);
  return { ok: true, valueLen: ta.value.length };
})()
```

用 bash 生成参数：

```bash
F=/path/to/test-case.md
NAME=$(basename "$F")
B64=$(base64 -i "$F" | tr -d '\n')
# 常见 MIME：
#   .md/.txt/.csv -> text/plain（最稳）
#   .png -> image/png，.jpg/.jpeg -> image/jpeg，.pdf -> application/pdf
#   .docx -> application/vnd.openxmlformats-officedocument.wordprocessingml.document
#   .xlsx -> application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
#   .zip  -> application/zip
```

把 `BASE64_PLACEHOLDER`、`name`、`mime` 替换后调用。

### 4. 读取上传结果

等 2~5 秒（GitHub 上传是异步的），再次调用 `browser_evaluate`：

```js
(() => {
  const ta = document.querySelector('textarea');
  const text = ta ? ta.value : '';
  const links = [...text.matchAll(/https:\/\/github\.com\/user-attachments\/files\/[^\s)]+/g)]
    .map(m => m[0]);
  return { links, text: text.slice(0, 3000) };
})()
```

看到 `https://github.com/user-attachments/files/<id>/<文件名>` 就是上传成功。编辑器里通常会自动插入：

```
[文件名](https://github.com/user-attachments/files/<id>/<文件名>)
```

### 5. 清理

上传拿到链接后，**不要提交这个测试页面**。关闭标签页（`browser_tabs` action: close）即可，GitHub 草稿不会变成 issue。

### 6. 多个文件

逐个执行第 3、4 步（每个文件单独粘贴、单独等待）。也可以在一次 paste 里塞多个 `File`，但逐个更稳，也更容易确认每个文件是否成功。

## 排错

### `browser_tabs` 返回 0 个标签页

常见原因：Chrome 当前窗口不在 DSH Browser Control 扩展所在的 profile。扩展的 tab 权限只覆盖它自己所在的 profile。

排查：

```bash
# 1. 确认浏览器进程在运行
pgrep -fl "Google Chrome"

# 2. 找到扩展所在 profile（unpacked 扩展路径通常包含 DSH 字样）
python3 - <<'EOF'
import json, os
base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
for prof in os.listdir(base):
    sec = os.path.join(base, prof, "Secure Preferences")
    if not os.path.isfile(sec):
        continue
    d = json.load(open(sec))
    for eid, cfg in (d.get("extensions", {}).get("settings") or {}).items():
        path = cfg.get("path", "")
        if "dsh" in path.lower() or "browser-control" in path.lower():
            print(prof, eid, path)
EOF
```

如果输出 `Profile 1`，用该 profile 打开新窗口：

```bash
open -na "Google Chrome" --args --profile-directory="Profile 1" --new-window \
  "https://github.com/<owner>/<repo>/issues/new"
```

然后重新调用 `browser_tabs`。

### 找不到 textarea

GitHub 编辑器可能是新版组件（`.prc-Textarea-*`），但核心仍是 `<textarea>`。页面没加载完时先用 `browser_wait` 等 `textarea` 出现；如果页面用了富文本编辑器（contenteditable），把 `document.querySelector('textarea')` 换成 `document.querySelector('[contenteditable="true"]')`，事件目标一致。

### 上传后没有 user-attachments 链接

- 网络慢：多等几秒再读一次
- 文件太大：base64 注入建议 ≤ 1MB；更大文件先压缩
- 文件类型被禁：GitHub 不允许上传可执行文件等类型，测试用例一般没问题
- 未登录：先确认浏览器已登录目标 GitHub 账号

### 所有浏览器手段都不可用

降级方案：

1. `gh gist create <file>`：创建 gist 并得到公开链接，issue 正文里引用 gist 链接
2. 文本类测试用例（md/txt/csv）直接把内容贴进 issue 正文的代码块
3. 在 issue 正文里说明"附件上传失败"，并给出本地文件路径
