# 规则集与来源

> 这一页是组件清单：用了哪些规则集、各自从哪来、按什么顺序生效。
> **三内核（Surge / Egern / mihomo）共用的是分流意图，不是规则集文件** —— 分工见 §0。
> 条数一律现抓（本仓纪律：写死的数字必然过期）：
> `python skill/tests/sync_docs.py --check` 会把本节与配置对拍。
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
> [`../surge/ruleset-weight.md`](../surge/ruleset-weight.md) ·
> [`../egern/ruleset-weight.md`](../egern/ruleset-weight.md) ·
> [`../clash/ruleset-weight.md`](../clash/ruleset-weight.md)（mihomo）。
> 本页只做**三内核对照与共用真源**这一层，不重复那份清单。

## 0 · 先分清一件最重要的事：共用的是「内容」，不是「文件」

这是三内核整合仓最容易误判的一处。三个内核引用规则集的方式**分属两套文件体系**：

| | Surge | Egern | mihomo（clash） |
|:--|:--|:--|:--|
| 规则集文件形态 | `.list` / `.txt`（**Surge 原生文本**） | 同左（可直接消费 Surge 格式） | **`.mrs`（MetaCubeX 二进制，分流版 20 份）+ `.yaml`（5 份）** |
| URL 写在哪 | 直接写在 `RULE-SET,<URL>,<策略>` | `rule_set.match` | 先在 `rule-providers` 声明名字 / `format` / `behavior` / `path` / `interval`，规则里**按名字**引用 |
| 条数纪律 | 一律不写死 | 一律不写死 | 自托管 3 份可写死（本仓静态文件），远程集不写死 |

⇒ **把 `.list` 的 URL 直接塞进 mihomo 的 `RULE-SET` 名字位是错的**；
反过来把 `.mrs` 给 Surge 也读不动。**三内核共享的是"要接住哪些域名、按什么顺序接"这个语义层。**

### 0.1 唯一的例外：三内核真正共用的那 3 份

本仓自托管的 `rules/*.list` 是**唯一真源**，三个内核都吃它 —— 但**吃的不是同一份文件**：

```text
rules/AI.list             （272 条 —— 条数以该文件头注「合计」行为唯一真源）
rules/apple_system.list   （18 条）
rules/emby.list           （4 条）
   │
   ├─ Surge  ── 直接消费 .list（原生）
   ├─ Egern  ── 直接消费 .list（原生）
   └─ mihomo ── 由 skill/scripts/clash/build_rules.py 生成 .yaml 后再消费
```

```bash
python skill/scripts/clash/build_rules.py           # 生成
python skill/scripts/clash/build_rules.py --check   # CI 用：过期即判负
```

`.yaml` 是**生成物**，禁止手工编辑（改真源 `.list` 后重跑）。
整合前两仓各存一份（内容逐条相同）⇒ 改一处忘一处就漂移；单一真源后物理上不可能漂移。

> 📌 `rules/AI_Domains.yaml` / `apple_system.yaml` / `emby.yaml` 的头部都写着真源名与条数，
> 且标注「纯域名集、零 IP 条目 ⇒ 引用方**不写**规则级 `no-resolve`」—— 这条提示对三内核都成立。

### 0.2 为什么 mihomo 那份是 `.mrs` 而不是 `.list`

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
[`../clash/profile-anatomy.md`](../clash/profile-anatomy.md) §9。）

