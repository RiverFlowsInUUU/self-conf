# 已知缺陷（18 条）

> 本文是 [`SKILL.md`](../../SKILL.md) 的引用文件。 **何时读**：排查实际泄露、或改动审计判据 / 规则集之前。

每条都是真实事故复盘。**「审计通过 ≠ 配置可用」是贯穿全部 18 条的母题** ——
连续 5 次出现「脚本全绿、实测仍有问题」，每次的结论都一样：
必须假设「存在审计器看不见的维度」，并把它补成一个可复跑的脚本。

## 目录

1. 用 JSON API 判 DoH 端点死活 → 误判。
2. 给 `geoip` 加 `no_resolve` 会悄悄改掉 DNS 端点的路由。
3. 自己的审计脚本只能验证自己编码进去的假设。
4. 别假定 `.list` 是域名表。
5. `policy` 嵌在类型字典里。
6. `proxy_nameservers` 不是"多加一层保险"，是"砍掉整条 forward"。
7. 审计器的"兜底判定"不要只认一种写法。
8. `forward` 里的 `proxy_rule_set` 若含 IP 类条目且不带 `no-resolve`，会为了判定而强制一次预解析。
9. 审计器"看不见"的那一类名字，就是最终泄露的那一类。
10. 官方文档说"未配置或解析失败时自动使用系统 DNS"—— 这句是"运营商泄露"的入口，别只当兜底描述读。
11. 先确认"用户是在什么设备、什么链路上测的"，再谈机制。
12. 端点写成 IP 字面量之前，必须逐个实测它真的能用。
13. 兜底组挂在"必须经代理才可达"的组上 —— 审计器判 OK，用户实测却是 `upstream: bootstrap`。
14. 看到客户端词汇表里的名字（`bootstrap` / `system`），一步就能锁定"明文回退面"。
15. 漏写 `no_resolve` 的 `geoip`，会给每一个走到它的域名强制一次本地预解析 —— leak test 的随机子域正是靠这条路进场的。
16. 强制解析不写在 profile 里，藏在别人仓库的 `.list` 里。
17. 治好 DNS 泄露的那一手，会顺手把国内域名的分流一起干掉 —— 它们是同一个机制。
18. 不要把节点域名写进 DNS 分流规则 —— 它既没用，又让配置"看起来需要随订阅维护"。

---

**坑 1：用 JSON API 判 DoH 端点死活 → 误判。**
`?name=x&type=A` + `accept: application/dns-json` 是 Google 风格的**可选** JSON API。RFC 8484 只强制**线格式**（`?dns=<base64url>` + `accept: application/dns-message`）。`dns.google`、`8.8.8.8`、`dns.alidns.com` 用 JSON 都会回 400 —— 它们没坏。**判断端点是否可用，只能用 `skill/scripts/egern/probe_doh.py` 的线格式请求。**

**坑 2：给 `geoip` 加 `no_resolve` 会悄悄改掉 DNS 端点的路由。**
`no_resolve: true` 之后 geoip **不再匹配域名**（官方："仅匹配已解析的 IP 地址"）。于是以主机名出现的加密 DNS 端点失去「CN → DIRECT」，只能靠某个 rule_set 里的 `DOMAIN-SUFFIX,cn` 兜住 —— 而那个规则集一旦加载失败（例如含 Egern 未文档化的类型），国内 DNS 查询就落到 `default → 代理`，被绕到境外出口再回国内，超时后**回退明文 bootstrap → 运营商 DNS**。**这就是"DNS 泄露到运营商"的完整机制链。修法：给每个 DNS 端点写显式路由（见模板），别依赖规则集内容。**

**坑 3：自己的审计脚本只能验证自己编码进去的假设。** 脚本报 `0 high` 不等于真的没泄露。用户实测出泄露时，必须回到**机制层**重新推导（回退链 / 端点路由 / 分组兜底），而不是重跑同一个脚本。

