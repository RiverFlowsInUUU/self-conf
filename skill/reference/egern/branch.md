# 分支 B · Egern 配置防 DNS 泄露

> 本文从 [`SKILL.md`](../../SKILL.md) 拆出 —— **Egern 单侧任务只读本文件，不读分支 A**。
> 共享骨架（泄露面五类 / 四条铁律 / 六条底线 / 标准动线 / 按需读取索引）在 SKILL.md §1–§4。

### 适用

用户给一份 Egern `Profile.yaml`（或含 `dns:` 段的 YAML），要求「防 DNS 泄露 / 别让 DNS 裸奔 / 检查 DNS 配置」，或反馈「实测有 DNS 泄露」。也可用于交付前自检。

### 引用文件（按需读取）

本文件是**主干**：Egern 双轨 DNS 模型、18 项审计清单、模板骨架速览、验收标准。
`reference/egern/` 七篇的「何时读」索引见 SKILL.md §4。**移植到 Surge 侧前必读
[`reference/shared/cross-kernel-diff.md`](../shared/cross-kernel-diff.md)**。

### Egern 的 DNS 模型（不理解这个就会改错地方）

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

### 泄露只可能出在这六个位置

| # | 位置 | 机制与备注 |
|:-:|:-----|:-----------|
| 1 | `upstreams` / `proxy_nameservers` 里用了**域名**形式的加密 DNS | 必被 bootstrap 明文解析一次（用途①） |
| 2 | ⭐ **节点 `server` 是域名，且解析没有显式出口** | 未配 `proxy_nameservers` 时：落 `forward` 境外组 → 直连通不了 → 回退明文 bootstrap / `system`。**CN 环境下最常见、也最容易被漏掉的一条**。f7 起由 `proxy_nameservers` 收口（见清单 2 / 2b） |
| 3 | **回退被触发** | 上游写错、端点失效、或端点路由被绕坏 → 落到明文 bootstrap / system |
| 4 | **IP 类规则没 `no_resolve`** | 为判定规则而触发解析 |
| 5 | **国内解析器被用在境外域名上** | 见下方实测铁律——不是泄露这么轻，是直接解析错 |
| 6 | ⭐ **profile 自身运行所必需的解析**（`proxy_latency_test_url` / `direct_latency_test_url` 的域名、策略组 `icon` 的域名）没有被靠前的 forward 规则接住 | 这些名字**普遍不在 ChinaDomain.list 里**——实测 `cp.cloudflare.com`、`connectivitycheck.platform.hicloud.com`、`jsdelivr.net`、`raw.githubusercontent.com` 全部 **0 命中**（表里唯一两条 cloudflare 还是注释掉的），于是整类落到兜底 = 境外组。而这类解析**每轮节点测速都要做一次**（策略组 `interval` 到点就全量测一遍）⇒ 泄露是**持续型**的、与访问什么网站无关。**继节点域名之后第二个必须显式接住的名字类别**（f3 漏的就是它；f6 起兜底换国内组后天然覆盖，f10 起连单列规则都不再需要——见清单 15 / 18） |

### ⚠️ 实测铁律：国内解析器不能用来解析境外域名（只约束"本地解析"路径）

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

### 审计清单

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

### 加固模板

完整模板（`dns:` 段逐键注释 + `rules` 骨架 + 顶层字段，**权威版本**）：
[`reference/egern/hardening-template.md`](hardening-template.md)。要改模板只改那一份。骨架速览：

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

### 判断 hosts 能不能钉

**先实测解析**，IP 固定才钉；CDN 池不能钉（钉了反而破坏轮换）：

```bash
python -c "
import socket
for h in ['dns.alidns.com','doh.pub','doh.18bit.cn']:
    print(h, sorted({a[4][0] for a in socket.getaddrinfo(h,443)}))"
```

> 🪟 **Windows Git Bash 用户**：此命令含多行，粘入双引号会被 MSYS 参数转换**静默扭曲**（实测 `\n` → `/n`）——改存 .py 文件执行（任何平台通用）。

实测参考：`dns.alidns.com`→223.5.5.5/223.6.6.6（固定 ✅）、`doh.pub`→1.12.12.12/120.53.53.53（固定 ✅）、`doh.18bit.cn`→**11 个 IP 的 CDN 池（不可钉 ❌）**，且它落在 **42.51.x.x（中国联通）** 上的自建服务 —— 能用作国内上游，但别让它承担"所有国内域名"。

### ⚠️ 已知缺陷索引

**18 条，每条都是真实事故复盘**，全文（含完整机制链与修法）见
[`reference/egern/pitfalls.md`](pitfalls.md)——排查实际泄露、或改动判据 / 规则集之前先读它。

