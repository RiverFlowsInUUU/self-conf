# 规则集体量与覆盖度 · 25 份 / 10 份的选型、权重与代价

> **何时读**：用户问「规则集是不是太多 / 太重」、要换掉或新增一份规则集、
> 想知道「为什么 AI 用了两份集」、或要判断某个远程集能不能用时。
>
> 本文只讨论**体量与覆盖度**：一份集有多大、接住了多少、漏了什么、代价是什么。
> `rule-providers` 的三种 `format × behavior` 组合与键语义见
> [`profile-anatomy.md`](profile-anatomy.md) §9；门禁命令与退出码见
> [`checker.md`](checker.md)；上游供应链评估见 [`public-repo.md`](public-repo.md) §9。
>
> **本文的中心结论**：规则集的"重量"不是条数，是**覆盖面与落点的正确性**。
> 本仓真实发生过的一次事故不是"集太大"，而是**一份 188 条的集漏了 94 条伴生域** ——
> 漏掉的那些请求从另一个出口出去，触发了风控（§3）。

## 0 · 目录

| # | 节 | # | 节 |
|:-:|:---|:-:|:---|
| 1 | 规模概览：25 份与 10 份 | 7 | 覆盖度实测：AI 组为什么用两份集 |
| 2 | 分流版 25 份清单表 | 8 | 自托管 vs 跨仓引用 |
| 3 | 懒人版 10 份清单表 | 9 | 生成链路与 `--check` 防过期 |
| 4 | 四类来源的分类 | 10 | 刷新周期与失效风险 |
| 5 | 为什么有的用 MRS、有的用 yaml | 11 | 体量的真实代价：内存与匹配 |
| 6 | 覆盖度是怎么量出来的 | 12 | FAQ · 维护者须知 |

---

## 1 · 规模概览：25 份与 10 份

两条产品线共用同一套规则集仓库，但**取用份数差一倍以上**：

| profile | 规则集份数 | 规则条数 | 策略组 | 生成源 |
|:--|:--:|:--:|:--:|:--|
| `clash/profiles/routing.yaml` | **25** | **27** | 25 | `override/my_clash.js` |
| `clash/profiles/lazy.yaml` | **10** | **11** | 3 | `override/my_clash_lazy.js` |

两份文件都由 `skill/scripts/clash/build_profiles.py` 生成，头注里的"规模"行
是脚本自动写的（"25 个策略组 / 25 份规则集 / 27 条规则"、"3 个策略组 / 10 份规则集 / 11 条规则"）。

⚠️ **份数与规则条数不相等**（25 vs 27、10 vs 11）。拆开看：

| profile | `rules` 总行数 | 其中 `RULE-SET` | 其中非规则集规则 |
|:--|:--:|:--:|:--|
| `routing.yaml` | 27 | **25** | 2（1 条 `DOMAIN-SUFFIX,music.youtube.com,YouTube Music` + 1 条 `MATCH,Proxy`） |
| `lazy.yaml` | 11 | **10** | 1（1 条 `MATCH,Proxy`） |

即 **`RULE-SET` 条数 = 规则集份数**（25 / 10），多出来的规则是不引用任何集的
`DOMAIN-SUFFIX` 直写规则与 `MATCH` 兜底。
本仓 25 份集**全部被引用**，没有"定义了但没用"的空集
（`rule-providers` 的键集合与 `RULE-SET` 引用的标识集合**完全相等**）。

**⇒ 判据：统计"规则集份数"应数 `rule-providers` 的键，或等价地数 `RULE-SET` 条数；
不要数 `rules` 的行数。** 用 `grep -c 'RULE-SET'` 在本仓是准的，
但它**不能**告诉你有多少份集 —— 如果将来两条规则引用同一份集（本仓目前没有），
这个等式就会失效。稳妥做法是数 `rule-providers` 的键。

⚠️ 另一个易错点：**两个 AI 集是两份集、两条规则，不是一份集被引用两次**。
`category-ai-chat-!cn` 与 `AI_Domains` 是两个不同的 provider，各自一条 `RULE-SET`，
所以它们既占 2 个 provider 键，也占 2 条 `RULE-SET`（§7 解释为什么需要两份）。

### 1.1 一个反复出现的头注错误

`lazy.yaml` 的头注曾写「5 份 MRS + 5 份 yaml」，实际是 **6 份 mrs + 4 份 yaml**
（见 [`profile-anatomy.md`](profile-anatomy.md) §18.4）。

**教训**：手写的规模描述一定会漂移。凡是可以由解析结果算出来的数字，
就让脚本写进头注，不要在注释里手抄。本文所有份数与条数均以
`yaml.safe_load` 解析为准。

---

## 2 · 分流版 25 份清单表

来源自 `clash/profiles/routing.yaml` 的 `rule-providers` 段（解析结果，非手抄）。
**刷新周期全部是 `interval: 86400`（24 小时）**，无一份例外。

### 2.1 MRS 格式（20 份 = MetaCubeX 19 + AWAvenue 1）

格式与处置方式相同，故列在一张表；**供应链归属不同**，见 §4。

| # | 名称 | behavior | format | 条目数 | 落点 |
|:-:|:--|:--|:--|:--|:--|
| 1 | `apple-update` | domain | mrs | 现抓 | Apple Update |
| 2 | `spotify` | domain | mrs | 现抓 | Spotify |
| 3 | `private` | domain | mrs | 现抓 | DIRECT |
| 4 | `anthropic` | domain | mrs | 现抓 | Claude |
| 5 | `category-ai-chat-!cn` | domain | mrs | **181 / 188** ⚠️ | AI |
| 6 | `github` | domain | mrs | 现抓 | Proxy |
| 7 | `youtube` | domain | mrs | 现抓 | YouTube |
| 8 | `google` | domain | mrs | 现抓 | Google |
| 9 | `microsoft` | domain | mrs | 现抓 | Microsoft |
| 10 | `apple-cn` | domain | mrs | 现抓 | DIRECT |
| 11 | `telegram` | domain | mrs | 现抓 | Telegram |
| 12 | `twitter` | domain | mrs | 现抓 | Twitter |
| 13 | `cn` | domain | mrs | 现抓 | DIRECT |
| 14 | `openai` | domain | mrs | 现抓 | ChatGPT |
| 15 | `google-gemini` | domain | mrs | 现抓 | Gemini |
| 16 | `geoip-private` | ipcidr | mrs | 现抓 | DIRECT `no-resolve` |
| 17 | `geoip-google` | ipcidr | mrs | 现抓 | Google |
| 18 | `geoip-telegram` | ipcidr | mrs | 现抓 | Telegram |
| 19 | `geoip-cn` | ipcidr | mrs | 现抓 | DIRECT |
| 20 | `AWAvenue-Ads` | domain | mrs | 现抓 | AD |

