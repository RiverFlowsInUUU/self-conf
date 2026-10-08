# 定位「泄露到运营商」的实测流程

> **何时读**：用户报「leak test 显示 China Telecom / 电信 / 联通 / 移动」，
> 或者**只是感觉**有泄露但说不清哪里漏。
>
> 本文是 mihomo（clash/）侧。Surge / Egern 侧见各自的 `leak-localization.md` ——
> 三侧的**归并方式一致**（按「谁触发了一次明文查询」分类），但**通道清单不同**：
> mihomo 侧多一条 IPv6 面，且引导链的键名与语义完全不同。

## 0 · 目录

| # | 节 | # | 节 |
|:-:|:---|:-:|:---|
| 1 | 先分清三类"泄露" | 6 | **③′ IPv6 泄露面（本仓特有）** |
| 2 | mihomo 的 DNS 通路图 | 7 | 修法对照表 |
| 3 | 抓包定位（最可靠）| 8 | 验证修好了 |
| 4 | 五类泄露面 · 定位与收口 | 9 | 结论：五类必须全堵 |
| 5 | 不抓包的近似判断 | 10 | FAQ · 边界 |

---

## 1 · 先分清三类"泄露"

`leak test` 的结果需要**分类解读**，它们指向完全不同的修法：

| 现象 | 含义 | 属于本项目的范围吗 |
|:-----|:-----|:-------------------|
| 检测到运营商 DNS 服务器 IP | **明文 `:53` 被链路读到** | ✅ 是，本文处理 |
| 检测到的是境外公共解析器（`8.8.8.8`） | 明文但也可能是你自己配的 | ✅ 是（面 ① 或 ②）|
| 显示节点出口 IP 的城市 | **不是泄露** —— 是你实际走代理的证据 | ❌ 否 |

⚠️ 第三类是**常见误报**。很多 leak test 网站会把"你从哪来"也列出来 ——
那正是代理在工作的标志。

⚠️ mihomo 侧还多一类**假象**：检测到 `198.18.x.x`。
那是 **fake-ip 段**（本仓 `fake-ip-range: 198.18.0.1/16`），
不是泄露 —— 它恰恰说明查询**被 mihomo 接住了**，只是没做真实解析。

## 2 · mihomo 的 DNS 通路图

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

## 3 · 抓包定位（最可靠）

### 3.1 环境

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

### 3.2 抓包命令

```bash
# macOS / Linux：抓 DNS 端口
sudo tcpdump -i en0 -n -s 0 'udp port 53 or tcp port 53' -w dns.pcap

# 只看目标地址，出结果快
sudo tcpdump -i en0 -n 'udp port 53' | awk '{print $3, $5}'

# ⭐ mihomo 侧要额外看 IPv6 —— 面③′ 不走 :53
sudo tcpdump -i en0 -n 'ip6 and not port 443' | head -40
```

### 3.3 读结果

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

### 3.4 时机很重要

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

## 4 · 五类泄露面 · 定位与收口

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

### 4.1 面① · 引导解析（冷启动必走一次）

**表现**：冷启动瞬间有一到两条明文 `:53`，查询的域名是 DoH 端点自己。

**机制**：`nameserver` 写的是 `https://dns.cloudflare.com/dns-query` ——
**端点本身是主机名**。要连它就得先知道它的 IP，这一问只能用 `default-nameserver`
（那一层是**明文 UDP**，因为它不能再依赖任何加密解析器，否则成环）。

⭐ **本仓已实测过这条**（CHANGELOG，2026-09-22，本地 mihomo 内核 + 本机 DNS sink）：

> 把唯一走明文 UDP 的 `default-nameserver` 顶到本机 sink 上跑真实解析，
> **明文 `UDP:53` 只出现在 `dns.google` / `dns.cloudflare.com` 两个 DoH 端点域名上**
> （解析端点自身所需的引导），业务域名与节点域名全部走 `443` 加密端点。

**定位方法**：

```bash
# 看引导层写了什么
grep -A3 'default-nameserver' clash/profiles/*.yaml
# 看主解析器是不是主机名（是 ⇒ 必然需要引导）
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

**验证脚本**：`skill/tests/clash/check_structure.py`（守 ipv6 与结构，不判引导）；
引导层本身**没有门禁** —— 靠 §3 的冷启动抓包实测。

### 4.2 面② · 回退链落到明文

**表现**：明文 `:53`，目标是某个解析器，查询的域名是**业务域名**。

**机制**：`fallback` 的作用是「主解析器的答案被判定为境外时，换一台再问一次」。
若 `fallback` 里写的是明文解析器（`8.8.8.8` / `114.114.114.114`），
那么每次 `fallback-filter` 命中 ⇒ **一次明文查询，且带的是业务域名**。

**定位方法**：

```bash
# 看 fallback 与 filter
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

