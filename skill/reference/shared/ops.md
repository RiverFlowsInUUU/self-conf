# 操作：Surge · Egern · mihomo · 日常维护

> 由原手册 03、04、06 三章合并。装完之后怎么改、怎么维护，都在这一篇。
> mihomo 章是整合后新增 —— 那一侧的目录与生成链跟 Surge / Egern **不是同一套**
> （配置真源是覆写脚本，不是静态 profile），动手前先读 §5.2 的动线。

## 三侧共通：动手前先记住五条

三个内核目录并列（`surge/` · `egern/` · `clash/`），各写各的语法，但**操作层的规矩是共通的**。
下面五条先记住，再翻到对应内核那一章；各侧独有的东西（文件结构、改配置的动线、生成器）在各自章里。

| # | 规矩 | 落点 |
|:-:|:-----|:-----|
| 1 | **固定名四件**：每侧现役只有 `routing` / `lazy` × 完整版 / `.min` 共四件，订阅地址不随版本改名 | 三侧一致，见 §6.1 |
| 2 | **`.min` 不手工编辑**：它是"同一份配置去掉注释"，漂了肉眼看不出来 | Surge / Egern → `make_min.py`；mihomo → `build_profiles.py`（见下表） |
| 3 | **改完跑全套闸门**：`python skill/tests/verify_all.py`（现 46 道，其中 mihomo 相关 13 道） | §6.2 动线⑤ |
| 4 | **不提交真实地址 / 凭据 / token** | `check_secrets.py` 两份都跑（跨内核版 + mihomo 版，见 §5.9） |
| 5 | **改配置去适配判据，不是改判据去适配配置** | §6.8 |

三侧现役件与生成器对照 —— **生成器这一列是本仓最容易记错的地方**：

| 内核 | 现役四件 | `.min` 由谁生成 | 配置真源 |
|:-----|:---------|:----------------|:---------|
| Surge | `surge/profiles/{routing,lazy}.conf` + `.min.conf` | `skill/tests/make_min.py --apply` | 完整版 `.conf`（手工维护） |
| Egern | `egern/profiles/{routing,lazy}.yaml` + `.min.yaml` | 同左 | 完整版 `.yaml`（手工维护） |
| mihomo | `clash/profiles/{routing,lazy}.yaml` + `.min.yaml` | `skill/scripts/clash/build_profiles.py` | **`clash/override/*.js`**（脚本才是真源） |

> ⚠️ mihomo 那一行的"配置真源"是三侧里唯一的例外：Surge / Egern 改**完整版**，
> mihomo 改**覆写脚本**、再由脚本生成静态 profile（§5.2）。别把两侧的习惯带过去 ——
> 手工改 `clash/profiles/*.yaml` 会被下一次重生成整份覆盖（§5.3）。
>
> ℹ️ 版本头注与归档**三内核通用**：mihomo 静态 profile 自 2026-10-07 起也带 `#! version=` 头注，
> 并按版本存进 `clash/profiles/config_old/`（§5.10）。Surge / Egern / mihomo 三侧口径一致。

## Surge 操作

对象：`../surge/profiles/` 下 `lazy` / `routing` 两版（各含带注释完整版与 `.min` 版）。
加固清单逐项与验收标准见 [`shared/hardening-checklist.md`](hardening-checklist.md)（清单本体在那份文件，本章讲怎么用它）；逐键权威是 [`surge/reference/profile-anatomy.md`](../surge/profile-anatomy.md)。

### 3.1 文件结构速览

Surge 的 `.conf` 按节组织，模板里与防泄露相关的节：

| 节 | 作用 | 防泄露相关 |
|:---|:-----|:-----------|
| `[General]` | 全局开关 | DNS 段全部键都在这里：`dns-server`、`encrypted-dns-server`、`hijack-dns`、`always-real-ip`、测试端点等 |
| `[Proxy]` | 静态节点 | 仅 `lazy` 有（占位节点）；`routing` **段为空**，节点全来自订阅（2026-10-06 起） |
| `[Proxy Group]` | 策略组 | 出口选择逻辑 |
| `[Rule]` | 规则 | 顺序即优先级，见 3.4 |
| `[URL Rewrite]` / `[Header Rewrite]` 等 | 附加功能 | 与防泄露无关，可整节删 |

> **说明**　两份配置的 `[General]` DNS 相关键四份（`lazy` 与 `routing` 及各自 `.min`）保持逐字一致 —— 这是维护纪律，没有自动判据，改 DNS 段时四份一起改（流程见下文「日常维护」）。

### 3.2 `[General]` DNS 段：每行堵哪个出口

对照 [DNS 基础的泄露面全景](dns-basics.md)，这些键各自堵一条通路：

| 键 | 堵哪 | 注意 |
|:---|:-----|:-----|
| `dns-server` | 引导与连通性测试用的本地上游 | 全 IP 字面量，不放 `system`。不要删它来"减少解析面"：删了 Surge 会用系统 DNS（运营商下发），正是出口 ① |
| `encrypted-dns-server` | 日常解析走加密通道 | 端点尽量 IP 字面量；保留的 2 个主机名端点已用 `# audit-waive:` 记录豁免与理由 |
| `hijack-dns` | 旁路设备（出口 ②） | 模板列出最常见的境外解析器地址把它们收进本地；想一网打尽可写 `hijack-dns = *`（有取舍，见 `profile-anatomy` §10.3） |
| `encrypted-dns-follow-outbound-mode` | 防止"出站走代理、解析也跟着出境"的意外 | 模板显式设 `false`，理由在 `profile-anatomy` |
| `use-local-host-item-for-proxy` | 防止本地 hosts 条目污染代理侧解析 | 理由在 `profile-anatomy` |
| `always-real-ip` | Fake-IP 模式下游戏机 / NTP / STUN 拿到假 IP | 是功能清单，不是可选装饰。里面的主机名应能被 `[Rule]` 域名规则接住，`check_surge_dns.py` 第 11 项专查这条 |
| `internet-test-url` / `proxy-test-url` | — | 性能探针，不是泄露通道：前者国内 204（测"能不能上网"），后者保持境外 `gstatic.com`（`smart` 打分要含国际段才是真实路径）。把后者"为防泄露"改成国内是典型的原则误套用，见 `profile-anatomy` §16 |

> **注意**　`# audit-waive: <编号> <理由>` 是有语义的注释，审计器真的会读它。删掉那行，读数立刻从「已豁免」变「HIGH/MEDIUM」；同文件内编号不重复。

### 3.3 广告拦截：pre-matching 与 AD 组的分层

模板里广告拦截有两条清单：白名单 guard 在前、拦截在后。关键约束：

> **注意**　`pre-matching` 的规则，策略必须是字面量 `REJECT` 家族，不能是策略组。预匹配发生在"还来不及决定出口"的阶段；策略组运行时可能解析成 `DIRECT`，Surge 会直接拒绝加载整份配置。

所以链路是刻意的分层：拦截规则写字面量 `REJECT`，换取 DNS / SYN 阶段即拒、不建连不解析（全模板最大的一笔省电优化）；旁边 `AD` 组作为独立手动开关，不被任何规则引用，职责是给人工干预留入口——成员只有 `REJECT` 一个（分流版 Surge 的同位组另挂一个 `DIRECT` 兜底）。

想让面板开关接管拦截？可以，但要一并去掉 `pre-matching`，接受"先解析再拒"的代价。

### 3.4 `[Rule]` 顺序铁律

两版共享同一条顺序铁律，自上而下、首个命中生效：

```
① 广告白名单 guard（防误杀，DIRECT）
②③ 广告拦截（REJECT 字面量，pre-matching）×2
④ 系统域白名单（`SYSTEM` → DIRECT）
⑤⑥ 内网 / LAN
⑦…（routing 版：应用规则插在中间，见 3.5）
⑳ 域名类国内直连（direct.txt 等）
㉕ IP 类（GEOIP,CN,DIRECT,no-resolve）
㉖ FINAL 兜底（dns-failed 一并标注）
```

> **分流版专有**：位 ④ 之前还插一条 `SystemOTA.list` → `Apple Update` 组（位 ④，仅分流版有）。
> 懒人版不设该组、也无这条规则（共 11 条）。

三条不能错位的细节：

1. **广告白名单必须在 REJECT 之前**。「DIRECT 永远在 REJECT 前」这种一刀切不变量本身是错的 —— 白名单就是 DIRECT，且必须排在 REJECT 前。
   ⭐ **白名单是两层，但两层不再连写**（2026-10-06 起变更）：
   **① 广告白名单**（`surge-direct.list`，位 ①）· **系统域白名单**
   （Surge 内置 `SYSTEM` ／ Egern `apple_system.list`，分流版位 ⑤ / 懒人版位 ④，在广告清单**之后**）。
   ⚠️ 变更依据：`SYSTEM` 18 个域名与两条广告清单零交集（排前后结果相同）
   ⇒ 不再占用「最前」这个语义位置；`apple.txt` 与 AWAvenue 有 1 条交集
   （`iadsdk.apple.com`）⇒ 它**不上提**。
