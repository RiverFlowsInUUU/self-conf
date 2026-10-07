# 加固模板（逐段完整版）

> **何时读**：要产出一份加固后的 mihomo profile 时，或想对照模板检查自己配置缺了什么。
>
> 本文件是 [`clash/profiles/routing.yaml`](../../../clash/profiles/routing.yaml) 的
> 逐段复刻 + 逐键理由。分流版 25 组 / 27 条，是三内核里结构最细的一份，
> 拿它做教学载体能把每一段的理由讲透。
> 只想直接拿走用 → 用仓库里的 `clash/profiles/routing.min.yaml`（纯配置）
> 或 `clash/override/my_clash.js`（挂到自己的订阅）。
>
> 📌 本文教的加固结构（tun 收口、dns 段分工、广告拦截双条件、IPv6 关闭）
> **对两份配置都适用** —— 懒人版只是在策略组与规则上更简。
>
> 相关：[`profile-anatomy.md`](profile-anatomy.md)（逐键语义）·
> [`leak-localization.md`](leak-localization.md)（泄露面定位）·
> [`pitfalls.md`](pitfalls.md)（踩过的坑）

## 0 · 目录

| # | 节 | # | 节 |
|:-:|:---|:-:|:---|
| 1 | 结构总览与顺序语义 | 7 | `fake-ip-filter`：谁必须跳过假 IP |
| 2 | `tun` 段：防泄露的收口装置 | 8 | 广告拦截的两个必要条件 |
| 3 | `dns` 段：四个键各管一段路 | 9 | 规则层：顺序铁律与 `no-resolve` |
| 4 | `default-nameserver`：引导解析器 | 10 | 订阅槽位：导入前必改的一处 |
| 5 | `nameserver` / `fallback`：主解析 | 11 | 逐项验证：用哪个脚本 |
| 6 | `nameserver-policy`：按域换解析器 | 12 | FAQ · 维护者须知 |

## 1 · 结构总览与顺序语义

```
ipv6: false                  # ① 顶层开关（与 dns.ipv6 成对，见 §3.6）
proxy-providers:             # 订阅槽位，唯一需要用户填的东西
proxy-groups:                # 25 个策略组
rule-providers:              # 25 份规则集（19 MRS + 1 AWAvenue + 2 Jinx + 3 自托管）
rules:                       # 27 条，自上而下
dns:                         # 防泄露本体
tun:                         # 收口装置
```

**顺序有语义**：`rules` 自上而下匹配，第一条命中即决定去向。

⚠️ 本仓的生成顺序由 `skill/scripts/clash/build_profiles.py` 固定（见该脚本的 `order`），
手工调整 YAML 顶层键顺序会在下次重新生成时被覆盖 —— 想改顺序改脚本，不要改文件。

## 2 · `tun` 段：防泄露的收口装置

> ⚠️ **先分清形态 —— 这一段只对「静态 profile」成立**
>
> | 形态 | 需不需要 `tun` 段 | 理由 |
> |:--|:--|:--|
> | **静态 profile**（`profiles/*.yaml`）| **必须有** | 用户直接导入这个文件，没人替他开 TUN |
> | **覆写脚本**（`override/*.js` 的输出）| **不该有** | 客户端（Mihomo Party / Clash Verge）**自己管理 TUN**，脚本只覆写策略组与规则 |
>
> 两种形态的判断标准不同，**勿混用**。脚本输出里没有 tun 不是缺陷，
> 把它补进脚本反而是越俎代庖（可能与客户端设置冲突）。
> 本仓 `build_profiles.py` 生成静态 profile 时会从静态版**继承** tun，
> 正是为了维持这个区分。

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

| 键 | 为什么必须有 |
|:--|:--|
| `dns-hijack: any:53` | 应用自己发的明文 `:53` 查询会被内核**接管**，而不是放出去。这是「不识 DNS 设置的设备」唯一的收口手段 |
| `auto-route` | 把出站流量拉进 TUN |
| `strict-route` | 锁死绕行 —— 没有它，仍有流量走物理网卡出去 |
| `stack: mips` | mihomo 自研协议栈（可选 system / gvisor / mixed / mips） |

