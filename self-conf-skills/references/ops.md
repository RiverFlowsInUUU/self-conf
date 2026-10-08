# 运维 · 日常操作、加固清单与发版


## 日常操作

> 由原手册 03、04、06 三章合并。装完之后怎么改、怎么维护，都在这一篇。
> mihomo 章是整合后新增 —— 那一侧的目录与生成链跟 Surge / Egern **不是同一套**
> （配置真源是覆写脚本，不是静态 profile），动手前先读本篇「mihomo 操作」的「改配置的正确顺序」。

### 三侧共通：动手前先记住五条

三个内核目录并列（`surge/` · `egern/` · `clash/`），各写各的语法，但**操作层的规矩是共通的**。
下面五条先记住，再翻到对应内核那一章；各侧独有的东西（文件结构、改配置的动线、生成器）在各自章里。

| # | 规矩 | 落点 |
|:-:|:-----|:-----|
| 1 | **固定名四件**：每侧现役只有 `routing` / `lazy` × 完整版 / `.min` 共四件，订阅地址不随版本改名 | 三侧一致，见 §6.1 |
| 2 | **`.min` 不手工编辑**：它是"同一份配置去掉注释"，漂了肉眼看不出来 | Surge / Egern → `make_min.py`；mihomo → `build_profiles.py`（见下表） |
| 3 | **改完跑全套闸门**：`python self-conf-skills/gates/verify_all.py`（全套闸门（含 mihomo 相关）） | §6.2 动线⑤ |
| 4 | **不提交真实地址 / 凭据 / token** | `check_secrets.py` 两份都跑（跨内核版 + mihomo 版，见「两份 secrets 扫描」） |
| 5 | **改配置去适配判据，不是改判据去适配配置** | 本篇「判据脚本的纪律」 |

三侧现役件与生成器对照 —— **生成器这一列是本仓最容易记错的地方**：

| 内核 | 现役四件 | `.min` 由谁生成 | 配置真源 |
|:-----|:---------|:----------------|:---------|
| Surge | `surge/profiles/{routing,lazy}.conf` + `.min.conf` | `self-conf-skills/run/make_min.py --apply` | 完整版 `.conf`（手工维护） |
| Egern | `egern/profiles/{routing,lazy}.yaml` + `.min.yaml` | 同左 | 完整版 `.yaml`（手工维护） |
| mihomo | `clash/profiles/{routing,lazy}.yaml` + `.min.yaml` | `self-conf-skills/run/clash/build_profiles.py` | **`clash/override/*.js`**（脚本才是真源） |

> ⚠️ mihomo 那一行的"配置真源"是三侧里唯一的例外：Surge / Egern 改**完整版**，
> mihomo 改**覆写脚本**、再由脚本生成静态 profile（见本篇「mihomo 操作」）。别把两侧的习惯带过去 ——
> 手工改 `clash/profiles/*.yaml` 会被下一次重生成整份覆盖（§5.3）。
>
> ℹ️ 版本头注**三内核通用**：mihomo 静态 profile 也带 `#! version=` 头注，三内核同号（§5.10）。

### Surge 操作

对象：`../surge/profiles/` 下 `lazy` / `routing` 两版（各含带注释完整版与 `.min` 版）。
加固清单逐项与验收标准见 [`ops.md`](./ops.md)（清单本体在那份文件，本章讲怎么用它）；逐键权威是 [`surge.md`](./profiles/surge.md)。

#### 3.1 文件结构速览

Surge 的 `.conf` 按节组织，模板里与防泄露相关的节：

| 节 | 作用 | 防泄露相关 |
|:---|:-----|:-----------|
| `[General]` | 全局开关 | DNS 段全部键都在这里：`dns-server`、`encrypted-dns-server`、`hijack-dns`、`always-real-ip`、测试端点等 |
| `[Proxy]` | 静态节点 | 仅 `lazy` 有（占位节点）；`routing` **段为空**，节点全来自订阅（2026-10-06 起） |
| `[Proxy Group]` | 策略组 | 出口选择逻辑 |
| `[Rule]` | 规则 | 顺序即优先级，见 3.4 |
| `[URL Rewrite]` / `[Header Rewrite]` 等 | 附加功能 | 与防泄露无关，可整节删 |

> **说明**　两份配置的 `[General]` DNS 相关键四份（`lazy` 与 `routing` 及各自 `.min`）保持逐字一致 —— 这是维护纪律，没有自动判据，改 DNS 段时四份一起改（流程见下文「日常维护」）。

#### 3.2 `[General]` DNS 段：每行堵哪个出口

对照 [DNS 基础的泄露面全景](./dns.md)，这些键各自堵一条通路：

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

#### 3.3 广告拦截：pre-matching 与 AD 组的分层

模板里广告拦截有两条清单：白名单 guard 在前、拦截在后。关键约束：

> **注意**　`pre-matching` 的规则，策略必须是字面量 `REJECT` 家族，不能是策略组。预匹配发生在"还来不及决定出口"的阶段；策略组运行时可能解析成 `DIRECT`，Surge 会直接拒绝加载整份配置。

所以链路是刻意的分层：拦截规则写字面量 `REJECT`，换取 DNS / SYN 阶段即拒、不建连不解析（全模板最大的一笔省电优化）；旁边 `AD` 组作为独立手动开关，不被任何规则引用，职责是给人工干预留入口——成员只有 `REJECT` 一个（分流版 Surge 的同位组另挂一个 `DIRECT` 兜底）。

想让面板开关接管拦截？可以，但要一并去掉 `pre-matching`，接受"先解析再拒"的代价。

#### 3.4 `[Rule]` 顺序铁律

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
3. `GEOIP` 必须带 `no-resolve`，且必须与 ⑤ 成对。见 [DNS 基础](./dns.md)。

> **说明**　两版 `[Rule]` 都没有游戏机域名规则（`nintendo.net` 等只在 `always-real-ip` 里）—— 这些主机名照旧拿真实 IP，去向由常规规则链决定。别把"缺这三条"当 bug 来"修"。

#### 3.5 分流版（`routing.conf`）要点

完整的分组层次与逐条规则表直接读 [`routing.conf`](../../surge/profiles/routing.conf) 本体（注释齐全）。这里只讲动手最容易撞的四条墙。

##### ① smart 组不能拿组名当子策略

官方限制：Smart 组不可使用其他组作为子策略，也不可用作 `url-test` / `load-balance` 组的子策略。等价做法是 `include-other-group`：

```ini
Proxy = smart, include-other-group="Airport"    # ✅ 拿到的是解析后的具体节点
Proxy = smart, Airport                           # ❌ 成员是"Airport"这一个组名，测不到组内节点
```

##### ② flatten 的对应物

Egern 的 `flatten: true` 在 Surge 没有同名字段，语义对应 `include-other-group`（官方："includes the resolved member policies from other policy groups"）。应用组因此写成：

```ini
ChatGPT = select, include-other-group="Proxy"
```

差异要说白：Egern 应用组自 `routing_v3` 起同为手动 `select`（旧版是 `fallback`），与 Surge 的 `select` 现版同形。想要应用组自动选优：Egern 换 `fallback` / `smart`、Surge 把某组换成 `smart, include-other-group="Proxy"`，代价是面板不能再手动挑节点。旧版这处确是能力差异，现已拉平 —— 史实写明，不假装一直没差过。

##### ③ 地区组靠正则筛名字，且有两个开关要一起开

```ini
Hong Kong = smart, include-all-proxies=true, include-other-group="Airport", policy-regex-filter=(?i)🇭🇰|香港|…
```

- `policy-regex-filter` 对显式列出的成员无效 —— 手写在 `[Proxy]` 里的节点，必须靠 `include-all-proxies=true` 才会被筛到；
- 正则别写太宽：`(?i)us` 会同时命中 `Russia` / `Belarus` / `AUStralia`，保守用 `\b` 锁词边界；
- `Other Regions` 是负向断言，把其余地区组的关键词逐字抄了一遍 —— 任何组加关键词必须同步改它，漏改不报错、面板也看不出（节点会同时出现在两个组）。这条拷贝在配置层面消灭不掉，靠 `audit_region_filters.py` 守（用法见 [验证与自检](./pitfalls.md)）。

##### ④ 已知边界（都是设计，不是 bug）

| 边界 | 说明 |
|:-----|:-----|
| 空地区组 | 节点名不含关键词则该组为空，指向它的规则会断流。导入后到面板确认 |
| `Smart` 权重 = 低倍率优先 | 全部 smart 组（`Smart` + 6 个地区组）带 `policy-priority` 0.15：默认出口优先落低倍率节点（省钱但可能稍慢），与 Egern 对齐；不想要就把这项权重去掉 |
| `https` 类型节点不支持 UDP 中继 | 别让承担 UDP 的组落到它们 |
| Apple 无独立策略组 | 走 `Apple` 规则 → DIRECT；要"给 Apple 挑地区"得自己复制 select 组 |
| 段内顺序 | 与 Egern 逐位对齐（维护纪律）；"先写引用别人的，后写被引用的"，Surge 允许前向引用 |

#### 3.6 你必须替换 / 可以删除的

必须替换（逐键语义见 [`surge.md`](./profiles/surge.md)）：

- `lazy` 的 `[Proxy]` 占位节点（`routing` 此段已空，无需替换）；
- `routing` 的 `Airport` 组 `policy-path` 占位订阅地址；
- 两份 `[SSID Setting]` 段里的 `SSID:MyHome` —— `MyHome` 是照官方示例留的占位网络名，不替换就匹配不到任何 Wi-Fi，「回家自动暂停」静默不生效。该段只有 Surge 侧有，Egern 无对等件（见 [`rulesets.md`](./rulesets.md) §1「网络级暂停」）。

可以删（按收益排序，删完必须重跑分流覆盖审计）：

- `[URL Rewrite]` / `[Header Rewrite]` 等附加节；
- AI 分流（`AI` 组 + 对应规则）；
- `AD` 组（反正不被规则引用）。

不能删：`direct.txt` 规则、`GEOIP,CN`（连同 `no-resolve` 是一对）、白名单 guard。删任何一个都会立刻构成 [DNS 基础](./dns.md) 说的"只交一半"。

改 `routing.conf` 想加新应用组：照 §3.5 的写法复制一个 `select, include-other-group="Proxy"` 组，把它的规则插在国内直连集之前，并给 `audit_routing_coverage.py` 加对应探针（期望值精确到组名，不许放宽成"不是 DIRECT 就行"）。

#### 3.7 官方文档入口

