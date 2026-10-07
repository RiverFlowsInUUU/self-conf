# 加固模板（逐段完整版）

> **何时读**：要产出一份加固后的 Surge profile 时。或者想对照现成模板检查自己配置缺了什么。
>
> 本文件是 [`surge/profiles/lazy.conf`](../../../surge/profiles/lazy.conf) 的完整复刻 + 逐行理由 ——
> **刻意用最简的那份做教学载体**（4 组 / 10 条），把每一段的理由讲透。
> 只想直接拿走用 → 用仓库里的 `surge/profiles/lazy.conf`（带注释）或 `surge/profiles/lazy.min.conf`（纯配置）。
>
> 📌 **本文教的加固结构（`[General]` 段、规则顺序铁律、`no-resolve` 成对交付）
> 对两份配置都适用** —— 分流版只是在 `[Proxy Group]` 与 `[Rule]` 上更细。
> 分流版专属的设计约束（`flatten` 的对应写法、Smart 组不能嵌套组、地区关键词双份）

## 0 · 结构总览

```
[General]       全局：加密 DNS / IPv6 / GeoIP / 测试端点 / 安全开关
[Proxy]         节点：中转链 + 落地
[Proxy Group]   策略组：Proxy / AI / AD
[Rule]          规则：白名单 → 广告 → AI → 系统 → 内网 → 国内 → 兜底
[Host]          特殊主机名
[URL Rewrite]   可选
```

**顺序有语义**：`[Rule]` 自上而下匹配，第一条命中即决定去向。

## 1 · `[General]`

### 1.1 DNS 段（防泄露本体）

```
dns-server = 223.5.5.5, 119.29.29.29, 1.1.1.1, 8.8.8.8
```

| 要点 | 说明 |
|:-----|:-----|
| **绝不能写 `system`** | 它承担引导与连通性测试职责。写 `system` = 把引导交给运营商 DHCP 下发的那台解析器 |
| **至少 2 个国内解析器** | 任一机构故障时有退路。本模板用阿里 + 腾讯 |
| **可含境外** | 用于验证「加密 DNS 就绪前的连通性」，不是主路径 |

```
encrypted-dns-server = https://1.1.1.1/dns-query, https://dns.google/dns-query, https://dns.alidns.com/dns-query
```

| 要点 | 说明 |
|:-----|:-----|
| **至少一个 IP 字面量** | 保证冷启动可用（不依赖引导解析） |
| **其余可以是主机名** | 但**每个主机名会被引导解析一次** —— 这是出口 ① |
| **多个不同机构** | 任一故障有退路 |

⚠️ 主机名端点是**刻意的取舍**，不是漏改。换成纯 IP 字面量能消掉这次解析，
但会失去「按域名走 CDN 就近解析」与「ECS 合规」。取舍后在 profile 内声明：

```
# audit-waive: 1 加密 DNS 端点保留 2 个主机名形式（dns.google / dns.alidns.com）。
```

```
encrypted-dns-follow-outbound-mode = false
```

**必须 `false`**。设 `true` 时 DoH 连接自己也要遵循代理规则 ——
若代理规则把解析器域名指向代理，就形成「要解析它 → 需要它 → 要解析它」的环，
Surge 会检测并回退**明文**。

```
hijack-dns = 8.8.8.8:53, 8.8.4.4:53, 1.1.1.1:53, 1.0.0.1:53, 9.9.9.9:53, 208.67.222.222:53
```

出口 ②。接管忽略 Surge DNS 的设备发出的明文 `:53`。

| 要点 | 说明 |
|:-----|:-----|
| **判据不是"列了几个"** | `:53` 的地址空间无限，永远列不全 |
| **覆盖最常见的 6 个即可** | Google / Cloudflare / Quad9 / OpenDNS |
| **想一网打尽写 `*`** | Surge 官方示例值。代价是极少数依赖原生 `:53` 行为的应用可能异常 |
| **拦不住 DoH** | DoH 走 443，不是 `:53` |