⚠️ **官方语义**：不写协议前缀时默认 `udp://`，即 `any:53` 只收 UDP:53。
要把 TCP:53 也收进来，需再加 `tcp://any:53`。本仓当前只收 UDP —— 这是已知取舍，
详见 §12 FAQ。

### 2.1 这一段本仓真的丢过

由脚本重建**静态 profile** 时，直接用了脚本输出（其中本就没有 tun），
于是四份静态配置全没了 tun —— 防线破了而门禁全绿，因为当时没有任何判据检查它。

注意这不是「脚本少了 tun」的问题（脚本本就不该有），
而是「拿脚本输出当静态 profile 用」时**漏了继承**的问题。

现在有两道守门：

1. `skill/scripts/clash/build_profiles.py` 会从静态版**继承** tun，且自检要求它存在
2. `skill/tests/clash/check_structure.py` 第 ④ 项检查 `enable` / `dns-hijack` /
   `auto-route` / `strict-route` 四键

删掉 tun 实测会报 4 处并判负。

## 3 · `dns` 段：四个键各管一段路

mihomo 的 dns 段比 Surge / Egern 分得细，**四个键不要混用**：

| 键 | 管什么 | 本仓取值 |
|:--|:--|:--|
| `default-nameserver` | **引导解析器**：只用于解析 DoH 端点自身的域名 | `223.5.5.5` / `119.29.29.29`（纯 IP） |
| `proxy-server-nameserver` | 只解析**代理节点域名**（连节点前还没有代理可用，鸡生蛋） | `doh.18bit.cn` / `dns.alidns.com` |
| `direct-nameserver` | 只解析 **DIRECT 出站**的域名 —— 直连流量也不碰系统 DNS | 同上 |
| `nameserver` | **主解析器**：需要本地解析出真实 IP 的域名 | `dns.cloudflare.com` / `dns.google` |

### 3.1 `enhanced-mode: fake-ip`

```yaml
enhanced-mode: fake-ip
fake-ip-range: 198.18.0.1/16
```

代理域名只回假 IP，**真实解析在落地侧完成** —— 本地不留答案。

`198.18.0.0/15` 是 RFC 6815 保留段。⚠️ 这个地址曾被 Surge 侧的凭据扫描
判成「真实 IP」（那个内核不认识这个段），已加入 `DOC_NETS` 白名单。
两个内核的「常识」不同，整合时必须处理这类分歧。

### 3.2 `respect-rules: true`

DNS 查询自己也受路由规则管辖 —— 发往境外 DoH 的查询会按规则经代理发出。

### 3.3 `prefer-h3: false`

不优先 HTTP/3，只用 HTTP/1.1 + HTTP/2。

### 3.4 `use-hosts: true` / `use-system-hosts: false`

读配置里的 hosts，**不读系统 hosts 文件**（避免被本机污染）。

### 3.5 `fallback` 与 `fallback-filter`

```yaml
fallback:
  - https://dns.cloudflare.com/dns-query
  - https://dns.google/dns-query
fallback-filter:
  geoip: true
```

主解析器失败时的退路。`geoip: true` 让回退只在 geoip 判定需要时才用。

### 3.6 IPv6：两处都要关

```yaml
ipv6: false        # 顶层
dns:
  ipv6: false      # dns 段内
```

**只关一处会漏**：

- 只关 `dns.ipv6` → 顶层仍放行 IPv6 流量
- 只关顶层 → DNS 仍返回 AAAA 记录

后果是双栈站点优先走 IPv6、绕过 TUN，出口 IP 与节点不符
（表现为站点测到与节点所在地不同的 IP）。

## 4 · `default-nameserver`：引导解析器

```yaml
default-nameserver:
  - 223.5.5.5
  - 119.29.29.29
```

**只用于解析 DoH 端点自身的域名**。内核要求必须是**纯 IP**，不能写域名 ——
否则「解析解析器」这件事本身又需要一次明文解析，形成鸡生蛋。

本仓其余端点都写成 DoH URL 或 IP 字面量，引导需求只有极少数条目。

## 5 · `nameserver` / `fallback`：主解析