> 第 20 项 `AWAvenue-Ads` 的 URL 在 `TG-Twilight/AWAvenue-Ads-Rule` 仓下，
> 但历史上本仓把它与 MetaCubeX 一起归为"MRS 域名集"这一类讨论；
> 严格按来源分它是**第 4 类**（见 §4）。本表按"格式与 behavior 相同、处置方式相同"归类，
> 供应链归属以 §4 的表为准。

其中 16 份是 `mrs` + `domain`，4 份是 `mrs` + `ipcidr`。

### 2.2 本仓自托管 yaml（3 份）

| # | 名称 | behavior | format | 条目数 | 真源 | 落点 |
|:-:|:--|:--|:--|:--:|:--|:--|
| 21 | `emby` | classical | yaml | **4** | `rules/emby.list` | Emby |
| 22 | `AI_Domains` | classical | yaml | **272** | `rules/AI.list` | AI |
| 23 | `apple-system` | classical | yaml | **18** | `rules/apple_system.list` | DIRECT |

这 3 份的条目数是**确定的** —— 它们是本仓自己维护的静态文件，不随上游变化。

### 2.3 Jinx（2 份）

| # | 名称 | behavior | format | 条目数 | 落点 |
|:-:|:--|:--|:--|:--|:--|
| 24 | `Jinx-CN` | classical | yaml | 现抓 | DIRECT |
| 25 | `Jinx-Ads` | classical | yaml | 现抓 | AD |

三类合计 **20 + 3 + 2 = 25 份**，与 `rule-providers` 的键数一致。

### 2.4 关于"条目数"这一列的纪律

> ⚠️ **除本仓自托管的 3 份外，条目数一律不写死精确数字。**
> 这些集都没锁 commit（`cdn.jsdelivr.net/gh/...@meta`、`raw.githubusercontent.com/.../main`），
> 上游滚动更新，写死的数字很快过期 —— 这与 Surge 侧
> [`../surge/ruleset-weight.md`](../surge/ruleset-weight.md) §2.2 的口径一致。
>
> **唯一例外**是 §7 的覆盖度对比，那里的数字是**一次实测的结论**，
> 必须带日期与快照路径记录，因为它是论证的一部分，不是规模描述。

---

## 3 · 懒人版 10 份清单表

来源自 `clash/profiles/lazy.yaml`。刷新周期同样是**全部 `interval: 86400`**。

| # | 名称 | 来源 | behavior | format | 条目数 | 落点 |
|:-:|:--|:--|:--|:--|:--|:--|
| 1 | `private` | MetaCubeX | domain | mrs | 现抓 | DIRECT |
| 2 | `cn` | MetaCubeX | domain | mrs | 现抓 | DIRECT |
| 3 | `category-ai-chat-!cn` | MetaCubeX | domain | mrs | 181 / 188 ⚠️ | AI |
| 4 | `geoip-private` | MetaCubeX | ipcidr | mrs | 现抓 | DIRECT `no-resolve` |
| 5 | `geoip-cn` | MetaCubeX | ipcidr | mrs | 现抓 | DIRECT `no-resolve` |
| 6 | `AWAvenue-Ads` | AWAvenue | domain | mrs | 现抓 | AD |
| 7 | `Jinx-CN` | Jinx | classical | yaml | 现抓 | DIRECT |
| 8 | `Jinx-Ads` | Jinx | classical | yaml | 现抓 | AD |
| 9 | `AI_Domains` | 本仓 | classical | yaml | **272** | AI |
| 10 | `apple-system` | 本仓 | classical | yaml | **18** | DIRECT |

### 3.1 与分流版的差集（15 份）

懒人版砍掉的 15 份，按性质分三类：

| 类别 | 被砍的集 | 为什么可以砍 |
|:--|:--|:--|
| **地区/服务细分** | `apple-update` `spotify` `github` `youtube` `google` `microsoft` `apple-cn` `telegram` `twitter` `openai` `google-gemini` `anthropic` | 懒人版只有 3 个组（Proxy / AI / AD），没有对应的策略组可落；这些域落到 `MATCH,Proxy` 结果一样 |
| **IP 集** | `geoip-google` `geoip-telegram` | 同上，且没有 Google / Telegram 组 |
| **自托管小集** | `emby` | Emby 是自用枚举域名，属个人场景，不进极简版 |

⚠️ 注意 `geoip-cn` 的 `no-resolve` 在两份 profile 里**不一致**：
分流版是 `RULE-SET,geoip-cn,DIRECT`（**不带** `no-resolve`），
懒人版是 `RULE-SET,geoip-cn,DIRECT,no-resolve`（**带**）。
这是**已知差异**，不是笔误 —— 分流版前面还有 `cn`（域名集）与 `apple-cn` 先接住国内域名，
`geoip-cn` 主要兜 IP 直连场景；懒人版把 `cn` 排在它前面后，
`geoip-cn` 若不带 `no-resolve` 会对每个国内域名触发一次解析。
相关讨论见 [`leak-localization.md`](leak-localization.md)。