- 策略组 / `include-other-group`：[manual.nssurge.com/policy-groups/policy-including.html](https://manual.nssurge.com/policy-groups/policy-including.html)
- Smart 组限制（中文）：[kb.nssurge.com · smart-group](https://kb.nssurge.com/surge-knowledge-base/zh/guidelines/smart-group)
- 其余逐节引用见 `profile-anatomy` 各节脚注。

#### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 对侧内核的操作章 | 本篇「Egern 操作」章 ·「mihomo 操作」章（均已并入本篇） |
| 换、加、删任何规则集之前 | [规则集与素材](./rulesets.md) |
| 出问题了 | [故障排查 · FAQ](./pitfalls.md) |
| 把本篇改动搬到 Egern 侧 | [跨内核移植](./rulesets.md) |
| 名词不认识、常见疑问没解决 | [FAQ 与术语表](./pitfalls.md) |

### Egern 操作

对象：`egern/profiles/` 下 `routing.yaml`（推荐，完整分流）与 `lazy.yaml`（懒人配置），各含带注释完整版与 `.min.yaml` 形态，共四件，历史版本看 git。
加固清单在 [`ops.md`](./ops.md)；逐键权威是 [`egern.md`](./profiles/egern.md)。

#### 4.1 顶层字段：值等于默认的不写

Egern 的 YAML 顶层：`ipv6`、`vif_only`、`hijack_dns`、`geoip_db_url` / `asn_db_url`、两个延迟测试 URL、`real_ip_domains`、`default_proxy_group` 等。三条维护经验：

1. 值恰好等于官方默认值的行是冗余（`routing_v2.1` 一次性删掉了五十多行这种）。读旧版看到它们，别当"定制"。
2. 非默认值必须显式写，尤其 `vif_only: true`（官方只有一句"虚拟网接口模式，默认 false"，细节无法确认）。遇到"某些 App 不走代理"，它是第一个 A/B 候选，但别凭猜测替用户改。
3. `hijack_dns: ['*']` 接管 `:53` 并返回 Fake IP；`real_ip_domains`（`*.lan` / `*.local` / `*.push.apple.com`）让推送与内网发现拿真实 IP —— Fake IP 反而会让 APNs 异常。
4. **例外（2026-09-29 定）**：两内核对齐面的显式声明键不适用第 1 条 —— `ipv6: false` 虽等于默认值也必须写，让"四份对拍"看文件即知、不用查各内核默认值；同类对齐面键若将来出现，照此办理。

#### 4.2 `dns:` 段：五小节，一个原则

原则一句话：`bootstrap` 唯一安全的形态是"永远不被触发"。逐节要点：

| 小节 | 要点 |
|:-----|:-----|
| `bootstrap` | 全国内明文 IP，绝不写 `system`（等于把运营商接进回退链）。也别指望"换更好的 bootstrap IP"：实测换 IP 后泄露仍来自透明重定向 / 回退，机制见 [DNS 基础](./dns.md) 的泄露面各出口 |
| `upstreams` | `Domestic-DNS` 端点全部 IP 字面量（消灭 bootstrap 用途①）；「两家机构 × 两种协议」的冗余结构，同组并发竞速、全组失败才触发回退。`Foreign-DNS` 整组已注释保留：它必须经代理才可达，不能当兜底（启动期解析会掉进明文）。Quad9 教训：`https://9.9.9.9/dns-query` 静默失效（只提供 HTTP/3），`tls://9.9.9.9` 可用 |
| `forward` | f10 起塌缩为纯兜底（指向 `Domestic-DNS`）—— 换订阅、换节点域名，本段一个字都不用改。两条兜底与一条等价的原因：value 单值 + 顺序求值，删任何一条行为不变（`audit_dns_forward.py` 可证） |
| `proxy_nameservers` | 硬覆盖：一设就绕过 `forward`、强制直连、成为代理侧解析的唯一出口。"不设"本身也留了一条"未命中回退 Bootstrap"的明文分支 —— 模板最终选择显式设置 + 国内端点（它是强制直连的，境外解析器在国内线路不可达）。排障口诀：节点连不上，第一件事注释掉这个列表 |
| `hosts` / `block_ips` | `hosts` 是"端点写主机名"时代的补救，端点全 IP 后无引用点、已删；`block_ips` 丢弃空路由式污染应答，刻意不含私网段，免误伤内网 |

已知代价（完整版见 `profile-anatomy` 的取舍节）：设置了 `proxy_nameservers` + 兜底国内组，需要本地解析的境外域名会拿到国内答案，实际影响面仅限 `DIRECT` 域名。审计里那两条 `LOW`（一条是 `proxy_nameservers` 成为代理侧解析唯一出口，一条是 `forward` 兜底指向国内组）就是它 —— 是取舍，不是缺陷。

#### 4.3 `proxies:` 与节点形态

- 分流版模板 `proxies` **为空**（节点全来自订阅，2026-10-06 起）；懒人版模板带 2 条占位节点（`Node-A` / `Node-B`），`server` 都写成 IP 字面量。
- 自己填节点时，`server` 能写 IP 就写 IP：写域名必然产生一次"本机 + 直连 + 明文"解析（代理还没通）。这是从根上消除节点域名解析面的唯一办法；中转 `prev_hop` 同理，且无需为节点域名改 `forward`。

#### 4.4 `policy_groups:`：四类组与三个易踩的坑

组分三类：入口（`Proxy`）、应用组（`ChatGPT` / `Gemini` 等，现行版皆为 `select`，旧版才是 `fallback`）、智能组（`Smart` 与各地区组，皆 `smart`；地区组用 `filter` 正则筛名 + `flatten: true`；两者都带低倍率优先权重）、订阅槽位（`external` 组，`hidden: true`，当前版只有一个 `Airport`；旧版为 `Airport-A` / `Airport-B` 两槽、更早四槽）。

必须知道的三条：

1. `flatten: true` 把组名展开成组内全部具体节点，让 `fallback` / `smart` 做节点级尝试。`fallback` 不给 `flatten` 时，`policies: [Proxy]` 只有一个候选单位，等于没有故障转移。官方明确 `flatten` 在 `select` / `auto_test` / `smart` / `fallback` / `load_balance` 五种类型通用。
2. `fallback` 不做延迟择优，按顺序取第一个可用。想固定地区，把目标写首位；想自动挑最快，改 `smart`。`ChatGPT` / `Gemini` 在旧版曾是空组 `[]` 而规则直指它们，导入即静默断流；当前版已填 `[Proxy]` + `flatten`，且这两组自 `routing_v3` 起已由 `fallback` 改为 `select`。
3. 低倍率优先改由**权重**承担：全部 smart 组（`Smart` + 6 个地区组）写 `policy-priority` / `priorities` 系数 0.15，两内核同值同正则；`Proxy` 首项即 `Smart`，默认出口因此优先落低倍率节点，低倍率不可用或过慢时**自动让位**。该正则须带左边界以免误收 `10.1` / 漏收 `0.5`。改任何地区组 filter 关键词，必须同步 `Other Regions` 的负向断言（`audit_region_filters.py` 守）。

`lazy` 特有：只有 `Proxy` / `AI` / `AD` 三组；`Proxy` 组 `policies` 为空，必须自己填节点名；`AD` 子策略只有 `REJECT`（无 `DIRECT` 兜底）。临时放行单个域名，在 `rules` 更前面加一条 `DIRECT` 规则，别整组切走。

#### 4.5 `rules:`：分四段理解顺序

| 段 | 内容 | 要点 |
|:--:|:-----|:-----|
| A | DNS 端点固定路由 | 已整体移除。端点全是 IP 字面量，解析器直接以 IP 访问，不需要在 `rules` 里钉。只有你自己把 DNS 端点写成主机名时，才需要补一条 `DIRECT` 路由，否则它落 `default → Proxy` |
| B | 白名单 guard → 广告 → 内网 → 各应用规则集 | 顺序即优先级；`Proxy.list` 类"默认 `disabled: true`"的规则由 `Final` 兜底；AI 规则集 URL 钉 commit 防上游漂移；每条 `rule_set` 各自带 `update_interval`（现值两侧统一钉 `604800`，别只写第一条） |
| C | Apple（`apple.txt`）→ `direct.txt` → `.cn` 后缀 → `geoip: CN` + `no_resolve` | 这就是 [成对交付篇的判据 A+B](./dns.md) 在本内核的落点：`geoip` 带 `no_resolve` 后不匹配域名，国内域名直连完全依赖 `direct.txt` 那条纯域名规则集，动一条必须看另一条。Apple 那条 2026-10-04 起引零 IP 的 `apple.txt`（与 `direct.txt` 同仓库同 release）；此前是 `Apple_All_No_Resolve.list` —— 它的**原版**藏 13 条裸 IP、会强制解析，所以当时必须锁定 `No_Resolve` 变体 |
| D | `default: {name: Final, policy: Proxy}` | 未命中走代理，由节点远程解析、不经过 `dns` 段 —— 日志里的 `default → Final → Proxy` 是正常决策，不是泄露。`lazy` 没有 `Final` 这层组，`policy` 直写 `Proxy`；`name: Final` 只是日志标签 |

> **注意**　`no_resolve` 有三层，写之前先确认自己在哪一层：规则级（`geoip` / `ip_cidr` 的 `no_resolve`）、`rule_set` 级（在这里写不生效，这是坑）、条目级（`.list` 每条自带的 `,no-resolve`）。

`default_proxy_group: Proxy` 不是兜底：官方定义是"添加代理时自动加入的策略组"。改它不换出口，删它则手动新加的节点不进组。Egern 只有一条兜底通路，就是 `rules` 末尾的 `default`。

#### 4.6 分流顺序与应用组默认出口

逐位匹配顺序表直接读 [`routing.yaml`](../../egern/profiles/routing.yaml) 的 `rules:` 段注释。
两条与 Surge 侧共同的铁律同样成立：应用规则必须排在 `direct.txt` 之前；具体的在前、兜底在后。
应用组的 `policies` 里只有 `Proxy` 一项（+ `flatten`）—— 这是设计，不是"忘了加地区"；想固定地区，改首位即可。

#### 4.7 必须替换与环境

- 必填：`Airport`（旧版 `Airport-A` / `Airport-B`）订阅组的 `url(s)` 占位，换成你的订阅地址。当前版所有分流组已填好 —— **分流版填完这一个占位就能直接导入**（节点全来自订阅）。
- 懒人版另可选：`proxies` 里那 2 条占位节点换成你的自建节点（`server` 尽量 IP），或整条删掉并把组里的名字一并摘掉。
- 运行审计脚本需要 Python 3 + PyYAML（本仓唯一第三方依赖）。
- 官方文档入口：DNS `https://egernapp.com/docs/configuration/dns` · rules 字段 `https://egernapp.com/docs/configuration/rules` · 顶层字段全表 `https://egernapp.com/docs/configuration/example`（两处页键名不一致，以 example 页为准）。

> **注意**　`https://egernapp.com/zh-CN/docs` 与 `https://egernapp.com/docs/configuration/general` 是 404，别按其他客户端文档站的直觉找路径。

#### 4.8 改完之后的验证

```bash
python self-conf-skills/gates/egern/check_egern_dns.py         egern/profiles/routing.yaml
python self-conf-skills/run/egern/audit_ruleset_noresolve.py egern/profiles/routing.yaml   # 联网：下载规则集数条目
python self-conf-skills/run/egern/audit_routing_coverage.py  egern/profiles/routing.yaml   # 联网：真实域名走规则链
python self-conf-skills/run/egern/audit_dns_forward.py       egern/profiles/routing.yaml
python self-conf-skills/gates/egern/check_egern_dns.py egern/profiles/lazy.yaml egern/profiles/routing.yaml
```

判据逐项见 `self-conf-skills/gates/egern/check_egern_dns.py` 头注。
最后在目标链路（尤其蜂窝）跑一次 leak test，并先写下"哪台设备、哪条链路、谁的 DNS" —— 混链路会让整轮结论作废。

#### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 对侧内核的操作章 | 本篇「Surge 操作」章 ·「mihomo 操作」章（均已并入本篇） |
| 换、加、删任何规则集之前 | [规则集与素材](./rulesets.md) |
| 出问题了 | [故障排查 · FAQ](./pitfalls.md) |
| 把本篇改动搬到 Surge 侧 | [跨内核移植](./rulesets.md) |
| 名词不认识、常见疑问没解决 | [FAQ 与术语表](./pitfalls.md) |

### mihomo 操作

对象：`clash/` 下的**两种交付形态**（静态 profile 四件 + 覆写脚本两份）。
加固清单在 [`ops.md`](./ops.md) 的 mihomo 侧；
逐键权威（语义、边界、取舍）是 [`clash.md`](./profiles/clash.md)
—— **那一篇是权威，本章只讲动线与坑，不重复逐键语义**；
门禁命令与判据细节在 [`gates.md`](./gates.md)。

> 📌 **三侧里只有这一侧"配置真源不是 profile 本身"**：改配置改的是 `override/*.js`，
> 静态 `profiles/*.yaml` 由脚本生成。这是最容易带错的一侧，先读 §5.2 再动手。

#### 5.1 文件结构速览

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

> ℹ️ **过期文字已清理（2026-10-07）**：此前脚本头注与覆写脚本文档里写着旧数字
> （`my_clash.js`「20 组 / 20 份 / 26 条」、`routing.yaml`「23 / 22 / 24」、`my_clash_lazy.js`「5 MRS + 5 yaml」等），
> 现已全部按实际值更正为 22 组 / 25 份 / 27 条（分流版）与 3 组 / 10 份 / 11 条（懒人版）。
> **判据以配置文件为准** —— 头注数字由 `check_header_numbers.py` 与脚本实际输出对拍。

#### 5.2 改配置的正确顺序

```bash
① 改真源：        clash/override/my_clash.js        （或 my_clash_lazy.js）
② 重生成 profile： python self-conf-skills/run/clash/build_profiles.py
                  # 一次性写好 routing/lazy 的 .yaml 与 .min.yaml 四件
③ 若动了规则集内容：python self-conf-skills/run/clash/build_rules.py   # rules/*.list → *.yaml
④ 跑全套闸门：      python self-conf-skills/gates/verify_all.py            # 全套闸门，含 mihomo 相关
```

> ⚠️ **步骤 ② 不可跳过，也不可用手工同步替代。** 脚本与静态是同一套配置的两个形态，
> 由 `check_script_sync.py` 逐位对拍（比 `rules`、`rule-providers` URL 集合、
> `proxy-groups` / `dns` / `ipv6`）。只改一边 ⇒ 用户遇到「照文档用脚本订阅，
> 效果跟直接导入配置不一样」，而两边都能正常跑、都不报错 —— 只能靠对拍发现。
>
> ⚠️ **步骤 ② 的 `--check` 是门禁**（`build_profiles.py --check` 是闸门之一）：
> 脚本有更新而静态 profile 没重生成 ⇒ 判负。想只看看有没有漂移，跑这个。

三个只在这一侧存在的环节，逐个说清：

| 环节 | 脚本 | 判据 |
|:-----|:-----|:-----|
| 静态 profile 新鲜度 | `self-conf-skills/run/clash/build_profiles.py --check` | 脚本输出 ≠ 静态文件即判负（闸门 #46） |
| 规则集生成物新鲜度 | `self-conf-skills/run/clash/build_rules.py --check` | `.yaml` 与 `.list` 真源不一致即判负 |
| 脚本 ↔ 静态对拍 | `self-conf-skills/gates/clash/check_script_sync.py` | 需 **node**（Windows 下由 `_clash_common.find_node` 显式探测；Git Bash 的 PATH 不继承给 subprocess） |

#### 5.3 不要手工改 `profiles/*.yaml`

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

> ⚠️ **每次手工改过 profile 之后**，跑 `python self-conf-skills/run/clash/build_profiles.py --check`
> 确认生成器认为"已是最新" —— 若它说"已过期"，说明有改动没回灌进脚本，
> 要么把改动搬进 `override/*.js` 重生成，要么接受下次重生成时被覆盖。

#### 5.4 规则集：改 `.list` 真源，再生成 `.yaml`

`rules/` 是本仓**三内核共享真源**（合并最直接的收益）：

| 唯一真源 | 条数 | 生成物 | 谁消费 |
|:---------|----:|:-------|:-------|
| `rules/AI.list` | **272** | `rules/AI_Domains.yaml` | Surge / Egern 直接引 `.list`；mihomo 引 `.yaml`（classical） |
| `rules/apple_system.list` | **18** | `rules/apple_system.yaml` | Egern 补 Surge 内置 `SYSTEM`；mihomo 用 `.yaml` |
| `rules/emby.list` | **4** | `rules/emby.yaml` | 同 AI |

```bash
python self-conf-skills/run/clash/build_rules.py            # 生成
python self-conf-skills/run/clash/build_rules.py --check    # CI 用：过期即判负（闸门 #39）
```

改内容**只改 `.list`**，重跑脚本 —— 物理上不可能漂移。
❌ **不手工编辑 `rules/*.yaml`**（生成物；`AGENTS.md` 的红线之一）。
mihomo 其余 **20 份 `.mrs` 远程集 + 5 份 YAML** 不在此链上，由 `rule-providers` 自己管理。

#### 5.5 日常验什么、用哪个脚本

| 想验什么 | 跑哪个 | 联网 |
|:---------|:-------|:----:|
| 结构 / 悬空引用 / 广告双条件 / **禁止 tun** / IPv6 / 零 dat | `self-conf-skills/gates/clash/check_structure.py`（8 项） | 否 |
| 防 DNS 泄露语义（分级发现） | `self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/routing.yaml` | 否 |
| `.min` 与完整版是否漂移 | `self-conf-skills/gates/check_min_pair.py` | 否 |
| 脚本 ↔ 静态是否漂移 | `self-conf-skills/gates/clash/check_script_sync.py` | 否（需 node） |
| 规则集生成物是否过期 | `self-conf-skills/run/clash/build_rules.py --check` | 否 |
| 静态 profile 是否过期 | `self-conf-skills/run/clash/build_profiles.py --check` | 否（需 node） |
| **远程集 URL 是否还活着** | `self-conf-skills/gates/clash/check_remote_urls.py` | **是**（慢，按需） |
| 全部（含 Surge / Egern） | `python self-conf-skills/gates/verify_all.py` | 部分 |

一键命令（详见 [`gates.md`](./gates.md) §2）：

```bash
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/lazy.yaml clash/profiles/routing.yaml
python self-conf-skills/gates/clash/check_structure.py
python self-conf-skills/gates/check_min_pair.py
python self-conf-skills/gates/clash/check_script_sync.py
python self-conf-skills/gates/clash/check_remote_urls.py          # 慢，按需
```

当前基线（2026-10-07 实测）：`check_clash_dns.py` 分流版 **0 high / 0 medium / 7 LOW / 21 OK**，
懒人版 **0 high / 0 medium / 2 LOW / 21 OK**；`check_structure.py` 四份 profile 全绿。

那些 **LOW 是取舍，不是缺陷**，别去"修"它们：分流版 `proxy-server-nameserver` / `direct-nameserver`
的国内端点写的是主机名（`doh.18bit.cn` / `dns.alidns.com`）⇒ 引导期明文解析一次，信号弱（只带出"本机在用哪个 DoH"）；
`dns-hijack: any:53` 未接管 TCP:53（不写协议前缀时默认 `udp://`，明文 TCP 查询在现代客户端罕见）；
5 个 `classical` 规则集内容无法静态判定（本仓自托管的 `rules/*.list` 实测 0 条 IP 条目）；
`fallback-filter.geoip: true` 是双倍延迟、不是泄露。**改它们之前先问一句"我真的需要吗"**（懒人版干脆不开 `fallback` 就是同一个判断）。

> ⚠️ **审计通过 ≠ 配置可用**（三侧共通的母题，见 [故障排查 · FAQ](./pitfalls.md) §7.5）。
> mihomo 侧**已有**专用的分流覆盖审计脚本（`self-conf-skills/run/clash/audit_routing_coverage.py`，闸门 #9；2026-10-07 补出）。Surge / Egern 各自也有。
> 因此每次增删 `no-resolve`、替换 `cn` provider、或移动 `MATCH` 前的规则时，
> 仍要人工核对三条：`cn` 仍是 `behavior: domain` 的国内域名集；
> `RULE-SET,cn,DIRECT` 仍在 `MATCH,Proxy` 之前；用国内**非 `.cn`** 域名验证，不能只测会被后缀兜底救活的样本。

#### 5.6 两种交付形态分别怎么维护

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

#### 5.7 必须替换与环境

- **必填（两形态各一处）**：静态 profile 的 `proxy-providers.Airport.url`
  （当前占位 `https://sub.example.com/api/v1/client/subscribe?token=REPLACE_WITH_YOUR_TOKEN`）
  换成你自己的订阅地址。不换 ⇒ 走代理的流量全不通 —— 占位地址是 `example.com`，不是真实服务。
- 覆写脚本不需要这一步：它保留传入订阅自己的 `proxies`（若订阅还带 `proxy-providers`，
  脚本自动从 `include-all-proxies` 切到 `include-all`，避免 provider 里的节点成为孤儿）。
- 运行门禁需要 **Python 3 + PyYAML**（本仓唯一第三方依赖）；`check_script_sync.py` 与
  `build_profiles.py` 另需 **node**（跑 `override/*.js` 取输出）。
- 从**仓库根**调用门禁。四个 clash 门禁的 `_default_root` 都是「当前工作目录 → 逐级向上 + `/clash`」，
  找到同时含 `profiles/` 与 `override/` 的目录为止 —— CWD 优先是刻意设计
  （CI 上基于 `__file__` 探测会算错目录，报"缺文件"而本地全过）。

#### 5.8 改完之后

```bash
python self-conf-skills/gates/clash/check_structure.py
python self-conf-skills/gates/check_min_pair.py
python self-conf-skills/gates/clash/check_script_sync.py          # 需 node
python self-conf-skills/run/clash/build_profiles.py --check
python self-conf-skills/run/clash/build_rules.py --check
python self-conf-skills/gates/verify_all.py                       # 全套闸门
python self-conf-skills/gates/clash/check_remote_urls.py          # 慢，联网，按需
```

最后在目标链路（尤其蜂窝）跑一次 leak test，并先写下"哪台设备、哪条链路、谁的 DNS" ——
混链路会让整轮结论作废（[故障排查 · FAQ](./pitfalls.md) §7.0）。
判据逐项见 `self-conf-skills/gates/clash/check_clash_dns.py` 头注与
[`gates.md`](./gates.md) §4–§8。

#### 5.9 两个 `check_secrets.py`，别只跑一个

| 脚本 | 扫描面 | 判据 |
|:-----|:-------|:-----|
| `self-conf-skills/gates/check_secrets.py`（跨内核，进闸门） | 全仓 `.conf` / `.yaml` / `.yml`，**跳过 `icons/`** | 禁串 `tange365.com` / `wangxinyu`；IPv4 白名单；`YAML_CRED_KEYS` 值必须占位 |
| `self-conf-skills/gates/clash/check_secrets.py`（mihomo 版） | 全仓 **`.js`** / `.yaml` / `.md` / `.conf` / `.list` / `.txt` / `.json`，跳过 `icons/` 与 `rules/` 的主机扫描 | 凭据字段非占位即报；IPv4 白名单；主机白名单；私钥头无条件报 |

两者互不可替代：mihomo 版能扫 **`.js`**（脚本里也有订阅 URL），跨内核版带禁串黑名单。
**改名合并会同时丢掉两边的判据。**

> ⚠️ **各内核的"常识"不同**：`198.18.0.1` 是 mihomo 的 `fake-ip-range`（`198.18.0.1/16`，
> RFC 6815 保留段），但 Surge / Egern 侧的 secrets 扫描不认识它 —— 整合时已加入 `DOC_NETS` 白名单。
> 这类分歧必须在整合层处理，不能指望某一侧的脚本天然认识另一侧的合法值。

#### 5.10 版本号与生成物

mihomo 静态 profile **由脚本生成**（`build_profiles.py`），也带 `#! version=` 头注，
与 Surge / Egern **同号**（三内核统一，见 §6.1）。

⚠️ **头注是「生成物」的例外 —— 必须手改 profile**（2026-10-08 更正）：
`clash/override/*.js` 里**没有**任何 `version=` 字符串（实测 `grep -c version= ` 为 0）；
`build_profiles.py` 的逻辑是**从磁盘上现有 profile 读第一行并保留**它
（源码注释：「保留 `#! version=` 头……若生成时丢掉，重生成一次就没了」）。
⇒ 版本真值在 **`clash/profiles/*.yaml` 的第一行**，所以：

| 要改 | 改哪 | 会不会被覆盖 |
|:--|:--|:--|
| mihomo 的**配置内容** | `clash/override/my_clash*.js` | 会 —— 必须改 JS |
| mihomo 的**版本号** | `clash/profiles/*.yaml` 第 1 行（**手改**） | **不会** —— 生成器保留它 |

> 本节此前写「改版本号要改脚本」，那是**错的**（脚本里没有这个字符串，
> 照做会无效）。2026-10-08 用「全新 AI 实测」发现并更正。

#### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| mihomo 逐键权威（语义 / 边界 / 取舍） | [`clash.md`](./profiles/clash.md) |
| 门禁命令与逐条判据 | [`gates.md`](./gates.md) |
| mihomo 加固清单（14 项判据 + 验收标准） | [加固清单 · mihomo 侧](./ops.md#mihomo-侧) |
| `no-resolve` 的三侧成对交付 | [分流与 no-resolve 必须成对交付](./dns.md) |
| 对侧内核的操作章 | 本篇「Surge 操作」章 ·「Egern 操作」章 |
| 换、加、删任何规则集之前 | [规则集与素材](./rulesets.md) |
| 出问题了 | [故障排查 · FAQ](./pitfalls.md) |
| 把本篇改动搬到另外两侧 | [跨内核移植](./rulesets.md) |

### 日常维护

面向"改这份配置的人"：改哪里、怎么升版、怎么同步、怎么记录。
仓库级红线（节点不提交真实值等）见根 [`SECURITY.md`](../../SECURITY.md)，本章不重复其条文，只讲操作动线。
⚠️ 本章版本号与 Release 各节（§6.1、§6.9）三内核通用；mihomo 侧的生成物特性见 §5.10。

#### 6.1 固定名规矩：先记住这个，再碰任何文件

- 顶层永远只有四个固定名 × 三内核（`.conf` / `.yaml` 各一对）：`routing` / `lazy` 的完整版与 `.min` 版。它们是永久订阅地址的落点，**不随版本改名**。
- "当前是哪一版"只写在文件头注 `#! version=…`。
- **升号规则**：配置键有变动 ⇒ 升号（改**三内核 × 两产品线 × 两形态 = 12 处**头注；
  数量现抓：`grep -rc "^#! version=" */profiles/ | ...`）；
  只改注释 / 文案 / 排版 ⇒ **不升号**（配置行为没变，号是**功能**的刻度）。
- **一天一版**：同一个自然日内同一产品线只升一次号；当天后续改动沿用同号。
  ⚠️ 此条**靠纪律**，仓内无归档可判，也没有专门的节奏判据（改革前有 V7 断言，
  那依赖已删除的归档快照；**现在没有机器守它**）。
- 因此：任何文档、脚本、README 里出现的"带版本号的订阅 URL"都是错的
  （Release 资产 URL 例外，那是钉版快照）。
- **仓内不保留历史版本** —— 要看历史用 `git log`，要下载历史版本去 Releases。

#### 6.2 改配置的标准动线

```
① 改带注释完整版（lazy.conf / routing.conf / 对应 .yaml）
② 生成 .min：      python self-conf-skills/run/make_min.py --family routing|lazy|all        # 默认只出差异计划
                   python self-conf-skills/run/make_min.py --family all --apply              # 确认后写盘
③ 核豁免行：       .min 由生成器重算正文、按锚点继承注释 —— 仍要肉眼确认 `# audit-waive:` 那几行在 min 版里读得到
④ 升版（仅当配置键有变动）：改 6 份 profile 头注的 `#! version=`（`.min` 由生成器重算继承）
   —— ⚠️ **一天一版**：当天该产品线已升过号就跳过本步、沿用同号（见 §6.1）
⑤ 收尾：`python self-conf-skills/gates/check_secrets.py && python self-conf-skills/gates/check_portability.py && python self-conf-skills/gates/check_min_pair.py && python self-conf-skills/gates/check_links.py .`（push 后 CI 会再跑一遍同组检查）
   ↑ 也可一键：`python self-conf-skills/gates/verify_all.py` —— 与 ci.yml 同源的全套闸门并行跑、出汇总表（含 DNS 审计与 releases 方案，比本行列的更全）
⑥ 发布 Release（push 之后）：`python self-conf-skills/run/release_publish.py --apply`
   —— 说明**从 commit subject 自动汇总**，无需手写条目表。详见 §6.9
```

> **注意**　`.min` 不手工编辑。手工同步迟早漂 —— `check_min_pair.py` 会拿完整版对拍 `.min`，漂了就红。

> **注意**　`audit-waive` 是有语义的注释，同文件内编号不重复。

> **建议**　`make_min.py` 默认只出计划不写盘，`--apply` 才动文件 —— 先读计划再落盘是刻意设计。

#### 6.3 DNS 段是"一份内容、四张脸"

`lazy` / `routing` × 完整版 / `.min` 共四份，DNS 相关键保持逐字一致（维护纪律，无自动判据）。

操作含义只有一条：改 DNS 段 = 一次改全套，闸门负责抓漏。想只给某一版加一条防泄露键，先问它为什么不是四条都要 —— 答案是"是"的才动手。

#### 6.4 换设备与双端一致

本机与另一台设备（或新克隆）之间核对配置一致性，跑：

```bash
python self-conf-skills/gates/check_portability.py
```

`check_portability.py` 逐条比对"两份拷贝是否等价"（规则清单现算，直接看脚本输出）。

换机常见坑：行尾（本仓 `.gitattributes` 统一 `text=auto eol=lf`，不要动任何人的 git config）、编码（脚本内部已钉 UTF-8 输出）、路径分隔符（拼接一律用 `/`）。

#### 6.6 精简配置（给自己瘦身）

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

删完必做：重跑分流覆盖审计与单侧回归（见 [验证与自检](./pitfalls.md)）。

#### 6.7 想加第三份配置

先问：这是新分工，还是老配置的另一种写法？后者一律否掉（那是版本分叉）。
确认是新分工后，走 [`surge.md`](./profiles/surge.md) 维护者一节 —— 一句话判据：能过全部检查的才算一份新配置（固定名、`.min` 对拍、DNS 段一致）。

#### 6.8 判据脚本的纪律

日常维护的正确姿势是：改配置与文档去适配判据，而不是改判据去适配配置。确实证明判据本身错了才动它，改动时写清"哪个反例会漏判、改后能抓住什么"。

**跑判据前先确认它的前置条件 —— 缺前置时的"红"不是缺陷，是噪声。** 两类最容易踩：

| 判据 | 前置条件 | 缺了会怎样 |
|:-----|:---------|:-----------|
| `check_releases` | 网络 + `GITHUB_TOKEN`（缺省回退 `gh auth token`） | 远端不可达 → 走 SKIP（退出码 3），非判负；`verify_all` 会以 ⚠️ 明示「未验证 ≠ 绿」。⚠️ 在 CI 里 SKIP 视为失败 |
| `release_publish` | **tag**（从「上一个 tag..HEAD」汇总说明） | 无 tag ⇒ 退化为「全部历史」；浅克隆仍可用 |

⚠️ **要点**：跑判据前先确认前置条件（完整克隆 / 网络 / token），否则会把「历史缺失」读成「配置有缺陷」。


> 📖 **新增/修改闸门前，先读 [`gates.md`](./gates.md)**：
> 三条注错铁律 + 怎么跑判别力矩阵 + 已验证清单。

#### 6.8.1 无 CI 兜底的工具（用了才知道，别指望 CI 替你验）

以下脚本**不在闸门里**，CI 对它们**没有任何自动化兜底** —— 绿不绿都跟它们无关。
它们必须**人工在本地跑**，且各有硬前置（真内核 / 真网络 / 真订阅）。

| 脚本 | 为什么进不了 CI | 怎么跑 |
|:-----|:----------------|:-------|
| `self-conf-skills/run/repo_state.py` | **一屏现状**（版本号 / 最新 Release / CI 结论一次输出）—— 是 AI **动线①的开工动作**，不是判据 ⇒ 不进闸门，但**每个任务开工都该先跑它**（此前全仓 0 处引用，未登记 ⇒ 长期孤儿，2026-10-08 补登记） |
| `self-conf-skills/gates/clash/check_real_kernel.py` | 需要**真实 mihomo 内核二进制 + 真实网络**。GitHub Actions 沙箱里两者都没有，塞进去只会得到一条**永远失败或永远跳过**的判据 —— 那比不跑更有害（会污染计数，正是 V3 那条修掉的老毛病） | 在有内核的机器上手动跑；它验的是「真机上到底通不通」，与静态判据互补 |

⚠️ 这条是**有意的设计，不是疏漏**。但「无兜底」这件事本身必须被看见 ——
所以写在这里，而不是让它默默躺在某个脚本头注里。
**新增任何不进闸门的脚本时，同步更新本节。**

#### 6.8.2 `self-conf-skills/run/` 的审计工具 —— 2026-10-08 已大部分进闸门

⚠️ **本节已被推翻重写**：原先判定这些工具「度量/诊断性质，不适合硬套判据」⇒
登记了事、靠人记得跑。**实测推翻了这判断** —— 它们都给出明确的过/不过（exit 0/1）。
现 **12** 项已进闸门（地区组判别力 ×3、分流覆盖 **×3**、规则集内容 ×2、
刷新周期 ×2、DNS 转发泄露、no-resolve 配对），不再需要人记得跑。
📌 计数订正：分流覆盖是 **×3**（Surge / Egern / mihomo），合计 **12 项**审计工具已进闸门（此前误写 ×2 / 11 项）。

⚠️ **又一次校准（同日）**：`profile_ruleset.py` 实测输出
「✅ 没有裸 IP 条目」+ 明确退出码 ⇒ 也可进闸门，已作为 **#17–19** 道接入（离线、快）。

至今**仍在闸门外的**（实测确认是纯读数 / 需联网，无过-不过语义）：
| 脚本 | 为什么留在外面 |
|:-----|:---------------|
| `weigh_ruleset.py` | 输出是条目列表与耗时读数，无判负语义 —— 排查「规则集太重」时手动跑 |
| `probe_doh.py` | 逐端点打印响应，无总结计数；且需联网 —— 排查 DoH 端点时手动跑 |
| `probe_dns_endpoints.py` | 有「失效端点：N / 总数」计数，**语义上可判负**，但需联网实测 10 个端点 ⇒ 网络抖动会造成假红。故**不进闸门**，改由 CI 周任务级检查（同 check_remote_urls 的处理） |
| `profile_ruleset.py` | ✅ **已进闸门**（#17–19）|

#### 6.8.3 `self-conf-skills/run/` 是工具区，不是判据区（原始说明，保留沿革）

`self-conf-skills/run/{surge,egern,clash}/` 下的**审计 / 探测 / 生成**脚本，大多**不进闸门**，
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
`audit_ruleset_noresolve` · `check_clash_dns` —— 这些**已进闸门**。

📌 **本仓的 CI 不受此影响**：`.github/workflows/ci.yml` 已固定 `fetch-depth: 0`（该处注释亦写明"shallow clone 会把所有日期退化成 push 当天"）。这条纪律管的是**本地与人工审查**场景。

🔍 **判据的通用姿势**：断言报红时，先问「它依赖的输入是否齐全」（历史深度 / 网络 / 凭据 / 前置文件），再问「是不是真的不过」。⚠️ 但**反向也成立**：不得因为"可能是前置问题"就把红当噪声放过 —— 判据与 CI 结论冲突时（如 CI 绿、本地红），先查**两边跑法差异**（历史深度、工作目录、环境变量），再下结论。上面的实证里，审查者一度把该冲突解释成"CI 只验当前状态、本地更全"，方向正好相反。

#### 6.9 Release 发布规矩

模型**极简**：**当前版本 → 一张 Release**，tag = `vYYYY-MM-DD`（发布日）。
不再从 git 历史重建历史 Release（那需要归档快照 + 手写历史表 + 日期口径文档，
改革前正是这三样东西各自长出了门禁）。

**命令**：

```bash
python self-conf-skills/run/repo_state.py                    # 看清现状（版本 / Release / CI）
python self-conf-skills/run/release_publish.py               # 计划模式：预览说明，一个字不发
python self-conf-skills/run/release_publish.py --apply       # 真发（需 GITHUB_TOKEN）
python self-conf-skills/gates/check_releases.py                  # 断言 R1–R5
```

**说明从 commit 自动汇总** —— 取「上一个 tag..HEAD」的 subject，过滤
`chore/ci/style/test/refactor` 与 merge，剥掉 `fix:` 这类前缀。因此：
- **不可能与代码漂移**（它就是 commit 本身）；
- 想让某条变更出现在 Release 里 ⇒ **把它写进 commit subject**（写清楚、写完整句子）。
- ⚠️ 刻意**只取 subject 不取正文**：本仓 commit 正文是给人看的详细记录（含 markdown
  片段与回溯说明），抽成要点会变成一堆半句。subject 才是被约定为「一句话概括」的字段。

**资产**：三内核 × 两产品线 × 完整版/`.min` = 最多 12 件，固定名**带内核前缀**
（`surge-lazy.conf` / `egern-routing.min.yaml` / `clash-lazy.yaml` …，Assets 面板自解释），
**一律不带版本号**。固定名全集单一真源 = `release_publish.ASSET_NAMES`
（`check_releases` 的 R2 白名单从它派生，不手抄第二份）。

**幂等**：同一天重复 `--apply` 不会重复建 —— 回写标题/正文并对账资产
（缺的补传、同名不同内容的删传、清单外的删除）。

**判据**（`check_releases.py`，CI 同跑）：
R1 tag 形状 `vYYYY-MM-DD` 且唯一 · R2 资产名 ∈ 固定名集合且无版本号样式 ·
R3 最新那张的资产 = 当前应发的 12 件（不多不少）· R4 正文含当前三内核版本号 ·
R5 仓库级 Latest 指向最新那张。

#### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 改 DNS 段之前先读泄露面 | [DNS 基础](./dns.md) |
| Surge 侧的操作动线 | 本篇「Surge 操作」章 |
| Egern 侧的操作动线 | 本篇「Egern 操作」章 |
| 换、加、删任何规则集之前 | [规则集与素材](./rulesets.md) |
| 出问题了 | [故障排查 · FAQ](./pitfalls.md) |
| 把本篇改动同步到对侧内核 | [跨内核移植](./rulesets.md) |

---

## 加固清单

> 由原两侧 `docs/03` 合并，整合后增补 mihomo 侧。清单按内核分节，逐项对应各侧配置键。

### Surge 侧

> 📛 本文件 2026-09-25 前名为 `03-加固清单-12项.md`：**名字停在 12，而清单早已长到 14**
> （第 13/14 项是后加的，正文自己都引用了它们）—— 文件名里的数字此前**没有任何判据管**，

> 用法：从上到下逐条对照你的 profile。**每一项都给出判据与严重度**。
> 全部自动化：`python self-conf-skills/gates/surge/check_surge_dns.py Profile.conf` 覆盖第 1–12 项；
> [`audit_ruleset_content.py`](../run/surge/audit_ruleset_content.py) 覆盖第 13 项；[`audit_routing_coverage.py`](../run/surge/audit_routing_coverage.py) 覆盖第 14 项。

#### 清单

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `encrypted-dns-server` 的端点是否 **IP 字面量** | 出现主机名端点 → 该主机名**必被明文解析一次**才能建连 | **高**（境外域名端点）；低（国内域名端点） |
| 2 | `dns-server` 是否显式、是否含 `system` | 写 `system` = 把引导交给运营商 DHCP；**绝不允许**。另要求 ≥2 个**不同机构**的国内解析器 IP | **高**（缺失或含 system） |
| 3 | `hijack-dns` 是否接管硬编码解析器 | 缺失 → 忽略 Surge DNS 的设备（HomePod / Apple TV / 智能音箱）明文 `:53` 裸奔 | **高**（缺失时） |
| 4 | `encrypted-dns-follow-outbound-mode` | 必须 `false`。`true` 时 DoH 连接遵循代理规则 ⇒ 解析代理本身要代理 ⇒ 启动期成环 / 回落明文 | **高**（为 true 时） |
| 5 | `use-local-host-item-for-proxy` | 保持 `false`。`true` 会把本地 DNS 结果变成硬性代理目标，破坏远端解析 | **高**（为 true 时） |
| 6 | 延迟测试端点（`internet-test-url` / `proxy-test-url` / `proxy-test-udp`） | **性能探针，非泄露通道**。官方 KB：走代理时解析在代理服务器进行。选址是性能取向：连通性检测宜国内，`smart` 打分宜境外（含国际段）。仅作提示 | 低 |
| 7 | 策略组引用的成员是否都存在 | 引用不存在的节点名 → Surge **拒绝加载整份配置** | **高** |
| 8 | ⭐ 规则引用的策略是否可解析 | ⚠️ 策略字段位置随类型而变：`DOMAIN-SUFFIX,x,POLICY` 与 `GEOIP,CN,DIRECT` 都在 index 2；只有 `FINAL,POLICY` 在 index 1。写错方向会报出**假 HIGH**（把 `CN` 当策略名） | **高** |
| 9 | ⭐ 规则顺序 | 白名单 → REJECT → 域名类直连 → IP 类 → FINAL。REJECT 排在 `direct.txt` / `GEOIP,CN` 之后 = 白加 | **高** |
| 10 | ⭐ 广告拦截的策略是否是**字面量** REJECT 族 | 写成策略组 → Surge 以「使用了非 REJECT 策略」拒绝加载（组在运行时可能解析成 DIRECT）。另建议带 `extended-matching` | **高** |
| 11 | `always-real-ip` 的主机名是否被兜底之前的域名规则接住 | 没接住 → 落兜底；若兜底依赖代理，启动期那次解析会回退明文 | 中（有远程规则集时降为低） |
| 12 | IP 类规则（`GEOIP` / `IP-CIDR` / `IP-ASN`）是否都带 `no-resolve` | 不带 → 规则匹配时会**额外触发一次本地解析**。⚠️ **定性**：走代理策略时解析本就在代理服务器进行（官方 KB），**这不是泄露补丁**；加它是去掉一次冗余解析 + 把约束固化 | 中 |
| 13 | ⭐⭐ **远程规则集里有没有"不带 `no-resolve` 的 IP 类条目"** | 缺陷藏在**别人仓库的 `.list`** 里，profile 写得再干净也看不见。一条启用的 `RULE-SET` 里只要有**一条**这种条目，**每个走到该规则的域名都会被强制本地解析一次**。必须逐个下载 + 数 | **高** |
| 14 | ⭐⭐ **国内域名有没有"域名类"规则兜底** | 给 IP 规则补 `no-resolve` 会**同时**关掉"靠解析判 IP 归属"这条直连路径。判据是**数域名条目**（不是看规则集名字）：`ChinaMax.list` 只有 64 条域名 / 12472 条 IP，名字叫 ChinaMax 但 99.5% 是 IP | **高** |

#### `no-resolve` 的位置：两个层级

| 层级 | 写法 | 作用范围 |
|---|---|---|
| **profile 规则级** | `GEOIP,CN,DIRECT,no-resolve` | 只影响这一条规则 |
| **规则集条目级** | `.list` 里的 `IP-CIDR,x/y,no-resolve` | **第三方 `.list` 走的就是这一层** —— 也是第 13 项缺陷最常藏身的地方，profile 管不到它 |

> ⚠️ 注意：`no-resolve` 写在 `RULE-SET` 那条 profile 规则上（如 `RULE-SET,foo.list,DIRECT,no-resolve`）
> 是**给规则集里所有条目加的默认值**，Surge 支持这个写法。但如果规则集里**条目自带** `no-resolve`
> 缺失，仅靠 profile 侧的写法并不能保证生效 —— 所以要**下载下来数**（第 13 项）。

#### 验收标准（六条同时满足才算完）

1. `encrypted-dns-server` 里**没有**主机名端点（全部 IP 字面量或已知的 CDN 端点，后者需显式豁免）
2. `dns-server` 显式列出 ≥2 个不同机构的国内公共解析器 IP，**且不含 `system`**
3. `hijack-dns` 覆盖已知的硬编码解析器（建议直接 `*`）
4. 所有 IP 类规则（`GEOIP` / `IP-CIDR` / `IP-ASN`）**都带 `no-resolve`**
5. ⭐ **所有被启用的远程规则集，其 IP 类条目都带 `no-resolve`**
6. ⭐⭐ **分流仍然正确：国内域名仍判给 `DIRECT`**（17 个国内探针必须全绿，且**必须包含非 `.cn` 的域名**）
   **这一条是第 12 项的代价，必须成对交付** —— 给 IP 规则补 `no-resolve` 会同时关掉
   "靠解析判 IP 归属"那条直连路径。所以补 `no_resolve` 的同一时刻，必须确认
   `FINAL` 之前有一份**含大量域名条目**的国内规则集。

> ⚠️ **只检查 `.cn` 后缀会假通过** —— 那靠的是 `DOMAIN-SUFFIX,cn` 这条兜底，
> 而不是真的接住了国内域名。[`audit_routing_coverage.py`](../run/surge/audit_routing_coverage.py) 的国内探针刻意混入了
> `qq.com` / `taobao.com` / `miui.com` / `bilibili.com` 这类非 `.cn` 域名。

### Egern 侧

> 用法：从上到下逐条对照你的 profile。**每一项都给出判据与严重度**，"⭐"标出本清单里最容易被跳过、也最容易只看字面就漏掉机理的关键项。
> 全部自动化：`python self-conf-skills/gates/egern/check_egern_dns.py Profile.yaml` 覆盖第 1–15 项；
> [`audit_ruleset_noresolve.py`](../run/egern/audit_ruleset_noresolve.py) 覆盖第 16 项；[`audit_routing_coverage.py`](../run/egern/audit_routing_coverage.py) 覆盖第 17 项；
> [`audit_dns_forward.py`](../run/egern/audit_dns_forward.py) 覆盖第 18 项。

#### 清单

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `upstreams` / `proxy_nameservers` 的加密 DNS 端点是否为 **IP 字面量**（或已钉 `hosts`） | 出现主机名端点 → **必定被 `bootstrap` 明文解析一次** | **高**（境外域名端点）；低（国内域名端点） |
| 2 | ⭐ `proxies[].server` 是**域名**的节点，**代理 DNS 那条路**有没有落在国内加密组上 | 没有 → 代理 DNS 强制直连、问不到境外解析器 → 回退明文 `bootstrap`（国内解析器）→ **节点域名明文暴露**。判据看 `proxy_nameservers` **或** `forward` 兜底（二者任一即可，见 2b）；根治手段是把节点 `server` 改写成 IP 字面量。⚠️ **"在 `forward` 里为节点域名加一条 `domain_suffix`"是错的查法/修法** —— 设了 `proxy_nameservers` 后代理 DNS **跳过** `forward`，该规则永不命中（f7 起即为死代码） | **高** |
| 2b | `proxy_nameservers` 是否存在 | 它是**硬覆盖**：一设就跳过 `forward`、强制直连。**两种写法都成立，但必须二选一、不要叠加**：① **不设置** —— 代理 DNS 与默认 DNS 共用 `forward`，靠兜底接住节点域名；② **设置** —— 把"未命中回退 `bootstrap`"这条分支从结构上消掉，且强制直连 ⇒ 不依赖代理就绪。**本模板采用 ②，理由即此。** ⚠️ 设置后 `forward` 对节点域名失效 | 中（设了要说明理由 —— 本模板已在 `dns` 段注释里说明） |
| 3 | ⭐ DNS 端点是否有**显式路由** | `geoip` 加了 `no_resolve` 就**不再匹配域名**；主机名形式的端点会落到 `default` → 国内端点被绕到境外出口 / 境外端点直连被阻断。**国内端点必须显式 → `DIRECT`，境外端点必须显式 → `Proxy`** | **高** |
| 4 | ⭐ `forward` 里是否存在「捕获一切」的兜底，**且该兜底组「直连可达」** | 兜底存在的意义只有一个：让未命中的域名不回退 `bootstrap` 明文。**判据是「这组在代理没起来时能不能工作」** —— 组内端点必须全是 IP 字面量，**且满足下面两条之一**：<br>**判据 A** 至少一个端点在 `rules` 里被判给 `DIRECT`；<br>**判据 B** 至少一个是已知的**国内**公共解析器 IP（`223.5.5.5` / `223.6.6.6` / `119.29.29.29` / `1.12.12.12` / `120.53.53.53` …）—— 其归属与服务商是公开事实，在国内任何链路上都直连可达，与"在 `rules` 里判给 `DIRECT`"等价，且不需要在配置里写装饰性规则。<br>⚠️ 判据 B 是 f10 引入的：模板删掉那 15 条 DNS 端点路由规则后，正是靠它通过验收。脚本 [`check_egern_dns.py`](../gates/egern/check_egern_dns.py) 的 `group_reach` 同时实现了 A 与 B。<br>只判给 `Proxy` 的组 = 依赖代理 = 启动期会掉进明文。**写法要认全**：`domain_wildcard: '*'` **和** `domain_regex: '.'`（官方 PCRE2 find 式）都算兜底 —— 推荐**两条都写** | **高** |
| 5 | `geoip` / `ip_cidr` / `ip_cidr6` / `asn` 是否带 `no_resolve` | 官方：`no_resolve` **仅适用这四类**；不加则规则会**触发解析** | **高** |
| 6 | ⭐ 规则引用的**策略名能否解析** | `policy` 嵌在类型字典里（`{domain: {match, policy}}`）—— 要读 `r[type]['policy']`。抓 `负载均衡` 这类笔误 | **高** |
| 7 | 硬编码 DoH IP（`8.8.8.8` / `1.1.1.1` / `9.9.9.9` / OpenDNS…）是否有**启用**的规则 → 代理 | `hijack_dns` 只覆盖 **:53**，App 自带 DoH on **:443** 会绕过 | 中 |
| 8 | ⭐ `rule_set.match` 是否为 **URL 或文件路径** | 写成 `AI` / `抓取` / `Apple push` 这种名字 → 无法加载，等同**死规则** | 中 |
| 9 | `block_ips` | 未设 → `0.0.0.0` 这类空路由式污染应答照单全收 | 低 |
| 10 | `real_ip_domains` | 为空 → 走不到隧道的流量（APNs / 内网）也拿 Fake IP，推送/内网会异常 | 低 |
| 11 | `ipv6` | `true` → AAAA 可绕过 IPv4 侧封堵 | 中 |
| 12 | `hijack_dns` 是否覆盖全部 | 官方示例值即 `['*']`（接管 `:53` 并返回 Fake IP） | **高**（缺失时） |
| 13 | `public_ip_lookup_url` | **不配置**才不发 ECS（不把公网 IP 交给 DNS 服务器） | 配了才是问题 |
| 14 | `skip_tls_verify` | 应为未设置 / `false` | 低 |
| 15 | ⭐ **profile 自身必需解析的名字**（两个 latency test URL 的域名 + 策略组 `icon` 的域名）是否被"兜底之前"的 `forward` 规则接住 | 没接住 → 落兜底；一旦这次解析发生在直连侧，境外组不可达 → 回退明文 → 再落 `system` = 运营商。**延迟测试端点 = 高**（每轮测速都触发，持续泄露）；**图标 = 低**（失败只是图标不显示；硬钉到国内解析器反而可能拿到污染/`0.0.0.0` 应答，收益 < 风险，可故意不动） | **高** |
| 16 | ⭐⭐ **远程规则集里有没有"不带 `no-resolve` 的 IP 类条目"** | 缺陷藏在**别人仓库的 `.list`** 里，profile 写得再干净也看不见。官方：`no_resolve` 为 `true` 才"不触发 DNS 解析" ⇒ **不带就触发**。一条启用的 `rule_set` 规则里只要有**一条**这种条目，**每个走到该规则的域名都会被强制本地解析一次**。实测 `Apple_All.list` 有 13 条。**必须逐个下载 + 数** | **高** |
| 17 | ⭐⭐ **国内域名有没有"域名类"规则兜底**（不是"有没有一条叫 China 的规则"） | 给 IP 规则补 `no_resolve` 会**同时**关掉"靠解析判 IP 归属"这条直连路径。若没有一个**真正的域名规则集**接住国内域名，它们会整片落到 `default → Final → 代理`。判据：把规则集**下载下来数域名条目**，再用 [`audit_routing_coverage.py`](../run/egern/audit_routing_coverage.py) 拿真实域名走一遍 | **高** |
| 18 | ⭐ `forward` 的 **`value` 是否单值**、以及**订阅耦合度**（`forward` 里有没有把节点域名写死） | `value` 单值时，**规则顺序与域名清单都不影响结果** ⇒ 可塌缩为纯兜底、与订阅解耦。判据：`value` 集合只有 1 个元素 + `proxies[].server` 的域名在 `forward` 里出现 0 次。用 [`audit_dns_forward.py`](../run/egern/audit_dns_forward.py)` --drill` 拿**合成的"未来订阅"域名**演练验证 | 中 |

#### `no_resolve` 的三个层级

| 层级 | 写法 | 作用范围 |
|---|---|---|
| **规则级** | `rules:` 里的 `- geoip: {match: CN, policy: DIRECT, no_resolve: true}` | 官方明说**只适用 `geoip`/`ip_cidr`/`ip_cidr6`/`asn` 四类**；写在 `rule_set` 规则上**不生效** |
| **规则集文件顶层** | Egern 原生 YAML 规则集里的 `no_resolve: true` | 影响该文件内所有 IP 相关规则 |
| **规则集条目级** | Surge `.list` 里的 `IP-CIDR,x/y,no-resolve` | **第三方 `.list` 走的就是这一层** —— 也是第 16 项缺陷最常藏身的地方，profile 管不到它 |

#### 验收标准（六条同时满足才算完）

1. `upstreams` 与 `proxy_nameservers` 里**没有任何主机名端点**（全部 IP 字面量，或已钉 `hosts`）
   → 消灭 `bootstrap` 用途①。
2. `forward` 有兜底，**且兜底组直连可达**（端点全为 IP 字面量 + 满足**判据 A 或判据 B**，见清单第 4 项）
   → 消灭 `bootstrap` 用途②，且不依赖"代理已就绪"。
3. 所有 IP 类规则（`geoip` / `ip_cidr` / `ip_cidr6` / `asn`）**都带 `no_resolve`**。
4. ⭐ **所有被启用的 `rule_set` / `proxy_rule_set`，其规则集文件里的 IP 类条目都带 `no-resolve`**。
5. `bootstrap` 显式列 2 个以上国内公共 DNS 的 IP，**且不含 `system`**
   → 把"全失败 → 系统 DNS"这一最坏分支的概率压到最低。
   ⚠️ **前 4 条是"让它不被用到"；第 5 条只是把最坏分支的概率压小。** `bootstrap` 是明文 UDP:53，在运营商线路上无论指向哪个 IP 都可能被接管 —— **它唯一安全的形态是"永远不被触发"。**
6. ⭐⭐ **分流仍然正确：国内域名仍判给 `DIRECT`**（15 个国内探针必须全绿）。
   **这一条是第 3 条的代价，必须成对交付** —— 给 IP 规则补 `no_resolve` 会同时关掉"靠解析判 IP 归属"那条直连路径。
   所以补 `no_resolve` 的同一时刻，必须确认 `default` 之前有一份**含大量域名条目**的国内规则集。
   **"DNS 审计全绿"不等于"配置可用"** —— f7 时两个审计脚本双双通过，分流却整片是坏的。

#### 五个脚本的定位与分工

| 脚本 | 看哪一层 | 关键点 |
|---|---|---|
| `check_egern_dns.py` | **profile 文本** | 能验证的只有"你自己编码进去的假设" |
| `audit_ruleset_noresolve.py` | **被引用的规则集文件** | 缺陷不在 profile 里 —— 不下载就永远看不见 |
| `audit_routing_coverage.py` | **域名 → 命中规则 → 策略** | 验证"防泄露"没把"分流"一起干掉 |
| `audit_dns_forward.py` | **`forward` 的结构**（单值性 / 订阅耦合 / 换订阅演练） | 验证"换订阅后还能不能防泄露" |
| `audit_region_filters.py` | **地区组 filter 的「两份拷贝」** | 负向断言（"排除以上全部"）必须逐字重抄关键词，Egern 不支持 `filter` 引用 ⇒ 只能靠脚本守同步 |

> ⭐ **本项目最贵的一条工程教训：审计通过 ≠ 配置可用。**
> 这条线上连续出现过 5 次"脚本 0 high、用户实测仍有问题"：有的是靠加配置压指标、有的是审计维度缺失（只看 profile、没看它引用的规则集）、有的是两个脚本双双全绿而分流整片是坏的。
> **固化规则：任何一次「审计绿了但实测有问题」，都必须假设"存在审计器看不见的维度"，并把这个维度补成一个可复跑的脚本 —— 而不是重跑同一个脚本。**

### mihomo 侧

> 用法：从上到下逐条对照你的 profile。**14 项判据与 `check_clash_dns.py` 一一对应**（编号即脚本里的判据号）；
> 另有 `check_structure.py` 8 项结构判据与之互补（见文末的分工表）。
> 逐键语义与边界的权威是 [`clash.md`](./profiles/clash.md)，
> 本章只列清单与判据，不重复逐键解释。

**自动化**：

```bash
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/routing.yaml
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/lazy.yaml
python self-conf-skills/gates/clash/check_clash_dns.py out.yaml --override   # 覆写脚本输出形态：不要求 tun 段
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/routing.yaml --strict   # medium 也算失败

python self-conf-skills/gates/clash/check_structure.py
```

退出码：`0` = 无 high（`--strict` 下还要求无 medium）· `1` = 有 high · `2` = 用法错误 / 读不到 / YAML 坏 / 缺 pyyaml。
⚠️ `2` 与 `1` 必须分开：环境炸掉**绝不能被读成一次成功的判负**（Windows cp936 下 `print` 一个中文就可能让进程以 1 退出 —— 而 1 恰是"判负"的码）。

#### 清单（14 项，与 `check_clash_dns.py` 判据号一致）

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `dns` 段存在且 `enable: true` | 没有 `dns` 段 ⇒ 全部查询走**系统 DNS**（运营商 DHCP 下发的那台）；`enable` 不为 true ⇒ DNS 劫持与 fake-ip 全部失效 | **高** |
| 2 | ⭐ `default-nameserver` 是否全为 **IP 字面量** | 官方硬性要求。这一层**唯一**用途是解析其余 DNS 端点**自己的域名**（引导），它必然是明文 UDP:53（不能再依赖加密解析器，否则成环）⇒ 它自己写主机名 = "解析解析器"又要一次明文解析 = **鸡生蛋**。带 scheme 的写法（如 `https://223.5.5.5/dns-query`）判 MEDIUM（引导层成环）。当前两版均为 `223.5.5.5` / `119.29.29.29` 纯 IP | **高**（主机名）／中（带 scheme） |
| 3 | ⭐ `nameserver` / `fallback` 端点必须是「**IP 字面量** **且** **加密 scheme**」的**合取** | 两条独立的坏法对应两个面：**写主机名** ⇒ 冷启动必然用 `default-nameserver` 明文解析一次（面①）；**写裸 IP**（如 `nameserver: 8.8.8.8`）⇒ **每一笔查询都是明文 UDP:53**（面②，比面①严重得多 —— 带的是业务域名）。⚠️ 只判"是不是 IP"会把最坏写法判成通过 | **高** |
| 4 | ⭐ `proxy-server-nameserver` 必须存在（节点域名解析的鸡蛋问题） | 缺它 ⇒ 代理节点自己的域名走主路径（本仓是境外 DoH）⇒ "要先有代理才能解析出节点地址"，失败时退回明文 / 系统 DNS，**节点域名明文暴露**（与 Egern 侧 `proxy_nameservers` 同一条判据）。缺 `direct-nameserver` ⇒ `DIRECT` 出站的域名也去问境外主解析器（答案不准 + 多一次境外查询，非明文 ⇒ MEDIUM）。当前分流版两个端点写的是**主机名**（`doh.18bit.cn` / `dns.alidns.com`）⇒ 4 条 LOW：国内端点、信号弱，是取舍不是缺陷 | **高**（缺前者）／中（缺后者）／低（端点用主机名） |
| 5 | `enhanced-mode: fake-ip` 且 `fake-ip-range` 落在 **RFC 6815 保留段** | `redir-host` / 未设置 ⇒ 每个域名都真实解析一次（本地留答案）；`fake-ip-range` 不在 `198.18.0.0/15` ⇒ 拿假 IP 去连真实网络。当前 `198.18.0.1/16` ✅ | **高**（段不对）／中（模式不对） |
| 6 | ⭐ IPv6 **两处**都要显式关闭：顶层 `ipv6` **与** `dns.ipv6` | 判据用 `is not False` ⇒ **键缺失也算不过**。`dns.ipv6: true` ⇒ 应用拿到真实 AAAA；顶层 `ipv6: false` ⇒ IPv6 流量不被 TUN 接管；两者叠加 = 双栈站点直连出去、绕过代理。⚠️ 只关一处比两处都开更隐蔽 | **高** |
| 7 | ⭐ `tun` 是否接管 `:53`（旁路设备面③）+ `strict-route` | ⭐ 判据不是"列了几条"，而是**是否覆盖 `:53` 的整个地址空间** —— 地址空间无限，逐个列举永远列不全（Surge 侧第 3 项踩过同一个坑：按条数判负是错的）。只有 `any:53` / `0.0.0.0:53` 才叫收口。另要求 `enable` / `auto-route` / `strict-route` 三键。<br>⚠️ **形态差异**：覆写脚本（`override/*.js`）的输出**不该有** `tun`（客户端自己管 TUN）⇒ `--override` 下本项整体跳过；当前也未接管 TCP:53（不写协议前缀默认 `udp://`，LOW，是已知取舍） | **高** |
| 8 | ⭐⭐ **DNS 层广告拦截的两个必要条件**（缺任一 ⇒ 静默失效、且不报错） | ① `nameserver-policy` 里 `rule-set:<广告集>: rcode://success`；② **同一个广告集在 `fake-ip-filter` 里再列一遍** —— 否则 `withFakeIP` 中间件对 A / AAAA **直接返回假 IP**，请求永远走不到 ①。另：两处广告集**必须一致**，且都**不得引用未定义**的 `rule-set:`（死引用 ⇒ 静默消失）。当前两版均为 `AWAvenue-Ads` + `Jinx-Ads`，两处一致 ✅ | **高** |
| 9 | `nameserver-policy` 的**广告项必须排在 `cn` / `private` 之前** | YAML mapping 在 Python 3.7+ 保持插入顺序，而这个顺序**就是 mihomo 的匹配顺序**：先命中 `rule-set:cn` ⇒ 拿国内答案，永远走不到后面的 `rcode://success` | **高** |
| 10 | ⭐⭐ IP 类规则必须带 `no-resolve`（面④），域名类不该写 | ⭐ 判"是不是 IP 类规则"的**第一依据是 provider 的 `behavior`**，不是名字前缀：`ipcidr` ⇒ 不带会为判定而强制解析；`domain` ⇒ 写了无意义；`classical` ⇒ 内容混合、**无法静态判定**（单独归组提示）。只有 provider 未声明 `behavior` 时才退回 `geoip-` 名字前缀兜底。<br>⚠️ **双刃与另两侧同**：给 IP 规则补 `no-resolve` 会同时关掉"靠解析判 IP 归属"那条直连路径 ⇒ 必须与域名补偿**成对交付**（见 [no-resolve-pairing.md](./dns.md)）。当前分流版 4 条 / 懒人版 2 条全部带 ✅ | **高**（IP 类缺）／低（域名类写了） |
| 11 | ⭐ **零 dat 依赖** | 顶层出现 `geox-url` / `geo-auto-update` / `geo-update-interval` ⇒ mihomo 会去下载并加载 `GeoSite.dat` / `GeoIP.dat`；规则写原生 `GEOSITE,` / `GEOIP,` ⇒ 直接查那两个库；`nameserver-policy` 键用 `geosite:` 同理；provider 引 `.dat` 文件同样判负。<br>⚠️ **这不排斥 `.mrs`**：`geoip-private` / `geoip-cn` 等是 MetaCubeX 的**独立远程集文件**（`format: mrs`），与 dat 数据库无关 —— 正是本仓想要的形态。判据只拦 dat，不拦 mrs（注入测试专门验过不误伤） | **高** |
| 12 | `rule-provider` 形态（**不做网络探测**） | 既无 `url` 也无 `path` ⇒ 永远加载不出来 ⇒ 引用它的规则**静默变成空集**（死规则），门禁看不出来。一个 provider 都没有 ⇒ MEDIUM。可达性归 `check_remote_urls.py` | **高**（缺 url+path）／中（零 provider） |
| 13 | ⭐ 规则引用的名字必须**能解析**（provider / 策略组） | 引用不存在的东西**不会让 mihomo 拒绝启动** —— 它只是静默不生效。对防泄露而言这最危险：那正是收口装置所在的位置（广告集 / 国内集 / 兜底）。策略名笔误（如 `负载均衡`）同判 | **高** |
| 14 | 其余 DNS 开关（提示性） | `respect-rules` 未开 ⇒ DNS 查询自己不按路由规则走；`use-system-hosts: true` ⇒ 读本机 hosts；`prefer-h3: true` ⇒ 优先 HTTP/3；`dns.listen` 设了 ⇒ 内核对外开明文 `:53` 端口（脚本**不设**它，早期写死 `0.0.0.0:7874` 会与客户端 DNS 端口冲突） | 低 |

#### `no_resolve` 的位置：两个层级

| 层级 | 写法 | 作用范围 |
|---|---|---|
| **规则级** | `RULE-SET,geoip-cn,DIRECT,no-resolve` | 只影响这一条规则。mihomo 的 `RULE-SET` 确实解析该参数并传给 `NewRuleSet`（源码：`rules/parser.go` 的 `case "RULE-SET": isSrc, noResolve := RC.ParseParams(params)`） |
| **provider 的 `behavior`** | `behavior: ipcidr` | **判定"这条规则是不是 IP 类"的第一依据** —— 比名字前缀可靠，也是 `check_clash_dns.py` 判据 10 的落点 |

> ⚠️ 与 Egern 相反的一点是：**写在 `rule-set` 规则对象上（Egern 的 `no_resolve: true`）不生效**，
> mihomo 的 `no-resolve` 写在规则行尾。三侧落点对照见 [no-resolve-pairing.md](./dns.md)。

#### 验收标准（六条同时满足才算完）

1. `dns` 段存在且 `enable: true`；`default-nameserver` **全部 IP 字面量**（不带 scheme）。
2. `nameserver`（及 `fallback`，若开启）端点全部「**IP 字面量 + 加密 scheme`**」的合取 ——
   消灭面①（引导解析）与面②（明文回退链）。
3. `proxy-server-nameserver` **存在**（节点域名有独立出口，不依赖代理）—— 消灭面③ 的鸡蛋问题；
   另 `direct-nameserver` 存在 ⇒ 直连域名不碰境外解析器。
4. ~~`tun` 收口~~ ⇒ **2026-10-08 起本仓不带 `tun` 段**（见下条与代码）；TUN 由客户端接管，配置不写。
   —— 消灭面③（旁路设备）。⚠️ 覆写脚本形态下这一条换成"客户端自己管 TUN"，用 `--override` 审。
5. 顶层 `ipv6: false` **与** `dns.ipv6: false` —— 两处，少一处都不算完（面③′）。
6. ⭐⭐ **分流仍然正确：国内域名仍判给 `DIRECT`** —— `RULE-SET,cn,DIRECT` 必须在 `MATCH,Proxy` **之前**，
   且它必须是 `behavior: domain` 的真正域名集。
   **这一条是第 10 项的代价，必须成对交付**：给 IP 规则补 `no-resolve` 会同时关掉
   "靠解析判 IP 归属"那条直连路径。
   ✅ **mihomo 侧已有专用分流覆盖审计脚本** `self-conf-skills/run/clash/audit_routing_coverage.py`（2026-10-07 补出，已进闸门 #9）—— 前 5 条自动化后，这一条**先跑闸门 #9**；但离线档按规则集名+实际策略校验，**不能证明真实域名命中** ⇒ 仍需实测兜底，别把闸门绿当充分条件。（此处曾长期写「没有」，与实际相反。）
   且要用**国内非 `.cn` 域名**验证（只测 `.cn` 会被后缀兜底救活，假通过）。

#### 两个脚本的定位与分工

| 脚本 | 看哪一层 | 关键点 |
|---|---|---|
| `check_clash_dns.py`（`self-conf-skills/run/clash/`） | **profile 文本 + provider 语义** | 14 项防泄露判据，分级（🔴/🟠/🟡/✅）。判据是**实测推导**而非字符串匹配；**不做网络探测**；豁免写在**被审对象**里（`# audit-waive: <判据号> <理由>`） |
| `check_structure.py`（`self-conf-skills/gates/clash/`） | **结构 / 引用 / 形态** | 8 项：① 无悬空引用 ② 规则指向的 provider 与策略组存在 ③ 广告双条件 + 广告项排在 `cn` 之前 ④ **禁止** `tun` 段（4c4bc56 起反转；原为「要求四键」，文档曾长期说反）⑤ `geoip-*` 规则带 `no-resolve` ⑥ `nameserver` 必须 IP 字面量 ⑦ 零 dat 依赖 ⑧ IPv6 两处显式关闭 |
| `check_min_pair.py`（`self-conf-skills/gates/clash/`） | **`.min` ↔ 完整版** | 去掉注释后配置本体必须逐字相同 |
| `check_script_sync.py`（`self-conf-skills/gates/clash/`） | **脚本输出 ↔ 静态 profile** | 同一套配置的两种交付形态必须逐位一致（需 node）；Smart 三档是**已知差异**，打印提醒不判负 |
| `build_profiles.py --check`（`self-conf-skills/run/clash/`） | **生成物新鲜度** | 改了 `override/*.js` 没重生成 ⇒ 判负；内含自检（防"纵向堆叠 7 份"那类畸形） |
| `build_rules.py --check`（`self-conf-skills/run/clash/`） | **`rules/*.yaml` ↔ `.list` 真源** | 生成物过期即判负；❌ 不手工编辑 `rules/*.yaml` |
| `check_remote_urls.py`（`self-conf-skills/gates/clash/`） | **远程集可达性**（联网，慢） | 死链不是报错，是**静默降级** —— provider 拉不到就变空集，广告全进兜底出口而配置看着跑得挺好 |

> ⭐ **审计通过 ≠ 配置可用**（三侧共通的母题）。mihomo 侧**已有**分流覆盖审计脚本（闸门 #9），但审计通过仍不等于真机可用 —— 这句母题对三侧都成立。
> （三内核均有 `audit_routing_coverage.py`，闸门 #7/#8/#9）—— 第 6 条验收标准**先跑它们**，但注意离线档按规则集名推演、不读实际策略，**仍需实测兜底**，别把闸门绿当充分条件。
> 这正是 `no-resolve-pairing.md` 要跨内核保留下来的教训：**不得因为两道静态门禁全绿就跳过它。**

#### 已知取舍（LOW 不是缺陷）

当前基线（2026-10-07 实测）：分流版 **0 high / 0 medium / 7 LOW / 21 OK**，懒人版 **0 high / 0 medium / 2 LOW / 21 OK**。
那些 LOW 都是刻意留下的取舍，改之前先问"我真的需要吗"：

| LOW | 来源 | 为什么留着 |
|:----|:-----|:-----------|
| `proxy-server-nameserver` / `direct-nameserver` 端点是主机名（`doh.18bit.cn` / `dns.alidns.com`） | 判据 4 | 国内端点：只带出"本机在用哪个 DoH"，信号弱；改成 IP 字面量需自建端点 |
| `dns-hijack` 未接管 TCP:53 | 判据 7 | 不写协议前缀时默认 `udp://`；明文 TCP 查询在现代客户端里罕见（要覆盖得写 `tcp://any:53`） |
| 5 个 `classical` 规则集内容无法静态判定 | 判据 10 | 面⑤：远程集里的裸 IP 条目**不在本文件里**，本地静态门禁看不见，必须拉下来数；本仓自托管的 `rules/*.list` 实测 **0 条 IP 条目** |
| `fallback-filter.geoip: true` | 判据 3 | 两端都是 DoH 时不是泄露，是**双倍延迟**；懒人版干脆不开 `fallback` 就是同一个判断 |

---

下一步：[分流与 no-resolve 必须成对交付](./dns.md)。

---

## 发版规矩

> 本仓的发版模型：一个更新日 = 一个 Release，tag = `vYYYY-MM-DD`。

⚠️ 本文是**规矩**，不是历史。历史请看 git 记录（本仓不在仓内保留 CHANGELOG）。

### 1 · 版本号放哪

版本号写在 profile 的**头注第一行**，格式 `#! version=<产品线>_v<X.Y.Z>`：

```
#! version=routing_v1.0.0
```

| 内核 | 产品线 | 头注 |
|:--|:--|:--|
| Surge | 分流版 / 懒人版 | `#! version=routing_vX.Y.Z` / `#! version=lazy_vX.Y.Z` |
| Egern | 分流版 / 懒人版 | 同上（与 Surge 同号，强制对齐） |
| mihomo | 分流版 / 懒人版 | `#! version=routing_vX.Y.Z` / `#! version=lazy_vX.Y.Z` |

- Surge 与 Egern 同一产品线**必须同号**（跨内核对拍的前提，由 `check_min_pair.py` 的 X 判据守着）。
- mihomo **2026-10-08 起与 Surge / Egern 同号**（三内核统一 `v1.0.0`）；此前是独立版本线，该说法已作废。由 `check_version_header.py` 的 V5 断言守着。
- `.min` 版必须带**同一行**头注（对拍判据要求逐字节一致）。

### 2 · 什么时候升号

| 改动类型 | 升号 | 进 Release |
|:--|:--:|:--:|
| 配置键变动（功能变化） | ✅ | ✅ |
| 只改注释 / 文案 / 排版（配置键零变动，`.min` 逐字节不变） | ❌ | ✅（并入当天那张） |

- **一天一版**：一天内改几次都只升一次号，当天后续改动沿用同号。
- 版本号是**功能**的刻度 —— 注释改动不升号。
- 仓内不归档历史版本（历史在 git 与 Releases）。

### 3 · Release 怎么发

- **tag**：`vYYYY-MM-DD`（该日版本的诞生日期），指向 main。
- **资产**：当日各产品线最终版本的文件（完整版 + `.min`），固定名**带内核前缀**
  （`surge-lazy.conf` / `egern-routing.min.yaml` / `clash-lazy.min.yaml` 这样 ——
  Assets 面板自解释，不依赖「.conf=Surge / .yaml=Egern / clash-*=mihomo」的圈内约定）。
- **资产一律不带版本号** —— 这是铁律；版本号仅存在于正文条目与 profile 头注。
- **单边内核日如实注明**（如某日只有 mihomo 有内容），不硬凑。

#### 标题与正文模板

标题 = 分类 emoji + 日期 + 当日主题。正文层级（**H1 更新日志**标题永远置顶）：

```markdown
🛡️ 2026-10-07 · 三内核并列与 DNS 防泄露统一      ← Release 标题


> 本次两版同步，变更一致。

### 共同变更

#### 1. 关闭 IPv6
- Surge：`ipv6 = false`
- Egern：`ipv6: false`
- mihomo：顶层 `ipv6` + `dns.ipv6` 两处都关
- 影响：不再返回 AAAA 记录，双栈站点自动回落 IPv4；三内核行为对齐。

### 适用版本

- 分流版 v4.0.5
- 懒人版 v2.0.5
```

### 4 · 谁在守这些规矩

| 规矩 | 判据 |
|:--|:--|
| 头注版本格式合法、`.min` 与完整版一致 | `check_min_pair.py`（V1 / V2） |
| 三内核版本同号 | `check_min_pair.py`（X 判据）+ `clash/check_version_header.py`（V5） |
| 徽章承诺的组数 / 规则数与实际一致 | `check_badges.py` |
| 线上 Release 与当前版本一致 | `check_releases.py`（R1–R5） |

**没有豁免项。** 全套闸门全部对现役判，不存在「已登记的跳过」。
（改革前有 `SKIP_V7` / `STRICT_ARCHIVE` 两个逃生门 —— 它们只服务于已删除的归档机制，
随归档一并移除。现在 verify_all 在 CI 里对任何 SKIP 一律判失败。）

### 5 · 环境变量

分三类，登记**写在代码里**（`self-conf-skills/gates/verify_all.py` 的 `ESCAPES` / `INPUT` /
`DYNAMIC_READS` 三个常量），不写在文档里 —— 文档与代码分居两处就必须同步，
那是漂移的来源。判据：AST 抓到的全部环境变量名 − `INPUT` 必须是 `ESCAPES` 的子集，
否则启动即报错（防悄悄加后门）。

⚠️ **改判据宽严的开关（放行类）当前为空** —— 本仓刻意不留这类后门。
需要加时：写进 `ESCAPES` 并注明「默认是否安全、谁在用」。

### 6 · 版本号怎么升

- 版本号写在 profile **头注第一行**：`#! version=routing_vX.Y.Z`。
- **三内核同号**（由 X 判据与 V5 硬守）。
- `.min` 必须带**同一行**头注（对拍要求逐字节一致）。
- 升号改**全部 12 处**头注（三内核 × 两产品线 × 完整版/`.min`），改完跑 `verify_all.py`。
  ⚠️ **clash 的头注要手改** —— 它的 profile 虽由脚本生成，但头注是**保留**而非生成的。
- **历史版本不再在仓内归档** —— 要看历史用 `git log`；要下载历史版本去 Releases。


### 7 · 发布流程

```bash
python self-conf-skills/run/repo_state.py                      # ① 看清现状（版本 / Release / CI）
python self-conf-skills/gates/verify_all.py                        # ② 门禁全绿
python self-conf-skills/run/release_publish.py                 # ③ 计划模式：预览说明，一个字不发
python self-conf-skills/run/release_publish.py --apply         # ④ 真发（需 GITHUB_TOKEN）
```

**说明从 commit 自动汇总**（自上一个 tag 以来的 subject，过滤 chore/ci/style/test/refactor）
—— 不再有手写的发布说明表，因此不可能与代码漂移。
⇒ 想让某条变更出现在 Release 里，**把它写进 commit subject**。

tag = `vYYYY-MM-DD`（发布日）。同一天重复 `--apply` 是幂等的（回写同一张 + 对账资产）。

⚠️ 改 mihomo 的版本号要改**脚本**（`clash/override/*.js` 不直接写版本头 ——
版本头由 `build_profiles.py` 保留并写入；`.min` 由生成器同步）。直接改 profile 会在重新生成时被覆盖。

### 8 · 已知取舍

- 三内核统一同号（`check_min_pair` 的 X 判据 + `check_version_header` 的 V5 守着）；
  历史上 mihomo 曾是独立版本线，已作废。
- **仓内不保留历史版本快照** —— 历史在 git 与 Releases 里。

---

## Surge · 定位泄露实测（surge 侧）

> **何时读**：用户报「leak test 显示 China Telecom / 电信 / 联通 / 移动」，
> 或者**只是感觉**有泄露但说不清哪里漏。

#### 0 · 先分清三类"泄露"

`leak test` 的结果需要**分类解读**，它们指向完全不同的修法：

| 现象 | 含义 | 属于本项目的范围吗 |
|:-----|:-----|:-------------------|
| 检测到运营商 DNS 服务器 IP | **明文 `:53` 被链路读到** | ✅ 是，本文处理 |
| 检测到的是境外公共解析器（`8.8.8.8`） | 明文但也可能是你自己配的 | ✅ 是（出口 ② 或 ①） |
| 显示节点出口 IP 的城市 | **不是泄露** —— 是你实际走代理的证据 | ❌ 否 |

⚠️ 第三类是常见误报。很多 leak test 网站会把"你从哪来"也列出来 ——
那正是代理在工作的标志。

#### 1 · 抓包定位（最可靠）

#### 1.1 环境

```
设备 ← Wi-Fi → 路由器 ←→ 上游
         └─ 若能在路由器上抓，覆盖面最全
```

三种抓法，按覆盖面排序：

| 位置 | 抓得到 | 抓不到 |
|:-----|:-------|:-------|
| **路由器** | 全部：Surge 设备 + 旁路设备 + 未走 Surge 的流量 | 需要路由器支持 tcpdump / 镜像口 |
| **Surge 设备本机** | 本机发出的（含 Surge 自身） | 旁路设备的流量 |
| **macOS 做热点共享给 iOS** | 两者都抓得到 | 需要一台 mac |

**推荐第三种**：macOS 开热点，iOS 连上去，在 mac 上抓 `en0`。
一次能看到"iOS 本机 + Surge"和"经 iOS 转发出去的"。

#### 1.2 抓包命令

```bash
sudo tcpdump -i en0 -n -s 0 'udp port 53 or tcp port 53' -w dns.pcap

sudo tcpdump -i en0 -n 'udp port 53' | awk '{print $3, $5}'
```

#### 1.3 读结果

```
IP 192.168.1.50.53123 > 8.8.8.8.53: 12345+ A? example.com. (28)     ← ❌ 明文，出口 ②
IP 192.168.1.50.53124 > 223.5.5.5.53: 12346+ A? dns.google. (38)    ← ❌ 引导解析，出口 ①
IP 192.168.1.50.51000 > 1.1.1.1.443: ...                             ← ✅ DoH，加密
```

| 观察到 | 结论 |
|:-------|:-----|
| 目标是 `8.8.8.8:53` 等境外解析器，且**不是** Surge 设备发起的 | 出口 ② —— 旁路设备。检查 `hijack-dns` |
| 查询的域名是解析器自己的域名（`dns.google` / `dns.alidns.com`） | 出口 ① —— 引导解析。检查 `encrypted-dns-server` 是否写成了主机名 |
| 查询的域名是**你要访问的站点** | 出口 ③ —— 规则触发解析。检查 IP 类规则的 `no-resolve` |
| 目标端口是 443 或 853，且流量加密 | 不是明文泄露 |

#### 1.4 时机很重要

**冷启动期**（Surge 刚启动、网络刚切换）是出口 ① 的高发窗口 ——
此时加密 DNS 还没就绪，一切走 `dns-server`。

抓包要**从冷启动开始**：

```
1. 关掉 Surge
2. 开始抓包
3. 打开 Surge
4. 浏览几个网站
5. 停止抓包
```

只在"已经跑了一阵"的状态下抓，出口 ① 已经被掩盖了。

#### 2 · 不抓包的近似判断

如果没法抓包，按这个顺序排查：

#### 2.1 出口 ①

```bash
python self-conf-skills/gates/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 1\]'
python self-conf-skills/gates/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 2\]'
```

- `[1]` 报「N 个加密 DNS 端点不是 IP 字面量」→ 出口 ①
- `[2]` 报「`dns-server` 里出现 `system`」→ 出口 ①

#### 2.2 出口 ②

```bash
python self-conf-skills/gates/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 3\]'
```

- 报「缺少 `hijack-dns`」→ 出口 ② 完全敞开
- 报「未覆盖 N 个知名境外解析器」→ 出口 ② 部分敞开

**辅助判断**：家里有没有 HomePod / Apple TV / Chromecast / 智能音箱 / 智能电视？
有的话出口 ② 一定在发生。

#### 2.3 出口 ③

```bash
python self-conf-skills/gates/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 12\]'
python self-conf-skills/run/surge/audit_ruleset_content.py <profile> 2>&1 | grep -B1 -A3 'HIGH'
```

- `[12]` 报「第 N 行的 IP 类规则缺少 `no-resolve`」→ 本地规则缺
- `audit_ruleset_content` 报「N 条 IP 类条目**不带 no-resolve**」→ **远程规则集**里有

⚠️ **后者是最容易漏的** —— 它不在你的 profile 里，你本地的审计器看不见。
必须下载规则集内容才能发现。

#### 2.4 关于测试端点 —— **先确认它是不是泄露面**

```bash
grep 'proxy-test-url\|internet-test-url' <profile>
```

⚠️ **别急着下结论。** 官方 KB 明确：「走代理策略时…DNS 解析永远在代理服务器进行」，
本地解析只在命中 DIRECT 时发生。所以：

- 端点域名**只有在它落进 DIRECT 路径时**才产生本地解析；
- 它是给 `smart` 打分的**性能探针**，不是泄露通道。

选址是**性能取向**：`internet-test-url`（连通性）宜国内，
`proxy-test-url`（打分）宜境外（含国际段才反映真实路径）。
审计器 `check_6` 对境外端点**只报 LOW 提示**。

> 这一条曾是本项目的**误报来源** —— 详见 `pitfalls.md` 坑 14。

#### 3 · 修法对照表

| 定位到的出口 | 修法 | 注意 |
|:-------------|:-----|:-----|
| ① 引导解析 | `encrypted-dns-server` 端点改 IP 字面量；`dns-server` 去掉 `system` 与主机名 | 换成 IP 会失去"按域名走 CDN 就近解析"与 ECS 合规 |
| ② 旁路设备 | 配 `hijack-dns`；想全量写 `*` | `hijack-dns` **拦不住 DoH**（走 443） |
| ③ 规则触发 | 所有 IP 类规则加 `no-resolve`（本地 + 远程规则集） | ⚠️ **必须同时确认 `FINAL` 前有域名体量足够的国内直连集**，见下 |
| 测速端点 | 换国内 204 | 见 [`clash.md`](./profiles/clash.md) §1.4 |

#### ⚠️ 出口 ③ 的修法有个陷阱

给 IP 规则加 `no-resolve` 会**同时**关掉「解析后判 IP 归属」这条直连路径。
若 `FINAL` 前没有域名类国内直连集，国内网站会整片走代理。

**修完必须再跑一次分流覆盖审计**：

```bash
python self-conf-skills/run/surge/audit_routing_coverage.py <profile>
```

期望国内探针全部命中 `DIRECT`。详见 [`pitfalls.md`](./pitfalls.md) 坑 1。

#### 4 · 验证修好了

```
1. 冷启动抓包（§1.4 的 5 步）→ 应无明文 :53
2. python self-conf-skills/gates/surge/check_surge_dns.py <profile>       → exit 0
3. python self-conf-skills/run/surge/audit_ruleset_content.py <profile> → exit 0
4. python self-conf-skills/run/surge/audit_routing_coverage.py <profile>→ exit 0
5. leak test 网站复测 → 不再显示运营商 DNS
6. 实测：国内网站直连（不绕代理）；游戏机 NAT 检测正常
```

⚠️ 第 5 步的解读见 §0 —— **leak test 显示节点出口城市不是泄露**。

#### 5 · 边界：什么情况不该"修"

不是所有明文 `:53` 都必须消除。以下情况属**可接受的取舍**，纠结它们是浪费：

| 情况 | 为什么可接受 |
|:-----|:-------------|
| 解析器端点本身是主机名，冷启动解析一次 | 换 IP 会失去 CDN 就近解析与 ECS 合规。声明 `# audit-waive: 1` 即可 |
| 设备用 DoH 直连（不经 Surge） | DoH 本身加密，不算明文泄露。除非你想统一管控 |
| 企业内网 DNS（`192.168.x.1:53`） | 那是本地网络的一部分，不是"泄露到运营商" |
| `hijack-dns` 没穷举全部解析器 | `:53` 地址空间无限，永远列不全。覆盖常见 6 个够用 |
| 自建 DNS 服务器上的明文查询 | 那是你自己控制的链路，不是第三方 |

> 📌 判断标准始终是同一条：**这条明文通路是否"必然会被走到"？**
> 一次性、可控、且能说清收益的通路，不算必须消除的泄露面。

---

## Egern · 定位泄露实测（egern 侧）

> 本文是 [`AGENTS.md`](../../AGENTS.md) 的引用文件。 **何时读**：用户报「leak test 显示 china telecom / 联通」时。

**第一个动作不是改配置** —— 配置层只能证明「我声明的上游不会产生这个应答」，
剩下的必须落到网络层实测。

---

用户说"leak test 显示 china telecom / 联通"时，**第一个动作不是改配置，是把"运营商解析器"这条路径实测出来**。配置层能证明的只有"我声明的上游不会产生这个应答"，剩下的必须落到网络层。

**⓪ 先确认链路（不做这步，后面全是白做——见坑 11）。** 问清「哪台设备 / Wi-Fi 还是蜂窝 / 谁是 DNS」。两条链路的实测对象不同：

| 链路 | 明文 :53 的下场 | 怎么测 |
|---|---|---|
| 家庭网 + 旁路由（OpenClash/mihomo） | 被透明重定向到旁路由，返回 **Fake IP `198.18.x`** | 逐个问外部解析器同一域名（见 ③） |
| **运营商蜂窝** | 被运营商重定向到**它自己的递归解析器**；或直接不通 → 掉到系统 DNS | 见 ④ 的「蜂窝变体」 |

**① 先算 IP 归属**（`curl -s https://ipinfo.io/<ip>/json`）。`org` 里带哪个运营商，就直接排除掉所有非该运营商的上游。**这一步常常一下就把范围锁到"没走到 profile 声明的上游"。**

**② 看设备自己网络的 DNS/网关**（Windows：`netsh interface ipv4 show dnsservers` / `show config`）。

**③ 测这张网有没有把 :53 全量劫持**（旁路由/OpenClash 的 DNS 重定向很常见）。逐个问外部解析器同一个域名：
```bash
for s in 223.5.5.5 119.29.29.29 1.1.1.1 8.8.8.8 <可疑IP> 192.168.2.1; do nslookup www.qq.com "$s"; done
```
若**所有**外部解析器都返回同一个 `198.18.x.x`（mihomo/Clash 默认 Fake IP 段），说明明文 :53 被旁路由吃掉了。
**关键副作用：Egern 的 bootstrap 也就此失效**（拿回的是一张 Fake IP，不是可用应答），而官方规定 bootstrap 失败就**自动使用系统 DNS** → 运营商。

**④ 用 `whoami.akamai.net` 直接问出某条路径的真实递归方**（Akamai 会回显"它看到的解析器出口 IP"）：
```bash
nslookup -type=A whoami.akamai.net 192.168.2.1      # 真实出口：如 219.128.79.150（中国电信广州）
nslookup -type=A whoami.akamai.net 192.168.2.168    # 若返回 198.18.x 说明被 fake-ip 吃掉，看不到真实出口
```
把回显 IP 和用户报的 IP 对比（同运营商/同段 = 同一条路径），**结论就从"怀疑"变成"实锤"**。

**④-蜂窝变体（本次真正用上的，比 ③④ 更通用）**：手机在运营商蜂窝上时，你没法从电脑去探测它那条链路，所以**只能"改一行、复测"**。最有效的一个实验是**把 `bootstrap` 换成一个可辨识的国内公共 DNS**（如 `180.76.76.76` 百度），复测 leak test：

| 结果 | 结论 |
|---|---|
| 归属变成 **Baidu/百度** | bootstrap 在应答且可用 ⇒ 原来的"运营商"来自 **bootstrap 全失败 → 系统 DNS** |
| **仍是 China Telecom** | 明文 :53 被运营商**透明重定向**（或那次解析根本没走 bootstrap）⇒ 去查系统级加密 DNS（`hijack_dns` 只劫持 UDP:53，拦不住配置描述文件里的 DoH/DoT） |

**④-蜂窝变体-2**：让用户核对 **设置 → 通用 → VPN与设备管理 → 配置描述文件** 里有没有 DNS/DoH/DoT 描述文件（运营商推的、公司 MDM 推的、1.1.1.1 App 装的）。**存在即绕过 UDP:53**，此时 Egern 无辜。这是"改了半天配置却发现不是配置问题"的高频原因。

**⑤ 交叉验证测试环境**：Egern 只跑在 Apple 设备上。若 leak test 是在 Windows/安卓上跑的，结果必然是局域网 DNS 的，与 profile 无关 —— 这种情况先问清楚，别改配置。同理，让用户提供 **Egern 自己的 DNS 日志**（它详细记录 DNS 流量）：哪条规则、哪个上游应答的，是唯一能直接证伪/证实的一条证据。

**⑥ 能治本的路由器侧动作**：把主路由 WAN/LAN 的 DNS 从"自动获取（= 运营商）"改成 `223.5.5.5`/`119.29.29.29`。这样即使将来任何客户端回退到 `system`，落点也不再是运营商。

⚠️ **`vif_only` 语义官方只有一句"仅虚拟网接口模式，默认 false"，无法确认细节。** 用户配置里若出现**非默认值**（`true`），只能当作 A/B 候选单独排除，**不要凭猜测替用户改**（常见于把机场模板当基线改的场景）。

---

## mihomo · 定位泄露实测（clash 侧）

> **何时读**：用户报「leak test 显示 China Telecom / 电信 / 联通 / 移动」，
> 或者**只是感觉**有泄露但说不清哪里漏。
>
> 本文是 mihomo（clash/）侧。Surge / Egern 侧见各自的 `ops.md` ——
> 三侧的**归并方式一致**（按「谁触发了一次明文查询」分类），但**通道清单不同**：
> mihomo 侧多一条 IPv6 面，且引导链的键名与语义完全不同。

<!-- Egern 侧同 Surge 侧（见上方「先分清三类泄露」）—— 唯一差异：mihomo 侧多一类 fake-ip 假象（见下） -->

#### 2 · mihomo 的 DNS 通路图

先建立机制模型，再谈定位。mihomo 的解析器分**五层**，各管一件事：

| 键 | 本仓现役值 | 管什么 |
|:---|:-----------|:-------|
| `default-nameserver` | `223.5.5.5` · `119.29.29.29` | **仅**解析下面那些 DoH 端点**自身的域名**（引导）|
| `nameserver` | `https://dns.cloudflare.com/dns-query` · `https://dns.google/dns-query` | 主解析器（业务域名）|
| `fallback` | 同上（`routing` 有，`lazy` 未设）| 主解析器被判定为"境外答案"时的备用 |
| `fallback-filter` | `geoip: true` | 判定规则：答案 IP 落在境外 ⇒ 改用 `fallback` |
| `proxy-server-nameserver` | 国内 DoH | 解析**代理节点自己的域名** |
| `direct-nameserver` | 国内 DoH | 解析 **DIRECT 出站**的域名 |
| `nameserver-policy` | 广告集 → `rcode://success`；`private,cn` → 国内 DoH | 按域名换解析器 |

配套的三个开关：

| 键 | 本仓值 | 作用 |
|:---|:-------|:-----|
| `enhanced-mode` | `fake-ip` | 不真解析就先返回假 IP，等连接建立时再按域名分流 |
| `fake-ip-range` | `198.18.0.1/16` | 假 IP 段（**见到它就说明被 mihomo 接住了**）|
| `dns.ipv6` / 顶层 `ipv6` | 均为 `false` | 不返回 AAAA —— 见 §6 |

外加 TUN 层接管：

```yaml
tun:
  enable: true
  dns-hijack:
    - any:53        # ⭐ 接管所有发往 :53 的 UDP
  auto-route: true
  strict-route: true
```

```
                    ┌──────────────────────────────────┐
   应用/旁路设备 ───▶│ tun.dns-hijack: any:53           │──▶ mihomo DNS
        :53         │ （不识 DNS 设置的设备也吃进来）    │
                    └──────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      default-nameserver     nameserver            nameserver-policy
      （明文 UDP:53）         （DoH :443）           （按域名分流）
       引导 DoH 端点           业务域名              广告→rcode / cn→国内DoH
              │                    │
              │            fallback（geoip 判定）
              │
      ⚠️ 面①：冷启动必走一次
```

⭐ **读图要点**：`default-nameserver` 是**唯一走明文 UDP:53** 的一层，
而且它只解析那两个 DoH 端点的域名（`dns.cloudflare.com` / `dns.google`）。
这正是本仓实测过的结论 —— 见 §4.1。

#### 3 · 抓包定位（最可靠）

#### 3.1 环境

```
设备 ← Wi-Fi → 路由器 ←→ 上游
         └─ 若能在路由器上抓，覆盖面最全
```

三种抓法，按覆盖面排序：

| 位置 | 抓得到 | 抓不到 |
|:-----|:-------|:-------|
| **路由器** | 全部：mihomo 设备 + 旁路设备 + 未走 TUN 的流量 | 需要路由器支持 tcpdump / 镜像口 |
| **mihomo 设备本机** | 本机发出的（含 mihomo 自身） | 旁路设备的流量 |
| **macOS 做热点共享给 iOS** | 两者都抓得到 | 需要一台 mac |

#### 3.2 抓包命令

同 Surge 侧的「抓包命令」（`tcpdump` 逐字相同）。

#### 3.3 读结果

```
IP 192.168.1.50.53123 > 8.8.8.8.53: 12345+ A? example.com. (28)      ← ❌ 明文，面②
IP 192.168.1.50.53124 > 223.5.5.5.53: 12346+ A? dns.google. (38)     ← ⚠️ 引导解析，面①
IP 192.168.1.50.51000 > 1.1.1.1.443: ...                              ← ✅ DoH，加密
IP6 2001:db8::2 > 2400:3200::1.53: AAAA? www.google.com               ← ❌ 面③′
```

| 观察到 | 结论 | 去查哪节 |
|:-------|:-----|:---------|
| 目标是 `8.8.8.8:53` 等解析器，且**不是** mihomo 设备发起的 | 面② —— 旁路设备 | §4.2 |
| 查询的域名是解析器自己的域名（`dns.google` / `dns.cloudflare.com`）| 面① —— **引导解析，冷启动必走** | §4.1 |
| 查询的域名是**你要访问的站点** | 面④ —— 规则判定触发的解析 | §4.4 |
| **AAAA 查询** / 目标是 IPv6 地址 | 面③′ —— **mihomo 特有** | §6 |
| 目标端口 443 / 853 且流量加密 | 不是明文泄露 | — |

#### 3.4 时机很重要

**冷启动期**（mihomo 刚启动、网络刚切换）是面①的高发窗口 ——
此时 `default-nameserver` 必须先把 DoH 端点的域名解析成 IP，才能建立加密通道。

抓包要**从冷启动开始**：

```
1. 停掉 mihomo
2. 开始抓包
3. 启动 mihomo
4. 浏览几个网站
5. 停止抓包
```

只在"已经跑了一阵"的状态下抓，面① 已经被掩盖了。

#### 4 · 五类泄露面 · 定位与收口

归并口径：**谁触发了一次明文查询**。同一类"现象"可能来自不同触发者，
修法完全不同 —— 所以按触发者分，不按现象分。

| # | 触发者 | 面 | 本仓现役状态 |
|:-:|:-------|:---|:-------------|
| ① | 引导链 | 加密端点写成主机名 ⇒ 冷启动必解析一次 | ⚠️ **必然发生**（设计取舍）|
| ② | 回退链 | `fallback` 落到明文解析器 | ✅ 已收口（`fallback` 也是 DoH）|
| ③ | 旁路设备 | 不识 DNS 设置的设备直接发 `:53` | ✅ 已收口（`tun.dns-hijack: any:53`）|
| ④ | 规则判定 | IP 类规则缺 `no-resolve` ⇒ 为判定而解析 | ⚠️ `routing` 版有 3 条待核 |
| ⑤ | 远程规则集 | 内嵌裸 IP 条目 ⇒ 每个走到该规则的域名都被解析 | ⚠️ 需拉下来数 |
| ③′ | **IPv6** | AAAA 返回 + 真实 IPv6 绕过 TUN | ✅ 已收口（双 `ipv6: false`）|

#### 4.1 面① · 引导解析（冷启动必走一次）

**表现**：冷启动瞬间有一到两条明文 `:53`，查询的域名是 DoH 端点自己。

**机制**：`nameserver` 写的是 `https://dns.cloudflare.com/dns-query` ——
**端点本身是主机名**。要连它就得先知道它的 IP，这一问只能用 `default-nameserver`
（那一层是**明文 UDP**，因为它不能再依赖任何加密解析器，否则成环）。

⭐ **本仓已实测过这条**（2026-09-22，本地 mihomo 内核 + 本机 DNS sink）：

> 把唯一走明文 UDP 的 `default-nameserver` 顶到本机 sink 上跑真实解析，
> **明文 `UDP:53` 只出现在 `dns.google` / `dns.cloudflare.com` 两个 DoH 端点域名上**
> （解析端点自身所需的引导），业务域名与节点域名全部走 `443` 加密端点。

**定位方法**：

```bash
grep -A3 'default-nameserver' clash/profiles/*.yaml
grep -A3 '^  nameserver:' clash/profiles/*.yaml
```

**收口手段**：

| 方案 | 做法 | 代价 |
|:-----|:-----|:-----|
| A（本仓采用）| 接受引导，把 `default-nameserver` 钉成**国内**解析器 | 冷启动仍有一次明文，但只泄露端点域名 |
| B | `nameserver` 端点改成 IP 字面量（`https://1.1.1.1/dns-query`）| 失去 CDN 就近解析与 ECS 合规；且 IP 证书校验需配 `sni` |
| C | 用系统 hosts 预置端点 IP | 要维护，且端点 IP 会变 |

⚠️ **方案 A 是取舍不是遗漏**：引导解析在机制上**不可能消除**，
只能把它限制在「只解析端点自己的域名」这一点上。
**这属于"可接受的取舍"**（见 §10）—— 判断标准是「这条通路是否**必然会被走到**」：
面① 是必然的，但它只带出端点域名，不带出用户访问了什么。

**验证脚本**：`self-conf-skills/gates/clash/check_structure.py`（守 ipv6 与结构，不判引导）；
引导层本身**没有门禁** —— 靠 §3 的冷启动抓包实测。

#### 4.2 面② · 回退链落到明文

**表现**：明文 `:53`，目标是某个解析器，查询的域名是**业务域名**。

**机制**：`fallback` 的作用是「主解析器的答案被判定为境外时，换一台再问一次」。
若 `fallback` 里写的是明文解析器（`8.8.8.8` / `114.114.114.114`），
那么每次 `fallback-filter` 命中 ⇒ **一次明文查询，且带的是业务域名**。

**定位方法**：

```bash
grep -A4 'fallback' clash/profiles/*.yaml
```

本仓现役：

| profile | `fallback` | `fallback-filter` |
|:--------|:-----------|:------------------|
| `routing.yaml` | `https://dns.cloudflare.com/dns-query` · `https://dns.google/dns-query` | `geoip: true` |
| `lazy.yaml` | **未设置** | 未设置 |

✅ 两版都没有明文回退 —— `routing` 的 `fallback` 与 `nameserver` 同为 DoH，
`lazy` 干脆不开回退。**面② 已收口。**

**收口手段**：`fallback` 里**只写加密端点**（`https://…` / `tls://…`），
绝不写裸 IP。若为了国内解析精度想用国内解析器，写成 `https://223.5.5.5/dns-query`
而不是 `223.5.5.5`。

⚠️ 一个容易忽略的点：`fallback-filter.geoip: true` 会让**每一个**被判定为境外答案的查询
都触发第二次查询。即使两端都是 DoH，这也是双倍延迟。
**先问一句"我真的需要回退吗"** —— `lazy` 版不开回退就是这个判断。

**验证脚本**：无专门门禁 —— 需要人工核对 §5.1 的清单。

#### 4.3 面③ · 旁路设备（不识 DNS 设置的设备直接发 :53）

**表现**：明文 `:53`，**源地址不是 mihomo 设备**（或该设备根本没装 mihomo）。

**机制**：智能音箱 / Apple TV / 游戏机 / 智能电视这类设备不认你的 DNS 配置，
它们按 DHCP 下发的解析器（通常是**运营商的**）直接发 `:53`。
mihomo 在本机上接管不了它们的查询 —— 除非在 **TUN 层劫持**。

**收口手段**：

```yaml
tun:
  enable: true
  dns-hijack:
    - any:53      # ⭐ 接管所有目的 :53 的 UDP，不问来源
```

✅ 本仓四份 profile 都是 `dns-hijack: [any:53]`。**面③ 已收口。**

| 写法 | 效果 |
|:-----|:-----|
| `any:53` | 劫持**所有** UDP:53（推荐）|
| `0.0.0.0:53` / 逐个列解析器 | 只劫持列出的目标 —— **列不全就漏** |

⚠️ **`dns-hijack` 拦不住 DoH**（走 443，不是 53）。
设备自己配了 DoH 的话，这条面仍然敞开 —— 但那时流量是加密的，
不算"明文泄露到运营商"，除非你要统一管控。

⚠️ 前提：设备流量必须**经过运行 mihomo 的那台机器**（旁路由 / 网关场景）。
旁路设备走另一条物理链路时，TUN 再怎么劫持也看不见。

**定位方法**：

```bash
sudo tcpdump -i en0 -n 'udp port 53' | awk '{print $3}' | sort -u
grep -A3 'dns-hijack' clash/profiles/*.yaml
```

**验证脚本**：`self-conf-skills/gates/clash/check_structure.py`（守结构与 ipv6，**不判 dns-hijack**）
⇒ **面③ 没有门禁**，靠抓包 + 人工核对 `tun` 段。

#### 4.4 面④ · 规则判定触发的解析

**表现**：明文（或至少多余一次）解析，查询的域名是**你要访问的站点**。

**机制**：**IP 类规则没带 `no-resolve`，就会为了"判断这个域名是不是某个 IP 段"
而强制先解析一次。** 这条与 Surge / Egern 侧同构，但**落点不同**：

| 内核 | 写法 |
|:-----|:-----|
| Surge | `IP-CIDR,1.2.3.0/24,DIRECT,no-resolve`（行内）|
| mihomo | `RULE-SET,geoip-cn,DIRECT,no-resolve`（行内，规则级）|

**定位方法**：

```bash
python - <<'PY'
import yaml
for f in ["lazy.yaml","routing.yaml"]:
    c = yaml.safe_load(open("clash/profiles/"+f, encoding="utf-8"))
    rp = c.get("rule-providers") or {}
    print("="*20, f)
    for r in c.get("rules") or []:
        p = [x.strip for x in r.split(",")]
        prov = p[1] if p[0] == "RULE-SET" else None
        beh = (rp.get(prov) or {}).get("behavior") if prov else None
        if beh == "ipcidr" or p[0].startswith(("IP-CIDR","GEOIP","IP-ASN")):
            ok = "no-resolve" in [x.lower for x in p]
            print("  %-45s behavior=%-8s no-resolve=%s" % (r, beh, ok))
PY
```

本仓实测结果：

| profile | 规则 | `no-resolve` |
|:--------|:-----|:------------|
| `lazy` | `RULE-SET,geoip-private,DIRECT,no-resolve` | ✅ |
| `lazy` | `RULE-SET,geoip-cn,DIRECT,no-resolve` | ✅ |
| `routing` | `RULE-SET,geoip-private,DIRECT,no-resolve` | ✅ |
| `routing` | `RULE-SET,geoip-google,Google` | ❌ **缺** |
| `routing` | `RULE-SET,geoip-telegram,Telegram` | ❌ **缺** |
| `routing` | `RULE-SET,geoip-cn,DIRECT` | ❌ **缺** |

⚠️ **这是本仓现役的真实差异，不是文档笔误**：`lazy` 两条都带，`routing` 有 3 条不带。

**这 3 条该不该补？先别急着补。** 见下节的双刃陷阱 ——
补 `no-resolve` 会**同时关掉**「解析后判 IP 归属」这条直连路径。

**收口手段**：给所有 **ipcidr** 行为的规则加 `no-resolve`，
且**同一时刻**确认 `MATCH` 之前有域名体量足够的国内直连集接住。

##### 4.4.1 ⚠️ `no-resolve` 是双刃刀（补之前必读）

```
刀刃一：不带 no-resolve  ⇒ 为判定而强制解析（面④）
刀刃二：带上 no-resolve  ⇒ 它不再匹配域名（没有解析结果，IP 归属无从判断）
```

⇒ **后果**：单独靠 `geoip-cn` 判国内的话，补完 `no-resolve` 之后
国内域名**全靠 IP 判定，而 IP 判定刚被关掉** ⇒ 整片走 `MATCH → Proxy`。

本仓 `routing` 版的顺序是目前**不补的理由**：

```
… RULE-SET,cn,DIRECT          ← 域名类国内集（META geosite/cn.mrs）
  RULE-SET,geoip-cn,DIRECT    ← IP 类兜底
  MATCH,Proxy
```

`cn`（域名集）排在 `geoip-cn`（IP 集）**之前** ⇒ 多数国内域名已被 `cn` 接住，
`geoip-cn` 只对漏网的做 IP 判定。这个顺序下，缺 `no-resolve` 的代价是
「漏网的国内域名多解析一次」，而不是「国内整片走代理」。

> 📌 **判据：补 `no-resolve` 的准入条件是「它前面已有域名类国内集接住」。
> 本仓 `routing` 满足（`cn` 在 `geoip-cn` 前），所以补是安全的；
> 但若哪天把 `geoip-cn` 挪到 `cn` 之前，补了就会出事。**

**补完之后必须再跑一次分流验证**（本仓**已有** mihomo 侧的分流覆盖审计脚本 `self-conf-skills/run/clash/audit_routing_coverage.py`，闸门 #9 ——
这是与姊妹仓的一个差距，见 §9.2）。

**验证脚本**：无（本仓 mihomo 侧没有 `no-resolve` 审计器）。
定位靠上面的手工脚本；**收口后的分流验证靠实测**。

#### 4.5 面⑤ · 远程规则集内嵌裸 IP 条目

**表现**：profile 里每条 IP 规则都写了 `no-resolve`，但日志/抓包显示仍有大量意外解析。

**机制**：规则是 `RULE-SET,<provider>,<policy>` —— **你引用的规则集在别人仓库里**。
如果那份 `.yaml` / `.mrs` 里有**裸 IP 条目且不带 `no-resolve`**，
那么**每个走到该规则的域名都会被强制本地解析一次**。

> ⚠️ **这是最容易漏的一条** —— 它不在你的 profile 里，**本地的静态门禁看不见**。
> 必须把规则集**下载下来数**才能发现。

**定位方法**：

```bash
grep -cE '^(IP-CIDR|IP-CIDR6|IP-ASN|GEOIP|ASN)' rules/emby.list rules/apple_system.list rules/AI.list

curl -s https://raw.githubusercontent.com/RiverFlowsInUUU/Jinx/main/mihomo-direct.yaml \
  | grep -cE 'IP-CIDR'
```

**本仓现役的规则集按行为分两类**（`self-conf-skills/gates/clash/check_structure.py` 读得到 `behavior`）：

| behavior | 是否可能含裸 IP | 本仓哪些 |
|:---------|:----------------|:---------|
| `ipcidr`（mrs）| ✅ **是**（内容就是 IP 段）| `geoip-private` / `geoip-google` / `geoip-telegram` / `geoip-cn` |
| `domain`（mrs）| ❌ 否 | `cn` / `openai` / `github` / `youtube` … |
| `classical`（yaml）| ⚠️ 混合，要看内容 | `Jinx-CN` / `Jinx-Ads` / `emby` / `AI_Domains` / `apple-system` |

⭐ **`build_rules.py` 生成物自带结论**，头部注释写明：

```
```

⇒ `emby` / `AI_Domains` / `apple-system` 三份**零 IP 条目**
（`grep -cE '^(IP-CIDR|...)' rules/*.list` 实测均为 0），
**引用它们时不写 `no-resolve` 是正确的** —— 写了反而有害（见 §4.4.1 的刀刃二）。

**收口手段**：

1. 自托管的三份：改真源 `.list`，重跑 `build_rules.py`（**单一真源，不可能漂移**）；
2. 第三方集：要么换源，要么在规则行加 `no-resolve`（代价见 §4.4.1）；
3. 定期跑 `check_remote_urls.py` —— 它守的是「URL 活不活」，
   **不守内容**，但死链 ⇒ 空集 ⇒ 该走的规则不生效（静默降级）。

**验证脚本**：`self-conf-skills/run/clash/build_rules.py --check`（只守**生成物新鲜度**，
不守第三方内容）。第三方内容**没有门禁** —— 靠人工拉下来数。

#### 4.6 汇总：哪一面有门禁，哪一面没有

| 面 | 有门禁守吗 | 靠什么定位 |
|:--:|:-----------|:-----------|
| ① 引导解析 | ❌ 无 | 冷启动抓包（§3.4）|
| ② 回退链 | ❌ 无 | 人工核对 §5.1 清单 |
| ③ 旁路设备 | ❌ 无 | 抓包看源地址 + 核对 `tun.dns-hijack` |
| ④ 规则判定 | ❌ 无（本仓 mihomo 侧无 `no-resolve` 审计器）| 手工脚本列 IP 类规则 |
| ⑤ 远程集内容 | ⚠️ 只守新鲜度，不守内容 | 拉下来数 |
| ③′ IPv6 | ✅ **有** | `check_structure.py` 的两条断言 |

> 🔴 **六个面里只有一个有门禁。** 这不是文档遗漏，是**本仓 mihomo 侧的现状**：
> 现有四道 clash 门禁守的是**结构 / 两形态一致 / 脚本静态一致 / 生成物新鲜度**，
> **没有一道是"防泄露语义"审计器**。
> 姊妹仓 Surge 侧有 `check_surge_dns.py`（12 项判据）、Egern 侧有 `check_egern_dns.py`
> —— **mihomo 侧缺这一层**。定位泄露面因此必须靠机制推导 + 抓包实测。

#### 5 · 不抓包的近似判断

#### 5.1 一张核对清单（按顺序过）

```bash
grep -A3 'default-nameserver' clash/profiles/*.yaml      # 期望：国内解析器（明文层只有它）
grep -A3 '^  nameserver:'     clash/profiles/*.yaml      # 期望：https://（端点为主机名 ⇒ 必有引导）

grep -A5 'fallback'           clash/profiles/*.yaml      # 期望：https:// 或整段不设

grep -A3 'dns-hijack'         clash/profiles/*.yaml      # 期望：any:53


grep -cE '^(IP-CIDR|IP-CIDR6|IP-ASN|GEOIP|ASN)' rules/*.list   # 期望：0

grep -n '^ipv6:' clash/profiles/*.yaml; grep -n '  ipv6:' clash/profiles/*.yaml
python self-conf-skills/gates/clash/check_structure.py              # 期望 exit 0
```

#### 5.2 关于测试端点 —— **先确认它是不是泄露面**

mihomo 侧的健康检查与延迟测试 URL（`proxy-providers.*.health-check.url`、
`proxy-groups[].url`）在**本仓是 `https://www.gstatic.com/generate_204`**。

⚠️ **别急着把它当泄露面。** 这些探针走的是**代理路径**（`proxy-server-nameserver` 那一层，
本仓是国内 DoH），不是本地明文。它们是**性能探针**，不是泄露通道。

⚠️ 但有一条例外要核：`check_remote_urls.py` 的 `HC_URLS` 常量
把 `https://www.gstatic.com/generate_204` 排除在探测之外 ——
它是**连通性探测目标，不是规则集资源**，可达性检查不该探测它。

#### 5.3 一个高频的"不是配置问题"

若本机或旁路上**另有**一台跑着 mihomo / OpenClash 的设备，
你从电脑探测到的 `:53` 可能被**透明重定向**到它 ——
返回的是 Fake IP（`198.18.x`），看不到真实出口。

判据：逐个外部解析器问同一个域名，若**全部**返回 `198.18.x.x` ⇒ 被旁路由吃掉了。

```bash
for s in 223.5.5.5 119.29.29.29 1.1.1.1 8.8.8.8; do nslookup www.qq.com "$s"; done
```

#### 6 · ③′ IPv6 泄露面（本仓特有，Surge / Egern 侧无对应物）

⭐ **这一节是 mihomo 侧独有的。** Surge / Egern 侧的 `ipv6: false` 只影响
"是否返回 AAAA"，它们**没有 TUN** ⇒ 不存在"绕过 TUN"这条通路。
mihomo 侧因为**有 TUN**，IPv6 的两件事会叠加成一个真正的泄露面。

#### 6.1 机制：两个开关，缺一个就漏

| 开关 | 作用 | 不关会怎样 |
|:---|:---|:---|
| `dns.ipv6` | 是否返回 AAAA 记录 | 开了 ⇒ 双栈站点拿到 AAAA |
| 顶层 `ipv6` | TUN 是否接管 IPv6 流量 | 关了 ⇒ **IPv6 流量不走 TUN** |

⇒ **关键组合**：`dns.ipv6: true` + 顶层 `ipv6: false`
= 应用拿到了真实的 IPv6 地址，但 IPv6 流量**不被 TUN 接管**
⇒ **双栈站点直接走本机真实 IPv6 出网，绕过代理** = 必然通路。

> 📌 历史记录里记的正是这条：
> 「此前 `dns.ipv6` 为 `true` 时会返回 AAAA 记录，而本机真实 IPv6 未被 TUN 完整接管，
> 双栈站点优先走 IPv6 ⇒ 出口 IP 与节点不符（表现为**站点测到美国 IPv6**）。」

#### 6.2 表现

| 现象 | 说明 |
|:---|:---|
| leak test 显示**你的真实 IPv6 地址**（不是节点出口）| 最常见 |
| 站点测到"美国 IPv6"而你节点在日本 | 出口 IP 与节点不符 |
| 部分站点能开、部分超时 | 双栈站点优先 IPv6，那条路没代理 |
| **只有 IPv4 的站点完全正常** | 印证是 IPv6 侧的问题 |

⚠️ 误诊风险：这些现象也像"节点挂了"或"分流错了"。
**区分方法**：IPv4 侧（同一个站点的 A 记录）走代理正常，只有 IPv6 侧露馅 ⇒ 面③′。

#### 6.3 定位方法

```bash
grep -n '^ipv6:'  clash/profiles/*.yaml
grep -n '  ipv6:' clash/profiles/*.yaml

nslookup -type=AAAA www.google.com

sudo tcpdump -i en0 -n 'ip6' | head -40

python self-conf-skills/gates/clash/check_structure.py        # 期望 exit 0
```

#### 6.4 收口手段

```yaml
ipv6: false          # 顶层：TUN 不管 IPv6（配合下一条，让应用根本不拿 AAAA）
dns:
  ipv6: false        # DNS：不返回 AAAA ⇒ 双栈站点自动回落 IPv4
```

✅ **本仓四份 profile 均为 `ipv6: false` + `dns.ipv6: false`**，与姊妹仓对齐。

**为什么两个都要写**（而不是只关 `dns.ipv6`）：

| 只关哪个 | 剩下什么风险 |
|:---------|:-------------|
| 只关 `dns.ipv6` | 应用拿不到 AAAA，但**应用自己用 IPv6 字面量 / 其它途径拿到 IPv6 时**，那条路仍不被 TUN 接管 |
| 只关顶层 `ipv6` | TUN 不管 IPv6，但 `dns.ipv6: true` 仍会返回 AAAA ⇒ **应用拿着 AAAA 直连出去**（正是曾经记过的那个 bug）|
| **两个都关** | 不返回 AAAA ⇒ 应用只能走 IPv4 ⇒ IPv4 必经 TUN ⇒ **通路闭合** |

⭐ **两个都关才是"必然不通"**：关 `dns.ipv6` 让应用**拿不到** IPv6 地址，
关顶层 `ipv6` 让 IPv6 流量**即使存在也不被误当成已接管**。两者叠加才没有残余通路。

#### 6.5 验证脚本

```bash
python self-conf-skills/gates/clash/check_structure.py
```

守的两条（`check_structure.py` §④）：

```python
if c.get("ipv6") is not False:
    errs.append("顶层 ipv6 未显式关闭")
if dns.get("ipv6") is not False:
    errs.append("dns.ipv6 未显式关闭")
```

⚠️ 用的是 **`is not False`** ⇒ **键缺失也算不过**。这是刻意的：
`ipv6: false` 虽等于 mihomo 默认值，但**必须显式声明**（对齐面纪律：
让"四份对拍看文件即知"，不用查各内核默认值）。

⭐ **面③′ 是六个面里唯一有门禁的。** 其余五面都没有 —— 见 §4.6。

#### 7 · 修法对照表

| 面 | 修法 | 注意 |
|:---|:---|:---|
| ① 引导解析 | 接受它（方案 A）：把 `default-nameserver` 钉成国内解析器 | 换 IP 字面量会失去 CDN 就近解析与 ECS 合规；**机制上不可能完全消除** |
| ② 回退链 | `fallback` 只写 `https://`；或干脆不开 `fallback` | 开 `fallback-filter.geoip` 会双查（双倍延迟）|
| ③ 旁路设备 | `tun.dns-hijack: [any:53]` | 拦不住 DoH（443）；且设备流量必须经本机 |
| ④ 规则判定 | IP 类规则加 `no-resolve` | ⚠️ **必须同时确认 `MATCH` 前有域名类国内直连集**（§4.4.1）|
| ⑤ 远程集内容 | 自托管改真源 `.list` 重生成；第三方换源或加 `no-resolve` | 本地静态门禁**看不见**，必须拉下来数 |
| ③′ IPv6 | 顶层 `ipv6: false` **+** `dns.ipv6: false` | ⭐ **两个都要**，只关一个留残余通路（§6.4）|

#### 7.1 面④ / 面⑤ 修完的必跑项

```
1. 国内网站是否仍直连（不绕代理）  ← 补 no-resolve 后最容易翻车的一条
2. 境外网站是否仍走代理
3. 游戏机 NAT 检测是否正常（fake-ip 下 STUN 类要走 fake-ip-filter）
```

✅ 本仓 **mihomo 侧已有分流覆盖审计脚本**（闸门 #9）⇒ 第 1、2 条可先跑它；⚠️ 但它的**离线档按规则集名推演**，不读实际策略（见 §4.4.1），所以仍需实测兜底 —— 别把它当充分条件。
这是与姊妹仓的已知差距（Surge 侧有 `audit_routing_coverage.py`，43 条判据）。

#### 8 · 验证修好了

```
1. 冷启动抓包（§3.4 的 5 步）→ 应无业务域名的明文 :53
                              （端点域名那两条是面①，属可接受取舍）
2. python self-conf-skills/gates/clash/check_structure.py        → exit 0（含面③′ 两条）
3. python self-conf-skills/gates/check_min_pair.py         → exit 0
4. python self-conf-skills/gates/clash/check_script_sync.py      → exit 0
5. python self-conf-skills/run/clash/build_rules.py --check   → exit 0
6. python self-conf-skills/gates/clash/check_remote_urls.py      → exit 0（慢，按需）
7. python self-conf-skills/gates/verify_all.py                   → exit 0（全套闸门）
8. leak test 网站复测 → 不再显示运营商 DNS
9. 实测：国内直连；游戏机 NAT 正常；IPv6 侧不再露真实地址
```

⚠️ 第 8 步的解读见「leak test 结果的解读」—— **显示节点出口城市不是泄露**；
显示 `198.18.x.x` 也不是泄露（那是 fake-ip，说明被接住了）。

#### 9 · 结论：五类必须全堵

#### 9.1 归并口径回顾

| # | 触发者 | 面 | 本仓状态 |
|:-:|:-------|:---|:---------|
| ① | 引导链 | 冷启动必解析一次端点域名 | ⚠️ 必然（取舍）|
| ② | 回退链 | 落明文 ⇒ 业务域名明文 | ✅ 收口 |
| ③ | 旁路设备 | 直发 `:53` | ✅ 收口（`any:53`）|
| ④ | 规则判定 | IP 类缺 `no-resolve` | ⚠️ `routing` 3 条缺 |
| ⑤ | 远程集 | 内嵌裸 IP 条目 | ⚠️ 需拉下来数 |
| ③′ | IPv6 | AAAA + 真实 IPv6 绕过 TUN | ✅ 收口（双 false）|

> 🔴 **五类必须全堵，堵四类剩一类仍是必然通路。**
>
> 这不是修辞。每一类都是**一条独立的、端到端可达的**明文通路：
> - 堵了 ②③④⑤，但 `dns.ipv6: true` ⇒ 双栈站点**必然**走真实 IPv6 出网（面③′）；
> - 堵了 ③④⑤③′，但 `fallback` 写明文 ⇒ 每次 geoip 判定命中就**必然**明文查一次（面②）；
> - 堵了 ②④⑤③′，但旁路设备直发 `:53` ⇒ 那些设备**必然**用运营商 DNS（面③）。
>
> **"堵了大部分"没有意义** —— 泄露是**或**关系，不是**且**关系：
> 任何一条通路存在，查询就会从那条路出去，而且**必然会被走到**
> （只要触发条件出现：冷启动 / 判定命中 / 设备开机 / 访问双栈站点）。
>
> 唯一的例外是面①：它是**机制上不可能消除**的引导查询，
> 只能靠"限定它只解析端点自己的域名"把代价压到最小。
> 所以严格说是**五类必须全堵 + 一类必须接受并收窄**。

#### 9.2 由此得到的一条判断标准

> **判断一条通路是否必须消除的标准只有一条：它是否"必然会被走到"。**
>
> 一次性、可控、且能说清收益的通路（面① 的引导查询），不算必须消除的泄露面；
> 有明确触发条件、且会反复发生的通路（其余五类），**必须堵**。

#### 9.3 ⚠️ 本仓 mihomo 侧的一个结构性缺口

把 §4.6 的结论再说一遍，因为它影响上面所有的"已收口"判断：

> **六个面里只有面③′ 有门禁。** 现有四道 clash 门禁守的是
> 结构 / 两形态一致 / 脚本静态一致 / 生成物新鲜度 —— **没有一道是防泄露语义审计器**。
>
> ⇒ 上表里 ② ③ 的「✅ 收口」是**当前文件的状态**，不是**被机器守住的状态**。
> 哪天有人把 `dns-hijack` 删掉、或把 `fallback` 改成明文解析器，
> **全套门禁会全绿**。
>
> ⇒ 参照姊妹仓：Surge 侧有 `check_surge_dns.py`（12 项判据）、
> Egern 侧有 `check_egern_dns.py` + `audit_ruleset_noresolve.py`。
> **mihomo 侧缺这一层** —— 这是整合后最值得补的一块。

#### 10 · 边界：什么情况不该"修"

不是所有明文 `:53` 都必须消除。以下属**可接受的取舍**，纠结它们是浪费：

| 情况 | 为什么可接受 |
|:-----|:-------------|
| **引导解析**（`default-nameserver` 解析 DoH 端点域名）| 机制上不可能消除。本仓已把它限定为"只解析端点自己的域名"，实测确认过（§4.1）|
| 设备用 DoH 直连（不经 mihomo）| DoH 本身加密，不算明文泄露。除非你要统一管控 |
| 企业内网 DNS（`192.168.x.1:53`）| 那是本地网络的一部分，不是"泄露到运营商" |
| `dns-hijack` 没穷举全部解析器 | `:53` 地址空间无限，列不全。用 `any:53` 才是正解 |
| 自建 DNS 服务器上的明文查询 | 那是你自己控制的链路，不是第三方 |
| 见到 `198.18.x.x` | **不是泄露** —— 是 fake-ip，说明查询被 mihomo 接住了 |

> 📌 判断标准始终是同一条：**这条明文通路是否"必然会被走到"？**
> 一次性、可控、且能说清收益的通路，不算必须消除的泄露面。

---

#### 11 · FAQ

**Q：leak test 显示运营商 DNS，但我的 `nameserver` 全是 `https://`，怎么会漏？**

大概率是面①（冷启动引导）或面③（旁路设备）。
先按 §3.4 从冷启动抓一遍；若明文来自**别的设备**的源地址 ⇒ 面③。
另外确认 `default-nameserver` 那层是明文 —— 它**必然**走 `:53`。

**Q：`198.18.x.x` 是不是泄露？**

**不是。** 那是 `fake-ip-range: 198.18.0.1/16`，
mihomo 的 fake-ip 模式先返回假 IP、等连接建立时再按域名分流。
**见到它恰恰说明查询被 mihomo 接住了。**

**Q：我关了 `dns.ipv6`，为什么还会有 IPv6 泄露？**

两个开关要**一起关**。只关 `dns.ipv6` 时，应用拿不到 AAAA，
但顶层 `ipv6: false` 若没写，IPv6 流量侧的行为不明确；
反过来只关顶层而 `dns.ipv6: true` ⇒ 应用拿着 AAAA 直连出去 ——
**这正是曾经记过的那个 bug**。见 §6.4。

**Q：`ipv6: false` 是默认值，为什么门禁要求必须写？**

判据用 `is not False` ⇒ **键缺失也算不过**。理由是对齐面纪律：
显式声明键不适用"默认值就不写"，让四份 profile 对拍**看文件即知**，
不用去查各内核默认值。Surge / Egern 侧同一条纪律。

**Q：`routing` 版有 3 条 IP 规则缺 `no-resolve`，要补吗？**

先看顺序再决定。`routing` 的 `cn`（域名集）排在 `geoip-cn`（IP 集）**之前**
⇒ 多数国内域名已被 `cn` 接住，缺 `no-resolve` 的代价只是"漏网的多解析一次"。
补是安全的（准入条件满足），但**补完必须实测国内是否仍直连** ——
本仓已有 mihomo 侧的分流覆盖脚本（闸门 #9），但离线档只按规则集名推演，不能替代实测。见 §4.4.1。

**Q：为什么 `emby` / `AI_Domains` / `apple-system` 不写 `no-resolve`？**

它们是 `build_rules.py` 从 `.list` 生成的**纯域名集**（`grep -cE '^(IP-CIDR|...)' rules/*.list`
实测均为 0），生成物头部注释写明「零 IP 条目 ⇒ 引用方不写规则级 no-resolve」。
**写了反而有害** —— 会关掉域名匹配（刀刃二）。见 §4.5。

**Q：门禁全绿，是不是就没泄露了？**

**不是。** 六个面里只有一个（面③′）有门禁守。
现有四道 clash 门禁守的是结构 / 两形态一致 / 脚本静态一致 / 生成物新鲜度，
**没有防泄露语义审计器**。见 §4.6 与 §9.3。泄露面必须靠机制推导 + 抓包实测。

**Q：旁路设备的 DoH 怎么办？**

`dns-hijack` 只劫持 `:53`，**拦不住 443 上的 DoH**。
那条路本身是加密的，不算明文泄露；要统一管控只能在网络层拦 DoH 端点。
属"要统一管控"的目标，不是"防泄露"的目标。

**Q：改完 DNS 段，为什么 `check_min_pair.py` 红了？**

DNS 段在四份 profile（`.yaml` / `.min.yaml` × `lazy` / `routing`）里必须完全一致。
只改完整版 ⇒ 立刻判负。同步 `.min` 时**没有生成器可用**
（`make_min.py` 只管 surge / egern 两族）—— 用 `yaml.safe_load` + `yaml.safe_dump`
重出一份纯配置再比对最省事，别逐行手改。见 [`gates.md`](./gates.md) §5.1。
