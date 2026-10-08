---
name: self-conf-skills
description: 维护 Surge / Egern / mihomo（Clash Meta）三内核代理配置模板仓库。改 profile 配置键、调分流规则与策略组、加换删规则集、防 DNS 泄露、排查拦截失效或分流异常、发版、跑门禁、改判据时使用。包含 8 篇技术参考（逐键语义 / DNS 原理 / 规则集选型 / 事故复盘 / 运维发版 / 门禁纪律）、整套判据脚本与生成工具。只要用户提到 self-conf、Surge 配置、Egern 配置、mihomo 或 Clash 配置、分流版、懒人版、规则集、DNS 泄露、审计脚本、闸门，或让你修改本仓的配置，就应使用本技能。
license: MIT
---

# self-conf 维护技能

本仓是 Surge / Egern / mihomo **三内核代理配置模板**。
配置本身是给人读的（注释写满「为什么」）；本技能是 AI 的操作规程与参考资料。

## 本仓遵循的规范

| 规范 | 用于 | 本仓的落实 | 谁在守 |
|:--|:--|:--|:--|
| **[Agent Skills](https://agentskills.io/specification)**（Anthropic 发布，开放标准，30+ 工具） | 本目录的形态 | 目录名 = `name`、有 frontmatter、SKILL.md < 500 行、`references/` 按需加载 | `gates/check_skill_spec.py` |
| **[AGENTS.md](https://agents.md)**（Linux Foundation 托管，60k+ 项目） | 仓库根的常驻指令 | 根 `AGENTS.md` 是唯一真源；不建 `CLAUDE.md`/`.cursorrules`（会屏蔽真源） | `gates/check_ai_entry.py` |
| 本仓自制：**写死数字必漂** | 文档里的数量 | 一律现抓，不写死 | `gates/check_doc_numbers.py` |

> 两个入口**分工不同、不重复**：根 `AGENTS.md` 常驻（底线/命令/边界，~90 行）；
> 本文件按需加载（详细参考 + 流程）。

> 📌 **常驻规则在仓库根的 [`AGENTS.md`](../AGENTS.md)** —— 那份每次会话都会加载，
> 只有底线、命令与边界。本文件按需加载，装的是**详细参考与流程**。
> 两者分工不同，**不重复内容**。

---

## 先读哪一个

```bash
# ① 定位：grep 关键词拿行号与节标题（references/ 每篇 45~135 KB，别整篇读）
grep -n "include-all" references/profiles/clash.md
# ② 只读那一节：从命中行往上找最近标题，往下读到下一个同级标题（通常 2~5 KB）
```

| 你要做什么 | 读哪份 |
|:--|:--|
| 改某个配置键的语义与边界 | `references/profiles/{surge,egern,clash}.md` |
| DNS / 防泄露原理与三内核落地 | `references/dns.md` |
| 规则集选型、权重、跨内核差异 | `references/rulesets.md` |
| 排查拦截失效 / 分流异常 | `references/pitfalls.md` |
| 日常操作 / 发版 / 加固清单 | `references/ops.md` |
| 门禁判据与纪律（改判据前必读） | `references/gates.md` |

**每条配置键的权威解释，是它自己在 profile 里的注释** —— 文档讲的是
「跨键的机制与取舍」，不是注释的复述。改键之前先读那个键的注释。

---

## 目录

```
self-conf-skills/
  SKILL.md        本文件（技能入口，按需加载）
  references/     8 篇知识：profiles/* · dns · rulesets · pitfalls · ops · gates
  gates/          全部判据 + verify_all.py（唯一入口）· <kern>/ 各内核专属
                  （道数**现抓**：`verify_all.py --index | head -1`）
  run/            按需工具：生成 / 审计 / 探测 / 发布 · <kern>/
  lib/            共用模块（paths.py · _*_common.py）
```

**`gates/` 与 `run/` 的区别**（都是脚本，用途不同）：
`gates/` = 「要不要判负」的判据（跑一套就知道对不对）；
`run/` = 「帮我干活」的工具（生成物 / 审计报告 / 探测）。

---

## 改动的完整流程

```bash
# ① 改（注意哪侧是生成物，见仓库根 AGENTS.md 的「改动去哪」表）
# ② 同步派生文件
python self-conf-skills/run/make_min.py --apply            # 完整版 → .min
python self-conf-skills/run/clash/build_profiles.py        # my_clash*.js → profiles/*.yaml
python self-conf-skills/run/clash/build_rules.py           # rules/*.list → rules/*.yaml
# ③ 验证（唯一入口，与 CI 同源）
python self-conf-skills/gates/verify_all.py
```

**门禁绿了才算改完。** 退出码：0 = 全过 · 1 = 判负 · 2 = 环境不达标（先修环境）·
3 = 未验证（**不是绿**）。分界线：没读到远端真值 = 3；读到了但不过 = 1。

---

## 改判据时

先读 `references/gates.md` 的「新增闸门自查清单」。两条铁律：

1. **一道从不判红的闸门比没有更糟** —— 它给虚假的安全感。新判据必须**注错验证**过。
2. **注错要落在判据的扫描面上** —— 「改了没红」时，**先怀疑自己的注错**，
   再怀疑判据失灵（本仓已两次误判：改 GEOIP 而判据扫的是地区组正则；
   把 `[General]` 插进注释行而判据要求行首）。

本技能也提供 8 篇参考中的 `gates.md` 作为方法论（注错三铁律、判别力矩阵）。
