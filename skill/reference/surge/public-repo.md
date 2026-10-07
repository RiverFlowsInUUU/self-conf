# 公开仓库的交付物与维护（Surge 侧）

> **何时读**：要更新模板、了解仓库结构或门面纪律时。

## 1 · 交付物清单

```
self-conf/
├── README.md                    # 门面（人类看的唯一文档）：订阅地址 / 组表 / 隐私对照 / AI 指路
├── LICENSE                      # MIT
├── .gitattributes · .gitignore
├── icons/                       # 图标 PNG + icons.json / icons-full.json —— 两内核共用
├── skill/                       # ★ AI 驱动的唯一知识库（无人类文档）
│   ├── SKILL.md                 # 单一入口：底线与纪律 → §0 判内核 → 分支 A(Surge) / 分支 B(Egern)
│   ├── reference/shared/        # 跨内核主题七篇：cross-kernel-diff · rulesets · hardening-checklist ·
│   │                            #   no-resolve-pairing · dns-basics · ops · troubleshoot-faq
│   ├── reference/{surge,egern}/ # 单侧主题：profile-anatomy（逐键权威）· hardening-template · pitfalls ·
│   │                            #   leak-localization · checker · ruleset-weight · public-repo（本文）
│   ├── scripts/{surge,egern}/   # 审计脚本（Surge 5+1 共享模块 / Egern 10+1 共享模块）
│   └── tests/                   # check_secrets · check_portability · check_min_pair · check_links · make_min
└── surge/                       ── Surge 全部产品物 ──
    ├── profiles/                # 顶层固定名四件 = 2 种分工 × 2 种形态（订阅地址永久不变）
    │   ├── lazy.conf            # 懒人版（带注释）—— 改这份
    │   ├── lazy.min.conf        # 懒人版（纯配置）—— 导入用
    │   ├── routing.conf         # 分流版（带注释）—— 改这份
    │   ├── routing.min.conf     # 分流版（纯配置）—— 导入用
    │   └── config_old/          # 历史归档（配置变动时按规则入档，只增不删）
    └── apple_system.list        # （在 egern/ 侧）本仓自托管的 Apple 系统域名规则集
```

> 原根级 `docs/`、两侧 `DetailsReadme/`、`CHANGELOG.md`、`skill/README.md` 已于 2026-09-27
> 全部并入 `skill/`（git 历史与备份 tag `pre-cleanup-20260927` 可查）。

### 1.1 各层的职责边界

| 层 | 装在什么 | **不装什么** |
|:---|:---------|:-------------|
| `README.md` | 能用起来所需的一切（产品结论） | 原理推导、逐行理由 |
| `skill/SKILL.md` | AI 的工作手册：底线、归档动线、审计清单、验收判据 | 逐键细节（下沉 reference） |
| `skill/reference/` | 机制推导、逐键语义、实测读数、已知取舍、FAQ、事故复盘 | 面向使用者的说明 |

⚠️ **不要把工作过程倒进产品文档。** 内部重构、仓库运维、行尾规范化 —— 使用者无感，
不进 README。改动历史看 git log（备份 tag：`pre-cleanup-20260927`）。

## 2 · README 门面纪律

README 是**产品介绍**：读者要知道「这东西是什么、怎么用」。已定下的规矩：

- 🚫 **只讲产品，不讲改动过程。**「为什么这样归类」「原写 X 属误标」这类话不进 README。
  实测反例（2026-09-22）：在组表下补一段 📌 解释「为什么这样归类」，用户一句打回 ——
  「readme 是产品介绍，不是自说自话的地方」。
- 🚫 **门面只写「得到什么」—— 标题里不出现「原理」二字。**
  功能清单写两列：「防的是什么 · 得到什么」。内核实现键（`fake-ip` / `dns-hijack`…）不进首页。
- 🚫 **首页不列规则集。**「`OpenAI.list` → `ChatGPT`」对读者没有意义；
  「AI 应用走 `AI` 组，面板上可改道」才有意义。规则集清单在 `reference/shared/rulesets.md`。
- 🚫 **三端（Surge / Egern / Clash）各写各的，不许互抄 DNS 防泄露的表述** ——
  机制不同，照抄等于把不存在的机制写进别人的仓。
- 📐 **清单类内容用列表不用表格**（GitHub 表格宽度不可控）；emoji 只放条目最前面，句中零个。
  ⚠️ **例外**：二维对应关系可用表格（首页「内核 × 产品线」的下载地址即此例，2026-10-01 改版）——
  但**长 URL 不进单元格**：单元格只放短文本链接、完整 URL 走链接目标。放裸 URL 会把表格撑宽、
  窄屏横向滚动，正是本条要避的情况。
- 📐 **相对链接必须能解析**；改标题后必须重算锚点并同步所有引用处
  （中文/emoji 标题的 GitHub 锚点规则见 git 历史里的 `skill/reference/surge/public-repo.md` §2.3）。

**自查**：README 里出现「为什么…」「不算」「误标」「判据」「原写」，八成是改动记录漏出来了。

## 3 · 文件组织

### 3.1 分工关系，不是版本关系

本仓库有**两份配置**：`lazy.conf`（懒人版）与 `routing.conf`（分流版）。
这是分工关系（基础款 / 进阶款），不是版本关系。选一份用，不要叠加。
想让你手头那份更轻，就在**它上面直接删**，不另开第三份。

### 3.2 两种形态

`.conf`（带注释，给人读）+ `.min.conf`（纯配置，导入用）。
**内容必须一致，只差注释** —— 由 `check_min_pair.py` 对拍兜底。
⚠️ `.min.conf` 里**必须保留 `# audit-waive:` 行** —— 那是有语义的注释。
`make_min.py` 按锚点把这类注释继承过去，`--apply` 写盘；不要手工同步 `.min`。

