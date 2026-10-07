# Surge 配置模板 · 逐键语义与内核行为（profile-anatomy）

> **何时读**：改 Surge 配置需要确认某个键 / 组 / 规则的语义与边界时。本文件原为 `surge/DetailsReadme/DetailsReadme.md`，2026-09-27 起并入 skill。

> 面向想彻底弄明白「为什么这么写」的读者。
> 只想赶紧用起来 → 看 [`README`](../../../README.md) 的 [📥 两份配置](../../../README.md#-两全其美--皆合心意)。
>
> 目录
> [1 · 文件结构与两份形态](#1--文件结构与两份形态) ·
> [2 · 防泄露原理：从机制到推导](#2--防泄露原理从机制到推导) ·
> [3 · `[General]` 逐键](#3--general-逐键) ·
> [4 · `[Proxy]` 与占位符](#4--proxy-与占位符) ·
> [5 · 占位符与脱敏规则](#5--占位符与脱敏规则) ·
> [6 · `smart` / `select` 组的差别](#6--smart--select-组的差别) ·
> [7 · `underlying-proxy` 中转链](#7--underlying-proxy-中转链) ·
> [8 · `pre-matching` 与 `extended-matching`](#8--pre-matching-与-extended-matching) ·
> [9 · `always-real-ip` 与 Fake-IP](#9--always-real-ip-与-fake-ip) ·
> [10 · `hijack-dns` 的边界](#10--hijack-dns-的边界) ·
> [11 · 规则集与刷新](#11--规则集与刷新) ·
> [12 · `no-resolve` 的双刃](#12--no-resolve-的双刃) ·
> [13 · `[Proxy Group]`：组结构与两处「不能用组」的地方](#13--proxy-group组结构与两处不能用组的地方) ·
> [14 · `[Rule]`：两版规则顺序](#14--rule两版规则顺序) ·
> [15 · 审计体系](#15--审计体系) ·
> [16 · 已知取舍](#16--已知取舍) ·
> [17 · FAQ](#17--faq) ·
> [18 · 维护者须知](#18--维护者须知)

## 0 · 目录

| # | 节 | # | 节 |
|:-:|:---|:-:|:---|
| 1 | 文件结构与两份形态 | 10 | `hijack-dns` 的边界 |
| 2 | 防泄露原理：从机制到推导 | 11 | 规则集与刷新 |
| 3 | `[General]` 逐键 | 12 | `no-resolve` 的双刃 |
| 4 | `[Proxy]` 与占位符 | 13 | `[Proxy Group]`：组结构与两处「不能用组」的地方 |
| 5 | 占位符与脱敏规则 | 14 | `[Rule]`：两版规则顺序 |
| 6 | `smart` / `select` 组的差别 | 15 | 审计体系 |
| 7 | `underlying-proxy` 中转链 | 16 | 已知取舍 |
| 8 | `pre-matching` 与 `extended-matching` | 17 | FAQ |
| 9 | `always-real-ip` 与 Fake-IP | 18 | 维护者须知 |

## 1 · 文件结构与两份形态

```
Self-Configuration/                          # 两内核合并后同仓（2026-09-23）
├── surge/                                   # 本文档讲的这一侧
│   ├── profiles/                            # 固定名四件（当前版恒为 lazy / routing，升版不改名）
│   │   ├── lazy.conf · lazy.min.conf        # 懒人版（带注释 / 纯配置，注释剥掉那份）
│   │   ├── routing.conf · routing.min.conf  # 分流版（带注释 / 纯配置，注释剥掉那份）
│   │   └── config_old/                      # 历史版本归档（成对快照，永不删除）
│   └── （原 docs/ 与 DetailsReadme/ 已并入 skill/，2026-09-27，git 历史可查）
├── egern/                                   # 姊妹内核一侧（同构：profiles / skill/reference/egern）
├── icons/                                   # 策略组图标 PNG + 两个图标订阅 JSON —— 仓库根，两内核共用、不跨项目引用
├── LICENSE · SECURITY.md · README.md        # 许可证 · 安全披露 · 门面（订阅入口 + 指路）
└── skill/                                   # AI 知识库（本仓唯一文档区）
    ├── SKILL.md                             # AI 唯一入口：六条底线 / 归档机制 / 动线 / 分支索引
    ├── reference/                           # 逐条判据（shared/ 七篇 + surge/ · egern/ 各七篇）
    ├── scripts/                             # surge/ 5 个审计脚本 + 1 个共享模块 · egern/ 10 个 + 1 个
    └── tests/                               # 五个闸门脚本（secrets / portability / min_pair / links / make_min）
```

**两份配置是分工关系，不是版本关系**：`lazy` 是懒人版（4 组 / 10 条，全量一个出口），
`routing` 是分流版（24 组 / 24 条，按应用 + 按地区）。选一份用，不要叠加。
分流版的设计约束（`flatten` 的对应写法、Smart 组不能嵌套组、地区关键词双份）原见
`docs/11-分流版设计.md`（已随 2026-09-27 仓库精简移除）。

### 1.1 两份形态的由来

| 形态 | 给谁 | 特点 |
|:-----|:-----|:-----|
| `.conf` | 想读懂的人 | 每个键上方有理由；结构分段带标题 |
| `.min.conf` | 只想导进去的人 / 机器处理 | 同内容，无注释，行数少一半 |

两者**内容必须一致，只差注释**。这条由 `skill/tests/check_min_pair.py` 的对拍判据兜底
（比对 16 个 DNS 相关键的逐字相等）。

> ⚠️ `.min.conf` 里仍保留 `# audit-waive:` 那行 —— 它是**有语义的注释**，不是说明文字。
> 删掉它，审计读数就从「2 waived」变成「2 high」。

## 2 · 防泄露原理：从机制到推导

### 2.1 先定义「泄露」

本文所说的 DNS 泄露，**不是**「DNS 请求被加密了没有」，也不是「权威服务器知道你是谁」。
定义收紧到一条：

> **设备发出的、能被链路上的第三方（运营商 / Wi-Fi 提供者 / 旁路设备）直接读到的
> 明文 DNS 查询，存在任何一条「必然会被走到」的通路。**

「必然会被走到」是关键。一个只在极端条件下才会发生的明文查询，和每 5 分钟发生一次的
明文查询，风险量级完全不同 —— 但配置语法上它们看起来一样。

### 2.2 明文查询从哪来：三条出口

#### 出口 ①：引导解析（bootstrap）

DoH / DoT 端点写成一个**主机名**时，会出现一个循环：

```
要用 DoH 查 dns.google 的 IP
  → 但得先知道 dns.google 的 IP 才能建 DoH 连接
    → 于是先用明文 DNS 查一次 dns.google 的 IP
      → 这一步就是泄露
```

这不是实现缺陷，是协议固有的先有鸡先有蛋。**唯一彻底的解法是端点写 IP 字面量**，
让循环不存在。

`dns-server` 同理：它承担引导解析职责，如果写成 `system`，等于把这一步交给
运营商 DHCP 下发的那台解析器 —— 那正是要消除的对象。

**配置里的对策**

```
dns-server = 223.5.5.5, 119.29.29.29, 1.1.1.1, 8.8.8.8     # 裸 IP，不是 system
encrypted-dns-server = https://1.1.1.1/dns-query, …        # 至少一个 IP 字面量
```

`encrypted-dns-server` 里保留了 `https://dns.google/dns-query` 与
`https://dns.alidns.com/dns-query` 两个主机名端点 —— 这是**刻意的取舍**（见 §16），
已在 profile 内用 `# audit-waive: 1` 声明。

#### 出口 ②：旁路设备

HomePod、Apple TV、Chromecast、智能音箱、部分 IoT 设备**不使用** Surge 的 DNS
（它们有自己的硬编码解析器，通常是 `8.8.8.8`），发出的就是明文 `UDP:53`。

这些查询会穿过 Surge 的 TUN 接口。**默认情况下 Surge 不管它们** —— 它们直接到
硬编码的那台境外解析器。这既是泄露，也常常是「设备能用但很慢」的原因
（境外解析器在国内链路上时通时不通）。

**配置里的对策**

```
hijack-dns = 8.8.8.8:53, 8.8.4.4:53, 1.1.1.1:53, 1.0.0.1:53, 9.9.9.9:53, 208.67.222.222:53
```

把这些地址的 `:53` 查询接管回来，走 Surge 的加密 DNS。
想一网打尽可以写 `hijack-dns = *`（Surge 官方示例值），代价是所有 `:53`
查询都进 Surge 处理，极少数依赖原生 `:53` 行为的应用可能受影响。

#### 出口 ③：规则触发解析

这是最隐蔽的一条。**不带 `no-resolve` 的 IP 类规则会主动发起 DNS 解析**：

```
GEOIP,CN,DIRECT          ← 没有 no-resolve
```

Surge 求值到这条规则时，如果请求只是一个域名（还没有 IP），它会**先做一次 DNS 查询**
拿到 IP，再拿这个 IP 去查 GeoIP 库。

关键在于：**这次解析走的是 Surge 的 DNS 客户端**，所以它本身是加密的、不泄露。
但它的存在会带来两个后果：

1. 每个走到这条规则的域名都要等一次解析 —— 表现为「首个请求卡一下」；
2. 在启动早期（加密 DNS 还没就绪）或加密 DNS 不可达时，这次解析会**回退明文**。

**配置里的对策**

```
GEOIP,CN,DIRECT,no-resolve
RULE-SET,LAN,DIRECT,no-resolve
RULE-SET,…,private.txt,DIRECT,no-resolve
RULE-SET,…,direct.txt,DIRECT,no-resolve
RULE-SET,…,AI.list,…,no-resolve
```

⚠️ 但 `no-resolve` 有代价，见 §12 —— 这是本模板最需要注意的一处。

### 2.3 三处收口之后

| 出口 | 收口手段 |
|:----:|:---------|
| ① 引导 | 端点写 IP 字面量；`dns-server` 写裸 IP |
| ② 旁路 | `hijack-dns` 接管 |
| ③ 规则 | 所有 IP 类规则带 `no-resolve` |

三者叠加，明文 `UDP:53` 没有任何一条通路是「必然会被走到」的。
注意措辞：是「没有必然通路」，不是「绝对零明文」——
一个从没访问过的域名、一次极端网络切换，仍可能产生零星明文。**任何声称
"绝对零泄露"的配置都在夸大**。

## 3 · `[General]` 逐键

### 3.1 DNS 段（防泄露本体）

| 键 | 值 | 为什么 |
|:---|:---|:-------|
| `dns-server` | `223.5.5.5, 119.29.29.29, 1.1.1.1, 8.8.8.8` | 引导与连通性测试。**绝不用 `system`**。前两个是国内（快、稳），后两个境外（用于验证加密 DNS 前的连通性） |
| `encrypted-dns-server` | `1.1.1.1` + `dns.google` + `dns.alidns.com` | 三个不同机构，任一故障有退路。1 个 IP 字面量保证冷启动可用 |
| `encrypted-dns-follow-outbound-mode` | `false` | 见下 |
| `hijack-dns` | 6 个境外解析器的 `:53` | 出口 ② |
| `allow-dns-svcb` | `false` | 不向应用下发 HTTPS/SVCB 记录。开启会让应用绕过 Surge 的部分解析路径 |
| `exclude-simple-hostnames` | `true` | 单标签主机名（`nas`、`router`）直接交给系统解析，不产生查询 |
| `read-etc-hosts` | `true` | 尊重本机 hosts |
| `use-local-host-item-for-proxy` | `false` | 见下 |

**`encrypted-dns-follow-outbound-mode` 为什么必须 `false`**

设成 `true` 时，DoH 连接自己也要遵循代理规则。若代理规则里这个解析器域名指向代理，
就形成「要解析它 → 需要它 → 要解析它」的环。Surge 会检测并回退明文，等于泄露。

**`use-local-host-item-for-proxy` 为什么必须 `false`**

`[Host]` 段与 `read-etc-hosts` 提供的本地映射只服务 DIRECT 路径。
一旦开启，本地 DNS 结果会变成**硬性的代理目标** —— 走代理的域名应该由节点侧
根据地理位置解析（CDN 就近），本地给它一个答案反而会把它钉在错误的 IP 上。

### 3.2 IPv6

| 键 | 值 | 为什么 |
|:---|:---|:-------|
| `ipv6 = false` | 不向客户端返回 AAAA 记录，双栈站点自动回落 IPv4 | 封堵面与 Egern 内核等效（Egern 默认不启用 IPv6），AAAA 绕过面收窄；2026-09-29 实测不影响 DNS 泄露面，官方对无 v6 需求的用户亦建议关闭 |
| `ipv6-vif = disable` | VIF 不再承载任何 IPv6 路径 | IPv6 已关，VIF 承载 v6 无意义；写 `auto`/`true` 会与 `ipv6 = false` 的语义打架 |

### 3.3 GeoIP

| 键 | 值 |
|:---|:---|
| `geoip-maxmind-url` | `adysec/IP_database` 的手工构造 `GeoLite2-Country.mmdb` |
| `disable-geoip-db-auto-update` | `false`（保持自动更新） |

手动构造的 mmdb 不一定带 MaxMind 官方签名，Surge 可能报警。当前配置保持更新开启；
若日志出现更新报错，把它改成 `true` 即可（代价是库会变旧）。

### 3.4 测试端点

| 键 | 值 | 为什么 |
|:---|:---|:-------|
| `test-timeout` | `5` | 5 秒足够区分「慢」和「坏」 |
| `internet-test-url` | `connect.rom.miui.com/generate_204` | 国内 204，低方差 |
| `proxy-test-url` | `www.gstatic.com/generate_204` | 保持源配置的境外端点**不改** —— 取向理由见 §16.1 |
| `proxy-test-udp` | `apple.com@1.1.1.1` | `smart` 组的 UDP 评分要用；`1.1.1.1` 是 IP 字面量，不产生解析 |

### 3.5 流量处理

| 键 | 值 | 为什么 |
|:---|:---|:-------|
| `udp-policy-not-supported-behaviour` | `reject` | `https` 类型节点不支持 UDP 中继（见 §4.3）。落到这类节点上的 UDP 直接拒绝，语义清晰 |
| `udp-priority` | `true` | 系统繁忙时优先处理 UDP（游戏、视频通话受益） |
| `block-quic` | `per-policy` | 默认阻止 QUIC，只在策略明确支持时放行。QUIC 走 UDP，绕过 TCP 类规则会导致分流失效 |

### 3.6 局域网与安全

| 键 | 值 | 为什么 |
|:---|:---|:-------|
| `allow-wifi-access` / `allow-hotspot-access` | `false` | 局域网设备的共享出口由专用网关承担，本机不再开放监听端口，暴露面直接归零 |
| `proxy-restricted-to-lan` / `gateway-restricted-to-lan` | `true` | **安全项**：监听端口万一重新启用时，即使上级网络 DMZ / 端口转发配得潦草也不会暴露到当前子网之外 |

### 3.7 Wi-Fi / 蜂窝

| 键 | 值 | 为什么 |
|:---|:---|:-------|
| `all-hybrid` | `false` | `true` 会让**每条 TCP 连接和每次 DNS 查询**同时走 Wi-Fi + 蜂窝 —— 明确的耗电与流量代价 |
| `wifi-assist` | `false` | Wi-Fi 弱时自动切蜂窝，会打断代理连接 |

### 3.8 `always-real-ip`

```
always-real-ip = *.lan, *.local, *.localdomain, *.home.arpa,
                 *.srv.nintendo.net, *.stun.playstation.net, *.xboxlive.com,
                 stun.*, time.*.com, ntp.*.com, *.pool.ntp.org, *.market.xiaomi.com
```

两类：

- **本地类**（`*.lan` / `*.local` / `*.home.arpa`）—— 局域网设备必须拿真实地址
- **功能类**（游戏机 / STUN / NTP）—— NAT 类型检测与时间同步需要真实可路由地址

⚠️ `always-real-ip` **只改变返回真实 IP 还是 Fake-IP，不改变流量的目的地**。
它不参与分流 —— 想让游戏机流量走代理，还得靠 `[Rule]` 里的 `DOMAIN-SUFFIX` 规则。

## 4 · `[Proxy]` 与占位符

### 4.1 `[Proxy]` 段不写死节点（2026-10-06 起）

**分流版 `routing.conf` 的 `[Proxy]` 段是空的** —— 全部节点来自订阅
（`Airport` 组的 `policy-path`）。占位节点 `Node-A` / `Node-B` 已移除：
它们的存在让读者以为必须手工补两条本机节点才能跑，而实际上只填订阅即可。

要加自己的节点（自建 / 中转链 / 本地入口）就在这里写：
`名字 = 类型, 服务器, 端口, 参数…`。写法与限制见 §4.1.1 下方原占位节点一段的沿革。

两类的**订阅节点引用面不同**（这是两版真正的设计差）：懒人版里订阅节点直接进
`Proxy` / `AI`（`include-other-group="Airport"`）；分流版里订阅节点只进
`Smart` / `Select` / 6 个地区组，其余应用组的成员表不变。

> ⚠️ **命名不是装饰，是功能**（只影响分流版的地区组）—— 地区组用 `policy-regex-filter`
> 按**节点名**筛节点。叫 `HK-01` 会进 `Hong Kong` 组，叫 `香港一号` 也会，叫 `node1`
> 则哪个地区组都进不去。命名规则与关键词表见
> `docs/11` §4（原文档已随仓库精简移除）。
> ⚠️ 另有一条官方限制：正则**对显式写在 `[Proxy]` 的成员不生效**，所以手写节点
> 想进地区组，得给对应组补 `include-all-proxies=true`。本模板默认不写死节点，故未启用。

### 4.2 `download-bandwidth` 不写的原因

`hysteria2` 的 `download-bandwidth` 是**服务端**拥塞控制提示。填一个偏大的值会让
服务端猛发、链路 buffering 撑爆（bufferbloat），填偏小则浪费带宽。除非服务商
明确公布数字，否则交给服务端自适应。

### 4.3 `https` 类型不支持 UDP 中继

这是 Surge 的代理类型限制，不是配置问题。后果：

- 落到 `https` 类型节点上的 UDP 请求会被拒绝（由
  `udp-policy-not-supported-behaviour = reject` 决定）；
- 所以这类节点**不适合做默认出口** —— AI 流量以稳定长连接为主，历史上本模板把它放在 `AI` 组；
- 反过来，需要 UDP 的场景（游戏、部分 QUIC 应用）必须走 `hysteria2`。
- 📌 当前模板不写死节点，本节讲的是你**自己加** `https` / `http`
  类节点时的行为（旧版 `lazy` 的 `Node-C` / `Node-D` 就是这一类，已随占位节点精简移除）。

### 4.4 节点用 IP 还是域名

- 若你的节点写成 **IP 字面量** —— 不产生「解析节点域名」这一次查询。
  这是本配置里唯一**必定发生**的本地解析，能省则省。
- 你换成域名节点（例如 CDN 中转）时，这次解析就会回来：它是"按域名就近解析"的代价，
  旧版 `lazy` 的 `Node-C` 正是这种形态。

### 4.5 占位节点只留 hysteria2 的原因

两版的 `[Proxy]` 现在都只剩 2 条同类型占位，读者一眼就能改完。历史形态是 4 条
（`hysteria2` ×2 + `https` 中转链 ×2）外加一条被注释的 `Node-E = vless` —— 那条注释
留着是因为 `vless` / `XTLS Reality` **不是 Surge 的原生代理类型**，写了会被跳过并告警，
只增加解析噪音；给从 Clash 迁过来的读者提个醒。⚠️ 这个知识点仍然成立，只是模板里
那一行注释已随「节点缩减成 2 条」一起删掉了。

## 5 · 占位符与脱敏规则

本仓库是公开模板，**所有节点信息都是占位符**。脱敏规则：

| 字段 | 占位形式 |
|:-----|:---------|
| 节点 IP | RFC 5737 文档地址段：`192.0.2.0/24`、`198.51.100.0/24`、`203.0.113.0/24` |
| 密码 / 用户名 | `REPLACE_WITH_YOUR_PASSWORD` / `REPLACE_WITH_USERNAME` |
| SNI | `REPLACE_WITH_YOUR_SNI` 或与 server 相同的 IP / 域名 |

这三类都是**国际标准保留给文档用的**，不会指向任何真实主机，也不会误导使用者。

检验由 `skill/tests/check_secrets.py`（原 architecture.sh ① 提炼）自动完成：
非文档段 IPv4、非 `REPLACE_WITH_*` 凭据、不在允许清单的节点主机名、以及若干
禁止出现的敏感子串，任一命中即失败。

> 🔐 `skill/reference/shared/troubleshoot-faq.md` 里明确写着：**不要把真实节点提交回来**。
> 改完本地用可以，`git push` 前跑一次 `check_secrets.py`。

## 6 · `smart` / `select` 组的差别

### 6.1 `smart` 的打分方式

三个信号：

| 维度 | 说明 |
|:-----|:-----|
| 真实连接首字节延迟 | 主项，比 ping 更贴近实际体验 |
| TCP 重传率 | 每 1% 约折算 50 ms —— 丢包按时延折算才能进同一套评分 |
| UDP 响应延迟 | 单列。`https` 类型不支持 UDP，UDP 表现必须单独看 |

- 重测间隔固定 **5 分钟**
- **按站点记住最优策略** —— 所以「同一节点，A 站快 B 站慢」能自适应
- 成员越少选得越快

### 6.2 什么时候不该用 `smart`

`smart` 会**静默换节点**。如果你：

- 需要出口 IP 稳定（某些服务按 IP 做风控）
- 想知道「我现在到底走哪个节点」

那 `select` 更合适（想这么用的话，把 `Proxy = smart, …` 改成 `select`）。
静默换节点对这类诉求是**意外行为**。代价是节点挂了要手动切。

### 6.3 本模板的分工

| 组 | 类型 | 理由 |
|:---|:-----|:-----|
| `Proxy` | `select` | 日常流量：`Smart`（订阅池自动选最快）/ `Select`（全池手动指定） |
| `AI` | `select` | `include-other-group="Proxy"` 摊平的订阅池 |
| `Airport` | `select` | 订阅槽位，`hidden=true`（不在面板显示，只被上两组 include） |
| `AD` | `select` | 手动开关（独立于规则链路） |

## 7 · `underlying-proxy` 中转链

> 📌 **当前模板不带中转链** —— 旧版 `lazy` 的 `Node-C` / `Node-D` 是这一形态，
> 已随「占位节点缩减成 2 条」移除。本节讲的是**你自己在 `[Proxy]` 加链式节点时**的机制，
> 结论仍然成立。

### 7.1 机制

```
Node-C = https, cdn-relay.example.com, 443, …, underlying-proxy="落地节点名", …
                        │                                    │
                        │                                    └─ 先连它，再由它去连 cdn-relay
                        └─ 实际目标
```

`underlying-proxy` 指向的节点先建连，再由它去访问本节点。等价于一层手写链式代理。

### 7.2 两条硬约束

1. **被指向的名字必须存在**（在 `[Proxy]` 或 `[Proxy Group]` 里）。
   否则 Surge 会以「无法解析 `underlying-proxy`」**拒绝加载整份配置**。
   旧版 `lazy` 里是 `Node-C → Node-B`、`Node-D → Node-A`（当时的占位节点），都在同一个 `[Proxy]` 段里。
2. **不能形成环**。`A → B` 且 `B → A` 会让 Surge 拒绝加载。

### 7.3 改动顺序

改了节点名之后，**先确认 `underlying-proxy` 引用的新名字存在，再保存**。
这是本文件里唯一需要「按顺序改」的地方 —— 顺序错了会直接导致配置无法加载。

## 8 · `pre-matching` 与 `extended-matching`

### 8.1 `pre-matching`

让 REJECT 在 **DNS 查询阶段 / TCP-SYN 阶段**就被求值。
被拦的请求得到一个「No Record」或 TCP RST 就结束了，**连接层完全不会启动**。

这是全模板最大的一笔 CPU 与耗电优化。省的不只是带宽，是「解析 → 建连 →
等首字节 → 丢弃」这一整串唤醒。移动端省电的关键从来不是省流量，是少唤醒。

### 8.2 硬约束：策略必须是字面量

`pre-matching` 的规则，策略必须是 **REJECT 族的字面量策略名**。

**不能是策略组** —— 哪怕那个组只有 `REJECT` 一个成员。原因：策略组在运行时
可以解析成 `DIRECT`（例如组被切走、或组成员动态变化），Surge 无法据此保证
「一定拦得住」，于是**直接拒绝加载整份配置**。

⇒ 这是 `AD` 组「不由任何规则引用」的根因。规则里写字面量 `REJECT`，`AD` 组
留给面板上手动切 —— 但要让读者知道：**把 `AD` 切成 `DIRECT` 并不会关闭广告拦截**，
因为规则根本不经过它。想真正关掉，改规则那一行的策略或注释掉整行。

### 8.3 `extended-matching`

额外按 **TLS SNI / HTTP Host** 匹配。专治「App 直连 IP，域名规则失效」——
很多 App 会先解析出 IP 再直连，此时纯域名规则不再命中；`extended-matching`
从 TLS 握手里读 SNI 补上这一步。

⚠️ 本项目**没有**在 `AI.list` 那条规则上加它 —— 那条是分流不是拦截，
加 `extended-matching` 会让它按 SNI 匹配，与「域名规则集」的语义不符。
`check_surge_dns.py` 的 `check_10` 只对带 `pre-matching` 的规则提示缺
`extended-matching`，不给非拦截规则报负。

## 9 · `always-real-ip` 与 Fake-IP

### 9.1 两种模式

| 模式 | 对应用返回什么 | 后果 |
|:-----|:---------------|:-----|
| Fake-IP | 一个假地址（如 `198.18.x.x`），Surge 靠它反查域名 | 分流准确，但拿不到真实 IP |
| Real-IP | 真实地址 | 应用能拿到真实 IP，但分流会变弱（只能靠 IP） |

Surge 默认对走代理的域名用 Fake-IP，对 DIRECT 的域名用 Real-IP。

### 9.2 `always-real-ip` 强制某些主机名走 Real-IP

NAT 类型检测（STUN）、时间同步（NTP）、游戏机配对，都需要真实可路由地址 ——
给它们 Fake-IP 会直接坏掉。

⚠️ 再次强调：`always-real-ip` **不改变流量的目的地**。它只是让应用拿到真实 IP。

### 9.3 与规则顺序的关系

`always-real-ip` 里的主机名，如果在 `[Rule]` 里没有被域名规则接住，
就会走到后面的 IP 类规则 —— 而 IP 类规则带 `no-resolve`，对未解析的主机名**跳过**。

于是它们最终落 `FINAL → Proxy`，其解析必须由节点远端完成 —— 这本身没问题
（远端解析更准）。但**本地若需要它的地址**（NAT 检测要真实 IP），就会出问题。

⚠️ **两份配置都不再为它们单开规则**（2026-09-23，与 Egern 对齐 —— Egern 侧本就没有对应规则，
`lazy` 一并删除）。`always-real-ip` 保留不变 —— 这些主机名照旧拿到真实 IP；
未被域名规则接住的会走到 IP 类规则（`no-resolve` 对未解析的主机名**跳过**），
最终落 `FINAL → Proxy`，解析由节点远端完成（远端解析更准）——
**结果去向与原先三条规则一致**（同为代理链），差别只在不再单独占一节。

## 10 · `hijack-dns` 的边界

### 10.1 能拦什么

- 硬编码了知名公共解析器 IP（`8.8.8.8` 等）的设备
- 显式发往这些地址的 `:53` 查询

### 10.2 拦不住什么

- **DoH / DoT 客户端**：`https://dns.google/dns-query` 走 443，不是 `:53`。
  `hijack-dns` 管不到。唯一办法是让那个 App 走代理，或承认它（多数情况下 DoH 本身
  是加密的，不算「明文泄露」）。
- **自建解析器**：企业内网 DNS、某些路由器的 `192.168.x.1:53`。要覆盖得显式列。
- **`:53` 之外的端口**：非标准端口上的 DNS。
- **不经过 Surge 的流量**：例如另一个 VPN、或 Surge 未接管时。

### 10.3 `hijack-dns = *` 的取舍

| | 列具体地址（本模板） | 写 `*` |
|:--|:---------------------|:-------|
| 覆盖面 | 6 个最常见 | 全部 `:53` |
| 风险 | 少量自建解析器 / 冷门公共解析器漏掉 | 极少数依赖原生 `:53` 行为的应用可能异常 |
| 审计读数 | LOW（「未覆盖 N 个知名解析器」） | OK |

本模板选列具体地址，因为「覆盖面足够 + 行为可预测」比「一网打尽 + 边界情况未知」更稳。
想换就改一行。

> ⚠️ 审计器**不会**因为「列得少」判负 —— 第一版按条数判负是错的（`:53` 的地址空间
> 是无限的，列举永远不可能「列全」）。现在的判据是「还有多少**已知的**知名境外
> 解析器没被覆盖」，且只报 LOW。

## 11 · 规则集与刷新

### 11.1 引用清单

| 规则集 | 条数 | 类型 | 上游 |
|:-------|:----:|:-----|:-----|
| `surge-direct.list` | — | 纯域名 | Jinx |
| `surge-ads.list` | — | 纯域名 | Jinx |
| `AWAvenue-Ads-Rule-Surge-RULE-SET.list` | — | 纯域名 | TG-Twilight（⚠️ **必须用 RULE-SET 版**） |
| `AI.list` | — | 域名系（零 IP；含 KEYWORD×2 + URL-REGEX×1） | Repcz/Tool（分支头，活跃维护） |
| `private.txt` | — | 域名 + 可能含 IP | Loyalsoldier |
| `direct.txt` | 十几万 | 纯域名 | Loyalsoldier |
| `SYSTEM` / `LAN` | — | 内置 | Surge |

> ⚠️ **条数一律不写死精确数字**：`—` = 现抓；`direct.txt` 那格写「十几万」只用于表达量级。
> 本仓所有远程 URL 都没锁 commit、上游每次更新都会变，固定数字很快过期。
> 要精确值现抓：`python skill/scripts/surge/audit_ruleset_content.py <profile>`。
> 这张表真正有意义的是**类型**（纯域名 / 含 IP）与**上游**，不是条数。

### 11.2 `update-interval=604800`（一周）

远程 `RULE-SET` 全部显式带一周刷新。

⚠️ **别把这条写成"不写就不刷新"** —— Surge 手册写明该键**缺省即 86400（24 小时）**，
只有写成**负值**才关闭自动更新。所以漏写不会让规则集停在首次下载的版本，它只是让
刷新周期**不可见**、并且与 Egern 侧不一致（Egern 才是真正未文档化缺省值的一侧）。
本仓统一钉成 604800，图的是两侧同周期、文件里看得见。

⚠️ 同一个键只应该写在一处。源配置里 `update-interval=3600` 曾写在 `[Proxy Group]`
的 `smart` 组上 —— 那只对订阅型组有意义，写在那里是空转。本模板已移除。

### 11.3 `AI.list` 曾钉 commit，2026-09-28 改跟分支头

（原设计）`AI` 组的出口隔离是有意设计，钉 commit 让「哪些域名走 AI 组」可复现 ——
代价是上游更新不跟进，实测 ACL4SSR 的 AI.list 长期停在 51 行，Gemini 新形态全部缺失。

⇒ 2026-09-28 起换 [Repcz/Tool](https://github.com/Repcz/Tool) 的 AI.list 并改跟分支头（该仓滚动维护），
   取舍细节见 [`hardening-template.md` §4.7](hardening-template.md)。bm7 四条专属集不受影响。

### 11.4 广告拦截的两条清单与 `-RULE-SET` 版地址

**① 两条并列，不是替换。** 顺序是 `白名单 → Jinx → AWAvenue → 应用分流`，
与 Egern 的结构一致。两条同策略同参数（`REJECT,pre-matching,extended-matching`）——
Surge 这边指向**字面量 `REJECT`** 而不是 `AD` 组，理由见 §13.3：
只有字面量 REJECT 族才能吃到 `pre-matching`（组不行）。

**② 收益按「净新增覆盖」算，不是按总条数。** 实测（2026-09-22）：

| 指标 | 值 |
|:-----|:---|
| AWAvenue 条目数 | 965 |
| 已被 Jinx 的后缀 / 通配规则覆盖 | 884 |
| **净新增覆盖** | **81（8.4%）** |

**③ 地址必须用 `...-RULE-SET.list`。** 上游同仓提供两个变体，**格式不同、不能互换**：

| 文件 | 条数 | 内容形式 | 对应 Surge 类型 |
|:-----|:----:|:---------|:----------------|
| `AWAvenue-Ads-Rule-Surge.list` | — | **裸域名**（`.8le8le.com`，前导点） | `DOMAIN-SET` |
| `AWAvenue-Ads-Rule-Surge-RULE-SET.list` | — | `DOMAIN,xxx` 规则行 | **`RULE-SET`** ✅ |

（两版条数不写死，上游每周更新；要现值就跑 `audit_ruleset_content.py`。）

本模板用的是 `RULE-SET` ⇒ 必须取后者。RULE-SET 版还**多几条**（那几条是无法写成
裸域名的 `DOMAIN-KEYWORD` / `DOMAIN-SUFFIX`）。换成裸域名版，Surge 会把
「前导点域名」那几行当规则行解析 —— 格式不匹配。（Egern 于 2026-09-22 修过同一问题。）

**④ 顺序是这条的命门。** AWAvenue 会命中白名单里的 **10 条**功能域
（`jpush.cn` / `appcfg.v.qq.com` / `p.l.qq.com` / 微信登录 `apd-pcdnwx*` / 字节 `tnc3-*`）——
白名单留在最前面才拦得住这 10 条误杀。同理，两条清单**都不能**挪到
`direct.txt` / `GEOIP,CN` 之后，否则永远轮不到。

### 11.5 `direct.txt` 的主承重作用

见 §12。

## 12 · `no-resolve` 的双刃

这是全项目最需要注意的一处，也是 [`docs/no-resolve-pairing.md`](../shared/no-resolve-pairing.md)
整篇复盘的由来。

### 12.1 刀刃一：不带 `no-resolve` → 触发解析

```
GEOIP,CN,DIRECT       # 每个走到这里的域名都要被解析一次
```

### 12.2 刀刃二：带上 `no-resolve` → 不再匹配域名

```
GEOIP,CN,DIRECT,no-resolve    # 对未解析的主机名直接跳过
```

于是「**解析出来发现是国内 IP 就直连**」这条路**也一起没了**。
国内域名不再被 `GEOIP,CN` 接住。

### 12.3 后果

如果没有别的规则接住国内域名，它们会全部落到 `FINAL → Proxy` ——
**国内网站整片走代理**。

而更糟的是：两个审计脚本当时**双双通过**，因为
- `check_surge_dns.py` 审的是**结构**（顺序、`no-resolve`、策略可解析）；
- `audit_ruleset_content.py` 数的是**规则集条目类型**。

两者都不会问「一个国内域名走完这份规则，最后去哪」。

### 12.4 修法：两条判据必须成对交付

> **A** —— 所有 IP 类规则带 `no-resolve`
> **B** —— `FINAL` 之前有一个**域名体量足够**的国内直连规则集

只交 A 会漏分流，只交 B 会漏 DNS。**必须一起。**

本模板的 B 是 `direct.txt`（十几万条**域名**条目）。
`skill/tests/check_secrets.py` 把这两条写成了断言。

### 12.5 一个配套的假通过陷阱

审计国内直连时，**只测 `.cn` 域名会假通过** ——
这种配置靠的是 `DOMAIN-SUFFIX,cn` 这条兜底，不是真的接住了国内域名。

`audit_routing_coverage.py` 的 17 个国内探针里**刻意混入非 `.cn`** 的：
`qq.com` / `taobao.com` / `miui.com` / `bilibili.com` / `jd.com` …
（见脚本里的注释：「只有 `.cn` 后缀能直连的配置是**假通过**」）。

## 13 · `[Proxy Group]`：组结构与两处「不能用组」的地方

### 13.1 两版的组结构

**`lazy.conf` —— 4 个组**（3 个分流组 + 1 个隐藏订阅槽）

```
Airport = select, policy-path=…, update-interval=86400, hidden=true, icon-url=…/Airport.png
Proxy   = select, Smart, Select, …, icon-url=…/Proxy.png
AI      = select, include-other-group="Proxy", icon-url=…/grok.png
AD      = select, REJECT, icon-url=…/AdBlock.png
```

| 组 | 类型 | 承载 | 被谁引用 |
|:---|:-----|:-----|:---------|
| `Airport` | `select` | `policy-path` 订阅槽位（`hidden=true`） | `Smart` / `Select` / 6 个地区组的 `include-other-group` |
| `Proxy` | `select` | 各组名（`Smart` / `Select` / 6 个地区组） | `FINAL,Proxy,dns-failed` 一处（游戏机那 3 条域名规则已于 2026-09-23 删除，见 §9.3） |
| `AI` | `select` | `include-other-group="Proxy"` 摊平的订阅节点 | `AI.list` |
| `AD` | `select` | `REJECT` | 独立手动开关（不被规则引用，见 §13.3） |

> 📌 懒人版的 `AI` **不引用 `Proxy`**（2026-09-26 定）：两组各挂自己那条占位节点、
> 再各自 include 订阅槽。`smart` 组也不能把别的组当子策略，只有 `include-other-group`
> 能把订阅里的**具体节点**复制进来。

**`routing.conf` —— 22 个组**

组序与 Egern 当前版 **v3.4** **逐位对齐**（维护纪律，无自动判据）。

| 层 | 组 | 类型 | 作用 |
|:---|:---|:----:|:-----|
| ① 总入口 | `Proxy` / `Smart` / `Select` | `select` / `smart` / `select` | `Proxy` 是**手动**总出口（首项 `Smart`）；`Smart` 自动选优（低倍率优先）；`Select` 全节点池、无权重，供手动指定节点 |
| ② 应用（11 组） | `ChatGPT` / `Gemini` / `Claude` / `AI` / `Google` / `YouTube` / `YouTube Music` / `Telegram` / `Spotify` / `Twitter` / `Microsoft` | `select` | 都带 `include-other-group="Proxy"` —— 复制 `Proxy` 的**已解析成员**；首项各不相同：`ChatGPT` / `Gemini` / `Spotify` / `YouTube Music` → **`United States`** · `Claude` `Taiwan` · `Google` `Gemini` · `Microsoft` `DIRECT`（见下方 📌） |
| ③ 订阅 | `Airport` | `select` | `policy-path` 订阅槽位，`hidden=true` |
| ③ 开关 | `AD` | `select` | 独立手动开关，**不被规则引用**（见 §13.3） |
| ④ 地区 | `Hong Kong` / `Taiwan` / `Japan` / `Singapore` / `United States` / `Other Regions` | `smart` | `policy-regex-filter` 按节点名筛；另带 `policy-priority` 低倍率优先（0.15） |
| ⑤ 兜底 | ~~`Final`~~ | — | **2026-10-05 删除**：兜底由 `FINAL,Proxy,dns-failed` **直指 `Proxy`**（与懒人版拉平）—— 该组只有一个成员、面板上无从选择 |

> 📌 **`AD` 的位置说明（别被分节编号误导）**：它在 `[Proxy Group]` 里排在 `Airport` 之后、
> 这是**位置**，随 Egern 的组序（维护纪律），**不是功能归类**。
> 判据是「有没有被规则引用」：`AD` 被刻意设计成**不被任何规则引用**（§13.3）⇒
> 它是本仓唯一的「开关」，其余组均由 `[Rule]` 里某条规则引用。
> 配置里 `# --- ③ 订阅槽位 + 开关 ---` 这个分节标题同样是按**位置**切的。

> ⚠️ **应用组是 `select` 而不是 `smart`** —— 官方限制：**Smart 组不能拿其他组当子策略**
> （见 §13.2 ②）。而 Egern 的对应物是 `policies: [Proxy] + flatten: true`，
> 其 Surge 等价写法就是 `select, include-other-group="Proxy"`。
> 地区组用 `smart` 是因为它筛的是**具体节点**，需要打分。
>
> ⚠️ **能力差异（必须说清）**：Egern 的应用组自 `routing_v3` 起同为手动 `select`（旧版才是 `fallback`），
> Surge 的 `select` 是**纯手动** ⇒ 两侧应用组同形：「默认走 `Proxy` 全部节点 + 面板可手动改」，
> **应用组没有自动故障转移**（两侧地区组均为 `smart` 自动选优）。想要应用组也自动选优：Egern 换 `fallback` / `smart`、Surge 换 `smart, include-other-group="Proxy"`
> （代价：面板上不能再手动挑节点）。
>
> 完整推导原见 `docs/11` §2.2（已随 2026-09-27 仓库精简移除）。

**应用组各自的默认取向**（首项即默认，与 Egern v3.4 对齐）：

| 应用组 | 默认 | 备注 |
|:-------|:----:|:-----|
| `ChatGPT` / `Gemini` | `Proxy` | |
| `AI` | `Proxy` | 跟随 `Proxy` 的整池节点 |
| `Claude` | **`Taiwan`** | Egern 的取向，Claude 对台湾线路较友好 |
| `Google` | `Gemini` → `Proxy` | 首项是 `Gemini` 组 ⇒ 「Google 走 Gemini → Proxy」 |
| `Spotify` / `YouTube Music` | **`United States`** | 媒体类的解锁地区（2026-09-26 定；组名由 `USA` 改名而来） |
| `YouTube` | `Proxy` | 媒体类 |
| `Telegram` / `Twitter` | `Proxy` | 社交类 |
| `Microsoft` | **`DIRECT`** | 微软国内可直连，走代理反而慢 |
| —（`GitHub`） | `Proxy`（**规则直指**） | 开发者服务；2026-10-05 起不再单设组，`GitHub.list` 直接 `policy: Proxy` |

### 13.2 不能用组的地方

**① `pre-matching`** —— 见 §8.2。`pre-matching` 的规则策略**必须是字面量 REJECT 族**，
写成组会加载失败。所以广告拦截写的是 `REJECT` 而不是 `AD`。

**② `smart` 组当父组** —— 官方明确：Smart 策略组**不可以使用其他组作为子策略**，
也不可以用作 `url-test` / `load-balance` 组的子策略。
想要"把一个组的成员并进来"，正确写法是 `include-other-group="X"`
（把 X 的**已解析成员**复制过来），而不是把 `X` 当成成员名写进去。
原见 `docs/11` §2.1 / §2.2（原文档已随仓库精简移除）。

### 13.3 `AD` 组的定位：独立的手动开关

`AD` 组**被刻意设计为独立于规则链路**，这是一处明确的分层设计：

- 规则里的广告拦截写的是字面量 `REJECT`，**不经过 `AD` 组** —— 这是为了拿到
  `pre-matching` 在 DNS 阶段的拦截能力（见 §8.2），代价是拦截动作绕开了 `AD`；
- `AD` 组因此成为一个**纯粹的手动开关**：面板上随时可切，不牵动规则引擎。

> 📌 **职责划分**：`RULE-SET,…,surge-ads.list` 负责「默认拦截」，
> `AD` 组负责「人工干预入口」。两者独立存在，`AD` 组不被规则引用是设计结果，
> 不是配置遗漏。

想让 `AD` 组真正接管拦截开关，把 `[Rule]` 里那条 `RULE-SET,…,surge-ads.list`
的策略从 `REJECT` 改成 `AD` 即可 —— 但要清楚**改完那行就不能带 `pre-matching` 了**
（见 §8.2），也就是用「面板可控」换掉「DNS 阶段最大那笔耗电优化」。
**这是两条都成立的路线，本模板选了前者，并把开关入口保留下来。**

### 13.4 `AI` 组独立的理由

不是「更细」，是**出口隔离**：

- AI 服务的风控对出口 IP 的稳定性敏感；
- `Proxy` 是 `smart`，会按站点静默换节点 —— 出口 IP 飘忽反而有害；
- 独立组可以把 AI 出口钉在专门的节点上（若你有自建节点，写进 `[Proxy]` 后作为本组首项即可）。

### 13.5 组名与成员名的大小写

Surge 的组名 / 节点名引用**不区分大小写地可解析**，但 `check_surge_dns.py`
的 `check_7` 会同时按原名与全小写匹配，避免把 `Proxy` 与 `proxy` 判成两个东西。

## 14 · `[Rule]`：两版规则顺序

`[Rule]` 是**有序的** —— 自上而下匹配，**第一条命中即决定去向**。

**`lazy.conf` —— 11 条**

| # | 规则 | 策略 | 选项 | 为什么排这里 |
|:-:|:-----|:----:|:-----|:-------------|
| 1 | `RULE-SET,…,surge-direct.list` | `DIRECT` | — | 广告白名单。**必须**在 REJECT 之前，否则形同虚设。它同时兜住两条黑名单的误杀 |
| 2 | `RULE-SET,…,surge-ads.list` | `REJECT` | `pre-matching,extended-matching` | 黑名单第 1 条（Jinx）。必须在 `direct.txt` / `GEOIP,CN` **之前** —— 否则国内广告域名被 `direct.txt` 接走 |
| 3 | `RULE-SET,…,AWAvenue-Ads-Rule-Surge-RULE-SET.list` | `REJECT` | `pre-matching,extended-matching` | 黑名单第 2 条（AWAvenue）。顺序与 Egern 对齐，见 §11.4 |
| 4 | `RULE-SET,SYSTEM` | `DIRECT` | — | **系统域白名单（位 ④，2026-10-06 起不再置顶）**：Apple 激活 / 推送 / 配对，内置权威集合，**保底**。实测其 18 个域名与两条广告清单零交集 ⇒ 排前后拦截结果相同。⚠️ **懒人版不设 `Apple Update` 组**（仅分流版有），OTA 域名在此接成 `DIRECT` |
| 5 | `RULE-SET,LAN` | `DIRECT` | `no-resolve` | 含 18 条 IP-CIDR，**必须** `no-resolve`。内网段排在应用之前，与 Egern 同位 |
| 6 | `RULE-SET,…,private.txt` | `DIRECT` | `update-interval=604800` | 内网域名。实测零 IP ⇒ 按原则**不写** `no-resolve` |
| 7 | `RULE-SET,…,AI.list`（Repcz） | `AI` | `update-interval=604800` | 实测零 IP（纯域名系）⇒ 不写 `no-resolve` |
| 8 | `RULE-SET,…/Self-Configuration/main/rules/AI.list` | `AI` | `update-interval=604800` | 本仓自托管整合集（伴生域 / 宽后缀），与 7 号同指 `AI` 组 |
| 9 | `RULE-SET,…,direct.txt` | `DIRECT` | `update-interval=604800` | **主承重墙**，纯域名、零 IP（条数一律现抓）。见 §12 |
| 10 | `GEOIP,CN,DIRECT` | `DIRECT` | `no-resolve` | IP 类规则，放最后 |
| 11 | `FINAL,Proxy,dns-failed` | `Proxy` | `dns-failed` | 兜底 |

> ⚠️ **懒人版无 `Apple Update` 组与 `SystemOTA` 规则**（2026-10-06 定）：系统更新分流只在分流版提供。
>    懒人版的取向是「全量流量一个出口」，不为此再开一个组。

**`routing.conf` —— 26 条（内容与顺序逐行对齐 Egern 侧现役）**

| # | 规则 | 策略 | 与 lazy 的差异 |
|:-:|:-----|:----:|:---------------|
| 1 | 广告白名单：`surge-direct.list` | `DIRECT` | 同 lazy |
| 2–3 | 广告拦截 ×2 | `REJECT` | 同 lazy |
| 4 | **Apple 更新**：`SystemOTA.list` | `Apple Update` 组 | **分流版独有**（懒人版不设该组） |
| 5 | **系统域白名单**：`SYSTEM` | `DIRECT` | 同 lazy（2026-10-06 起不再置顶） |
| **6–7** | 内网：`LAN` / `private.txt` | `DIRECT`（`LAN` 带 `no-resolve`，`private.txt` 零 IP 不写） | 同 lazy |
| **8–12** | AI 厂商：`OpenAI` / `Gemini` / `Anthropic` / `Claude` / `AI` | `ChatGPT` / `Gemini` / `Claude` / `Claude` / `AI` | **新增 5 条**（AI 细分） |
| **13** | 本仓自托管 `AI.list` | `AI` | **新增**（伴生域 / 宽后缀） |
| **14** | 媒体：`YouTubeMusic` | `YouTube Music` | **新增**（因包含关系前移，见 §14 要点 4） |
| **15–22** | `GitHub`→`Proxy` · `YouTube` · `emby` · `Google` · `Telegram` · `Spotify` · `Twitter` · `Microsoft` | 同名组（`Microsoft` 首项 `DIRECT`） | **新增 8 条**（应用分流） |
| 23 | Apple 域名集：`apple.txt` | `DIRECT`（零 IP **不写**开关） | 新增 |
| 24–25 | `direct.txt` / `GEOIP,CN` | `DIRECT`（`direct.txt` 零 IP **不写**开关；`GEOIP` 带 `no-resolve`） | 同 lazy |
| **26** | `FINAL,Proxy,dns-failed` | `Proxy` 组 | 与懒人版一致（2026-10-05 起不再挂 `Final` 中间组） |
| — | ~~游戏机主机名 3 条~~ | — | **已删除**（Egern 侧无对应规则，为对齐而移除；`lazy.conf` 同步没有，两侧只剩 `always-real-ip` 里的主机名） |

> 📌 **五条顺序要点**：
> 0. ⭐ **`SystemOTA` 必须排在 `SYSTEM` 之前**（2026-10-06 立）—— 两集有 3 条重叠
>    （`configuration.apple.com` / `mesu.apple.com` / `xp.apple.com`），`SYSTEM` 会先把它们接成 `DIRECT`，
>    排在后面 `Apple Update` 组就永远轮不到那 3 条。属「规则集包含关系所致的前移」，Z0 按允许前移处理。
>    ⚠️ 本组**仅分流版提供**（2026-10-06 定）：懒人版不设 `Apple Update` 组，也无 `SystemOTA` 规则。
> 1. ⭐ **系统域白名单（`SYSTEM`）不再置顶**（2026-10-06 起）—— 分流版落在位 ⑤（`SystemOTA` 之后、内网之前），
>    懒人版落在位 ④（两条广告拦截之后、`LAN` 之前）。
>    原口径「系统域优先级高于一切 ⇒ 置顶」已废止：实测其 18 个域名与两条广告清单**零交集**，
>    排前或排后**拦截结果完全相同** ⇒ 不再占用「最前」这个语义位置。
> 1. **厂商专属规则必须排在通用 `AI.list` 之前** —— 否则 AI 域名先被 `AI.list` 接走，
>    `ChatGPT` / `Gemini` / `Claude` 组永远轮不到。
> 2. **`GitHub.list` 必须排在 `direct.txt` 之前** —— 实测 `direct.txt` 收录了若干含 `github`
>    的域名（githubim.com / githubshare.com / hellogithub.com / kkgithub.com 等），它们会被
>    `GitHub.list` 的 `DOMAIN-KEYWORD,github` 命中；排到后面这几个会走 DIRECT。
>    ⚠️ 本条**直接指向 `Proxy`**（2026-10-05 起不再单设 `GitHub` 组，规则集仍保留）；
>    `github.com` 本身**不在** `direct.txt` 里，它走代理由覆盖审计断言守。
> 3. **内网段排在应用段之前** —— 这处位置是**对齐 Egern v3.2 的结果**：
>    内网清单里的域名不在任何应用清单中，IP 段又带 `no-resolve` 不触发解析
>    ⇒ 提前与否语义等价，只为两侧顺序逐行一致。
> 4. **`YouTubeMusic.list` 必须排在 `YouTube.list` 之前**（因规则集**包含**关系前移，
>    与上一条 `SystemOTA` 之于 `SYSTEM` 同性质）：`YouTube.list`（190 条）内含
>    `YouTubeMusic.list` 的 UA 规则（`USER-AGENT,*YouTubeMusic*` 等），排后面就永远轮不到。
>    而它的组在面板上排在 `YouTube` **之后** —— Z0 因此判「允许前移、不许乱序」。

### 14.1 Apple 规则集曾经必须用 `No_Resolve` 版的原因

> 📌 2026-09-24 起这条只适用于**分流版**：懒人版已经删掉远程 Apple 规则集，
>     系统服务那部分交给内置 `SYSTEM`。
> 📌 2026-10-04 起**本节整节成为历史**：分流版那条也由 `Apple_All_No_Resolve.list`（1,616 条）
>     换成零 IP 的 `apple.txt`（纯域名）—— 没有 IP 条目，就不存在"该用哪个变体"的问题。
>     顺带：`developer.apple.com` / `gateway.icloud.com` 这类只被全量集覆盖的域**按设计改走代理**
>     （探针期望已同步移出，见 `checker.md`）。下面的坑留在文档里当判据示例。

这是 Egern 项目实测踩出来的坑，直接搬过来：

`Apple_All.list` 里有 **13 条 `IP-CIDR` 没带 `no-resolve`**（`139.178.128.0/18` 等 Apple CDN 段）。
而这条规则排在后面那些 IP 类规则**之前**、策略又是 `DIRECT` ⇒
**每个还没被前面规则命中的域名，经过这里都会被强制解析一次**。

那次解析走的是本地 DNS —— 就是泄露本身。
症状是 dnsleaktest 里「判定结果显示 default → Final → Proxy，但 upstream 显示 bootstrap」：
为了判定这条 IP 规则而触发的解析走了明文。

`No_Resolve` 版与原版**逐条等价**（只是那 13 条补上了 `,no-resolve`），
覆盖面无损失，对 IP 形式的连接判定也完全不受影响（IP 本就无需解析）。
所以这里没有取舍，纯粹是用对版本。

> 📌 当年 Egern 把 20 个远程规则集逐个下载核对过：**只有 `Apple_All.list` 存在这个缺陷**。
> 本项目的 `audit_ruleset_content.py` 会把这条检查自动跑一遍。

### 14.2 铁律（两版通用）

**白名单(DIRECT) → 黑名单(REJECT) → 常规分流（`direct.txt` / `GEOIP,CN`）**

REJECT 绝不能排在 `direct.txt` / `GEOIP,CN` 之后 —— 那等于白加，
因为国内广告域名会先被 `direct.txt` 接走。

### 14.3 IP 类规则置于最后的理由

IP 类规则需要有已解析的地址。放在所有域名规则之后，使走代理 / 被广告拦截 /
国内直连的流量都**不必做本地 DNS 查询**。

### 14.4 `FINAL` 的 `dns-failed`

万一规则求值因 DNS 失败而中断，用代理策略而不是让请求直接失败。
走代理的域名由节点远端解析 —— 所以这一条既修好了失败，也**避免了一次明文本地查询**。

> 📌 两版的 `FINAL` 策略不同：`lazy` 直接写 `Proxy`（`smart` 组，自动选最快节点）；
> `routing` 写 `Final`（`select` 组，默认第一成员是 `Proxy`）。
> 后者多一层间接，换来的是**面板上可手动改道**。见
> `docs/11` §5（原文档已随仓库精简移除）。

## 15 · 审计体系

### 15.1 五个脚本 + 两个测试

| 脚本 | 审什么 | 需要联网 |
|:-----|:-------|:--------:|
| [`check_surge_dns.py`](../../scripts/surge/check_surge_dns.py) | 文件内部的**结构**（12 项检查） | ❌ |
| [`audit_ruleset_refresh.py`](../../scripts/surge/audit_ruleset_refresh.py) | 远程规则集的**刷新参数** `update-interval`（非正值 = 关掉自动更新 → HIGH；与约定值 604800 不同 → 仅 `--strict` 判负） | ❌ |
| [`audit_ruleset_content.py`](../../scripts/surge/audit_ruleset_content.py) | **远程规则集的内容**（缺 no-resolve 的 IP 条目 / 直连集合的域名体量） | ✅ |
| [`audit_routing_coverage.py`](../../scripts/surge/audit_routing_coverage.py) | 拿**真实域名走一遍** `[Rule]`，看最终去哪（期望表按配置自动切换） | ✅ |
| [`audit_region_filters.py`](../../scripts/surge/audit_region_filters.py) | **地区组正则的一致性**（`Other Regions` 的负向断言有没有漏词、组间有没有重叠） | ❌ |
| [`skill/tests/check_secrets.py`](../../tests/check_secrets.py) | 项目不变量（占位符纪律 / 订阅 token 纪律，全仓 `.conf` + `.yaml`） | ❌ |
| [`skill/tests/check_links.py`](../../tests/check_links.py) | markdown 相对链接与锚点（改标题后**静默失效**的那一类问题） | ❌ |

> 📌 第 4 个（`audit_region_filters.py`）是分流版带来的：`Other Regions` 用的负向断言
> 把另外 5 个地区组的关键词**抄了一遍**（61 个 token），而 Surge 的 `filter`
> 只吃字面正则、不支持变量 ⇒ 结构上消灭不掉这份拷贝。
> **兜底做法是给拷贝配一个比对器，并给比对器配一个判负样本** ——
> 见 [`skill/reference/surge/pitfalls.md` 坑 16](pitfalls.md)。

### 15.2 需要多个而非一个的原因

它们回答的是**不同层次**的问题：

- `check_surge_dns.py`：「这份文件自洽吗？」
- `audit_ruleset_content.py`：「它引用的东西里有雷吗？」（profile 里看不见）
- `audit_routing_coverage.py`：「一个真实请求进来，实际去哪？」（结构全绿也可能错）
- `audit_region_filters.py`：「两处必须一致的正则，现在一致吗？」（不一致时**静默失效**）
- `audit_ruleset_refresh.py`：「规则集多久重新下载一次？有没有人被写成**不再更新**？」（唯一会**真的**让规则集停在旧版的那一项）

第三个是 Egern 项目的教训换来的：**两个审计脚本双双通过，分流却整片是坏的。**
第四个则是"消灭不掉拷贝时怎么办"的答案。

### 15.3 豁免机制

`# audit-waive: <检查号> <理由>` 写在 **profile 里**，不写在审计器里。

| | 写在审计器 | 写在 profile |
|:--|:-----------|:-------------|
| 影响面 | 判据被**永久**削弱，别的 profile 也失去保护 | 只豁免这一份 |
| 可追溯 | 要去读代码 | 在**被豁免的对象旁边**，可 grep |
| 改配置的人 | 看不到 | 一定看到 |

豁免把 finding 降级为 `WAIVED:` 并**照常逐条打印** —— 不改判定语义的前提是它仍然可见。

### 15.4 共享模块 `_surge_common.py`

所有脚本从这里 import 判据。背景是 Egern 项目里两个脚本各自实现了一份
「端点主机名解析」逻辑 —— **判据本体同步了、喂给判据的 helper 没同步**，
同一份配置给出相反结论。

⇒ 教训：**靠注释提醒同步两份拷贝是不可靠的。** 从结构上消灭拷贝。

### 15.5 `policy_index()` —— 最容易写错的一处

```python
# 有匹配值：DOMAIN-SUFFIX,x.com,POLICY / GEOIP,CN,DIRECT / RULE-SET,SET,POLICY
#          → 策略恒为 index 2
# 无匹配值：FINAL,POLICY → 策略为 index 1
```

**`GEOIP` 属于「有匹配值」**（匹配值是 `CN`）。第一版把它归错了组，
于是把 `CN` 当成策略名，报出「规则引用了未定义的策略 `CN`」这个**假 HIGH**。
同一处还漏掉了 `RULE-SET` 的 index 1 是规则集标识而不是策略。

> 判据写错方向比漏报更危险 —— 它会让使用者去改一条**本来正确的**规则。

### 15.6 全绿 ≠ 可用

审计脚本只覆盖**静态可判定**的部分。拦截效果、误杀、节点可用性必须实测。
这是 Egern 项目连续 5 次「脚本全绿、实测仍有问题」换来的结论。

## 16 · 已知取舍

### 16.1 `proxy-test-url` 保持境外端点（性能取向）

源配置是 `http://www.gstatic.com/generate_204`（境外）。**本模板不改它。**

原因：`proxy-test-url` 是**性能探针**，不是泄露通道。它决定 `smart` / `url-test`
拿什么给节点打分，测的是「本机 → 测试地址 → 节点 → 回来」这一整圈：

- **用境外端点**：这一圈包含国际段，测出的延迟与你实际访问境外站点的体感**相关** ——
  对「选哪个节点上网更快」这个决策更有意义；
- 用境内端点：测出的是境内 RTT，节点在境外时「节点→境内端点」那段路由与真实路径不同，
  **不是更准，只是测了另一个东西**。

至于「周期性解析」的顾虑，官方 KB 已明确：走代理策略时解析发生在**代理服务器**
（「DNS 解析永远在代理服务器进行」），本地不解析；只有命中 DIRECT 才本地解析。

⇒ 所以端点选境内还是境外，是**性能取向**的取舍，不是安全对错。
`check_surge_dns.py` 的 `check_6` 对此**只报 LOW 提示，不计入风险等级**。

⚠️ 注意区分：`proxy-test-url` 决定 TCP 测速用什么，`proxy-test-udp` 决定 UDP 测速用什么。
`internet-test-url`（连通性检测）本模板用国内 204 —— 那测的是「本机能不能上网」，
用国内端点更贴切。

### 16.2 保留 2 个主机名形式的加密 DNS 端点

`dns.google` / `dns.alidns.com` 会被引导解析一次。换成纯 IP 字面量能消掉，
但会失去两项收益：

1. **按域名走 CDN 就近解析**；
2. **ECS 合规**（不把公网 IP 交给非 CDN 的解析器）。

已在 profile 内用 `# audit-waive: 1` 声明（详见 §15.3）。
想彻底消掉就把它们换成 IP 字面量，同时删掉那行 waive。

### 16.3 `hijack-dns` 不穷举

见 §10.3。

### 16.4 `AD` 组与拦截链路的分层

见 §13.3。`AD` 组是**独立的手动开关**，不被规则引用是刻意的分层设计。

### 16.5 形态与配置之间的一致性

架构检查断言三条：

| 断言 | 比对对象 | 理由 |
|:-----|:---------|:-----|
| ②-a | `lazy.conf` ↔ `lazy.min.conf` | `.min.conf` 的定位是「去掉注释」，不是「裁剪配置」 |
| ②-b | `routing.conf` ↔ `routing.min.conf` | 同上 |
| ②-c | `lazy.conf` ↔ `routing.conf` | **防泄露标准不因分流粒度而变** |

比对的是两边共有的 **16 个 DNS 相关键**，逐字相同。改配置时两份都要动，只改一份会被拦下。

⚠️ ②-c 是本项目**唯一一条跨配置**的断言。它挡的是「反正这是分流版，DNS 段差不多就行」
这种想法 —— 两份配置允许出现的差异**只在** `[Proxy Group]` 与 `[Rule]` 的粒度上。

### 16.6 兜底：两版都直指 `Proxy`（2026-10-05 起）

两份**写法相同**：`FINAL,Proxy,dns-failed` —— **直接**指 `Proxy` 组，中间不挂任何组。

⚠️ **2026-10-05 修正**：此前分流版写 `FINAL,Final,dns-failed`（多一层 `Final = select, Proxy`），
理由记为「这样你在面板上还能改兜底去向」。**实测该理由不成立** —— 查全部 27 个历史版本，
`Final` 组成员**始终只有 `Proxy` 一个**，单成员 `select` 组在面板上无从选择。
⇒ 已删除该组，与懒人版拉平（Egern 侧同改：`default.policy` 由 `Final` 改直写 `Proxy`）。

两者都**不做**「分流兜底的境内 / 境外切分」。国内直连靠 `direct.txt` + `GEOIP,CN`
正面覆盖，不靠兜底。

## 17 · FAQ

**Q：我照抄了，但国内网站慢 / 打不开。**

先跑 `python skill/scripts/surge/audit_routing_coverage.py surge/profiles/lazy.conf`。
若国内探针没命中 `DIRECT`，检查两条：① 有没有删掉 `direct.txt` 那条规则；
② 有没有把 `GEOIP,CN` 挪到域名规则前面。

**Q：`GEOIP,CN` 加了 `no-resolve` 之后国内 IP 还判得准吗？**

判得准，但**前提是它前面有域名类规则接住国内域名**。`no-resolve` 只是
「对未解析的主机名跳过」，已经解析出 IP 的请求照常判。见 §12。

**Q：为什么广告拦截不指向 `AD` 组？**

见 §8.2 / §13.3。这是刻意的分层：`pre-matching` 要求字面量策略，所以拦截动作
走 `REJECT`（换取 DNS 阶段拦截能力）；`AD` 组则作为**独立的手动开关**保留，
职责是「给人工干预留入口」，不与规则链路耦合。想让 `AD` 接管开关可以改，
但要一并去掉 `pre-matching`。

**Q：`smart` 组一直换节点，我想固定。**

把 `Proxy = smart, …` 改成 `select`。或把 `AI` 的成员单独钉一个节点。

**Q：我删了 `# audit-waive:` 那行，为什么突然报 HIGH？**

那是有语义的注释，不是说明文字。见 §15.3。

**Q：能不能只保留 `encrypted-dns-server`，去掉 `dns-server`？**

不建议。`dns-server` 承担引导与连通性测试职责。去掉后 Surge 会用系统 DNS
（运营商 DHCP 下发的那台）—— 正是出口 ①。

**Q：iOS 上怎么用？**

Surge iOS 版不支持本地文件配置，需要把 profile 内容托管到一个可访问的地址
（Gist / 自己仓库），再用 URL 导入。`icons/` 里的图标地址已是绝对 URL，
不依赖本地路径。

## 18 · 维护者须知

### 18.1 改动前必须知道的三条

1. **DNS 段不许只改一份，也不许只改一个配置。** 三组比对（`lazy` 两形态 / `routing` 两形态 /
   `lazy` ↔ `routing`）共 16 个键由测试逐字比对。要改就**四份一起改**。
   ⚠️ 注意 `routing.min.conf` 是从 `routing.conf` 生成的，生成脚本会丢掉注释 ——
   新加 `# audit-waive:` 行后要**手动补回 min 版**，否则审计器会对 min 版报 HIGH。
2. **规则顺序铁律不许破。** 白名单 → REJECT → 域名类直连 → IP 类 → `FINAL`。
3. **节点不许提交真实值。** `check_secrets.py` 会拦。

### 18.2 想加第三份配置

**先问：这是新分工，还是老配置的另一种写法？** 后者不推荐（那就是版本分叉，
原见 `docs/07` §3.2 / §6，原文档已随仓库精简移除）。确认是新分工后，对照
`check_secrets.py` 的 6 条清单 ——
以上基本就是 `check_secrets.py` 的全部判据。
**能过测试的才算一份新配置。**

### 18.3 全部验证都在本地

```bash
python skill/scripts/surge/check_surge_dns.py surge/profiles/lazy.conf
python skill/scripts/surge/check_surge_dns.py surge/profiles/routing.conf
```

CI（根 `.github/workflows/ci.yml`）在 push / PR 自动跑同一组检查；本地可随时手动复跑同组命令。

### 18.4 退出码约定

| 码 | 含义 |
|:--:|:-----|
| 0 | 通过 |
| 1 | 有发现（审计器）/ 有断言失败（测试） |
| 2 | **环境故障**（解释器坏、文件缺失、用法错误） |

退出码 `0` 全过 · `1` 有判负。
如果解释器坏掉，脚本也返回 1 —— 会被误判成「判负通过」。**审计器的故障
绝不能被计成一次成功的判负。**