```yaml
nameserver:
  - https://dns.cloudflare.com/dns-query
  - https://dns.google/dns-query
```

⚠️ **如实标注待确认项**：这里用的是**主机名**而非 IP 字面量
（与 §4「端点一律写 IP」的纪律不一致）。

它成立的前提是 `default-nameserver` 能解析这两个主机名 ——
本仓 `default-nameserver` 是国内解析器（223.5.5.5 / 119.29.29.29），
解析 `dns.cloudflare.com` 与 `dns.google` **会走一次明文引导查询**。

这是已知代价（冷启动一次），修改需连带评估 `nameserver` 的可用性，
本仓尚未改成 IP 字面量。详见 §12 FAQ。

## 6 · `nameserver-policy`：按域换解析器

```yaml
nameserver-policy:
  "rule-set:AWAvenue-Ads": rcode://success
  "rule-set:Jinx-Ads": rcode://success
  "rule-set:private,cn":
    - https://doh.18bit.cn/dns-query
    - https://dns.alidns.com/dns-query
```

- 私有域 + 中国大陆域名交回**国内 DoH**（解析结果准、延迟低）
- 两条广告清单返回 `rcode://success`（空回答）—— 见 §8

⚠️ **顺序有语义**：广告项**必须排在 `private,cn` 之前**，
否则先命中 `cn` 就拿不到空回答。

⚠️ **两版写法不一致（待确认）**：分流版是 `rule-set:private,cn`，
懒人版是 `geosite:private,cn`。逗号分隔的多个 provider 名是否被内核
当作集合处理，本仓未取得源码级证据。判据以配置文件实际行为为准。

## 7 · `fake-ip-filter`：谁必须跳过假 IP

```yaml
fake-ip-filter:
  - "*.lan"                    # 局域网
  - "*.local"
  - "*.localdomain"
  - "*.home.arpa"
  - "+.msftconnecttest.com"    # 微软联网探测
  - "+.msftncsi.com"
  - "localhost.ptlogin2.qq.com"
  - "+.srv.nintendo.net"       # 游戏机
  - "+.stun.playstation.net"
  - "+.xboxlive.com"
  - "stun.*"                   # NAT 穿透
  - "time.*.com"               # 时间同步
  - "ntp.*.com"
  - "+.pool.ntp.org"
  - "+.market.xiaomi.com"
  - "rule-set:AWAvenue-Ads"    # 广告（必须列，见 §8）
  - "rule-set:Jinx-Ads"
```

通配语义：`+.` 含本域与任意层子域；`*` / `*.` 只匹配一层。

**这类东西拿到假 IP 会直接失效**（NTP 对不上、游戏机连不上、联网探测误判离线）。

## 8 · 广告拦截的两个必要条件

DNS 层拦截比规则层早（连接根本建立不起来），但要**两个条件同时满足**：

| 条件 | 配置 | 缺了会怎样 |
|:--|:--|:--|
| ① | `nameserver-policy` 里 `rule-set:<广告集>: rcode://success` | 域名被正常解析，拦截不生效 |
| ② | 同一个广告集在 `fake-ip-filter` 里再列一遍 | `withFakeIP` 中间件对 A/AAAA **直接返回假 IP**，请求永远到不了 ① |

**缺任一条件拦截就完全失效，而且不报错。** 这是本仓最隐蔽的一类坑。

还有第三个条件：**① 中的广告项必须排在 `private,cn` 之前**（见 §6）。

规则层 `AD` 组保留作兜底 —— DNS 拦截覆盖不到 IP 直连、DoH/DoT 与客户端缓存命中。

## 9 · 规则层：顺序铁律与 `no-resolve`

### 9.1 顺序铁律

白名单 → 广告 → Apple 更新/系统 → 内网 → AI → 应用 → 国内 → 兜底。

⚠️ 白名单**必须留在两条广告清单之前** —— 两份黑名单存在重叠域名，
顺序颠倒会把白名单里的功能域误杀。

### 9.2 `no-resolve`

IP 类规则（geoip-\*）原则上应带 `no-resolve`，避免为判定而触发一次本地解析。
纯域名规则集**不写**（没有 IP 规则，写了无意义）。