**坑 4：别假定 `.list` 是域名表。** 实测 `ChinaMax.list`：12614 条里 **12472 条是 IP-CIDR/IP-CIDR6** 另有 1 条 `IP-ASN`（IP 类合计 12473），域名只有 64 条，还含 65 条 `USER-AGENT` 和 **12 条 `PROCESS-NAME`（Egern 未文档化）** —— 这几档相加恰好等于 12614。用之前**下载 + 统计类型分布**（见 `skill/scripts/egern/profile_ruleset.py`）。⚠️ 但"IP 多"不等于"会触发解析"：2026-09-27 现抓该文件的 IP 条目**全部带 `,no-resolve`** ⇒ 它的代价是体积与匹配，不是解析（裸 IP 条目那种雷见坑 16）。
　→ ⚠️ **这条不只是"别误判"，它还有直接的后果**：把它当"国内域名走直连"的兜底规则用，等于没有兜底。真正能兜住的是 `ChinaMax_All_No_Resolve.list`（111k 域名 + 同份 IP，IP 条目全带 `no-resolve`）。详见**坑 17**。

**坑 5：`policy` 嵌在类型字典里。** `- domain: {match: x, policy: Proxy}` —— 读 `r.get('policy')` 永远得到 `None`（审计器 f1 就是这么废掉的）。要读 `r[type]['policy']`。

**坑 6：`proxy_nameservers` 不是"多加一层保险"，是"砍掉整条 forward"。**
官方：一旦设置，**所有代理 DNS 查询强制走它、完全绕过 `forward` 规则、且强制直连**。所以"顺手加一行指向阿里/腾讯"这件事，实际效果是**把代理侧解析无条件钉死在国内解析器上**（哪怕 `forward` 里已经把节点域名引到了正确的组）。**默认不要设它**；要设必须能说清为什么，并在报告里写明"成为唯一出口"的代价。**实测教训：f1 加了它 → 用户实测仍泄露，且比原配置更确定。**

**坑 7：审计器的"兜底判定"不要只认一种写法。** f2 里把 `has_catchall` 写成「最后一条必须是 `domain_wildcard: '*'`」，于是配置里写 `domain_regex: '.'` 这条等效兜底时被误报 HIGH、而 `domain_wildcard` 前面的同义兜底又被算成"靠前规则指向境外组"报了假 LOW。**判定要按语义（是否覆盖一切域名）而不是按字面键名+位置**；同时必须显式排除兜底规则本身，避免它污染"靠前规则"检查。修好后同一份 f3 从 `1 high/3 low` 变成 `0 high/1 low`。

**坑 8：`forward` 里的 `proxy_rule_set` 若含 IP 类条目且不带 `no-resolve`，会为了判定而强制一次预解析。** 实测 `ChinaDomain.list` 里那 9 条 `IP-CIDR(6)` 都带 `no-resolve`，所以安全；但用户自选的规则集不保证。审这类文件时**一定要数类型分布**（`skill/scripts/egern/profile_ruleset.py`）。

**坑 9：审计器"看不见"的那一类名字，就是最终泄露的那一类。**
f3 的审计结果是 `0 high / 1 low`，但用户实测**持续泄露到中国电信**。原因是脚本只检查了「用户会访问的域名」和「节点域名」，**从没把 profile 自己运行必需的域名（延迟测试 URL、策略组图标）拉进来做覆盖判定**。补上这项检查后：原始配置 `4 high`、**f3 `2 high`**（两个 latency test 域名）、f4 `0 high` —— **f3 的"0 high"是审计盲区造成的假安心**。
同时修掉一个 helper bug：`hostpart()` 里 `SCHEME` 白名单只有 `udp|tls|https|quic|h3`，遇到 `http://…`（延迟测试 URL 正是这种）不剥离协议头，再按 `:` 切就得到假主机名 **`'http'`**，导致检查结果牛头不对马嘴。**修法：先按 `'://'` 通用剥离，不依赖协议白名单。**（检查一个 URL 类字段的解析结果时，务必先打印几个样例看看解析出来的是什么。）

