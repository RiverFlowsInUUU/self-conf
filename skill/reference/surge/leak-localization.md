# 定位「泄露到运营商」的实测流程

> **何时读**：用户报「leak test 显示 China Telecom / 电信 / 联通 / 移动」，
> 或者**只是感觉**有泄露但说不清哪里漏。

## 0 · 先分清三类"泄露"

`leak test` 的结果需要**分类解读**，它们指向完全不同的修法：

| 现象 | 含义 | 属于本项目的范围吗 |
|:-----|:-----|:-------------------|
| 检测到运营商 DNS 服务器 IP | **明文 `:53` 被链路读到** | ✅ 是，本文处理 |
| 检测到的是境外公共解析器（`8.8.8.8`） | 明文但也可能是你自己配的 | ✅ 是（出口 ② 或 ①） |
| 显示节点出口 IP 的城市 | **不是泄露** —— 是你实际走代理的证据 | ❌ 否 |

⚠️ 第三类是常见误报。很多 leak test 网站会把"你从哪来"也列出来 ——
那正是代理在工作的标志。

## 1 · 抓包定位（最可靠）

### 1.1 环境

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

### 1.2 抓包命令

```bash
# macOS：抓着 DNS 端口
sudo tcpdump -i en0 -n -s 0 'udp port 53 or tcp port 53' -w dns.pcap

# 只看目标地址，出结果快
sudo tcpdump -i en0 -n 'udp port 53' | awk '{print $3, $5}'
```

### 1.3 读结果

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

### 1.4 时机很重要

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

## 2 · 不抓包的近似判断

如果没法抓包，按这个顺序排查：

### 2.1 出口 ①

```bash
python skill/scripts/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 1\]'
python skill/scripts/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 2\]'
```

- `[1]` 报「N 个加密 DNS 端点不是 IP 字面量」→ 出口 ①
- `[2]` 报「`dns-server` 里出现 `system`」→ 出口 ①

### 2.2 出口 ②

```bash
python skill/scripts/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 3\]'
```

- 报「缺少 `hijack-dns`」→ 出口 ② 完全敞开
- 报「未覆盖 N 个知名境外解析器」→ 出口 ② 部分敞开

**辅助判断**：家里有没有 HomePod / Apple TV / Chromecast / 智能音箱 / 智能电视？
有的话出口 ② 一定在发生。

### 2.3 出口 ③

```bash
python skill/scripts/surge/check_surge_dns.py <profile> 2>&1 | grep -A2 '\[ 12\]'
python skill/scripts/surge/audit_ruleset_content.py <profile> 2>&1 | grep -B1 -A3 'HIGH'
```

- `[12]` 报「第 N 行的 IP 类规则缺少 `no-resolve`」→ 本地规则缺
- `audit_ruleset_content` 报「N 条 IP 类条目**不带 no-resolve**」→ **远程规则集**里有

⚠️ **后者是最容易漏的** —— 它不在你的 profile 里，你本地的审计器看不见。
必须下载规则集内容才能发现。

### 2.4 关于测试端点 —— **先确认它是不是泄露面**

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

## 3 · 修法对照表

| 定位到的出口 | 修法 | 注意 |
|:-------------|:-----|:-----|
| ① 引导解析 | `encrypted-dns-server` 端点改 IP 字面量；`dns-server` 去掉 `system` 与主机名 | 换成 IP 会失去"按域名走 CDN 就近解析"与 ECS 合规 |
| ② 旁路设备 | 配 `hijack-dns`；想全量写 `*` | `hijack-dns` **拦不住 DoH**（走 443） |
| ③ 规则触发 | 所有 IP 类规则加 `no-resolve`（本地 + 远程规则集） | ⚠️ **必须同时确认 `FINAL` 前有域名体量足够的国内直连集**，见下 |
| 测速端点 | 换国内 204 | 见 [`hardening-template.md`](hardening-template.md) §1.4 |

### ⚠️ 出口 ③ 的修法有个陷阱

给 IP 规则加 `no-resolve` 会**同时**关掉「解析后判 IP 归属」这条直连路径。
若 `FINAL` 前没有域名类国内直连集，国内网站会整片走代理。

**修完必须再跑一次分流覆盖审计**：

```bash
python skill/scripts/surge/audit_routing_coverage.py <profile>
```

期望国内探针全部命中 `DIRECT`。详见 [`pitfalls.md`](pitfalls.md) 坑 1。

## 4 · 验证修好了

```
1. 冷启动抓包（§1.4 的 5 步）→ 应无明文 :53
2. python skill/scripts/surge/check_surge_dns.py <profile>       → exit 0
3. python skill/scripts/surge/audit_ruleset_content.py <profile> → exit 0
4. python skill/scripts/surge/audit_routing_coverage.py <profile>→ exit 0
5. leak test 网站复测 → 不再显示运营商 DNS
6. 实测：国内网站直连（不绕代理）；游戏机 NAT 检测正常
```

⚠️ 第 5 步的解读见 §0 —— **leak test 显示节点出口城市不是泄露**。

## 5 · 边界：什么情况不该"修"

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