⚠️ **本仓现状不一致（待确认）**：

| 配置 | `geoip-*` 是否带 `no-resolve` |
|:--|:--|
| 分流版 | `geoip-google` / `geoip-telegram` / `geoip-cn` **未带** |
| 懒人版 | 两条都**带** |

`skill/reference/clash/verification.md` 里声称「两条 GEOIP 都不带」，
与懒人版实际写法矛盾。本仓尚未统一，改动前先确认 mihomo 对 `RULE-SET`
规则级 `no-resolve` 的语义。

## 10 · 订阅槽位：导入前必改的一处

```yaml
proxy-providers:
  Airport:
    type: http
    url: https://sub.example.com/api/v1/client/subscribe?token=REPLACE_WITH_YOUR_TOKEN
```

这是**占位假值**，不换的话所有走代理的流量不通。
`sub.example.com` 是 RFC 2606 保留域，不会指向真实主机。

节点来源：各策略组用 `include-all` 引入（proxies + providers），
不再需要手工列节点。`proxies` 段为空。

## 11 · 逐项验证：用哪个脚本

| 加固项 | 用什么验证 |
|:--|:--|
| tun 四键齐全（**仅静态 profile**）| `python skill/tests/clash/check_structure.py` |
| IPv6 两处关闭 | 同上 |
| 广告拦截双条件 + 顺序 | 同上 |
| 无悬空引用、规则指向存在 | 同上 |
| `.min` 与完整版一致 | `python skill/tests/clash/check_min_pair.py` |
| 脚本输出 = 静态文件 | `python skill/tests/clash/check_script_sync.py` |
| 规则集 URL 全可达 | `python skill/tests/clash/check_remote_urls.py` |
| 无真实凭据 | `python skill/tests/clash/check_secrets.py` |
| 不引用原仓资源 | `python skill/tests/check_selfcontained.py` |
| 生成物未过期 | `python skill/scripts/clash/build_rules.py --check`<br>`python skill/scripts/clash/build_profiles.py --check` |
| 全跑 | `python skill/tests/verify_all.py`（17 道） |

## 12 · FAQ

**Q：`dns-hijack` 只写 `any:53` 够吗？**
A：按官方语义它默认收 UDP:53。要收 TCP:53 需再加 `tcp://any:53`。
本仓当前只收 UDP，是已知取舍 —— 绝大多数明文查询走 UDP。

**Q：为什么 `nameserver` 用主机名而不是 IP？**
A：见 §5，这是历史写法、已知代价（一次明文引导解析）。
改成 IP 字面量需连带评估可用性，尚未改。

**Q：为什么 `proxies` 段是空的？**
A：节点全来自 `Airport` 订阅。只填一个订阅 URL 即可导入。
有固定节点也可以直接写进 `proxies`，它们与订阅节点合并入组。

**Q：分流版与懒人版加固结构一样吗？**
A：tun / dns / 广告拦截 / IPv6 完全一致，差别只在策略组粒度（25 vs 3）
与规则数（27 vs 11）。两版 `AD` 组口径不同（分流版 `REJECT,DIRECT`，
懒人版单成员 `REJECT`）—— 懒人版定位极简，不留放行口子。

**Q：改了脚本要做什么？**
A：`python skill/scripts/clash/build_profiles.py` 重新生成两份 profile + 两份 .min，
再跑 `verify_all.py`。不要手工改 profile —— 上次手工操作把 routing.yaml
纵向堆了 7 份。

## 13 · 维护者须知

- **改配置改脚本**，不要手工改 `profiles/*.yaml` —— 它们由 `build_profiles.py` 生成，
  手工改会在下次生成时被覆盖（而追加写会堆叠）
- **改规则集改真源** `rules/*.list`，不要改 `rules/*.yaml`（生成物）
- **新增加固项时同步加判据** —— 本仓丢 tun 那次就是因为只有配置没有判据
- **判别力要验证**：注入坏样例确认门禁真的会判负，只测「好配置通过」证明不了
- **两版口径不同的地方**（`AD` 组、`no-resolve`、`nameserver-policy` 键名）
  先确认再统一，不要想当然对齐