**坑 10：官方文档说"未配置或解析失败时自动使用系统 DNS"—— 这句是"运营商泄露"的入口，别只当兜底描述读。** 它意味着**任何一次上游失败都可能把查询交给你家路由器的 DNS**。所以在 CN 环境下，判断标准不是"我配的解析器够不够好"，而是"**有没有任何一条路径会失败**"。
配套的另一半在同一页：bootstrap 的**用途①是「解析 `upstreams` 中加密 DNS 服务器的主机名」**。所以**端点上每写一个主机名，就多欠一次明文查询**；写 IP 字面量则一次都不产生。这也解释了官方示例为什么写成 `https://8.8.8.8/dns-query` 而不是 `https://dns.google/dns-query`。
顺带：`bootstrap` 里的特殊值 `system` = 「合并系统 DNS（Wi-Fi/**蜂窝网络下发**的 DNS）」→ **在配置里写 `system` 等于主动把运营商解析器接进回退链**，审计器现在把这条判 HIGH。

**坑 11（流程坑，代价最大）：先确认"用户是在什么设备、什么链路上测的"，再谈机制。**
本次真实事故：用户报"新规则会泄露中国的 ISP"，我**默认他在和之前同一台 Windows + 同一张旁路由网络上测**，于是花了一整轮做本机网络侧实测（`:53` 被旁路由劫持成 `198.18.x`、`whoami.akamai.net → 219.128.79.150`），并据此产出一份"根因报告"。下一句用户说"**leak test 肯定是 iPhone 上跑的，用流量**" —— **旁路由根本不在链路上，那整套证据与结论全部作废**。
**规矩：动手前先问清三件事 —— ① 哪台设备（有没有可能根本没装这个客户端）；② 哪条链路（Wi-Fi / 蜂窝 / 有线）；③ 谁提供的 DNS（家庭路由器 / 运营商 / 系统级加密 DNS）。** 不同链路下"明文 :53 的下场"完全不同：
- 家庭网 + 旁路由：:53 被透明重定向到旁路由的 Fake IP（**看起来像"解析成功但返回假 IP"**）；
- 运营商蜂窝：:53 被运营商透明重定向到它自己的递归解析器，或直接不通后掉到系统 DNS（**看起来就是"leak test 显示运营商"**）。
两种都是同一条"明文回退"链，但**要拿的实测数据完全不同**。先问，再测。

**坑 12：端点写成 IP 字面量之前，必须逐个实测它真的能用。**
"IP 字面量 + 证书覆盖该 IP"不是想当然的。实测：`https://223.5.5.5/dns-query`、`https://1.12.12.12/dns-query`、`tls://1.12.12.12` 都正常；但 **`https://9.9.9.9/dns-query` 直接失败 —— `HTTP Version Not Supported`**（Quad9 在 `9.9.9.9` 上只提供 HTTP/3，不响应 RFC8484 的 HTTP/1.1 线格式；`149.112.112.112` 同样），而 **`tls://9.9.9.9` 正常**（证书 `CN=dns.quad9.net`）。**写错形式 = 白占一个端点，而且它是"静默失效"**，不会在配置校验时报错。
测法见 `skill/scripts/egern/probe_dns_endpoints.py` —— **直接吃 profile 文件**，把 `upstreams` / `proxy_nameservers` / `bootstrap` 里每个端点逐个跑一遍（DoH 走 RFC8484 线格式、DoT 走 853 握手并校验证书、裸 IP 走 UDP:53），最后输出「失效端点 N / M」。**加固后报告里附上这张表，别只写"端点已改 IP"。**（f5 实测：15 个端点 0 失效。对候选端点应**连测 3 轮**再下"稳定/不稳"的结论 —— 本次就吃过一次单轮抖动误判。）

**坑 13：兜底组挂在"必须经代理才可达"的组上 —— 审计器判 OK，用户实测却是 `upstream: bootstrap`。**
本次事故：f5 把兜底指向 `Foreign-DNS`（端点全为 IP 字面量、且都在 `rules` 里判给 Proxy），审计判 `0 high`。用户复测报 **`upstream: bootstrap`**。复盘出两个漏洞：
1. 官方只写了「未命中 Forward 回退 Bootstrap」，**"命中组的端点全失败"会怎样并没有写** —— 未定义行为。一旦它同样回退 bootstrap，兜底挂在境外组就是一条明文通道。
2. 兜底组经代理 ⇒ 引入隐式依赖「**先有代理，才敢解析**」。**启动阶段**（规则集与 `geoip_db_url` / `asn_db_url` 的下载、策略组首轮测速）代理尚未就绪，这一刻的本地解析会掉进 bootstrap 明文。本次配置里 `raw.githubusercontent.com` 正是这类**启动依赖**（规则集 + 两个 DB + 用户自己的策略组图标都托管在它上面），在 f5 里它落到兜底 → 境外组 → 启动期必然失败。
⇒ **判据收紧为「端点全为 IP 字面量 + 至少一个在 `rules` 里判给 `DIRECT`」**（即"直连可达"，而非"路由确定"）。修好后 f5 `1 high`、f6 `0 high`。**教训：对"审计器给了 OK"保持不信任 —— 脚本只能验证你编码进去的假设，而"这组在代理没起来时还能用吗"从来不在假设里。**

⚠️ **该判据在 f10（2026-09-20）后被双向化 —— 别再用上面那半句当完整判据。** f10 删掉了全部 15 条 DNS 端点路由规则（`upstreams`/`proxy_nameservers`/`bootstrap` 全是 IP 字面量 ⇒ 解析器直接以 IP 访问，不需要在 `rules` 里钉域名/IP），于是「至少一个在 `rules` 里判给 `DIRECT`」这半句**永远不成立** ⇒ 脚本把自有模板误判 `3 high`、退出码 1（外部审查报告抓到的就是这个）。
现在的完整判据是**两条二选一**：
- **(a) 旧判据**：端点全为 IP 字面量，**且至少一个在 `rules` 里判给 `DIRECT`**（适用于把 DNS 端点显式路由的配置）；**或**
- **(b) 新判据**：端点全为 IP 字面量，**且至少一个是已知的国内解析器 IP**（`check_egern_dns.py` 里的 `DOMESTIC_RESOLVER_IPS` 白名单：223.5.5.5 / 223.6.6.6 / 119.29.29.29 / 1.12.12.12 / 120.53.53.53 / 114.114.114.114 / 180.76.76.76 …）—— 国内到这些 IP 的可达性是**公共事实**，不需要在 profile 里用路由来"证明"。

❗ **绝不要采纳「端点全为 IP 即充分」这种更宽的写法** —— 一个全为境外 IP 的组（如纯 `8.8.8.8`）虽是 IP 字面量，却必须经代理才可达，那会**直接回退到坑 13 的 f5 事故形态**。放宽必须保留收紧面。
回归守卫：`tests/` 目录下有五份合成 profile —— **改 `group_reach` 判据后必须五份都跑**
（或把构造的几份 yaml 同时喂给两个脚本逐份验证）：

| profile | 构造 | 期望 | 命令 |
|---|---|---|---|
| `skill/tests/egern/bad_foreign.yaml` | 兜底组端点全为**境外** IP（`8.8.8.8` / `1.1.1.1`） | **HIGH + 退出码 1** | `python skill/scripts/egern/check_egern_dns.py skill/tests/egern/bad_foreign.yaml` |
| `skill/tests/egern/bad_hostname.yaml` | 兜底组端点含**主机名**（`dns.alidns.com`） | **HIGH + 退出码 1** | `python skill/scripts/egern/check_egern_dns.py skill/tests/egern/bad_hostname.yaml` |
| `skill/tests/egern/ok_route.yaml` | 兜底组端点全为国内 IP **且有显式 `ip_cidr → DIRECT`**（走判据 A） | **通过 + 退出码 0** | `python skill/scripts/egern/check_egern_dns.py skill/tests/egern/ok_route.yaml` |
| 临时构造：`ipv6_only.yaml` | 端点仅 IPv6 国内解析器（`[2400:3200::1]`） | **通过 + 退出码 0，且两脚本结论必须一致** | 喂 `check_egern_dns.py` + `audit_dns_forward.py` |
| 临时构造：`scheme_case.yaml` | 端点 scheme 写成大写（`HTTPS://` / `TLS://`），其余与正确版**逐字相同** | **通过 + 退出码 0，结论必须与正确版完全相同** | 喂 `check_egern_dns.py` + `audit_dns_forward.py` |

前两个是**收紧面**（证明判据没被放宽成"全 IP 即安全"）；后三个是**放行面**（分别证明判据 A 路径、
IPv6 端点解析、scheme 任意拼法都仍有效）。后两份的期望值都必须在**修 bug 之前先验证它会失败** ——
否则只是个恒绿的摆设。

⭐ **同一判据只要在第二处有实现，就必须在注释里互指。** `audit_dns_forward.py` 的 `endpoint_route`/`direct_ips` 与 `check_egern_dns.py` 的 `group_reach` 是**同一判据的副本** —— 只改一个，两个脚本就会给出相反结论（比没有脚本更糟）。改判据时**两处一起改**，并跑 `check_egern_dns.py` + `audit_dns_forward.py --drill` 双确认。

**坑 14：看到客户端词汇表里的名字（`bootstrap` / `system`），一步就能锁定"明文回退面"。**
`bootstrap` 不是网络上的实体，是 **Egern 内部给启动 DNS 组起的名字** —— 官方把它和 `system` 并列为可直接引用的 upstream 值（`bootstrap` 展开为全部 Bootstrap 服务器，`system` 展开为系统 DNS），而这个字符串**第三方泄露测试站不可能打印**（它们只给 IP / ASN / 国家）。所以一旦用户报出它，就说明**有一次查询确实走了明文 UDP:53**，范围立刻锁死到"谁把它推上去的"：
- **用途①** 解析 `upstreams` 里的主机名端点 → 查端点是不是域名；
- **用途②** 未命中 Forward 的最终回退 → 查兜底在不在、兜底组可不可直连。
反过来也成立：**报"泄露到某运营商"时，先索要这一栏的名字**（是 IP？还是 `bootstrap` 这类客户端标签？），比让他描述"访问哪个网站"有用得多。

**坑 15：漏写 `no_resolve` 的 `geoip`，会给每一个走到它的域名强制一次本地预解析 —— leak test 的随机子域正是靠这条路进场的。**
官方 rules 文档：`no_resolve` **只适用 `geoip` / `ip_cidr` / `ip_cidr6` / `asn` 四类**，语义是"不触发 DNS 解析"。**不写 = 为了判定归属必须先解析一次**。本次事故的完整链（每一步都在配置里有坐标）：
```
aaaa.dnsleaktest.com（随机子域）
  → 不在任何规则集里（实测 bm7-Proxy / Apple_All / ChinaMax / Lan / ChinaDomain 全部 0 命中）
  → 落到 rules 里那条 geoip:CN（原配置没有 no_resolve）⇒ 强制本地解析一次
  → 默认 DNS → forward 兜底 → Foreign-DNS（端点是主机名 dns.google / cloudflare-dns.com）
  → Bootstrap 用途①：明文 UDP:53 解析 dns.google ⇒ 蜂窝上被运营商接管 ⇒ 解析器归属 = 运营商
```
**两个必要条件缺一不可**（漏 `no_resolve` + 主机名端点），这也是为什么泄露表现为"每测一次漏一次"。**审别人的配置时，`geoip`/`ip_cidr` 的 `no_resolve` 要当成 P0 项看。**

**坑 16（f7 的真正解法，也是最反直觉的一条）：强制解析不写在 profile 里，藏在别人仓库的 `.list` 里。**
本次的真实链路（用户报了 `default → Final → Proxy` + `upstream: bootstrap` 同时出现）：
```
aaaa.dnsleaktest.com
  → rules 0..40 全不命中（实测这些规则集里确实没有 dnsleaktest）
  → 命中 rules[41]  rule_set: Apple_All.list → DIRECT，**enabled**
       而该文件里有 13 条 `IP-CIDR,x/y` **没带 ,no-resolve**
       ⇒ 官方语义：不带 = 会触发解析 ⇒ **为了判定这条 IP 规则，先强制本地解析一次**
  → 这次解析走了明文（日志里的 `upstream: bootstrap`）
  → 之后继续往下匹配，42/44/45/46 都不中 → rules[47] `default → Final → Proxy`
  ⇒ 于是日志里"判定"与"解析"看起来矛盾：「default → Final → Proxy」但 upstream 是 bootstrap
```
**诊断要点：`upstream: <明文标签>` 与"判定结果看起来没问题"同时出现 ⇒ 去找"为了判定某个规则而被迫发生的解析"。**
排查顺序：把 profile 里**所有** `rule_set` / `proxy_rule_set` 的 URL 抓下来，逐个统计"IP 类条目里有多少条不带 `no-resolve`"，并确认该规则 `disabled` 与否。实测 22 个规则集的结论（含 2026-09-21 新增的 `white-guard` / `ads`，两条均为纯域名、无 IP 条目）：**只有 `Apple_All.list` 有问题（13/13 全裸；2026-09-27 复取仍全裸 —— 它与 `Apple_All_No_Resolve.list` 逐行只差这 13 枚 `,no-resolve`，字节差 143 = 13×11 ⇒ 本仓两侧 profile 引用的正是补好的那个变体）**，其余（含 12614 条的 `ChinaMax.list`，12473 条 IP 全带）都干净 —— 所以这类问题不是"普遍存在"，而是**个别文件埋的雷，必须逐个核对**。

**修法优先级**：
1. ⭐ **换用同源等价文件**。blackmatrix7 的命名约定：`XXX.list`（标准）/ **`XXX_No_Resolve.list`（IP 条目全带 no-resolve，首选）** / `XXX_Resolve.list`（全不带）/ `XXX_Domain.list`（纯域名）。Apple 实测 `Apple_All_No_Resolve.list` 与 `Apple_All.list` 在**去掉 `,no-resolve` 后 1616 条逐条相同** ⇒ 换 URL 就完事，覆盖范围零损失，**对 IP 形式的连接判定也完全不受影响**（IP 本就不需要解析）。
   换用前**必须**跑一次归一化比对（去掉 `,no-resolve` 后是否逐条相同），否则可能悄悄换了覆盖范围。
2. 上游没有 No_Resolve 变体 → 自建镜像，把那几条 IP 条目补上 `,no-resolve` 再托管。
3. 下策：整条规则 `disabled: true`（会丢掉该规则集的路由能力）。
❌ **不要**试图在 `rule_set` 规则上写 `no_resolve: true` —— 官方明说只适用 IP 类规则，写了也不生效（写了还可能被当成未知字段）。

顺带记一条实测修正：`ChinaDomain.list` 用 `curl` 直接抓会拿到 0 条（`github.com/.../raw/...` 是 301，**必须加 `-L`**）。用 `-L` 后是 635 条、9 条 IP 全带 no-resolve。审规则集时 curl 漏了 `-L` 会得出"这文件是空的"的错误结论。

**坑 17（f8 的教训，也是全项目最值得记的一条）：治好 DNS 泄露的那一手，会顺手把国内域名的分流一起干掉 —— 它们是同一个机制。**

用户 f7 复测："没有 dns 泄露了，可是国内外的分流好像出了问题，国内网站都不是直连反而走了代理，chinamax 基本都是一些 ip 走了直连，而国内域名基本都走了 final。"

这不是"新引入的 bug"，而是**同一次改动的另一面**：

```
原始配置：国内域名 → 命中 geoip:CN（**没有** no_resolve）
             → 为判定归属**强制本地解析一次**（← 这就是当年的 DNS 泄露）
             → 判出 CN IP → DIRECT ✅（← 这就是当年的国内直连）
f7 改动：geoip:CN 补上 no_resolve: true（官方：不再触发解析）
             → 泄露没了 ✅
             → 但 geoip **不再匹配域名**，那条"解析判归属"的直连路径也一起没了 ❌
             → 本该补位的 ChinaMax 规则**不含域名规则**，于是国内域名整片落 default → Final
```

⚠️ **认知陷阱：`no_resolve` 不是"纯安全加固"，它是"用解析换分流"的开关。** 补它之前必须先确认"国内域名的直连已由域名类规则承担"。

⚠️ **第二个陷阱：规则集的名字骗人。** `ChinaMax.list` 看起来最像"中国域名表"，实际 **99.5% 是 IP**（实测 12,627 行 / 12,614 条：8251 `IP-CIDR` + 4221 `IP-CIDR6` + 1 `IP-ASN` = **12,473 条 IP 类**，域名只有 **51 `DOMAIN-SUFFIX` + 13 `DOMAIN-KEYWORD` = 64 条**，另 65 `USER-AGENT` + 12 `PROCESS-NAME`。99.5% 取的是 IP 类 ∶ 域名类两类的比 —— 按 12,614 条全量算是 98.9%）。该仓库自己的 `ChinaMax/README.md` 明写：

> `ChinaMax.list`，请使用 RULE-SET。
> **`ChinaMax.list`、`ChinaMax_Domain.list` 共同使用。**
> `ChinaMax_All.list` / `ChinaMax_All_No_Resolve.list` **单独使用**。

所以"用了 ChinaMax 却不生效"非常正常 —— **必须下载 + 数域名条目**，别按名字推断（同坑 4）。判据只有一条：**`policy=DIRECT` 的规则集里域名条目数是多少**。≈0 就等于没有直连兜底。

**修法（f8 实测最简单）**：把 URL 换成同目录的 `ChinaMax_All_No_Resolve.list`（3.42 MB）：

| 判据 | 实测结果 |
|---|---|
| 域名覆盖 | 111,332 条（111051 后缀 + 268 精确 + 13 关键词） |
| 旧覆盖是否丢失 | 旧文件那 64 条**全被包含**，差集 = 0 |
| IP 覆盖是否变化 | 12,472 条 IP **去掉 `,no-resolve` 后逐条相同**（diff 为空） |
| 会不会重新触发解析 | 12,473 条 IP 类（12,472 条 CIDR + 1 条 `IP-ASN`）**全部带 `,no-resolve`** ⇒ 不会（别用标准版 `ChinaMax_All.list`，它的 IP 条目**不带**） |
| 效果 | 15/15 国内探针 `DIRECT`；境外探针仍命中各自的 Google/GitHub/ChatGPT 组，无过宽误判 |

⇒ **凡是要"用 IP 规则判归属"的配置，都必须有一份域名类国内规则集兜底。这一步和补 `no_resolve` 是同一次改动，不能分两次做。**

**配套新增脚本 `skill/scripts/egern/audit_routing_coverage.py`（清单 17；合并前路径为 `scripts/…`，现 `skill/scripts/egern/…`）**：吃 profile，先统计每个启用的 `rule_set` 的域名/IP 构成，再拿一批探针域名按 rules 顺序走一遍，输出"命中规则 + 策略"。内置 15 个**不以 `.cn` 结尾**的国内探针（专门暴露"`.cn` 兜底掩盖了国内域名无覆盖"这种假象）+ 7 个境外探针（查是否被误判直连）。**动过 `no_resolve` 或换过规则集，必须复跑。** f7 实测 `7/15 落 Final`（完整复现用户现象），f8 `15/15 DIRECT`。

**坑 18（f10 的教训）：不要把节点域名写进 DNS 分流规则 —— 它既没用，又让配置"看起来需要随订阅维护"。**

用户的原话很准：「还要把节点的域名写在配置里配置对应的 dns 设置，过于复杂了 —— 这意味着我换了订阅，防 DNS 泄露就失效了」。核查后要说得更严厉一点：**那几条规则自 f7 起就是死代码。** 两条结构性事实（官方 dns 文档逐字支持）：

1. **代理 DNS 不走 `forward`。** 官方：「配置了 `proxy_nameservers` 后，代理 DNS 会**跳过 Forward 阶段**，直接走该列表」。节点域名的解析走的正是代理 DNS ⇒ 写在 `forward` 里的节点域名规则**从未被查询过**。（f3 写它们时还没有 `proxy_nameservers`，当时确实需要；f7 补上之后它们就退役了，只是没人回头清理。）
2. **当所有 forward 规则的 `value` 相同时，顺序与域名清单都不影响结果。**（`routing_v3` 起判据扩展为「**除 `reject` 外**的去向单值且等于兜底组」—— `reject` 是终止动作、不产生解析，与兜底可并存） 官方说"第一条命中的决定上游"，但**单值集合里不存在"命中错"这回事** —— 加一条、删一条、写错一条，结果都一样。

⇒ 正确做法不是"想办法动态生成节点域名规则"，而是**删掉它们**：`forward` 只留兜底，防泄露由**兜底组的安全性**（端点全为 IP 字面量 + 满足判据 A 或判据 B，见坑 13）承担，而不是由"记得去列举域名"承担。实测 f10：`forward` 10 条 → 2 条，`dns` 段与节点域名的耦合 4 → 0，四项审计逐项不变。

⚠️ **更要提防它带来的错觉**：这些规则让配置**看起来**很严谨（"我专门照顾了节点域名"），实际既无功能，又把"换订阅"变成了一件需要复查配置的事。**判断一条规则该不该存在，只问两个问题：删掉它结果会变吗？它是否引入了维护耦合？**

**配套新增脚本 `skill/scripts/egern/audit_dns_forward.py`（清单 18）**：打印 `forward` 的 value 集合与结构性冗余条数、统计"订阅耦合度"（从 `proxies[].server` 提取节点域名，查有几条 forward 规则把它们写死）、并支持 `--drill` 用**合成的"未来订阅"域名**做演练（默认 6 个故意不在任何规则集里的域名，验证"未命中的域名到底落到哪个上游"）。退出码 0/1，用于提交前本地检查。
