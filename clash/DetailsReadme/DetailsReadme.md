# Clash 配置模板 · 完整技术文档

> 面向想彻底弄明白「为什么这么写」的读者。
> 只想赶紧用起来 → 直接看 [`README`](../README.md) 的两份配置。
>
> 目录
> [1 · 先定义「泄露」](#1--先定义泄露) ·
> [2 · 明文查询从哪来：三条出口](#2--明文查询从哪来三条出口) ·
> [3 · `dns` 段逐键](#3--dns-段逐键) ·
> [4 · `tun` 段：收口装置](#4--tun-段收口装置) ·
> [5 · 明文泄露面实测](#5--明文泄露面实测) ·
> [6 · 已知代价与取舍](#6--已知代价与取舍)
>
> 🔜 本文目前覆盖 `dns` / `tun` 两段（防泄露本体）。分流版设计、占位符与脱敏规则等章节随配置落地补齐；
> 规则集清单、来源与刷新机制已由 [`docs/01-规则集与来源.md`](../docs/01-规则集与来源.md) 承接。

---

## 1 · 先定义「泄露」

本文所说的 DNS 泄露，**不是**「请求加密了没有」，也不是「权威服务器知道你是谁」。定义收紧到一条：

> 设备发出的、能被链路上的第三方（运营商 / Wi-Fi 提供者 / 旁路设备）直接读到的
> **明文 DNS 查询**，存在任何一条「必然会被走到」的通路。

「必然会被走到」是关键。一个只在极端条件下才发生的明文查询，和每 5 分钟发生一次的明文查询，风险量级完全不同 —— 但配置语法上它们看起来一样。

---

## 2 · 明文查询从哪来：三条出口

mihomo 的 DNS 是**内核内建**型：解析器在 `dns` 段指定，查询入口在 `tun` 段收口。明文 `UDP:53` 的出口有三条。

### 2.1 出口 ①：应用直发明文查询

应用（尤其是移动端 App 与 IoT 设备）无视系统设置，直接向 `8.8.8.8:53` 发查询。这既是泄露，也常常是「设备能用但很慢」的原因 —— 境外解析器在国内链路上时通时不通。

**对策**

```
tun:
  auto-route: true        # 自动接管路由表
  strict-route: true      # 流量无法绕开 TUN
  dns-hijack:
    - any:53              # 命中 :53 的连接交给内核 DNS 模块，而不是往外发
```

三者叠加，应用自己发的明文查询会被内核接管并就地应答。语义细节见 §4。

### 2.2 出口 ②：代理域名的本地真实解析

`enhanced-mode: real-ip`（mihomo 默认）下，本机自己把域名解析成真实 IP，再把 IP 交给代理 —— 那么「本机向谁解析」本身就是泄露面。

**对策**

```
enhanced-mode: fake-ip
fake-ip-range: 198.18.0.1/16
```

命中代理的域名只回一个 `198.18.0.0/16` 段的**假 IP**，真实解析在落地侧（代理出口）完成，本地压根不产生这次真实查询。假 IP 与域名的映射由内核维护，回程按映射表还原，应用侧无感。

**例外**：部分域名拿到假 IP 会直接失效 —— NTP、游戏机联网探测、局域网域名、微软连通性探测。这些需要在 `fake-ip-filter` 里逐个列出，让它们跳过 fake-ip、走真实解析。见 §3.2。

### 2.3 出口 ③：节点域名解析打转

代理节点的 `server` 写成域名时有个死循环：

```
要连代理 → 得先解析节点域名 → 但这时候还没有代理可用 → 只能明文解析
```

**对策**：`proxy-server-nameserver` 单独承担这件事，与主解析器分离，避免「连节点的解析」和「走节点的解析」互相污染。见 §3.1。

### 2.4 三处收口之后

| 出口 | 收口手段 |
|:----:|:---------|
| ① 应用直发 | `auto-route` + `strict-route` + `dns-hijack` |
| ② 本地真实解析 | `enhanced-mode: fake-ip` |
| ③ 节点域名 | `proxy-server-nameserver` 单列 |

再加一条结构保障：需要解析的键全部写成加密端点（见 §3.1），所以「为了解析某个 DNS 端点而先发明文查询」这条引导通路只可能落在 `default-nameserver` 上（见 §6）。

注意措辞：是「没有必然通路」，不是「绝对零明文」。一个从没访问过的域名、一次极端网络切换，仍可能产生零星明文。**任何声称「绝对零泄露」的配置都在夸大。**

---

## 3 · `dns` 段逐键

| 键 | 值 | 作用 |
|:--|:--|:--|
| `enable` | `true` | 启用内核 DNS 模块 |
| `ipv6` | `false` | `AAAA` 查询由内核直接回**空应答**，不往外发 |
| `listen` | `0.0.0.0:7874` | 内核 DNS 服务的监听地址，供局域网设备直接指向 |
| `enhanced-mode` | `fake-ip` | 代理域名只回假 IP |
| `fake-ip-range` | `198.18.0.1/16` | 假 IP 段 |
| `prefer-h3` | `false` | DoH 只用 HTTP/1.1 与 HTTP/2，不尝试 HTTP/3 |
| `respect-rules` | `true` | DNS 查询自身也走路由规则 |
| `use-hosts` | `true` | 优先查配置里的 `hosts` |
| `use-system-hosts` | `false` | 不读系统 hosts 文件 |
| `fake-ip-filter` | 15 条 | 跳过滤假的域名清单 |
| `default-nameserver` | `223.5.5.5` · `119.29.29.29` | 引导解析器 |
| `proxy-server-nameserver` | 国内 DoH ×2 | 节点域名 |
| `direct-nameserver` | 国内 DoH ×2 | `DIRECT` 出站域名 |
| `nameserver` | 境外 DoH ×2 | 主解析器 |
| `nameserver-policy` | `geosite:private,cn` → 国内 DoH | 按域名换解析器 |

### 3.1 五个解析器键的分工

mihomo 的解析器不是一个，而是各管一段路。混用会让「本不该走代理的域名」或「本不该在本机解析的域名」走错路。

| 键 | 管哪条路 | 本配置的值 |
|:--|:--|:--|
| `nameserver` | 主解析器 —— 需要本地解析出真实 IP 的域名 | 境外 DoH：`dns.cloudflare.com` · `dns.google` |
| `nameserver-policy` | 按域名换解析器（优先于 `nameserver`） | `geosite:private,cn` → 国内 DoH |
| `proxy-server-nameserver` | 代理节点域名（出口 ③） | 国内 DoH：`223.5.5.5` · `120.53.53.53` |
| `direct-nameserver` | `DIRECT` 出站的域名 —— 直连流量也不碰系统 DNS | 国内 DoH：同上 |
| `default-nameserver` | 解析**其他 DNS 服务器自身的域名** | 纯 IP：`223.5.5.5` · `119.29.29.29` |

**为什么 `default-nameserver` 必须是纯 IP**：它本身就是「引导」用的。写成域名，就又需要一次解析，循环回来了。内核对这个键做合法性检查（拆分端口后 host 必须是 IP），并且显式跳过 `system`；该键也不允许为空。

**为什么需要 `nameserver-policy` 这条**：主解析器是境外 DoH，而 `geosite:private,cn`（私有域 + 中国大陆域名）交给境外解析会得到不合用的答案（CDN 调度到境外节点、甚至解析失败），所以这一档单列回国内 DoH。

### 3.2 `fake-ip-filter`：15 条过滤项与通配语义

| 类 | 条目 | 拿到假 IP 的后果 |
|:--|:--|:--|
| 🏠 局域网 | `*.lan` · `*.local` · `*.localdomain` · `*.home.arpa` | 局域网设备不在代理链路里，假 IP 直接连不上 |
| 🪟 微软联网探测 | `+.msftconnecttest.com` · `+.msftncsi.com` | 探测失败 → 系统判定「无 Internet」并限制联网 |
| 🎮 游戏机 | `+.srv.nintendo.net` · `+.stun.playstation.net` · `+.xboxlive.com` | 联网检测与 NAT 类型判定失败 |
| 🕐 NTP / STUN | `stun.*` · `time.*.com` · `ntp.*.com` · `+.pool.ntp.org` | 时间同步走假 IP 直接失败 |
| 🧩 其他 | `localhost.ptlogin2.qq.com` · `+.market.xiaomi.com` | 登录与应用商店的本地连通性检测 |

**通配语义**（mihomo v1.19.31 实测，`fake-ip-filter` 置入 `+.example.com` / `time.*.com` / `*.lan` 后逐名查询）：

| 模式 | 命中 | 不命中 | 结论 |
|:--|:--|:--|:--|
| `+.example.com` | `example.com` · `a.example.com` · `a.b.example.com` | — | 本域**与**任意层子域 |
| `time.*.com` | `time.a.com` | `time.a.b.com` | `*` 只匹配**一层** |
| `*.lan` | `x.lan` | `a.b.lan` | `*.` 只匹配**一层** |

⚠️ 由此得到一条边界：`*.lan` / `*.local` 只覆盖一层子域，像 `a.b.lan` 这样的多层名字**不会**被过滤。局域网里若有嵌套域名，需要按需补 `+.lan` 这类写法。

命中的域名会**真的去走一次本地真实解析**（用的是主解析器，即加密端点）—— 这是「出口 ②」的代价面，属于设计已知。

### 3.3 `respect-rules: true` 的连带要求

打开后 DNS 查询自身也受路由规则管辖 —— 好处是发往境外 DoH 的查询会按规则经代理发出。代价是内核**强制要求**同时给出 `proxy-server-nameserver`，缺了直接报错：

```
if "respect-rules" is turned on, "proxy-server-nameserver" cannot be empty
```

（离线门禁 `mihomo -t` 会拦下这一条。）

---

## 4 · `tun` 段：收口装置

| 键 | 值 | 作用 |
|:--|:--|:--|
| `enable` | `true` | 启用 TUN |
| `stack` | `mips` | IP 协议栈实现，可选 `system` / `gvisor` / `mixed` / `mips` |
| `auto-route` | `true` | 自动接管路由表 |
| `auto-detect-interface` | `true` | 自动识别出接口 |
| `strict-route` | `true` | 流量无法绕开 TUN |
| `dns-hijack` | `any:53` | 命中 `:53` 的连接交给内核 DNS 模块 |

**`dns-hijack` 的语义细节**：不写协议前缀时默认 `udp://`，即 `any:53` 收的是 **UDP**:53。要把 `TCP:53` 也收进来，需要另外加一条 `tcp://any:53`（本配置未加 —— 明文 TCP 查询在现代客户端里已属罕见）。

---

## 5 · 明文泄露面实测

**方法**：`default-nameserver` 是本配置里唯一还会走明文 `UDP:53` 的键（见 §6）。把它顶到一个本机 DNS sink 上（`127.0.0.1`，记录每个查询的名字与类型）再跑真实解析 —— 内核每一次明文引导都会落到 sink，明文泄露面就变成一份**可枚举的域名清单**。全程 TUN 关闭、只监听回环地址，明文查询不出网。

| 用例 | sink 收到的明文查询 | 涉及域名 |
|:--|:--|:--|
| 基线（`nameserver` 为域名形式 DoH） | 34 条 | 只有 `dns.google` · `dns.cloudflare.com` |
| 重跑（复现性） | 34 条 | 同上 |
| `nameserver` 改为 IP 形式 DoH | 0 条 | 无 |
| DoH 端点不可达 | 0 条 | 无 —— 业务域名解析失败，**不回退明文** |

内核日志里两条并排出现，就是结论本身：

```
[DNS] resolve dns.google A from udp://127.0.0.1:15353                               ← 明文，只有端点自己
[DNS] resolve www.google.com A from https://dns.cloudflare.com:443/dns-query        ← 业务域名，加密
```

**判定**：明文只剩「解析 DoH 端点自身」这一条设计上已知的引导，不含任何业务域名、节点域名、内网域名；把 `nameserver` 换成 IP 形式的端点可做到**零明文**；DoH 全部不可用时不回落明文。

> 两项与泄露无关的观测：`AAAA` 查询会被内核对同一域名重复发起（噪音，不是泄露）；`192.0.2.0/24`（TEST-NET-1）会被内核的 GeoIP 库判为 `private`、命中 `GEOIP,private` 走 `DIRECT` —— 拿保留段做「黑洞」故障注入不干净，要造不可达得用真连不上的公网端口。

---

## 6 · 已知代价与取舍

| 项 | 代价 | 为什么接受 |
|:--|:--|:--|
| `default-nameserver` 走明文 UDP | 明文暴露「在用哪家 DoH」，不含业务域名 | 它是引导解析，端点写成域名时必然需要一次明文；把 `nameserver` 换成 IP 形式端点可完全消除 |
| `GEOIP,private` / `GEOIP,cn` 不带 `no-resolve` | 走到这两条规则的域名会多触发一次本地解析 | 本地解析走的是加密解析器，不产生明文；代价只是首个请求多一次解析耗时 |
| `stack: mips` | mihomo 自研协议栈，有些场景不如 `gvisor` 稳 | 常规使用足够；遇到兼容性问题换成 `gvisor` 即可 |
| `*.lan` / `*.local` 只覆盖一层子域 | 多层局域网名字不走过滤、会拿到假 IP | 常见 mDNS 名字是单层；需要时改用 `+.lan` |