**⇒ 判据：删规则集时，要同时检查它后面那条规则的 `no-resolve` 是否还成立。**
砍掉一条规则会改变前序集合的构成，进而改变后续 IP 规则的行为。

---

## 4 · 四类来源的分类

| 类别 | 份数（分流版） | 格式 | 谁保证内容 | 供应链风险 |
|:--|:--:|:--|:--|:--|
| **MetaCubeX** `meta-rules-dat` | **19** | `mrs` | 上游每日重建 | 移动分支 `@meta`（不可钉 commit） |
| **本仓自托管** `rules/*.yaml` | **3** | `yaml` / classical | **本仓自己** | 无第三方依赖；失效即本仓事故 |
| **Jinx** `RiverFlowsInUUU/Jinx` | **2** | `yaml` / classical | 姊妹仓 | `main` 移动分支 |
| **AWAvenue** `TG-Twilight/AWAvenue-Ads-Rule` | **1** | `mrs` | 上游 | `main` 移动分支 |
| **合计** | **25** | | | |

⚠️ **"20 份 MRS" ≠ "20 份 MetaCubeX"** —— 这是本仓最容易混淆的一处。
严格拆分是 **MetaCubeX 19 份 + AWAvenue 1 份 = 20 份 MRS**。
§2.1 按"格式与 behavior 相同、处置方式相同"把两者列在一张表里讨论，
但**供应链归属以本表为准**：评估上游可用性、写事故报告时，`AWAvenue-Ads` 要单独算。

懒人版按同一口径拆：**MetaCubeX 5**（`private` `cn` `category-ai-chat-!cn`
`geoip-private` `geoip-cn`）+ **本仓 2**（`AI_Domains` `apple-system`）
+ **Jinx 2** + **AWAvenue 1** = **10 份**。

### 4.1 为什么"来源"这一维重要

因为它决定了**出问题时找谁**：

- `cn.mrs` 突然变空 → MetaCubeX 上游问题 → 只能等或换源；
- `AI_Domains.yaml` 404 → **本仓问题**（文件被删、仓改名、分支改名）→ 立刻可修；
- `Jinx-CN.yaml` 变空 → 姊妹仓问题 → 需要跨仓协调。

⇒ 判据：**自托管的 3 份是唯一"出事能自己修"的**。这也是 §8 的取舍基础。

---

## 5 · 为什么有的用 MRS、有的用 yaml

### 5.1 硬约束：`mrs` 只支持两种 behavior

`mrs`（Meta Rule Set）是**二进制容器**，里面只能装两类内容：

| behavior | 装什么 | 本仓份数 |
|:--|:--|:--:|
| `domain` | 纯域名集合（无类型前缀，全是裸域名/后缀） | 16 |
| `ipcidr` | 纯 CIDR 集合 | 4 |

**它装不下"带规则类型的行"** —— 也就是装不下 `DOMAIN-SUFFIX,xxx`、
`DOMAIN-KEYWORD,xxx`、`URL-REGEX,xxx` 这种**完整规则行**。

### 5.2 所以：classical 行为必须用 yaml

`behavior: classical` 的集合，每一条 payload 都是**一条完整的 mihomo 规则**
（`TYPE,value`），匹配时按整条规则求值。这类内容只能放在
`format: yaml`（或 `text`）里。

本仓 5 份 classical 集（`Jinx-CN` `Jinx-Ads` `emby` `AI_Domains` `apple-system`）
之所以必须是 yaml，**不是偏好，是内容决定的**：

| 集 | 为什么不能是 `domain` 集 |
|:--|:--|
| `AI_Domains` | 272 条里有 **39 条 `DOMAIN`、8 条 `DOMAIN-KEYWORD`、1 条 `URL-REGEX`** —— 关键字与正则在 `domain` 行为下就是一串永远匹配不上的字符 |
| `apple-system` | 18 条里 12 条 `DOMAIN` 精确匹配（如 `DOMAIN,mesu.apple.com`），`domain` 行为下会退化 |
| `emby` | 4 条全 `DOMAIN-SUFFIX` —— 理论可转，但纳入生成链路统一用 yaml 更省事 |
| `Jinx-*` | 上游本身就是 mihomo classical payload |

**⇒ 判据：先看 payload 的形态，再定 format。**
`domain` 集里混进一条 `DOMAIN-SUFFIX,xxx` 这样的完整规则行，
该行会被当成一个**域名字面量**（含逗号），永远匹配不上 ⇒ 该条静默失效。
反过来 `classical` 写成了 `domain`，整份集退化成空集 —— 且**不报错**。
（后果细节见 [`profile-anatomy.md`](profile-anatomy.md) §9.4。）

### 5.3 一张选型表

| 你的 payload 是 | 用 format | 用 behavior |
|:--|:--|:--|
| 纯域名/后缀列表（裸 `example.com`） | `mrs`（或 `text`/`yaml` + domain） | `domain` |
| 纯 CIDR 列表 | `mrs` | `ipcidr` |
| 完整规则行（`DOMAIN-SUFFIX,x` / `DOMAIN-KEYWORD,x` / `URL-REGEX,x`） | `yaml` / `text` | `classical` |

---

## 6 · 覆盖度是怎么量出来的

这是本文最需要说清的方法论。Surge 侧
[`../surge/ruleset-weight.md`](../surge/ruleset-weight.md) 的核心判据是
「**数域名条目，不是看名字**」；Egern 侧
[`../egern/ruleset-weight.md`](../egern/ruleset-weight.md) 是
「**按覆盖率判，绝不能按体积判**」。mihomo 侧沿用的是后者的思路，
但**量的对象不同**：不是"大表 vs 小表"，而是"**上游通用集 vs 本仓整合集**"。

### 6.1 三个层次的覆盖度

| 层次 | 问的问题 | 怎么量 |
|:--|:--|:--|
| **条目数** | 这份集有多少条 | 数 payload 行数 |
| **命中率** | 随机抽 N 个真实域名，命中几条 | 抽样对拍 |
| **差集** | A 集有、B 集没有的是哪些，那些是什么 | 求差集并**人工分类** |

