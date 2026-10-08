# 规则集 · 选型、权重与跨内核差异



## 🚀 新增一份规则集：完整步骤（**照这个做**）

> 2026-10-08 补：此前文档反复说「加规则集之前读本篇」，但本篇是**选型知识库**，
> 不是 SOP —— 用「全新 AI 实测」发现新手要跨 5+ 处自己拼步骤。现补成清单。

```bash
# ① 定体系：这份规则集给哪个（些）内核用？
#    Surge / Egern → 远程 .list/.txt 或自托管 rules/*.list
#    mihomo        → .mrs 或 .yaml（见「为什么 mihomo 那份是 .mrs」）
#    三内核都要用   → 优先自托管（见「本仓的选择：自托管」）

# ② 定落点：挂到哪个策略组？
#    看「匹配顺序（Surge / Egern 基准序）」—— 应用规则在国内直连之前，IP 类排最后
#    新规则集要不要**新建策略组**？—— 见「排序与选材约束」

# ③ 改配置（⚠️ 注意哪侧是生成物，见根 AGENTS.md）
#    Surge   → surge/profiles/routing.conf   [Rule] 段加 RULE-SET,<url>,<策略>
#    Egern   → egern/profiles/routing.yaml   rules: 加 rule_set: 条目
#    mihomo  → clash/override/my_clash.js    rule-providers + rules（改 JS！）

# ④ 同步派生
python self-conf-skills/run/make_min.py --apply         # Surge/Egern 的 .min
python self-conf-skills/run/clash/build_profiles.py     # mihomo 的 profile
#    自托管清单：改 rules/*.list 后（自托管判据见「本仓的选择：自托管」）
python self-conf-skills/run/clash/build_rules.py        # 生成 rules/*.yaml

# ⑤ ⚠️ 登记到文档表（**隐藏的强制点**，不做会判负且报错难懂）
#    改 self-conf-skills/references/profiles/clash.md 的「全部规则集」表
#    判据：gates/clash/check_ruleset_doc_sync.py

# ⑥ 验证
python self-conf-skills/gates/verify_all.py
```

### 会被哪些判据拦（逐个知道就不慌）

| 判据 | 拦什么 |
|:--|:--|
| `gates/clash/check_ruleset_doc_sync.py` | 配置里的 URL **必须**在文档表登记（反之亦然） |
| `gates/clash/check_remote_urls.py` | 远程 URL 必须可达（慢，联网） |
| `gates/check_priority_weight.py` | 规则顺序 / 权重口径 |
| `gates/{surge,egern}/audit_ruleset_*.py` | 含 IP 条目的规则集必须带 `no-resolve` |
| `gates/*/audit_routing_coverage.py` | 应用段「组顺序 ↔ 规则顺序」不许乱序 |

### 自托管 vs 跨仓引用（§8.1 的判据）

- **自托管**（放 `rules/*.list`）：需跨内核共用、要人工过审、低频更新
- **跨仓引用**：单内核消费、整份接收、高频更新（上游自己维护）

⚠️ 自托管清单改完要跑 `build_rules.py` 生成 `rules/*.yaml`；
`rules/AI.list` 由 `run/ai_domains_build.py` 从 `run/ai_sources/` 合并生成。


## 规则集与来源

> 这一页是组件清单：用了哪些规则集、各自从哪来、按什么顺序生效。
> **三内核（Surge / Egern / mihomo）共用的是分流意图，不是规则集文件** —— 分工见 §0。
> 条数一律现抓（本仓纪律：写死的数字必然过期）：
> **Egern 独有 2 项** —— `Lan.list` 与 `apple_system.list`，各用来补 Surge 的一个内置集合（内置 `LAN` / `SYSTEM`），
> 这是 Surge / Egern 两内核引用 URL **不逐字相同**的唯一原因（其余全部相同）。
>
> 引用位口径（数的是 `rules` 段里指向规则集的条目，同一份规则集被两条规则各引用一次就占两位）：
> Surge / Egern 分流版 **<!-- auto:ruleset-refs -->24<!-- /auto:ruleset-refs --> 条规则集引用**。
> 懒人版 **9 条规则集引用**。
> 这两个数以本文件与两侧 profile 的现算为准，别混。
> ⚠️ mihomo 侧**另有一套文件、另算一套数**（§5）：分流版 25 份 / 懒人版 10 份。
> 它与上面的 24 / 9 **不是同一个口径，不要相加、也不要对拍**。
>
> 三个内核各自的规则集清单与体量分析，见各自的专文：
> [`rulesets.md`](./rulesets.md) ·
> [`rulesets.md`](./rulesets.md) ·
> [`rulesets.md`](./rulesets.md)（mihomo）。
> 本页只做**三内核对照与共用真源**这一层，不重复那份清单。

### 0 · 先分清一件最重要的事：共用的是「内容」，不是「文件」

这是三内核整合仓最容易误判的一处。三个内核引用规则集的方式**分属两套文件体系**：

| | Surge | Egern | mihomo（clash） |
|:--|:--|:--|:--|
| 规则集文件形态 | `.list` / `.txt`（**Surge 原生文本**） | 同左（可直接消费 Surge 格式） | **`.mrs`（MetaCubeX 二进制，分流版 20 份）+ `.yaml`（5 份）** |
| URL 写在哪 | 直接写在 `RULE-SET,<URL>,<策略>` | `rule_set.match` | 先在 `rule-providers` 声明名字 / `format` / `behavior` / `path` / `interval`，规则里**按名字**引用 |
| 条数纪律 | 一律不写死 | 一律不写死 | 自托管 3 份可写死（本仓静态文件），远程集不写死 |

⇒ **把 `.list` 的 URL 直接塞进 mihomo 的 `RULE-SET` 名字位是错的**；
反过来把 `.mrs` 给 Surge 也读不动。**三内核共享的是"要接住哪些域名、按什么顺序接"这个语义层。**

#### 0.1 唯一的例外：三内核真正共用的那 3 份

本仓自托管的 `rules/*.list` 是**唯一真源**，三个内核都吃它 —— 但**吃的不是同一份文件**：

```text
rules/AI.list             （272 条 —— 条数以该文件头注「合计」行为唯一真源）
rules/apple_system.list   （18 条）
rules/emby.list           （4 条）
   │
   ├─ Surge  ── 直接消费 .list（原生）
   ├─ Egern  ── 直接消费 .list（原生）
   └─ mihomo ── 由 self-conf-skills/run/clash/build_rules.py 生成 .yaml 后再消费
```

```bash
python self-conf-skills/run/clash/build_rules.py           # 生成
python self-conf-skills/run/clash/build_rules.py --check   # CI 用：过期即判负
```

`.yaml` 是**生成物**，禁止手工编辑（改真源 `.list` 后重跑）。
整合前两仓各存一份（内容逐条相同）⇒ 改一处忘一处就漂移；单一真源后物理上不可能漂移。

> 📌 `rules/AI_Domains.yaml` / `apple_system.yaml` / `emby.yaml` 的头部都写着真源名与条数，
> 且标注「纯域名集、零 IP 条目 ⇒ 引用方**不写**规则级 `no-resolve`」—— 这条提示对三内核都成立。

#### 0.2 为什么 mihomo 那份是 `.mrs` 而不是 `.list`

`.mrs`（Meta Rule Set）是**二进制容器**，zstd 压缩，**只能装两类内容**：

| `behavior` | 装什么 | 本仓份数（分流版） |
|:--|:--|:--:|
| `domain` | 纯域名集合（裸域名 / 后缀，**不带类型前缀**） | 16 |
| `ipcidr` | 纯 CIDR 集合 | 4 |

它**装不下 `DOMAIN-SUFFIX,xxx` 这种完整规则行**。所以凡是 payload 是完整规则行的集合
（本仓的 `AI_Domains` / `apple-system` / `emby`、以及 Jinx 的 2 份）**必须**是
`format: yaml` + `behavior: classical` —— 不是偏好，是内容决定的。

⚠️ 判据：**先落样本看 payload 形态，再定 `format` / `behavior`**。
`domain` 集里混进一条 `DOMAIN-SUFFIX,xxx`，该行会被当成**一个含逗号的域名字面量**，
永远匹配不上且不报错；`classical` 写成 `domain` 则整份集退化成空集。

（mihomo 侧 `format × behavior` 的三种组合与键语义，见
[`clash.md`](./profiles/clash.md) §9。）

### 1 · Surge / Egern 共用规则集

两侧都是 **Surge 原生 `.list` / `.txt` 格式**，由客户端自行下载与缓存。
Egern 的规则集**内联在 `rules` 段的 `rule_set` 条目里**，没有独立 `rule_sets` 段。
`update-interval=604800` / `update_interval: 604800` 表示**一周**刷新，本仓两侧全部远程规则集都显式带着它。
两侧都要显式写，但**理由并不相同**：Surge 手册写明该键缺省即 `86400`（24 小时），**只有写负值才关掉自动更新** ⇒ 不写也会刷新，显式写是为了「刷新节奏可见、可统一」；Egern 只在 `rule_set` 示例里出现过这个字段、**未文档化缺省值** ⇒ 不写就是行为不可知，必须钉死。

