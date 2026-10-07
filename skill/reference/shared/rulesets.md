# 规则集与来源

> 这一页是组件清单：用了哪些规则集、各自从哪来、按什么顺序生效。
> 两内核共用同一批远程规则集，**条数一律现抓**（本仓纪律：写死的数字必然过期）：
> `python skill/tests/sync_docs.py --check` 会把本节与配置对拍。
> **Egern 独有 2 项** —— `Lan.list` 与 `apple_system.list`，各用来补 Surge 的一个内置集合（内置 `LAN` / `SYSTEM`），
> 这是两内核引用 URL **不逐字相同**的唯一原因（其余全部相同）。
>
> 引用位口径（数的是 `rules` 段里指向规则集的条目，同一份规则集被两条规则各引用一次就占两位）：
> 分流版 **<!-- auto:ruleset-refs -->24<!-- /auto:ruleset-refs --> 条规则集引用**。
> 懒人版 **9 条规则集引用**。
> 这两个数以本文件与两侧 profile 的现算为准，别混。

## 1 · 共用规则集

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

## 2 · 只有一侧有的

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

## 3 · 匹配顺序

自上而下，第一条命中即决定去向。分流版两侧 26 条**逐位对齐**（仅第 3 节的三处引擎差异例外）。

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
4b. ⭐ **规则级开关的取舍，四份 profile 共用一条原则**：**实测零 IP 条目的规则集不写，真含 IP 条目的必须写**。
    该开关只对规则集里的 IP 类条目起作用，纯域名集写上是空转 —— 本仓 2026-09-24 起把它从 12 条零 IP 规则上删掉。
    ⚠️ 判据是「实测零 IP」不是「纯域名」（`YouTube Music` 有 UA、`Microsoft` 还有 PROCESS-NAME，同样零 IP），
    且这些 URL 没锁 commit ⇒ 每次由 `audit_ruleset_content.py`（Surge）/ `audit_ruleset_noresolve.py`（Egern）重测。
    **两内核落点不同**：Surge 能写在规则级，Egern 的 `no_resolve` 只适用 `geoip`/`ip_cidr`/`ip_cidr6`/`asn`，
    写在 `rule_set` 上不生效 ⇒ Egern 的这层防线在**规则集文件里**（条目级 `,no-resolve`）。
5. ⭐ **用 `*_No_Resolve` 变体，并下载下来数条目**。`Apple_All.list` 实测含 13 条不带 `no-resolve` 的裸 IP（Apple CDN 网段），
   一条这样的条目就让**每个走到该规则的域名**都被强制解析一次。判据是"下载 + 数条目"，**不是看规则集名字**
   （`ChinaMax.list` 名字像域名集，2026-09-24 快照里 **IP 类条目 12,472 条、域名类只有 64 条**）。
   （本仓 Apple 那条 2026-10-04 起已换成零 IP 的 `apple.txt`，此处保留 `Apple_All.list` 作判据示例。）
6. **两条广告清单的策略与参数必须逐字相同**，否则同一广告域名因命中不同清单而进出不一致。

> 🛡️ 本仓自托管的 `rules/apple_system.list` 没有第三方刷新审计 ⇒ 漂移只能靠人：Surge 大版本更新时把内置 `SYSTEM` 与这份快照比对一次
> （这份快照同时是 `audit_routing_coverage.py` 里 `SYSTEM` 那条内置集的判定依据，见该脚本的 `BUILTIN_SET_SNAPSHOTS`）。

## 5 · 素材与许可

| 素材 | 用途 | 来源 |
|:-----|:-----|:-----|
| 策略组图标（`icons/*.png`，条数一律现抓：`ls icons/*.png \| wc -l`） | 面板图标（两内核共用同一份） | [RiverFlowsInUUU/Rule](https://github.com/RiverFlowsInUUU/Rule) · [jnlaoshu/MySelf](https://github.com/jnlaoshu/MySelf) · [Koolson/Qure](https://github.com/Koolson/Qure)。三者均已归档，**仅作署名归属**；实际使用的图标已**下载整合进本仓** `icons/`，运行时不依赖上游 |
| `icons/icons.json` | 图标订阅（**纯本仓**，永不失效） | 本仓派生 |
| `icons/icons-full.json` | 图标订阅（**大集成**＝本仓 + 上游全量） | 本仓 + 上述两个上游仓库，⚠️ 标「上游」的条目为**外部引用**、靠第三方在线 |
| `GeoLite2-Country.mmdb` | Surge 侧 `GEOIP` 判定 | [adysec/IP_database](https://github.com/adysec/IP_database) |
| `Country.mmdb` · `GeoLite2-ASN.mmdb` | Egern 侧 `geoip` / `asn` 判定 | [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) |

本仓按 MIT 许可分发（根 `LICENSE`）；图标来源见上表。第三方规则集版权归其原作者。

> ⚠️ **上游图标仓库的许可状态**：`RiverFlowsInUUU/Rule` · `jnlaoshu/MySelf` · `Koolson/Qure` 三者**均未声明 SPDX 许可**（GitHub 上 `license` 字段为空）且**均已归档**。因此本仓只把它们的图标「下载整合」作为素材来源（本仓自有文件按 MIT 分发），`icons-full.json` 里对上游的**外部引用**则属风险自担 —— 上游删仓/转私有即失效，见 [`boundaries.md`](boundaries.md) 的登记。

---

相关：[`cross-kernel-diff.md`](cross-kernel-diff.md) · [`troubleshoot-faq.md`](troubleshoot-faq.md) · [`../README.md`](../../../README.md)
