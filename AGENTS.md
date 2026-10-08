# self-conf · Agent 指南

Surge / Egern / mihomo（Clash Meta）**三内核代理配置模板**。
人类请看 [`README.md`](./README.md)；公开仓安全纪律见 [`SECURITY.md`](./SECURITY.md)。

> 本文件是 AI 操作手册的**唯一真源**——**任何 AI 工具都读这一份**。
> （`AGENTS.md` 是跨工具开放格式：Codex / Cursor / Copilot / Claude Code / Amp /
> Jules / Windsurf / Zed 等 20+ 工具原生支持。**不要**再建 `CLAUDE.md` /
> `.cursorrules` / `copilot-instructions.md` / `GEMINI.md` —— 工具专属入口会被
> **优先于** `AGENTS.md` 读取（Claude 有 `CLAUDE.md` 时只读它；Gemini CLI 默认只读
> `GEMINI.md`），那是第二份要同步的东西，且会屏蔽真源。本仓只留这一个入口。）
> ⚠️ `clash/` 有独立的生成链，**在那里工作时先读就近的 [`clash/AGENTS.md`](./clash/AGENTS.md)**。

---

## 命令

```bash
python self-conf-skills/gates/verify_all.py          # 门禁唯一入口（与 CI 同源）。绿了才算改完
python self-conf-skills/gates/verify_all.py -v       # 带详细输出
python self-conf-skills/gates/verify_all.py --index  # 列闸门清单（现抓，勿手抄）

python self-conf-skills/run/make_min.py --apply              # 改完完整版后同步 .min
python self-conf-skills/run/clash/build_profiles.py          # 改完 my_clash*.js 后重生成 mihomo profile
python self-conf-skills/run/clash/build_rules.py             # 改完 rules/*.list 后重生成 .yaml
python self-conf-skills/run/repo_state.py                    # 一屏现状：版本 / Release / CI
```

退出码：**0 = 全过 · 1 = 判负 · 2 = 环境不达标（先修环境，别读判据）· 3 = 未验证**。
⚠️ **3 不是绿**（显示 ⚠️，不计入 passed）。**没读到远端真值 = 3；读到了但不过 = 1。**

---

## 边界

**✅ 总是**
- 改完跑 `verify_all.py` —— **"我改对了"不算做完，门禁绿了才算**
- 改完整版后同步 `.min`（两份只差注释，内容必须逐字相同）
- 每条配置键的权威解释是**它自己在 profile 里的注释**（写满了理由）；改键前先读它

**⚠️ 先问**
- 改判据 / 加闸门（先说明「原判据错在哪」，再读 `self-conf-skills/references/gates.md` 的自查清单）
- 结构性调整（先补判据，不靠"再跑一遍"）

**🚫 从不**
- 手工编辑生成物：`rules/*.yaml`（改 `rules/*.list`）、
  `clash/profiles/*.yaml`（改 `clash/override/my_clash*.js`）、`*.min.*`（跑 `make_min.py --apply`）、
  **`rules/AI.list`**（改 `self-conf-skills/run/ai_sources/` 再跑 `ai_domains_build.py`）
- 为了「让门禁变绿」而改判据
- 把文档里写的数字当权威（组数/条数一律现抓）
- **把三内核「对齐」** —— 机制不同，看起来的不一致常是刻意的

---

## 改动去哪（**推不出来的部分**）

| 改什么 | 改哪个文件 | ⚠️ 易错 |
|:--|:--|:--|
| Surge 配置 | `surge/profiles/*.conf` | **不是**生成物，直接改 |
| Egern 配置 | `egern/profiles/*.yaml` | **不是**生成物，直接改 |
| mihomo 配置 | `clash/override/my_clash*.js` | ⚠️ **是**生成物 ⇒ 改 JS 再 build |
| 远程规则集内容 | `rules/*.list` | ⚠️ `.yaml` 是生成的 |
| **版本号** | ⚠️ **12 处头注**（见下） | 不是 6 处 —— 每份文件都有自己的头注 |

**五个生成链**（改左边，跑右边重生成）：

