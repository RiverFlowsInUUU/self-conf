# DNS 防泄露 · 原理与三内核落地


## DNS 原理与泄露面

> 由原 `surge/docs/01` 与 `02` 合并。
> **原理部分（DNS 怎么工作、为什么会泄露）与内核无关** —— Surge / Egern / mihomo 三内核共用同一套推导；
> **落地语法逐内核不同**：三内核并列对照见 §7，mihomo 侧的六个专属特点见 §8。
> 判据脚本：Surge `check_surge_dns.py` · Egern `check_egern_dns.py` · mihomo `check_clash_dns.py`。

### DNS 是怎么工作的

> 这份文档的目标不是复述百科，而是让"为什么我的配置会把查询送到运营商那里"变得**可推导**。
> 读完后应能回答：一次解析有多少个环节可能被第三方看到、所谓"加密 DNS"到底加密了什么、以及为什么"开了 DoH"仍然可能泄露。

#### 1. 一句话定义

DNS 是互联网的**电话簿**：把人类可读的域名（`www.baidu.com`）翻译成机器可路由的 IP 地址（`110.242.68.66`）。

它有两个容易忽略的性质，正是所有泄露问题的根源：

- **它几乎总是明文的**（传统 DNS 走 UDP:53，无加密、无认证）。
- **它几乎总是"由别人替你去问"的**（递归解析，你只问一个"递归解析器"，它替你把整条链跑完）。

#### 2. 一次递归解析的完整过程

当你的设备要解析 `www.example.com`，它自己是不知道答案的。它做的事是：**问一台"递归解析器"，请它替你跑完全程**。

```
你的设备（stub resolver）
   │  ① 问：www.example.com 的 A 记录是？
   ▼
递归解析器（Recursive Resolver）  ← 你配置的 DNS 服务器，比如 223.5.5.5
   │
   │  ② 根服务器："com 的权威服务器在哪？"
   ├──────────────► 根服务器 (a.root-servers.net 等 13 组)
   │  ◄────────────── "去问 a.gtld-servers.net"
   │
   │  ③ TLD 服务器："example.com 的权威服务器在哪？"
   ├──────────────► .com TLD 服务器
   │  ◄────────────── "去问 ns1.example.com"
   │
   │  ④ 权威服务器："www.example.com 的 A 记录是什么？"
   ├──────────────► example.com 的权威服务器
   │  ◄────────────── "93.184.216.34"
   │
   ▼  ⑤ 把答案给你（并缓存一段时间 = TTL）
你的设备
```

**能从这里读出的第一个结论：**
在第 ②–⑤ 步里，有**四台不同的服务器**看到了"有人在查 `www.example.com`"。而在第 ① 步，**递归解析器**也看到了。

于是问题变成：**这五台里，哪几台能看到"是你"在查？**

- 第 ②–④ 步看到的是**递归解析器的 IP**，不是你。
- 第 ① 步看到的是**你的 IP**。

⇒ **谁是你的递归解析器，谁就知道你在访问什么。** 这就是"DNS 泄露"这句话真正的内容 —— 它泄露的不是"某个域名被查了"，而是**"你在用哪台解析器"**，以及这台解析器可以把你的查询和你本人关联起来。

#### 3. 明文 DNS 的暴露面

传统 DNS（UDP:53）在这三个位置会被旁观或篡改：

| 位置 | 谁能看 | 能做什么 |
|---|---|---|
| **你的设备 ↔ 递归解析器** | 你的接入网（运营商 / 公共 Wi-Fi） | 看到**完整的域名**；可以丢弃、可以返回伪造应答 |
| **递归解析器本机** | 解析器运营方 | 完整日志：查询域名 + 你的 IP + 时间 |
| **递归解析器 ↔ 权威服务器** | 沿途网络 | 通常看到的是解析器 IP，但应答仍可被注入 |

> **"运营商 DNS 劫持"就发生在第 1 行。**
> 中国运营商对**第三方明文 :53** 普遍做**透明重定向**：你把包发给 `8.8.8.8:53`，它在链路上被改写成发给运营商的解析器。
> 表现上"服务器配置无误"，实际应答却来自运营商 —— leak test 上就会显示"DNS 泄露到中国电信"。
>
> ⇒ **唯一安全的明文 :53 形态是"永远不被用到"。**

#### 4. 加密 DNS 加密了什么

DoH（DNS over HTTPS）把 DNS 查询包进 HTTPS 请求里，于是：

| 层 | 是否加密 | 说明 |
|---|:---:|---|
| 查询内容（域名） | ✅ | 运营商看不到你在查什么 |
| 往返路径 | ✅ | 与普通 HTTPS 流量无差别 |
| **"你用哪台解析器"** | ❌ | 除非走代理，否则目标 IP 仍是明文可见的 |

⇒ **这是最关键的一条："加密 DNS"只保护查询内容，不保护查询目标。**
所以一份只说"我用了 DoH"的配置，仍可能告诉运营商"这个人在用 Cloudflare 的 1.1.1.1"。

##### 但 DoH 有个自己带来的问题：引导（bootstrap）

DoH 端点通常写成 `https://dns.google/dns-query` —— **那是个域名，要先解析它**。
"先用明文 DNS 解析 DoH 服务器的 IP"这一步就叫**引导**。

⇒ 只要端点写主机名，就**必定**产生一次明文解析。这就是加固清单第 1 项要审的东西。
把端点写成 IP 字面量（`https://1.1.1.1/dns-query`），引导这一步就不存在了。

#### 5. Fake-IP 与 Real-IP

三个内核都让走代理的域名返回一个**假 IP**（`198.18.x.x` 段），好处是：

- 域名不需要在本地解析 —— 交给代理服务器远端解析，本地全程不产生查询；
- 本地的 DNS 缓存被彻底绕过，污染无处下手。

代价是：**有些流量拿假 IP 会坏**。典型是：

- **游戏机 NAT 类型检测**（Stun / UPNP 需要真实地址）
- **NTP 时间同步**
- **Apple 推送（APNs）与局域网设备发现**

所以各内核都提供一份"跳过假 IP"的名单，但**键名与通配语法都不同**（§7）：

| 内核 | 键 | 形态 |
|:--|:--|:--|
| Surge | `always-real-ip` | 逗号分隔的主机名通配，写在 `[General]` |
| Egern | `real_ip_domains` | YAML 列表 |
| mihomo | `dns.fake-ip-filter` | YAML 列表；`+.` 含本域与任意层子域，`*` / `*.` **只匹配一层** |

> ⚠️ 但要注意：这份名单 **只改变"返回真实 IP 还是假 IP"，不改变路由去向**。
> 一个在名单里的域名，如果规则判它走代理，它依然走代理 ——
> 只是它的 IP 是真实的而已。（Egern 项目出现过这个误读。）

#### 6. 接到本模板上

DNS 泄露的出口（以 Surge 为例是三条），本模板逐条堵：