### 4.3 面③ · 旁路设备（不识 DNS 设置的设备直接发 :53）

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
# 1. 家里有没有 HomePod / Apple TV / Chromecast / 智能音箱 / 智能电视？
#    有的话面③ 一定在发生
# 2. 抓包看源地址
sudo tcpdump -i en0 -n 'udp port 53' | awk '{print $3}' | sort -u
# 3. 确认劫持已开
grep -A3 'dns-hijack' clash/profiles/*.yaml
```

**验证脚本**：`skill/tests/clash/check_structure.py`（守结构与 ipv6，**不判 dns-hijack**）
⇒ **面③ 没有门禁**，靠抓包 + 人工核对 `tun` 段。

### 4.4 面④ · 规则判定触发的解析

**表现**：明文（或至少多余一次）解析，查询的域名是**你要访问的站点**。

**机制**：**IP 类规则没带 `no-resolve`，就会为了"判断这个域名是不是某个 IP 段"
而强制先解析一次。** 这条与 Surge / Egern 侧同构，但**落点不同**：

| 内核 | 写法 |
|:-----|:-----|
| Surge | `IP-CIDR,1.2.3.0/24,DIRECT,no-resolve`（行内）|
| mihomo | `RULE-SET,geoip-cn,DIRECT,no-resolve`（行内，规则级）|

**定位方法**：

```bash
# 找出所有 IP 类规则，看哪些缺 no-resolve
python - <<'PY'
import yaml
for f in ["lazy.yaml","routing.yaml"]:
    c = yaml.safe_load(open("clash/profiles/"+f, encoding="utf-8"))
    rp = c.get("rule-providers") or {}
    print("="*20, f)
    for r in c.get("rules") or []:
        p = [x.strip() for x in r.split(",")]
        prov = p[1] if p[0] == "RULE-SET" else None
        beh = (rp.get(prov) or {}).get("behavior") if prov else None
        if beh == "ipcidr" or p[0].startswith(("IP-CIDR","GEOIP","IP-ASN")):
            ok = "no-resolve" in [x.lower() for x in p]
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

#### 4.4.1 ⚠️ `no-resolve` 是双刃刀（补之前必读）

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

**补完之后必须再跑一次分流验证**（本仓**已有** mihomo 侧的分流覆盖审计脚本 `skill/scripts/clash/audit_routing_coverage.py`，闸门 #9 ——
这是与姊妹仓的一个差距，见 §9.2）。

**验证脚本**：无（本仓 mihomo 侧没有 `no-resolve` 审计器）。
定位靠上面的手工脚本；**收口后的分流验证靠实测**。

### 4.5 面⑤ · 远程规则集内嵌裸 IP 条目

**表现**：profile 里每条 IP 规则都写了 `no-resolve`，但日志/抓包显示仍有大量意外解析。

**机制**：规则是 `RULE-SET,<provider>,<policy>` —— **你引用的规则集在别人仓库里**。
如果那份 `.yaml` / `.mrs` 里有**裸 IP 条目且不带 `no-resolve`**，
那么**每个走到该规则的域名都会被强制本地解析一次**。

> ⚠️ **这是最容易漏的一条** —— 它不在你的 profile 里，**本地的静态门禁看不见**。
> 必须把规则集**下载下来数**才能发现。

**定位方法**：

```bash
# 本仓自托管的三份（真源 .list，零 IP 条目）
grep -cE '^(IP-CIDR|IP-CIDR6|IP-ASN|GEOIP|ASN)' rules/emby.list rules/apple_system.list rules/AI.list
# ⇒ 实测均为 0 —— 三份都是纯域名集

# 第三方（Jinx 的 classical yaml）要拉下来数
curl -s https://raw.githubusercontent.com/RiverFlowsInUUU/Jinx/main/mihomo-direct.yaml \
  | grep -cE 'IP-CIDR'
```

**本仓现役的规则集按行为分两类**（`skill/tests/clash/check_structure.py` 读得到 `behavior`）：

| behavior | 是否可能含裸 IP | 本仓哪些 |
|:---------|:----------------|:---------|
| `ipcidr`（mrs）| ✅ **是**（内容就是 IP 段）| `geoip-private` / `geoip-google` / `geoip-telegram` / `geoip-cn` |
| `domain`（mrs）| ❌ 否 | `cn` / `openai` / `github` / `youtube` … |
| `classical`（yaml）| ⚠️ 混合，要看内容 | `Jinx-CN` / `Jinx-Ads` / `emby` / `AI_Domains` / `apple-system` |

⭐ **`build_rules.py` 生成物自带结论**，头部注释写明：

```
# ⚠️ 纯域名集、零 IP 条目 ⇒ 引用方**不写**规则级 no-resolve。
```

⇒ `emby` / `AI_Domains` / `apple-system` 三份**零 IP 条目**
（`grep -cE '^(IP-CIDR|...)' rules/*.list` 实测均为 0），
**引用它们时不写 `no-resolve` 是正确的** —— 写了反而有害（见 §4.4.1 的刀刃二）。

**收口手段**：

1. 自托管的三份：改真源 `.list`，重跑 `build_rules.py`（**单一真源，不可能漂移**）；
2. 第三方集：要么换源，要么在规则行加 `no-resolve`（代价见 §4.4.1）；
3. 定期跑 `check_remote_urls.py` —— 它守的是「URL 活不活」，
   **不守内容**，但死链 ⇒ 空集 ⇒ 该走的规则不生效（静默降级）。

**验证脚本**：`skill/scripts/clash/build_rules.py --check`（只守**生成物新鲜度**，
不守第三方内容）。第三方内容**没有门禁** —— 靠人工拉下来数。

### 4.6 汇总：哪一面有门禁，哪一面没有

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

## 5 · 不抓包的近似判断

### 5.1 一张核对清单（按顺序过）

```bash
# ① 引导链
grep -A3 'default-nameserver' clash/profiles/*.yaml      # 期望：国内解析器（明文层只有它）
grep -A3 '^  nameserver:'     clash/profiles/*.yaml      # 期望：https://（端点为主机名 ⇒ 必有引导）

# ② 回退链
grep -A5 'fallback'           clash/profiles/*.yaml      # 期望：https:// 或整段不设

# ③ 旁路设备
grep -A3 'dns-hijack'         clash/profiles/*.yaml      # 期望：any:53

# ④ 规则判定（用 §4.4 的脚本列 IP 类规则）

# ⑤ 远程集内容
grep -cE '^(IP-CIDR|IP-CIDR6|IP-ASN|GEOIP|ASN)' rules/*.list   # 期望：0

# ③′ IPv6
grep -n '^ipv6:' clash/profiles/*.yaml; grep -n '  ipv6:' clash/profiles/*.yaml
# 期望：四处顶层 + 四处 dns 下，全为 false
python skill/tests/clash/check_structure.py              # 期望 exit 0
```

### 5.2 关于测试端点 —— **先确认它是不是泄露面**

mihomo 侧的健康检查与延迟测试 URL（`proxy-providers.*.health-check.url`、
`proxy-groups[].url`）在**本仓是 `https://www.gstatic.com/generate_204`**。

⚠️ **别急着把它当泄露面。** 这些探针走的是**代理路径**（`proxy-server-nameserver` 那一层，
本仓是国内 DoH），不是本地明文。它们是**性能探针**，不是泄露通道。

⚠️ 但有一条例外要核：`check_remote_urls.py` 的 `HC_URLS` 常量
把 `https://www.gstatic.com/generate_204` 排除在探测之外 ——
它是**连通性探测目标，不是规则集资源**，可达性检查不该探测它。

### 5.3 一个高频的"不是配置问题"

若本机或旁路上**另有**一台跑着 mihomo / OpenClash 的设备，
你从电脑探测到的 `:53` 可能被**透明重定向**到它 ——
返回的是 Fake IP（`198.18.x`），看不到真实出口。

判据：逐个外部解析器问同一个域名，若**全部**返回 `198.18.x.x` ⇒ 被旁路由吃掉了。

```bash
for s in 223.5.5.5 119.29.29.29 1.1.1.1 8.8.8.8; do nslookup www.qq.com "$s"; done
```

## 6 · ③′ IPv6 泄露面（本仓特有，Surge / Egern 侧无对应物）

⭐ **这一节是 mihomo 侧独有的。** Surge / Egern 侧的 `ipv6: false` 只影响
"是否返回 AAAA"，它们**没有 TUN** ⇒ 不存在"绕过 TUN"这条通路。
mihomo 侧因为**有 TUN**，IPv6 的两件事会叠加成一个真正的泄露面。

### 6.1 机制：两个开关，缺一个就漏

| 开关 | 作用 | 不关会怎样 |
|:---|:---|:---|
| `dns.ipv6` | 是否返回 AAAA 记录 | 开了 ⇒ 双栈站点拿到 AAAA |
| 顶层 `ipv6` | TUN 是否接管 IPv6 流量 | 关了 ⇒ **IPv6 流量不走 TUN** |

⇒ **关键组合**：`dns.ipv6: true` + 顶层 `ipv6: false`
= 应用拿到了真实的 IPv6 地址，但 IPv6 流量**不被 TUN 接管**
⇒ **双栈站点直接走本机真实 IPv6 出网，绕过代理** = 必然通路。

> 📌 CHANGELOG 原文记录的正是这条：
> 「此前 `dns.ipv6` 为 `true` 时会返回 AAAA 记录，而本机真实 IPv6 未被 TUN 完整接管，
> 双栈站点优先走 IPv6 ⇒ 出口 IP 与节点不符（表现为**站点测到美国 IPv6**）。」

### 6.2 表现

| 现象 | 说明 |
|:---|:---|
| leak test 显示**你的真实 IPv6 地址**（不是节点出口）| 最常见 |
| 站点测到"美国 IPv6"而你节点在日本 | 出口 IP 与节点不符 |
| 部分站点能开、部分超时 | 双栈站点优先 IPv6，那条路没代理 |
| **只有 IPv4 的站点完全正常** | 印证是 IPv6 侧的问题 |

⚠️ 误诊风险：这些现象也像"节点挂了"或"分流错了"。
**区分方法**：IPv4 侧（同一个站点的 A 记录）走代理正常，只有 IPv6 侧露馅 ⇒ 面③′。

### 6.3 定位方法

```bash
# 1. 看两个开关（四处 profile × 两处键 = 8 个位置）
grep -n '^ipv6:'  clash/profiles/*.yaml
grep -n '  ipv6:' clash/profiles/*.yaml
# 期望：全 false

# 2. 直接问 AAAA —— 有返回就说明 dns.ipv6 没关
nslookup -type=AAAA www.google.com

# 3. 抓 IPv6（面③′ 不走 :53，别只抓 53）
sudo tcpdump -i en0 -n 'ip6' | head -40

# 4. 门禁确认
python skill/tests/clash/check_structure.py        # 期望 exit 0
```

### 6.4 收口手段

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
| 只关顶层 `ipv6` | TUN 不管 IPv6，但 `dns.ipv6: true` 仍会返回 AAAA ⇒ **应用拿着 AAAA 直连出去**（正是 CHANGELOG 记的那个 bug）|
| **两个都关** | 不返回 AAAA ⇒ 应用只能走 IPv4 ⇒ IPv4 必经 TUN ⇒ **通路闭合** |

⭐ **两个都关才是"必然不通"**：关 `dns.ipv6` 让应用**拿不到** IPv6 地址，
关顶层 `ipv6` 让 IPv6 流量**即使存在也不被误当成已接管**。两者叠加才没有残余通路。

### 6.5 验证脚本

```bash
python skill/tests/clash/check_structure.py
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

## 7 · 修法对照表

| 面 | 修法 | 注意 |
|:---|:---|:---|
| ① 引导解析 | 接受它（方案 A）：把 `default-nameserver` 钉成国内解析器 | 换 IP 字面量会失去 CDN 就近解析与 ECS 合规；**机制上不可能完全消除** |
| ② 回退链 | `fallback` 只写 `https://`；或干脆不开 `fallback` | 开 `fallback-filter.geoip` 会双查（双倍延迟）|
| ③ 旁路设备 | `tun.dns-hijack: [any:53]` | 拦不住 DoH（443）；且设备流量必须经本机 |
| ④ 规则判定 | IP 类规则加 `no-resolve` | ⚠️ **必须同时确认 `MATCH` 前有域名类国内直连集**（§4.4.1）|
| ⑤ 远程集内容 | 自托管改真源 `.list` 重生成；第三方换源或加 `no-resolve` | 本地静态门禁**看不见**，必须拉下来数 |
| ③′ IPv6 | 顶层 `ipv6: false` **+** `dns.ipv6: false` | ⭐ **两个都要**，只关一个留残余通路（§6.4）|

### 7.1 面④ / 面⑤ 修完的必跑项

```
1. 国内网站是否仍直连（不绕代理）  ← 补 no-resolve 后最容易翻车的一条
2. 境外网站是否仍走代理
3. 游戏机 NAT 检测是否正常（fake-ip 下 STUN 类要走 fake-ip-filter）
```

✅ 本仓 **mihomo 侧已有分流覆盖审计脚本**（闸门 #9）⇒ 第 1、2 条可先跑它；⚠️ 但它的**离线档按规则集名推演**，不读实际策略（见 §4.4.1），所以仍需实测兜底 —— 别把它当充分条件。
这是与姊妹仓的已知差距（Surge 侧有 `audit_routing_coverage.py`，43 条判据）。

## 8 · 验证修好了

```
1. 冷启动抓包（§3.4 的 5 步）→ 应无业务域名的明文 :53
                              （端点域名那两条是面①，属可接受取舍）
2. python skill/tests/clash/check_structure.py        → exit 0（含面③′ 两条）
3. python skill/tests/clash/check_min_pair.py         → exit 0
4. python skill/tests/clash/check_script_sync.py      → exit 0
5. python skill/scripts/clash/build_rules.py --check   → exit 0
6. python skill/tests/clash/check_remote_urls.py      → exit 0（慢，按需）
7. python skill/tests/verify_all.py                   → exit 0（46 道）
8. leak test 网站复测 → 不再显示运营商 DNS
9. 实测：国内直连；游戏机 NAT 正常；IPv6 侧不再露真实地址
```

⚠️ 第 8 步的解读见 §1 —— **leak test 显示节点出口城市不是泄露**；
显示 `198.18.x.x` 也不是泄露（那是 fake-ip，说明被接住了）。

## 9 · 结论：五类必须全堵

### 9.1 归并口径回顾

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

### 9.2 由此得到的一条判断标准

> **判断一条通路是否必须消除的标准只有一条：它是否"必然会被走到"。**
>
> 一次性、可控、且能说清收益的通路（面① 的引导查询），不算必须消除的泄露面；
> 有明确触发条件、且会反复发生的通路（其余五类），**必须堵**。

### 9.3 ⚠️ 本仓 mihomo 侧的一个结构性缺口

把 §4.6 的结论再说一遍，因为它影响上面所有的"已收口"判断：

> **六个面里只有面③′ 有门禁。** 现有四道 clash 门禁守的是
> 结构 / 两形态一致 / 脚本静态一致 / 生成物新鲜度 —— **没有一道是防泄露语义审计器**。
>
> ⇒ 上表里 ② ③ 的「✅ 收口」是**当前文件的状态**，不是**被机器守住的状态**。
> 哪天有人把 `dns-hijack` 删掉、或把 `fallback` 改成明文解析器，
> **46 道门禁会全绿**。
>
> ⇒ 参照姊妹仓：Surge 侧有 `check_surge_dns.py`（12 项判据）、
> Egern 侧有 `check_egern_dns.py` + `audit_ruleset_noresolve.py`。
> **mihomo 侧缺这一层** —— 这是整合后最值得补的一块。

## 10 · 边界：什么情况不该"修"

不是所有明文 `:53` 都必须消除。以下属**可接受的取舍**，纠结它们是浪费：

| 情况 | 为什么可接受 |
|:-----|:-------------|
| **引导解析**（`default-nameserver` 解析 DoH 端点域名）| 机制上不可能消除。本仓已把它限定为"只解析端点自己的域名"，实测确认过（§4.1）|
| 设备用 DoH 直连（不经 mihomo）| DoH 本身加密，不算明文泄露。除非你要统一管控 |
| 企业内网 DNS（`192.168.x.1:53`）| 那是本地网络的一部分，不是"泄露到运营商" |
| `dns-hijack` 没穷举全部解析器 | `:53` 地址空间无限，列不全。用 `any:53` 才是正解 |
| 自建 DNS 服务器上的明文查询 | 那是你自己控制的链路，不是第三方 |
| 见到 `198.18.x.x` | **不是泄露** —— 是 fake-ip，说明查询被 mihomo 接住了（§1）|

> 📌 判断标准始终是同一条：**这条明文通路是否"必然会被走到"？**
> 一次性、可控、且能说清收益的通路，不算必须消除的泄露面。

---

## 11 · FAQ

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
**这正是 CHANGELOG 记过的那个 bug**。见 §6.4。

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
重出一份纯配置再比对最省事，别逐行手改。见 [`checker.md`](checker.md) §5.1。