### 3.3 想加第三份配置的 6 条清单

**先问：这是新分工，还是老配置的另一种写法？** 后者不推荐（那是版本分叉）。
确认是新分工后，必须同时满足：

1. **DNS 段与 `lazy.conf` 逐字节一致**（跨配置断言 ②-c；若确实必须不同，要说明理由并改测试）
2. 规则顺序符合铁律：白名单 → 黑名单 → 常规分流
3. `FINAL` 之前有域名体量足够的国内直连规则集
4. 所有 IP 类规则带 `no-resolve`
5. 节点全部占位化（`203.0.113.x` + `REPLACE_WITH_*`），订阅 token 用 `REPLACE_WITH_YOUR_TOKEN`
6. 若有豁免，`# audit-waive:` 写在文件里

**能过测试的才叫一份新配置，否则只是一个改坏了的副本。**

## 4 · 脱敏规则（公开模板的底线）

| 字段 | 占位形式 |
|:-----|:---------|
| 节点 IP | RFC 5737 文档段：`192.0.2.0/24` / `198.51.100.0/24` / `203.0.113.0/24` |
| 中转域名 | `cdn-relay.example.com`（RFC 2606 保留域） |
| 密码 / 用户名 | `REPLACE_WITH_YOUR_PASSWORD` / `REPLACE_WITH_USERNAME` |
| SNI | `REPLACE_WITH_YOUR_SNI` 或与 server 相同 |
| 订阅 URL（含 token） | `REPLACE_WITH_YOUR_TOKEN` |

### 4.1 push 前必跑

```bash
python skill/tests/check_secrets.py        # 占位符纪律（全仓 .conf + .yaml）
```

它会拦住：非文档段 IPv4（真实节点 IP）、非 `REPLACE_WITH_*` 的凭据、
不在允许清单的节点主机名、若干禁止出现的敏感子串（**注释里也不许出现**）。

### 4.2 全仓扫描（补一道）

`check_secrets.py` 只认 `.conf` / `.yaml` —— markdown 与 Python 需另扫：

```bash
grep -rn -iE '<你的私有域名|你的密码片段|你的用户名>' . \
  --exclude-dir=.git --exclude-dir=icons
```

> ⚠️ 不要用 `grep -rn 'github'` 这类宽泛关键词 —— 规则集 URL 全含
> `githubusercontent`，几百条假阳性会淹没真命中。

## 5 · 验证

CI（根 `.github/workflows/ci.yml`）在 push / PR 自动跑：占位符扫描 → 可移植性 → `.min` 对拍 →
链接锚点 → 两侧 DNS 审计 → `.min` 漂移检查。本地同组命令见 [`SKILL.md`](../../SKILL.md) §3 动线第 ⑤ 步。

### 5.1 改 markdown 版式前：先问 GitHub 本人

README（及任何 GitHub 渲染的 markdown）的**最终长相由 GitHub 的渲染管线决定，不由本地预览决定**：
本地预览有完整 CSS 自由，GitHub 却会**剥掉 `style` 属性**、丢弃废弃属性 —— 两者"能做/不能做"的
边界不同，凭本地预览判断版式，会把真机上办不到的效果当成可行（2026-10-01 实测踩过）。

推送前用 GitHub 自己的渲染接口拿真机答案：

```bash
MSYS_NO_PATHCONV=1 gh api --method POST /markdown \
  -f mode=gfm \
  -f context=RiverFlowsInUUU/self-conf \
  -f text='| | <div align="center">Surge</div> | <div align="center">Egern</div> |
|:--|:------|:------|'
```

输出即 **GitHub 渲染后的 HTML**，一眼看出某写法保不保留。实证：

- `<th align="left"><div align="center" dir="auto">Surge</div></th>` ⇒ `div` 与 `align` **被保留**
  （对比 `style` 会被剥）；同表体仍是 `<td align="left">` ⇒ 「只居中表头、不动表体」可行。
- ⚠️ Git Bash 下漏了 `MSYS_NO_PATHCONV=1`，`/markdown` 会被当文件路径改写、报 `invalid API endpoint`。

> ⚠️ 表头居中只能给单元格包 `<div align="center">`；**不能**改用列对齐 `:--:` —— 它按列生效，
> 会把表体的长句一并居中（取向见 §2「清单类内容用列表不用表格」）。

## 6 · 这个仓库最容易被改坏的地方

按风险排序：

| # | 位置 | 改坏的症状 | 守它的东西 |
|:-:|:-----|:-----------|:-----------|
| 1 | `[Proxy]` 段的节点（填成真实值） | 隐私泄露 | `check_secrets.py` |
| 2 | `[Rule]` 的顺序（`direct.txt` 挪到 REJECT 前） | 广告拦截失效 | 人工核对 + `check_surge_dns.py` 第 9 项 |
| 3 | IP 类规则的 `no-resolve`（删掉） | DNS 泄露 | `check_surge_dns.py` 第 12 项 |
| 4 | 只改 `.conf` 或只改 `.min.conf` | 两份行为不一致 | `check_min_pair.py` |
| 5 | `pre-matching` 的策略（改成策略组） | **Surge 拒绝加载** | `check_10` |
| 6 | `underlying-proxy` 指向的名字 | **Surge 拒绝加载** | `check_7` |
| 7 | `# audit-waive:` 行（删掉） | 从 2 waived 变 2 high | 无（靠"知道它是有语义的"） |

> ⚠️ 第 4 条的覆盖是部分的：`check_min_pair.py` 对拍整份去注释正文，
> `.min.conf` 里其余部分（规则、组、节点）改歪了不会被拦住。
> 第 7 条完全没有自动化覆盖。这两条是**已知的测试盲区**，靠纪律补：改配置时两份一起改。