```
allow-dns-svcb = false
exclude-simple-hostnames = true
read-etc-hosts = true
use-local-host-item-for-proxy = false
```

| 键 | 值 | 理由 |
|:---|:---|:-----|
| `allow-dns-svcb` | `false` | 不下发 HTTPS/SVCB 记录。开启会让应用绕过 Surge 的部分解析路径 |
| `exclude-simple-hostnames` | `true` | 单标签主机名（`nas` / `router`）直接交系统，不产生查询 |
| `read-etc-hosts` | `true` | 尊重本机 hosts |
| `use-local-host-item-for-proxy` | **`false`** | 本地映射只服务 DIRECT；开启会把本地结果变成**硬性代理目标**，破坏远端解析 |

### 1.2 IPv6

```
ipv6 = false
ipv6-vif = disable
```

- `ipv6 = false`：不向客户端返回 AAAA 记录，双栈站点自动回落 IPv4。
  封堵面与 Egern 内核等效（Egern 默认不启用 IPv6），AAAA 绕过面收窄；
  2026-09-29 实测不影响 DNS 泄露面，官方对无 v6 需求的用户亦建议关闭
- `ipv6-vif = disable`：IPv6 已关，VIF 不再承载任何 IPv6 路径

### 1.3 GeoIP

```
geoip-maxmind-url = https://raw.githubusercontent.com/adysec/IP_database/main/geolite/GeoLite2-Country.mmdb
disable-geoip-db-auto-update = false
```

手工构造的 mmdb 不一定带 MaxMind 官方签名，可能报警。保持自动更新开启；
日志出现更新报错时改成 `true`（代价是库会变旧）。

### 1.4 测试端点（**性能探针，不是泄露通道**）

```
test-timeout = 5
internet-test-url = http://connect.rom.miui.com/generate_204
proxy-test-url = http://www.gstatic.com/generate_204
proxy-test-udp = apple.com@1.1.1.1
```

⭐⭐ **先定性，再选址：`proxy-test-url` 是给 `smart` / `url-test` 打分的性能探针，
不是泄露通道。** 官方 KB 明确「走代理策略时…DNS 解析永远在代理服务器进行」，
本地只在命中 DIRECT 时解析。

所以**按用途分工**，别一律求境内：

| 键 | 用途 | 建议 | 理由 |
|:---|:-----|:-----|:-----|
| `internet-test-url` | 连通性检测 | 国内 204 | 测的是「本机能不能上网」，国内端点更贴切 |
| `proxy-test-url` | `smart` 打分 | **境外**（`gstatic.com`） | 测含国际段的真实路径，对选节点才有参考价值 |
| `proxy-test-udp` | UDP 评分 | 目的地址写 IP 字面量 | 现值 `apple.com@1.1.1.1` 的探测目的是 `1.1.1.1` ⇒ 不因该探针产生解析（见本段末句） |

⚠️ **反面教材**：曾以"减少周期性解析面"为由把 `proxy-test-url` 改成境内 ——
理由是错的（见 §7 自检清单）。**如果一个字段的职责是"测准"，就不要用
"藏掉解析"去改它。**

| | 境外端点 | 国内端点 |
|:--|:---------|:---------|
| 解析路径 | 未被任何分流接住 → 走代理 | 被 `direct.txt` 接住 → 直连 |
| RTT 方差 | 大（受国际路由波动影响） | 小 |
| `smart` 评分质量 | 差 | 好 |

`proxy-test-udp` 的 `1.1.1.1` 是 IP 字面量，不产生解析。

### 1.5 流量处理

```
udp-policy-not-supported-behaviour = reject
udp-priority = true
block-quic = per-policy
```