⚠️ **只有第三层有意义。** 条目数会被冗余条目虚增（本仓 `AI.list` 就曾
318 → 286 → 272 两次归并，条目少了 46 条但**匹配行为零变化**，
见 `rules/AI.list` 头注"六修/七修"）；命中率会被抽样偏差带偏。
**差集 + 人工分类**才能回答"漏的是什么、后果是什么"。

### 6.2 求差集时必须做的两件事

**(1) 后缀感知地比，不要字符串相等地比。**

`DOMAIN-SUFFIX,clients6.google.com` 覆盖 `waa-pa.clients6.google.com`。
如果按字符串相等比，会得出"漏了"的错误结论。正确的比法是：
对每条值，枚举它的所有父后缀，看对方集合里有没有。

**(2) 先把两边的格式归一化。**

本仓 `rules/AI.list` 是 Surge ruleset 格式（`TYPE,value`）；
MetaCubeX 的 `category-ai-chat-!cn` 源自 v2ray domain-list 格式，
用的是 `+.example.com`（后缀）、`full:example.com`（精确）、
`keyword:xxx`、`regexp:xxx` 这套前缀。**直接按行比对会得到荒谬的结果**
（实测：朴素字符串相等只得出 28 条交集，后缀感知归一化后是 177 条）。

⇒ 判据：**跨格式比对前先归一化到 `(type, value)` 对，再按后缀语义求交/差。**

---

## 7 · 覆盖度实测：AI 组为什么用两份集

这是本仓**唯一一份同时引用两个 AI 规则集**的设计，也是本文的重点。

### 7.1 现象

`routing.yaml` 与 `lazy.yaml` 都有这两条相邻规则：

```yaml
  - RULE-SET,category-ai-chat-!cn,AI     # MetaCubeX，188 条
  - RULE-SET,AI_Domains,AI               # 本仓自托管，272 条
```

**两条都指向 `AI` 组。** 既然落点相同，为什么不是二选一？

因为**它们互相漏**，而且漏的方向不同。

### 7.2 实测（2026-10-01 快照对拍）

| 项 | 数值 |
|:--|:--|
| A = 本仓 `rules/AI.list`（→ `AI_Domains.yaml`） | **272 条**（其中 271 条域名类 + 1 条 `URL-REGEX`） |
| B = MetaCubeX `category-ai-chat-!cn` | **181 条**（本仓快照 `skill/scripts/ai_sources/meta-ai.list` 实测）/ **188 条**（历史记录值） |
| A ∩ B（B 能接住的 A 条目） | **177 条** |
| **A − B（B 漏掉的）** | **94 条** |
| B − A（A 漏掉的） | **4 条** |

> ⚠️ **181 vs 188 的差异**：188 是历史记录的读数，181 是本仓
> `skill/scripts/ai_sources/meta-ai.list` 快照的实测值（2026-10-01 抓取）。
> **该快照是上游的一次抓取，不随上游滚动更新**（`--check` 不覆盖它，见 §9.3）。
> 引用"188"时请注明它是历史值；要现数请重新抓
> `cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo/geosite/category-ai-chat-!cn.mrs`。
> 无论取 181 还是 188，**"漏掉 94 条"这个结论的量级不变**。

### 7.3 漏掉的 94 条是什么

**这是本节的关键。** 把它们按性质分类后，结论非常清楚：

| 类别 | 代表条目 | 条数量级 |
|:--|:--|:--|
| **认证 / 身份** | `auth0.com` `DOMAIN,oauth2.googleapis.com` `oauthaccountmanager.googleapis.com` `DOMAIN,account.jetbrains.com` `setup.workos.com` `cdn.workos.com` | ~10 |
| **遥测 / 特性开关 / 埋点** | `api.statsig.com` `statsigapi.net` `events.statsigapi.net` `launchdarkly.com` `featuregates.org` `segment.io` `in.appcenter.ms` `self.events.data.microsoft.com` `static.cloudflareinsights.com` | ~10 |
| **人机验证 / 风控** | `arkoselabs.com` `client-api.arkoselabs.com` `challenges.cloudflare.com` `identrust.com` | ~4 |
| **Google 通用 API 网关** | `apis.google.com` `clients4.google.com` `clients6.google.com` `play.googleapis.com` `googleusercontent.com` | ~6 |
| **AI 服务自有但上游未归类** | `DOMAIN-KEYWORD,-pa.googleapis.com`（一条封死整个动态命名空间）`jules.googleapis.com` `appcatalyst.pa.googleapis.com` `colab.google.com` `notebooklm.cloud.google.com` `antigravity.google.com` | ~15 |
| **Apple Intelligence / 私有中继** | `apple-relay.apple.com` `apple-relay.mask.apple-dns.net` `humb.apple.com` | 3 |
| **Bing / Copilot 面** | `www.bing.com` `sydney.bing.com` `r.bing.com` `edgeservices.bing.com` `services.bingapis.com` `assets.msn.com` `api.msn.com` `ai.azure.com` | ~12 |
| **Meta AI 面** | `facebook.com` `fbcdn.net` `connect.facebook.net` `atmeta.com` `meta.com` `llama.com` `llamameta.net` | ~7 |
| **AI 工具链** | `cursorvm.com` `zed.dev` `augmentcode.com` `chorus.sh` `udify.app` `algolia.net` | ~6 |
| **其他长尾** | `DOMAIN,api.github.com` `livekit.cloud` `muse.ai` `observeit.net` … | 余下 |

**⇒ 一句话总结：漏的主要是"伴生域"。**

**伴生域** = AI 服务本身不拥有、但 AI 请求**必须顺带访问**的第三方基础设施：
登录认证（auth0 / workos / OAuth 端点）、遥测埋点（statsig / launchdarkly / segment）、
人机验证（arkoselabs / challenges.cloudflare）、特性开关（featuregates）、
以及大厂内部共享的通用网关（`apis.google.com` / `clients6.google.com`）。

