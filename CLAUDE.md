<!-- 本文件是指针：完整规程在 AGENTS.md。请先读那个文件。 -->

# CLAUDE.md

**完整规程见 [`AGENTS.md`](AGENTS.md) —— 请先读它。**

本仓是 Surge / Egern / mihomo（Clash Meta）三内核代理配置模板。

> 本文件只是入口指针，内容以 `AGENTS.md` 为准（**不做第二份副本**，避免漂移）。

## ⚠️ 红线（先看这个，再看全文）

**✅ 总是**：改完跑 `python tools/gates/verify_all.py`（唯一入口，与 CI 同源）——
绿了才算改完；改完整版后跑 `python tools/run/make_min.py --apply` 同步 `.min`。

**🚫 从不**：手工编辑生成物 —— `rules/*.yaml`（改真源 `rules/*.list`）、
`clash/profiles/*.yaml`（改 `clash/override/my_clash*.js`）；
不要为「让门禁变绿」而改判据；不要把三内核「对齐」（机制不同，差异常是刻意的）。