| 键 | 值 | 理由 |
|:---|:---|:-----|
| `udp-policy-not-supported-behaviour` | `reject` | `https` 类型节点不支持 UDP 中继，落到它上面的 UDP 直接拒绝，语义清晰 |
| `udp-priority` | `true` | 系统繁忙时优先处理 UDP（游戏 / 视频通话受益） |
| `block-quic` | `per-policy` | 默认阻止 QUIC，只在策略明确支持时放行。QUIC 走 UDP，绕过 TCP 类规则会导致分流失效 |

### 1.6 局域网与安全

```
allow-wifi-access = false
allow-hotspot-access = false
proxy-restricted-to-lan = true
gateway-restricted-to-lan = true
```

⭐ 前两个保持 `false`：局域网设备的共享出口由专用网关承担，本机不开放
监听端口，暴露面归零。**后两个是安全项**：监听端口万一重新启用时，
即使上级网络 DMZ / 端口转发配得潦草也不会暴露到当前子网之外。**保持 `true`。**

### 1.7 Wi-Fi / 蜂窝

```
all-hybrid = false
wifi-assist = false
```

- `all-hybrid = true` 会让**每条 TCP 连接和每次 DNS 查询**同时走 Wi-Fi + 蜂窝 ——
  明确的耗电与流量代价
- `wifi-assist = true` 会在 Wi-Fi 弱时自动切蜂窝，打断代理连接

### 1.8 `always-real-ip`

```
always-real-ip = *.lan, *.local, *.localdomain, *.home.arpa, *.srv.nintendo.net, *.stun.playstation.net, *.xboxlive.com, stun.*, time.*.com, ntp.*.com, *.pool.ntp.org, *.market.xiaomi.com
```

两类：

| 类 | 例子 | 为什么 |
|:---|:-----|:-------|
| **本地类** | `*.lan` / `*.local` / `*.home.arpa` | 局域网设备必须拿真实地址 |
| **功能类** | 游戏机 / `stun.*` / `ntp.*` | NAT 类型检测与时间同步需要真实可路由地址 |

⚠️ **`always-real-ip` 只改变返回真实 IP 还是 Fake-IP，不改变流量的目的地。**
它不参与分流。

⚠️ 这些主机名如果在 `[Rule]` 里没被域名规则接住，会走到后面的 IP 类规则 ——
而那些规则带 `no-resolve`，对未解析的主机名**跳过**。所以需要在 `[Rule]` 里
用 `DOMAIN-SUFFIX` 先接住（见 §3.4）。

## 2 · `[Proxy]`

```
# 本模板不写死节点 —— 全部节点来自订阅（`Airport` 的 `policy-path`）。
# 要加自己的节点就照这样写：名字 = 类型, 服务器, 端口, 参数…
```

> 📌 沿革：这里曾长期写两条 `hysteria2` 占位节点（`Node-A` → `Proxy`、`Node-B` → `AI`），
> 让「只填节点、不导订阅」也能跑。2026-10-06 移除 —— 它让人以为必须手工补节点，
> 而实际上只填订阅即可。链式节点的机制仍见 §2.3，那是**你加链式节点时**要读的。

### 2.1 节点 `server` 用 IP 还是域名

⭐ **这是整份配置里唯一"必定发生"的本地解析。**

- 域名形式 → 每次建连都要先解析它一次（本机 + 直连）
- IP 字面量 → 不产生解析

**动手前先统计节点形式**：能换成 IP 的尽量换。

### 2.2 `download-bandwidth` 不要瞎写

它是 `hysteria2` 的**服务端**拥塞控制提示。填偏大 → 服务端猛发、链路 buffering 撑爆（bufferbloat）；
填偏小 → 浪费带宽。除非服务商明确公布数字，否则留给服务端自适应。

### 2.3 `underlying-proxy` 中转链

> 📌 当前模板不带中转链；这一节是**你自己加链式节点时**的机制与硬约束。

```
Node-C = https, <目标>, 443, …, underlying-proxy="落地节点名", …
                                     └─ 先连它，再由它去连目标
```