**为什么各家上游都不收它们？** 因为从分类学上，这些域**不属于任何一家 AI 服务**：

- `auth0.com` 是 Auth0 的，OpenAI 用它、Cursor 用它、无数非 AI 站也用它；
- `statsig.com` 是 Statsig 的，ChatGPT 用它做 A/B，别的产品也用；
- `apis.google.com` 是 Google 的通用 API 网关，不是"AI 专用"。

上游按"域属于谁"分类 ⇒ 这些域被归到"通用基础设施"或干脆不收。
但**用户实际发起的一次 AI 会话会真的去访问它们**。

### 7.4 漏掉伴生域的两个后果

**后果一：伴生请求漏出 AI 组。**

`RULE-SET,category-ai-chat-!cn,AI` 没接住 `auth0.com` ⇒ 该请求继续往下走，
最终落到 `MATCH,Proxy`（通用代理组）而不是 `AI` 组。
如果用户在 `AI` 组里选的是某个特定地区/特定倍率的节点，
**这次请求就走了另一个节点**。

**后果二：出口不一致触发风控。** ⚠️ 这是更严重的一条

一次 ChatGPT 会话里：

```
chatgpt.com          → AI 组   → 节点 A（出口 IP 1，地区 X）
auth0.com            → MATCH   → 节点 B（出口 IP 2，地区 Y）   ← 同一会话，不同出口
statsig.com          → MATCH   → 节点 B（出口 IP 2，地区 Y）
```

用户在 `AI` 组选了美西节点，但**登录请求从日本节点出去**。
对服务端的风控系统看，这是典型的"会话内 IP 漂移"信号 ——
**账号被要求重新验证、被限流、甚至被判为异常登录**。

⚠️ 注意这个后果的隐蔽性：**没有一条规则"错"**。
每条规则都按设计工作，配置能通过所有语法/结构门禁，
用户能正常打开网页 —— 只是**每隔一段时间就被踢下线一次**，
而且很难归因到规则集。

**⇒ 这就是"覆盖度"必须按差集+分类来量的原因：**
它不会表现为任何一条规则的错误，只表现为"一部分请求走了不该走的出口"。

### 7.5 那反过来呢：本仓 272 条漏了上游什么

**只有 4 条。** 这个方向的差集很小，原因是本仓 `AI.list` 的生成器
（`skill/scripts/ai_domains_build.py`）**把 MetaCubeX 当作 10 个上游源之一**
（源列表里的 `meta-ai.list`，标签 `MetaCubeX geosite category-ai-!cn`）。

也就是说：**272 条是"10 源整合"，181/188 条是"其中 1 源"。**
整合集覆盖单源，差集小是设计使然；单源覆盖不了整合集，差集大也是设计使然。

⚠️ **这不意味着"用大集就安全"。** 大集的条数里有一部分是冗余
（历史上 318 → 272 的两次归并就是消冗余），
而单源集里**有一些是整合集刻意剔除的**（黑名单，见 §7.6）。
两边都不是"全集"，所以 §7.2 的两个方向都要量。

### 7.6 272 条里被**刻意**剔除的

`ai_domains_build.py` 有两组黑名单，理解它们才能读懂差集：

| 黑名单 | 内容 | 剔除理由 |
|:--|:--|:--|
| `BLACKLIST`（宽后缀） | `amazonaws.com` `cloudflare.com` `wp.com` `imgix.net` `sentry.io` `stripe.com` `googleapis.com` `envato.com` 等 | 过宽的云/CDN/支付后缀，**误伤面巨大** |
| `BLACKLIST_EXACT`（点名主机） | `js.stripe.com` `o207216.ingest.sentry.io` `login.live.com` `login.microsoftonline.com` `copilot-reports.github.com` `origin-tracker.githubusercontent.com` 等 | 两类：通用基础设施的个别主机；**撞本仓其他分流规则的共享域** |

⚠️ **第二类的理由要特别注意**：`login.live.com` / `api.github.com` 这类域
被剔除是因为「AI 组排在 GitHub / 微软规则之前，收了会**静默改写这些域的出口**」。
`BLACKLIST_EXACT` 的注释明确写了：判据是**逐个主机**，不是后缀 ——
因为整域剔除会误杀 `challenges.cloudflare.com`（AI 服务人机验证，该收）与
`openaicom.imgix.net`（OpenAI 专属）。

**⇒ 覆盖度不是越大越好。** 收一条域的收益是"该域走对出口"，
代价是"所有用到该域的非 AI 请求也被拉进 AI 组"。
`googleapis.com` 宽后缀就是被这样否掉的：整域收编会把
`youtubei.googleapis.com`（YouTube App 核心 API）拉进 AI 组，
用户实测表现为 **IP 乱跳**。

---

## 8 · 自托管 vs 跨仓引用

### 8.1 本仓的选择：自托管（各存一份）

3 份自托管集（`emby` / `AI_Domains` / `apple-system`）的 URL 都指向本仓自己：

```
https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/rules/AI_Domains.yaml
https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/rules/apple_system.yaml
https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/rules/emby.yaml
```

而 Jinx 的 2 份指向姊妹仓：

```
https://raw.githubusercontent.com/RiverFlowsInUUU/Jinx/main/mihomo-direct.yaml
https://raw.githubusercontent.com/RiverFlowsInUUU/Jinx/main/mihomo-ads.yaml
```

**同样是 RiverFlowsInUUU 名下的仓，为什么一个自托管、一个跨仓引用？**

| | 自托管（`rules/`） | 跨仓引用（Jinx） |
|:--|:--|:--|
| 消费方 | **三内核共用**（Surge / Egern 吃 `.list`，mihomo 吃 `.yaml`） | 只有 mihomo 侧引用 |
| 是否要跨格式 | 是（`.list` ⇄ `.yaml`） | 否（上游已是 yaml payload） |
| 是否要人工过审 | 是（`AI.list` 有黑名单与归并规则） | 否（整份接收） |
| 更新频率 | 低（人工拍板） | 高（上游滚动） |