## 1 · Surge / Egern 共用规则集

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
| `AI_Domains`（本仓自托管） | → `AI`（伴生域/宽后缀/基础设施域，**必须紧跟 `AI.list`**） | ✅ | ✅ | 本仓 `rules/AI.list`（静态整合 · 生成器 `skill/scripts/ai_domains_build.py`；条数与来源见该文件头部档案） |
| `Spotify.list` · `YouTubeMusic.list` · `YouTube.list` | 各自应用组 | ✅ | ✅ | [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) |
| `GitHub.list` | → **`Proxy` 直指**（2026-10-05 起不再单设 `GitHub` 组） | ✅ | ✅ | 同上 |
| `Google.list` · `Microsoft.list` | 各自应用组 | ✅ | ✅ | 同上 |
| `Telegram.list` · `Twitter.list` | 各自应用组 | ✅ | ✅ | 同上 |
| `apple.txt` | Apple 在中国大陆可直连的域名 → `DIRECT` | ✅ 仅分流版 | ✅ 仅分流版 | [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules)，与 `direct.txt` **同仓库同 release 同格式**。**纯域名、零 IP**（条数随上游更新，一律现抓）⇒ 不写规则级开关（第 4 节 4b）。懒人版 2026-09-24 起不引用只留内置 `SYSTEM`；分流版 2026-10-04 起由 `Apple_All_No_Resolve.list`（1,616 条）换入 |
| `Proxy.list` | 常用代理名单 | 注释态，不参与匹配 | 注释态，不参与匹配（2026-09-24 起与 Surge 同写法；原先是 `disabled: true`，那条仍占 `rules` 的一位） | 同上 |
| `GEOIP,CN` / `geoip: CN` | 国内 IP 段 | `DIRECT` `no-resolve` | `DIRECT` `no_resolve` | Surge：`GeoLite2-Country.mmdb` · [adysec/IP_database](https://github.com/adysec/IP_database)；Egern：`Country.mmdb` + `GeoLite2-ASN.mmdb` · [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) |

## 2 · 只有一侧有的（Surge / Egern 之间）

| 规则集 | 只在哪侧 | 原因 |
|:-------|:---------|:-----|
| `LAN`（内置） | 仅 Surge | Surge 有内置局域网规则集 |
| `Lan.list` | 仅 Egern | Egern 无内置 LAN，引用 [blackmatrix7](https://github.com/blackmatrix7/ios_rule_script) 的清单补位。与 `private.txt` **互补**：`Lan` 管 IP 段与路由管理域，`private` 管特殊 TLD 与 `miwifi.com` |
| `SYSTEM`（内置）→ 快照 `apple_system.list` | Surge 内置 ／ Egern 引用快照 | 系统服务 → `DIRECT`。2026-09-24 起两侧同一位置各有一套：Egern 没有内置系统集，引用 [`../rules/apple_system.list`](../../../rules/apple_system.list)（2026-09-27 起自 `egern/` 根提升到顶层 `rules/`，两侧文件夹布局就此对称）—— 内容 = 内置 `SYSTEM` 的 2026-09-24 时点快照，删掉 Egern 不支持的两条 `PROCESS-NAME`（`trustd` / `netbiosd`） |
| ~~`domain_suffix: cn`~~ | 两侧均已删除 | 2026-09-24 懒人版也删了。理由与分流版 v3 同：`direct.txt` 本身含 `DOMAIN-SUFFIX,cn`（2026-09-24 快照第 23,829 行），留着只会把「规则集没接住」掩盖成「cn 直连正常」 |

✅ **懒人版两侧现已逐位同构**：各 10 条，白名单 → 广告 ×2 → 内网 ×2 → 系统集 → AI → 国内直连 → 地理 → 兜底。
剩余差异只剩写法与内核能力：广告策略（Surge 字面量 `REJECT` ／ Egern `AD` 组）、内置 `LAN` ↔ `Lan.list`、
内置 `SYSTEM` ↔ 本仓快照、`FINAL` ↔ `default`。Apple 全量集与 `.cn` 后缀兜底两侧现在**都没有**。
逐项差异见 [`cross-kernel-diff.md`](cross-kernel-diff.md) 第 4 节。

## 3 · 匹配顺序（Surge / Egern 基准序）

自上而下，第一条命中即决定去向。分流版两侧 26 条**逐位对齐**（仅第 3 节的三处引擎差异例外）。
⚠️ 本节是 **Surge / Egern 的基准序**；mihomo 分流版是 **27 条**、另一套顺序，见 §5.1 与
[`cross-kernel-diff.md`](cross-kernel-diff.md) §3。

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

## 4 · 排序与选材约束（改动前逐条确认）

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
4. **IP 类规则排最后，且必须带 `no-resolve` / `no_resolve`** —— 否则每个走到它的域名都会被强制本地解析一次，那正是泄露来源。详见 [`no-resolve-pairing.md`](no-resolve-pairing.md)。
4b. ⭐ **规则级开关的取舍，六份 profile 共用一条原则**：**实测零 IP 条目的规则集不写，真含 IP 条目的必须写**。
    该开关只对规则集里的 IP 类条目起作用，纯域名集写上是空转 —— 本仓 2026-09-24 起把它从 12 条零 IP 规则上删掉。
    ⚠️ 判据是「实测零 IP」不是「纯域名」（`YouTube Music` 有 UA、`Microsoft` 还有 PROCESS-NAME，同样零 IP），
    且这些 URL 没锁 commit ⇒ 每次由 `audit_ruleset_content.py`（Surge）/ `audit_ruleset_noresolve.py`（Egern）重测。
    **三内核落点不同**，见 [`no-resolve-pairing.md`](no-resolve-pairing.md)：
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

## 5 · mihomo（clash）侧：另一套文件，同一套意图

> 本页 §1–§4 讲的是 Surge / Egern 的 `.list` 世界。mihomo 侧**自成一套**，以下数字全部由
> `yaml.safe_load` 解析 `clash/profiles/*.yaml` 现算（2026-10-08 复核），**不手抄头注**。
> 清单表、体量实测与选型决策见 [`../clash/ruleset-weight.md`](../clash/ruleset-weight.md)（体量与覆盖度）
> 与 [`../clash/ruleset-sources.md`](../clash/ruleset-sources.md)（来源与选型）——**本页不重复那份清单**。

### 5.1 规模：25 份 / 10 份（不是 24 / 9）

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
   [`../clash/profile-anatomy.md`](../clash/profile-anatomy.md) §18.4）。
   ⇒ 凡是可由解析算出的数字，别手抄进注释。

### 5.2 来源四分（分流版）

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

### 5.3 刷新周期：`interval: 86400`，与 Surge / Egern 的 604800 不一致是**刻意的**

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
（本仓踩过 Jinx 上游改名导致 404 的那一遭）⇒ 由 `skill/tests/clash/check_remote_urls.py` 定期问（慢，按需跑）。

### 5.4 mihomo 分流版 27 条的顺序（与 Surge / Egern 的 26 条**不是逐位同构**）

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

### 5.5 ⭐ 两个 AI 集：mihomo 侧独有的"双保险"

`category-ai-chat-!cn`（远程滚动）与 `AI_Domains`（本仓自托管 272 条）**都落 `AI` 组**，
两个内核侧也有同名的一对（`AI.list` Repcz + 本仓 `AI_Domains`），**形态一致、理由同源**：

- `AI_Domains`（272 条）= **10 源人工整合快照**，覆盖度更高；
- `category-ai-chat-!cn`（181 / 188 条）= **每 24 小时自动刷新**，能接住"两次人工整合之间"新出现的域。

⚠️ 二者**互相漏，且漏的方向不对称**（实测差集：上游漏本仓 **94 条**伴生域，本仓只漏上游 **4 条**）。
漏掉的 94 条多为认证 / 遥测 / 风控 / 通用网关类**伴生域**（`auth0.com` `statsig.com`
`apis.google.com` `challenges.cloudflare.com` …）—— 后果是**同一次会话里请求走了不同出口，触发风控**。
详见 [`../clash/ruleset-weight.md`](../clash/ruleset-weight.md) §7。

### 5.6 三条 mihomo 专属纪律

1. **`.mrs` 与 `yaml` 不可互换**：`mrs` 只装 `domain` / `ipcidr`，装不下带类型的规则行。
   需要 `DOMAIN-KEYWORD` / `URL-REGEX` / 精确 `DOMAIN` 的集合**必须**是 `yaml` + `classical`
   （本仓 5 份：3 份自托管 + Jinx 2 份）。
2. **`no-resolve` 按 `behavior` 判，不按名字**：`ipcidr` ⇒ 必须写；`domain` ⇒ 写了无意义；
   `classical` ⇒ 内容混合、静态判不出（本仓自托管 3 份实测零 IP）。
   由 `skill/scripts/clash/check_clash_dns.py` 判据 ⑩ 守。
3. **零 dat 依赖**：本仓 mihomo 侧**不用** `geosite.dat` / `geoip.dat`，全部走远程 `.mrs` / `.yaml`
   （原生 `GEOSITE` / `GEOIP` 规则已从分流版全部替换为 `RULE-SET`）。
   ⚠️ 这不排斥 `.mrs` —— 它们是独立远程集文件，与 dat 数据库无关。判据 ⑪ 守。

## 6 · 素材与许可

| 素材 | 用途 | 来源 |
|:-----|:-----|:-----|
| 策略组图标（`icons/*.png`，条数一律现抓：`ls icons/*.png \| wc -l`） | 面板图标（**三内核共用同一份**） | [RiverFlowsInUUU/Rule](https://github.com/RiverFlowsInUUU/Rule) · [jnlaoshu/MySelf](https://github.com/jnlaoshu/MySelf) · [Koolson/Qure](https://github.com/Koolson/Qure)。三者均已归档，**仅作署名归属**；实际使用的图标已**下载整合进本仓** `icons/`，运行时不依赖上游 |
| `icons/icons.json` | 图标订阅（**纯本仓**，永不失效） | 本仓派生 |
| `icons/icons-full.json` | 图标订阅（**大集成**＝本仓 + 上游全量） | 本仓 + 上述两个上游仓库，⚠️ 标「上游」的条目为**外部引用**、靠第三方在线 |
| `GeoLite2-Country.mmdb` | Surge 侧 `GEOIP` 判定 | [adysec/IP_database](https://github.com/adysec/IP_database) |
| `Country.mmdb` · `GeoLite2-ASN.mmdb` | Egern 侧 `geoip` / `asn` 判定 | [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) |
| （无 dat 依赖） | mihomo 侧 `geoip-*` 判定 | **零 dat**：4 份 `ipcidr` 集全部走远程 MetaCubeX `.mrs`，见 §5.6 |

本仓按 MIT 许可分发（根 `LICENSE`）；图标来源见上表。第三方规则集版权归其原作者。

> ⚠️ **上游图标仓库的许可状态**：`RiverFlowsInUUU/Rule` · `jnlaoshu/MySelf` · `Koolson/Qure` 三者**均未声明 SPDX 许可**（GitHub 上 `license` 字段为空）且**均已归档**。因此本仓只把它们的图标「下载整合」作为素材来源（本仓自有文件按 MIT 分发），`icons-full.json` 里对上游的**外部引用**则属风险自担 —— 上游删仓/转私有即失效，见 [`boundaries.md`](boundaries.md) 的登记。

---

相关：[`cross-kernel-diff.md`](cross-kernel-diff.md) · [`troubleshoot-faq.md`](troubleshoot-faq.md) · [`../README.md`](../../../README.md)
-weight.md) · [`../clash/ruleset-sources.md`](../clash/ruleset-sources.md) ·
[`../clash/profile-anatomy.md`](../clash/profile-anatomy.md) §9 · [`../../../README.md`](../../../README.md)