两条硬约束：

1. **被指向的名字必须存在**（在 `[Proxy]` 或 `[Proxy Group]` 里）。否则 Surge
   以「无法解析 `underlying-proxy`」**拒绝加载整份配置**。
2. **不能形成环**（`A → B` 且 `B → A`）。

⚠️ 这是文件里唯一需要**按顺序改**的地方：改节点名之前，先确认 `underlying-proxy`
引用的新名字存在。

### 2.4 `https` 类型不支持 UDP 中继

Surge 的代理类型限制。后果：落到这类节点上的 UDP 会被拒绝。
所以这类节点**不要做默认出口**，也不适合需要 UDP 的场景（游戏 / 部分 QUIC 应用）。

### 2.5 `reuse` 保持默认

`reuse = true`（默认）让连接复用 —— 每个请求省掉一次 TCP + TLS 握手。
设成 `false` 是自找延迟。

### 2.6 非 Surge 原生类型不写

`vless` / `XTLS Reality` 不是 Surge 的代理类型。写了会被跳过并告警，
只增加解析噪音。

### 2.7 内置策略别名

Surge 允许在 `[Proxy]` 段给内置策略起别名：

```
AdBlock = reject
```

之后可在规则 / 组里用这个名字。
⚠️ 但 `pre-matching` 的规则**建议直接写字面量内置名** —— 别名的解析链路更长，
字面量保证能过校验。

## 3 · `[Proxy Group]`

```
Airport = select, policy-path=https://sub.example.com/api/v1/client/subscribe?token=REPLACE_WITH_YOUR_TOKEN, update-interval=86400, hidden=true, icon-url=…/Airport.png
Proxy   = select, Smart, Select, …, icon-url=https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Proxy.png
Smart   = smart, include-other-group="Airport", icon-url=…/Auto.png
Select  = select, include-other-group="Airport", icon-url=…/Static.png
AI      = select, include-other-group="Proxy", icon-url=…/grok.png
AD      = select, REJECT, icon-url=…/AdBlock.png
```

> 📌 懒人版的订阅节点直接进 `Proxy` / `AI`（`smart` 只能靠 `include-other-group` 复制
> 具体节点）；分流版相反，那里的订阅节点只进 `Smart` / `Select` / 地区组。

### 3.1 `smart` 组

三个评分信号：

| 维度 | 说明 |
|:-----|:-----|
| 真实连接首字节延迟 | 主项，比 ping 贴近实际体验 |
| TCP 重传率 | 每 1% 约折算 50 ms |
| UDP 响应延迟 | 单列（`https` 类型不支持 UDP，UDP 表现必须单独看） |

重测间隔 5 分钟，**按站点记住最优策略**，成员越少选得越快。

### 3.2 `select` 组

用户手动选。**`smart` 会静默换节点** —— 需要出口 IP 稳定时（服务按 IP 做风控）
`select` 更合适。

### 3.3 不要写的参数

- `update-interval=3600` —— 只对**订阅型组**有意义，写在 `smart` / `select` 组上是空转
- `include-all-proxies=0` / `no-alert=0` / `hidden=0` —— 都已是默认值

### 3.4 ⚠️ 广告拦截**不能**指向策略组

```
# ❌ 会加载失败
RULE-SET,<ads.list>,AD,pre-matching
# ✅
RULE-SET,<ads.list>,REJECT,pre-matching,extended-matching
```

原因：`pre-matching` 要求在连接层启动前就确定策略，而策略组在运行时**可以解析成
DIRECT**（组被切走 / 成员动态变化），Surge 无法保证"一定拦得住"，于是
**直接拒绝加载整份配置**。

⇒ 这正是 `AD` 组被设计成「独立于拦截链路之外」的原因：拦截动作走字面量
`REJECT`，`AD` 组作为**面板上独立的手动开关**保留 —— 刻意的分层，不是遗漏。
**职责边界**：改默认拦截行为要改规则那一行；想让 `AD` 接管开关，把策略改成
`AD` 并**一并去掉 `pre-matching`**（这是明确的取舍）。