**⇒ 判据：需要跨内核共用、需要人工过审、更新频率低的 → 自托管；
单内核消费、整份接收、上游高频更新的 → 跨仓引用。**

### 8.2 自托管的代价：人工同步

这是本仓**明确接受**的代价：

> ⚠️ **外部仓库的同类资产更新后，本仓不会自动跟随** —— 自托管的代价是人工同步。
> 需要人工同步。

具体地：

- `rules/*.list` 是本仓的**唯一真源**；原仓的同名文件更新了，本仓**不知道**；
- `build_rules.py --check` 只检查「`.yaml` 是否落后于本仓的 `.list`」，
  **不检查「本仓的 `.list` 是否落后于原仓」**（它没法检查，原仓不在本仓视野内）；
- 因此同步动作是**人工的**：diff 两个仓的 `.list`，确认后手工合并，重跑生成器。

### 8.3 为什么还是选自托管

三条理由，按重要性排：

1. **可修性**（§4.1）。自托管的 3 份出事能自己立刻修；跨仓引用要等别人。
2. **单一真源**。`.list` 是三内核共用的真源，`.yaml` 是生成物 ——
   物理上不可能漂移。整合前两仓各存一份（内容逐条相同），
   **改一处忘一处就漂移**，这是合并最直接的收益。
3. **整合权**。`AI.list` 是 10 源整合 + 人工黑名单 + 归并的结果 ——
   这个加工过程**只能在自托管的形态下存在**。如果跨仓引用上游，
   就拿不到 §7.3 那 94 条伴生域，也做不了 §7.6 的剔除。

⚠️ **反过来，自托管不是万能的。** 它把"上游漂移"风险换成了"**没人同步**"风险。
一份 2026-09-24 手工快照的 `apple_system.list`（其内容源自 Surge 内置 `SYSTEM`），
在 Surge 大版本更新后就会落后 —— 文件头注里写明了这一点，
并规定了「Surge 大版本更新时人工比对一次」。
**自托管的集没有第三方刷新审计可依赖，必须自己记得。**

---

## 9 · 生成链路与 `--check` 防过期

### 9.1 链路

```text
rules/AI.list              ← 唯一真源（Surge ruleset 格式）
    │                         ↑ 由 skill/scripts/ai_domains_build.py 从
    │                           skill/scripts/ai_sources/ 的 10 份上游快照整合而来
    │
    ├─ Surge / Egern 直接消费（原生 .list）
    │
    └─ build_rules.py ──→ rules/AI_Domains.yaml   ← mihomo 消费（classical payload）

rules/apple_system.list ──→ rules/apple_system.yaml
rules/emby.list         ──→ rules/emby.yaml
```

`build_rules.py` 的 `TARGETS` 常量钉死了三对映射：

```python
TARGETS = [
    ("emby.list", "emby.yaml", "Emby 自用枚举域名 → Emby 组"),
    ("apple_system.list", "apple_system.yaml", "Apple 系统域 → DIRECT"),
    ("AI.list", "AI_Domains.yaml", "AI 伴生域 → AI 组"),
]
```

### 9.2 生成物是自证的

生成的 `.yaml` 头部写明了真源与条数：

```yaml
# AI_Domains.yaml
# ⚠️ 本文件由 build_rules.py **自动生成**，请勿手工编辑。
#    真源是同目录的 `AI.list`（共享于三内核），改内容请改真源后重跑：
#      python skill/scripts/clash/build_rules.py
#
# AI 伴生域 → AI 组
#
# 条数：272
# 格式：mihomo rule-provider（format: yaml / behavior: classical）
#
# ⚠️ 纯域名集、零 IP 条目 ⇒ 引用方**不写**规则级 no-resolve。
```

⚠️ 最后一行是**给引用方的关键提示**：这 3 份自托管集**零 IP 条目**，
所以在 `rules:` 里引用它们时**不需要**（也不应该）加 `no-resolve`。
这与 §3.1 讨论的 `geoip-*` 正好相反 —— `no-resolve` 只对 IP 类规则有意义。

### 9.3 `--check` 检查什么、不检查什么

```bash
python skill/scripts/clash/build_rules.py           # 生成
python skill/scripts/clash/build_rules.py --check   # CI 用：过期即判负（退出码 1）
```

它的机制是**逐字节比对**：把真源 `.list` 重新渲染一遍，
与磁盘上的 `.yaml` 全文比对，不同即判过期。

| 检查 | 覆盖 |
|:--|:--|
| `.yaml` 落后于本仓 `.list` | ✅ 覆盖 |
| `.yaml` 被手工编辑过 | ✅ 覆盖（与渲染结果不同） |
| `.yaml` 缺失 | ✅ 覆盖 |
| **本仓 `.list` 落后于原仓** | ❌ **不覆盖**（§8.2） |
| **本仓 `.list` 落后于上游 10 源** | ❌ **不覆盖**（`ai_sources/` 是快照，需人工重抓） |
| `.yaml` 内容**语义**是否正确 | ❌ 不覆盖（只比字节，不验语义） |

⚠️ 最后两行是这套门禁的**盲区**，必须靠人工流程补：

- `skill/scripts/ai_sources/` 里的 10 份快照（含 `meta-ai.list`）**不会自动刷新**。
  要更新得手工重抓上游，再跑 `ai_domains_build.py`。
  **⇒ 这也解释了 §7.2 里 181 与 188 的差异：快照停在 2026-10-01。**
- 语义正确性（黑名单是否合理、新收的域会不会误伤）**只能人工审**。
  `AI.list` 头注里的"一修/二修/…/七修"记录就是这套人工审计的留痕。

**⇒ 判据：`--check` 防的是"生成物过期"，不是"真源过期"。**
真源过期没有自动化防线，靠的是维护者记得跑一次上游 diff。

---

## 10 · 刷新周期与失效风险