2. 应用类规则必须排在 `direct.txt` 之前。否则域名恰好被国内清单收录的应用会被直连接走 —— 实测：`direct.txt` 收录了若干含 `github` 的域名（githubim.com / githubshare.com / hellogithub.com / kkgithub.com 等），`GitHub.list` 的 `DOMAIN-KEYWORD,github` 本可兜住它们，排到后面就分流失效。（`github.com` 本身**不在** `direct.txt` 里；该条现直指 `Proxy`。）
3. `GEOIP` 必须带 `no-resolve`，且必须与 ⑤ 成对。见 [DNS 基础](dns-basics.md)。

> **说明**　两版 `[Rule]` 都没有游戏机域名规则（`nintendo.net` 等只在 `always-real-ip` 里）—— 这些主机名照旧拿真实 IP，去向由常规规则链决定。别把"缺这三条"当 bug 来"修"。

### 3.5 分流版（`routing.conf`）要点

完整的分组层次与逐条规则表直接读 [`routing.conf`](../../../surge/profiles/routing.conf) 本体（注释齐全）。这里只讲动手最容易撞的四条墙。

#### ① smart 组不能拿组名当子策略

官方限制：Smart 组不可使用其他组作为子策略，也不可用作 `url-test` / `load-balance` 组的子策略。等价做法是 `include-other-group`：

```ini
Proxy = smart, include-other-group="Airport"    # ✅ 拿到的是解析后的具体节点
Proxy = smart, Airport                           # ❌ 成员是"Airport"这一个组名，测不到组内节点
```

#### ② flatten 的对应物

Egern 的 `flatten: true` 在 Surge 没有同名字段，语义对应 `include-other-group`（官方："includes the resolved member policies from other policy groups"）。应用组因此写成：

```ini
ChatGPT = select, include-other-group="Proxy"
```

差异要说白：Egern 应用组自 `routing_v3` 起同为手动 `select`（旧版是 `fallback`），与 Surge 的 `select` 现版同形。想要应用组自动选优：Egern 换 `fallback` / `smart`、Surge 把某组换成 `smart, include-other-group="Proxy"`，代价是面板不能再手动挑节点。旧版这处确是能力差异，现已拉平 —— 史实写明，不假装一直没差过。

#### ③ 地区组靠正则筛名字，且有两个开关要一起开

```ini
Hong Kong = smart, include-all-proxies=true, include-other-group="Airport", policy-regex-filter=(?i)🇭🇰|香港|…
```

- `policy-regex-filter` 对显式列出的成员无效 —— 手写在 `[Proxy]` 里的节点，必须靠 `include-all-proxies=true` 才会被筛到；
- 正则别写太宽：`(?i)us` 会同时命中 `Russia` / `Belarus` / `AUStralia`，保守用 `\b` 锁词边界；
- `Other Regions` 是负向断言，把其余地区组的关键词逐字抄了一遍 —— 任何组加关键词必须同步改它，漏改不报错、面板也看不出（节点会同时出现在两个组）。这条拷贝在配置层面消灭不掉，靠 `audit_region_filters.py` 守（用法见 [验证与自检](troubleshoot-faq.md)）。

#### ④ 已知边界（都是设计，不是 bug）

| 边界 | 说明 |
|:-----|:-----|
| 空地区组 | 节点名不含关键词则该组为空，指向它的规则会断流。导入后到面板确认 |
| `Smart` 权重 = 低倍率优先 | 全部 smart 组（`Smart` + 6 个地区组）带 `policy-priority` 0.15：默认出口优先落低倍率节点（省钱但可能稍慢），与 Egern 对齐；不想要就把这项权重去掉 |
| `https` 类型节点不支持 UDP 中继 | 别让承担 UDP 的组落到它们 |
| Apple 无独立策略组 | 走 `Apple` 规则 → DIRECT；要"给 Apple 挑地区"得自己复制 select 组 |
| 段内顺序 | 与 Egern 逐位对齐（维护纪律）；"先写引用别人的，后写被引用的"，Surge 允许前向引用 |

### 3.6 你必须替换 / 可以删除的

必须替换（逐键语义见 [`surge/reference/profile-anatomy.md`](../surge/profile-anatomy.md)）：

- `lazy` 的 `[Proxy]` 占位节点（`routing` 此段已空，无需替换）；
- `routing` 的 `Airport` 组 `policy-path` 占位订阅地址；
- 两份 `[SSID Setting]` 段里的 `SSID:MyHome` —— `MyHome` 是照官方示例留的占位网络名，不替换就匹配不到任何 Wi-Fi，「回家自动暂停」静默不生效。该段只有 Surge 侧有，Egern 无对等件（见 [`cross-kernel-diff.md`](cross-kernel-diff.md) §1「网络级暂停」）。

可以删（按收益排序，删完必须重跑分流覆盖审计）：

- `[URL Rewrite]` / `[Header Rewrite]` 等附加节；
- AI 分流（`AI` 组 + 对应规则）；
- `AD` 组（反正不被规则引用）。

不能删：`direct.txt` 规则、`GEOIP,CN`（连同 `no-resolve` 是一对）、白名单 guard。删任何一个都会立刻构成 [DNS 基础](dns-basics.md) 说的"只交一半"。

改 `routing.conf` 想加新应用组：照 §3.5 的写法复制一个 `select, include-other-group="Proxy"` 组，把它的规则插在国内直连集之前，并给 `audit_routing_coverage.py` 加对应探针（期望值精确到组名，不许放宽成"不是 DIRECT 就行"）。

### 3.7 官方文档入口