## 4 · `[Rule]`

```
# 1. 白名单（必须在 REJECT 之前）
RULE-SET,<surge-direct.list>,DIRECT

# 2. 广告拦截
RULE-SET,<surge-ads.list>,REJECT,pre-matching,extended-matching

# 3. 局域网 / 内网（IP 段带 no-resolve ⇒ 提前不触发解析）
RULE-SET,LAN,DIRECT,no-resolve
RULE-SET,<private.txt>,DIRECT          # 实测零 IP ⇒ 按 4.6 的取舍不写开关

# 4. AI 分流
RULE-SET,<AI.list>,AI,"update-interval=604800"   # 钉 commit、实测零 IP ⇒ 同上

# 5. Apple 系统
RULE-SET,SYSTEM,DIRECT

# 6. 国内直连（主承重墙）
RULE-SET,<direct.txt>,DIRECT           # 主承重墙；实测零 IP ⇒ 同上

# 7. IP 规则，放最后
GEOIP,CN,DIRECT,no-resolve

# 8. 兜底
FINAL,Proxy,dns-failed
```

### 4.1 铁律一：顺序

**白名单(DIRECT) → 黑名单(REJECT) → 常规分流（`direct.txt` / `GEOIP,CN`）**

REJECT 绝不能排在 `direct.txt` / `GEOIP,CN` **之后** —— 那等于白加，
因为国内广告域名会先被 `direct.txt` 接走。

### 4.2 铁律二：`no-resolve` 与国内直连集**成对**

见主干 `SKILL.md`。要点：给 IP 规则补 `no-resolve` 会**同时**关掉
「解析后判 IP 归属」这条直连路径。**判据是「数域名条目」，不是看规则集名字。**

实测反例：`ChinaMax.list` 12472 条里只有 64 条域名 —— 名字像国内域名集，
实际 99.5% 是 IP。单独引用它 = 国内域名全靠 IP 判定 = 加了 `no-resolve` 就坏。

### 4.3 铁律三：IP 类规则放最后

IP 类规则需要有已解析的地址。放在所有域名规则之后，使走代理 / 被广告拦截 /
国内直连的流量都**不必做本地 DNS 查询**。

### 4.4 `pre-matching` 与 `extended-matching`

| 选项 | 作用 |
|:-----|:-----|
| `pre-matching` | REJECT 提前到 **DNS 查询 / TCP-SYN 阶段**求值，连接层完全不启动。**最大一笔耗电优化** |
| `extended-matching` | 额外按 **TLS SNI / HTTP Host** 匹配。专治「App 直连 IP 导致域名规则失效」 |

⚠️ `extended-matching` 只加在**拦截**规则上。加在分流规则上会改变它的语义
（从"按域名"变成"按 SNI"）。

### 4.5 `FINAL` 的 `dns-failed`

```
FINAL,Proxy,dns-failed
```

规则求值因 DNS 失败而中断时，用代理策略而不是让请求直接失败。
走代理的域名由节点远端解析 —— 既修好失败，也**避免一次明文本地查询**。

### 4.6 `update-interval`

远程 `RULE-SET` 都应带：

```
RULE-SET,<url>,<策略>,"update-interval=604800"[,no-resolve]
```

一周刷新。`no-resolve` **不是**这条的固定尾巴 —— 取舍是「实测零 IP 条目的规则集不写、真含 IP 条目的必须写」，纯域名集写上是空转（Surge 四份 profile 共用这一条，见 [`../shared/rulesets.md`](../shared/rulesets.md) 原则 4b）。