改动判据时最高频的三条：**13**（兜底挂在"必须经代理才可达"的组上 → 审计 OK、实测 `upstream: bootstrap`）·
**16**（强制解析藏在别人仓库的 `.list` 里——`Apple_All.list` 实测 13 条裸 IP）·
**17**（治好 DNS 泄露的那一手会顺手砍掉国内域名分流——`no_resolve` 与域名兜底必须成对交付）。

### 改配置的安全姿势

Egern profile 常含**超长单行**（`mitm.ca_p12` 的 base64 CA 证书，可达数千字符）。**不要用 YAML dump 重写整个文件**（会丢注释、改格式）。正确做法：

1. 按行读入（`raw.split('\n')`）
2. 用「内容定位 + 断言唯一性」的方式插行/替换行
3. 额外写回，逐字节对比关键字段（如 `ca_p12` 完全一致）
4. 用 `yaml.safe_load` 验证新旧两份都能解析

⭐ **替换锚点必须换行锚定**：`src.index('dns:\n')` 会命中 `hijack_dns:\n` 里的子串，静默吃掉中间十几行（实测）。用 `src.index('\ndns:\n') + 1`，并且改完**逐字段比对未触碰的部分**（本项目用它抓到了那次误删）。

定位改动点的核心是 `find_one(pred, what)` —— 对每处改动断言「全文恰好命中 1 行」，命中 0 或 >1 行就中止。

#### 删除顶层键（实测：f9 删 `mitm` 段）

用户说「HTTPS 解密暂时不用了 / 把 mitm 删掉」时，**先查依赖再删**：

1. ⭐ **有没有规则依赖解密？** 只有 **`url_regex` / `header` / `user_agent` / `process_name`** 这四类需要 MITM 解密才能匹配；`domain*` / `ip_cidr` / `rule_set` / `geoip` 在 TLS 握手前就能判定。查法：
   `sed -n '<rules 起始行>,$p' profile.yaml | grep -c 'url_regex\|header\|user_agent\|process_name'`
   —— 零命中才可安全删（本项目实测零命中，零能力损失）。
2. **删除范围不能按行数猜**：先定位 `^mitm:$`，再断言紧随的缩进行**恰好**是 `  ca_p12:` + `  ca_passphrase:` 两行，再断言第 4 行不是缩进（否则段内还有别的子键，按行数删会吃错）。`ca_p12` 是**单行 3674 字符**的超长行，只有一行，别当成多行 base64。
3. **断言清单（七项）**：被删字段名与 base64 主体零残留 → 其余行逐条未变 → 顶层键数 = 原数 −1 且**差集恰好是 `{mitm}`** → 其余顶层键的值逐个相同 → `dns` / `rules` / `proxies` / `policy_groups` 解析后逐项相等 → YAML 可解析 → UTF-8 无 BOM / LF。
4. **原位留一行中性注释**（**不含** `mitm` / `ca_p12` 等字样，如「此处原为 HTTPS 解密（个人证书）配置段，2026-09-19 按需删除；需要时从 vN 取回」）—— 便于日后恢复，又不会干扰敏感串扫描。
5. **告知用户**：设备上已装的 CA 证书**不必删**（配置里不再解密，它不会被使用；真要清理去「设置 → 通用 → VPN与设备管理 → 配置描述文件」，但这与 DNS 泄露/分流无关）；**回滚 = 用上一版覆盖**，所以上一版必须保留。
6. 删 `mitm` 后三项审计应**与上一版逐字相同**（DNS 面 / 规则集 / 分流）—— 不同就是误删，回去查第 2 步的断言。

### 加固结束的验收标准（七条同时满足才算完）

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

### 官方文档入口

- DNS 机制：`https://egernapp.com/docs/configuration/dns`（**核心页**，两条路径 + bootstrap + proxy_nameservers + block_ips + hosts 全在此）
- 规则字段：`https://egernapp.com/docs/configuration/rules`（`no_resolve` 适用范围、逻辑规则 `and`/`or`/`not`、rule_set 内部字段）
- 顶层字段全表：`https://egernapp.com/docs/configuration/example`（**注意键名与 DNS 页不一致**）
- 社区参考实现（中国网络环境的最佳实践，DNS 段写法值得对照）：`https://doc.repcz.link/egern/`（原 `repcz.github.io/Egern` 已迁至此，旧地址现 404）
- sitemap（找页面用）：`https://doc.egernapp.com/sitemap.xml`

⚠️ `https://egernapp.com/zh-CN/docs` 和 `/docs/configuration/general` 是 **404**；顶层字段只能从 `configuration/example` 页获取。DNS 页有中文版 `/zh-CN/docs/configuration/dns`。