- 策略组 / `include-other-group`：[manual.nssurge.com/policy-groups/policy-including.html](https://manual.nssurge.com/policy-groups/policy-including.html)
- Smart 组限制（中文）：[kb.nssurge.com · smart-group](https://kb.nssurge.com/surge-knowledge-base/zh/guidelines/smart-group)
- 其余逐节引用见 `profile-anatomy` 各节脚注。

### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 对侧内核的操作章 | 本篇「Egern 操作」章（已并入本篇）·「mihomo 操作」章（§5） |
| 换、加、删任何规则集之前 | [规则集与素材](rulesets.md) |
| 出问题了 | [故障排查 · FAQ](troubleshoot-faq.md) |
| 把本篇改动搬到 Egern 侧 | [跨内核移植](cross-kernel-diff.md) |
| 名词不认识、常见疑问没解决 | [FAQ 与术语表](troubleshoot-faq.md) |

## Egern 操作

对象：`egern/profiles/` 下 `routing.yaml`（推荐，完整分流）与 `lazy.yaml`（懒人配置），各含带注释完整版与 `.min.yaml` 形态，共四件，历史版本看 git。
加固清单在 [`hardening-checklist.md`](hardening-checklist.md)；逐键权威是 [`egern/reference/profile-anatomy.md`](../egern/profile-anatomy.md)。

### 4.1 顶层字段：值等于默认的不写

Egern 的 YAML 顶层：`ipv6`、`vif_only`、`hijack_dns`、`geoip_db_url` / `asn_db_url`、两个延迟测试 URL、`real_ip_domains`、`default_proxy_group` 等。三条维护经验：

1. 值恰好等于官方默认值的行是冗余（`routing_v2.1` 一次性删掉了五十多行这种）。读旧版看到它们，别当"定制"。
2. 非默认值必须显式写，尤其 `vif_only: true`（官方只有一句"虚拟网接口模式，默认 false"，细节无法确认）。遇到"某些 App 不走代理"，它是第一个 A/B 候选，但别凭猜测替用户改。
3. `hijack_dns: ['*']` 接管 `:53` 并返回 Fake IP；`real_ip_domains`（`*.lan` / `*.local` / `*.push.apple.com`）让推送与内网发现拿真实 IP —— Fake IP 反而会让 APNs 异常。
4. **例外（2026-09-29 定）**：两内核对齐面的显式声明键不适用第 1 条 —— `ipv6: false` 虽等于默认值也必须写，让"四份对拍"看文件即知、不用查各内核默认值；同类对齐面键若将来出现，照此办理。

### 4.2 `dns:` 段：五小节，一个原则

原则一句话：`bootstrap` 唯一安全的形态是"永远不被触发"。逐节要点：

| 小节 | 要点 |
|:-----|:-----|
| `bootstrap` | 全国内明文 IP，绝不写 `system`（等于把运营商接进回退链）。也别指望"换更好的 bootstrap IP"：实测换 IP 后泄露仍来自透明重定向 / 回退，机制见 [DNS 基础](dns-basics.md) 的泄露面各出口 |
| `upstreams` | `Domestic-DNS` 端点全部 IP 字面量（消灭 bootstrap 用途①）；「两家机构 × 两种协议」的冗余结构，同组并发竞速、全组失败才触发回退。`Foreign-DNS` 整组已注释保留：它必须经代理才可达，不能当兜底（启动期解析会掉进明文）。Quad9 教训：`https://9.9.9.9/dns-query` 静默失效（只提供 HTTP/3），`tls://9.9.9.9` 可用 |
| `forward` | f10 起塌缩为纯兜底（指向 `Domestic-DNS`）—— 换订阅、换节点域名，本段一个字都不用改。两条兜底与一条等价的原因：value 单值 + 顺序求值，删任何一条行为不变（`audit_dns_forward.py` 可证） |
| `proxy_nameservers` | 硬覆盖：一设就绕过 `forward`、强制直连、成为代理侧解析的唯一出口。"不设"本身也留了一条"未命中回退 Bootstrap"的明文分支 —— 模板最终选择显式设置 + 国内端点（它是强制直连的，境外解析器在国内线路不可达）。排障口诀：节点连不上，第一件事注释掉这个列表 |
| `hosts` / `block_ips` | `hosts` 是"端点写主机名"时代的补救，端点全 IP 后无引用点、已删；`block_ips` 丢弃空路由式污染应答，刻意不含私网段，免误伤内网 |

已知代价（完整版见 `profile-anatomy` 的取舍节）：设置了 `proxy_nameservers` + 兜底国内组，需要本地解析的境外域名会拿到国内答案，实际影响面仅限 `DIRECT` 域名。审计里那两条 `LOW`（一条是 `proxy_nameservers` 成为代理侧解析唯一出口，一条是 `forward` 兜底指向国内组）就是它 —— 是取舍，不是缺陷。

### 4.3 `proxies:` 与节点形态

- 分流版模板 `proxies` **为空**（节点全来自订阅，2026-10-06 起）；懒人版模板带 2 条占位节点（`Node-A` / `Node-B`），`server` 都写成 IP 字面量。
- 自己填节点时，`server` 能写 IP 就写 IP：写域名必然产生一次"本机 + 直连 + 明文"解析（代理还没通）。这是从根上消除节点域名解析面的唯一办法；中转 `prev_hop` 同理，且无需为节点域名改 `forward`。

### 4.4 `policy_groups:`：四类组与三个易踩的坑

组分三类：入口（`Proxy`）、应用组（`ChatGPT` / `Gemini` 等，现行版皆为 `select`，旧版才是 `fallback`）、智能组（`Smart` 与各地区组，皆 `smart`；地区组用 `filter` 正则筛名 + `flatten: true`；两者都带低倍率优先权重）、订阅槽位（`external` 组，`hidden: true`，当前版只有一个 `Airport`；旧版为 `Airport-A` / `Airport-B` 两槽、更早四槽）。

必须知道的三条：

1. `flatten: true` 把组名展开成组内全部具体节点，让 `fallback` / `smart` 做节点级尝试。`fallback` 不给 `flatten` 时，`policies: [Proxy]` 只有一个候选单位，等于没有故障转移。官方明确 `flatten` 在 `select` / `auto_test` / `smart` / `fallback` / `load_balance` 五种类型通用。
2. `fallback` 不做延迟择优，按顺序取第一个可用。想固定地区，把目标写首位；想自动挑最快，改 `smart`。`ChatGPT` / `Gemini` 在旧版曾是空组 `[]` 而规则直指它们，导入即静默断流；当前版已填 `[Proxy]` + `flatten`，且这两组自 `routing_v3` 起已由 `fallback` 改为 `select`。
3. 低倍率优先改由**权重**承担：全部 smart 组（`Smart` + 6 个地区组）写 `policy-priority` / `priorities` 系数 0.15，两内核同值同正则；`Proxy` 首项即 `Smart`，默认出口因此优先落低倍率节点，低倍率不可用或过慢时**自动让位**。该正则须带左边界以免误收 `10.1` / 漏收 `0.5`。改任何地区组 filter 关键词，必须同步 `Other Regions` 的负向断言（`audit_region_filters.py` 守）。

`lazy` 特有：只有 `Proxy` / `AI` / `AD` 三组；`Proxy` 组 `policies` 为空，必须自己填节点名；`AD` 子策略只有 `REJECT`（无 `DIRECT` 兜底）。临时放行单个域名，在 `rules` 更前面加一条 `DIRECT` 规则，别整组切走。

### 4.5 `rules:`：分四段理解顺序

| 段 | 内容 | 要点 |
|:--:|:-----|:-----|
| A | DNS 端点固定路由 | 已整体移除。端点全是 IP 字面量，解析器直接以 IP 访问，不需要在 `rules` 里钉。只有你自己把 DNS 端点写成主机名时，才需要补一条 `DIRECT` 路由，否则它落 `default → Proxy` |
| B | 白名单 guard → 广告 → 内网 → 各应用规则集 | 顺序即优先级；`Proxy.list` 类"默认 `disabled: true`"的规则由 `Final` 兜底；AI 规则集 URL 钉 commit 防上游漂移；每条 `rule_set` 各自带 `update_interval`（现值两侧统一钉 `604800`，别只写第一条） |
| C | Apple（`apple.txt`）→ `direct.txt` → `.cn` 后缀 → `geoip: CN` + `no_resolve` | 这就是 [成对交付篇的判据 A+B](no-resolve-pairing.md) 在本内核的落点：`geoip` 带 `no_resolve` 后不匹配域名，国内域名直连完全依赖 `direct.txt` 那条纯域名规则集，动一条必须看另一条。Apple 那条 2026-10-04 起引零 IP 的 `apple.txt`（与 `direct.txt` 同仓库同 release）；此前是 `Apple_All_No_Resolve.list` —— 它的**原版**藏 13 条裸 IP、会强制解析，所以当时必须锁定 `No_Resolve` 变体 |
| D | `default: {name: Final, policy: Proxy}` | 未命中走代理，由节点远程解析、不经过 `dns` 段 —— 日志里的 `default → Final → Proxy` 是正常决策，不是泄露。`lazy` 没有 `Final` 这层组，`policy` 直写 `Proxy`；`name: Final` 只是日志标签 |

> **注意**　`no_resolve` 有三层，写之前先确认自己在哪一层：规则级（`geoip` / `ip_cidr` 的 `no_resolve`）、`rule_set` 级（在这里写不生效，这是坑）、条目级（`.list` 每条自带的 `,no-resolve`）。

`default_proxy_group: Proxy` 不是兜底：官方定义是"添加代理时自动加入的策略组"。改它不换出口，删它则手动新加的节点不进组。Egern 只有一条兜底通路，就是 `rules` 末尾的 `default`。

### 4.6 分流顺序与应用组默认出口

逐位匹配顺序表直接读 [`routing.yaml`](../../../egern/profiles/routing.yaml) 的 `rules:` 段注释。
两条与 Surge 侧共同的铁律同样成立：应用规则必须排在 `direct.txt` 之前；具体的在前、兜底在后。
应用组的 `policies` 里只有 `Proxy` 一项（+ `flatten`）—— 这是设计，不是"忘了加地区"；想固定地区，改首位即可。

### 4.7 必须替换与环境

- 必填：`Airport`（旧版 `Airport-A` / `Airport-B`）订阅组的 `url(s)` 占位，换成你的订阅地址。当前版所有分流组已填好 —— **分流版填完这一个占位就能直接导入**（节点全来自订阅）。
- 懒人版另可选：`proxies` 里那 2 条占位节点换成你的自建节点（`server` 尽量 IP），或整条删掉并把组里的名字一并摘掉。
- 运行审计脚本需要 Python 3 + PyYAML（本仓唯一第三方依赖）。
- 官方文档入口：DNS `https://egernapp.com/docs/configuration/dns` · rules 字段 `https://egernapp.com/docs/configuration/rules` · 顶层字段全表 `https://egernapp.com/docs/configuration/example`（两处页键名不一致，以 example 页为准）。

> **注意**　`https://egernapp.com/zh-CN/docs` 与 `https://egernapp.com/docs/configuration/general` 是 404，别按其他客户端文档站的直觉找路径。

### 4.8 改完之后的验证

```bash
python skill/scripts/egern/check_egern_dns.py         egern/profiles/routing.yaml
python skill/scripts/egern/audit_ruleset_noresolve.py egern/profiles/routing.yaml   # 联网：下载规则集数条目
python skill/scripts/egern/audit_routing_coverage.py  egern/profiles/routing.yaml   # 联网：真实域名走规则链
python skill/scripts/egern/audit_dns_forward.py       egern/profiles/routing.yaml
python skill/scripts/egern/check_egern_dns.py egern/profiles/lazy.yaml egern/profiles/routing.yaml
```

判据逐项见 `skill/scripts/egern/check_egern_dns.py` 头注。
最后在目标链路（尤其蜂窝）跑一次 leak test，并先写下"哪台设备、哪条链路、谁的 DNS" —— 混链路会让整轮结论作废。

### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 对侧内核的操作章 | 本篇「Surge 操作」章（已并入本篇）·「mihomo 操作」章（§5） |
| 换、加、删任何规则集之前 | [规则集与素材](rulesets.md) |
| 出问题了 | [故障排查 · FAQ](troubleshoot-faq.md) |
| 把本篇改动搬到 Surge 侧 | [跨内核移植](cross-kernel-diff.md) |
| 名词不认识、常见疑问没解决 | [FAQ 与术语表](troubleshoot-faq.md) |

## mihomo 操作

对象：`clash/` 下的**两种交付形态**（静态 profile 四件 + 覆写脚本两份）。
加固清单在 [`hardening-checklist.md`](hardening-checklist.md) 的 mihomo 侧；
逐键权威（语义、边界、取舍）是 [`clash/reference/profile-anatomy.md`](../clash/profile-anatomy.md)
—— **那一篇是权威，本章只讲动线与坑，不重复逐键语义**；
门禁命令与判据细节在 [`clash/reference/checker.md`](../clash/checker.md)。

> 📌 **三侧里只有这一侧"配置真源不是 profile 本身"**：改配置改的是 `override/*.js`，
> 静态 `profiles/*.yaml` 由脚本生成。这是最容易带错的一侧，先读 §5.2 再动手。

### 5.1 文件结构速览

```
clash/
├── profiles/                          # 静态 profile 四件（**生成物**）
│   ├── routing.yaml · routing.min.yaml   # 分流版  25 组 / 25 集 / 27 条
│   └── lazy.yaml    · lazy.min.yaml      # 懒人版   3 组 / 10 集 / 11 条
└── override/                          # 覆写脚本（**真源**）
    ├── my_clash.js                    # → 分流版  22 组 / 25 集 / 27 条
    ├── my_clash_lazy.js               # → 懒人版   3 组 / 10 集 / 11 条
    └── README.md                      # 两形态差别、用法、本地实测
```

两份 profile 是**分工关系**（分流版细分 / 懒人版全量一个出口），不是版本关系，选一份用、不要叠加。
现役规模（实测 `build_profiles.py --check` 与 `yaml.safe_load` 核对，2026-10-07）：

| | 分流版 `routing` | 懒人版 `lazy` |
|:--|:--|:--|
| 策略组 | **25** | **3**（`Proxy` / `AI` / `AD`） |
| `rule-providers` | **25**（16 `.mrs`/domain + 4 `.mrs`/ipcidr + 5 `.yaml`/classical） | **10**（4 + 2 + 4） |
| 规则 | **27** | **11** |
| 带 `no-resolve` 的规则 | **4** | **2** |

两份脚本与两份 profile 的**差一处、且是有意的**：
脚本分流版 **22 组** vs 静态 **25 组**，差的是模板专属的三个隐藏分档子组
`Low Mult.` / `Auto` / `High Mult.`（mihomo 没有权重键，倍率偏好靠 `fallback` + `filter` 分档模拟；
脚本侧 `Smart` 是单组 `fallback`，做不到这三档）。规则数、provider 数、provider URL 集合两边相同。
懒人版则**完全同构**：脚本 3 组 / 11 条 / 10 份，与 `lazy.yaml` 逐位相同。

> ℹ️ **过期文字已清理（2026-10-07）**：此前脚本头注与 `override/README.md` 表格里写着旧数字
> （`my_clash.js`「20 组 / 20 份 / 26 条」、`routing.yaml`「23 / 22 / 24」、`my_clash_lazy.js`「5 MRS + 5 yaml」等），
> 现已全部按实际值更正为 22 组 / 25 份 / 27 条（分流版）与 3 组 / 10 份 / 11 条（懒人版）。
> **判据以配置文件为准** —— 头注数字由 `check_header_numbers.py` 与脚本实际输出对拍。

### 5.2 改配置的正确顺序

```bash
① 改真源：        clash/override/my_clash.js        （或 my_clash_lazy.js）
② 重生成 profile： python skill/scripts/clash/build_profiles.py
                  # 一次性写好 routing/lazy 的 .yaml 与 .min.yaml 四件
③ 若动了规则集内容：python skill/scripts/clash/build_rules.py   # rules/*.list → *.yaml
④ 跑全套闸门：      python skill/tests/verify_all.py            # 现 46 道，含 mihomo 相关 13 道
```

> ⚠️ **步骤 ② 不可跳过，也不可用手工同步替代。** 脚本与静态是同一套配置的两个形态，
> 由 `check_script_sync.py` 逐位对拍（比 `rules`、`rule-providers` URL 集合、
> `proxy-groups` / `dns` / `ipv6`）。只改一边 ⇒ 用户遇到「照文档用脚本订阅，
> 效果跟直接导入配置不一样」，而两边都能正常跑、都不报错 —— 只能靠对拍发现。
>
> ⚠️ **步骤 ② 的 `--check` 是门禁**（`build_profiles.py --check` 是 46 道之一）：
> 脚本有更新而静态 profile 没重生成 ⇒ 判负。想只看看有没有漂移，跑这个。

三个只在这一侧存在的环节，逐个说清：

| 环节 | 脚本 | 判据 |
|:-----|:-----|:-----|
| 静态 profile 新鲜度 | `skill/scripts/clash/build_profiles.py --check` | 脚本输出 ≠ 静态文件即判负（46 道之第 46 道） |
| 规则集生成物新鲜度 | `skill/scripts/clash/build_rules.py --check` | `.yaml` 与 `.list` 真源不一致即判负 |
| 脚本 ↔ 静态对拍 | `skill/tests/clash/check_script_sync.py` | 需 **node**（Windows 下由 `_clash_common.find_node()` 显式探测；Git Bash 的 PATH 不继承给 subprocess） |

### 5.3 不要手工改 `profiles/*.yaml`

`clash/profiles/` 四件全部由 `build_profiles.py` 生成，头注里也写了"请勿手工编辑"。两条理由，都不是理论：

1. **手工改会被整份覆盖** —— 下次跑脚本，`open(fp, "w")` 覆盖写，你的改动无声消失；
2. **更糟的是追加写会堆叠** —— 本仓**真踩过**：此前靠临时脚本手工重生成，
   误用追加模式把 `routing.yaml` 纵向堆了 **7 份**完整配置（**3294 行**、
   7 个历史版本首尾相接、无 `---` 分隔）。PyYAML 只保留最后一份 ⇒
   **门禁全绿、肉眼也看不出来**，但用户拿到的是畸形文件。

`build_profiles.py` 现在的两条硬保证正是为这个存在（写在它自己的头注里）：

- ① **一律覆盖写**（`"w"` 模式），绝不追加；
- ② **生成后立即自检**：顶层键不得重复（专抓堆叠）、解析后组数 / 规则数与脚本输出一致、
  `proxy-providers` 与 `tun` 必须存在。

> ⚠️ **每次手工改过 profile 之后**，跑 `python skill/scripts/clash/build_profiles.py --check`
> 确认生成器认为"已是最新" —— 若它说"已过期"，说明有改动没回灌进脚本，
> 要么把改动搬进 `override/*.js` 重生成，要么接受下次重生成时被覆盖。

### 5.4 规则集：改 `.list` 真源，再生成 `.yaml`

`rules/` 是本仓**三内核共享真源**（合并最直接的收益）：

| 唯一真源 | 条数 | 生成物 | 谁消费 |
|:---------|----:|:-------|:-------|
| `rules/AI.list` | **272** | `rules/AI_Domains.yaml` | Surge / Egern 直接引 `.list`；mihomo 引 `.yaml`（classical） |
| `rules/apple_system.list` | **18** | `rules/apple_system.yaml` | Egern 补 Surge 内置 `SYSTEM`；mihomo 用 `.yaml` |
| `rules/emby.list` | **4** | `rules/emby.yaml` | 同 AI |

```bash
python skill/scripts/clash/build_rules.py            # 生成
python skill/scripts/clash/build_rules.py --check    # CI 用：过期即判负（46 道之第 35 道）
```

改内容**只改 `.list`**，重跑脚本 —— 物理上不可能漂移。
❌ **不手工编辑 `rules/*.yaml`**（生成物；`SKILL.md` 的红线之一）。
mihomo 其余 **20 份 `.mrs` 远程集 + 5 份 YAML** 不在此链上，由 `rule-providers` 自己管理。

### 5.5 日常验什么、用哪个脚本

| 想验什么 | 跑哪个 | 联网 |
|:---------|:-------|:----:|
| 结构 / 悬空引用 / 广告双条件 / **禁止 tun** / IPv6 / 零 dat | `skill/tests/clash/check_structure.py`（8 项） | 否 |
| 防 DNS 泄露语义（分级发现） | `skill/scripts/clash/check_clash_dns.py clash/profiles/routing.yaml` | 否 |
| `.min` 与完整版是否漂移 | `skill/tests/clash/check_min_pair.py` | 否 |
| 脚本 ↔ 静态是否漂移 | `skill/tests/clash/check_script_sync.py` | 否（需 node） |
| 规则集生成物是否过期 | `skill/scripts/clash/build_rules.py --check` | 否 |
| 静态 profile 是否过期 | `skill/scripts/clash/build_profiles.py --check` | 否（需 node） |
| **远程集 URL 是否还活着** | `skill/tests/clash/check_remote_urls.py` | **是**（慢，按需） |
| 全部（含 Surge / Egern） | `python skill/tests/verify_all.py` | 部分 |

一键命令（详见 [`clash/reference/checker.md`](../clash/checker.md) §2）：

```bash
python skill/scripts/clash/check_clash_dns.py clash/profiles/lazy.yaml clash/profiles/routing.yaml
python skill/tests/clash/check_structure.py
python skill/tests/clash/check_min_pair.py
python skill/tests/clash/check_script_sync.py
python skill/tests/clash/check_remote_urls.py          # 慢，按需
```

当前基线（2026-10-07 实测）：`check_clash_dns.py` 分流版 **0 high / 0 medium / 7 LOW / 21 OK**，
懒人版 **0 high / 0 medium / 2 LOW / 21 OK**；`check_structure.py` 四份 profile 全绿。

那些 **LOW 是取舍，不是缺陷**，别去"修"它们：分流版 `proxy-server-nameserver` / `direct-nameserver`
的国内端点写的是主机名（`doh.18bit.cn` / `dns.alidns.com`）⇒ 引导期明文解析一次，信号弱（只带出"本机在用哪个 DoH"）；
`dns-hijack: any:53` 未接管 TCP:53（不写协议前缀时默认 `udp://`，明文 TCP 查询在现代客户端罕见）；
5 个 `classical` 规则集内容无法静态判定（本仓自托管的 `rules/*.list` 实测 0 条 IP 条目）；
`fallback-filter.geoip: true` 是双倍延迟、不是泄露。**改它们之前先问一句"我真的需要吗"**（懒人版干脆不开 `fallback` 就是同一个判断）。

> ⚠️ **审计通过 ≠ 配置可用**（三侧共通的母题，见 [故障排查 · FAQ](troubleshoot-faq.md) §7.5）。
> mihomo 侧**已有**专用的分流覆盖审计脚本（`skill/scripts/clash/audit_routing_coverage.py`，闸门 #39；2026-10-07 补出）。Surge / Egern 各自也有。
> 因此每次增删 `no-resolve`、替换 `cn` provider、或移动 `MATCH` 前的规则时，
> 仍要人工核对三条：`cn` 仍是 `behavior: domain` 的国内域名集；
> `RULE-SET,cn,DIRECT` 仍在 `MATCH,Proxy` 之前；用国内**非 `.cn`** 域名验证，不能只测会被后缀兜底救活的样本。

### 5.6 两种交付形态分别怎么维护

这是 mihomo 侧**独有**的东西，Surge / Egern 都没有对等件：

| 形态 | 给谁 | 怎么用 |
|:-----|:-----|:-------|
| 静态 `.yaml` | 下载即用的人 | 导入客户端 / 订阅这个文件的 raw 地址 |
| 覆写 `.js` | 想保留自己订阅的人 | 挂到**任意订阅**上，把订阅改造成同款结构 |

脚本做的事（`main(config)` 返回改写后的 config）：
`proxies` **保留**（订阅的节点原样）· `proxy-groups` **整体替换** ·
`rule-providers` **整体重建**（先清空，避免残留无用 provider 与命名冲突）·
`rules` **整体替换** · `dns` **整体替换**（含双层广告拦截）· `ipv6` 显式置 `false` ·
入站端口（`port` / `mixed-port` / `dns.listen`）**不覆盖**，交给客户端决定。

两种形态维护上的**三条硬分界**：

1. **`tun` 只属于静态 profile。** 脚本**不生成** `tun` 段是对的 —— 客户端
   （Mihomo Party / Clash Verge）自己管理 TUN，脚本只覆写策略组与规则，不该越俎代庖。
   ⚠️ 本仓踩过：由脚本重建静态 profile 时把 `tun` 丢了（脚本输出里本就没有），
   四份配置全没了 `dns-hijack` + `strict-route` —— **防线破了而门禁全绿**。
   现在两道守门：`build_profiles.py` 从静态版**继承** `tun` 且自检它存在；
   `check_structure.py` 第 ④ 项查 `enable` / `dns-hijack` / `auto-route` / `strict-route` 四键。
2. **`proxy-providers` 只属于静态 profile。** 脚本用 `include-all` 直接吃节点，不需要订阅槽位；
   但静态 profile **必须有** `proxy-providers.Airport`（用户导入后要靠它填自己的订阅地址）。
   同样踩过：重建时把它丢了，而头注还让用户去改 `proxy-providers.Airport.url` ⇒ 用户无从下手。
3. **`Smart` 三档必须"接上"**，不只是"声明"。三个子组的定义有了、`Smart.proxies` 仍写 `["DIRECT"]`
   的话，三档形同虚设 —— 声明了却没连，比不声明更隐蔽。`build_profiles.py` 的自检会抓这一条。

> 📌 一句话记法：**脚本不生成的字段只有 `proxy-providers` 与 `tun` 两个，生成时必须从静态版继承。**
> 这条来自一次真实回归的事后系统排查（见 `build_profiles.py` 头注）。

### 5.7 必须替换与环境

- **必填（两形态各一处）**：静态 profile 的 `proxy-providers.Airport.url`
  （当前占位 `https://sub.example.com/api/v1/client/subscribe?token=REPLACE_WITH_YOUR_TOKEN`）
  换成你自己的订阅地址。不换 ⇒ 走代理的流量全不通 —— 占位地址是 `example.com`，不是真实服务。
- 覆写脚本不需要这一步：它保留传入订阅自己的 `proxies`（若订阅还带 `proxy-providers`，
  脚本自动从 `include-all-proxies` 切到 `include-all`，避免 provider 里的节点成为孤儿）。
- 运行门禁需要 **Python 3 + PyYAML**（本仓唯一第三方依赖）；`check_script_sync.py` 与
  `build_profiles.py` 另需 **node**（跑 `override/*.js` 取输出）。
- 从**仓库根**调用门禁。四个 clash 门禁的 `_default_root()` 都是「当前工作目录 → 逐级向上 + `/clash`」，
  找到同时含 `profiles/` 与 `override/` 的目录为止 —— CWD 优先是刻意设计
  （CI 上基于 `__file__` 探测会算错目录，报"缺文件"而本地全过）。

### 5.8 改完之后

```bash
python skill/tests/clash/check_structure.py
python skill/tests/clash/check_min_pair.py
python skill/tests/clash/check_script_sync.py          # 需 node
python skill/scripts/clash/build_profiles.py --check
python skill/scripts/clash/build_rules.py --check
python skill/tests/verify_all.py                       # 全套 46 道
python skill/tests/clash/check_remote_urls.py          # 慢，联网，按需
```

最后在目标链路（尤其蜂窝）跑一次 leak test，并先写下"哪台设备、哪条链路、谁的 DNS" ——
混链路会让整轮结论作废（[故障排查 · FAQ](troubleshoot-faq.md) §7.0）。
判据逐项见 `skill/scripts/clash/check_clash_dns.py` 头注与
[`clash/reference/checker.md`](../clash/checker.md) §4–§8。

### 5.9 两个 `check_secrets.py`，别只跑一个

| 脚本 | 扫描面 | 判据 |
|:-----|:-------|:-----|
| `skill/tests/check_secrets.py`（跨内核，进 46 道） | 全仓 `.conf` / `.yaml` / `.yml`，**跳过 `icons/`** | 禁串 `tange365.com` / `wangxinyu`；IPv4 白名单；`YAML_CRED_KEYS` 值必须占位 |
| `skill/tests/clash/check_secrets.py`（mihomo 版） | 全仓 **`.js`** / `.yaml` / `.md` / `.conf` / `.list` / `.txt` / `.json`，跳过 `icons/` 与 `rules/` 的主机扫描 | 凭据字段非占位即报；IPv4 白名单；主机白名单；私钥头无条件报 |

两者互不可替代：mihomo 版能扫 **`.js`**（脚本里也有订阅 URL），跨内核版带禁串黑名单。
**改名合并会同时丢掉两边的判据。**

> ⚠️ **各内核的"常识"不同**：`198.18.0.1` 是 mihomo 的 `fake-ip-range`（`198.18.0.1/16`，
> RFC 6815 保留段），但 Surge / Egern 侧的 secrets 扫描不认识它 —— 整合时已加入 `DOC_NETS` 白名单。
> 这类分歧必须在整合层处理，不能指望某一侧的脚本天然认识另一侧的合法值。

### 5.10 版本与归档：这一侧不适用

Surge / Egern 的 `#! version=` 头注、`config_old/` 归档、"一天一版"（§6.1）**只管那两侧**。
mihomo 静态 profile 由脚本生成、当前文件**没有 `#! version=`**，也不进 `config_old/`。
**不要把那套版本号与归档约定机械搬到 mihomo** —— 生成物天然由 git 历史记录中间态，
再叠一层人工版本号只会多一个会对不上的数字（历史教训见 §6.7）。

### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| mihomo 逐键权威（语义 / 边界 / 取舍） | [`clash/reference/profile-anatomy.md`](../clash/profile-anatomy.md) |
| 门禁命令与逐条判据 | [`clash/reference/checker.md`](../clash/checker.md) |
| mihomo 加固清单（14 项判据 + 验收标准） | [加固清单 · mihomo 侧](hardening-checklist.md#mihomo-侧) |
| `no-resolve` 的三侧成对交付 | [分流与 no-resolve 必须成对交付](no-resolve-pairing.md) |
| 对侧内核的操作章 | 本篇「Surge 操作」章 ·「Egern 操作」章 |
| 换、加、删任何规则集之前 | [规则集与素材](rulesets.md) |
| 出问题了 | [故障排查 · FAQ](troubleshoot-faq.md) |
| 把本篇改动搬到另外两侧 | [跨内核移植](cross-kernel-diff.md) |

## 日常维护

面向"改这份配置的人"：改哪里、怎么升版、怎么同步、怎么记录。
仓库级红线（节点不提交真实值等）见根 [`SECURITY.md`](../../../SECURITY.md)，本章不重复其条文，只讲操作动线。
⚠️ 本章的版本 / 归档 / Release 各节（§6.1、§6.9）**只适用 Surge / Egern 两侧**，mihomo 侧见 §5.10。

### 6.1 固定名规矩：先记住这个，再碰任何文件

- 顶层永远只有四个固定名 × 两内核（`.conf` / `.yaml` 各一对）：`routing` / `lazy` 的完整版与 `.min` 版。它们是永久订阅地址的落点，不随版本改名；
- "当前是哪一版"只写在文件头注 `#! version=…` 里；
- ⭐ **一天一版（2026-10-04 起）**：同一个自然日内，**每条产品线只在当天第一次配置变动时归档 + 升号**；当天后续的改动 —— 包括修前一次改动带出来的连带问题 —— **沿用同一版本号**，不动归档、不升号 ⇒ 一天之内版本号最多走一格。中间态看 git 历史；归档层只承诺"当天开始前的那一版"。断言见 `check_min_pair.py` 的 V7（前置条件：完整 git 历史，见 §6.8）。
- ⭐ **注释 / 文案改动不升号（2026-10-05 起）**：只改注释 / 文案 / 排版（配置键零变动，`.min` 逐字节不变）时**不升号、不入归档**，改动直接落进当天那张 Release 的同一版本号条目。与"一天一版"合起来的完整规则：当天已升过号 ⇒ 沿用同号；当天未升号且只有注释 ⇒ 不升号（号与 Release 归组停在上一版）；当天未升号且含配置键变动 ⇒ 正常升号 + 归档。
  ⚠️ 于是「版本号诞生日」与「内容诞生日」可以分离（号停在旧日、内容进了新日）—— 刻意如此：版本号是**功能**的刻度。Release 归组以**版本号首现日**为准（`release_publish.number_birth`），因此注释改动不会把旧版本号拖进新一天那张 Release。
- **当天第一次配置变动时**，变动前的旧配置归档进 `profiles/config_old/`：归档版本号 = 该目录内此分工最新号的下一位（2026-09-29 起三段制 X.Y.Z：Z=小修、Y=中改、X=大改，每位满 10 进 1，4.0.10 合法；历史两段号不回改），完整版与 `.min` 成对，现役头注同步升为下一位；更早历史看 git（备份 tag：`pre-cleanup-20260927`）；
- 因此：任何文档、脚本、README 里出现的"带版本号的订阅 URL"都是错的。

### 6.2 改配置的标准动线

```
① 改带注释完整版（lazy.conf / routing.conf / 对应 .yaml）
② 生成 .min：      python skill/tests/make_min.py --family routing|lazy|all        # 默认只出差异计划
                   python skill/tests/make_min.py --family all --apply              # 确认后写盘
③ 核豁免行：       .min 由生成器重算正文、按锚点继承注释 —— 仍要肉眼确认 `# audit-waive:` 那几行在 min 版里读得到
④ 升版（要对外发布时）：直接改四份 profile 头注里的 `#! version=`（`.min` 由生成器重算继承）
   —— ⚠️ **一天一版**：当天该产品线已升过号就跳过本步、沿用同号（见 §6.1）
⑤ 收尾：`python skill/tests/check_secrets.py && python skill/tests/check_portability.py && python skill/tests/check_min_pair.py && python skill/tests/check_links.py .`（push 后 CI 会再跑一遍同组检查）
   ↑ 也可一键：`python skill/tests/verify_all.py` —— 与 ci.yml 同源的 46 道闸门并行跑、出汇总表（含 DNS 审计与 releases 方案，比本行列的更全）
⑥ 发布 Release（push 之后）：`python skill/scripts/release_publish.py --apply`（时间线模型与规矩见 §6.9；发版前先补 `DAY_THEMES` 当日主题 + `PUBLIC_NOTES` 对应条目）
```

> **注意**　`.min` 不手工编辑。手工同步迟早漂 —— `check_min_pair.py` 会拿完整版对拍 `.min`，漂了就红。

> **注意**　`audit-waive` 是有语义的注释，同文件内编号不重复。

> **建议**　`make_min.py` 默认只出计划不写盘，`--apply` 才动文件 —— 先读计划再落盘是刻意设计。

### 6.3 DNS 段是"一份内容、四张脸"

`lazy` / `routing` × 完整版 / `.min` 共四份，DNS 相关键保持逐字一致（维护纪律，无自动判据）。

操作含义只有一条：改 DNS 段 = 一次改全套，闸门负责抓漏。想只给某一版加一条防泄露键，先问它为什么不是四条都要 —— 答案是"是"的才动手。

### 6.4 换设备与双端一致

本机与另一台设备（或新克隆）之间核对配置一致性，跑：

```bash
python skill/tests/check_portability.py
```

`check_portability.py` 逐条比对"两份拷贝是否等价"（规则清单现算，直接看脚本输出）。

换机常见坑：行尾（本仓 `.gitattributes` 统一 `text=auto eol=lf`，不要动任何人的 git config）、编码（脚本内部已钉 UTF-8 输出）、路径分隔符（拼接一律用 `/`）。

### 6.6 精简配置（给自己瘦身）

不要另开第三份配置 —— 历史教训是"同一件事写在两个地方，早晚会只改一处"（`v0` / `v1` 分叉就是这么砍掉的）。在你要用的那份上直接删，按收益排序：

| 可删 | 备注 |
|:-----|:-----|
| `[URL Rewrite]` 等附加节（Surge）/ 用不到的应用组 | 删组时连同指向它的规则一起删 |
| AI 分流（`AI` 组 + 规则） | 出口退回兜底 |
| `AD` 开关组（Surge） | 它不被规则引用，删了不影响拦截链路本体 |

| 不能删 | 原因 |
|:-------|:-----|
| `direct.txt` 域名直连集 | 判据 B 的一半 |
| `GEOIP,CN` / `geoip: CN`（连同 `no-resolve` 语义） | 判据 A 的一半；两条拆开即"只交一半" |
| 白名单 guard | 它必须排在 REJECT 之前，删了广告清单会开始误杀 |

删完必做：重跑分流覆盖审计与单侧回归（见 [验证与自检](troubleshoot-faq.md)）。

### 6.7 想加第三份配置

先问：这是新分工，还是老配置的另一种写法？后者一律否掉（那是版本分叉）。
确认是新分工后，走 [`surge/reference/profile-anatomy.md`](../surge/profile-anatomy.md) 维护者一节 —— 一句话判据：能过全部检查的才算一份新配置（固定名、`.min` 对拍、DNS 段一致）。

### 6.8 判据脚本的纪律

日常维护的正确姿势是：改配置与文档去适配判据，而不是改判据去适配配置。确实证明判据本身错了才动它，改动时写清"哪个反例会漏判、改后能抓住什么"。

**跑判据前先确认它的前置条件 —— 缺前置时的"红"不是缺陷，是噪声。** 两类最容易踩：

| 判据 | 前置条件 | 缺了会怎样 |
|:-----|:---------|:-----------|
| `check_releases` R3/R4 | **完整 git 历史**（`git log --find-object` 反查每个归档快照的诞生提交） | 浅克隆下历史被截断 → 早期快照查不到诞生提交 → 落不进任何日期分组，报出「tag 不在本地日期分组 plan 里」+「正文缺少 vX.Y 条目」的**成片假红** |
| `check_releases` 全脚本 | 网络 + `GITHUB_TOKEN`（缺省回退 `gh auth token`） | 远端不可达 → 走 SKIP（退出码 3），非判负；`verify_all` 会以 ⚠️ 明示「未验证 ≠ 绿」 |
| `check_min_pair` V7（一天一版） | **完整 git 历史**（版本诞生日期 = **现役版**取版本号首现日 `number_birth`；**归档版**取快照 blob 诞生日 `version_date`；均由 `release_publish.build_days` 现算） | 浅克隆 / 历史缺失 → 日期分组退化成「未知日期」，那些分组按**未验证**跳过并在该条说明里点名（不冒充通过）。该说明在**通过时也会打印**，正是为了不把它藏起来 |

⚠️ **浅克隆的实证（2026-10-04，一次外部审查踩的坑）**：审查者用 `gh repo clone -- --depth 50` 取了本仓（实际 **248** 个提交），跑 `check_releases` 得 `81 passed, 28 failed`；改用完整克隆后得 `113 passed, 0 failed`。⚠️ **这是姊妹仓 Self-Configuration 的数字**（2026-10-04 那次审查针对的是它）。**本仓 self-conf 的实际数字是 `79 passed / 0 failed`**（2026-10-08 首个 Release 发布后实测）——引用时别把两仓数字混用。四条「tag 不在 plan 里」与 23 条「正文缺条目」全部消失 —— 它们只反映历史缺失，不反映任何真实缺陷。

> 📖 **新增/修改闸门前，先读 [`gate-discipline.md`](gate-discipline.md)**：
> 三条注错铁律 + 怎么跑判别力矩阵 + 已验证清单。

### 6.8.1 无 CI 兜底的工具（用了才知道，别指望 CI 替你验）

以下脚本**不在 46 道闸门里**，CI 对它们**没有任何自动化兜底** —— 绿不绿都跟它们无关。
它们必须**人工在本地跑**，且各有硬前置（真内核 / 真网络 / 真订阅）。

| 脚本 | 为什么进不了 CI | 怎么跑 |
|:-----|:----------------|:-------|
| `skill/scripts/repo_state.py` | **一屏现状**（版本号 / 归档进度 / 最新 Release / CI 结论一次输出）—— 是 AI **动线①的开工动作**，不是判据 ⇒ 不进闸门，但**每个任务开工都该先跑它**（此前全仓 0 处引用，未登记 ⇒ 长期孤儿，2026-10-08 补登记） |
| `skill/tests/clash/check_real_kernel.py` | 需要**真实 mihomo 内核二进制 + 真实网络**。GitHub Actions 沙箱里两者都没有，塞进去只会得到一条**永远失败或永远跳过**的判据 —— 那比不跑更有害（会污染计数，正是 V3 那条修掉的老毛病） | 在有内核的机器上手动跑；它验的是「真机上到底通不通」，与静态判据互补 |

⚠️ 这条是**有意的设计，不是疏漏**。但「无兜底」这件事本身必须被看见 ——
所以写在这里，而不是让它默默躺在某个脚本头注里。
**新增任何不进闸门的脚本时，同步更新本节。**

### 6.8.2 `skill/scripts/` 的审计工具 —— 2026-10-08 已大部分进闸门

⚠️ **本节已被推翻重写**：原先判定这些工具「度量/诊断性质，不适合硬套判据」⇒
登记了事、靠人记得跑。**实测推翻了这判断** —— 它们都给出明确的过/不过（exit 0/1）。
现 11 项已进 46 道闸门（地区组判别力 ×3、分流覆盖 ×2、规则集内容 ×2、
刷新周期 ×2、DNS 转发泄露、no-resolve 配对），不再需要人记得跑。

⚠️ **又一次校准（同日）**：`profile_ruleset.py` 实测输出
「✅ 没有裸 IP 条目」+ 明确退出码 ⇒ 也可进闸门，已作为 #16–18 道接入（离线、快）。

至今**仍在闸门外的**（实测确认是纯读数 / 需联网，无过-不过语义）：
| 脚本 | 为什么留在外面 |
|:-----|:---------------|
| `weigh_ruleset.py` | 输出是条目列表与耗时读数，无判负语义 —— 排查「规则集太重」时手动跑 |
| `probe_doh.py` | 逐端点打印响应，无总结计数；且需联网 —— 排查 DoH 端点时手动跑 |
| `probe_dns_endpoints.py` | 有「失效端点：N / 总数」计数，**语义上可判负**，但需联网实测 10 个端点 ⇒ 网络抖动会造成假红。故**不进 46 道**，改由 CI 周任务级检查（同 check_remote_urls 的处理） |
| `profile_ruleset.py` | ✅ **已进闸门**（#16–18）|

### 6.8.3 `skill/scripts/` 是工具区，不是判据区（原始说明，保留沿革）

`skill/scripts/{surge,egern,clash}/` 下的**审计 / 探测 / 生成**脚本，大多**不进 46 道**，
也不在 CI 里 —— 它们是**人用的分析工具**，按需手动跑（都要传 `profile` 参数，
直接无参跑会打印 usage 并以 exit 2 结束，那不是崩溃）。

⚠️ 2026-10-07 零信任自查清点：以下 **6 个从未被任何闸门或 CI 调用**
（在 `.md` 里被提到不算真调用）：

| 脚本 | 干什么 | 什么时候该跑 |
|:-----|:-------|:-------------|
| `clash/audit_region_filters.py` | 地区组正则一致性（负向断言漏词 / 组间重叠） | 改地区正则后 |
| `egern/audit_region_filters.py` | 同上（Egern 侧） | 同上 |
| `egern/audit_ruleset_refresh.py` | 规则集刷新周期审计 | 改 `interval` / 新增远程集后 |
| `egern/audit_dns_forward.py` | DNS 转发泄露审计 | 改 DNS 段后 |
| `clash/weigh_ruleset.py` | 规则集体量/权重测算 | 评估规则集时 |
| `egern/probe_doh.py` · `probe_dns_endpoints.py` · `profile_ruleset.py` | 探测类工具 | 排查具体问题时 |

为什么不做成判据：它们多为**度量/诊断**性质（输出供人判断，不天然是"过/不过"），
硬套判据会得到一堆需要人工解读的"红"。保持工具定位，但**必须被看见** —— 故登记于此。

📌 已被闸门调用的（不用手动跑）：`audit_routing_coverage` · `audit_ruleset_content` ·
`audit_ruleset_noresolve` · `check_clash_dns` —— 这些**已进 46 道**。

📌 **本仓的 CI 不受此影响**：`.github/workflows/ci.yml` 已固定 `fetch-depth: 0`（该处注释亦写明"shallow clone 会把所有日期退化成 push 当天"）。这条纪律管的是**本地与人工审查**场景。

🔍 **判据的通用姿势**：断言报红时，先问「它依赖的输入是否齐全」（历史深度 / 网络 / 凭据 / 前置文件），再问「是不是真的不过」。⚠️ 但**反向也成立**：不得因为"可能是前置问题"就把红当噪声放过 —— 判据与 CI 结论冲突时（如 CI 绿、本地红），先查**两边跑法差异**（历史深度、工作目录、环境变量），再下结论。上面的实证里，审查者一度把该冲突解释成"CI 只验当前状态、本地更全"，方向正好相反。

### 6.9 Release 发布规矩

版本信息现在有三层落点：**现役**（固定名四件，版本号只在头注）→ **归档**（`config_old/`，文件名带头注同号）→ **发布**（GitHub Release）。发布层是归档层之上的对外窗口，不替代归档，也不改变 §6.1 的任何条文。

⭐ **三层节拍一致：一天一个。** 现役头注、`config_old` 归档、Release tag 都以自然日为节拍 —— 同一天里的多次改动共用一个版本号、落进同一张 Release。当天已发布之后又改，同一张 Release 会被 reconcile 更新成当天最终内容（版本号不变）；这是「一天一版」（§6.1）刻意换来的代价，断言在 `check_min_pair.py` 的 V7。

**粒度（时间线模型，2026-09-29 定稿）**：一个更新日 = 一个 Release，懒人版与分流版**同日更新合并进同一张**。为什么不用"一个分工版本 = 一个 Release"：Releases 列表按创建时间排序且 `created_at` 不可回写，分工版补发会让列表变成"先懒人版一块、再分流版一块"，时间线永远不正 —— 只有按日合并，列表顺序才与真实演进一致。同日多个版本在正文里逐版本列要点（内容不丢），资产只挂当日各产品线**最终版本**；回滚粒度 = 天，更细粒度走 git 历史与 `config_old/`。

**归组口径（2026-10-05 起）**：**现役版按「版本号首现日」**（`release_publish.number_birth`，即 `#! version=<fam>_v<ver>` 首次加进该 profile 的那天）；**归档版按「快照 blob 诞生日」**（`version_date`，快照是冻住的内容，与升号无关）。
为什么现役版不再用"文件内容姞生日"：与「注释不升号」（§6.1）配套 —— 若只改注释而号不动，文件 blob 的日期会跟着挑到现在，把旧版本号拉进当天那张 Release。号首现日不受无号改动影响。
⚠️ 用 `-G "^#! version=<号>$"`（`^$` 锚定整行）而**不是** `-S`（子串匹配），并取 `--reverse` 首条。早期版本（v1 / v2 / v3.0–v3.4）无 `#! version=` 头注 ⇒ 查不到，退回 blob 口径。
⚠️ -G 是**防御性**选择：当前两个产品线的现役号互不为前缀（互为前缀的如 `_v1`/`_v1.0` 只存在于**归档**，而归档走 `version_date`、不经这里），所以今天 -G 与 -S 结果相同；换 -G 是不对**未来**埋雷。
⚠️ 这个换 -G 的动作**无闸门可守**（2026-10-05 实测：把 -G 改回 -S，`check_releases` 仍 140 passed）—— 只能靠代码里的注释与 `-G` 本身。

`DATE_OVERRIDES` 表登记"版本号与内容不同日"的例外（首例：routing v3.5 —— c593895（09-26）一个提交同时给懒人版（v1.3）与分流版（当时头注 v3.4）加 `[SSID Setting]`，49392da（09-27）补归档升版只改头注 ⇒ Wi-Fi 自动暂停必须随内容归 9-26，两条产品线同框；劈到两张会让 9-27 那张看起来"只有分流版有此功能"）。

**tag**：`vYYYY-MM-DD`（该日版本的诞生日期），指向 main。tag 是发布层身份，**允许带日期** —— §6.1"带版本号的订阅 URL 是错的"指的是指向 `raw/main` 漂移内容的地址；Release 资产 URL 是钉版快照，允许且鼓励用于钉版。

**资产**：当日各产品线最终版本的两内核文件（完整版 + `.min`），固定名**带内核前缀**（`surge-lazy.conf` / `surge-lazy.min.conf` / `egern-lazy.yaml` / `egern-routing.min.yaml` 这样 —— Assets 面板自解释，不依赖「.conf=Surge / .yaml=Egern」的圈内约定），单张最多 8 件 —— **一律不带版本号**，这是铁律；版本号仅存在于正文条目。固定名全集单一真源 = `release_publish.ASSET_NAMES`，check_releases 的 R2 白名单从它派生。单边内核日如实注明（如某日懒人版仅 Surge 内核有内容），不硬凑。

**标题与说明模板**（`release_publish.py` 自动生成，字段固定防漂移；2026-09-29 用户二次定稿）：

标题 = 分类 emoji + 日期 + 当日主题（主题取自 `DAY_THEMES` 表）。正文层级（**H1 更新日志
标题永远置顶**，`## 共同变更` 这类节标题不得成为页面最大的字）：

```markdown
🛡️ 2026-09-29 · 监听端口收敛与 IPv6 对齐关闭     ← Release 标题（tag 芯片在旁显示 v2026-09-29）

# 懒人版 v2.0 / 分流版 v4.0 更新日志

> 本次两版同步，变更一致。

## 共同变更

### 1. 关闭局域网代理共享端口
- Surge：`allow-wifi-access = false`、`allow-hotspot-access = false`
- 影响：局域网共享出口由专用网关承担；本机不再开放监听端口，暴露面收窄。

### 2. 关闭 IPv6
- Surge：`ipv6 = false`、`ipv6-vif = disable`
- Egern：`ipv6: false`
- 影响：不再返回 AAAA 记录，双栈站点自动回落 IPv4；两版行为对齐。

## 适用版本

- 懒人版 v2.0
- 分流版 v4.0

[Surge · 懒人版] [Egern · 懒人版] [Surge · 分流版] [Egern · 分流版]
← shields.io 徽章，颜色编码内核、文字编码产品线；单边内核日该产品线只出一枚
```

条目两种形态：**结构化条目**（`('标题', ['Surge：键值…', 'Egern：…', '影响：…'])`，进 `### N. 标题`）
与**散文条目**（一句完整要点，维持列表项；历史条目即此形态，不硬编标题）。两产品线条目
归一化键完全一致才进「共同变更」，否则各写各的，不许为凑共用改写措辞。同日多版本时：
H1 与「适用版本」写版本区间（`懒人版 v1.2 → v1.3`），共同变更散文条目加粗
`**懒人版 v1.3 · 分流版 v3.5**：`前缀消歧，分侧条目加粗 `**vX.Y(.Z)**` 前缀；单边内核日在
引言括注（如「（懒人版当日仅 Surge 内核有内容变化）」）。
**没有元信息小字行**（资产策略、Assets 指引等说明性句子不进正文）。

更新内容 = `PUBLIC_NOTES` 表的要点列表（每版本 1~4 条，**逐版本如实总结**，依据是
config_old 相邻快照的逐行 diff —— 「维护性更新」「早期演进」这类万能句是模板句复用，禁止）。
**文风 = 面向用户的正式产品语言**（参考 Apple 更新说明）：完整句子、专业、克制、通俗；
不用文言腔（口径修正 / 收编 / 压到最小 / 上线），不搬内部过程语言。
⭐ **「不搬内部过程语言」的可执行判据（2026-10-05 立，来自「读起来容易困惑」被写进正文）**——
  写每一条前先问：**这句话对「只用配置、不看仓库」的用户有意义吗？**
  · ❌ **维护者视角**：讲「两个列表为什么对不上」「改起来容易困惑」「逐位对齐」「本只有一个成员、
    面板上无从选择」「此前排列不同」—— 这些是**我们内部的一致性问题**，用户看不到、也不关心；
  · ✅ **用户视角**：只写**用户能感知的结果** —— 分组少了几个、顺序变成什么、
    某个流量改走哪里、有没有行为变化。
  · 判据一句话：**把主语从「我们的列表/文档/注释」换成「分组/规则/流量」**。
    反例「规则集的应用段顺序改为与分组顺序逐位对齐（此前两者排列不同，读起来容易困惑）」
    → 正例「规则与分组的排列顺序已整理一致，面板上的分组先后与规则判定的先后一一对应」。
  · ⚠️ 同理禁止出现在正文里的词：「冗余」「无从选择」「逐位」「对不上」「容易困惑」
    「本只有一个成员」—— 它们是**设计取舍的内部理由**，属 `reference/` 文档，不属 Release 正文。
**两条硬要求（2026-10-01 定，来自两次实际改稿返工）**：
① **关键实体必须点名** —— 涉及哪个分组 / 文件 / 功能，就直接写它的名字（如「原 MAX 分组并入
   Smart 分组」），**不得**用「低倍率精选分组」这类模糊概括：那是把最该说的信息省掉了。
② **忌赘述** —— 同一句里不重复同一名词；**一件事只写一条**，不要为凑条数把同一件事拆成两条
   （拆开必然重复用词），也不要加「两者的」这类同义回指。
③ ⭐ **同日多次变动必须「归类整合」，不得机械堆叠**（2026-10-05 定，来自当日 8 条堆叠的返工）——
   一天一版意味着**当天所有改动共用一个版本号**，条目很容易被一次次改动**追加**成流水账
   （同一天里「移除韩国分组」「移除 GitHub 分组」「移除 Final 分组」被写成三条，
   实际是**同一件事**：分组精简）。要求：
   · **先归类、再落笔** —— 先把当天全部改动按**性质**归并（如「分组增减」「顺序与命名」
     「默认取向」「规则顺序」「注释」），每类**只写一条**，条内按类展开；
   · **同类合并要显式点数** —— 如「移除 A、B 与 C 三个分组」并给出**总量变化**
     （「分组数量由 24 个减少至 21 个」），读者一眼看到规模；
   · **变更过程中的中间态不进正文** —— 当天改了三轮同一处（如某个分组先建后删），
     只写**最终状态**相对**当天开始前**的差异；中间态属 git 历史，不属更新日志；
   · **判定「同类」用语义、不用文字** —— 「移除韩国分组」与「移除 Final 分组」字面不同、
     性质相同（都是删组且都不改变分流）⇒ 同类；「改顺序」与「改名」字面都像"调整"
     但一个是排序、一个是标识 ⇒ 可同类（都是「面板呈现」）也可分列，取决于当日总量，
     判据是**读者关心的粒度**，不是机械字面。
**内核维度写全称 `Surge` / `Egern`** —— 允许并列合并成「Surge / Egern 内核」（共享一个
「内核」后缀）；与产品线词汇（懒人版/分流版）严格区分，任何一句里两个维度不得混写。
⚠️ 同一句里**不得**把「内核」写两遍，也**不得**加「两者的」这类同义回指：
反例「Surge 内核与 Egern 内核同步支持该策略，两者的取值一致。」／
正例「Surge / Egern 内核同步支持该策略，取值一致。」。
下载按钮用 shields.io 在线徽章（`badge_url()`），不落仓库静态文件。

**说明是面向公众的产品更新日志，不是内部 commit 记录**：变更摘要一律取自
`release_publish.py` 的 `PUBLIC_NOTES` 表（公众向措辞），**禁止**把内部 commit subject
直接贴上去（「用户拍板」「实测反馈」「入档」这类过程语言只属于本仓库内部，出现在
Release 页就是内部讨论外泄）；「更新内容」写"这版给使用者带来了什么"，不写"我们怎么决定的"。
**发新版本前必须先在 `PUBLIC_NOTES` 补对应条目、`DAY_THEMES` 补当日主题** —— 这是动线⑥的一部分。
（已修正的教训：①旧实现把"归档文件入 repo 的提交主题"当摘要，那永远是退役提交，
写的实际是**下一个版本**的内容 —— 版号整体错位一格；②摘要直接搬运 commit subject；
③缺侧说明曾把"缺席的内核"写成"仅提供 XX 侧文件"，方向颠倒。）

**命令**：

```bash
python skill/scripts/release_publish.py                      # 计划模式：列日期分组清单 + 说明样例，不发
python skill/scripts/release_publish.py --apply              # 补齐缺失 Release（按日期升序创建）+ 幂等回写
python skill/tests/check_releases.py                         # 断言：tag 形状 / 资产命名 / 标题与正文模板一致 / 版本全覆盖 / Latest
```

**判据**在 `skill/tests/check_releases.py`（CI 同跑）：R1 tag = `vYYYY-MM-DD` 且唯一；R2 资产文件名 ∈ 固定名集合且无版本号样式；R3 标题与正文模板一致（与 `release_publish` 同源，取真 plan）；R4 覆盖 —— `config_old` 全部归档版本 + 现役版本，每个 (产品线, 版本) 都按诞生日期出现在对应日期 Release 的正文里（`**vX.Y**` 条目），**删归档版本或删 Release 都会红**；R5 仓库级 **Latest** = 含现行版本的那张（最新日期）。`release_publish.py` 仅在 Latest 未指向现行日时补钉（逐个 PATCH 会让指针抖动，与 CI 竞态）。

### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 改 DNS 段之前先读泄露面 | [DNS 基础](dns-basics.md) |
| Surge 侧的操作动线 | 本篇「Surge 操作」章 |
| Egern 侧的操作动线 | 本篇「Egern 操作」章 |
| 换、加、删任何规则集之前 | [规则集与素材](rulesets.md) |
| 出问题了 | [故障排查 · FAQ](troubleshoot-faq.md) |
| 把本篇改动同步到对侧内核 | [跨内核移植](cross-kernel-diff.md) |