⚠️ **别把这条判据说成"不写就不刷新"** —— Surge 手册写明该键缺省即 `86400`（24 小时），
只有**负值**才关闭自动更新 ⇒ 漏写只是让周期不可见，不会让规则集停在首次下载的版本。
真正需要"必须显式写"的是 **Egern**：官方只在示例里出现过 `update_interval`、未文档化缺省值。
本仓两侧统一钉成 604800：同周期、写法一致、文件里看得见。审计时**只报两件事**：
出现负值（= 关掉自动更新），或 Egern 的远程 `rule_set` 缺这个字段。

### 4.7 AI 集曾钉 commit，2026-09-28 改跟分支头

（原设计）AI 组的出口隔离是有意设计：AI.list 内容变没变，决定「哪些域名走 AI 组」。
钉 commit 让集合**可复现** —— 但代价是上游更新不自动跟进，要手动换 hash。

实测这个代价爆发了：ACL4SSR 的 AI.list 长期停在 51 行，Gemini 新形态
（aistudio / notebooklm / antigravity / sora / grok 等）全部缺失，AI 分流名存实亡。

⇒ 2026-09-28 起换 [Repcz/Tool](https://github.com/Repcz/Tool) 的 AI.list 并**改跟分支头**：
   该仓滚动维护、新 AI 域名进集快，「可复现」让位给「及时跟进」。集内均为纯域名系
   （DOMAIN / DOMAIN-SUFFIX / DOMAIN-KEYWORD / URL-REGEX，零 IP 条目），两内核语法均原生支持。
   分流版的 OpenAI / Gemini / Claude 四条 **bm7 专属集不受影响**（本就引用分支头）。

```
RULE-SET,https://raw.githubusercontent.com/Repcz/Tool/X/Surge/Rules/AI.list,AI,…
                                                      ^^^^^^^ 分支名（X = 该仓主分支）
```

## 5 · `[Host]`

```
localhost = server:system
*.lan = server:system
*.local = server:system
```

只列 Surge 自带 DNS 客户端可能处理错的特殊主机名。
`localhost` 内部就能解析；`*.lan` 已被 `exclude-simple-hostnames` + LAN 规则覆盖，
再映射一遍是冗余的 —— 但显式写入无害，且让意图清楚。

## 6 · `[URL Rewrite]`

```
^https?://(www\.)?g\.cn https://www.google.com 302
^https?://(www\.)?google\.cn https://www.google.com 302
```

可选段，与防泄露无关，纯便利。不需要可整段删掉。

## 7 · 交付前自检清单

```
[ ] dns-server 无 system、无主机名、≥2 个国内解析器
[ ] encrypted-dns-server 至少 1 个 IP 字面量
[ ] encrypted-dns-follow-outbound-mode = false
[ ] hijack-dns 已配置
[ ] use-local-host-item-for-proxy = false
[ ] proxy-test-url 按用途选址（打分宜境外 / 连通性宜国内），不作为泄露项检查
[ ] 所有 IP 类规则带 no-resolve（含第三方规则集里的条目）
[ ] FINAL 之前有域名体量足够的国内直连集（数域名条目，不是看名字）
[ ] 白名单 DIRECT 在第一条 REJECT 之前
[ ] REJECT 在 direct.txt / GEOIP,CN 之前
[ ] pre-matching 的策略是字面量 REJECT 族
[ ] always-real-ip 的功能类主机名被前置域名规则接住
[ ] 节点 server 能换 IP 的都换了 IP
[ ] 所有 underlying-proxy 指向的名字存在

[ ] python skill/scripts/surge/check_surge_dns.py <profile>              → exit 0
[ ] python skill/scripts/surge/audit_ruleset_content.py <profile>        → exit 0
[ ] python skill/scripts/surge/audit_routing_coverage.py <profile>       → exit 0
[ ] python skill/tests/check_secrets.py                                  → exit 0
[ ] 抓包实测：冷启动无明文 :53
[ ] 实测：游戏机 NAT 检测 / 时间同步正常
```

> ⚠️ 最后两条**没有脚本** —— 必须人工实测。审计通过 ≠ 配置可用。