| 出口 | 怎么堵 |
|---|---|
| **引导解析**（端点是主机名） | 端点写 IP 字面量；`dns-server` 写裸 IP，绝不用 `system` |
| **旁路设备**（忽略本内核 DNS 的设备发 `:53`） | `hijack-dns` / `hijack_dns` / `tun.dns-hijack` 把查询接管回来 |
| **规则触发解析**（IP 类规则不带 `no-resolve`） | 全部 IP 类规则带 `no-resolve`，含第三方规则集 |

逐条判据见 [加固清单](./ops.md)。
为什么泄露一定会落到"运营商"那一边，见 [本篇「DNS 为什么会泄露」](#dns-为什么会泄露)。

> ⚠️ **出口清单不是三内核共用的**：mihomo 侧还多一条 **IPv6 面**（§8.4），
> 且它的收口装置（TUN 劫持）挂在 `tun` 段而不是 DNS 段。三内核的完整对照见 §7。

### DNS 为什么会泄露

> 五个真实案例，每个给出：**现象 → 机制 → 修法**。
> 全部来自 Egern / Surge 两份配置的实测复盘，不是假设。
> （**机制在三内核上同构** —— mihomo 侧的对应判据编号见文末汇总表。）

#### 案例 1 · "我用的是国内加密 DNS，却泄露到中国电信"

**现象**：`1.1.1.1` 的 leak test 显示「DNS 泄露到中国电信」，但配置里明明写了 DoH。

**机制**：运营商的**透明重定向**。
你把包发给 `1.1.1.1:53`，它在链路上被改写成发给运营商的解析器。你的配置没错，包也没错 ——
是链路上有人替你改了收件地址。而 leak test 看到的应答来源，就是运营商那台。

**修法**：不用明文。DoH/DoT 走 443 / 853，重定向需要同时劫持 SNI，代价高得多，
运营商的策略通常是**阻断**而不是重定向。本模板把三处明文出口全部收口。

#### 案例 2 · "规则判定明明是走代理，upstream 却是明文引导"

**现象**：日志里规则判定 `FINAL → Proxy`，但同一时刻的 upstream 显示走了明文解析。

**机制**：**IP 类规则没带 `no-resolve`**。
Surge 的 `GEOIP` / `IP-CIDR` 类规则需要一个**已解析的地址**才能判定。
如果查到某条 IP 规则时地址还没解析，Surge 会**暂停规则求值、先做一次本地解析**。
（mihomo 同构：走到 `RULE-SET,geoip-*,…` 这类 `behavior: ipcidr` 的规则时同样会为判定而解析。）

**修法**：给所有 IP 类规则加 `no-resolve`。
⚠️ 但这条改动有代价 —— **它会同时关掉"靠解析判 IP 归属"这条直连路径**（见案例 5）。
所以补 `no-resolve` 的**同一时刻**必须确认国内域名有域名类规则集接住。
（mihomo 侧这道防线由 `check_clash_dns.py` 判据 **⑩** 守，且判"是不是 IP 类"的第一依据是
provider 的 `behavior`，不是 `geoip-` 名字前缀。）

#### 案例 3 · 第三方规则集不受 profile 洁净度影响

**现象**：profile 里每条 IP 规则都写了 `no-resolve`，但日志显示仍有大量意料之外的本地解析。

**机制**：**缺陷藏在第三方 `.list` 文件里**。
实测 `blackmatrix7/Surge/Apple/Apple_All.list` 里有 **13 条** `IP-CIDR` 条目**不带** `no-resolve`
（`139.178.128.0/18` 等 Apple CDN 段）。一条启用的 `RULE-SET` 规则里只要有**一条**这种条目，
**每个走到该规则的域名都会被强制本地解析一次**。

**修法**：换用上游提供的 `No_Resolve` 变体，或把整个规则集下载下来**数**一遍。
这正是 `self-conf-skills/run/surge/audit_ruleset_content.py` 存在的原因 —— 这个缺陷**无法从 profile 里看出来**。

（mihomo 侧的同一条面：远程集里**内嵌的裸 IP 条目**不在 profile 里，本地静态门禁看不见。
`check_clash_dns.py` 判据 ⑩ 对 `behavior: classical` 的集**明确判不了**，只给 LOW 提示 ——
必须拉下来数。本仓自托管的 `rules/*.list` 实测 **0 条 IP 条目**，所以那一侧天然没有这个面。）

#### 案例 4 · "profile 自己需要的域名，我一个都没接住"

**现象**：配置看起来完全正确，但启动期的前几秒仍有明文查询。

**机制**：**配置自己也依赖解析**。三类名字：

1. **代理测试端点的域名** —— `proxy-test-url` / `internet-test-url` 的域名。
   ⚠️ **但这里要克制**：官方 KB 明确「走代理策略时 DNS 解析永远在代理服务器进行」，
   本地不解析；只有命中 DIRECT 才本地解析。所以端点域名**只在它落进 DIRECT 路径时**
   才形成本地解析面，且这是**性能探针**不是泄露通道。
2. **策略组图标 URL 的域名** —— 只在启动时取一次，影响较小（失败只是图标不显示）。
3. **`always-real-ip` 里的主机名** —— 若没被前置规则接住，会落到兜底。

**修法**：选端点时按**用途**定，而不是一律求境内：

- `internet-test-url`（连通性检测）用国内 204 —— 测的是「本机能不能上网」。
- `proxy-test-url`（`smart` 打分）**保持境外** —— 测的是含国际段的真实路径，
  对「哪个节点上网更快」才有参考价值。这是性能取向，不是缺陷。

本模板即按此分工：`internet-test-url` 用 `connect.rom.miui.com`（被 `direct.txt` 接住），
`proxy-test-url` 用 `gstatic.com`。

#### 案例 5 · "加了 no-resolve 之后，国内网站全走代理了"

**现象**：给 IP 规则补上 `no-resolve` 之后，DNS 审计全绿，但**国内网站访问变慢**（走了代理）。

**机制**：`no-resolve` 是一把**双刃刀**。
`GEOIP,CN,DIRECT` 这条规则的能力来自"**先把域名解析成 IP，再看 IP 属不属于中国**"。
加了 `no-resolve` 之后，**它不再匹配域名了** —— 没有解析结果，IP 归属无从判断。

此时若没有一个**真正的域名类规则集**接住国内域名，它们会**整片落到 `FINAL → Proxy`**。

**修法**：确认 `FINAL` 之前有一份**含大量域名条目**的国内规则集。
⚠️ 判据是**数域名条目**，不是看规则集名字：
`ChinaMax.list` 只有 **64 条域名 / 12472 条 IP** —— 名字叫 ChinaMax，但 99.5% 是 IP，
单独引用它等于国内域名全靠 IP 判定，而 IP 判定已经被 `no-resolve` 关掉了。

本模板用 `Loyalsoldier/surge-rules` 的 `direct.txt`（**纯域名**；条数一律现抓，上游每周更新）作主承重墙。

> **这是本项目最重要的一条教训：审计全绿 ≠ 配置可用。**
> 两份审计脚本双双通过、分流却整片是坏的情况真实发生过。
> ⇒ 所以本仓库多了一个脚本：`audit_routing_coverage.py` —— 拿真实域名走一遍，
> 而且国内探针**刻意混入非 `.cn` 域名**（只靠 `DOMAIN-SUFFIX,cn` 兜住的配置会在这里暴露）。

#### 五个案例的共同点（三内核判据对照）

| 案例 | 缺陷在哪 | 能不能静态审出来 | Surge | Egern | **mihomo** |
|---|---|:---:|:--|:--|:--|
| 1 · 透明重定向 | 链路上 | ❌ 只能靠"不产生明文"来规避 | — | — | — |
| 2 · 规则缺 no-resolve | profile 里 | ✅ | `check_surge_dns.py` 第 12 项 | `check_egern_dns.py` | **判据 ⑩** |
| 3 · 规则集缺 no-resolve | **别人仓库里** | ✅ 但必须**下载下来数** | `audit_ruleset_content.py` | `audit_ruleset_noresolve.py` | ⚠️ **判不了**，只给 LOW 提示（面⑤） |
| 4 · 配置自身依赖的域名 | profile + 规则集 | ⚠️ 部分可判（远程内容未知） | 第 11 项 | 对应项 | 判据 **④**（节点域名） |
| 5 · 分流覆盖 | 规则集**内容** | ✅ 必须**拿真实域名走一遍** | `audit_routing_coverage.py` | 同左 | 同思路（差集 + 人工分类） |

⇒ 结论：**判据必须落到"实际会发生什么"上，而不是"配置里写了什么"。**

---

### 7 · 三内核语法对照

> 原理共用，**键名一律不能照抄**。目标可以照搬为「关闭 IPv6 / 端点钉 IP / 劫持 :53」，
> 但把 Surge 的 `ipv6-vif` 或 mihomo 的 `dns.ipv6` 搬到另一个内核是**无意义的**（甚至被判负）。

| 语义 | Surge | Egern | mihomo（clash） |
|:--|:--|:--|:--|
| 接管 DNS 的开关 | `[General]` 里写全套 DNS 键即接管 | `dns:` 段 | **`dns.enable: true` 必须显式给**（缺省是不接管） |
| 主解析器（加密） | `encrypted-dns-server` | `dns.upstreams.<名>` | `dns.nameserver`（＋可选 `fallback`） |
| 引导 / 兜底解析器 | `dns-server`（裸 IP，**绝不写 `system`**） | `dns.bootstrap` | `dns.default-nameserver`（**必须纯 IP**） |
| 节点域名专用解析器 | 无需（走本地路径） | `dns.proxy_nameservers` ⚠️ 会绕过 `forward` | **`dns.proxy-server-nameserver`**（鸡生蛋层） |
| 直连域名专用解析器 | — | 由 `forward` 分流到 `Domestic-DNS` | **`dns.direct-nameserver`** |
| 按域换解析器 | — | `dns.forward`（`proxy_rule_set` → `value`） | **`dns.nameserver-policy`**（`rule-set:xxx`） |
| 假 IP 模式 | 默认 Fake-IP | 默认 Fake-IP | **`enhanced-mode: fake-ip` 必须显式给** |
| 跳过假 IP 的名单 | `always-real-ip` | `real_ip_domains` | **`dns.fake-ip-filter`**（`+.` ≠ `*.`） |
| 旁路设备 :53 收口 | `hijack-dns = 8.8.8.8:53, …`（**列举式**） | `hijack_dns: ['*']` | **`tun.dns-hijack: [any:53]`** ⭐ 覆盖整个地址空间 |
| 是否走路由规则 | `encrypted-dns-follow-outbound-mode = false` | — | **`respect-rules: true`**（反向：要它**跟着**规则走） |
| 关闭 IPv6 | `ipv6 = false` + `ipv6-vif = disable` | `ipv6: false` | **顶层 `ipv6: false` + `dns.ipv6: false`（两处）** |
| 地理判定依赖 | `GeoLite2-Country.mmdb` | `Country.mmdb` + `GeoLite2-ASN.mmdb` | **无 dat** —— 全部远程 `.mrs` |
| 判据脚本 | `self-conf-skills/gates/surge/check_surge_dns.py` | `self-conf-skills/gates/egern/check_egern_dns.py` | `self-conf-skills/gates/clash/check_clash_dns.py` |

⚠️ 三处最容易照抄错的地方：

1. **`hijack-dns` / `dns-hijack` 不是同一种东西**。Surge 是**列举解析器地址**，mihomo 是
   **TUN 层劫持**且 `any:53` 才叫收口。判据也不是「列了几条」——:53 的地址空间是无限的，
   逐个列举**永远列不全**。
2. **`respect-rules` 的方向与 Surge 相反**。Surge 显式关掉「解析跟着出站走」；mihomo 打开它
   是为了让发往境外 DoH 的查询按规则经代理发出（否则国内线路直连境外 :443 常被阻断）。
   ⚠️ 代价：打开后内核**强制要求**同时给 `proxy-server-nameserver`，缺了直接报错。
3. **IPv6 的关闭处数不同**：Surge 两处（`ipv6` + `ipv6-vif`）、Egern 一处（`ipv6`）、
   mihomo 两处（顶层 `ipv6` + `dns.ipv6`）—— 但**是不同语义的两处**，不是同一处的两种写法。

### 8 · mihomo 的六个专属特点

> 以下六条是 mihomo 侧**独有或与另两内核结构不同**的机制。
> 逐键行为与边界继续看 [`clash.md`](./profiles/clash.md) §13；
> 加固理由见 [`clash.md`](./profiles/clash.md)；
> 泄露面定位流程见 [`ops.md`](./ops.md)。
> 以下数字全部由 `yaml.safe_load` 解析 `clash/profiles/*.yaml` 现算（2026-10-08 复核）。

#### 8.1 四个解析器键「各管一段路」，别混用

这是 mihomo 与另两内核最大的结构差异：**解析器不是一个，而是一组，每个只管一段路**。

| 键 | 管哪条路 | 本仓取值（两份 profile 各 2 个端点） |
|:--|:--|:--|
| `default-nameserver` | **引导**：只解析其余 DNS 端点**自己的域名** | `223.5.5.5` · `119.29.29.29`（**纯 IP**） |
| `proxy-server-nameserver` | 只解析**代理节点域名**（连节点前还没有代理可用 ⇒ 鸡生蛋） | 国内 DoH 端点 |
| `direct-nameserver` | 只解析 **`DIRECT` 出站**的域名 —— 直连流量也不碰系统 DNS | 国内 DoH 端点 |
| `nameserver` | **主解析器**：需要本地解析出真实 IP 的域名 | `https://1.1.1.1/dns-query` · `https://8.8.8.8/dns-query` |

（另有 `fallback` + `fallback-filter`：主解析器失败时的退路，**仅分流版有**，
懒人版刻意不配 —— 极简单出口不做污染判定这一层。）

⚠️ **`default-nameserver` 必须纯 IP**（内核做合法性检查，且**不允许为空**）。
它本身就是"引导"用的：写成域名 ⇒ 「解析解析器」又需要一次解析，形成鸡生蛋。
且这一层**必然是明文 UDP:53**（它不能再依赖任何加密解析器，否则成环）——
所以正确的姿势不是"给它加密"，而是**让别的层都不需要引导**（端点全部写 IP 字面量）。

⇒ 判据（判据 ②/③/④）：`default-nameserver` 全 IP；`nameserver` / `fallback` 必须
**「IP 字面量 + 加密 scheme」两者同时满足**。只判前者会把 `nameserver: 8.8.8.8`
这种最坏写法判成通过 —— 那是**每一笔查询都是明文 UDP:53**，比引导面严重得多。

#### 8.2 `enhanced-mode: fake-ip` + `fake-ip-range`

```yaml
dns:
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
```

代理域名只回假 IP，**真实解析在落地侧完成** —— 本地不留答案。

`198.18.0.0/15` 是 **RFC 6815 保留段**（198.18.0.0 ~ 198.19.255.255），mihomo 默认与官方示例都用这段。

> ⚠️ **跨内核的"常识冲突"**：这个地址曾被 **Surge 侧的凭据扫描判成「真实 IP」** ——
> 那个内核不认识这个段。已加入 `DOC_NETS` 白名单（见 [`AGENTS.md`](../../AGENTS.md) §4）。
> 整合仓必须处理这类分歧：一个内核的合法保留段，是另一个内核眼里的可疑 IP。

⭐ **判据不是"基地址对不对"，而是"整段是否被包含"**（判据 ⑤）：`198.18.0.1/8` 这种写法
会一路覆盖到 198.255.x.x 的**真实地址** —— 应用会拿着"假 IP"去连真实网络。

⚠️ **fake-ip 模式下有一个必踩的坑**：`withFakeIP` 中间件对 A/AAAA **直接返回假 IP**，
请求根本走不到 `nameserver-policy`。所以**广告集必须在 `fake-ip-filter` 里再列一遍**
（判据 ⑧：两处不一致 ⇒ 有一半名字拿不到空回答，且不报错）。

#### 8.3 `nameserver-policy` 的键语法：用**单名**，不用逗号多值

```yaml
nameserver-policy:
  "rule-set:AWAvenue-Ads": rcode://success      # 广告 → 空回答
  "rule-set:Jinx-Ads": rcode://success
  "rule-set:private":                            # 私有域 → 国内 DoH
    - https://doh.18bit.cn/dns-query
  "rule-set:cn":                                 # 国内域名 → 国内 DoH
    - https://doh.18bit.cn/dns-query
```

✅ **已确认并统一（2026-10-07）**：键用**单名**形式（本仓 4 条 policy，两份 profile 一致）。

依据：**官方文档的示例只有单名**（`'rule-set:cn'`、`geosite:xxx`），
**逗号分隔多值没有任何官方依据**。此前分流版写 `rule-set:private,cn`、
懒人版写 `geosite:private,cn`，两版既不一致也无据可依；拆成两条后语义明确，
且统一用 `rule-set:` 前缀（本仓规则集都是 rule-provider，`geosite:` 无对应物，
写了反而会引入 dat 依赖 —— 见 §8.5）。

另外两条语义要点：

- **顺序即匹配顺序**（YAML mapping 在 Python 3.7+ 保持插入顺序，而这个顺序**就是 mihomo 的匹配顺序**）
  ⇒ 广告项**必须排在 `rule-set:private` / `rule-set:cn` 之前**（判据 ⑨）；
- **`policy` 优先于 `nameserver` / `fallback`**，且引用了不存在的 provider 时该条**静默消失**
  （判据 ⑧ 查死引用：不只是广告项，`rule-set:cn` 死掉 ⇒ 国内域名改用境外主解析器）。

#### 8.4 IPv6 关**两处**，不是一处

```yaml
ipv6: false          # 顶层：内核不处理 IPv6 流量本身
dns:
  ipv6: false        # dns 段：AAAA 查询直接回空应答，不往外发
```

**只关一处会漏**，而且两种漏法不同：

- 只关顶层 ⇒ DNS 仍在应答 `AAAA`，应用拿到真实地址后尝试建连，行为取决于系统栈；
- **只关 `dns.ipv6` ⇒ `AAAA` 不回，但 IPv6 通路还在，本机真实 IPv6 可能绕过 TUN 直接出网**
  ⇒ 站点测到的出口 IP 与节点不符。

⚠️ 判据用 `is not False`，**键缺失也算不过**（写成 `ipv6: no` / `ipv6: "false"` 同样判负 ——
必须是布尔真值）。这是 mihomo 与另两内核的结构差异：Surge 是 `ipv6` + `ipv6-vif`，
Egern 只要 `ipv6`。

⭐ **这条面在 Surge / Egern 侧没有对应物**，是 mihomo 特有的第六个泄露面（③′）。
它**不走 :53**，所以抓包只抓 53 抓不到它。定位与收口见
[`ops.md`](./ops.md) §6。

#### 8.5 零 dat 依赖：用 `.mrs`，不用 `geosite.dat` / `geoip.dat`

本仓 mihomo 侧**不用任何 dat 数据库** —— 分流版 20 份 `.mrs` + 5 份 `.yaml` 全部是远程集文件。

| | 原生 `GEOSITE` / `GEOIP` | 远程 `.mrs`（本仓） |
|:--|:--|:--|
| 依赖 | `geosite.dat` / `geoip.dat` + 顶层 `geox-url` | 只依赖一次 HTTP 拉取 |
| 落盘 | 无 | ✅ `path` 落盘，离线可用 |
| 体量 | 数据库全量加载 | 按需、zstd 压缩 |

⚠️ **这不排斥 `.mrs`** —— `geoip-private` / `geoip-cn` 是 MetaCubeX 的**独立远程集文件**，
与 dat 数据库无关，那正是本仓想要的形态。判据 **⑪ 只拦 dat，不拦 mrs**
（35 条坏样例注入测试专门验过这条不误伤）。

判据 ⑪ 拦的四类东西：顶层 `geox-url` / `geo-auto-update` / `geo-update-interval` ·
规则里的原生 `GEOSITE` / `GEOIP` · `nameserver-policy` 键写 `geosite:` ·
provider 的 `url` / `path` 以 `.dat` 结尾。

> ⚠️ **待确认**：`geodata-mode` / `geodata-loader` 是否同属此类，脚本未判。

#### 8.6 TUN 收口：`dns-hijack`，且只有 `any:53` 才叫收口

mihomo 的 :53 劫持挂在 **`tun` 段**，不在 `dns` 段：

```yaml
tun:
  enable: true
  stack: mips
  dns-hijack:
    - any:53
  auto-route: true
  auto-detect-interface: true
  strict-route: true
```

⭐ **判据不是「列了几条」，而是「是否覆盖 :53 的整个地址空间」**：
:53 的地址空间是无限的，逐个列举**永远不可能列全**（Surge 侧 `check_surge_dns.py` 第 3 项
踩过同一个坑：按条数判负是错的）。只有 `any:53` / `0.0.0.0:53` 才叫收口；
只列了具体解析器 ⇒ MEDIUM「列不全就漏」。

另外两个开关不能少：**`auto-route`**（没有它出站流量根本没进 TUN）与
**`strict-route`**（没有它仍有流量从物理网卡绕出去，锁不死绕行）。

⚠️ **形态差异**：`clash/override/*.js` 的输出**不该有** `tun` 段 —— 客户端（Mihomo Party /
Clash Verge）自己管 TUN，脚本只覆写策略组与规则。故审计时要带 `--override`，否则判据 ⑦ 会判负。

⚠️ **已知取舍**：`any:53` **不写协议前缀时默认 `udp://`** ⇒ 收的是 **UDP**:53。
要把 TCP:53 也收进来需另加一条 `tcp://any:53`（本仓**未加**，判据 ⑦ 给 LOW 提示）。
理由：明文 TCP 查询在现代客户端里罕见。

#### 8.7 对应判据脚本：`check_clash_dns.py`

```bash
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/lazy.yaml clash/profiles/routing.yaml
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/routing.yaml --strict   # medium 也算失败
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/routing.yaml --quiet    # 只打印汇总
python self-conf-skills/gates/clash/check_clash_dns.py override_out.yaml --override           # 覆写脚本输出形态
```

**14 项判据**，与泄露面一一对应：判据 2/3/4（面① 引导）· 3/4（面② 回退链）·
**7（面③ 旁路设备：dns-hijack 覆盖整个 :53 + strict-route）** · **10（面④ 规则判定）** ·
10/12（面⑤ 远程集内容）· **6（面③′ IPv6 两处）** · 11（零 dat）· 8/9（广告拦截双条件与顺序）。

⭐ **判别力有实测背书**：35 条坏样例注入 **35/35 全部命中预期**，对照组（两份 profile 原样）均为
exit 0 · 0 high。本仓纪律要求每条判据**真的会判负** —— 只让「好配置通过」证明不了判别力。
（坏样例写在仓库外的临时副本上，跑完即删，未改动任何被审文件。）

与另两内核脚本的两个**对齐点**：

- **豁免写在被审对象里**（`# audit-waive: <判据号> <理由>`），不写在审计器里 ——
  写在审计器里等于判据被永久削弱；写在 profile 里则每次豁免都留痕、可 grep、可复核；
- **判据是实测推导而非字符串匹配**：端点是否 IP 字面量 / 是否加密 scheme /
  provider 的 `behavior` / `fake-ip-range` 是否落在 RFC 6815 段 / `dns-hijack` 是否覆盖整个 :53。

⚠️ **边界**：它审的是**防 DNS 泄露语义**，不做网络探测（URL 可达性归
`check_remote_urls.py`）、不审结构（归 `check_structure.py` / `check_min_pair.py`）。
**审计通过 ≠ 配置可用** —— 这条是姊妹仓付出多次事故换来的结论。

---

相关：[`ops.md`](./ops.md) · [`dns.md`](./dns.md) ·
[`clash.md`](./profiles/clash.md) §13 ·
[`clash.md`](./profiles/clash.md) ·
[`ops.md`](./ops.md) ·
[`rulesets.md`](./rulesets.md) ·
[`rulesets.md`](./rulesets.md) · [`ops.md`](./ops.md)

---

## 分流与 no-resolve 必须成对交付

> 核心命题：「DNS 不泄露」和「分流正确」是同一个机制的正面和反面。
> 由原 Surge / Egern 两侧 `docs/05` 合并，机制论述三侧同源，案例与落点按内核分节。

### Surge 侧

> 本文是一次真实事故的复盘，也是本项目**最重要的一条教训**。
> 事故经过：两份审计脚本**双双通过**，分流却**整片是坏的**。

#### 1. 事故的成因

为了消掉"IP 类规则触发本地解析"这条泄露面，给所有 IP 规则补上了 `no-resolve`：

```
- GEOIP,CN,DIRECT,no-resolve        ← 补了 no-resolve
```

DNS 审计立刻全绿 —— 本地解析确实不再被触发了。**但国内网站全走代理了。**

#### 2. 机制：`no-resolve` 是一把双刃刀

`GEOIP,CN,DIRECT` 这条规则的**全部能力**来自：

```
域名 --(解析)--> IP --(查 GeoIP 库)--> 属于 CN? --是--> DIRECT
```

`no-resolve` 砍掉的正是中间那一步。没有解析结果，IP 归属**无从判断**，
这条规则对域名就**完全失效了**。

于是国内域名走到了哪里？—— 一个**真正的域名类规则集**接不住它们，它们就整片落到
`FINAL → Proxy`（或 `default`）。

```
❌ 补 no-resolve 之后，国内域名无人接住：

   GEOIP,CN,DIRECT,no-resolve    ← 不再匹配域名，形同虚设
   FINAL,Proxy                   ← 国内域名全落这里 → 走代理
```

#### 3. 审计脚本未捕获的原因

因为当时的审计脚本审的是**结构**：

| 当时的判据 | 判定 |
|---|---|
| "所有 IP 类规则都带 no-resolve 吗" | ✅ 都带了 |
| "规则顺序对吗" | ✅ `GEOIP` 在最后 |
| "策略名能解析吗" | ✅ 都能 |
| ⭐ "国内域名最终判给谁" | ❌ **当时根本没有这一项** |

⇒ **结构正确的配置可以是错的。** "配置里写了什么"与"实际会发生什么"是两件事。

#### 4. 修法：两条判据成对交付

| 判据 | 检查什么 |
|---|---|
| **A** | 所有 IP 类规则带 `no-resolve` → 消灭"规则触发解析"这条泄露面 |
| **B** | `FINAL` 之前有一份**含大量域名条目**的国内规则集 → 国内域名仍判给 `DIRECT` |

**A 和 B 必须同时成立。** 只做 A = 分流坏；只做 B = 泄露面还在。

#### 5. B 的判据是「数域名条目」，不是看名字

这是 B 最容易做错的地方。

| 规则集 | 名字暗示 | 实际内容 | 能不能独自承重 |
|---|---|:---:|:---:|
| `ChinaMax.list` | "中国大陆全量" | 64 条域名 / **12472 条 IP** | ❌ 99.5% 是 IP，而 IP 判定已被 `no-resolve` 关掉 |
| `direct.txt`（Loyalsoldier） | "直连清单" | **纯域名**（条数一律现抓） | ✅ |

`ChinaMax.list` 的仓库说明里写得很清楚：它与 `ChinaMax_Domain.list` **"需共同使用"**。
只看名字会以为一条搞定，实际上必须成对引用。

⇒ **判据必须落到"下载下来数一遍"上。** 这正是 `self-conf-skills/run/surge/audit_ruleset_content.py`
存在的原因 —— 它会把每个 `DIRECT` 规则集的域名条目数与 IP 条目数都列出来。

#### 6. 还有一个更隐蔽的坑：只测 `.cn` 会假通过

假设一份配置只靠这一条兜底：

```
DOMAIN-SUFFIX,cn,DIRECT
```

它会让**所有 `.cn` 域名**直连 —— 探针里如果全是 `.cn`，会显示 100% 通过。
但实际上 `qq.com`、`taobao.com`、`miui.com`、`bilibili.com` 这些**非 `.cn` 的国内域名**
全都走了代理。配置是坏的，测试却是绿的。

⇒ 所以 `audit_routing_coverage.py` 的国内探针**刻意混入非 `.cn` 域名**：

```
www.baidu.com     www.qq.com        www.taobao.com    www.jd.com
www.bilibili.com  www.163.com       www.zhihu.com     www.miui.com
connect.rom.miui.com                www.aliyun.com    www.huawei.com
www.iqiyi.com     www.douyin.com    www.meituan.com   …（共 17 个）
```

**测试集必须包含"能证伪配置"的样本**，否则它只是在复述配置里的假设。

#### 7. 推广：本条教训适用于任何"改动判据"的场景

事故的根因不是 `no-resolve` 这个具体参数，而是一个通用的思维错误：

> **以为"我加了一条规则"等于"我解决了问题"，而没有检查"这条规则同时破坏了什么"。**

同类风险清单（本项目已全部纳入审计）：

| 改动 | 顺带破坏了什么 | 补偿判据 |
|---|---|---|
| 给 IP 规则加 `no-resolve` | "靠解析判 IP 归属"这条直连路径 | 必须有域名类国内规则集 |
| 广告拦截改成 `pre-matching` | 策略必须**字面量** REJECT 族（不能用组） | `check_surge_dns.py` 第 10 项 |
| 端点全改成 IP 字面量 | 失去"按域名走 CDN 就近解析" | 显式豁免 + 记录取舍 |
| 移除 `always-real-ip` 的域名规则 | 游戏机 / NTP / STUN 拿假 IP | `check_surge_dns.py` 第 11 项 |

⇒ **凡是"补一个开关"，都要问一句"它同时关掉了什么"。**

### Egern 侧

> **这是本项目最贵的一条教训。**
> 「DNS 不泄露」和「分流正确」不是两个独立目标 —— 它们是**同一个机制的正面和反面**。
> 一份配置可以做到 DNS 审计全绿，同时国内网站全部走代理。

> **模板现状更新**：本文记录的是 f8 时期用 `ChinaMax_All_No_Resolve.list` 完成这次修复的实测与推导。
> 当前模板已把该规则集的 URL 换成 Loyalsoldier **`direct.txt`**（**纯域名**，零 IP 条目；数字随上游更新变动）；
> 原理完全一致 —— 「IP 规则带 `no_resolve`」必须与「一份域名条目足够多的国内直连规则集」成对交付。
> 换用纯域名规则集后，它自身不触发解析，`no-resolve` 那一半由 `geoip: CN` 承担。

#### 1. 机制：`no_resolve` 是"用解析换分流"的开关

官方 `rules` 文档原文：

> `no_resolve (bool)`，可选 —— 仅适用于 IP 类规则（`geoip`、`ip_cidr`、`ip_cidr6`、`asn`）。
> **设为 `true` 时仅匹配已解析的 IP 地址，不会触发 DNS 解析。**

反过来说：**不带 `no_resolve` 的 IP 类规则会触发一次解析** —— 这正是泄露源（见 [DNS 为什么会泄露](./dns.md#dns-为什么会泄露)）。

但很多人没注意到的是这条的**另一半**：

> **`no_resolve: true` 之后，`geoip` 不再匹配域名。**

于是产生了一个隐蔽的连锁反应：

```
原始配置的国内直连机制：
    收到域名 → 强制本地解析一次 → 判出 CN IP → DIRECT
                    ▲
                    └── 这次解析就是泄露源

加上 no_resolve: true 之后：
    ✅ 不再有强制解析  → 泄露治好
    ❌ geoip 不再匹配域名 → 这条直连路径**一起消失**
                            → 国内域名整片落到 default → 走代理
```

⇒ **补 `no_resolve` 的同一时刻，必须确认 `default` 之前有一份"域名条目足够多"的国内 DIRECT 规则集。**
这就是"成对交付"的含义。

#### 2. 事故复盘：治好泄露的那一手，把分流搞坏了

| 阶段 | 改动 | DNS 审计 | 分流 | 说明 |
|---|---|---|---|---|
| **f7** | 给 `geoip: CN` 补 `no_resolve`；换用 `Apple_All_No_Resolve.list`；显式写 `proxy_nameservers` | ✅ `check_egern_dns.py` → `0 high / 3 low / 43 ok`<br>✅ `audit_ruleset_noresolve.py` → `OK (20/20)` | ❌ **国内域名整片落 `default → Final → Proxy`** | **两个脚本双双全绿，配置却不可用** |
| **f8** | 只改一条：`ChinaMax.list` → `ChinaMax_All_No_Resolve.list` | ✅ 同上（无退化） | ✅ **15/15 国内探针命中 `DIRECT`** | 补回国内域名直连 |

**用户的原始反馈是这样的：**

> 「没有 dns 泄露了，可是国内外的分流好像出了问题……国内的网站怎么都不是直连 反而走了代理，chinamax 基本都是一些 ip 走了直连，而国内域名基本都走了 final」

这句话里其实**已经把根因说出来了**：`ChinaMax` 里"基本都是一些 IP"，所以只有 IP 形式的连接走了直连。
问题不在 DNS，而在**被引用规则集的构成**。

#### 3. 根因：规则集的名字会骗人

`ChinaMax.list` —— 这个名字听起来**最像**一份"中国域名表"。实测数据（GitHub API / `raw` / jsDelivr 三处交叉核对，均为 453,982 字节）：

| 类型 | 条数 |
|---|---|
| `IP-CIDR` | 8,251 |
| `IP-CIDR6` | 4,221 |
| `USER-AGENT` | 65 |
| **`DOMAIN-SUFFIX`** | **51** |
| **`DOMAIN-KEYWORD`** | **13** |
| `PROCESS-NAME`（Egern 未文档化） | 12 |
| `IP-ASN` | 1 |
| **合计** | **12,614** |

⇒ **IP 类 12,473 条 / 域名类只有 64 条（0.5%）。**

仓库自己的 README 写得很清楚：

> `ChinaMax.list`、`ChinaMax_Domain.list` **共同使用**。

同目录下另有：

| 文件 | 大小 | 内容 |
|---|---|---|
| `ChinaMax.list` | 454 KB | IP 为主（上面那张表） |
| `ChinaMax_Domain.list` | 1.5 MB | 纯域名 |
| **`ChinaMax_All_No_Resolve.list`** | **3.42 MB** | **111,332 域名 + 同份 12,472 IP（全带 `no-resolve`）** |

**⇒ 判据是「数域名条目」，不是看文件名，也不是看 README 标题。**

#### 4. 替换的安全性：覆盖面无损失

换规则集之前必须核对两件事：**IP 覆盖面没变**、**旧版域名全被包含**。

```bash
grep -E '^IP-CIDR' 旧.list | sed 's/,no-resolve$//' | sort -u > ipA.txt
grep -E '^IP-CIDR' 新.list | sed 's/,no-resolve$//' | sort -u > ipB.txt
diff ipA.txt ipB.txt && echo "IP 段逐条相同 ✅"

grep -E '^DOMAIN' 旧.list | sort -u > dA.txt
grep -E '^DOMAIN' 新.list | sort -u > dB.txt
comm -23 dA.txt dB.txt | wc -l    # 期望 0
```

实测结果：

| 核对项 | 结果 |
|---|---|
| IP 段（去 `,no-resolve` 后） | **12,472 条逐条相同** ✅ |
| 旧版 64 条域名 | **全部被新版包含**（差集 0）✅ |
| 新版域名条目 | **64 → 111,332** |
| 新版 IP 条目是否带 `no-resolve` | **12,473 条全部带** ⇒ 不会重新引入"为判定而强制解析" ✅ |

#### 5. 验证：一个能复现用户现象的脚本

光比对文件不够 —— 必须**拿真实域名走一遍规则链**，看它到底命中哪条、被判给什么策略。

`audit_routing_coverage.py` 就是干这个的。它的设计有两个关键点：

1. **探针域名必须"不以 `.cn` 结尾"。**
   如果探针全是 `xx.cn`，那么一条 `domain_suffix: cn` 兜底就会把它们全部救成 `DIRECT`，从而**掩盖"规则集没有域名覆盖"这个事实**。
   （懒人版原先正是这条兜底的存在地 —— 2026-09-24 已删，理由同上：`direct.txt` 本身含 `DOMAIN-SUFFIX,cn`。）
   所以脚本用的是 `jd.com` / `zhihu.com` / `163.com` / `qq.com` / `douyin.com` / `meituan.com` / `xiaohongshu.com` 这类**国内但非 `.cn`** 的域名。
2. **同时跑境外探针**，确认没有把境外域名误判成直连。

实测结果（同一份脚本跑两个版本）：

| 探针 | f7（问题版） | f8（修复版） |
|---|---|---|
| `jd.com` / `zhihu.com` / `163.com` / `qq.com` / `douyin.com` / `meituan.com` / `xiaohongshu.com` | `default → Final` ❌ | `ChinaMax_All_No_Resolve` → **`DIRECT`** ✅ |
| 国内合计 | **7/15 落 `Final`** | **15/15 `DIRECT`** |
| 境外（google / youtube / github / x / openai / netflix / wikipedia） | — | 各归其组或落 `Final`，**无误判直连** ✅ |

#### 6. 代价与取舍

| 项 | 旧 | 新 |
|---|---|---|
| 规则集大小 | 454 KB | **3.42 MB** |
| 首次加载/更新时间 | — | 略微增加（之后走缓存） |
| 内存 | — | 略微增加 |

如果感知明显变慢，有两条更轻的路子（**但都必须重跑分流审计**）：

1. 改用 `ChinaMax_Domain.list`（纯域名，1.5 MB）+ 保留 `geoip: CN` 的 IP 判定；
2. 只保留 `ChinaMax_All_No_Resolve.list`，并撤掉额外加的 `domain_suffix: cn` 那条兜底。

**回滚**：把第 44 条规则的 URL 改回 `ChinaMax.list` 即可（一行）。

#### 7. 固化下来的规则

> **任何一次动 `no_resolve`、换 `rule_set`，都必须同时跑「分流覆盖审计」。**
> 判据是**数域名条目**，不是看规则集名字。
> 三个脚本里，`check_egern_dns.py` 和 `audit_ruleset_noresolve.py` 全绿**不代表配置可用** —— 它们不检查分流。

这条规则现在写进了 `AGENTS.md` 的「加固结束的验收标准」第 6 条。

### mihomo 侧

> mihomo 侧没有留下一次可核实的、与 Surge / Egern 同量级的「审计双绿但国内分流整片坏掉」
> 独立事故；不能把姊妹内核的事故改写成 mihomo 事故。
> 可核实的历史问题是**两版漂移**：懒人版两条 `geoip-*` 都带 `no-resolve`，
> 分流版四条里只有 `geoip-private` 带，`geoip-google` / `geoip-telegram` / `geoip-cn`
> 三条缺失。当前六个规则落点（分流版 4 条、懒人版 2 条）已经全部补齐，
> 并用两道静态判据守住 `no-resolve` 落点，避免同类配置漂移重演。

#### 1. 落点：写在 `RULE-SET` 规则行尾

mihomo 把「规则集是什么」和「引用时怎么判」拆成两层：

```yaml
rule-providers:
  geoip-cn:
    behavior: ipcidr
    format: mrs
    # url / path 省略

rules:
  - RULE-SET,geoip-cn,DIRECT,no-resolve
```

这里有三个不能混淆的事实：

1. `behavior: ipcidr` 才是「这是一份 IP 段规则集」的语义依据；
2. `format: mrs` 只是远程集的存储格式，不会自动赋予 `no-resolve`；
3. `no-resolve` 写在消费 provider 的 `RULE-SET` 规则行末尾，不写进 provider 定义，
   也不是只看 `geoip-` 名字就能推断内核已经启用。

因此本仓的标准写法是：

```yaml
- RULE-SET,geoip-cn,DIRECT,no-resolve
```

不是只写：

```yaml
- RULE-SET,geoip-cn,DIRECT
```

#### 2. 源码证据：`RULE-SET` 确实接收并传递参数

此前本仓对「`no-resolve` 写在 `RULE-SET` 上是否真的有效」存疑；现在已经有
[mihomo `rules/parser.go`](https://github.com/MetaCubeX/mihomo/blob/Meta/rules/parser.go)
的源码级证据：

```go
case "RULE-SET":
    isSrc, noResolve := RC.ParseParams(params)
    parsed, parseErr = RP.NewRuleSet(payload, target, isSrc, noResolve)
```

`RC.ParseParams(params)` 解析出了 `noResolve`，随后原样传给 `RP.NewRuleSet`。
所以这不是「照搬 Clash 语法」或「待确认的猜测」：**对 `RULE-SET` 的行尾写法有效。**
同一结论也已经写入 [`profiles/<内核>.md` §9.2](./profiles/clash.md)。

#### 3. 为什么必须带：它收的是泄露面④

[`ops.md` §4](./ops.md) 把 mihomo 的泄露路径拆成五个面；
其中面④就是**规则判定触发的解析**：

```
收到域名
  ↓
走到 behavior: ipcidr 的 RULE-SET
  ↓
为了判断「目标 IP 是否落在这份网段里」先解析域名
  ↓
这次额外解析暴露了用户正要访问的站点
```

不带 `no-resolve`，IP 规则为了完成判定会主动补出目标 IP；带上以后，它只匹配已经拿到的
IP，不再为了规则判定另起一次解析。分流版的 `geoip-private` / `geoip-google` /
`geoip-telegram` / `geoip-cn`，以及懒人版的 `geoip-private` / `geoip-cn`，
provider 均为 `behavior: ipcidr`、`format: mrs`，所以六个引用落点都必须带。

但双刃刀的另一面没有改变：`no-resolve` 也会切断「先把域名解析成 IP，再靠 IP 集分流」
这条路径。对国内直连而言，正确结构仍然必须是：

```yaml
- RULE-SET,cn,DIRECT
- RULE-SET,geoip-cn,DIRECT,no-resolve
- MATCH,Proxy
```

`cn` 是域名类 provider，负责接住域名；`geoip-cn` 是 IP 类 provider，只兜已经是 IP 的连接；
`MATCH` 才是最终兜底。两者分工后，才同时得到：

| 判据 | mihomo 侧的落地 |
|---|---|
| **A · 不泄露** | 所有 `behavior: ipcidr` 的引用都带 `no-resolve` |
| **B · 分流不坏** | `MATCH` 前保留域名类国内直连集 `RULE-SET,cn,DIRECT` |

**只满足 A，仍可能复刻 Surge / Egern 的事故；只满足 B，面④仍然开着。**

#### 4. 本仓现状：4 条 + 2 条，已经统一

逐项核对现役 [`routing.yaml`](../../clash/profiles/routing.yaml) 与
[`lazy.yaml`](../../clash/profiles/lazy.yaml)：

| profile | provider | behavior / format | 现役规则 | 结果 |
|---|---|---|---|:---:|
| 分流版 | `geoip-private` | `ipcidr` / `mrs` | `RULE-SET,geoip-private,DIRECT,no-resolve` | ✅ |
| 分流版 | `geoip-google` | `ipcidr` / `mrs` | `RULE-SET,geoip-google,Google,no-resolve` | ✅ |
| 分流版 | `geoip-telegram` | `ipcidr` / `mrs` | `RULE-SET,geoip-telegram,Telegram,no-resolve` | ✅ |
| 分流版 | `geoip-cn` | `ipcidr` / `mrs` | `RULE-SET,geoip-cn,DIRECT,no-resolve` | ✅ |
| 懒人版 | `geoip-private` | `ipcidr` / `mrs` | `RULE-SET,geoip-private,DIRECT,no-resolve` | ✅ |
| 懒人版 | `geoip-cn` | `ipcidr` / `mrs` | `RULE-SET,geoip-cn,DIRECT,no-resolve` | ✅ |

数字口径是**每份 profile 内的规则行数**：分流版 4 条，懒人版 2 条；不是把同名 provider
跨版本去重后的数量。此前的差异也要准确表述：分流版不是「4 条全缺」，而是
`geoip-private` 已带、其余 **3 条缺**；懒人版 **2 条一直都带**。现在两版规则已统一为
「凡 `geoip-*` / `ipcidr` 引用，全部带 `no-resolve`」。

#### 5. 判据固化：一层看名字，一层看真实语义

本仓没有靠文档提醒维持现状，而是把缺口写进了两个门禁：

1. [`check_structure.py`](../gates/clash/check_structure.py) **第 ⑤ 项**：
   遍历 `RULE-SET,geoip-*`，任一规则缺 `no-resolve` 就判负。它针对本仓命名约定，
   能直接阻止「分流版又漏三条」这类漂移。
2. [`check_clash_dns.py`](../gates/clash/check_clash_dns.py) **判据 10**：
   判断 IP 类规则时以 provider 的 `behavior` 为第一依据；`behavior: ipcidr` 必须带，
   `behavior: domain` 不该带，`behavior: classical` 则标成内容无法静态判定。
   只有 provider 没声明 `behavior` 时，才退回 `geoip-` 名字前缀兜底。

这两层不是重复劳动：第 ⑤ 项守本仓结构约定，判据 10 守实际匹配语义。
当前实跑结果为：结构门禁四份 profile 全部通过；DNS 审计中分流版报告
「4 条 IP 类规则全部带 `no-resolve`」，懒人版对应为 2 条，两版均为 `0 high`。

但这里必须保留事故复盘最重要的边界：**这两道静态门禁只证明 A，不自动证明 B。**
本仓已有 mihomo 侧的分流覆盖审计脚本（`self-conf-skills/run/clash/audit_routing_coverage.py`，闸门 #9）；但每次增删 `no-resolve`、替换 `cn`
provider 或移动 `MATCH` 前规则时，还必须同时核对：

- `cn` 仍是 `behavior: domain` 的国内域名集；
- `RULE-SET,cn,DIRECT` 仍在 `MATCH,Proxy` 之前；
- 用国内非 `.cn` 域名做分流验证，不能只测会被后缀兜底救活的样本。

不能把「两道门禁全绿」再次误读成「配置一定可用」—— 这正是本文要跨内核保留下来的教训。

### 三侧对照：语法不同，成对交付的机制相同

| 内核 | 开关拼写与落点 | IP 侧示例 | 域名补偿必须落在 |
|---|---|---|---|
| Surge | 连字符 `no-resolve`，写在 IP 规则行尾 | `GEOIP,CN,DIRECT,no-resolve` | `FINAL` 前的国内域名规则集 |
| Egern | 下划线 `no_resolve: true`，写在结构化 IP 规则对象内 | `- geoip: {match: CN, policy: DIRECT, no_resolve: true}` | `default` 前的国内域名 `rule_set` |
| mihomo | 连字符 `no-resolve`，写在消费 provider 的 `RULE-SET` 行尾 | `RULE-SET,geoip-cn,DIRECT,no-resolve` | `MATCH` 前的 `RULE-SET,cn,DIRECT` |

三侧共同的机制可以压成一句话：

> **IP 规则不得为判定主动解析；关掉这条路以后，域名分流必须由真正的域名规则集接手。**

因此评审任何一侧时，都不能只搜开关字符串。必须同时问：

1. 这个开关是否落在内核真正读取的位置？
2. 被关掉的「域名 → IP → 归属」路径，由哪份域名规则集补回？
3. 审计是在检查结构，还是已经用能证伪的域名验证了最终去向？

---

下一步：[操作：Surge · Egern · 日常维护](./ops.md)。