### 10.1 现状：全部 86400

25 份（分流版）/ 10 份（懒人版）**无一例外**都是 `interval: 86400`（秒，= 24 小时）。

| 特性 | 值 | 含义 |
|:--|:--|:--|
| 单位 | 秒 | `86400` = 24 小时，**不是**毫秒也不是分钟 |
| 触发时机 | 内核启动 + 每 24 小时 | 不是"用到才刷" |
| 失败行为 | 保留旧缓存继续跑 | **不会**因为刷新失败就清空规则集 |

⚠️ 最后一条是**关键的安全阀**：如果上游挂了，mihomo 用上一份缓存继续工作，
而不是让整份集变空（变空意味着该集的规则全部失效 → 流量落到 `MATCH`）。
所以"上游 404"通常表现为**规则集静默变旧**，不是明显的断网。

### 10.2 86400 的实际风险

**风险一：新域要等最多一个周期。**

一个 AI 服务今天上线了新域名，最坏情况下要等 24 小时才被接住。
期间它走 `MATCH,Proxy` —— 也就是 §7.4 的"出口不一致"场景，只是范围更小。

**风险二：上游恶意/错误更新有 24 小时传播窗。**

`@meta` 与 `main` 都是**移动分支**，不可钉 commit（MRS 是二进制且走
jsDelivr 分支地址，没有 commit hash 可钉）。
上游一旦推了错误内容，本仓用户最多 24 小时内全部收到。
这是 [`public-repo.md`](public-repo.md) §9 供应链评估要覆盖的场景。

**风险三： Refresh 失败无告警。**

刷新失败不会弹窗、不会写显著日志。判断一份集是不是已经很旧，
要看 `rule_provider/` 目录下文件的 mtime。

### 10.3 为什么不再拉长

Surge 侧 [`../surge/ruleset-weight.md`](../surge/ruleset-weight.md) §5.3
提到「给远程集加 `update-interval` 拉长」可以减负，本仓**没有这么做**：

- mihomo 的 `interval` 只控制**刷新频率**，不影响内存与匹配开销（§11），
  拉长它**省不下任何可观测的资源**；
- 代价却是实打实的：新域等待时间变长。

**⇒ 判据：拉长 `interval` 只在"刷新本身造成可观测负担"时才划算
（极慢的网络、按流量计费的链路上）。**
本仓的 25 份集加起来是 MB 级（§11），一天一次不构成负担。

---

## 11 · 体量的真实代价：内存与匹配

这一节回答"25 份会不会太重"。结论直接引用 Egern 侧的实测
（同为原生内核、同一套匹配结构，结论可直接迁移）：

| 观察 | 实测 | 对本仓的含义 |
|:--|:--|:--|
| 稳态内存 | 域名条目 ≈ **130–175 B/条** | 本仓 25 份合计是 MB 级，**不是**几十 MB 级 |
| 加载时间 | 空配置 356 ms vs 加载 3.42 MB 355 ms | **加载时间与表规模无关** |
| 单次查询 | 0.36–0.69 µs；表从 1,000 → 111,332 条（111 倍），查询只从 0.36 → 0.69 µs | **匹配成本与表规模基本无关**（O(域名标签数)） |

**⇒ 三条结论：**

1. **25 份不是负担。** 唯一代价是常驻内存，而本仓的量级是 MB 级。
   （对比：Egern 侧单是 `ChinaMax_All_No_Resolve` 一份就是 111,332 条 / 3.42 MB / +22.6 MB。
   本仓 25 份加起来远不到这个量级 —— 因为本仓没有引入任何"国内域名全量表"。）
2. **不要为了"轻"而砍规则集。** 砍掉 `AI_Domains` 省下 272 条（约 40 KB），
   代价是 §7.4 的出口不一致。**这是一笔极坏的交换**。
3. ⚠️ **真正会变重的是"引入国内域名全量表"**。本仓目前用 `cn`（MetaCubeX 域名集）
   接国内域名，没有引入 ChinaMax 那种十万条目级的表。
   **如果将来有人提议"换更全的国内集"，那才是需要重新量内存的时刻。**

### 11.1 与 Surge 侧的口径差异

| | Surge 侧 | mihomo 侧 |
|:--|:--|:--|
| 主要风险 | 缺 `no-resolve` 的 **IP** 条目制造出口 ③ | 覆盖度不足导致的**出口不一致**（§7.4） |
| 承重墙 | `direct.txt`（十几万条域名） | `cn` + `Jinx-CN` + `geoip-cn` |
| 条数纪律 | 一律不写死 | 自托管 3 份写死，远程集不写死 |

⚠️ 差异的根源是**规则集构成不同**：Surge 侧的痛点是 IP 条目，
本仓 mihomo 侧的 25 份里只有 4 份是 `ipcidr`，且本仓 3 份自托管集**零 IP 条目**
（`AI.list` 生成器的纪律："零 IP 条目（防 DNS 泄露面）"）。
所以 IP 侧风险在本仓基本不存在，**覆盖度才是主要矛盾**。

---

## 12 · FAQ · 维护者须知

### 12.1 FAQ

**Q：25 份规则集太多了吧，能不能合并成几份？**

不能按"份数"合并。份数对应的是**落点**（策略组）与**来源**（供应链），
不是冗余。`category-ai-chat-!cn` 与 `AI_Domains` 都落 `AI` 组看似重复，
但 §7.2 实测显示前者漏 94 条 —— 合并（取并集）才是正确动作，
而取并集要跑生成器，不是手抄。

**Q：为什么 AI 要用两份集？只用 `AI_Domains`（272 条）不行吗？**

§7.5 显示反方向只漏 4 条。所以**理论上**只用 `AI_Domains` 覆盖度更高。
保留 `category-ai-chat-!cn` 的理由是**它滚动更新**：
`AI.list` 是 2026-10-01 的人工整合快照，上游新出的 AI 域要等人工同步；
MetaCubeX 那一份每 24 小时自动刷新，能接住"两次人工整合之间"新出现的域。
**⇒ 两份是"人工整合集 + 自动滚动集"的双保险，不是冗余。**

