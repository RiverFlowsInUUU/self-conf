# Egern · 逐段语义与加固


## Egern · 逐段语义（egern 侧）

> **何时读**：改 Egern 配置需要确认某个顶层字段 / 组 / 规则的语义与边界时。本文件原为 `egern/DetailsReadme/DetailsReadme.md`，2026-09-27 起并入 skill。

> **这份文档的定位**：`README.md` 只保留了「配置框架 + DNS 防泄漏」的精华，有意省略了大量推导、数据、谱系与工程方法。
> 本文档是 README 的**详版 / 补集**——把那些被省略的信息全部展开、讲清楚。
>
> **隐私声明**：本文档**不包含任何私人信息**。本仓库的模板本身是脱敏模板（节点只有 2 条连不上任何真实主机的占位、图标已整合进本仓库、订阅地址与 token 都是占位符、无证书）。
> 下文凡涉及「真实配置」之处，一律用抽象表述，不出现任何具体节点域名、订阅链接、证书串或个人凭据。
> 文中提到的图标来源（公开 GitHub 仓库）仅作**署名归属**，它们已被下载整合进本仓库的 `icons/`，模板不再跨项目引用。

### 0. 目录

1. [配置框架逐段详解](#1-配置框架逐段详解)
2. [防泄露原理：从机制到推导](#2-防泄露原理从机制到推导)
3. [版本谱系 f1–f10（完整）](#3-版本谱系-f1f10完整)
4. [审计清单（18 项）](#4-审计清单18-项)
5. [规则集开销实测](#5-规则集开销实测)
6. [已知代价与取舍](#6-已知代价与取舍)
7. [隐私与脱敏](#7-隐私与脱敏)
8. [提炼的 Skill / 方法论](#8-提炼的-skill--方法论)
9. [如何自行审计](#9-如何自行审计)
10. [常见问题（扩展版）](#10-常见问题扩展版)

### 1. 配置框架逐段详解

#### 1.1 顶层结构总览

模板由 12 个顶层段组成，按职责分三类：

**A. 全局开关 / 辅助项**
- `vif_only` —— 是否仅走虚拟接口。
- `hijack_dns` —— DNS 劫持开关，**接管本地 `:53` 并返回 Fake IP**，是防泄露的第一道闸门（缺失时 App 自带 DoH 仍能绕过）。
- `geoip_db_url` / `asn_db_url` —— `geoip` / `asn` 规则依赖的地理库（远程 `.mmdb`，非图标，保留原引用）。
- `proxy_latency_test_url` / `direct_latency_test_url` —— 延迟测试的 HTTP 端点（决定测速走代理还是直连）。
- `real_ip_domains` —— 不做 Fake IP 映射的域名白名单（APNs / 内网发现走的是「隧道外」链路，用 Fake IP 会异常）。
- `default_proxy_group` —— **添加代理时自动加入的策略组名称**（官方：*Policy group to automatically add
  proxies to*，默认值为空；本模板写 `Proxy`）。⚠️ 它与兜底**无关** —— 未命中任何规则时走的是 `rules`
  最后那条 `default`（见 1.4）。它的用处是：你手动加一个节点，Egern 自动把它放进这个组，不用回来编辑
  `policy_groups` —— 懒人版 `Proxy` 只有 `Airport`（隐藏订阅槽）一项，手动添加的节点正靠这一行接进来。

**B. 核心三段**
- `proxies` —— 节点定义（**分流版为空，节点全来自订阅**；懒人版带占位节点，见 1.2）。
- `policy_groups` —— 分流组（见 1.3）。
- `rules` —— 匹配表（见 1.4）。

**C. DNS**
- `dns` —— 双 DNS 模型核心（见 1.5）。

#### 1.2 `proxies` —— 分流版为空，节点全来自订阅

**分流版 `egern/profiles/routing.yaml` 的 `proxies` 段不写死任何节点** —— 全部来自
`Airport` 订阅。占位节点 `Node-A` / `Node-B` 于 2026-10-06 移除：它们让人以为必须
手工补两条本机节点，而实际上只填订阅即可。（懒人版 `lazy.yaml` 仍带占位节点。）

Egern 的 `proxies` 只描述节点本身（`server` 可为 IP 或域名、协议名决定类型、`auth` / `sni` 等凭据）。
要加自己的节点（自建 / 中转链 / 本地入口）就写在这里；写成 IP 字面量可省掉一次解析。

#### 1.3 `policy_groups` —— 四种类型、组间引用、图标

Egern 的分流组**按类型做键**，而不是平铺的 `name` 字段。一个组的典型形态是 `{select: {name: X, policies: [...], icon: ...}}`。四种类型：

| 类型 | 作用 | 模板里的例子 |
|---|---|---|
| `select` | 手动选路 | `Proxy` / 各类 App 组（`Final` 组 2026-10-05 已删） |
| `smart` | 智能选优：组内多轮测速，按延迟 / 抖动 / 可靠性综合打分自动选最稳节点 | `Hong Kong` / `Taiwan` / `Japan`（这些地区组另配 `filter` 正则从订阅里筛节点 —— 归类是 `filter` 的职责，不是 `smart` 的） |
| `fallback` | 故障转移：按 `policies` 顺序依次尝试，选第一个可用的节点 | 现版模板无 `fallback` 组（`ChatGPT` / `Gemini` 至 `routing_v2.4` 为该类型，`routing_v3` 起为 `select`） |
| `external` | 从订阅 URL 拉取节点 | 模板里是 `sub.example.com?token=REPLACE_WITH_YOUR_TOKEN` 占位 |

要点：
- **组与组之间可以互相引用**（例如 `Google` 的成员是 `Gemini`，App 组引用 `Proxy`）。这种引用关系保留，是模板的正常结构。
- **`routing_v2.3` 起已无空组**：`ChatGPT` / `Gemini` 曾是 `policies: []` 的空组，而规则直接指向它们
  ⇒ **导入即静默断流**；现已填成 `[Proxy]` + `flatten: true`（`flatten` 在这里起什么作用，
  见下方「组清单与要点」起的逐段讲解）。
- **图标**：模板用到的全部策略组图标（条数现抓：`ls icons/*.png | wc -l`）（整合自 RiverFlowsInUUU/Rule、jnlaoshu/MySelf、Koolson/Qure 三个公开仓库）已统一下载进本仓库 `icons/`，全部以 `https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/<file>` 形式引用，**不再跨项目引用任何图标地址**。

##### 组清单与要点（现役）

**节点来源**（1 个订阅槽位）：`Airport`（`external` · `type: smart` · `urls` 一条 + 一条 `urls_disabled` 示例 · `hidden: true`）。
`routing_v2.1` 及更早为 4 个槽位（多出 `Airport-C` / `Airport-Free`）—— `routing_v2.2` 精简掉，选路能力不变。

**`flatten: true`** —— 把子策略组**展开成全部具体节点**，而不是当成一个「组」单位。
以 `Smart` 为例（`policies: [Airport]`）：不加时候选是「`Airport` 组」这一个单位（两级选优），
加上后才是订阅里的**全部具体节点**（一级选优）。官方「通用字段」明确它在
`select` / `auto_test` / `smart` / `fallback` / `load_balance` 五种基础类型上通用。
本模板的 `Smart` / `ChatGPT` / `Gemini` 与全部地区组都用了它。

**`ChatGPT` / `Gemini` 为什么必须配 `flatten`** —— 它们现为 `select`（`routing_v3` 前是 `fallback`，语义**按顺序取第一个可用**）。
不加 `flatten` 时候选只有「`Proxy`」这一个组单位（`select` 下面板不能逐节点手选；旧版 `fallback` 下等于没有故障转移），且 `Proxy` 一挂整组就断；
加上后 `Proxy` 展开成全部具体节点，面板可直接逐节点选（旧版 `fallback` 则是在节点级依次尝试）
⇒ 效果是应用组拿到**节点级候选**，与 Surge `select, include-other-group="Proxy"` 的节点平铺同形。

**低倍率优先（原 `MAX` 组，v4.0.2 并入）** —— 不再单设 `MAX` 组，改为在**所有 smart 组**
（`Smart` + 6 个地区组）上写 `priorities: {"(?<![\d.])0\.\d*[1-9]": 0.15}`：
低倍率节点比当前最优节点**慢 6.7 倍以内**（= 1 ÷ 0.15）仍然胜出，超出或不可用则自动让位给池内其它节点。
与 Surge 的 `policy-priority` 同值同正则 —— 调这个口径要两侧 7 个组一起改。

**地区组** —— 「按正则把节点归类」是 **`filter`** 干的，不是 `smart` 本身；
`smart` 只负责在筛出来的节点里选最优。`Other Regions` 的负向断言把其余 5 个地区组的
关键词**逐字抄了一遍** —— 改任何一组的关键词都要同步改它，
用 [`skill/scripts/egern/audit_region_filters.py`](../../scripts/egern/audit_region_filters.py) 校验（漏改会被它拦下）。

**服务组**（默认策略与承接的规则集）见 [`shared/rulesets.md`](../rulesets.md)。

**`lazy` 的一处专属调整**（只属于它，不同步其他版本）：`AD` 组**只有 `REJECT`**（没有 `DIRECT` 兜底）。
⚠️ **两版的兜底写法现已完全一致**（2026-10-05 起）：`default` 规则的 `policy` 都**直写 `Proxy`**，
中间不挂 `Final` 组（`Final` 不是 Egern 的内置关键字，内置只有 `DIRECT` / `REJECT`，那一层组本就可选）。
`name: Final` 保留为**日志标签**，便于历代日志读通。

#### 1.4 `rules` —— 匹配表与直连规则集

`rules` 是「什么流量走哪里」的总指挥。支持的规则类型：

- `domain_suffix` / `domain` / `domain_keyword` —— 域名类（会触发解析，除非被后面的 `no_resolve` 逻辑约束）。
- `ip_cidr` / `ip_cidr6` / `asn` —— IP 类（**必须带 `no_resolve`**，见 2.3）。
- `rule_set` —— 引用远程 / 本地规则集文件（其内部的 IP 条目也必须带 `no-resolve`）。
- `geoip` —— 按 IP 地理归属（`no_resolve: true` 时只对「已经是 IP」的连接生效）。
- `default` —— 兜底策略。

**直连三件套**（决定国内流量不走代理）：
1. `Lan.list` —— 局域网。
2. `apple.txt` —— Apple **在中国大陆可直连**的域名（纯域名、零 IP，Loyalsoldier `surge-rules`，与 `direct.txt` 同仓库同 release；条数随上游更新，不写死）。零 IP ⇒ 无需 `no_resolve`。2026-10-04 起由 `Apple_All_No_Resolve.list` 换入。
3. **国内域名规则集（Loyalsoldier `direct.txt`）** —— **纯域名**规则集，零 IP 条目（十几万条；上游每周更新，条数一律现抓、不写死），是「国内域名直连」的主力。纯域名规则只做字符串匹配、不触发解析，因此无需 `no_resolve`；「已经是 IP 的连接」由下方 `geoip: CN` 兜住。
> （历史上这里还有一条 `domain_suffix: cn` —— 把整个 `.cn` TLD 再钉一次，**不依赖规则集是否加载成功**；
> 2026-09-24 起分流版与懒人版都不再需要：`direct.txt` 本身含 `DOMAIN-SUFFIX,cn`。）
> 另有一条本仓自托管的 `apple_system.list` —— **位 ③**的系统域名集（2026-10-06 起不再置顶，
> 落在两条广告拦截之后、内网之前），补 Egern 没有内置 `SYSTEM` 的缺口。
> ⚠️ 懒人版**不设 `Apple Update` 组**（仅分流版有）：OTA 域名在懒人版由本集合接成 `DIRECT`。
> （`direct.txt` 已覆盖绝大多数国内域名）。它与上面 3 条规则集合起来，构成 `rules` 的全部直连来源。

**规则的实际匹配顺序**（`rules` 按声明顺序求值，第一条命中即决定去向）：

> 广告白名单 → 广告拦截（`Jinx` + `AWAvenue`）→ 系统域（`apple_system`）
> → 内网（`Lan` + `private`）→ 应用（13 条）→ Apple（`apple.txt`）→ 国内域名 → 国内 IP（`geoip: CN`）→ 兜底（`default`）
>
> ⚠️ 上表为**分流版**；懒人版段序相同但**不含 `SystemOTA`**（`Apple Update` 组仅分流版有），
> 共 11 条规则。

`rules` 里**没有任何 `disabled` 条目**：原 `Proxy.list` 那条自 `routing_v3.2` 起改成**纯注释**、不再占规则位；内联 `domain_suffix: cn` 同期删除（`direct.txt` 已含 `DOMAIN-SUFFIX,cn`）。

**默认出口链**：未命中任何规则集的域名 → `default` 规则（`policy: Proxy`，2026-10-05 起直写、不再挂 `Final` 组）→ 走代理。这类流量由**节点远程解析**，不经过本地 `dns:` 段，日志里表现为 `default → Final → Proxy`（`Final` 是 `name` 日志标签）。

> ⚠️ 关键绑定：`geoip: CN`（`no_resolve: true`）**只对已经是 IP 的连接生效**，国内域名的直连**完全依赖那个纯域名国内规则集（`direct.txt`）**。两者绑定，动一条必须看另一条（详见 2.3 / 清单 17）。

#### 1.5 `dns` —— 双 DNS 模型核心

`dns` 段是本模板防泄露的中枢，由四个子段组成：

| 子段 | 作用 | 本模板取值 |
|---|---|---|
| `upstreams` | 默认 DNS 的解析器组 | 仅 `Domestic-DNS`（**4 个**国内加密端点 = 2 机构 × 2 协议，全为 IP 字面量） |
| `bootstrap` | 默认 DNS 的回退（明文 `:53`） | **2 个**国内公共 DNS 的 IP（阿里 + 腾讯），**不含 `system`** |
| `proxy_nameservers` | 代理 DNS（解析节点 `server` 里的域名），**硬覆盖** | **4 个**国内加密端点，与 `upstreams` 一致 |
| `forward` | 默认 DNS 按域名选上游 | **4 条**：白名单 → 两条广告 `reject` → catch-all 兜底（见 2.4） |

另有 `hijack_dns`（接管 `:53` 返回 Fake IP）。

> 关于 `Foreign-DNS` 组：迭代 f10 起它就无任何引用（forward 兜底改国内组后不再需要境外组）；`routing_v1` 里它被**整组注释**保留作 A/B 备用，**`routing_v2` 起整段删除**。想恢复境外解析答案，需自行在 `upstreams` 里加回该组、并把 `forward` 兜底的 `value` 改过去 —— 但要注意「先有代理才敢解析」的启动期明文风险。详见第 6 节。

#### 1.6 `rule_sets` 与 `no_resolve` 要求

模板通过 `rules` 里的 `rule_set` 引用远程规则集（blackmatrix7 / ACL4SSR / Qure 等公开仓库）。**致命点**：缺陷常藏在别人仓库的 `.list` 文件里——若其中存在「不带 `no-resolve` 的 IP 类条目」，profile 写得再干净也看不见（见清单 16）。因此所有被启用的规则集文件，其 IP 条目必须带 `no-resolve`，并用 `audit_ruleset_noresolve.py` 逐个下载核对。

### 2. 防泄露原理：从机制到推导

#### 2.1 双 DNS 模型

理解整份配置只需记住一个事实：**Egern 有两套 DNS**。

1. **默认 DNS** —— 处理业务流量的域名解析。按 `dns.forward` 匹配上游，未命中则回退到 `dns.bootstrap`。
2. **代理 DNS**（`dns.proxy_nameservers`）—— 只负责解析「节点 `server` 里的域名」，且强制在**直连侧**完成（代理还没通，不可能让代理去解析自己的地址）。它一旦设置，就**绕过 `forward`**。

**泄露只会发生在一条路径上：明文 `UDP:53` 的 `bootstrap`。** 一切加固都围绕「让 bootstrap 无事可做」展开。

#### 2.2 `bootstrap` 的两条用途与如何消灭

`bootstrap`（明文 `:53`）会被触发当且仅当：
- **用途①**：某个加密 DNS 端点本身是用**主机名**写的（如 `https://dns.google/dns-query`），Egern 得先用系统 DNS 把它解析成 IP ⇒ 暴露。
- **用途②**：`forward` 没有接住某个域名，默认 DNS 回退到 `bootstrap` ⇒ 暴露，且一旦本地递归失败还会掉到「系统 DNS」（运营商）。

消灭方式：
- 用途① → 所有端点写 **IP 字面量**（2.3 原则①）。
- 用途② → `forward` 必须有一条「直连可达」的兜底（2.3 原则③ / 清单 4）。

> ⚠️ **`bootstrap` 唯一安全的形态是「永远不被触发」。** 它本质是明文 UDP:53，在运营商线路上无论指向哪个 IP 都可能被接管或失败。所以「换一个更好的 bootstrap IP」是错误思路——本模板的做法是把前两条做到位，让它根本不被用到（清单 5）。

#### 2.3 三条原则详述

**① 端点全部写成 IP 字面量**
`dns.upstreams` 与 `dns.proxy_nameservers` 里**不出现任何主机名**。没有需要解析的目标 ⇒ 用途①被直接消灭（清单 1）。

**② `no_resolve` 成对出现（这是「用解析换分流」的开关）**
所有 IP 类规则（`geoip` / `ip_cidr` / `ip_cidr6` / `asn`）都带 `no_resolve`，它们只匹配「已经是 IP」的连接，不再触发任何域名解析。需要靠域名判定归属的国内直连，由**纯域名的国内规则集**（Loyalsoldier `direct.txt`，11 万条）承接——域名规则只做字符串匹配、不触发解析，故无需 `no_resolve`。两者绑定，缺一不可（清单 5 / 17）。

> `no_resolve` 有三个层级，别混：
> - **规则级**：写在 `rules:` 里的 `geoip/ip_cidr/...`，官方明说只适用这四类；写在 `rule_set` 规则上**不生效**。
> - **规则集文件顶层**：Egern 原生 YAML 规则集里的 `no_resolve: true`，影响整文件。
> - **规则集条目级**：Surge `.list` 里的 `IP-CIDR,x/y,no-resolve`——第三方 `.list` 走这一层，也是缺陷最常藏身之处（清单 16）。

**③ `forward`：白名单 → 广告 `reject` → catch-all（`routing_v2.4` 及更早只有一条 catch-all）**
```yaml
forward:
  - proxy_rule_set: <surge-direct.list>       value: Domestic-DNS   # 白名单先拿到解析
  - proxy_rule_set: <surge-ads.list>          value: reject         # 广告：解析阶段拒答
  - proxy_rule_set: <AWAvenue…-RULE-SET.list> value: reject
  - domain_wildcard: '*'                      value: Domestic-DNS   # 兜底
```
> **`routing_v3` 起扩为 4 条**（2026-09-23，对齐 Surge 的 `pre-matching` 拦截）：
> 官方 `value` 字段规定特殊值 **`reject` ——「refuse the query and return an empty response」**，
> 命中即在**解析阶段**拒答，连接根本不会发起，效果等价 Surge 的 `pre-matching REJECT`。
> ⚠️ 顺序是命门：**白名单必须排在两条广告清单之前**（AWAvenue 会命中白名单里 10 条功能域，
> 如 `jpush.cn` / `apd-pcdnwx*` / `tnc3-*`），否则白名单域名连解析都拿不到。
> `routing_v1` 里是两条（`domain_regex: '.'` + `domain_wildcard: '*'`）；`routing_v2.1` 删掉了 `domain_regex` ——
> 它与 `domain_wildcard` 语义完全重叠（任何域名两条都命中、`value` 又相同），
> 按官方「第一条命中即决定上游」，第二条永远不会被求值。详见 2.4。

#### 2.4 `forward` 的设计判据（两个反直觉事实）

决定「不必在 forward 里列举任何节点 / 订阅域名」的两层原因：
- 配了 `proxy_nameservers` 后，**代理 DNS 会跳过 forward** —— 节点域名根本不走这里（清单 2b）。
- 兜底 `value` 为**单值**时，**规则顺序与域名清单都不影响结果**（官方：「规则按声明顺序求值，第一条命中决定上游」；但所有兜底都指向同一个组，顺序无意义）。

**`routing_v3` 起判据补一条**：`reject` 是**终止动作**（拒答、不产生解析），
因此它与兜底组可以并存而不破坏上述性质 —— 真正要保证的是
**「所有非 `reject` 规则的去向都等于兜底组」**（`audit_dns_forward.py` 已按此扩展，2026-09-23）。

⇒ 于是 forward 与订阅**彻底解耦**：你换十个订阅，这里一行都不用改。

#### 2.5 兜底组安全性 vs 列举域名（核心设计原则）

> **防泄露由「兜底组本身是否直连可达」承担，不由「在 forward 里罗列域名」承担。**

判据：删掉一条 forward 规则，结果会变吗？会引入维护耦合吗？两个反直觉事实（2.4）说明：在 `value` 单值 + 代理 DNS 跳过 forward 的前提下，列举节点域名 / 延迟测试域名 / 图标域名 / `.cn` / 国内域名表都是**死代码或冗余**。因此模板只留兜底，把节点域名、订阅耦合全部剥离。这一手同时消灭了「换订阅导致 forward 配置失效」的风险（清单 18）。

### 3. 版本谱系 f1–f10（完整）

> 以下每版描述均为**机制层面**的演进，不涉及任何具体节点域名或私人配置。验收数据来自实际真机测试。

| 版本 | 改动 | 结果 |
|---|---|---|
| **f1** | 第一版加固 | ❌ 私自加了 `proxy_nameservers`，把代理侧解析钉死在国内 → 泄露从「偶发」变「确定」 |
| **f2** | 端点改 IP 字面量 + DNS 端点显式路由 + 加 `block_ips` | ❌ `proxy_nameservers` 仍在，问题未解 |
| **f3** | 删 `proxy_nameservers`；显式覆盖节点域名；forward 双兜底 | ✅ 修掉节点域名明文解析 ⚠️ 漏了 latency 测试域名 |
| **f4** | 补 profile 自身必需解析（两个延迟测试域名 + jsdelivr）→ 国内组 | ✅ 修掉「每轮测速触发一次」的持续泄露 |
| **f5** | `upstreams` 全部改 IP 字面量 + `bootstrap` 扩到 3 个国内 IP | ✅ 消灭 bootstrap 用途① |
| **f6** | forward 两条兜底的 value：境外组 → 国内组 | ✅ 消灭 bootstrap 用途②（兜底不再依赖代理） |
| **f7** | ① `Apple_All.list` → `Apple_All_No_Resolve.list`；② 显式写 `proxy_nameservers`；③ 给 `geoip: CN` 补 `no_resolve` | ✅ 泄露治好（第③条是真正答案）<br>❌ **但同一手把国内域名的直连路径一起关掉了** |
| **f8** | **只改一条**：`ChinaMax.list` → `ChinaMax_All_No_Resolve.list`（补齐国内域名直连） | ✅ **泄露与分流同时成立 —— 真机验收通过** |
| **f9** | 删除整个顶层 `mitm` 段（`ca_p12` + `ca_passphrase`） | ✅ 用户主动要求「暂时不用 HTTPS 解密」；纯删除，不触碰 DNS / 分流任何一行；证书串零残留 |
| **f10** | `dns.forward` 由 10 条塌缩为 2 条兜底（删 8 条结构性冗余 + 2 处死引用） | ✅ 与订阅 / 节点域名解耦；审计通过，订阅耦合 4 → 0 |

#### 每一版的验证结果

> ⚠️ **读数说明（很重要）**：下表的所有数字都是**作者的「自用配置」**跑出来的 ——
> 它带真实节点、且 **f2–f9** 时期 `rules` 里还有 DNS 端点路由规则（f2 引入 15 条、f10 删段 A ⇒ 「f1 起」与「止于 f8」两头都不准）。
> **本仓库发布的是一份脱敏模板**（订阅是占位 URL、f10 已删段 A 路由），
> 它的审计读数**与下表不同**，且**从未声称全绿**。两者的差异见本节末尾「发布模板的审计读数」。

| 版本 | `check_egern_dns.py` | `audit_ruleset_noresolve.py` | `audit_routing_coverage.py` |
|---|---|---|---|
| f6 | 0 high / 3 low / 43 ok | ❌ **HIGH** | 未覆盖 |
| f7 | 0 high / 3 low / 43 ok | ✅ OK (20/20) | ❌ **7/15 国内探针落 Final** |
| **f8** | **0 high / 3 low / 43 ok** | ✅ **OK (20/20)** | ✅ **15/15 DIRECT** |

> f7 那一行是本项目最重要的一张表：**两个脚本双双全绿，配置却不可用。**

#### 发布模板的审计读数（与上表不同）

发布模板**不是**自用配置，读数独立：

| 脚本 | 发布模板读数 | 说明 |
|---|---|---|
| `check_egern_dns.py` | ✅ **0 high / 2 low / 24 ok（退出码 0）** | 见下方「f3.1 判据修正」；24 这个数对应 `routing_v2` 起的全部版本（`routing_v1` 是 30 ok。`routing_v2` 时代两版 `rules` 均为 24 条、都不含 DNS 端点路由规则 ⇒ 6 项差在**逐端点**：`routing_v1` 多 `223.6.6.6` / `1.12.12.12` 两个国内端点，各计一条 `upstreams` 与一条 `proxy_nameservers` 的「IP 字面量」OK（+4）、再各计一条判据 B 的「直连可达」（+2）。⚠️ 现役 `rules` 为 24 条（2026-10-04 删去 `WeChat` 前为 25 条），规则集引用不落 DNS 判据，ok 计数仍恒 24。原见 `docs/07-文件版本沿革.md`，该文件已随仓库精简移除） |
| `audit_routing_coverage.py` | ✅ 15/15 国内探针 `DIRECT` | 分流正确性不受脱敏影响 |
| `audit_dns_forward.py --drill` | ✅ 通过（退出码 0） | `forward` value 单值、订阅耦合 0 |
| `audit_region_filters.py` | ✅ 5 个地区组关键词全部同步（退出码 0） | 负向断言与地区组 filter 逐字一致 |
| `audit_ruleset_refresh.py --strict` | ✅ 604800 × 22 条全部钉住（退出码 0） | 唯一会**真的**让规则集停在旧版的写法是非正值 |

**f3.1 判据修正（2026-09-20）** —— 曾有一段时间发布模板**过不了** `check_egern_dns.py`：

- **现象**：3 high / 8 low / 20 ok，退出码 1。
- **根因**：f10 删掉段 A（DNS 端点固定路由）后，脚本 `group_reach` 的判据是
  「端点全为 IP **且至少一个在 `rules` 里判给 `DIRECT`**」，后半句在无段 A 的模板里**永远不成立** ⇒
  兜底组 `Domestic-DNS` 被恒定判为「依赖代理」，连锁触发 3 条 HIGH（兜底组 + 两个延迟测试域名）。
  **这是判据的载体选错，不是配置的问题。**
- **修法**：补**第二判据** —— 端点全为 IP 且**至少一个是国内知名解析器 IP**（内置白名单：
  阿里 `223.5.5.5`/`223.6.6.6`、腾讯 `119.29.29.29`、`1.12.12.12`、`120.53.53.53` …）时同样判「直连可达」。
  此判据在 profile 文本内可验证、且语义等价于「不经代理即可到达」。
- **没有放松防护**：f5 的缺陷仍被拦住 —— **一个全由境外 IP 组成的组依然判 HIGH**
  （境外解析器必须经代理才可达）；含主机名端点的组依然判 HIGH。已用反例做过回归验证。
- **四处同步**：`check_egern_dns.py` 的 `group_reach` + 其国内端点路由检查、
  `audit_dns_forward.py` 的 `direct_ips` 收集 + 结论判定。
- ⭐ **（二次核查后）已消除「两份拷贝」隐患**：上述同步最初靠注释互相提醒，**被证明不可靠** ——
  判据本体同步了、但喂给它的 helper（`ep_ip`）没同步，导致
  `audit_dns_forward.py` 把 `[2400:3200::1]` 截断成 `'[2400:3200:'`，
  **同一份 IPv6 profile 两个脚本给出相反结论**（0/1）。
  现已把 `DOMESTIC_RESOLVER_IPS` / `hostpart` / `ip_literal` 收编到共享模块
  `skill/scripts/egern/_egern_common.py`，两个脚本都从它 import（2026-09-27 现抓：该目录 10 个脚本里已有 8 个 import 它）—— 从结构上消灭拷贝。
  并新增 `skill/tests/egern/run.sh`（阶段 1：5 fixture × 2 脚本）作为**防退化守卫**。
  （⚠️ 沿革记载：这两个守卫在后续整合中已移走/并入 `skill/tests/` 总入口，
  现役仓库里 `skill/tests/egern/` 只剩 `fixtures/`。此处保留原样以存其沿革。）
- ⚠️ **（三次核查后）"收编"这个动作本身又引入了一次回归**：`hostpart` 剥 scheme 从
  「通用剥离」退化成「大小写敏感白名单」，端点写 `HTTPS://223.5.5.5/dns-query` 时
  `HTTPS` 被当成主机名 ⇒ 同一份配置读数从 **0 high 翻成 9 high**。发布模板端点全小写所以没暴露。
  已改回大小写不敏感的通用正则，并新增 `skill/tests/egern/scheme_case.yaml` 守卫。
  **教训：重构式的"等价改写"必须逐输入对拍，测试还绿只说明已覆盖的输入没变。**
- ⚠️ **（三次核查后）"声称已交付"与"实际交付"必须分开核**：当时 README 与 commit message
  都写着"已加上某物"，实际那个文件**从未上传** —— 发布脚本遇到失败会**摘掉该文件继续推**，
  于是"推成功了"和"东西真的在那儿"是两回事。
  **教训：发布后要用 `git ls-files` 核对交付物，而不是相信发布脚本的 commit message。**

> 📌 **诚实声明**：本项目最长的一条教训就是「审计通过 ≠ 配置可用」，反向同样成立 ——
> **审计不通过 ≠ 配置不可用**。上面那次 3 high 就是判据的问题，配置本身（IP 字面量端点 + 单值兜底）
> 一直是对的。这类 false positive 必须当 bug 修掉，否则脚本的退出码就不能当守门判据。

#### 五次「审计通过但实测有问题」

| # | 表现 | 真实原因 | 补上的审计维度 |
|---|---|---|---|
| 1 | f1/f2 脚本报 0 high | 靠加配置压指标（`proxy_nameservers`）掩盖问题 | — |
| 2 | f3 脚本报 0 high | 审计器没看 latency 测试域名这一类 | 清单 15 |
| 3 | f5/f6 脚本报 0 high | 判据不足：`group_ready` 只要求端点全 IP + 至少一个被判路由，没要求那一条是 `DIRECT` | 收紧为 `group_reach` |
| 4 | f6 脚本报 0 high | 审计维度缺失：只看 profile 文本，没看它引用的规则集文件 | `audit_ruleset_noresolve.py`（清单 16） |
| 5 | f7 两个脚本都全绿 | 审计不覆盖分流——治泄露的副作用没人检查 | `audit_routing_coverage.py`（清单 17） |

#### 反向教训：审计**不通过**但配置是对的（f10，2026-09-20）

上面 5 次都是「审计绿了但配置不可用」。第 6 次是**镜像问题**：

| # | 表现 | 真实原因 | 修法 |
|---|---|---|---|
| 6 | f10 删段 A 后，发布模板 `check_egern_dns.py` 报 **3 high**、退出码 1 | **判据的载体过时了** —— `group_reach` 依赖 `rules` 里的 `ip_cidr → DIRECT` 作为「不经代理可达」的证据；f10 把那批规则删掉后证据消失，但配置本身没问题 | 补第二判据「端点全为 IP + 至少一个是国内知名解析器」；**两份拷贝同步改**，并用反例（全境外 IP 组）回归验证防护未被放松 |

**这条要记的是**：判据和被测对象是**同一套假设的两端**。改了配置、必须回跑审计脚本 —— 否则
脚本会开始报 false positive，而**退出码这个守门判据就成了摆设**。改配置的人有责任验另一端。

**固化规则**：任何一次「审计与实测不一致」（**无论哪个方向**），都必须假设「判据本身可能过时」，
先分清是配置错还是判据错，再动手。false positive 与 false negative 一样是 bug。

### 4. 审计清单（18 项）

> 📌 本节是 [`shared/hardening-checklist.md`](../ops.md) 的摘要。**逐条判据与严重度的权威版本以 `shared/hardening-checklist` 为准** —— 要改清单请改那一份，本节跟着同步。

> 全部自动化：`check_egern_dns.py` 覆盖 1–15；`audit_ruleset_noresolve.py` 覆盖 16；`audit_routing_coverage.py` 覆盖 17；`audit_dns_forward.py` 覆盖 18。

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `upstreams` / `proxy_nameservers` 端点是否为 IP 字面量 | 出现主机名端点 → 必被 bootstrap 明文解析一次 | 高（境外）/ 低（国内） |
| 2 | 节点 `server` 是域名时，`forward` 是否接住 | 没接住 → 节点域名明文暴露 | 高 |
| 2b | `proxy_nameservers` 是否存在 | 它是**硬覆盖**：一设就跳过 `forward`、强制直连。**两种写法都成立，但必须二选一、不要叠加** —— ① **不设置**（代理 DNS 与默认 DNS 共用 `forward`，靠兜底接住节点域名）；② **设置**（把「未命中 → 回退 `bootstrap`」这条分支从结构上消掉，且强制直连 ⇒ 不依赖代理就绪）。**本模板采用 ②** | 中 |
| 3 | DNS 端点是否全为 IP 字面量（无需在 `rules` 钉路由） | 主机名端点才需在 `rules` 显式路由（否则落 `default` 错判出口）；**本模板全部 IP 字面量，故 `rules` 中已无 DNS 端点路由规则**，此条由清单 1 覆盖 | 高（仅在你自己改用主机名端点时适用） |
| 4 | `forward` 是否有「直连可达」兜底 | 兜底组端点全为 IP 字面量 + 满足**判据 A 或判据 B**：**A** 至少一个在 `rules` 里被判给 `DIRECT`；**B** 至少一个是**国内知名解析器 IP**（`223.5.5.5` / `223.6.6.6` / `119.29.29.29` / `1.12.12.12` / `120.53.53.53` …）—— **本模板走判据 B**。写法要认全：`domain_wildcard:'*'` **和** `domain_regex:'.'` 都算兜底 | 高 |
| 5 | `geoip`/`ip_cidr`/`ip_cidr6`/`asn` 是否带 `no_resolve` | 不加则触发解析 | 高 |
| 6 | 规则引用的策略名能否解析 | 笔误（如「负载均衡」）会成死规则 | 高 |
| 7 | 硬编码 DoH IP 是否有启用规则 → 代理 | `hijack_dns` 只覆盖 `:53`，App 自带 DoH on `:443` 会绕过 | 中 |
| 8 | `rule_set.match` 是否为 URL / 文件路径 | 写成名字 → 无法加载，等同死规则 | 中 |
| 9 | `block_ips` | 未设 → 污染应答照单全收 | 低 |
| 10 | `real_ip_domains` | 为空 → 走不到隧道的流量也拿 Fake IP | 低 |
| 11 | `ipv6` | `true` → AAAA 可绕过 IPv4 侧封堵 | 中 |
| 12 | `hijack_dns` 是否覆盖全部 | 官方示例值 `['*']` | 高（缺失时） |
| 13 | `public_ip_lookup_url` | 不配置才不发 ECS | 配了才是问题 |
| 14 | `skip_tls_verify` | 应为未设置 / `false` | 低 |
| 15 | profile 自身必需解析（两个 latency test URL + 策略组 icon 域名）是否被兜底之前接住 | 没接住 → 直连侧解析失败回退明文 = 运营商；延迟测试端点 = 高（持续泄露），图标 = 低（可不动） | 高 |
| 16 | ⭐⭐ 远程规则集里有无「不带 `no-resolve` 的 IP 类条目」 | 缺陷藏在别人仓库的 `.list` 里；一条启用规则集里有 1 条就触发；必须逐个下载 + 数 | 高 |
| 17 | ⭐⭐ 国内域名有没有「域名类」规则兜底（不是「有没有一条叫 China 的规则」） | 给 IP 规则补 `no_resolve` 会同时关掉直连路径；必须有一份含大量域名条目的国内规则集；判据是数域名条目 | 高 |
| 18 | ⭐ `forward` 是否单值 + 是否写死节点域名（订阅耦合）+ 兜底是否直连可达 | `value` 单值 ⇒ 顺序/清单无意义；写死节点域名 ⇒ 换订阅变死代码；兜底不可达 ⇒ 掉进明文 | 高 |

**验收六条（同时满足才算完）**
1. `upstreams` / `proxy_nameservers` 无任何主机名端点 → 消灭用途①。
2. `forward` 有兜底且兜底组直连可达 → 消灭用途②，不依赖代理就绪。
3. 所有 IP 类规则都带 `no_resolve`。
4. 所有被启用的 `rule_set` / `proxy_rule_set`，其文件内 IP 类条目都带 `no-resolve`。
5. `bootstrap` 显式列 2 个以上国内公共 DNS IP，且不含 `system`。
6. ⭐⭐ 分流仍正确：国内域名仍判 `DIRECT`（15 个国内探针全绿）。**这是第 3 条的代价，必须成对交付。**

**五个脚本的定位（为什么不合成一个）**
| 脚本 | 看哪一层 | 关键点 |
|---|---|---|
| `check_egern_dns.py` | **profile 文本** | 能验证的只有「你自己编码进去的假设」 |
| `audit_ruleset_noresolve.py` | **被引用的规则集文件** | 缺陷不在 profile 里 —— 不下载就永远看不见 |
| `audit_routing_coverage.py` | **域名 → 命中规则 → 策略** | 验证「防泄露」没把「分流」一起干掉 |
| `audit_dns_forward.py` | **`forward` 的结构**（单值性 / 订阅耦合 / 换订阅演练） | 验证「换订阅后还能不能防泄露」 |
| `audit_region_filters.py` | **地区组 filter 的「两份拷贝」** | 负向断言（「排除以上全部」）必须逐字重抄关键词，Egern 不支持 `filter` 引用 ⇒ 只能靠脚本守同步 |

### 5. 规则集开销实测

> 数据来自在真实内核里加载规则集后量出的常驻内存与查询耗时。

- **内存估算**：原生实现约 130–175 B / 域名条目 ⇒ 内存 ≈ `条目数 × 0.15 KB`。
  例：`ChinaMax_All_No_Resolve`（写作时点快照：111,332 域名 + 12,473 IP / 3.42 MB）→ 稳态 RSS +22.6 MB；`adrules_surge_domainset`（199,781 条）→ +24.7 MB。
- **加载与匹配几乎无代价**：就绪时间无差别；单次域名匹配 0.36–0.69 µs，表规模涨 111 倍只让查询涨不到 2 倍（O(标签数)）。**大表不拖慢连接，只吃常驻内存。**
- **大表不能瘦身**：去重收益 0；父后缀冗余仅 4–5 条；99.5% 已是两级域名；表内 IP 段与 `geoip:CN` 大面积重合（61% 两端都在 CN / 面积 93.4%）。
- **换小表按覆盖率判，不按体积**：ACL4SSR `ChinaDomain.list`（586 条 / 17 KB）对大表长尾抽样只覆盖 0.4%（高频 26 站 21/26）⇒ 主流站几百条够用，长尾 99.5% 会掉进代理。
- **工具**：`skill/scripts/egern/weigh_ruleset.py <大表> --sub <小表> --probe <域名>`。

### 6. 已知代价与取舍

- **`Foreign-DNS` 已删除**：迭代 f10 起它就无任何引用（forward 兜底改国内组后不再需要境外组）；`routing_v1` 曾**整组注释**保留为 A/B 备用，**`routing_v2` 起整段删除**。要恢复境外解析答案，需自行在 `upstreams` 里加回该组。风险提醒：若用它作兜底且代理未就绪，会掉进明文 `:53`。
- **两条线 × 双形态**：可选只有 `egern/profiles/lazy.yaml`（**懒人版**，4 组 / 10 条规则）与 `egern/profiles/routing.yaml`（**分流版 · 推荐**，24 组 / 24 条），固定名四件，升版不改名。⚠️ 头注 `#! version=` 里的 `v` 是**文件版本**（三段制 X.Y.Z：Z=小修、Y=中改、X=大改，满 10 进 1，4.0.10 合法）；配置变动时变动前的旧配置归档进 `profiles/config_old/`（归档号 = 目录内此分工最新号的下一位，完整版与 `.min` 成对，现役头注同步升为下一位）；更早历史看 git（备份 tag：`pre-cleanup-20260927`）。
- **图标整合进本仓库**：图标已整合进 `icons/`，模板不再跨项目引用图标地址。来源归属见上表；本仓按 MIT 许可分发（根 `LICENSE`）。
- **不写死节点（2026-10-06 起）**：分流版 `proxies` 为空、`policy_groups` 里也不含任何字面量节点名 —— 不存在悬空引用（组间引用保留；`routing_v2.3` 起**已无空组**）。
- **与订阅解耦**：forward 不写任何节点 / 订阅域名，换订阅无需改动 DNS 段（清单 18 验证订阅耦合 4 → 0）。
- **审计脚本报的 2 条 `LOW`（刻意为之，不是缺陷）**：`check_egern_dns.py` 对本模板的读数是 `0 high, 2 low`。两条都属「安全性 vs 可用性」的自觉取舍，不是配置错误：
  - **① 设置了 `proxy_nameservers`** —— 它成为代理侧解析的唯一出口（绕过 `forward`、强制直连）。这是必须的：节点域名要在代理起来之前解析，只能走直连侧。
  - **② `forward` 兜底指向国内组**（`Domestic-DNS`）—— 需要本地解析的境外域名会拿到国内答案（可能被污染）。按官方语义，走代理的域名由节点**远程解析**、不经过 `dns` 段，所以实际影响面**仅限 `DIRECT` 域名**。

### 7. 隐私与脱敏

本仓库是纯模板，**发布前经过系统化脱敏**。脱敏五类：
1. 节点 `server` / 凭据 / `sni` / `reality` 公钥；
2. 机场订阅 URL（含 token）；
3. `mitm.ca_p12` + `ca_passphrase`（个人 CA 私钥，注释掉并占位）；
4. 机场组名 / 节点名；
5. `dns.forward` 里的节点域名。

**自检机制**：构建脚本对 38–39 个敏感串做零残留断言，并对全仓库做字符串扫描。发布前复核结论：
- 模板 yaml 外部图标源引用 **0**；
- 真实节点域名 / 订阅 host **0** 命中；
- `token=` / `ca_p12` / `sub.` 经核对均为占位符（`REPLACE_WITH_YOUR_TOKEN` / 注释说明 / `sub.example.com`），无真实泄露。

### 8. 提炼的 Skill / 方法论

本项目的工程方法已沉淀为两个可复用的 WorkBuddy Skill，并配套了本仓库的脚本。

#### 8.1 `egern-profile-dns-hardening`

- **定位**：审计并加固 Egern 配置（Profile.yaml）的 DNS 泄露面与分流覆盖。
- **触发词**：Egern 配置 / 防 DNS 泄露 / `proxy_nameservers` / `bootstrap` 泄露 / 节点域名明文解析 等。
- **脚本清单**（10 个，各自看不同层；另带共享模块 `_egern_common.py`）：
  | 脚本 | 层级 | 覆盖清单 |
  |---|---|---|
  | [`check_egern_dns.py`](../../scripts/egern/check_egern_dns.py) | profile 文本 | 1–15 |
  | [`audit_ruleset_noresolve.py`](../../scripts/egern/audit_ruleset_noresolve.py) | 被引用的规则集文件 | 16 |
  | [`audit_routing_coverage.py`](../../scripts/egern/audit_routing_coverage.py) | 域名 → 命中规则 → 策略 | 17 |
  | [`audit_dns_forward.py`](../../scripts/egern/audit_dns_forward.py) | forward 单值 / 订阅耦合 / 兜底可达 | 18 |
  | [`audit_region_filters.py`](../../scripts/egern/audit_region_filters.py) | 地区组 filter 与 `Other Regions` 负向断言的同步 | 辅助 |
  | [`audit_ruleset_refresh.py`](../../scripts/egern/audit_ruleset_refresh.py) | 远程规则集 `update_interval`（非正值 = 不再更新 → HIGH；偏离约定值 → `--strict` 判负） | 辅助 |
  | [`weigh_ruleset.py`](../../scripts/egern/weigh_ruleset.py) | 规则集重量（构成/冗余/耗时/覆盖） | 辅助 |
  | [`probe_dns_endpoints.py`](../../scripts/egern/probe_dns_endpoints.py) | 端点逐个实测（DoH 线格式 / DoT 握手） | 辅助 |
  | [`probe_doh.py`](../../scripts/egern/probe_doh.py) | 只测 DoH 线格式 | 辅助 |
  | [`profile_ruleset.py`](../../scripts/egern/profile_ruleset.py) | 规则集类型分布 | 辅助 |
- **核心价值**：把「审计通过 ≠ 配置可用」的教训固化成 **18 项可复跑清单**，尤其强调**规则集层（清单 16）**与**分流覆盖层（清单 17）**这两个 profile 文本审计看不见的维度。

#### 8.2 `github-publish-sanitized-repo`

- **定位**：把本地文件（配置 / 脚本 / 文档）**脱敏后**发布到 GitHub 仓库，或往已有仓库做增量单提交。
- **触发词**：上传到我的 github / 发布到仓库 / 脱敏后上传 / 增量提交 等。
- **方法论要点**：
  - **Git Data API 流程**：`blobs → tree → commit → ref` 单次增量提交；读 HEAD 作 parent + `base_tree` 保证幂等更新。
  - **空仓库 409 处理**：空仓库不能直接建 blob（`POST /git/blobs` → `409 Git Repository is empty`）；先用 **Contents API（PUT）** 落一个初始化提交，再取 HEAD 作 parent + `base_tree`。
  - **脱敏五类 + 全库自检**：同第 7 节，发布前对全仓库扫描，确保敏感串零残留。
  - **绑定 PAT**：GitHub REST API + PAT 操作（本机无 gh CLI / SSH）。发布后**应提醒撤销轮换所用 PAT**。

#### 8.3 本仓库配套脚本（公开）

除 `skill/scripts/egern/` 的 10 个审计 / 探针脚本外，早期发布链路还包含一组构建脚本（位于维护者本地 `outputs/`，**不进公开仓库**，避免暴露构建侧的私人源路径）：
- `_build_public_template.py` —— 从脱敏基线生成模板（dns 段取自加固版、结构取自基线）。
- `_transform_template.py` —— 在已脱敏产物上做改写（剥节点引用、图标改指本仓库）。
- `_make_min.py` —— 由带注释版生成纯配置版（去注释）。
- `_fetch_icons.py` —— 下载整合全部图标到 `icons/`。
- `_publish_to_github.py` —— 递归遍历 `public/` 走 Git Data API 增量提交。

> ⚠️ **这组脚本当前已不在维护者本机**（2026-09-21 核查确认，全盘搜索无结果）。
> 它们描述的"从自用配置生成模板"流程**已停用** —— `routing_v2.1` / `routing_v2.2` / `routing_v2.3` / `routing_v2.4`
> 都是在仓库里**直接改 `profiles/*.yaml`** 产出的（模板早已脱敏完毕，无需重新生成）。
> 此处保留是为了记录方法论；若要恢复该流程，见 §8.2 的 Git Data API 流程重建。

### 9. 如何自行审计

三个主审计脚本**退出码 0 = 通过**，可直接用于提交前检查。
CI（根 `.github/workflows/ci.yml`）在 push / PR 自动跑同一组检查；本地同组命令：

```bash
PY="<你的 python（含 pyyaml）>"
S="skill/scripts"

"$PY" "$S/check_egern_dns.py" Profile.yaml
"$PY" "$S/audit_ruleset_noresolve.py" Profile.yaml        # 会下载并缓存规则集
"$PY" "$S/audit_routing_coverage.py" Profile.yaml
"$PY" "$S/audit_dns_forward.py" Profile.yaml --drill       # 换订阅演练
"$PY" "$S/audit_region_filters.py" Profile.yaml            # 地区组 filter 同步（lazy 无此结构，自动跳过）

"$PY" "$S/weigh_ruleset.py" ChinaMax_All_No_Resolve.list --sub ChinaDomain.list
"$PY" "$S/probe_dns_endpoints.py" Profile.yaml
```

规则集缓存写在系统临时目录（分流版 22 个远程规则集 · 写作时点实测 3.25 MB），可离线复用（`--offline`）。

> 📌 全部检查可在本地完整复现；push / PR 时 CI（`.github/workflows/ci.yml`）自动再跑一遍。
> 这是个人模板仓库，不会有外部贡献者，"自动验 PR"没有服务对象，而本地跑一遍只要几十秒。
> 上表那批本地命令已覆盖自动化做过的全部断言，**功能上没有任何损失**。
> 详细说明见 [`skill/reference/egern/public-repo.md`](../gates.md)。

### 10. 常见问题（扩展版）

**Q1：为什么 forward 只留一条 catch-all 兜底，不写节点域名？**
因为配了 `proxy_nameservers` 后代理 DNS 跳过 forward（节点域名根本不走这里），且兜底 `value` 为单值时顺序与域名清单都无意义。写节点域名只会随订阅变化变成死代码。详见 2.4 / 清单 18。

**Q2：兜底指向国内组，会不会让境外网站拿到污染答案？**
不会。走代理的域名由节点远程解析，根本不经过本地 `dns` 段；兜底组只服务 DIRECT 域名、节点域名、profile 自身依赖。而且「泄露到运营商」（不可撤销）比「答案被污染」（对国内/Apple 域名反而更快更准）致命得多。兜底组的唯一判据是「直连可达」，不是「指向境外」。

**Q3：为什么 `geoip: CN` 不能单独承担国内直连？**
`geoip: CN`（带 `no_resolve`）只对「已经是 IP」的连接生效。国内域名的直连完全依赖那份**纯域名的国内规则集**（`direct.txt`）。给 IP 规则补 `no_resolve` 会同时关掉「靠解析判 IP 归属」那条直连路径——所以补 `no_resolve` 的同一时刻，必须确认有一份含大量域名条目的国内规则集。这是清单 17 的核心。

**Q4：规则集里的 `no-resolve` 是必备的吗？**
不是「所有规则集都要」，而是**只有能匹配 IP 的规则才需要**：
- **纯域名规则集**（`direct.txt`、多数分区表）——只做域名串匹配，**任何情况下都不触发解析** ⇒ `no-resolve` 是空操作，写不写都一样，不是必需的。
- **含 IP-CIDR / IP-CIDR6 / IP-ASN 条目的规则集**（历史上 `Apple_All.list` 有 13 条裸 IP、`ChinaMax.list` 有 12,472 条 IP）——这些 IP 条目若不带 `no-resolve`，**每个走到该规则的域名都会被强制本地解析一次**（泄露来源 + 额外延迟）⇒ 这几条 IP 必须带 `no-resolve`。
- **profile 级 IP 规则**（`geoip` / `ip_cidr` / `asn`）——同理必须带 `no_resolve`。

一句话：**`no-resolve` 是「IP 规则的开关」，与域名规则无关。** 判据是「这条规则能不能匹配 IP」，而不是「别人的配置里写了没写」。代价见 Q3：给 IP 规则关掉解析判定后，必须用域名规则补回来。

> **实证（本模板）**：`no_resolve` 在 profile 里**作为配置键只出现 1 次**（`geoip: CN`；带注释版另有 7 处提及全在注释里）。模板引用的 **21 个**远程规则集中，**14 个是纯域名**（`direct.txt` / `private.txt` / Gemini / Claude / Anthropic / AI / GitHub / Microsoft / YouTubeMusic / AWAvenue-Ads / **Jinx direct**（2026-10-04 前名 `white-guard`） / **Jinx ads** / 本仓自托管的 `apple_system.list` / **`apple.txt`**，无需 `no-resolve`）、**7 个含 IP 条目**（Lan / ChatGPT / Spotify / YouTube / Google / Telegram / Twitter；`Proxy.list` 已改纯注释、不再被引用），而这 7 个的 IP 条目**已在上游 `.list` 内全部自带 `,no-resolve`**（写作时点逐条核对：`Lan` 18/18、`ChatGPT` 2/2、`Spotify` 2/2、`YouTube` 3/3、`Google` 5/5、`Telegram` 10/10、`Twitter` 6/6）。所以「看起来到处是 `no-resolve`」是**上游规则集自带的**，不是 profile 在堆 —— profile 只需管好自己那一条 `geoip: CN`。（2026-10-04 前 Apple 那条是 `Apple_All_No_Resolve.list`，13/13 自带 `,no-resolve`，计入含 IP 的 8 个；换成零 IP 的 `apple.txt` 后为 7 个。）

**Q5：`Foreign-DNS` 组去哪了？我还能用吗？**
`routing_v2` 起已整段删除（迭代 f10 起它就无引用，`routing_v1` 曾注释保留为 A/B 备用）。想用境外解析答案，需自行在 `upstreams` 里加回该组（6 个境外 DoH/DoT 端点），并把 forward 兜底 `value` 改过去。但注意：若它作兜底且代理未就绪，会掉进明文 `:53` —— 迭代 f10 默认用国内组兜底正是为了避免这条路径。

**Q6：模板还需要手工填节点吗？**
不需要。分流版两个内核都只填 `Airport` 订阅 URL 即可 —— `Proxy` / `Smart` / `Select` / `AI`
与 6 个地区组全部从订阅取节点。（2026-10-06 起移除占位节点；此前版本需额外填 `Node-A` / `Node-B`。
懒人版 `lazy.yaml` 仍带占位节点。）

**Q7：图标为什么都收进本仓库 `icons/`？**
为了避免模板跨项目引用图标地址（你的项目或别人的项目）。图标已整合进 `icons/`，模板全部以本仓库原始地址引用，并保留来源署名。

**Q8：两个模板文件有什么区别？**
内容完全一致，仅注释差异。`egern/profiles/routing.yaml` 带注释（每段附原理），`egern/profiles/routing.min.yaml` 纯配置。按习惯取用其一（历史版本看 git）。

**Q9：审计全绿就安全了吗？**
不。本项目连续 5 次「脚本 0 high、实测仍有问题」，根因是审计维度缺失（没看规则集文件、没看分流覆盖）。必须把每个新维度补成可复跑脚本，而不是重跑同一脚本。详见第 3 节 / 清单 16、17。

---

回到 [README](../../../README.md) ｜ 原理与案例见 [DNS 基础](../dns.md) ｜ 清单见 [加固清单](../ops.md)

---

## Egern · 加固模板（egern 侧）

> 本文是 [`SKILL.md`](../../SKILL.md) 的引用文件。 **何时读**：要产出一份加固后的 `dns` 段 + `rules` 时。

模板里的行内注释就是**逐行理由**，别删。规则顺序不能反：
先把解析路径收口（`proxy_nameservers` 显式写 + `forward` 只留兜底），再去调 `upstreams` 里的解析器。

---

```yaml
dns:
  bootstrap:                      # 只能明文 UDP:53 —— 本文件唯一无法加密、无法走代理的出口。
  - 223.5.5.5                     # 列 2 个以上国内公共 DNS：官方「解析失败时自动使用系统 DNS」，
  - 223.6.6.6                     # 而 system 在蜂窝下就是运营商。多列几个只为压低这一最坏分支。
  - 119.29.29.29                  # ⚠️ 绝不写 system —— 那是主动把运营商解析器接进回退链。
  upstreams:
    Domestic-DNS:                 # 国内域名 → 国内加密 DNS。★ 全部写 IP 字面量：
    - https://223.5.5.5/dns-query  #   端点上每写一个主机名，官方就会用明文 bootstrap 解析它一次
    - https://223.6.6.6/dns-query  #   （bootstrap 用途①）。写 IP 则一次都不产生，且零依赖。
    - https://1.12.12.12/dns-query #   下面 6 个已实测通过（含证书覆盖 IP），两家机构 × 两种协议。
    - https://120.53.53.53/dns-query
    - tls://223.5.5.5
    - tls://1.12.12.12
    Foreign-DNS:                  # ★ 一律 IP 字面量，杜绝 bootstrap 解析
    - https://8.8.8.8/dns-query    # 需在 rules 里把这些 IP 显式判给 Proxy，链路才是
    - https://8.8.4.4/dns-query    # 「设备 → 代理 → 8.8.8.8」，从国内蜂窝也能建起来。
    - https://1.1.1.1/dns-query    # 多列端点：官方「组内并发竞速、最快者胜」，
    - https://1.0.0.1/dns-query    # 触发回退的唯一条件是「本组全失败」，端点越多越不可能。
    - tls://8.8.8.8
    - tls://9.9.9.9                # ⚠️ Quad9 只能走 DoT：其 9.9.9.9 的 DoH 实测
                                  #    返回 HTTP Version Not Supported（只提供 HTTP/3）
                                  #    写 https://9.9.9.9/dns-query 会静默失效。
    # ⚠️⚠️ 本组**不要**用作 forward 的兜底 —— 它必须经代理才可达，把兜底挂在它身上等于
    #      「先有代理，才敢解析」，代理未就绪时那次解析会掉进 bootstrap 明文（见坑 13）。
  forward:                        # ★★ f10 起只留兜底 —— **不要在这里写任何具体域名**（坑 18）
  - domain_regex:                 # ★★ 双保险之一：官方 PCRE2 find 式，'.' 必然命中任何域名
      match: '.'
      value: Domestic-DNS         # ★★ 兜底指向「直连可达」的国内加密组 —— 不是境外组。
  - domain_wildcard:              #    境外组必须经代理，代理没就绪时兜底就会掉进 bootstrap
      match: '*'                  #    明文（见坑 13）。按官方语义走代理的域名由节点远程解析，
      value: Domestic-DNS         #    本地 dns 段只服务 DIRECT 域名，所以国内组没有副作用。
  # ★ 为什么不需要 `.cn` / 国内域名表 / 节点域名 / 延迟测试域名 / 图标域名这些规则：
  #   ① 它们的 value 与兜底**完全相同** ⇒ 单值集合里"命中顺序"不产生任何影响，删掉也不变（清单 18）。
  #      官方那句"第一条命中的决定上游"只在 value 有差异时才有意义。
  #   ② 节点域名的解析走**代理 DNS**，配了 proxy_nameservers 后官方明确"**跳过 Forward**"
  #      ⇒ 写在 forward 里的节点域名规则是**死代码**（f7 之前它有用，f7 之后退役）。
  #   ③ 延迟测试域名与图标域名同理：f4 加它们是因为当时兜底是境外组（不安全）；
  #      f6 把兜底换成国内组之后，它们就已被兜底覆盖。
  #   ⚠️ 千万别为了"看起来严谨"再往这里堆域名 —— 每堆一条就把"换订阅"变成一次复查配置的义务。
  # ★★ f7 起必须显式写 proxy_nameservers —— 不写就等于留下一条通往明文 UDP:53 的兜底分支：
  #   官方原文：「未配置时，代理 DNS 与默认 DNS 共用 Forward 规则，**未命中回退到 Bootstrap**」；
  #   配置后语义：「所有代理 DNS 查询强制走该列表，**Forward 规则会被跳过**」。
  #   只能用国内端点 —— 代理 DNS **强制直连**，境外解析器在电信线路上不可达。
  proxy_nameservers:
  - https://223.5.5.5/dns-query
  - https://223.6.6.6/dns-query
  - https://1.12.12.12/dns-query
  - https://120.53.53.53/dns-query
  - tls://223.5.5.5
  - tls://1.12.12.12
  # ⚠️ 如果你发现"节点连不上"，第一件事是注释掉这 6 行（等价于回到 f6 的行为）。
  hosts:                          # ★ 把上面 DoH 域名钉到 IP（仅当 IP 固定）
    dns.alidns.com: [223.5.5.5, 223.6.6.6]
    doh.pub: [1.12.12.12, 120.53.53.53]
    dot.pub: [1.12.12.12, 120.53.53.53]
  block_ips:                      # 丢弃空路由式污染应答；别放私网段免得误伤内网
  - 0.0.0.0
  - 127.0.0.1

rules:
- domain_suffix:
    match: alidns.com
    policy: DIRECT
- domain:
    match: doh.pub
    policy: DIRECT
- ip_cidr:
    match: 223.5.5.5/32
    policy: DIRECT
    no_resolve: true
- domain:
    match: dns.google
    policy: Proxy
- domain_suffix:
    match: cloudflare-dns.com
    policy: Proxy
- ip_cidr:                        # ★ 兜住「App 硬编码 DoH IP + :443 绕过 hijack」
    match: 8.8.8.8/32
    policy: Proxy
    no_resolve: true
- rule_set:                      # ★★ 国内域名直连兜底（坑 17）—— 必须用域名条目足够多的那份：
    match: https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/ChinaMax/ChinaMax_All_No_Resolve.list
    policy: DIRECT               #   111332 条域名 + 12473 条 IP（IP 全带 no-resolve）
                                 #   ❌ 别用 ChinaMax.list：它只是 IP 规则集，域名只有 64 条
- domain_suffix:                  # ★ 补 .cn 直连兜底：不依赖上面那份规则集是否加载成功
    match: cn
    policy: DIRECT
- geoip:                          # ★ 不加 no_resolve 会为每次判定触发解析
    match: CN
    policy: DIRECT
    no_resolve: true
- default:
    policy: <代理组>
```

顶层另加：`ipv6: false`、`hijack_dns: ['*']`、`real_ip_domains: ['*.lan','*.local','*.push.apple.com']`。

⭐ **f10 起不要做这一步（它的反面才是对的）**：早期版本（f3）要求"把域名形式的节点逐个写成 `domain_suffix → Domestic-DNS`"，因为那时代理 DNS 会共用 `forward`。**f7 显式写出 `proxy_nameservers` 之后，代理 DNS 会跳过 `forward`** ⇒ 那些规则再也没被查询过（死代码，坑 18）。现在只需保证两件事：

1. `proxy_nameservers` **显式设置**，端点全部是**国内可达的 IP 字面量** —— 它是节点域名解析的唯一出口；
2. `forward` **只留兜底**，且兜底组「直连可达」。

⚠️ 顺序仍不能反：**先把解析路径收口（这两条），再去调 `upstreams` 里的解析器**。理由没变 —— 这些名字在隧道建立前必须被解析，而代理侧强制直连，国内根本问不到境外解析器。**但收口的手段是"把代理 DNS 钉死"，不是"在 forward 里列举域名"。**

⭐ **同理，profile 自身运行必需的域名**（`proxy_latency_test_url` / `direct_latency_test_url` / 策略组 `icon`）**也不需要单列规则**：f6 起兜底已是国内加密组，它们天然被覆盖。它们只在**兜底是境外组的配置里**才会造成持续泄露 —— 那正是 f4 加它们的场景。用 `audit_dns_forward.py --drill` 可验证任何域名（含这两类）都落到安全的兜底。

---

## Egern · 分支与变体（egern 侧）

> 本文从 [`SKILL.md`](../../SKILL.md) 拆出 —— **Egern 单侧任务只读本文件，不读分支 A**。
> 共享骨架（泄露面五类 / 四条铁律 / 六条底线 / 标准动线 / 按需读取索引）在 SKILL.md §1–§4。

#### 适用

用户给一份 Egern `Profile.yaml`（或含 `dns:` 段的 YAML），要求「防 DNS 泄露 / 别让 DNS 裸奔 / 检查 DNS 配置」，或反馈「实测有 DNS 泄露」。也可用于交付前自检。

#### 引用文件（按需读取）

本文件是**主干**：Egern 双轨 DNS 模型、18 项审计清单、模板骨架速览、验收标准。
`reference/egern/` 七篇的「何时读」索引见 SKILL.md §4。**移植到 Surge 侧前必读
[`reference/shared/cross-kernel-diff.md`](../rulesets.md)**。

#### Egern 的 DNS 模型（不理解这个就会改错地方）

官方 `docs/configuration/dns` 定义**两条互不相通的解析路径**：

| 路径 | 用途 | 连接上游时 | 未命中时 |
|---|---|---|---|
| **默认 DNS** | 解析**用户要访问**的域名 | **遵循代理规则**（可走代理） | 回退 Bootstrap |
| **代理 DNS** | 实际承担**节点 `server` 的域名**——那个名字必须在隧道建立前解析出来（官方措辞是"供代理服务解析目标域名"；从"强制直连"约束反推出这个实际角色） | **强制直连**（避免 DNS→代理→DNS 循环） | 未配 `proxy_nameservers` 时回退 Bootstrap |

**四个决定一切的要点**（改配置前逐一核对）：

| # | 事实 | 对改配置的直接推论 |
|:-:|:-----|:-------------------|
| 1 | **代理 DNS 强制直连**；国内直连去问境外解析器（`8.8.8.8:443` 之类）基本不通 | 代理侧的任何解析只有两条出路：**国内解析器**，或**明文 `bootstrap`**（还可能回落 `system` = 运营商）。这条路径**无法加密**，只能靠「让它不需要解析」（节点写 IP）或「给它确定的可达解析器」收口 |
| 2 | **`proxies[].server` 是域名的节点必然产生一次「本机 + 直连 + 明文」解析**——整份配置里唯一**必定发生**的国内解析，不取决于访问什么网站，只取决于连哪个节点 | 动手前先统计节点形式：`python -c "import yaml;d=yaml.safe_load(open('Profile.yaml',encoding='utf-8'));print([(list(p.values())[0].get('name'),list(p.values())[0].get('server')) for p in d['proxies']])"` |
| 3 | **进代理的域名由节点远端解析**（官方语义 + 社区事实标准 Repcz 原话：「已经匹配到走节点的规则交由节点 dns 查询，dns 设置仅对需要本地解析的域名进行查询」） | 本地 `dns:` 段只服务三类名字：**直连域名 · 节点自己的域名（走 `proxy_nameservers`）· profile 自身依赖**。改哪里才有意义由此决定 |
| 4 | **回退链**（"泄露到运营商"的唯一来源）：选中上游解析失败 → `bootstrap` → 再失败 → `system`。官方原文：bootstrap「仅支持传统 UDP 协议（端口 53），且不遵循代理规则——**流量直连**」，用途「① 解析 `upstreams` 中加密 DNS 服务器的主机名；② 作为最终的 DNS 回退」，且「未配置或解析失败时，自动使用系统 DNS 服务器」 | 🚨 国内运营商普遍对第三方明文 :53 做 DNS 重定向/调度 ⇒ 任何查询落到 bootstrap / system，最终应答者就可能变成**运营商自己的服务器**（用户看到「DNS 泄露到中国 ISP」）。**这条路无法加密，唯一办法是让它永不触发** |

#### 泄露只可能出在这六个位置

| # | 位置 | 机制与备注 |
|:-:|:-----|:-----------|
| 1 | `upstreams` / `proxy_nameservers` 里用了**域名**形式的加密 DNS | 必被 bootstrap 明文解析一次（用途①） |
| 2 | ⭐ **节点 `server` 是域名，且解析没有显式出口** | 未配 `proxy_nameservers` 时：落 `forward` 境外组 → 直连通不了 → 回退明文 bootstrap / `system`。**CN 环境下最常见、也最容易被漏掉的一条**。f7 起由 `proxy_nameservers` 收口（见清单 2 / 2b） |
| 3 | **回退被触发** | 上游写错、端点失效、或端点路由被绕坏 → 落到明文 bootstrap / system |
| 4 | **IP 类规则没 `no_resolve`** | 为判定规则而触发解析 |
| 5 | **国内解析器被用在境外域名上** | 见下方实测铁律——不是泄露这么轻，是直接解析错 |
| 6 | ⭐ **profile 自身运行所必需的解析**（`proxy_latency_test_url` / `direct_latency_test_url` 的域名、策略组 `icon` 的域名）没有被靠前的 forward 规则接住 | 这些名字**普遍不在 ChinaDomain.list 里**——实测 `cp.cloudflare.com`、`connectivitycheck.platform.hicloud.com`、`jsdelivr.net`、`raw.githubusercontent.com` 全部 **0 命中**（表里唯一两条 cloudflare 还是注释掉的），于是整类落到兜底 = 境外组。而这类解析**每轮节点测速都要做一次**（策略组 `interval` 到点就全量测一遍）⇒ 泄露是**持续型**的、与访问什么网站无关。**继节点域名之后第二个必须显式接住的名字类别**（f3 漏的就是它；f6 起兜底换国内组后天然覆盖，f10 起连单列规则都不再需要——见清单 15 / 18） |

#### ⚠️ 实测铁律：国内解析器不能用来解析境外域名（只约束"本地解析"路径）

实测（本机出口直连，取 `www.google.com` 的 A 记录）：

| 端点 | RFC8484 线格式 | JSON API | `www.google.com` 返回 |
|---|---|---|---|
| `doh.18bit.cn` | 200 ✓ | 400 | `216.239.38.120` |
| `dns.alidns.com` | 200 ✓ | 400 | **`31.13.92.37`（Facebook 段，典型 GFW 污染签名）** |
| `doh.pub` | 200 ✓ | 200 | `174.132.167.252` |
| `dns.google` / `1.1.1.1` / `8.8.8.8` | 200 ✓ | 400/200 | `142.251.x.x` ✓ 真实地址 |

**结论：让国内解析器解境外域名，不是"泄露"这么轻 —— 是直接解析错（拿到污染 IP）。** 所有分岔设计都要围绕这条。

**边界（2026-09-19 二次修正，不划清就会把配置改坏）**：

1. **只约束"本地解析"这条路径。** 已经匹配到走节点的域名由节点远程解析，本地 `dns:` 段只为"需要本地解析"的名字服务（DIRECT 域名、节点域名、profile 自身依赖）⇒ **兜底指国内组，不会让"要访问的境外网站"拿到污染答案**——它只影响本来就走直连的域名。
2. **"泄露到运营商"和"答案被污染"是两个问题，致命的是前者。** 兜底挂境外组、代理未就绪时回退明文的配置，比兜底用国内加密组的配置**危险得多**：前者泄露给运营商（不可撤销），后者最坏只是本地解析的 DIRECT 域名拿到国内答案（可接受，且对国内/Apple 域名反而更快更准）。

⇒ **兜底组的唯一判据是「直连可达」，不是「指向境外」。**（早期审计里"兜底指国内 = HIGH"是**错判**，已撤回，见坑 13。）

#### 审计清单

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `upstreams` / `proxy_nameservers` 的加密 DNS 是否 IP 字面量或已钉 hosts | 域名端点 → 必被 bootstrap 明文解析 | **境外域名=高**；国内域名=低 |
| 2 | ⭐ **`proxies[].server` 是域名的节点，它的解析走哪条路** | 节点域名走的是**代理 DNS**。f7 起 `proxy_nameservers` 已被显式设置 ⇒ 代理 DNS **跳过 `forward`**，只用那组 IP 字面量端点 ⇒ **不需要、也不应该**在 `forward` 里为节点域名写规则（那是死代码，见坑 18 / 清单 18）。判据从"forward 有没有接住"改成「**`proxy_nameservers` 是否显式设置、端点是否全为 IP 字面量**」 | **高** |
| 2b | `proxy_nameservers` 是否存在 | **f7 起必须显式写。** 它是**硬覆盖**：一设就绕过 `forward`、强制直连。**"不写"才是问题** —— 官方语义「未配置时，代理 DNS 与默认 DNS 共用 Forward 规则，**未命中回退 Bootstrap**」，等于留下一条通往明文 UDP:53 的兜底分支。只能用**国内**端点（代理 DNS 强制直连，境外解析器在电信线路上不可达） | **高（缺失时）** |
| 3 | ⭐ **DNS 端点是否有显式路由** | `geoip` 加了 `no_resolve` 就**不再匹配域名**；主机名形式的端点会落到 `default` → 国内端点被绕到境外出口 / 境外端点直连被阻断。**国内端点必须显式 → DIRECT，境外端点必须显式 → Proxy** | **高** |
| 4 | ⭐ **`forward` 里是否存在「捕获一切」的兜底，且该兜底组「直连可达」** | 兜底存在的意义只有一个：让"未命中的域名"不回退 bootstrap 明文。**判据是"这组在代理没起来时能不能工作"，不是"它指国内还是境外"** —— 组内端点必须全是 IP 字面量，**且至少一个端点在 `rules` 里被判给 `DIRECT`（判据 A），或至少一个是已知国内公共解析器 IP（判据 B，f10 引入）**。只判给 Proxy 的组 = 依赖代理 = 启动期（规则集/DB 下载、首轮测速）会掉进 bootstrap 明文。**兜底指国内组才是对的**（依据 = 上方实测铁律的边界两条）。**写法要认全**：`domain_wildcard: '*'` **和** `domain_regex: '.'`（官方 PCRE2 find 式，命中任意子串）都算兜底 —— 别只认前一种（审计器 f2 就误判过）。推荐**两条都写**（互不依赖的双保险），并让 `domain_wildcard` 放最后便于人/工具识别 | **高** |
| 5 | `geoip` / `ip_cidr` / `ip_cidr6` / `asn` 是否带 `no_resolve` | 官方：`no_resolve` **仅适用这四类**；不加则规则会触发解析 | 高 |
| 6 | ⭐ **规则引用的策略能否解析** | `policy` 是嵌在类型字典里的（`{domain: {match, policy}}`），要读 `r[type]['policy']`。抓 `负载均衡` 这类笔误 | 高 |
| 7 | 硬编码 DoH IP（8.8.8.8 / 1.1.1.1 / 9.9.9.9 / OpenDNS…）是否有启用规则 → 代理 | `hijack_dns` 只覆盖 **:53**，App 用 DoH on **:443** 会绕过 | 中 |
| 8 | ⭐ **`rule_set.match` 是否为 URL 或文件路径** | 写成 `AI` / `抓取` / `Apple push` 这种名字 → 无法加载，等同死规则 | 中 |
| 9 | `block_ips` | 未设 → `0.0.0.0` 这类空路由式污染应答照单全收 | 低 |
| 10 | `real_ip_domains` | 为空 → 走不到隧道的流量（APNs / 内网）也拿 Fake IP，推送/内网会异常 | 低 |
| 11 | `ipv6` | `true` → AAAA 可绕过 IPv4 侧封堵 | 中 |
| 12 | `hijack_dns` 是否覆盖全部 | 官方 example 示例值即 `['*']`（= 接管 :53 并返回 Fake IP） | 高（缺失时） |
| 13 | `public_ip_lookup_url` | **不配置**才不发 ECS（不把公网 IP 交给 DNS 服务器） | 配了才是问题 |
| 14 | `skip_tls_verify` | 应为未设置 / `false` | 低 |
| 15 | ⭐ **profile 自身必需解析的名字**（两个 latency test URL 的域名 + 策略组 `icon` 的域名）是否被"兜底之前"的 forward 规则接住 | 没接住 → 落兜底=境外组 → 一旦这次解析发生在直连侧（代理 DNS 强制直连 / 无代理可用），境外组不可达 → 回退 bootstrap 明文 → 再落 `system` = 运营商。**延迟测试端点 = 高**（每轮测速都触发，持续泄露）；**图标 = 低**（失败只是图标不显示；硬钉到国内解析器反而可能拿到污染/`0.0.0.0` 应答，收益<风险，可故意不动） | **高**（前提：兜底组不安全；f6 起兜底已换成直连可达的国内组 ⇒ 落到兜底不再构成泄露，实际降级为 LOW，且 f10 起**连"单列规则"都不再需要** —— 见清单 18） |
| 16 | ⭐⭐ **远程规则集里有没有"不带 `no-resolve` 的 IP 类条目"** | 这是**最隐蔽的一类**：缺陷不在 profile 里，而在别人仓库的 `.list` 文件里。官方 rules 文档：`no_resolve` 为 true 才"不触发 DNS 解析" ⇒ **不带就触发**。一条启用的 `rule_set` 规则里只要有**一条**这种条目，**每个走到该规则的域名都会被强制本地解析一次**。实测 `blackmatrix7/Surge/Apple/Apple_All.list` 有 13 条（139.178.128.0/18 等 Apple CDN 段）—— 这就是"规则判定 `default → Final → Proxy`、upstream 却是 `bootstrap`"的成因（坑 16）。**必须逐个下载 + 数**，用 `scripts/egern/audit_ruleset_noresolve.py` | **高** |
| 17 | ⭐⭐ **国内域名有没有"域名类"规则兜底**（不是"有没有一条叫 China 的规则"） | 给 IP 规则补 `no_resolve` 会**同时**关掉"靠解析判 IP 归属"这条直连路径。此时若没有一个**真正的域名规则集**接住国内域名，它们会整片落到 `default → Final → 代理`。判据：把规则集**下载下来数域名条目**（`DIRECT` 规则集域名条目 ≈ 0 就是这个坑），再用 `scripts/egern/audit_routing_coverage.py` 拿真实域名走一遍。实测 `ChinaMax.list` 只有 64 条域名 / 12472 条 IP（仓库 README：它与 `ChinaMax_Domain.list` 需"共同使用"） | **高** |
| 18 | ⭐ **`dns.forward` 的 `value` 是不是单值？有没有把节点域名写死？** | 若**除 `reject` 外**所有规则的 `value` 相同（`reject` 是终止动作、不产生解析，`routing_v3` 起允许与其并存） ⇒ **顺序与域名清单都不影响结果** ⇒ 本节对"换订阅/换机场"天然免疫；反之新域名会落到兜底组，必须先确认兜底组安全。另：节点域名的解析走**代理 DNS**，配了 `proxy_nameservers` 后官方明确"**跳过 Forward**" ⇒ **写在 `forward` 里的节点域名规则是死代码**（坑 18）。用 `scripts/egern/audit_dns_forward.py` 跑，含"换订阅演练"（合成未来节点域名） | **中**（可维护性/耦合面） |

**关于 `no_resolve` 的三个层级，别混**：
1. **规则级**（`rules:` 里 `- geoip: {match: CN, policy: DIRECT, no_resolve: true}`）—— 官方明说**只适用 `geoip`/`ip_cidr`/`ip_cidr6`/`asn` 四类**，写在 `rule_set` 规则上**不生效**。
2. **规则集文件内的顶层字段**（Egern 原生 YAML 格式才有的 `no_resolve: true`）—— "影响所有 IP 相关规则"。
3. **规则集条目级**（Surge `.list` 里的 `IP-CIDR,x/y,no-resolve`）—— **第三方 `.list` 走的就是这一层**，也是坑 16 的战场。profile 写得再干净也管不到它。

**键名以 DNS 专页为准**：`domain` / `domain_suffix` / `domain_keyword` / `domain_wildcard` / `domain_regex` / `proxy_rule_set`。
`configuration/example` 页里出现的是 `wildcard` / `regex` 这类短名（且与同页的 `domain_suffix` 混用）—— 那是**陈旧/不一致**的写法，别照抄。`real_ip_domains`、`vif_only`、`include_all_networks`、`include_apns`、`compat_route`、`block_quic` 等顶层字段确实存在（以 example 页为准，没有 `general` 页）。

#### 加固模板

完整模板（`dns:` 段逐键注释 + `rules` 骨架 + 顶层字段，**权威版本**）：
[`reference/egern/hardening-template.md`](../profiles/clash.md)。要改模板只改那一份。骨架速览：

1. `bootstrap`：≥2 个国内公共 DNS 的 **IP 字面量**，绝不写 `system`（回退链终点 = 运营商）；
2. `upstreams`：国内组 + 境外组端点**全部 IP 字面量**；境外组必须在 `rules` 里显式判给 Proxy，否则只能 bootstrap 明文去连；
3. `forward`：**只留兜底**——`domain_regex: '.'` + `domain_wildcard: '*'` 双保险都指向**直连可达**的国内加密组；不写任何具体域名（写了就是死代码 / 维护耦合，见清单 18）；
4. `proxy_nameservers`：**显式设置**，端点全是国内 IP 字面量（代理 DNS 的唯一出口，一设就跳过 `forward`）；
5. `rules`：最前钉 DNS 端点路由（国内端点 → DIRECT、境外端点 → Proxy，IP 类带 `no_resolve`），最后按序 `ChinaMax_All_No_Resolve` 域名兜底 → `.cn` → `geoip CN + no_resolve` → `default`。

顶层另加：`ipv6: false`、`hijack_dns: ['*']`、`real_ip_domains: ['*.lan','*.local','*.push.apple.com']`。

⭐ **f10 起不要做这一步（它的反面才是对的）**：早期版本（f3）要求"把域名形式的节点逐个写成 `domain_suffix → Domestic-DNS`"，因为那时代理 DNS 会共用 `forward`。**f7 显式写出 `proxy_nameservers` 之后，代理 DNS 会跳过 `forward`** ⇒ 那些规则再也没被查询过（死代码，坑 18）。现在只需保证两件事：

1. `proxy_nameservers` **显式设置**，端点全部是**国内可达的 IP 字面量** —— 它是节点域名解析的唯一出口；
2. `forward` **只留兜底**，且兜底组「直连可达」。

⚠️ 顺序仍不能反：**先把解析路径收口（这两条），再去调 `upstreams` 里的解析器**。理由没变 —— 这些名字在隧道建立前必须被解析，而代理侧强制直连，国内根本问不到境外解析器。**但收口的手段是"把代理 DNS 钉死"，不是"在 forward 里列举域名"。**

⭐ **同理，profile 自身运行必需的域名**（`proxy_latency_test_url` / `direct_latency_test_url` / 策略组 `icon`）**也不需要单列规则**：f6 起兜底已是国内加密组，它们天然被覆盖。它们只在**兜底是境外组的配置里**才会造成持续泄露 —— 那正是 f4 加它们的场景。用 `audit_dns_forward.py --drill` 可验证任何域名（含这两类）都落到安全的兜底。

#### 判断 hosts 能不能钉

**先实测解析**，IP 固定才钉；CDN 池不能钉（钉了反而破坏轮换）：

```bash
python -c "
import socket
for h in ['dns.alidns.com','doh.pub','doh.18bit.cn']:
    print(h, sorted({a[4][0] for a in socket.getaddrinfo(h,443)}))"
```

> 🪟 **Windows Git Bash 用户**：此命令含多行，粘入双引号会被 MSYS 参数转换**静默扭曲**（实测 `\n` → `/n`）——改存 .py 文件执行（任何平台通用）。

实测参考：`dns.alidns.com`→223.5.5.5/223.6.6.6（固定 ✅）、`doh.pub`→1.12.12.12/120.53.53.53（固定 ✅）、`doh.18bit.cn`→**11 个 IP 的 CDN 池（不可钉 ❌）**，且它落在 **42.51.x.x（中国联通）** 上的自建服务 —— 能用作国内上游，但别让它承担"所有国内域名"。

#### ⚠️ 已知缺陷索引

**18 条，每条都是真实事故复盘**，全文（含完整机制链与修法）见
[`reference/egern/pitfalls.md`](../pitfalls.md)——排查实际泄露、或改动判据 / 规则集之前先读它。

改动判据时最高频的三条：**13**（兜底挂在"必须经代理才可达"的组上 → 审计 OK、实测 `upstream: bootstrap`）·
**16**（强制解析藏在别人仓库的 `.list` 里——`Apple_All.list` 实测 13 条裸 IP）·
**17**（治好 DNS 泄露的那一手会顺手砍掉国内域名分流——`no_resolve` 与域名兜底必须成对交付）。

#### 改配置的安全姿势

Egern profile 常含**超长单行**（`mitm.ca_p12` 的 base64 CA 证书，可达数千字符）。**不要用 YAML dump 重写整个文件**（会丢注释、改格式）。正确做法：

1. 按行读入（`raw.split('\n')`）
2. 用「内容定位 + 断言唯一性」的方式插行/替换行
3. 额外写回，逐字节对比关键字段（如 `ca_p12` 完全一致）
4. 用 `yaml.safe_load` 验证新旧两份都能解析

⭐ **替换锚点必须换行锚定**：`src.index('dns:\n')` 会命中 `hijack_dns:\n` 里的子串，静默吃掉中间十几行（实测）。用 `src.index('\ndns:\n') + 1`，并且改完**逐字段比对未触碰的部分**（本项目用它抓到了那次误删）。

定位改动点的核心是 `find_one(pred, what)` —— 对每处改动断言「全文恰好命中 1 行」，命中 0 或 >1 行就中止。

##### 删除顶层键（实测：f9 删 `mitm` 段）

用户说「HTTPS 解密暂时不用了 / 把 mitm 删掉」时，**先查依赖再删**：

1. ⭐ **有没有规则依赖解密？** 只有 **`url_regex` / `header` / `user_agent` / `process_name`** 这四类需要 MITM 解密才能匹配；`domain*` / `ip_cidr` / `rule_set` / `geoip` 在 TLS 握手前就能判定。查法：
   `sed -n '<rules 起始行>,$p' profile.yaml | grep -c 'url_regex\|header\|user_agent\|process_name'`
   —— 零命中才可安全删（本项目实测零命中，零能力损失）。
2. **删除范围不能按行数猜**：先定位 `^mitm:$`，再断言紧随的缩进行**恰好**是 `  ca_p12:` + `  ca_passphrase:` 两行，再断言第 4 行不是缩进（否则段内还有别的子键，按行数删会吃错）。`ca_p12` 是**单行 3674 字符**的超长行，只有一行，别当成多行 base64。
3. **断言清单（七项）**：被删字段名与 base64 主体零残留 → 其余行逐条未变 → 顶层键数 = 原数 −1 且**差集恰好是 `{mitm}`** → 其余顶层键的值逐个相同 → `dns` / `rules` / `proxies` / `policy_groups` 解析后逐项相等 → YAML 可解析 → UTF-8 无 BOM / LF。
4. **原位留一行中性注释**（**不含** `mitm` / `ca_p12` 等字样，如「此处原为 HTTPS 解密（个人证书）配置段，2026-09-19 按需删除；需要时从 vN 取回」）—— 便于日后恢复，又不会干扰敏感串扫描。
5. **告知用户**：设备上已装的 CA 证书**不必删**（配置里不再解密，它不会被使用；真要清理去「设置 → 通用 → VPN与设备管理 → 配置描述文件」，但这与 DNS 泄露/分流无关）；**回滚 = 用上一版覆盖**，所以上一版必须保留。
6. 删 `mitm` 后三项审计应**与上一版逐字相同**（DNS 面 / 规则集 / 分流）—— 不同就是误删，回去查第 2 步的断言。

#### 加固结束的验收标准（七条同时满足才算完）

1. `upstreams` 与 `proxy_nameservers` 里**没有任何主机名端点**（全部 IP 字面量，或已钉 `hosts`）—— 消灭 bootstrap 用途①。
2. `forward` 有兜底，**且兜底组直连可达**（端点全为 IP 字面量 + **至少一个在 `rules` 里判给 `DIRECT`，或至少一个是已知国内解析器 IP** —— 两条二选一，见坑 13 末尾）—— 消灭 bootstrap 用途②，且不依赖"代理已就绪"。
3. 所有 IP 类规则（`geoip` / `ip_cidr` / `ip_cidr6` / `asn`）**都带 `no_resolve`** —— 否则每个走到它的域名都会被强制本地预解析一次（坑 15）。
4. ⭐ **所有被启用的 `rule_set` / `proxy_rule_set`，其规则集文件里的 IP 类条目都带 `no-resolve`** —— 用 `audit_ruleset_noresolve.py` 跑，必须 OK（坑 16）。
5. `bootstrap` 显式列 2 个以上国内公共 DNS 的 IP，**且不含 `system`** —— 把"全失败 → 系统 DNS"压到最低。
   ⚠️ 前 4 条是"让它不被用到"；第 5 条只是把最坏分支的概率压小。**bootstrap 是明文 UDP:53，在运营商线路上无论指向哪个 IP 都可能被接管 —— 它唯一安全的形态是"永远不被触发"。**
6. ⭐⭐ **分流仍然正确：国内域名仍判给 DIRECT。** 用 `audit_routing_coverage.py` 跑，15 个国内探针必须全 `DIRECT`。
   **这一条是第 3 条的代价，必须成对交付** —— 给 IP 规则补 `no_resolve` 会同时关掉"靠解析判 IP 归属"那条直连路径（坑 17）。所以补 `no_resolve` 的同一时刻，必须确认 `default` 之前有一份**含大量域名条目**的国内规则集（如 `ChinaMax_All_No_Resolve.list`）。**"DNS 审计全绿"不等于"配置可用"**：f7 时两个审计脚本双双通过，分流却整片是坏的。
7. ⭐ **`dns.forward` 与订阅零耦合：`value` 单值（`routing_v3` 起 = 非 `reject` 去向单值且等于兜底组），且没有任何一条规则把节点域名写死。** 用 `audit_dns_forward.py profile.yaml --drill` 跑，必须「零耦合 + 通过」。
   **防泄露必须由"兜底组的安全性"承担，而不是由"记得去列举域名"承担** —— 后者会让换订阅变成一件需要复查配置的事，而它连功能都没有（坑 18）。

#### 官方文档入口

- DNS 机制：`https://egernapp.com/docs/configuration/dns`（**核心页**，两条路径 + bootstrap + proxy_nameservers + block_ips + hosts 全在此）
- 规则字段：`https://egernapp.com/docs/configuration/rules`（`no_resolve` 适用范围、逻辑规则 `and`/`or`/`not`、rule_set 内部字段）
- 顶层字段全表：`https://egernapp.com/docs/configuration/example`（**注意键名与 DNS 页不一致**）
- 社区参考实现（中国网络环境的最佳实践，DNS 段写法值得对照）：`https://doc.repcz.link/egern/`（原 `repcz.github.io/Egern` 已迁至此，旧地址现 404）
- sitemap（找页面用）：`https://doc.egernapp.com/sitemap.xml`

⚠️ `https://egernapp.com/zh-CN/docs` 和 `/docs/configuration/general` 是 **404**；顶层字段只能从 `configuration/example` 页获取。DNS 页有中文版 `/zh-CN/docs/configuration/dns`。