```
surge|egern/profiles/*.conf|yaml   ──make_min.py──▶        *.min.*
clash/override/my_clash*.js        ──build_profiles.py──▶  clash/profiles/*.yaml + *.min.yaml
rules/*.list                       ──build_rules.py──▶     rules/*.yaml
self-conf-skills/run/ai_sources/*  ──ai_domains_build.py──▶ rules/AI.list
```

⚠️ **`rules/AI.list` 也是生成物**（由 `ai_sources/` 里 10 个来源合并而成）——
改它要改 `self-conf-skills/run/ai_sources/` 下的源文件，再跑
`python self-conf-skills/run/ai_domains_build.py`。
（它的头部注释写明了生成脚本；`rules/*.yaml` 同理。）

⚠️ **版本头注是「生成物」的例外**：`clash/profiles/*.yaml` 虽由脚本生成，
但头注 `#! version=` **是脚本保留而非生成的** ⇒ **升版时要手改 clash 的 profile**
（只改 JS 不会改版本号）。升版共 **12 处**头注：
三内核 × 两产品线 × （完整版 + `.min`）。
Surge / Egern 改完整版后跑 `make_min.py --apply` 会同步 `.min`；
clash 的 `.min` 跑 `build_profiles.py` 时保留。

**三内核机制差异**（看起来不一致 ≠ 漂移）：地区组 Surge/Egern 用 `smart`、mihomo 用
`url-test`；订阅源前者是 external 组、后者是 `proxy-provider`；倍率分档 mihomo 的
**脚本做不到**（生成期看不到节点名）。`check_script_sync.py` 把这类列为**已知差异**，
打印提醒但不判负 —— **不要去"修"它**。

---

## 文档怎么读（**不要整篇读**）

`self-conf-skills/references/` 8 篇（合计数百 KB），**但有 880+ 个节**
（最大的一节也只有 ~5 KB）⇒ 按需 grep 定位到节，一次只读 2~5 KB：

```bash
# ① grep 拿行号与节标题 ② 只读那一节（从命中行往上找最近标题，往下读到下一个同级标题）
grep -n "include-all" self-conf-skills/references/profiles/clash.md
```

**关键词要选得具体** —— 泛词会命中几十处，具体词通常 1~5 处（下表的关键词都实测过）：

| 想问什么 | 去哪份 | 用这些词（都实测过命中数） |
|:--|:--|:--|
| mihomo 的组/节点怎么配 | `profiles/clash.md` | `include-all-proxies`(10) · `respect-rules`(7) · `nameserver-policy`(19) |
| Surge 的键怎么配 | `profiles/surge.md` | `policy-regex-filter`(4) · `extended-matching`(16) · `hijack-dns`(17) |
| Egern 的段怎么配 | `profiles/egern.md` | `policy_groups`(5) · `proxy_nameservers`(37) |
| DNS 泄露怎么查 | `dns.md` | `抓包`(1) · `假 IP`(10) · `引导`(11) |
| 规则集怎么选/多重 | `rulesets.md` | `重量`(4) · `体量`(5) · `刷新周期`(6) |
| 改完怎么验证 | `ops.md` | `make_min`(7) · `升号`(7) · `动线`(8) |
| 出问题 | `pitfalls.md` | `假通过`(3) · `广告拦不住`(4) · `拒绝加载`(6) |
| 门禁本身 | `gates.md` | `自查清单`(1) · `判别力`(15) · `注错`(15) |

⚠️ 若 grep 命中 >20 处 ⇒ 说明**关键词太泛**，换更具体的词（或先 grep 标题：
`grep -n "^#\{2,4\} " <file>` 看目录）。

---

## 一件事：本地全绿 ≠ 线上能跑

改动涉及**路径 / 编码 / 联网**时，**等 CI 结果**，别只看本地 —— 这三类历史上都栽过
（Linux 上路径探测算错目录；中文 Windows 管道 GBK 崩成退出码 1，而 1 恰是判负码）。

同理：闸门「跑了没红」时，**先怀疑自己的注错没落在判据的扫描面上**，再怀疑判据失灵。