**Q：`mrs` 和 `yaml` 能不能互换？**

不能（§5）。`mrs` 只装 domain / ipcidr，装不下带类型的规则行。
凡是需要 `DOMAIN-KEYWORD` / `URL-REGEX` / 精确 `DOMAIN` 的集合，必须是 yaml + classical。

**Q：为什么 `AI_Domains.yaml` 里有一条 `URL-REGEX`？它会不会影响性能？**

272 条里 1 条。它是**不可预匹配**的类型（需在 HTTP 层求值），
但**不会触发 DNS 解析**，不参与 `no-resolve` 判据。
1 条不构成性能问题，Surge 侧
[`../surge/ruleset-weight.md`](../surge/ruleset-weight.md) §4 有同类说明。

**Q：我只改了 `rules/AI.list`，需要改三个内核吗？**

改真源即可，然后跑 `build_rules.py`。Surge / Egern 直接消费 `.list`，
mihomo 消费生成的 `.yaml`。**不要手工改两份** —— 见
[`branch.md`](branch.md) §13。

**Q：`--check` 通过了，是不是说明规则集是最新的？**

**不是。** `--check` 只证明"`.yaml` 没落后于本仓的 `.list`"（§9.3）。
它不检查：本仓 `.list` 是否落后于原仓、是否落后于那 10 份上游快照。
后者是**人工流程**，没有自动化防线。

**Q：能不能把 `interval` 改成 604800（一周）省点流量？**

技术上可以，但不划算（§10.3）：`interval` 不影响内存与匹配开销，
省不下可观测资源，代价是新域等待一周。
Surge 侧取一周是因为那里有具体理由，**本仓没有**，所以保持 86400。

**Q：`lazy.yaml` 头注说 5 份 MRS + 5 份 yaml，实际是 6 + 4，这是 bug 吗？**

是头注手写数字的漂移，已记录（[`profile-anatomy.md`](profile-anatomy.md) §18.4）。
规则集本身没错，错的是注释。**⇒ 凡可解析算出的数字，别手抄进注释。**

**Q：本仓 25 份会不会比 Egern 那份 111k 条的表还重？**

不会。Egern 侧单份 `ChinaMax_All_No_Resolve` 就是 111,332 条 / 3.42 MB / +22.6 MB；
本仓 25 份合计远不到这个量级 —— **本仓没有引入任何十万条目级的国内域名全量表**（§11）。

**Q：上游 404 了会怎样？**

不会断网。mihomo 刷新失败时**保留旧缓存继续跑**（§10.1），
所以表现为"规则集静默变旧"，需要看 `rule_provider/` 下文件的 mtime 才能发现。

### 12.2 维护者须知

1. **份数以解析结果为准**：数 `rule-providers` 的键，不要 `grep -c 'RULE-SET'`，
   也不要信手写的头注（§1.1）。
2. **条目数区别对待**：自托管 3 份（4 / 272 / 18）可以写死；
   远程集一律写"现抓"或带日期的实测值，**不写死**。
3. **跨格式比对先归一化**：`.list`（Surge `TYPE,value`）与 MetaCubeX
   （v2ray `+.` / `full:` / `keyword:`）必须归一化到 `(type,value)` 后再求交/差，
   且要比**后缀感知**（§6.2）。朴素字符串相等会得出荒谬结果（实测 28 vs 177）。
4. **覆盖度按差集+分类量**：不按条目数（会被冗余虚增），不按命中率（会被抽样带偏）。
   量完必须**人工分类**差集，才能回答"漏的后果是什么"（§6.1、§7.3）。
5. **伴生域是本仓的核心增量**：`AI.list` 相对上游的 94 条差集里，
   大部分是各家上游都不收的认证/遥测/风控域（§7.3）。
   删掉它们等于恢复"出口不一致触发风控"的故障 —— **不要为了"精简"删伴生域**。
6. **不要收过宽的域**：`googleapis.com` 宽后缀被否掉是因为会拉进
   `youtubei.googleapis.com`（实测 IP 乱跳）。收一条域前先问：
   **有没有非 AI 服务用它？**（§7.6）
7. **改 `.list` 后必须重跑生成器**：`build_rules.py`（无参数生成，`--check` 进 CI）。
   `.yaml` 是生成物，**禁止手工编辑**。
8. **真源过期没有自动防线**：`ai_sources/` 的 10 份快照不会自动刷新，
   原仓的 `.list` 也不会自动同步。定期人工 diff 一次并留痕（照 `AI.list` 头注"N 修"的格式）。
9. **先落样本再定 `behavior`**：不要照抄别人的配置（§5.2）。
   `domain` 集里混一条完整规则行 ⇒ 该条静默失效，且**不报错**。
10. **自托管集的 `no-resolve` 是反的**：3 份自托管 yaml **零 IP 条目**，
    引用它们时不加 `no-resolve`；`geoip-*` 才需要（§9.2）。
11. **砍规则集要连带检查后续规则的 `no-resolve`**：分流版与懒人版的
    `geoip-cn` 差异就是这么来的（§3.1）。
12. **引用历史数字要带出处**：`category-ai-chat-!cn` 的 188 是历史值、
    181 是 2026-10-01 快照实测值（§7.2）。两者混用会让后来的维护者以为上游缩表了。

---

相关：[`profile-anatomy.md`](profile-anatomy.md) §9 ·
[`checker.md`](checker.md) · [`leak-localization.md`](leak-localization.md) ·
[`public-repo.md`](public-repo.md) §9 · [`branch.md`](branch.md) ·
[`../surge/ruleset-weight.md`](../surge/ruleset-weight.md) ·
[`../egern/ruleset-weight.md`](../egern/ruleset-weight.md) ·
[`../../SKILL.md`](../../SKILL.md) · [`../../../README.md`](../../../README.md)