| 规则集 | 作用 | Surge 去向 | Egern 去向 | 来源 |
|:-------|:-----|:-----------|:-----------|:-----|
| `surge-direct.list` | 白名单（精确域名） | `DIRECT` | `DIRECT` | [Jinx](https://github.com/RiverFlowsInUUU/Jinx) |
| `surge-ads.list` | 广告拦截主清单 | `REJECT`（`pre-matching`） | `AD` 组 | [Jinx](https://github.com/RiverFlowsInUUU/Jinx) |
| `AWAvenue-Ads-Rule-Surge-RULE-SET.list` | 广告拦截第 2 条 | `REJECT`（`pre-matching`） | `AD` 组 | [TG-Twilight/AWAvenue-Ads-Rule](https://github.com/TG-Twilight/AWAvenue-Ads-Rule) |
| `SystemOTA.list` | Apple 系统更新（OTA） | `Apple Update` 组 | `Apple Update` 组 | [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)（**仅分流版引用**） |
| `private.txt` | 特殊 TLD 与路由器域（`.lan` `.local` `miwifi.com`） | `DIRECT`（实测零 IP ⇒ 不写规则级开关） | `DIRECT`（分流版 v3 起补） | [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules) |
| `direct.txt` | 国内域名（纯域名、零 IP；**条数一律现抓**）**主承重墙** | `DIRECT`（同上，不写开关） | `DIRECT` | [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules) |
| `OpenAI.list` | → `ChatGPT` | ✅ | ✅ | [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) |
| `Gemini.list` | → `Gemini` | ✅ | ✅ | 同上 |
| `Anthropic.list` · `Claude.list` | → `Claude` | ✅ | ✅ | 同上 |
| `AI.list` | → `AI`（通用 AI，必须排在上面三条**之后**） | ✅ | ✅ | [Repcz/Tool](https://github.com/Repcz/Tool)（分支头 · 活跃维护；2026-09-28 自 ACL4SSR 换入） |
| `AI_Domains`（本仓自托管） | → `AI`（伴生域/宽后缀/基础设施域，**必须紧跟 `AI.list`**） | ✅ | ✅ | 本仓 `rules/AI.list`（静态整合 · 生成器 `self-conf-skills/run/ai_domains_build.py`；条数与来源见该文件头部档案） |
| `Spotify.list` · `YouTubeMusic.list` · `YouTube.list` | 各自应用组 | ✅ | ✅ | [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) |
| `GitHub.list` | → **`Proxy` 直指**（2026-10-05 起不再单设 `GitHub` 组） | ✅ | ✅ | 同上 |
| `Google.list` · `Microsoft.list` | 各自应用组 | ✅ | ✅ | 同上 |
| `Telegram.list` · `Twitter.list` | 各自应用组 | ✅ | ✅ | 同上 |
| `apple.txt` | Apple 在中国大陆可直连的域名 → `DIRECT` | ✅ 仅分流版 | ✅ 仅分流版 | [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules)，与 `direct.txt` **同仓库同 release 同格式**。**纯域名、零 IP**（条数随上游更新，一律现抓）⇒ 不写规则级开关（第 4 节 4b）。懒人版 2026-09-24 起不引用只留内置 `SYSTEM`；分流版 2026-10-04 起由 `Apple_All_No_Resolve.list`（1,616 条）换入 |
| `Proxy.list` | 常用代理名单 | 注释态，不参与匹配 | 注释态，不参与匹配（2026-09-24 起与 Surge 同写法；原先是 `disabled: true`，那条仍占 `rules` 的一位） | 同上 |
| `GEOIP,CN` / `geoip: CN` | 国内 IP 段 | `DIRECT` `no-resolve` | `DIRECT` `no_resolve` | Surge：`GeoLite2-Country.mmdb` · [adysec/IP_database](https://github.com/adysec/IP_database)；Egern：`Country.mmdb` + `GeoLite2-ASN.mmdb` · [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) |

### 2 · 只有一侧有的（Surge / Egern 之间）

| 规则集 | 只在哪侧 | 原因 |
|:-------|:---------|:-----|
| `LAN`（内置） | 仅 Surge | Surge 有内置局域网规则集 |
| `Lan.list` | 仅 Egern | Egern 无内置 LAN，引用 [blackmatrix7](https://github.com/blackmatrix7/ios_rule_script) 的清单补位。与 `private.txt` **互补**：`Lan` 管 IP 段与路由管理域，`private` 管特殊 TLD 与 `miwifi.com` |
| `SYSTEM`（内置）→ 快照 `apple_system.list` | Surge 内置 ／ Egern 引用快照 | 系统服务 → `DIRECT`。2026-09-24 起两侧同一位置各有一套：Egern 没有内置系统集，引用 [`../rules/apple_system.list`](../../rules/apple_system.list)（2026-09-27 起自 `egern/` 根提升到顶层 `rules/`，两侧文件夹布局就此对称）—— 内容 = 内置 `SYSTEM` 的 2026-09-24 时点快照，删掉 Egern 不支持的两条 `PROCESS-NAME`（`trustd` / `netbiosd`） |
| ~~`domain_suffix: cn`~~ | 两侧均已删除 | 2026-09-24 懒人版也删了。理由与分流版 v3 同：`direct.txt` 本身含 `DOMAIN-SUFFIX,cn`（2026-09-24 快照第 23,829 行），留着只会把「规则集没接住」掩盖成「cn 直连正常」 |

✅ **懒人版两侧现已逐位同构**：各 10 条，白名单 → 广告 ×2 → 内网 ×2 → 系统集 → AI → 国内直连 → 地理 → 兜底。
剩余差异只剩写法与内核能力：广告策略（Surge 字面量 `REJECT` ／ Egern `AD` 组）、内置 `LAN` ↔ `Lan.list`、
内置 `SYSTEM` ↔ 本仓快照、`FINAL` ↔ `default`。Apple 全量集与 `.cn` 后缀兜底两侧现在**都没有**。
逐项差异见 [`rulesets.md`](./rulesets.md) 第 4 节。

### 3 · 匹配顺序（Surge / Egern 基准序）

自上而下，第一条命中即决定去向。分流版两侧 26 条**逐位对齐**（仅第 3 节的三处引擎差异例外）。
⚠️ 本节是 **Surge / Egern 的基准序**；mihomo 分流版是 **27 条**、另一套顺序，见 §5.1 与
[`rulesets.md`](./rulesets.md) §3。

**分流版（两侧共用基准序，位 ①–㉖，共 26 条）**

⭐ **应用段顺序与 `[Proxy Group]` 同名组的先后保持一致**（2026-10-05 立，由两内核
`audit_routing_coverage.py` 的 **Z0** 检查守）。
⚠️ **但规则可被「前移」，且这是必要的**：当某规则集**包含**另一集的条目时，被包含者必须前置，
否则永远轮不到它。两处实例（均由 Z0 按「允许前移、不许乱序」处理）：
  · `YouTube.list`（190 条）**内含** `YouTubeMusic.list` 的 UA 规则（`USER-AGENT,*YouTubeMusic*` 等）
    ⇒ `YouTubeMusic.list` 必须排在 `YouTube.list` 之前，而它的组在面板上排在 `YouTube` 之后；
  · `SystemOTA.list` 与 `SYSTEM` 有 **3 条重叠**（`configuration.apple.com` / `mesu.apple.com` / `xp.apple.com`）
    ⇒ 位 ④ 的 `SystemOTA` 必须排在位 ⑤ 的 `SYSTEM` 之前，否则那 3 条永远被 `SYSTEM` 接走。

| 位 | 内容 | 位 | 内容 |
|:-:|:-----|:-:|:-----|
| ① | 广告白名单 `surge-direct.list` → `DIRECT` | ⑭ | `YouTubeMusic.list` → `YouTube Music` |
| ② | 广告拦截 `surge-ads.list` → `REJECT`(S) / `AD`(E) | ⑮ | `GitHub.list` → **`Proxy`**（无同名组） |
| ③ | 广告拦截 `AWAvenue-Ads-Rule-...list` → `REJECT`(S) / `AD`(E) | ⑯ | `YouTube.list` → `YouTube` |
| ④ | `SystemOTA.list` → `Apple Update` | ⑰ | `emby.list`（**本仓自托管**）→ `Emby` |
| ⑤ | **系统域白名单**：Surge 内置 `SYSTEM` ／ Egern `apple_system.list` → `DIRECT` | ⑱ | `Google.list` → `Google` |
| ⑥ | 内网 `LAN`（Surge 内置）／ `Lan.list` → `DIRECT` | ⑲ | `Telegram.list` → `Telegram` |
| ⑦ | 内网 `private.txt` → `DIRECT` | ⑳ | `Spotify.list` → `Spotify` |
| ⑧ | 厂商专属 `OpenAI.list` → `ChatGPT` | ㉑ | `Twitter.list` → `Twitter` |
| ⑨ | 厂商专属 `Gemini.list` → `Gemini` | ㉒ | `Microsoft.list` → `Microsoft` |
| ⑩ | 厂商专属 `Anthropic.list` → `Claude` | ㉓ | `apple.txt` → `DIRECT` |
| ⑪ | 厂商专属 `Claude.list` → `Claude` | ㉔ | `direct.txt` → `DIRECT` |
| ⑫ | `AI.list`（Repcz）→ `AI` | ㉕ | `GEOIP,CN` → `DIRECT` |
| ⑬ | `AI.list`（**本仓自托管**）→ `AI` | ㉖ | `FINAL` → `Proxy` |

**懒人版**：两侧各 **11 条**、逐位同构。段序同上表把「应用段」收缩成一条 `AI` 的形态，
且**不含位 ④ `SystemOTA`**（`Apple Update` 组仅分流版有），即：
广告白名单 → 两条广告 → `SYSTEM` → `LAN` · `private` → `AI.list` ×2 → `direct.txt` → `GEOIP,CN` → `FINAL`。

### 4 · 排序与选材约束（改动前逐条确认）

1. **白名单必须排在两条广告清单之前** —— Jinx 与 AWAvenue 存在重叠域名，白名单排到后面会被误杀。
   ⭐ **白名单是两层，但两层不再连写**（2026-10-06 起变更）：
   **① 广告白名单**（`surge-direct.list`，位 ①，在广告清单之前）·
   **⑤ 系统域白名单**（Surge 内置 `SYSTEM` ／ Egern `apple_system.list`，位 ⑤，在广告清单**之后**）。
   ⚠️ **变更依据**：`SYSTEM` 的 18 个域名与两条广告清单**零交集**（裸域名与后缀覆盖均为 0，
   2026-10-06 复测仍成立）⇒ 排前或排后**拦截结果完全相同** ⇒ 不再占用「最前」这个语义位置。
   （分流版另有位 ④ `SystemOTA`：它与 `SYSTEM` 有 3 条重叠 ⇒ 必须排在 `SYSTEM` 之前，
   否则 `Apple Update` 组永远轮不到那 3 条。`Apple Update` **仅分流版提供**。）
   而 `apple.txt` 与 AWAvenue 有 **1 条交集**（`iadsdk.apple.com`）⇒ 它**不**上提（否则会放行一条苹果广告 SDK 域）。
2. **厂商专属规则（`OpenAI` / `Gemini` / `Anthropic` / `Claude`）排在 `AI.list` 之前** —— 否则 AI 域名先被 `AI.list` 接走，专属组形同虚设。
3. **`GitHub.list` 排在 `direct.txt` 之前** —— 实测 `direct.txt` 收录了若干含 `github` 的域名（githubim.com / githubshare.com / hellogithub.com / kkgithub.com 等），它们会被 `GitHub.list` 的 `DOMAIN-KEYWORD,github` 命中；排到后面这几个就接不到。本条**直指 `Proxy`**（2026-10-05 起不再单设 `GitHub` 组）。（`github.com` 本身**不在** `direct.txt` 里。）
4. **IP 类规则排最后，且必须带 `no-resolve` / `no_resolve`** —— 否则每个走到它的域名都会被强制本地解析一次，那正是泄露来源。详见 [`dns.md`](./dns.md)。
4b. ⭐ **规则级开关的取舍，六份 profile 共用一条原则**：**实测零 IP 条目的规则集不写，真含 IP 条目的必须写**。
    该开关只对规则集里的 IP 类条目起作用，纯域名集写上是空转 —— 本仓 2026-09-24 起把它从 12 条零 IP 规则上删掉。
    ⚠️ 判据是「实测零 IP」不是「纯域名」（`YouTube Music` 有 UA、`Microsoft` 还有 PROCESS-NAME，同样零 IP），
    且这些 URL 没锁 commit ⇒ 每次由 `audit_ruleset_content.py`（Surge）/ `audit_ruleset_noresolve.py`（Egern）重测。
    **三内核落点不同**，见 [`dns.md`](./dns.md)：
      · **Surge** —— 写在规则行末尾（`GEOIP,CN,DIRECT,no-resolve`）；
      · **Egern** —— `no_resolve` **仅对 `geoip` / `ip_cidr` / `ip_cidr6` / `asn` 四类生效**，
        写在 `rule_set` 上**不生效** ⇒ 这层防线在**规则集文件里**（条目级 `,no-resolve`）；
      · **mihomo** —— 写在规则行末尾（`RULE-SET,geoip-cn,DIRECT,no-resolve`），与 Surge 同。
        判「是不是 IP 类」的第一依据是 provider 的 `behavior`（`ipcidr` ⇒ 要写；`domain` ⇒ 不写），
        **不是**名字前缀 —— `check_clash_dns.py` 判据 ⑩ 即按此实测。
5. ⭐ **用 `*_No_Resolve` 变体，并下载下来数条目**。`Apple_All.list` 实测含 13 条不带 `no-resolve` 的裸 IP（Apple CDN 网段），
   一条这样的条目就让**每个走到该规则的域名**都被强制解析一次。判据是"下载 + 数条目"，**不是看规则集名字**
   （`ChinaMax.list` 名字像域名集，2026-09-24 快照里 **IP 类条目 12,472 条、域名类只有 64 条**）。
   （本仓 Apple 那条 2026-10-04 起已换成零 IP 的 `apple.txt`，此处保留 `Apple_All.list` 作判据示例。）
6. **两条广告清单的策略与参数必须逐字相同**，否则同一广告域名因命中不同清单而进出不一致。

> 🛡️ 本仓自托管的 `rules/apple_system.list` 没有第三方刷新审计 ⇒ 漂移只能靠人：Surge 大版本更新时把内置 `SYSTEM` 与这份快照比对一次
> （这份快照同时是 `audit_routing_coverage.py` 里 `SYSTEM` 那条内置集的判定依据，见该脚本的 `BUILTIN_SET_SNAPSHOTS`）。

### 5 · mihomo（clash）侧：另一套文件，同一套意图

> 本页 §1–§4 讲的是 Surge / Egern 的 `.list` 世界。mihomo 侧**自成一套**，以下数字全部由
> `yaml.safe_load` 解析 `clash/profiles/*.yaml` 现算（2026-10-08 复核），**不手抄头注**。
> 清单表、体量实测与选型决策见 [`rulesets.md`](./rulesets.md)（体量与覆盖度）
> 与 [`rulesets.md`](./rulesets.md)（来源与选型）——**本页不重复那份清单**。

#### 5.1 规模：25 份 / 10 份（不是 24 / 9）

| profile | `rule-providers` 键数 | `rules` 条数 | 其中 `RULE-SET` | 非规则集规则 | `format` 构成 | `behavior` 构成 |
|:--|:--:|:--:|:--:|:--|:--|:--|
| `clash/profiles/routing.yaml` | **25** | **27** | **25** | 2（`DOMAIN-SUFFIX,music.youtube.com` + `MATCH,Proxy`） | **20 `mrs` + 5 `yaml`** | 16 `domain` · 4 `ipcidr` · 5 `classical` |
| `clash/profiles/lazy.yaml` | **10** | **11** | **10** | 1（`MATCH,Proxy`） | **6 `mrs` + 4 `yaml`** | 4 `domain` · 2 `ipcidr` · 4 `classical` |

⚠️ **三个易错点，逐条都是本仓踩过的**：

1. **份数 ≠ 规则条数**（25 vs 27、10 vs 11）。多出来的是不引用任何集的
   `DOMAIN-SUFFIX` 直写规则与 `MATCH` 兜底。
   ⇒ **判据：数"规则集份数"应数 `rule-providers` 的键**（本仓恰好也等于 `RULE-SET` 条数，
   因为 25 份集全部被引用、没有空集）。用 `grep -c 'RULE-SET'` 在本仓是准的，
   但将来若两条规则引用同一份集就会失效。
2. **「20 份 MRS」≠「20 份 MetaCubeX」**。严格拆分是 **MetaCubeX 19 份 + AWAvenue 1 份 = 20 份 MRS**。
   评估上游可用性、写事故报告时 `AWAvenue-Ads` 要**单独算**。
3. **`my_clash_lazy.js` 头注曾写「5 份 MRS + 5 份 yaml」（**已改为 6 + 4**）是错的**，实际 6 + 4（见
   [`clash.md`](./profiles/clash.md) §18.4）。
   ⇒ 凡是可由解析算出的数字，别手抄进注释。

#### 5.2 来源四分（分流版）

| 类别 | 份数 | `format` / `behavior` | 谁保证内容 |
|:--|:--:|:--|:--|
| **MetaCubeX** `meta-rules-dat`（jsDelivr `@meta` 分支） | **19** | `mrs`（domain ×15 / ipcidr ×4） | 上游每日重建；**移动分支不可钉 commit** |
| **本仓自托管** `rules/*.yaml` | **3** | `yaml` / `classical` | **本仓自己**（真源 `rules/*.list`，§0.1） |
| **Jinx**（姊妹仓） | **2** | `yaml` / `classical` | `RiverFlowsInUUU/Jinx` `main` 移动分支 |
| **AWAvenue** | **1** | `mrs` / `domain` | `TG-Twilight/AWAvenue-Ads-Rule` `main` 移动分支 |
| **合计** | **25** | | |

懒人版同口径：**MetaCubeX 5 + 本仓 2 + Jinx 2 + AWAvenue 1 = 10**。

⇒ **供应链归属决定出问题时找谁**：`cn.mrs` 变空 → 只能等上游；`AI_Domains.yaml` 404 → **本仓事故，立刻可修**。
自托管的 3 份是唯一"出事能自己修"的。

#### 5.3 刷新周期：`interval: 86400`，与 Surge / Egern 的 604800 不一致是**刻意的**

25 份 / 10 份**无一例外**都是 `interval: 86400`（秒 = 24 小时）。而 Surge / Egern 侧是
`update-interval=604800` / `update_interval: 604800`（一周）。

⚠️ **不要去"对齐"这两个数** —— 两内核的键语义与缺省值都不同：

| | Surge | Egern | mihomo |
|:--|:--|:--|:--|
| 键 | `update-interval` | `update_interval` | `interval`（provider 级） |
| 缺省值 | 官方写明缺省 `86400`，**只有写负值才关掉自动更新** | 只在示例里出现过，**缺省值未文档化** | 无缺省必须显式给 |
| 本仓取值 | 604800（一周） | 604800（一周） | **86400（一天）** |

⇒ 所以 Surge 侧"显式写"是为了节奏可见可统一；Egern 侧"必须钉死"是因为不写行为不可知；
mihomo 侧则**本来就必填**，钉一天的理由是新域等待时间更短，而 `interval` 不影响内存与匹配开销
（mihomo 的匹配成本与表规模基本无关）。

顺带：mihomo 的 provider 都给 `path`（`./rule_provider/<文件名>`），**先落盘再解析** ——
刷新失败时沿用本地副本，不会因为一次网络抖动丢掉全部规则。
⚠️ 代价是**死链静默降级**：拉不到就变空集，该走 `AD` 的广告全进了兜底出口，配置看着跑得挺好
（本仓踩过 Jinx 上游改名导致 404 的那一遭）⇒ 由 `self-conf-skills/gates/clash/check_remote_urls.py` 定期问（慢，按需跑）。

#### 5.4 mihomo 分流版 27 条的顺序（与 Surge / Egern 的 26 条**不是逐位同构**）

⭐ **能跨内核同步的是"顺序命题"，不是"规则条数与 URL"**。三侧都必须保留的命题是：
**白名单先于广告 · 专属 AI 先于通用 AI · 应用规则先于国内兜底 · 域名规则先于 IP 规则 · 兜底最后**。
不能从"命题一致"推导出"文件必须逐位相同"。

mihomo 分流版的实际顺序（`rules` 段解析结果）：

| 位 | 规则 | 位 | 规则 |
|:-:|:-----|:-:|:-----|
| ① | `RULE-SET,Jinx-CN,DIRECT`（白名单） | ⑮ | `RULE-SET,youtube,YouTube` |
| ② | `RULE-SET,Jinx-Ads,AD` | ⑯ | `RULE-SET,emby,Emby`（本仓自托管） |
| ③ | `RULE-SET,AWAvenue-Ads,AD` | ⑰ | `RULE-SET,google,Google` |
| ④ | `RULE-SET,apple-update,Apple Update` | ⑱ | `RULE-SET,spotify,Spotify` |
| ⑤ | `RULE-SET,apple-system,DIRECT`（本仓自托管） | ⑲ | `RULE-SET,twitter,Twitter` |
| ⑥ | `RULE-SET,geoip-private,DIRECT,no-resolve` | ⑳ | `RULE-SET,microsoft,Microsoft` |
| ⑦ | `RULE-SET,private,DIRECT` | ㉑ | `RULE-SET,apple-cn,DIRECT` |
| ⑧ | `RULE-SET,openai,ChatGPT` | ㉒ | `RULE-SET,telegram,Telegram` |
| ⑨ | `RULE-SET,google-gemini,Gemini` | ㉓ | `RULE-SET,geoip-google,Google,no-resolve` |
| ⑩ | `RULE-SET,anthropic,Claude` | ㉔ | `RULE-SET,geoip-telegram,Telegram,no-resolve` |
| ⑪ | `RULE-SET,category-ai-chat-!cn,AI` | ㉕ | `RULE-SET,cn,DIRECT` |
| ⑫ | `RULE-SET,AI_Domains,AI`（本仓自托管） | ㉖ | `RULE-SET,geoip-cn,DIRECT,no-resolve` |
| ⑬ | `DOMAIN-SUFFIX,music.youtube.com,YouTube Music`（**唯一内联**） | ㉗ | `MATCH,Proxy` |
| ⑭ | `RULE-SET,github,Proxy`（无同名组） | | |

**懒人版 11 条**：`Jinx-CN` → `Jinx-Ads` → `AWAvenue-Ads` → `apple-system` →
`geoip-private`(no-resolve) → `private` → `category-ai-chat-!cn` → `AI_Domains` →
`cn` → `geoip-cn`(no-resolve) → `MATCH,Proxy`。

三处尤其**不是疏漏**（与 Surge / Egern 的结构差异）：

1. **mihomo 没有内置 `LAN` / `SYSTEM`** ⇒ 用 `private.mrs` 与本仓快照 `apple_system.yaml` 补位（§0.1）。
2. **mihomo 没有 `Claude.list`**（Surge / Egern 有 `Anthropic.list` + `Claude.list` 两条，
   位 ⑩⑪），只有一个 `anthropic.mrs`（位 ⑩）⇒ 少一位。
3. **mihomo 把 Google / Telegram 的 IP 兜底拆成独立 `ipcidr` provider**（位 ㉓㉔），
   因此比另外两侧多出规则位；Telegram 也由此下移到 ㉒。

⚠️ **位 ⑬ 那条内联规则是必需的**：`music.youtube.com` 是 `youtube.com` 的子域，
不前置就会被位 ⑮ 的 `youtube` 抢先命中（`geosite.dat` / `cn.mrs` 都没有独立 ytmusic 类别）。

#### 5.5 ⭐ 两个 AI 集：mihomo 侧独有的"双保险"

`category-ai-chat-!cn`（远程滚动）与 `AI_Domains`（本仓自托管 272 条）**都落 `AI` 组**，
两个内核侧也有同名的一对（`AI.list` Repcz + 本仓 `AI_Domains`），**形态一致、理由同源**：

- `AI_Domains`（272 条）= **10 源人工整合快照**，覆盖度更高；
- `category-ai-chat-!cn`（181 / 188 条）= **每 24 小时自动刷新**，能接住"两次人工整合之间"新出现的域。

⚠️ 二者**互相漏，且漏的方向不对称**（实测差集：上游漏本仓 **94 条**伴生域，本仓只漏上游 **4 条**）。
漏掉的 94 条多为认证 / 遥测 / 风控 / 通用网关类**伴生域**（`auth0.com` `statsig.com`
`apis.google.com` `challenges.cloudflare.com` …）—— 后果是**同一次会话里请求走了不同出口，触发风控**。
详见 [`rulesets.md`](./rulesets.md) §7。

#### 5.6 三条 mihomo 专属纪律

1. **`.mrs` 与 `yaml` 不可互换**：`mrs` 只装 `domain` / `ipcidr`，装不下带类型的规则行。
   需要 `DOMAIN-KEYWORD` / `URL-REGEX` / 精确 `DOMAIN` 的集合**必须**是 `yaml` + `classical`
   （本仓 5 份：3 份自托管 + Jinx 2 份）。
2. **`no-resolve` 按 `behavior` 判，不按名字**：`ipcidr` ⇒ 必须写；`domain` ⇒ 写了无意义；
   `classical` ⇒ 内容混合、静态判不出（本仓自托管 3 份实测零 IP）。
   由 `self-conf-skills/gates/clash/check_clash_dns.py` 判据 ⑩ 守。
3. **零 dat 依赖**：本仓 mihomo 侧**不用** `geosite.dat` / `geoip.dat`，全部走远程 `.mrs` / `.yaml`
   （原生 `GEOSITE` / `GEOIP` 规则已从分流版全部替换为 `RULE-SET`）。
   ⚠️ 这不排斥 `.mrs` —— 它们是独立远程集文件，与 dat 数据库无关。判据 ⑪ 守。

### 6 · 素材与许可

| 素材 | 用途 | 来源 |
|:-----|:-----|:-----|
| 策略组图标（`icons/*.png`，条数一律现抓：`ls icons/*.png \| wc -l`） | 面板图标（**三内核共用同一份**） | [RiverFlowsInUUU/Rule](https://github.com/RiverFlowsInUUU/Rule) · [jnlaoshu/MySelf](https://github.com/jnlaoshu/MySelf) · [Koolson/Qure](https://github.com/Koolson/Qure)。三者均已归档，**仅作署名归属**；实际使用的图标已**下载整合进本仓** `icons/`，运行时不依赖上游 |
| `icons/icons.json` | 图标订阅（**纯本仓**，永不失效） | 本仓派生 |
| `icons/icons-full.json` | 图标订阅（**大集成**＝本仓 + 上游全量） | 本仓 + 上述两个上游仓库，⚠️ 标「上游」的条目为**外部引用**、靠第三方在线 |
| `GeoLite2-Country.mmdb` | Surge 侧 `GEOIP` 判定 | [adysec/IP_database](https://github.com/adysec/IP_database) |
| `Country.mmdb` · `GeoLite2-ASN.mmdb` | Egern 侧 `geoip` / `asn` 判定 | [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) |
| （无 dat 依赖） | mihomo 侧 `geoip-*` 判定 | **零 dat**：4 份 `ipcidr` 集全部走远程 MetaCubeX `.mrs`，见 §5.6 |

本仓按 MIT 许可分发（根 `LICENSE`）；图标来源见上表。第三方规则集版权归其原作者。

> ⚠️ **上游图标仓库的许可状态**：`RiverFlowsInUUU/Rule` · `jnlaoshu/MySelf` · `Koolson/Qure` 三者**均未声明 SPDX 许可**（GitHub 上 `license` 字段为空）且**均已归档**。因此本仓只把它们的图标「下载整合」作为素材来源（本仓自有文件按 MIT 分发），`icons-full.json` 里对上游的**外部引用**则属风险自担 —— 上游删仓/转私有即失效，见 [`pitfalls.md`](./pitfalls.md) 的登记。

---

相关：[`rulesets.md`](./rulesets.md) · [`pitfalls.md`](./pitfalls.md) · [`../README.md`](../../README.md)
-weight.md) · [`rulesets.md`](./rulesets.md) ·
[`clash.md`](./profiles/clash.md) §9 · [`../../../README.md`](../../README.md)

---

## 三内核差异对照

> 本仓库把 Surge、Egern 与 clash-mihomo 三套模板放到一处。**分组意图和规则骨架可以共用，配置语法与执行阶段不能照抄。**
> 这一页是给“想把一侧的改动移植到另外两侧”的人看的：哪些能直接照搬、哪些照搬就是错的。
>
> 本页结论按当前文件逐条核对：`surge/profiles/routing.conf`、`egern/profiles/routing.yaml`、
> `clash/profiles/routing.yaml` 与 `clash/override/my_clash.js`。计数只算启用项，不算注释：
> Surge **23 组 / 26 条规则**，Egern **23 组 / 26 条规则**，mihomo 静态分流版
> **25 组 / 27 条规则 / 25 份 rule-provider**；mihomo 覆写脚本实际生成
> **<!-- auto:script-group-count -->22<!-- /auto:script-group-count --> 组 /
> <!-- auto:script-rule-count -->27<!-- /auto:script-rule-count --> 条规则 / 25 份 rule-provider**。
> （⚠️ 这三个数指**mihomo 覆写脚本**；Surge / Egern 是 <!-- auto:group-count -->23<!-- /auto:group-count --> 组 /
> <!-- auto:rule-count -->26<!-- /auto:rule-count --> 条 —— 两者不是一回事，别混用。）

### 1 · 语法与机制映射

| 语义 | Surge | Egern | clash-mihomo | 移植时注意 |
|:-----|:------|:------|:-------------|:-----------|
| 配置载体 | `.conf`，INI 分段 | `.yaml` | 静态 `.yaml`；另有 `.js` 覆写脚本 | mihomo 的脚本是第二种交付形态，不是可粘进 YAML 的配置片段 |
| 组结构 | 23 组 | 23 组，名称与顺序和 Surge 逐位相同 | 静态 25 组；覆写脚本 22 组 | 三侧共有 22 个业务/地区组；Surge/Egern 多 `Airport`，mihomo 静态多三个倍率子组 |
| 策略组类型 | `select` / `smart` | `select` / `smart` / `external` | `select` / `fallback` / `url-test`；内核还支持 `load-balance` | mihomo 没有 `smart`，不能只换类型名 |
| 订阅源 | `Airport = select, policy-path=…`，`hidden=true` | `Airport` 为 `external`，`urls` + `interval` + `hidden` | 静态 `routing.yaml` **已声明** `proxy-providers.Airport`（2026-10-07 起）；覆写脚本保留输入订阅的 `proxies` / `proxy-providers` | `policy-path`、`external.urls`、`proxy-providers/use/include-all*` 不是同一种对象，不能互抄 |
| 组展开 / 节点入组 | `include-other-group="X"`；显式成员不受 `policy-regex-filter` 影响 | `policies: [X]` + `flatten: true`；地区组再用 `filter` | 没有 `flatten`；用 `use`、`include-all`、`include-all-proxies` 或把组名写进 `proxies` | `flatten: true` 是 Egern 特有；mihomo 的 `include-all-proxies` 只收内联节点，`include-all` 才连 provider 一起收 |
| 组内筛选 | `policy-regex-filter` | `filter` | `filter` + `exclude-filter` | 三侧当前地区正则并不相同；只能移植“按地区筛”的意图，不能假定逐字等价 |
| 倍率 / 权重 | `policy-priority="正则:0.15"`，Smart 与 6 个地区组都有 | `priorities: {正则: 0.15}`，Smart 与 6 个地区组都有 | **无权重键**；只能用 `fallback` + `filter` / 节点排序模拟 | 0.15 在 Surge/Egern 是软权重；mihomo 的分档回落不是同一算法 |
| 规则顺序 | 26 条，first-match-wins | 26 条，与 Surge 逐位同义 | 27 条，保留“白名单 → 广告 → 系统/内网 → AI/应用 → 国内 → IP → 兜底”的骨架，但不是逐位同构 | mihomo 多 `geoip-google` / `geoip-telegram`，少独立 `Claude.list`，且 Telegram 位置不同，见 §3 |
| 远程规则集 | URL 直接写在 `RULE-SET,<URL>,<策略>` | URL 写在 `rule_set.match` | 先在 `rule-providers` 声明名字、`format`、`behavior`、`path`、`interval`，规则再按名字引用 | 把 `.list` URL 直接塞进 mihomo 的 `RULE-SET` 名字位是错的 |
| 规则集格式 | Surge `.list` / `.txt`，另有内置 `LAN` / `SYSTEM` | 可直接消费 Surge `.list` / `.txt` | 当前 25 份中：20 份 `.mrs`（16 个 `domain` + 4 个 `ipcidr`），5 份 `yaml` + `classical` | mihomo 的 `format` 与 `behavior` 必须和文件内容成对 |
| 刷新间隔 | `update-interval=604800` | `update_interval: 604800` | `interval: 86400` | 当前就是一周对一天；不要为了“数值统一”抹掉各侧既有节奏 |
| 本地 / 引导 DNS | `dns-server` 4 个 IP | `dns.bootstrap` 2 个 IP；`dns.upstreams` 4 个加密端点 | `default-nameserver` 2 个 IP；另分 direct / proxy-server / nameserver / fallback | 键名相似不代表调用阶段相同 |
| 加密与分流 DNS | `encrypted-dns-server` 3 个端点 | `upstreams.Domestic-DNS` + `forward` + `proxy_nameservers` | `direct-nameserver`、`proxy-server-nameserver`、`nameserver`、`fallback`、`nameserver-policy` | Egern 的 `proxy_nameservers` 会绕过 `forward`；mihomo 在 `respect-rules: true` 下需要 `proxy-server-nameserver` |
| 接管明文 53 | `hijack-dns` 枚举 6 个地址 | `hijack_dns: ['*']` | 仅静态 profile 的 `tun.dns-hijack: [any:53]`；当前只接管 UDP:53 | 覆写脚本不应写 `tun`；客户端自己管理 TUN |
| IPv6 | `ipv6 = false` + `ipv6-vif = disable` | `ipv6: false` | 顶层 `ipv6: false` + `dns.ipv6: false` | 目标可照搬为“关闭 IPv6”，键不能照搬；mihomo 少关一处都不完整 |
| 广告拦截 | 两条规则指向字面量 `REJECT`，并带 `pre-matching,extended-matching` | 规则层指向 `AD`；DNS 层 `dns.forward.value: reject` | 规则层指向 `AD`；DNS 层同时要求 `nameserver-policy: rcode://success` 与 `fake-ip-filter` | 三侧都在 DNS 前后设防，但触发链完全不同 |
| `no-resolve` | 规则行尾；当前用于 `LAN`、6 条含 IP 的应用集与 `GEOIP,CN` | `no_resolve: true` 只写在 `geoip`；写在 `rule_set` 上不生效 | 规则行尾；当前 4 个 `geoip-*` provider 引用都带 | 可移植的是“IP 规则不要为了匹配而先解析域名”的原则，不是字段落点 |
| 默认出口 | `FINAL,Proxy,dns-failed` | `default.policy: Proxy` | `MATCH,Proxy` | 只有 Surge 有 `dns-failed` 参数 |

mihomo 各键的逐键行为与边界，继续看 [`profiles/<kern>.md`](./profiles/clash.md)；
静态 profile 的 DNS / TUN 加固理由见 [`clash.md`](./profiles/clash.md)。

### 2 · 分组：22 个共同语义，三种实现

Surge 与 Egern 各 23 组，名称与顺序逐位相同：

```text
<!-- auto:group-list -->
Proxy · Smart · ChatGPT · Gemini · Claude · AI · YouTube · Emby · Google
Telegram · YouTube Music · Spotify · Twitter · Airport · Microsoft · Apple Update
AD · Hong Kong · Taiwan · Japan · Singapore · United States · Other Regions
<!-- /auto:group-list -->
```

mihomo 静态分流版没有 `Airport` 组，但有三个额外隐藏倍率组，所以是 25 组：

```text
Proxy · Smart · Low Mult. · Auto · High Mult. · ChatGPT · Gemini · Claude · AI
YouTube · Emby · Google · Telegram · YouTube Music · Spotify · Twitter · Microsoft
Apple Update · AD · Hong Kong · Taiwan · Japan · Singapore · United States · Other Regions
```

三侧真正共有的是除 `Airport` 外的 **22 个组名**。应用组的主要成员顺序也已对齐：
例如 `ChatGPT` 都是“美 → 台 → 日 → 新”，`Claude` 都是“台 → 日 → 新 → 美”，
`Microsoft` 都是 `DIRECT → Proxy`，`Apple Update` 都是 `DIRECT → REJECT`。
这类**产品取向**可以三侧同步改；组类型、节点展开方式和筛选键必须各写各的。

#### 2.1 Smart 与倍率不是同一个实现

- **Surge**：`smart` 直接展开 `Airport`，用 `policy-priority` 给低倍率节点乘 0.15。
- **Egern**：`smart` + `policies: [Airport]` + `flatten: true`，用 `priorities` 表达同一个 0.15 权重。
- **mihomo**：没有权重机制。静态文件声明 `Low Mult.` / `Auto` / `High Mult.` 三个
  `url-test` 组，以 `filter` 分档，再由 `fallback` 按档回落；覆写脚本则在执行时用
  `sortedByRate` 排可见的内联节点，`Smart` 仍是 `fallback`。

⚠️ **按真实配置核对出的当前状态**：`clash/profiles/routing.yaml` 虽然声明了三个隐藏分档组，
但 `Smart.proxies` 当前实际是单独的 `DIRECT`，并未引用这三个组；同一文件也没有
`proxy-providers`，末尾却是空的 `proxies: []`。这与文件头“替换
`proxy-providers.Airport.url`”的说明不一致。这里不替配置找理由：移植时应按“当前静态版没有可用订阅源、
三档没有接到 Smart”处理。**【2026-10-07 更新】此段已过时：静态 `routing.yaml` 现已声明
`proxy-providers.Airport`，且 Smart 三档已接入。移植时按“有可用订阅源”处理。**
它从传入订阅保留节点与 provider。

#### 2.2 地区组不能只复制正则

Surge/Egern 的 5 个命名地区组使用同一套长关键词表，并在 `Other Regions` 里维护对应负向集合；
mihomo 当前使用另一套较短正则。更关键的是节点入口不同：

- Surge：`include-other-group="Airport"`；
- Egern：`policies: [Airport]` + `flatten: true`；
- mihomo 静态：地区组是 `include-all: true`（2026-10-07 起；此前为 `include-all-proxies`）；
- mihomo 覆写：检测到输入有 provider 时用 `include-all`，否则用 `include-all-proxies`。

因此，“新增一个地区关键词”可以三侧同步做；“复制一整行地区组”一定不行。

### 3 · 规则：共同骨架，不是假装 27 条逐位相同

Surge 与 Egern 的 26 条规则逐位同义；mihomo 有 27 条。当前分流版的真实顺序如下：

| 语义 | Surge | Egern | clash-mihomo |
|:-----|:------|:------|:-------------|
| 广告白名单 | ① `surge-direct.list` → `DIRECT` | ① 同源 `.list` → `DIRECT` | ① `Jinx-CN`（yaml/classical）→ `DIRECT` |
| 两条广告 | ②③ `.list` → 字面量 `REJECT` + pre-matching | ②③ `.list` → `AD` | ②③ `Jinx-Ads` / `AWAvenue-Ads` → `AD` |
| Apple 更新 | ④ `SystemOTA.list` → `Apple Update` | ④ 同左 | ④ `apple-update.mrs` → `Apple Update` |
| 系统域 | ⑤ 内置 `SYSTEM` → `DIRECT` | ⑤ `apple_system.list` → `DIRECT` | ⑤ `apple-system.yaml` → `DIRECT` |
| 内网 | ⑥ 内置 `LAN`；⑦ `private.txt` | ⑥ `Lan.list`；⑦ `private.txt` | ⑥ `geoip-private.mrs`；⑦ `private.mrs` |
| AI 专属 | ⑧ OpenAI；⑨ Gemini；⑩ Anthropic；⑪ Claude | ⑧–⑪ 同左 | ⑧ openai；⑨ google-gemini；⑩ anthropic；**无独立 Claude 集** |
| AI 兜底 | ⑫ Repcz `AI.list`；⑬ 本仓 `AI.list` | ⑫⑬ 同左 | ⑪ `category-ai-chat-!cn.mrs`；⑫ 本仓 `AI_Domains.yaml` |
| YouTube Music | ⑭ 远程 `YouTubeMusic.list` | ⑭ 同左 | ⑬ 内联 `DOMAIN-SUFFIX,music.youtube.com` |
| GitHub / YouTube / Emby / Google | ⑮–⑱ | ⑮–⑱ | ⑭–⑰ |
| Telegram / Spotify / Twitter / Microsoft | ⑲–㉒，Telegram 在前 | ⑲–㉒，同左 | ⑱ Spotify；⑲ Twitter；⑳ Microsoft；Telegram 下移到㉒ |
| Apple | ㉓ `apple.txt` | ㉓ 同左 | ㉑ `apple-cn.mrs` |
| 应用 IP 补充 | 已合在部分 Surge `.list` 中 | 由清单与 Egern 能力处理 | ㉓ `geoip-google`；㉔ `geoip-telegram`，均带 `no-resolve` |
| 国内与兜底 | ㉔ `direct.txt`；㉕ `GEOIP,CN`；㉖ `FINAL` | ㉔ `direct.txt`；㉕ `geoip`；㉖ `default` | ㉕ `cn.mrs`；㉖ `geoip-cn.mrs`；㉗ `MATCH` |

三侧都必须保留的**顺序命题**是：白名单先于广告、专属 AI 先于通用 AI、应用规则先于国内兜底、
域名规则先于 IP 规则、最终兜底最后。不能从“顺序命题一致”推导出“规则数量和 URL 必须一致”。

三处尤其不是疏漏：

1. Surge 有内置 `LAN` / `SYSTEM`；Egern 与 mihomo 分别用远程清单或自托管快照补位。
2. Surge/Egern 用 Surge `.list` 体系；mihomo 优先用 MetaCubeX `.mrs`，只把 5 份清单留作 YAML。
3. mihomo 把 Google / Telegram 的 IP 兜底拆成独立 `ipcidr` provider，因此比另外两侧多出规则位。

完整规则集来源可与 [`rulesets.md`](./rulesets.md) 交叉看；但该页仍以 Surge/Egern 为主，
mihomo 的实际值应以本页和 [`profiles/<kern>.md`](./profiles/clash.md) 为准。

### 4 · 移植边界：什么能照搬，什么照搬就是错

#### 4.1 可以三侧同步的，是“意图”

以下改动适合一次设计、三侧落地：

1. **业务组名、默认取向和成员顺序**：例如把某服务默认出口从 `Smart` 改成 `United States`，
   三侧都应改；但仍分别写 INI、Egern YAML、mihomo YAML/JS。
2. **规则排序约束**：新增专属规则时放在通用规则之前；新增国内兜底不能越过应用规则；
   IP 规则放在域名规则之后。
3. **共享图标与三份自托管规则真源**：改 `icons/` 的同一路径可供三侧引用；改
   `rules/*.list` 后生成 mihomo YAML，见 §8。
4. **安全目标**：关闭 IPv6、接管明文 DNS、加密上游、广告在解析阶段拒答、IP 规则不触发额外解析。
   这些目标一致，但每个目标都有三种落点。
5. **共同业务规则的策略去向**：如 GitHub → `Proxy`、Apple 更新 → `Apple Update`、系统域 → `DIRECT`。
   规则集来源可以不同，最终策略应同步复核。

#### 4.2 下列写法照搬就是错

| 想移植的改动 | 错误照搬 | 实际后果 | 正确做法 |
|:-------------|:---------|:---------|:---------|
| Surge 解析阶段广告拦截 | 把 `pre-matching,extended-matching` 原样搬到 Egern / mihomo，或只把规则改成 `AD` | 两侧没有同名参数；mihomo 在 fake-IP 路径下甚至可能先返回假 IP，DNS 拒答根本走不到 | Egern 写 `dns.forward.value: reject`；mihomo 同时写 `nameserver-policy: rcode://success` 与同集 `fake-ip-filter`，规则层再指 `AD` |
| Egern 节点展开 | 把 `flatten: true` 搬到 mihomo | mihomo 无对应键；不会得到“展开 provider 节点”的效果 | 静态配置按来源选 `use` / `include-all` / `include-all-proxies`；覆写脚本先判断输入有没有 provider |
| 倍率偏好 | 把 Surge `policy-priority` 或 Egern `priorities` 政名后塞给 mihomo | mihomo 不支持节点权重；未知键不能产生 0.15 软偏好 | 用 `url-test` + `filter` 分档，再由 `fallback` 按档回落；脚本只能对执行时可见节点排序。当前静态接线异常见 §2.1 |
| mihomo TUN | 把静态 profile 的 `tun` 段写进 `my_clash.js` | 覆写脚本会越过客户端的 TUN 管理，可能与 Mihomo Party / Clash Verge 设置冲突 | `tun` 只属于 `profiles/*.yaml`；`override/*.js` 不生成它 |
| 规则集引用 | 把 Surge 的 `RULE-SET,https://…list,...` 原样搬进 mihomo | mihomo 的规则位需要 provider **名字**，不是下载 URL；同时缺 `format/behavior/path` | 先声明 `rule-providers`，再 `RULE-SET,<name>,<policy>` |
| `no-resolve` | 把 Surge 的规则尾参数改成 Egern `rule_set.no_resolve: true` | Egern 对 `rule_set` 不执行该字段，防解析形同虚设 | Egern 只在 `geoip/ip_cidr/ip_cidr6/asn` 用 `no_resolve`，远程集靠条目级语义；mihomo 的 `ipcidr` provider 引用可带行尾 `no-resolve` |
| IPv6 关闭 | 只复制一个 `ipv6: false` 到 mihomo | 只关顶层或只关 DNS 都不完整，AAAA 或真实 IPv6 通路仍可能存在 | mihomo 同时关顶层与 `dns.ipv6`；Surge 关 `ipv6` + `ipv6-vif`；Egern 关顶层 `ipv6` |
| 订阅入口 | 把 Surge `Airport` 当组名写进 mihomo `proxies` | `Airport` 在 mihomo 设计里应是 provider 名；未声明时就是悬空引用 | 静态声明 `proxy-providers.Airport` 并用 `use/include-all`；脚本沿用传入订阅。段**已存在**（2026-10-07） |
| DNS 路由 | 把 Egern `proxy_nameservers` 当成 mihomo `proxy-server-nameserver` 的纯改名 | Egern 的键会跳过 `forward`；mihomo 的键负责节点域名解析，并与 `respect-rules` 有约束，执行链不同 | 按“引导 / 直连 / 节点 / 主解析 / 回退”五个角色逐项重配 |
| 默认规则 | 把 `FINAL,Proxy,dns-failed` 改个大小写放进另外两侧 | Egern / mihomo 不认 Surge 的 `dns-failed` 语义 | Egern 用 `default.policy`；mihomo 用 `MATCH` |
| 规则禁用 | 把 Egern 的 `disabled: true` 搬到 Surge | Surge `RULE-SET` 没有该字段；整行仍可能无法加载 | 为保持位数一致，本仓两侧都把不用的 `Proxy.list` 注释掉；mihomo 则删除对应 rules 项与无用 provider |

> 最重要的判断法：先问“这个改动发生在**解析阶段、规则阶段、节点展开阶段还是客户端运行层**”，
> 再找目标内核的对应机制。只按相似键名替换，通常就是错的。

`no-resolve` 的三侧落点另见 [`dns.md`](./dns.md)。

### 5 · 懒人版：同为 11 条规则，不代表可以复制文件

当前实配计数：

| | Surge `lazy.conf` | Egern `lazy.yaml` | mihomo `lazy.yaml` / `my_clash_lazy.js` |
|:--|:------------------|:------------------|:-----------------------------------------|
| 分组 | 4：`Airport` / `Proxy` / `AI` / `AD` | 4：同左 | 3：`Proxy` / `AI` / `AD`；没有 `Airport` 组 |
| 规则 | 11 | 11 | 11 |
| 规则集载体 | URL 内联 `.list` | `rule_set.match` 指向 `.list` | 10 份 rule-provider；规则另有最终 `MATCH` |
| 广告解析阶段 | `pre-matching REJECT` | `dns.forward.value: reject` | `nameserver-policy` + `fake-ip-filter` |
| 系统 / 内网 | 内置 `SYSTEM` + `LAN` + `private.txt` | `apple_system.list` + `Lan.list` + `private.txt` | `apple-system.yaml` + `geoip-private.mrs` + `private.mrs` |
| 默认出口 | `FINAL,Proxy,dns-failed` | `default.policy: Proxy` | `MATCH,Proxy` |
| TUN | 由 Surge 自身配置模型处理 | 由 Egern 自身配置模型处理 | 静态 YAML 有 `tun`；覆写脚本没有，也不应有 |

三侧懒人版的**语义骨架**已经对齐为：广告白名单 → 广告 ×2 → 系统 → 内网 ×2 → AI ×2 → 国内域名 → 国内 IP → 兜底。
仍然只能按语义移植，不能复制规则行。mihomo 静态懒人版也存在“头注要求替换
`proxy-providers.Airport.url`”的对照 —— 该段**现已存在**，不再是待确认项。

### 6 · 版本保留策略

- 三侧 `profiles/` 顶层都保留固定名四件：`routing` / `lazy`，各有带注释版与 `.min` 版；订阅地址不随版本改名。
- Surge / Egern 的现役文件以 `#! version=` 标当前版本（仓内不保留历史版本）。
- mihomo 静态 profile 由 `self-conf-skills/run/clash/build_profiles.py` 生成，**现已带 `#! version=` 头注**（2026-10-07 补），
  版本由生成器写入头注；另有两个覆写脚本。
  **不要把 Surge/Egern 的头注版本与归档约定机械搬到 mihomo。**
- `.min` 的含义始终是“同一配置去注释”，不是精简功能；改完必须对拍。

### 7 · 脚本与测试

| 目的 | Surge | Egern | clash-mihomo |
|:-----|:------|:------|:-------------|
| DNS 判据 | `check_surge_dns.py` | `check_egern_dns.py` + `audit_dns_forward.py` | `self-conf-skills/gates/clash/check_structure.py` 检查 DNS、IPv6、广告双条件与静态 TUN |
| 地区组 | `audit_region_filters.py` | `audit_region_filters.py` | 当前无同名专用脚本；结构与脚本同步由 clash 门禁检查 |
| 路由覆盖 | `audit_routing_coverage.py` | `audit_routing_coverage.py` | `check_structure.py` 检查引用与排序，`check_script_sync.py` 对拍静态版 / 覆写版 |
| 规则集内容 | `audit_ruleset_content.py` | `audit_ruleset_noresolve.py` | `check_remote_urls.py`；共享 YAML 由 `build_rules.py --check` 对拍真源 |
| `.min` 对拍 | 共享 `self-conf-skills/gates/check_min_pair.py` | 同左 | `self-conf-skills/gates/check_min_pair.py` |
| 总入口 | `python self-conf-skills/gates/verify_all.py` | 同左 | 同一总入口会继续执行 mihomo 专属门禁 |
| 链接门禁 | `python self-conf-skills/gates/check_links.py` | 同左 | 同左 |

三侧测试不能合成一个“万能解析器”：相同目标背后的语法、默认值和失败方式不同。
维护入口与命令总表见 [`AGENTS.md`](../../AGENTS.md)。

### 8 · 合并后真正共享的东西

#### 8.1 `icons/`

根目录当前有 **40 个图标 PNG + 1 个 SVG**。三侧配置都引用同一个
`https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/…` 基址；覆写脚本也只定义这一份 `ICON`。

因此换图标时可以直接三侧共用同一路径。需要同步复核的是：组名是否仍指向正确文件、目标客户端是否支持该文件格式，
而不是再复制三份图片。

#### 8.2 `rules/`：`.list` 是真源，`.yaml` 是生成物

当前共享清单为三对文件：

| 唯一真源 | 条目数 | mihomo 生成物 | 三侧用途 |
|:---------|------:|:---------------|:---------|
| `rules/AI.list` | 272 | `rules/AI_Domains.yaml` | Surge/Egern 直接引用 `.list`；mihomo 引用 yaml/classical |
| `rules/apple_system.list` | 18 | `rules/apple_system.yaml` | Egern 补 Surge 内置 `SYSTEM`；mihomo 用 yaml；Surge 直接用内置集 |
| `rules/emby.list` | 4 | `rules/emby.yaml` | Surge/Egern 直接引用 `.list`；mihomo 引用 yaml/classical |

生成链只有一条：

```bash
python self-conf-skills/run/clash/build_rules.py

python self-conf-skills/run/clash/build_rules.py --check
```

`build_rules.py` 会去掉空行与注释，把每条 Surge 规则原样包进 mihomo 的 `payload:`；
当前对拍结果为 4 / 18 / 272 条全部一致。**不要手工编辑 `rules/*.yaml`。**

这里的“共享”不等于三内核直接读取同一种文件：Surge/Egern 消费 `.list`，mihomo 消费生成的 `.yaml`；
共享的是同一份内容真源。mihomo 其余 **20 份 `.mrs` + 5 份 YAML** 仍由自己的 `rule-providers` 管理。

### 9 · 已知单侧独有、不可移植项

| 只在哪侧 | 项 | 为什么不能移植 |
|:---------|:---|:---------------|
| Surge | `[SSID Setting]` 的 `suspend=true` | 是整机网络级暂停；Egern 的 `ssid` 条件规则和 mihomo 路由规则都只是选路，不等于暂停 |
| Surge | `pre-matching` / `extended-matching` | 是 Surge 的提前求值阶段；另外两侧只能用各自 DNS 拒答链实现目标 |
| Surge | 内置 `LAN` / `SYSTEM` | Egern/mihomo 没有同一内置集合，只能用远程集或本仓快照补位 |
| Surge | `FINAL,...,dns-failed` | `dns-failed` 没有另外两侧的同名参数 |
| Surge | `[Host]` 与 `[URL Rewrite]` 当前两条 302 | 本仓另外两份分流配置没有对应段；若真要移植，应按客户端能力另设计，不能塞进 rules |
| Egern | `flatten: true` | 是 Egern 的嵌套组展开键 |
| Egern | `dns.forward` 与 `proxy_nameservers` 绕行关系 | 是 Egern 自己的 DNS 执行链；mihomo 的 `nameserver-policy` 不是字段改名 |
| Egern | `vif_only`、`real_ip_domains`、`block_ips` | 都是 Egern 顶层 / DNS 模型的专有落点 |
| mihomo 静态 profile | `tun`、`dns-hijack`、`strict-route` | 静态导入需要自己收口；覆写脚本也不应继承这段 |
| mihomo | `rule-providers.format/behavior/path` 与 `.mrs` | Surge/Egern 的 URL 内联规则没有这层声明 |
| mihomo | `fake-ip-range`、`nameserver-policy`、`fake-ip-filter` 双条件 | 广告空回答必须绕开 fake-IP 快速返回；另外两侧没有同一中间件链 |
| mihomo | `.js` 覆写交付形态 | 脚本整体替换 groups/providers/rules/dns，同时保留输入节点；Surge/Egern 没有对应物 |
| mihomo 静态分流版 | `Low Mult.` / `Auto` / `High Mult.` 三个隐藏组 | 是为了模拟没有原生权重的限制；不能反向移植去替代 Surge/Egern 的权重键 |

还要保留三项**有意不统一**的差异：

1. **DNS 端点写法**：Surge 的 3 个加密端点中有 2 个主机名；Egern 的 4 个 upstream 全为 IP 字面量；
   mihomo 的主 `nameserver` / `fallback` 用 IP 字面量，但 direct / proxy-server 端点仍是主机名。
   不能拿任一侧的“全 IP”或“保留主机名”当三侧通用硬指标。
2. **刷新周期**：Surge/Egern 规则集当前统一 604800 秒；mihomo provider 是 86400 秒。
3. **静态与覆写职责**：mihomo 静态 YAML 自带 TUN，覆写 JS 交给客户端；这不是漏项。

最后，`my_clash.js` 头注写“22 组 / 25 份规则集 / 27 条规则”，与脚本实际执行结果一致
**22 / 25 / 27**；静态 `routing.yaml` 的头注数字 **25 / 25 / 27** 与实际一致，但订阅入口与 Smart 接线存在
§2.1 所述不一致。这些都应在后续修配置或生成器时处理，**不能在移植文档里替真实配置补写不存在的行为**。

---

相关：[`rulesets.md`](./rulesets.md) · [`dns.md`](./dns.md) ·
[`profiles/<kern>.md`](./profiles/clash.md) · [`clash.md`](./profiles/clash.md) ·
[`AGENTS.md`](../../AGENTS.md)

---

## Surge · 规则集重量（surge 侧）

> **何时读**：用户问「规则集是不是太重」、要换规则集、或想判断某个规则集能不能用。

#### 1 · 问题成因

Surge 把被引用的规则集**在内存里展开成匹配表**。一份十几万条的规则集
和一份 4 千条的规则集，对启动时间与常驻内存的影响不是一个量级。

但**更大的坑不是总量，是构成** —— 见 §2。

#### 2 · 核心判据：不是看条数，是看**类型分布**

本项目用到的三个「必须数的东西」：

| 判据 | 为什么 |
|:-----|:-------|
| **域名条目数** | 决定它能不能"接住国内域名"。IP 条目再多也接不住域名 |
| **IP 条目数** | 决定它会不会"触发解析"（不带 `no-resolve` 时） |
| **缺 `no-resolve` 的 IP 条目数** | 决定它会不会制造出口 ③ |

#### 2.1 名字骗人的实例

| 规则集 | 名字看起来 | 实测域名条目 | 实测 IP 条目 |
|:-------|:-----------|:------------:|:------------:|
| `direct.txt`（Loyalsoldier） | 国内直连 | **十几万** | 0 |
| `ChinaMax.list` | 国内最大集 | **64** | 12472 |

`ChinaMax.list` 名字像国内域名集，实际 **99.5% 是 IP**。

**后果**：一份"加了 `no-resolve` 之后国内域名走代理"的配置，
用 `ChinaMax.list` 当主承重墙。因为：
- 它的 12472 条 IP 条目在 `no-resolve` 下**不再匹配域名**；
- 它的 64 条域名条目**接不住**国内的量。

⇒ **判据是「数域名条目」，不是看名字，也不是看 README 标题。**

#### 2.2 本项目的构成

| 规则集 | 条数 | 域名 | IP | 缺 `no-resolve` 的 IP |
|:-------|:----:|:----:|:--:|:---------------------:|
| `surge-direct.list` | — | — | 0 | 0 |
| `surge-ads.list` | — | — | 0 | 0 |
| `AWAvenue-Ads-Rule-Surge-RULE-SET.list` | — | — | 0 | 0 |
| `AI.list` | — | — | 0 | 0 |
| `private.txt` | — | — | 0 | 0 |
| `direct.txt` | **十几万** | **十几万** | 0 | 0 |

> ⚠️ **条数一律不写死精确数字**：`—` = 现抓；`direct.txt` 那格写「十几万」只用于表达量级。
> 这些规则集都没锁 commit，上游每周更新，固定数字很快过期（本仓 lazy v1.1 起就是这个口径）。
> 要精确值现抓：`python self-conf-skills/run/surge/audit_ruleset_content.py <profile>`。
> 这张表真正有意义的列是 **IP 列** —— IP 数才决定 `no-resolve` 风险，它与条数无关。

**六份加起来 IP 条目为 0** —— 所以本项目的 `no-resolve` 风险主要来自
「将来换规则集」，而不是当下。

⚠️ 这意味着 `audit_ruleset_content.py` 的判据 A（缺 `no-resolve` 的 IP 条目）
在当前配置下是**空过**的。这是**已知且可接受**的 —— 它是一道**防将来**的闸门。
不要因为"现在空过"就把它删掉。

#### 3 · 数字的取得方式

```bash
python self-conf-skills/run/surge/audit_ruleset_content.py surge/profiles/lazy.conf
```

输出里每条规则集都有：

```
── 第 193 行 · surge-ads.list （新下载） → REJECT
   共 <n> 条：域名类 <n> / IP 类 0 / 其他 0
   域名类型：{'DOMAIN-SUFFIX': <n>, 'DOMAIN-WILDCARD': <n>}

── 第 210 行 · AWAvenue-Ads-Rule-Surge-RULE-SET.list （新下载） → REJECT
   共 <n> 条：域名类 <n> / IP 类 0 / 其他 0
   域名类型：{'DOMAIN': <n>, 'DOMAIN-SUFFIX': <n>, 'DOMAIN-KEYWORD': <n>}
```

末尾还有直连集合的汇总：

```
直连（DIRECT）规则集的域名条目统计：
   surge-direct.list                            域名    <n> / IP      0
   apple.txt                                    域名    <n> / IP      0
   private.txt                                  域名    <n> / IP      0
   direct.txt                                   域名 <十几万> / IP      0

✅ 直连集合共 <合计> 条域名条目 —— 足以接住国内域名
```

> ⚠️ **上面两个块是「输出长什么样」的样例，不是信得过的现行读数** ——
> 块里每一个数字都是写作时点的快照，上游每周更新后就变了，所以用占位符/量级表示。
> 要真数就跑一次命令。

加 `--show-domestic` 打印明细，加 `--force` 忽略缓存重下。

> ⚠️ **读数会被缓存带偏**：默认缓存在系统临时目录（`<tmp>/surge-ruleset-cache`），
> **跨会话保留**。上游改过条目后，不带 `--force` 会一直报旧条数。
> 对不上就加 `--force` 重跑一次再下结论 —— 别把旧缓存读数当成上游漂移。

#### 4 · 类型分布的读法

`parse_ruleset` 把条目分成三类：

```python
_DOMAIN_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "DOMAIN-SET", "DOMAIN-REGEX", "HOST", "HOST-SUFFIX", "HOST-KEYWORD",
    "HOST-WILDCARD",
}
_IP_TYPES = {"IP-CIDR", "IP-CIDR6", "IP6-CIDR", "SRC-IP", "DEST-IP", "IP-ASN"}
_OTHER_TYPES = {"URL-REGEX", "USER-AGENT", "PROCESS-NAME", "PROTOCOL",
                "DEST-PORT", "SRC-PORT"}
```

⚠️ **裸域名**（没有逗号的行，如 `example.com`）也按 `DOMAIN-SUFFIX` 计入 ——
部分社区的 `.list` 这么写。判据里同时记进 `<裸域名>` 与 `DOMAIN-SUFFIX` 两个桶，
前者便于看出"这份集用的是裸格式"。

⚠️ **`_OTHER_TYPES` 不参与任何判负。** `URL-REGEX` / `USER-AGENT` 这类
在 Surge 里是**不可预匹配**的（需要在 HTTP 层求值），也不会触发 DNS 解析。
但它们**不能带 `pre-matching`** —— 这是另一个话题，见
[`clash.md`](./profiles/clash.md) §4.4。

#### 5 · 超重时的处置

#### 5.1 先量，再判断

不要凭感觉换规则集。先跑一次上面的命令，看：

| 观察 | 结论 |
|:-----|:-----|
| 域名条目数 ≥ 10 万 | 内存占用会明显，但**这是国内直连的必要成本** |
| 域名条目里重复率高（多个集重叠） | 可以合并 |
| IP 条目占多数且判给 DIRECT | ⚠️ 检查 `no-resolve` 与"域名条目是否够" |
| 有 `URL-REGEX` / `USER-AGENT` | 不能用 `pre-matching`，但也不影响 DNS |

#### 5.2 本项目的取舍

`direct.txt` 这十几万条是**刻意保留**的。理由：

- 它是"`no-resolve` 之后国内域名还能直连"的**唯一承重墙**；
- 砍到 1 万条以内 → 大量国内域名落到 `FINAL → Proxy`，用户一定报障；
- 它这十几万条**全是域名**，所以不会制造出口 ③。

**结论：这份"重"是必须付的代价。** 想优化就从别处省，不要动它。

#### 5.3 真要减重

按这个顺序试：

1. **合并重叠的直连集** —— 去掉重复条目，不减少覆盖面
2. **换 IP 类规则集为域名类** —— 前提是域名条目够
3. **砍掉用不到的分流** —— 例如不要 AI 分流就删掉 `AI` 组与 `AI.list` 那条规则，
   少两个成员与一处分流
4. **给远程集加 `update-interval` 拉长** —— 减少刷新频率（新广告域名要等一个刷新周期才命得中；本仓取一周，再长就要在文件里写明理由）

⚠️ **不要**为了"轻"而把 `direct.txt` 换成一个名字像国内域名集、
实际以 IP 为主的规则集。那是本项目最典型的坑。

#### 6 · 缓存

规则集下载后会缓存在系统临时目录（约 6 MB）：

- Windows：`%TEMP%\surge-ruleset-cache`
- macOS / Linux：`/tmp/surge-ruleset-cache`

缓存文件名的生成：

```python
key = re.sub(r"[^A-Za-z0-9._-]", "_", url)[-120:]
```

**取 URL 的末尾 120 字符**并替换非法字符 —— 这样同一份规则集的不同 commit
（URL 只在末尾的 hash 处不同）会落成不同的缓存键。同时避免超长路径。

⚠️ 缓存**没有过期机制**。想拿最新内容用 `--force`。

---

## Egern · 规则集重量（egern 侧）

> 本文是 [`AGENTS.md`](../../AGENTS.md) 的引用文件。 **何时读**：用户问「3.42 MB 的规则集是不是负担太重 / 别的软件扛得住吗」。

配套脚本 `self-conf-skills/run/egern/weigh_ruleset.py`。**先纠正两个前提再谈数字**（见正文）。

---

用户问「3.42 MB 的规则集是不是负担太重 / 别的软件扛得住吗」时，**先纠正两个前提再谈数字**：

1. **rule-set 不是 profile 的一部分**。profile 本体 ~34 KB，规则表是远程文件，只在启动/更新时下载一次并缓存，**不参与每次连接**。"配置太大"这个说法本身不成立。
2. **大表不是用来治 DNS 泄露的**。治泄露是 `no_resolve` + 换掉带裸 IP 的规则集（坑 15/16）；大表（`ChinaMax_All_No_Resolve`）解决的是**分流**（坑 17）。两者不是一笔交易，别把成本记在泄露头上。

#### 实测（原生内核 mihomo v1.19.31 / Go，windows-amd64，稳态 RSS 中位数，3 次）

| 加载内容 | 条目 | 文件 | 稳态 RSS | 增量 |
|---|---|---|---|---|
| 空配置基线 | — | — | 29.2 MB | — |
| `ChinaMax_All_No_Resolve` | 111,332 域名 + 12,472 IP | 3.42 MB | 51.8 MB | **+22.6 MB** |
| 同上、删掉 IP 条目 | 111,409 域名 | 2.97 MB | 47.7 MB | +18.5 MB |
| `adrules_surge_domainset`（Cats-Team 广告表） | 199,781 | 4.36 MB | 53.8 MB | +24.7 MB |

- ⭐ **可复用判据：原生实现每个域名条目 ≈ 130–175 B ⇒ 内存 ≈ `条目数 × 0.15 KB`。**（Python dict 实现实测 ~290 B/条，约为原生 2 倍。）
- ⚠️ **别用"感觉"估**：本次先估"原生大概几 MB"，实测 +22.6 MB —— **差 5 倍**。要真数字就得起一个内核量（Windows 上可直接下载官方 release，用 `rule-providers: {type: file, behavior: classical, format: text}` 指向本地 `.list`，读进程 RSS）。
- **加载时间无差别**：空配置就绪 356 ms vs 加载 3.42 MB 就绪 355 ms。
- ⭐ **匹配成本与表规模基本无关**：单次查询 0.36–0.69 µs；表从 1,000 条涨到 111,332 条（111 倍），查询只从 0.36 µs → 0.69 µs（不到 2 倍，O(域名标签数)）。**所以大表不会拖慢任何连接，唯一代价是常驻内存。**

#### 大表不可瘦身

| 检查 | 实测 |
|---|---|
| 去重 | 111,319 → 111,319，**零重复** |
| 被更短父后缀覆盖的冗余 | **只有 4–5 条（0.004%）** |
| 标签深度分布 | 两级 110,754 条、三级 396、四级以上 119 ⇒ **99.5% 已是最小可用粒度**，没有归并空间 |
| 表内 IP 段 vs `geoip:CN` | 12,472 条中 7,622 条（61.1%）两端都在 CN；IPv4 面积 93.4% 落在 CN 内 ⇒ **那 12,472 条 IP 对本配置冗余**，但只值 4.1 MB / 13%，删了要自建托管，不划算 |

#### 换小表要按「覆盖率」判，绝不能按体积判

| 判据 | `ChinaMax_All_No_Resolve`（111k） | `ChinaDomain.list`（ACL4SSR，586 条 / 17 KB） |
|---|---|---|
| 从大表随机抽 5,000 条长尾域名 | 100% | **0.4%** |
| 26 个高频国内站点 | 25/26 | 21/26（漏 `deepseek.com` / `kimi.com` / `volces.com` / `didi.com`） |

⇒ **覆盖是双峰的**：主流站点几百条就够，其余 99.5% 是长尾国内站。用小表 = 你随机撞到的国内小站（尤其视频/CDN 边缘）会被塞进境外代理。

```bash
"<venv>/Scripts/python.exe" self-conf-skills/run/egern/weigh_ruleset.py <大表> --sub <小表> --probe www.jd.com --probe api.deepseek.com
```

**结论模板**：内存代价 20 MB 级（iPhone 上 0.5%，无感；RAM < 256 MB 的路由器要留意，叠加广告表后是 +45 MB 量级）；换来的是国内域名直连。**不值得为省这 20 MB 牺牲分流**；真正的大头往往是广告表（本项目里那份 199,781 条 / +24.7 MB 比 ChinaMax 还大，且更可控）。

---

## mihomo · 规则集重量（clash 侧）

> **何时读**：用户问「规则集是不是太多 / 太重」、要换掉或新增一份规则集、
> 想知道「为什么 AI 用了两份集」、或要判断某个远程集能不能用时。
>
> 本文只讨论**体量与覆盖度**：一份集有多大、接住了多少、漏了什么、代价是什么。
> `rule-providers` 的三种 `format × behavior` 组合与键语义见
> [`profiles/<kern>.md`](./profiles/clash.md) §9；门禁命令与退出码见
> [`gates.md`](./gates.md)；上游供应链评估见 [`gates.md`](./gates.md) §9。
>
> **本文的中心结论**：规则集的"重量"不是条数，是**覆盖面与落点的正确性**。
> 本仓真实发生过的一次事故不是"集太大"，而是**一份 188 条的集漏了 94 条伴生域** ——
> 漏掉的那些请求从另一个出口出去，触发了风控（§3）。

#### 1 · 规模概览：25 份与 10 份

两条产品线共用同一套规则集仓库，但**取用份数差一倍以上**：

| profile | 规则集份数 | 规则条数 | 策略组 | 生成源 |
|:--|:--:|:--:|:--:|:--|
| `clash/profiles/routing.yaml` | **25** | **27** | 25 | `override/my_clash.js` |
| `clash/profiles/lazy.yaml` | **10** | **11** | 3 | `override/my_clash_lazy.js` |

两份文件都由 `self-conf-skills/run/clash/build_profiles.py` 生成，头注里的"规模"行
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

#### 1.1 一个反复出现的头注错误

`lazy.yaml` 的头注曾写「5 份 MRS + 5 份 yaml」，实际是 **6 份 mrs + 4 份 yaml**
（见 [`profiles/<kern>.md`](./profiles/clash.md) §18.4）。

**教训**：手写的规模描述一定会漂移。凡是可以由解析结果算出来的数字，
就让脚本写进头注，不要在注释里手抄。本文所有份数与条数均以
`yaml.safe_load` 解析为准。

---

#### 2 · 分流版 25 份清单表

来源自 `clash/profiles/routing.yaml` 的 `rule-providers` 段（解析结果，非手抄）。
**刷新周期全部是 `interval: 86400`（24 小时）**，无一份例外。

#### 2.1 MRS 格式（20 份 = MetaCubeX 19 + AWAvenue 1）

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

#### 2.2 本仓自托管 yaml（3 份）

| # | 名称 | behavior | format | 条目数 | 真源 | 落点 |
|:-:|:--|:--|:--|:--:|:--|:--|
| 21 | `emby` | classical | yaml | **4** | `rules/emby.list` | Emby |
| 22 | `AI_Domains` | classical | yaml | **272** | `rules/AI.list` | AI |
| 23 | `apple-system` | classical | yaml | **18** | `rules/apple_system.list` | DIRECT |

这 3 份的条目数是**确定的** —— 它们是本仓自己维护的静态文件，不随上游变化。

#### 2.3 Jinx（2 份）

| # | 名称 | behavior | format | 条目数 | 落点 |
|:-:|:--|:--|:--|:--|:--|
| 24 | `Jinx-CN` | classical | yaml | 现抓 | DIRECT |
| 25 | `Jinx-Ads` | classical | yaml | 现抓 | AD |

三类合计 **20 + 3 + 2 = 25 份**，与 `rule-providers` 的键数一致。

#### 2.4 关于"条目数"这一列的纪律

> ⚠️ **除本仓自托管的 3 份外，条目数一律不写死精确数字。**
> 这些集都没锁 commit（`cdn.jsdelivr.net/gh/...@meta`、`raw.githubusercontent.com/.../main`），
> 上游滚动更新，写死的数字很快过期 —— 这与 Surge 侧
> [`rulesets.md`](./rulesets.md) §2.2 的口径一致。
>
> **唯一例外**是 §7 的覆盖度对比，那里的数字是**一次实测的结论**，
> 必须带日期与快照路径记录，因为它是论证的一部分，不是规模描述。

---

#### 3 · 懒人版 10 份清单表

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

#### 3.1 与分流版的差集（15 份）

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
相关讨论见 [`ops.md`](./ops.md)。

**⇒ 判据：删规则集时，要同时检查它后面那条规则的 `no-resolve` 是否还成立。**
砍掉一条规则会改变前序集合的构成，进而改变后续 IP 规则的行为。

---

#### 4 · 四类来源的分类

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

#### 4.1 为什么"来源"这一维重要

因为它决定了**出问题时找谁**：

- `cn.mrs` 突然变空 → MetaCubeX 上游问题 → 只能等或换源；
- `AI_Domains.yaml` 404 → **本仓问题**（文件被删、仓改名、分支改名）→ 立刻可修；
- `Jinx-CN.yaml` 变空 → 姊妹仓问题 → 需要跨仓协调。

⇒ 判据：**自托管的 3 份是唯一"出事能自己修"的**。这也是 §8 的取舍基础。

---

#### 5 · 为什么有的用 MRS、有的用 yaml

#### 5.1 硬约束：`mrs` 只支持两种 behavior

`mrs`（Meta Rule Set）是**二进制容器**，里面只能装两类内容：

| behavior | 装什么 | 本仓份数 |
|:--|:--|:--:|
| `domain` | 纯域名集合（无类型前缀，全是裸域名/后缀） | 16 |
| `ipcidr` | 纯 CIDR 集合 | 4 |

**它装不下"带规则类型的行"** —— 也就是装不下 `DOMAIN-SUFFIX,xxx`、
`DOMAIN-KEYWORD,xxx`、`URL-REGEX,xxx` 这种**完整规则行**。

#### 5.2 所以：classical 行为必须用 yaml

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
（后果细节见 [`profiles/<kern>.md`](./profiles/clash.md) §9.4。）

#### 5.3 一张选型表

| 你的 payload 是 | 用 format | 用 behavior |
|:--|:--|:--|
| 纯域名/后缀列表（裸 `example.com`） | `mrs`（或 `text`/`yaml` + domain） | `domain` |
| 纯 CIDR 列表 | `mrs` | `ipcidr` |
| 完整规则行（`DOMAIN-SUFFIX,x` / `DOMAIN-KEYWORD,x` / `URL-REGEX,x`） | `yaml` / `text` | `classical` |

---

#### 6 · 覆盖度是怎么量出来的

这是本文最需要说清的方法论。Surge 侧
[`rulesets.md`](./rulesets.md) 的核心判据是
「**数域名条目，不是看名字**」；Egern 侧
[`rulesets.md`](./rulesets.md) 是
「**按覆盖率判，绝不能按体积判**」。mihomo 侧沿用的是后者的思路，
但**量的对象不同**：不是"大表 vs 小表"，而是"**上游通用集 vs 本仓整合集**"。

#### 6.1 三个层次的覆盖度

| 层次 | 问的问题 | 怎么量 |
|:--|:--|:--|
| **条目数** | 这份集有多少条 | 数 payload 行数 |
| **命中率** | 随机抽 N 个真实域名，命中几条 | 抽样对拍 |
| **差集** | A 集有、B 集没有的是哪些，那些是什么 | 求差集并**人工分类** |

⚠️ **只有第三层有意义。** 条目数会被冗余条目虚增（本仓 `AI.list` 就曾
318 → 286 → 272 两次归并，条目少了 46 条但**匹配行为零变化**，
见 `rules/AI.list` 头注"六修/七修"）；命中率会被抽样偏差带偏。
**差集 + 人工分类**才能回答"漏的是什么、后果是什么"。

#### 6.2 求差集时必须做的两件事

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

#### 7 · 覆盖度实测：AI 组为什么用两份集

这是本仓**唯一一份同时引用两个 AI 规则集**的设计，也是本文的重点。

#### 7.1 现象

`routing.yaml` 与 `lazy.yaml` 都有这两条相邻规则：

```yaml
  - RULE-SET,category-ai-chat-!cn,AI     # MetaCubeX，188 条
  - RULE-SET,AI_Domains,AI               # 本仓自托管，272 条
```

**两条都指向 `AI` 组。** 既然落点相同，为什么不是二选一？

因为**它们互相漏**，而且漏的方向不同。

#### 7.2 实测（2026-10-01 快照对拍）

| 项 | 数值 |
|:--|:--|
| A = 本仓 `rules/AI.list`（→ `AI_Domains.yaml`） | **272 条**（其中 271 条域名类 + 1 条 `URL-REGEX`） |
| B = MetaCubeX `category-ai-chat-!cn` | **181 条**（本仓快照 `self-conf-skills/run/ai_sources/meta-ai.list` 实测）/ **188 条**（历史记录值） |
| A ∩ B（B 能接住的 A 条目） | **177 条** |
| **A − B（B 漏掉的）** | **94 条** |
| B − A（A 漏掉的） | **4 条** |

> ⚠️ **181 vs 188 的差异**：188 是历史记录的读数，181 是本仓
> `self-conf-skills/run/ai_sources/meta-ai.list` 快照的实测值（2026-10-01 抓取）。
> **该快照是上游的一次抓取，不随上游滚动更新**（`--check` 不覆盖它，见 §9.3）。
> 引用"188"时请注明它是历史值；要现数请重新抓
> `cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo/geosite/category-ai-chat-!cn.mrs`。
> 无论取 181 还是 188，**"漏掉 94 条"这个结论的量级不变**。

#### 7.3 漏掉的 94 条是什么

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

#### 7.4 漏掉伴生域的两个后果

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

#### 7.5 那反过来呢：本仓 272 条漏了上游什么

**只有 4 条。** 这个方向的差集很小，原因是本仓 `AI.list` 的生成器
（`self-conf-skills/run/ai_domains_build.py`）**把 MetaCubeX 当作 10 个上游源之一**
（源列表里的 `meta-ai.list`，标签 `MetaCubeX geosite category-ai-!cn`）。

也就是说：**272 条是"10 源整合"，181/188 条是"其中 1 源"。**
整合集覆盖单源，差集小是设计使然；单源覆盖不了整合集，差集大也是设计使然。

⚠️ **这不意味着"用大集就安全"。** 大集的条数里有一部分是冗余
（历史上 318 → 272 的两次归并就是消冗余），
而单源集里**有一些是整合集刻意剔除的**（黑名单，见 §7.6）。
两边都不是"全集"，所以 §7.2 的两个方向都要量。

#### 7.6 272 条里被**刻意**剔除的

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

#### 8 · 自托管 vs 跨仓引用

#### 8.1 本仓的选择：自托管（各存一份）

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

#### 8.2 自托管的代价：人工同步

这是本仓**明确接受**的代价：

> ⚠️ **外部仓库的同类资产更新后，本仓不会自动跟随** —— 自托管的代价是人工同步。
> 需要人工同步。

具体地：

- `rules/*.list` 是本仓的**唯一真源**；原仓的同名文件更新了，本仓**不知道**；
- `build_rules.py --check` 只检查「`.yaml` 是否落后于本仓的 `.list`」，
  **不检查「本仓的 `.list` 是否落后于原仓」**（它没法检查，原仓不在本仓视野内）；
- 因此同步动作是**人工的**：diff 两个仓的 `.list`，确认后手工合并，重跑生成器。

#### 8.3 为什么还是选自托管

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

#### 9 · 生成链路与 `--check` 防过期

#### 9.1 链路

```text
rules/AI.list              ← 唯一真源（Surge ruleset 格式）
    │                         ↑ 由 self-conf-skills/run/ai_domains_build.py 从
    │                           self-conf-skills/run/ai_sources/ 的 10 份上游快照整合而来
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

#### 9.2 生成物是自证的

生成的 `.yaml` 头部写明了真源与条数：

```yaml
#
#
#
```

⚠️ 最后一行是**给引用方的关键提示**：这 3 份自托管集**零 IP 条目**，
所以在 `rules:` 里引用它们时**不需要**（也不应该）加 `no-resolve`。
这与 §3.1 讨论的 `geoip-*` 正好相反 —— `no-resolve` 只对 IP 类规则有意义。

#### 9.3 `--check` 检查什么、不检查什么

```bash
python self-conf-skills/run/clash/build_rules.py           # 生成
python self-conf-skills/run/clash/build_rules.py --check   # CI 用：过期即判负（退出码 1）
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

- `self-conf-skills/run/ai_sources/` 里的 10 份快照（含 `meta-ai.list`）**不会自动刷新**。
  要更新得手工重抓上游，再跑 `ai_domains_build.py`。
  **⇒ 这也解释了 §7.2 里 181 与 188 的差异：快照停在 2026-10-01。**
- 语义正确性（黑名单是否合理、新收的域会不会误伤）**只能人工审**。
  `AI.list` 头注里的"一修/二修/…/七修"记录就是这套人工审计的留痕。

**⇒ 判据：`--check` 防的是"生成物过期"，不是"真源过期"。**
真源过期没有自动化防线，靠的是维护者记得跑一次上游 diff。

---

#### 10 · 刷新周期与失效风险

#### 10.1 现状：全部 86400

25 份（分流版）/ 10 份（懒人版）**无一例外**都是 `interval: 86400`（秒，= 24 小时）。

| 特性 | 值 | 含义 |
|:--|:--|:--|
| 单位 | 秒 | `86400` = 24 小时，**不是**毫秒也不是分钟 |
| 触发时机 | 内核启动 + 每 24 小时 | 不是"用到才刷" |
| 失败行为 | 保留旧缓存继续跑 | **不会**因为刷新失败就清空规则集 |

⚠️ 最后一条是**关键的安全阀**：如果上游挂了，mihomo 用上一份缓存继续工作，
而不是让整份集变空（变空意味着该集的规则全部失效 → 流量落到 `MATCH`）。
所以"上游 404"通常表现为**规则集静默变旧**，不是明显的断网。

#### 10.2 86400 的实际风险

**风险一：新域要等最多一个周期。**

一个 AI 服务今天上线了新域名，最坏情况下要等 24 小时才被接住。
期间它走 `MATCH,Proxy` —— 也就是 §7.4 的"出口不一致"场景，只是范围更小。

**风险二：上游恶意/错误更新有 24 小时传播窗。**

`@meta` 与 `main` 都是**移动分支**，不可钉 commit（MRS 是二进制且走
jsDelivr 分支地址，没有 commit hash 可钉）。
上游一旦推了错误内容，本仓用户最多 24 小时内全部收到。
这是 [`gates.md`](./gates.md) §9 供应链评估要覆盖的场景。

**风险三： Refresh 失败无告警。**

刷新失败不会弹窗、不会写显著日志。判断一份集是不是已经很旧，
要看 `rule_provider/` 目录下文件的 mtime。

#### 10.3 为什么不再拉长

Surge 侧 [`rulesets.md`](./rulesets.md) §5.3
提到「给远程集加 `update-interval` 拉长」可以减负，本仓**没有这么做**：

- mihomo 的 `interval` 只控制**刷新频率**，不影响内存与匹配开销（§11），
  拉长它**省不下任何可观测的资源**；
- 代价却是实打实的：新域等待时间变长。

**⇒ 判据：拉长 `interval` 只在"刷新本身造成可观测负担"时才划算
（极慢的网络、按流量计费的链路上）。**
本仓的 25 份集加起来是 MB 级（§11），一天一次不构成负担。

---

#### 11 · 体量的真实代价：内存与匹配

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

#### 11.1 与 Surge 侧的口径差异

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

#### 12 · FAQ · 维护者须知

#### 12.1 FAQ

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
[`rulesets.md`](./rulesets.md) §4 有同类说明。

**Q：我只改了 `rules/AI.list`，需要改三个内核吗？**

改真源即可，然后跑 `build_rules.py`。Surge / Egern 直接消费 `.list`，
mihomo 消费生成的 `.yaml`。**不要手工改两份** —— 见
[`profiles/<kern>.md`](./profiles/clash.md) §13。

**Q：`--check` 通过了，是不是说明规则集是最新的？**

**不是。** `--check` 只证明"`.yaml` 没落后于本仓的 `.list`"（§9.3）。
它不检查：本仓 `.list` 是否落后于原仓、是否落后于那 10 份上游快照。
后者是**人工流程**，没有自动化防线。

**Q：能不能把 `interval` 改成 604800（一周）省点流量？**

技术上可以，但不划算（§10.3）：`interval` 不影响内存与匹配开销，
省不下可观测资源，代价是新域等待一周。
Surge 侧取一周是因为那里有具体理由，**本仓没有**，所以保持 86400。

**Q：`lazy.yaml` 头注说 5 份 MRS + 5 份 yaml，实际是 6 + 4，这是 bug 吗？**

是头注手写数字的漂移，已记录（[`profiles/<kern>.md`](./profiles/clash.md) §18.4）。
规则集本身没错，错的是注释。**⇒ 凡可解析算出的数字，别手抄进注释。**

**Q：本仓 25 份会不会比 Egern 那份 111k 条的表还重？**

不会。Egern 侧单份 `ChinaMax_All_No_Resolve` 就是 111,332 条 / 3.42 MB / +22.6 MB；
本仓 25 份合计远不到这个量级 —— **本仓没有引入任何十万条目级的国内域名全量表**（§11）。

**Q：上游 404 了会怎样？**

不会断网。mihomo 刷新失败时**保留旧缓存继续跑**（§10.1），
所以表现为"规则集静默变旧"，需要看 `rule_provider/` 下文件的 mtime 才能发现。

#### 12.2 维护者须知

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

相关：[`profiles/<kern>.md`](./profiles/clash.md) §9 ·
[`gates.md`](./gates.md) · [`ops.md`](./ops.md) ·
[`gates.md`](./gates.md) §9 · [`profiles/<kern>.md`](./profiles/clash.md) ·
[`rulesets.md`](./rulesets.md) ·
[`rulesets.md`](./rulesets.md) ·
[`AGENTS.md`](../../AGENTS.md) · [`../../../README.md`](../../README.md)
