本仓的 AI 操作手册在 [`AGENTS.md`](./AGENTS.md)。**请先读它，再动手。**

Gemini CLI 默认只读 `GEMINI.md`（`AGENTS.md` 不在默认 `context.fileName` 里），
所以这里放一行指针 —— **唯一真源是 `AGENTS.md`，本文件不复制任何内容**，
（复制就会有两份要同步的东西。）

若你希望 Gemini CLI 直接读 `AGENTS.md`，在 `.gemini/settings.json` 里设：

```json
{ "context": { "fileName": ["AGENTS.md", "GEMINI.md"] } }
```
