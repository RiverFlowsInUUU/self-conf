# 故障排查 · 验证自检 · 注意事项 · FAQ

> 由原手册 07、08、10 三章与「注意事项」合并。出问题了按顺序查这一篇。

## 故障排查

两条入口先分流："泄露了"（隐私面）与"国内网站走代理了"（分流面）。它们常常是同一处改动的两面，所以本章 7.5 节把"成对交付"的复盘放在两边共同的位置。

### 7.0 动手前的第一个动作：确认链路

这是代价最大的流程坑：先问清三件事，再谈机制 ——

1. 哪台设备（上面到底装没装这个客户端）；
2. 哪条链路（Wi-Fi / 蜂窝 / 有线）；
3. 谁的 DNS（家庭路由器 / 旁路由 / 运营商 / 系统级配置描述文件）。

不同链路下"明文 `:53` 的下场"完全不同：

| 链路 | 明文 `:53` 的结果 | 测法 |
|:-----|:----------------|:-----|
| 家庭网 + 旁路由（OpenClash / mihomo） | 被透明重定向，返回 Fake IP `198.18.x` | 逐个外部解析器问同一域名，全回 `198.18.x` 即被劫持 |
| 运营商蜂窝 | 被重定向到运营商递归解析器，或不通，掉系统 DNS | 只能"改一行、复测"（见 7.2） |

> **注意**　真实事故：整套"旁路由劫持"证据链做完后，用户一句"leak test 是 iPhone 蜂窝上跑的"，全部作废。测试链路要写进报告开头。

### 7.1 leak test 结果的解读

| 现象 | 含义 |
|:-----|:-----|
| 出现运营商 DNS 或国内运营商出口 IP | 真泄露，往下查 |
| 出现境外公共解析器（`8.8.8.8` 等） | 也可能是泄露（你自己配的不算） |
| 出现节点出口城市的 IP | 不是泄露 —— 那是代理在工作的证据，别去"修" |

### 7.2 定位三个出口（Surge 侧）

抓包最可靠，但时机关键：冷启动期是引导解析泄露的高发窗口，抓包必须从"关客户端 → 开始抓 → 开客户端 → 浏览"整段覆盖。macOS 开热点给 iOS 连、在 mac 上抓 `en0` 覆盖面最好：

```bash
sudo tcpdump -i en0 -n 'udp port 53'
```

不抓包的近似判断，按脚本读数对号：

| 观察 | 出口 | 检查项 |
|:-----|:----:|:-------|
| 明文查询的目标是解析器自己的域名（`dns.google` 等） | ① 引导解析 | `check_surge_dns.py` 第 1、2 项：端点是否主机名、`dns-server` 是否含 `system` |
| 明文查询来自别的设备 | ② 旁路设备 | 第 3 项：`hijack-dns` 缺失或覆盖不全；家里有没有 HomePod / 电视 / 游戏机 |
| 明文查询的域名是你要访问的站点 | ③ 规则触发 | 第 12 项 + `audit_ruleset_content.py`：远程规则集里缺 `no-resolve` 的 IP 条目最容易漏（它不在你 profile 里，本地静态审计看不见） |

修法对照与"什么不该修"（可接受的一次性明文通路）见 [`../skill/reference/surge/leak-localization.md`](../surge/leak-localization.md)。
Egern 侧网络层流程（IP 归属 `ipinfo.io`、`whoami.akamai.net` 问真实递归方、换 bootstrap IP 复测、查配置描述文件、路由器侧把 WAN DNS 改国内公共解析器）见 [`../skill/reference/egern/leak-localization.md`](../egern/leak-localization.md)。

Egern 日志速读：

- `upstream: bootstrap` = 明文回退被触发，去找"哪条路径失败了"；
- `default → Final → Proxy` = 正常分流决策，不是泄露；
- 节点连不上，先注释 `proxy_nameservers`（硬覆盖，见 [操作手册](ops.md)）。

### 7.3 国内网站走代理了：排查序列

1. 跑分流覆盖审计（两侧都叫 `audit_routing_coverage.py`，联网）—— 国内探针是否命中 `DIRECT`；
2. 命中失败先看两条：`direct.txt` 那条规则还在不在；`GEOIP,CN` / `geoip: CN` 有没有被挪到域名规则前面；
3. 引用了新的国内规则集顶替？数它的域名条目，别看名字（ChinaMax 教训见 [成对交付篇](no-resolve-pairing.md)）；
4. 只测 `.cn` 通过不算数 —— 探针必须含 `jd.com` / `zhihu.com` 这类非 `.cn` 国内域名，否则一条后缀兜底就能造假通过。

### 7.4 三内核症状速查（改配置前也先扫一眼）

| 症状 | 高概率根因 | 内核 |
|:-----|:-----------|:----:|
| 导入后整份配置拒绝加载 | `pre-matching` 规则策略写了组（必须字面量 REJECT 族） | Surge |
| 面板某地区组是空的 | 节点名不含该地区关键词；或手写 `[Proxy]` 节点没被 `include-all-proxies=true` 纳入筛选 | Surge |
| 规则指向的应用组"能选但没流量" | 组是 `select` 而成员写成了组名单位，或空组（Egern 旧版 `ChatGPT: []` 的坑） | 双侧 |
| `smart` 组不测速换节点 | 成员是组名而非具体节点 —— 要用 `include-other-group`（Surge）/ `flatten: true`（Egern） | 双侧 |
| 游戏机 NAT 检测失败、Apple 推送异常 | 删了 `always-real-ip` / `real_ip_domains` 清单 | 双侧 |
| 删了一行注释后审计突然报 HIGH | 那是 `# audit-waive:`，有语义 | Surge |
| Quad9 端点"配了没效" | `https://9.9.9.9/dns-query` 静默失效（只有 HTTP/3），改用 `tls://9.9.9.9` | 双侧 |
| 审规则集审出"空文件" | `curl` 没带 `-L`（GitHub raw 301） | — |
| UDP 应用在某节点上不通 | `https` 类型节点不支持 UDP 中继 | Surge |
| 改判据后"坏 fixture 反而通过" | 环境坏了也返回 1 —— 看退出码 2 的语义是不是被吞了 | — |
| 导入后**所有走代理的流量不通** | mihomo：订阅槽位 `proxy-providers.Airport.url` 还是占位值没换自己的 | **mihomo** |
| 广告拦不住，且**没有任何报错** | mihomo：DNS 双条件缺一（`nameserver-policy` 的 `rcode://success` 与 `fake-ip-filter` 要成对），或广告项排在了 `cn` 之后 | **mihomo** |
| 站点测到的 IP 与节点所在地不符 | mihomo：IPv6 未关（`ipv6` 与 `dns.ipv6` **两处**都要 false），双栈站点走真实 IPv6 绕过 TUN | **mihomo** |
| 改了脚本但配置没变 | mihomo：`profiles/*.yaml` 由 `build_profiles.py` 生成，改完脚本必须重生成 | **mihomo** |
| profile 里出现大段重复内容 | mihomo：手工追加写把配置纵向堆了多份（`routing.yaml` 曾堆 7 份 / 3294 行）—— 不要手工改 profile | **mihomo** |
| 远程规则集静默变空、拦截悄悄失效 | mihomo：上游 404（Jinx 曾把 `*-white-guard.*` 改名 `*-direct.*`）—— 用 `check_remote_urls.py` 查 | **mihomo** |
| 头注里的组数/规则数是旧值 | mihomo：手写数字会过期，`check_header_numbers.py` 会判负 | **mihomo** |
| `Smart` 三档没生效 | mihomo：`Smart.proxies` 未接上 `Low Mult./Auto/High Mult.`（子组继承了却没连，比不声明更隐蔽） | **mihomo** |


更长的清单在原两侧坑档：[`../skill/reference/surge/pitfalls.md`](../surge/pitfalls.md) ·
[`../skill/reference/egern/pitfalls.md`](../egern/pitfalls.md)（速查表在各自文件顶部）。

### 7.5 母题：审计绿不等于配置可用

本项目反复出现"脚本全绿、实测仍有问题"。每次的结论都一样：存在审计器看不见的维度，把它补成一个可复跑的脚本，而不是重跑同一个脚本、或只解释为什么脚本是对的。

两个里程碑（详细复盘见 [`no-resolve-pairing.md`](no-resolve-pairing.md)）：

1. f7 事故：给 `geoip: CN` 补 `no_resolve` 后，两个 DNS 审计双双全绿，国内域名却整片落 `default → Proxy`。补上第三个维度：分流覆盖审计（`audit_routing_coverage.py`）。
2. 兜底判据失效：`group_ready` 只要求"端点全 IP + 至少一条被判路由"，没要求那一条是 `DIRECT`，于是 f5 假安心。收紧为 `group_reach`，后又因段 A 删除而双向化（见 [操作手册](ops.md)）。判据的载体选错时，报红的不是配置而是判据本身 —— 这是同一条母题的反向应用。

由此固化的验收观：**"配置里写了什么"与"实际会发生什么"是两件事；结构正确不代表行为正确。**

### 7.6 汇报纪律

给用户的结论必须带上三样：测试链路（设备 / 网络 / DNS）、复现命令、可证伪预期（"换上去之后应看到 X、不应看到 Y"）。缺任何一样，结论按未完成处理。

### 7.7 mihomo（clash）侧排障

> 三内核中 mihomo 的故障模式与另两个差异最大 —— 它多一个「覆写脚本」形态，
> 且 profile 是**生成物**。排障前先确认你在查的是哪种形态。

| 现象 | 怎么定位 | 怎么修 | 用哪个脚本验证 |
|:-----|:---------|:-------|:---------------|
| 所有走代理的流量不通 | 看 `proxy-providers.Airport.url` 是否还是 `sub.example.com/...REPLACE_WITH_YOUR_TOKEN` | 换成自己的订阅地址 | 人工（占位值不进判据） |
| 广告拦不住 | 看 `nameserver-policy` 是否有 `rcode://success`，且**同一广告集**是否也在 `fake-ip-filter` 里 | 两个条件都要满足；广告项排在 `cn`/`private` 之前 | `check_structure.py` 第 ③ 项 |
| 出口 IP 与节点不符 | 看顶层 `ipv6` 与 `dns.ipv6` | 两处都设 false | `check_structure.py` 第 ⑧ 项 + `check_clash_dns.py` 判据 6 |
| 改了脚本配置没跟着变 | 看 `profiles/*.yaml` 的修改时间是否晚于脚本 | 跑 `build_profiles.py` 重生成 | `build_profiles.py --check` |
| profile 内容重复/异常长 | 看顶层键是否重复出现 | 用生成脚本覆盖重写，不要手工追加 | `build_profiles.py` 自检 |
| 规则集突然失效 | 看 `interval` 到期后上游是否 404 | 换可用 URL | `check_remote_urls.py` |
| Smart 不按倍率选节点 | 看 `Smart.proxies` 是不是 `["DIRECT"]` | 接上三档子组 | `build_profiles.py` 自检 |
| 头注数字对不上 | 跑一次就知道 | 改文档数字为实际值 | `check_header_numbers.py` |

⚠️ **mihomo 侧已知的验证缺口**：没有分流覆盖审计脚本（Surge / Egern 均有
`audit_routing_coverage.py`）。即「规则是否真的接住了该接的域名」在 mihomo 侧
**只能人工验证** —— 见 [`boundaries.md`](boundaries.md) 的如实记录。
这与 [`no-resolve-pairing.md`](no-resolve-pairing.md) 的母题一致：
审计绿不等于配置可用。

### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| Surge 侧规则顺序与组写法 | [操作手册](ops.md) |
| 怀疑规则集本身（条数、裸 IP 条目） | [规则集与素材](rulesets.md) |
| 确定要改配置：标准动线与精简指引 | [操作手册 · 日常维护](ops.md) |
| 跑闸门收敛、核对读数落点 | 本篇「验证与自检」章 |
| 名词不认识、常见疑问没解决 | 本篇「FAQ 与术语表」章 |

## 验证与自检

一切改动的收尾都是这里。原则：本地先跑绿，CI 再把同一组检查跑一遍（`.github/workflows/ci.yml`，push / PR 自动触发）。
本章只讲"用什么、怎么读"；读数一律以脚本当次输出为准，本文不抄数 —— 抄了就会漂。规则集条数与来源的权威清单在 [`rulesets.md`](rulesets.md)。

### 8.1 环境要求

| 项 | 要求 |
|:---|:-----|
| Python | 3.8+；Surge 侧脚本仅标准库；Egern 侧需 PyYAML |
| 网络 | 只有内容 / 覆盖 / 刷新类 `audit_*` 需要联网，其余全离线 |
| 磁盘 | 规则集缓存数 MB 级、随上游漂移（实测读数见 [`../surge/checker.md`](../surge/checker.md) 「磁盘」行；`direct.txt` 一份十一万条，条数权威在 [`rulesets.md`](rulesets.md)），在系统临时目录（`surge-ruleset-cache` / `egern-ruleset-cache`）；`--cache-dir` 可换，`--force` 忽略缓存重下 |
| Windows | 输出必须 UTF-8（脚本内部已钉；中文控制台默认 GBK 会把 emoji 崩成退出码 1，与"期望判负"撞码，造成假绿）。Git Bash 的 `pwd` 是 `/c/Users/...`，Windows 版 Python 打不开，`.sh` 里用 `cygpath -w` 转换；拼路径一律用 `/` |

### 8.2 一条命令：全量闸门

```bash
python skill/tests/check_secrets.py     # 占位符 / 凭据扫描（全仓 conf/yaml）
python skill/tests/check_portability.py # 行尾 / BOM / 命名 / 单机残留
python skill/tests/check_min_pair.py    # .min 与完整版去注释对拍
python skill/tests/check_links.py .     # 全仓 markdown 链接与锚点
```

`all.sh` 串起仓内全部本地检查（逐项清单以脚本头注现算为准，本章不写死项数）：Surge 侧回归、Egern 侧回归、`.min` 形态对拍、换设备可移植性、文档读数与实测对拍、工具自检、回归断言数对拍。

退出码语义（全仓统一）：

| 码 | 含义 |
|:--:|:-----|
| 0 | 判据全过 |
| 1 | 有判负（审计发现 / 断言失败） |
| 2 | 前置环境不达标（缺解释器 / 缺 PyYAML / 固定名文件不存在 / 参数组合非法） |
| 3 | SKIP——未能验证（`check_releases` 远端 API 不可达 / 限流 / 上游 5xx / 响应非 JSON）；**不计失败，但汇总表必须明示「未验证 ≠ 绿」** |

> **注意**　铁律：审计器的故障绝不能被计成一次成功的判负。回归里有"期望退出码 1"的坏 fixture，解释器坏了也返回 1 就会假绿 —— 所以环境故障单独用 2。看到 2 先修环境，别读判据。
> 同理，SKIP 必须与 2 分开占用独立码（3）：若复用 2，verify_all 把 2 当 SKIP 剔除时，**环境故障会被吞成 SKIP → exit 0 假绿**（0930 外部审查实锤）。
> **3 的准入与两侧边界**：3 只表示「**没读到远端真值**」。两个方向都算滥用手法 ——① **故障/未知错误不许退 3**（该退 2；退了会被当 SKIP 吞成假绿）；② **读到远端、断言不过也不许退 3**（该退 1，否则等于用「未验证」躲判定，同样是假绿）。一句话：**1 = 读了并且不合规；2 = 环境坏了没跑起来；3 = 跑起来了但没拿到远端真相。**
> **同一脚本内的优先级**：**确定判负(1) 优先于未验证(3)** —— 已有「读到了且不过」的判据就直接退 1，只剩「全没读到」时才降级 3（`check_releases` 的 `bad` 非空即退 1，与 R5 的 `skipped` 共存时以 1 为准）。
> **404 的语义分档（别一刀切）**：若该端点语义下「404 = 明确回答不存在」，则 404 属**读到的答案** → 退 1（例：`check_releases` R5 的 `/releases/latest`，仓库无 Release 时 GitHub 返 404 = 「没有 Latest」）；其余情形的 404（仓名/凭据写错等）归 3。判据只有一条：**这个 404 是否就是端点对你所问问题的确定回答。**
> **2 的准入（与 3 对称的另一半）**：2 的判定依据只能来自**本地前置检查**——脚本在发出任何远端请求**之前**就能自证不达标（缺解释器 / 缺 PyYAML / 固定名文件缺失 / 参数组合自相矛盾 / 不是 git 仓）。**禁止把远端回复的 HTTP 码翻译成 2**：一旦允许，2 就沦为「远端故障的另一个名字」，与 3 的边界被抹平，且「先修环境」的引导会指向一个没坏的环境（仓被删 / 改私有 / token 被撤销，都不是本地配置的问题）。
> 现状核验（2026-09-30，AST 口径）：全仓 2 类退出码 **27 处**（`return 2` 25 + `sys.exit(2)` 3，剔除 1 处业务值），逐处核对**全部来自本地前置检查**，无一处是远端 HTTP 码翻译 —— 本规则与现状零冲突。

两档口径要分清：默认档判"判据过了"，只报不判"未提交 / 落后 / 未推送"三数；`--landed` 才把三数计入判负，只在 push 之后跑。维护者说"先改本地、不提交不推送"的那批，按设计不跑 `--landed`（跑了必红，那是设计不是故障）。`--offline --landed` 组合直接退 2：离线少跑联网项还宣布落地，等于假绿。

### 8.3 单侧回归与常用参数

```bash
python skill/scripts/surge/check_surge_dns.py surge/profiles/lazy.conf
python skill/scripts/surge/check_surge_dns.py surge/profiles/routing.conf
python skill/scripts/egern/check_egern_dns.py egern/profiles/lazy.yaml egern/profiles/routing.yaml
python skill/tests/make_min.py            # 计划模式：四份 .min 应全部「已同步」
```

> **说明**　判据构成以各脚本头注为准。"有一条红了"，先看输出点名的是哪份 profile、哪条判据。

### 8.4 脚本清单（按"我想知道什么"选）

#### Surge 侧（`skill/scripts/surge/`）

| 想知道 | 脚本 | 联网 |
|:-------|:-----|:----:|
| 这份 profile 的 DNS 结构有没有泄露面（逐键判据） | `check_surge_dns.py`（`--strict` medium 也算失败；`--quiet` 只出计数） | 否 |
| 远程规则集里有没有缺 `no-resolve` 的 IP 条目 | `audit_ruleset_content.py`（`--show-domestic --force`） | 是 |
| 拿真实域名走一遍规则链，国内是否 DIRECT、境外是否各归其组 | `audit_routing_coverage.py`（`--show-all`；期望表按配置自动切换） | 是 |
| 规则集刷新参数是否都钉住了 | `audit_ruleset_refresh.py`（`--strict`） | 否 |
| 地区组关键词是否同步、是否互斥 | `audit_region_filters.py`（`-v` 逐组计数） | 否 |

#### Egern 侧（`skill/scripts/egern/`）

| 想知道 | 脚本 | 联网 |
|:-------|:-----|:----:|
| profile 层 DNS 审计（清单前段） | `check_egern_dns.py` | 否 |
| 被引用规则集逐条数 `no_resolve`（规则集层） | `audit_ruleset_noresolve.py`（可 `--url` 单文件、`--offline` 只用缓存） | 是 |
| 分流覆盖（域名 → 命中规则 → 策略） | `audit_routing_coverage.py`（可 `--domain` 指定） | 是 |
| `forward` 与订阅解耦是否仍成立 | `audit_dns_forward.py`（`--drill` 用合成域名多演练一遍） | 否 |
| 地区组 filter 同步 | `audit_region_filters.py`（`lazy` 无此结构自动跳过） | 否 |
| 刷新参数 | `audit_ruleset_refresh.py`（`--strict`） | 否 |
| 端点逐个实测死活 | `probe_dns_endpoints.py`（吃 profile）/ `probe_doh.py` | 是 |
| 规则集类型分布（"数域名条目"判据的工具化） | `profile_ruleset.py` / `weigh_ruleset.py` | 是 |

### 8.5 什么在覆盖面之外

刻意的边界，不是遗漏：

- 抓包类结论（明文 `:53` 次数、leak test 复测）没有脚本，必须人工按本篇「故障排查」章的流程做 —— 审计脚本只覆盖静态可判定的部分；
- 提交前点名 stage，不一把 `git add -A` 扫进垃圾文件；
- 远程规则集明天会不会变，不可静态判定 —— 所以刷新参数与覆盖审计成对存在。

### 8.6 判据自身的纪律

- 判据演进史与逐条出处：[`../skill/reference/surge/checker.md`](../surge/checker.md)（Surge）· 两侧 [`surge/pitfalls.md`](../surge/pitfalls.md) / [`egern/pitfalls.md`](../egern/pitfalls.md)；
- 为让脚本变绿而改判据，可以，但必须留痕 —— 写清为什么退让、退让后还能抓住什么；
- 每条新判据要配能证伪它的坏 fixture（期望判负），否则它可能恒返回 0；
- 判据脚本（`skill/tests/` 四件）改动前按"两要素"自证：哪个反例会漏判、改后能抓住什么。

### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 判据为什么长这样：泄露面全景 | [DNS 基础](dns-basics.md) |
| Surge 侧改完之后的验证对象 | [操作手册](ops.md) |
| 引入或更换规则集前的预检 | [规则集与素材](rulesets.md) |
| 改配置的标准动线与收尾顺序 | [操作手册 · 日常维护](ops.md) |
| 把验证结论带到另一个内核 | [跨内核移植](cross-kernel-diff.md) |
| 验证结论汇报要带的三样 | 本篇「汇报纪律」小节 |

## 注意事项

> 使用前值得先看一遍的几条。订阅地址见 [`README`](../../../README.md)。

### 通用

| 项目 | 说明 |
|:----:|:-----|
| 🧩 **节点与订阅都得自己填** | 本仓库是**脱敏模板**：不含任何真实节点、订阅 token、凭据。懒人版自己填节点；分流版还需填订阅地址。不填则默认出口是断的——**所有走代理的流量都不通** |
| 🧭 **先选内核，再选分工** | 四份配置是「2 内核 × 2 分工」：`lazy`（至简，一个出口）与 `routing`（按应用 + 按地区）。**各选一份用，不要叠加** |
| 📄 **每份都有带注释版与 `.min` 版** | 内容一致、只差注释。**改配置改带注释那份，`.min` 交给 `python skill/tests/make_min.py --family <分工> --apply` 生成**（默认只出计划；判据与阶段 3 的对拍共用一份代码）——Surge 侧阶段 3 的架构检查会逐字比对两份的 DNS 段 |
| 🔄 **规则集刷新统一一周** | 全部远程规则集显式带 `604800`（一周）。Surge 缺省本就是 24 小时、写负值才关自动更新 ⇒ 不写也会刷新；**Egern 未文档化缺省值** ⇒ 不写等于把刷新行为交给未知。两侧统一写死，才是可预期的同一件事 |
| 🔐 **不要把真实节点提交回来** | 公开模板。本地用随意，push 前先过占位符与凭据扫描（`check_secrets.py` 扫全仓 `.conf` / `.yaml`） |
| 🧱 **本仓自包含** | 配置、图标、脚本与全部详解都部署在本仓，**不引用任何前身仓的地址**（它们可能转为私有）。需要外部参照时只指向内核官方文档；唯一的第三方依赖是社区规则集与图标来源，见 [`rulesets.md`](rulesets.md) |
| 🧪 **五项核心检查** | 占位符/凭据（`check_secrets.py`）· 可移植性（`check_portability.py`）· `.min` 对拍（`check_min_pair.py`）· 链接与锚点（`check_links.py .`）· DNS 审计（两侧 `check_*_dns.py`）。push / PR 时由 CI 自动执行；本地随时可手动复跑同组命令。环境要 **Python 3**（Egern 侧脚本还需 **PyYAML**）。所有检查**只看本仓库的文件**，clone 到哪都能跑 |
| ⚠️ **「审计全绿」不等于「配置可用」** | 脚本只覆盖**静态可判定**的部分。拦截效果、误杀、节点可用性必须实测——这是 Egern 侧连续 5 次「脚本全绿、实测仍有问题」换来的结论 |

### Surge 侧

| 项目 | 说明 |
|:----:|:-----|
| ✈️ **分流版的 `Airport` 组** | `policy-path=<订阅 URL>`，token 为占位符。不填则只能靠 `[Proxy]` 的本机节点（地区组按节点名关键词筛选，也能用） |
| 🌏 **地区组可能为空** | 靠 `policy-regex-filter` 匹配节点名里的地区关键词。没筛到节点时 Surge **不会**拒绝加载，但指向它的规则会断流。导入后到面板确认哪几个组是空的 |
| 🔁 **改地区关键词要改两处** | `Other Regions` 的负向断言把另外 5 个地区组的关键词抄了一遍。改完立刻跑 `python skill/scripts/surge/audit_region_filters.py surge/profiles/routing.conf` |
| 🚫 **`pre-matching` 策略不能写组** | 必须是字面量 `REJECT` 族，写成策略组会导致 **Surge 拒绝加载整份配置** |

### Egern 侧

| 项目 | 说明 |
|:----:|:-----|
| 🧩 **`lazy` 两处占位至少填一处** | 它也有隐藏订阅槽位 `Airport`，另带 2 条占位节点（`Node-A` → `Proxy`、`Node-B` → `AI`）；两者都不填则所有走代理的流量不通（**分流版无此问题**：只填订阅即可） |
| ✈️ **分流版填 1 处订阅槽位** | 单一隐藏组 `Airport`（`routing_v3` 起把 A/B 合并为单入口） |
| 📜 **历史版本看 git** | 订阅地址用固定名，升版只改文件内容与头注 `#! version=`，不改名；当前版永远只有顶层那四件。配置变动时，变动前的旧配置归档进 `profiles/config_old/`：归档版本号 = 该目录内此分工最新号的下一位（2026-09-29 起三段制 X.Y.Z：Z=小修、Y=中改、X=大改，每位满 10 进 1，4.0.10 合法；历史两段号不回改），完整版与 `.min` 成对，现役头注同步升为下一位；更早历史看 git（备份 tag：`pre-cleanup-20260927`） |
| 🔒 **`proxy_nameservers` 一设就跳过 `forward`** | 这是硬覆盖。设了它之后，写在 `forward` 里的节点域名规则就是**死代码**（Egern [`坑 18`](../egern/pitfalls.md)） |
| 🧷 **不要用 YAML dump 重写 profile** | 含数千字符的超长单行（如 CA 证书 base64），dump 会丢注释、改格式。按行读入 + 断言「全文恰好命中 1 行」 |

### 换设备 / 双端一致

目标写死在这里：**任何一台机器 clone → 直接改 → 推上去，线上线下逐字一致；本地目录删掉也不亏。**

| 项目 | 说明 |
|:----:|:-----|
| 🧮 **磁盘字节 = 提交字节 = 线上字节** | 根在 [`.gitattributes`](../../../.gitattributes)：`* text=auto eol=lf`。Windows 版 Git 安装器会把 `core.autocrlf=true` 写进**系统级**配置，没有这个文件时同一个 commit 在 Windows 上落盘成 CRLF、在 Linux / macOS 上落盘成 LF ⇒ 换台机器磁盘内容就变了，按 `\n` 写的正则也可能失配。`eol=lf` 的优先级高于 `core.autocrlf`，**不需要任何人改自己机器的 git 配置** |
| 🪟 **bash 双引号内的 `\n` 被 MSYS 静默扭曲** | Windows Git Bash 独有（Linux / macOS 无此参数转换层）：多行 `python -c` / heredoc 经 MSYS 参数传递后 `\n` 变字面 `/n`，锚点匹配 count=0 **静默失败**（2026-09-28 实测）。解法与平台无关：多行代码一律写 `.py` 脚本文件执行，单行无转义才用内联；锚点替换必带 `assert count==1`，写盘后 grep 抽查 |
| 🩹 **今天之前 clone 的旧克隆要手动重检出一次** | `.gitattributes` 只约束 git **写盘的那一刻**，不会回头改写已经在磁盘上的文件。老克隆 `git pull` 之后：磁盘仍是 CRLF，而 `git status` **照样干净**（比对时 git 会先把工作树归一回 LF）⇒ 这是一处隐形差异，只有检查会抓到。两种解法任选：`git rm -r --cached . && git reset --hard`（实测 CRLF 94 → 0、`all.sh` 第 4 项 17 → 18 全绿），或干脆**删掉整个目录重新 clone** —— 反正仓内不留任何单机事实 |
| 🔤 **文件名不构成风险** | 全树实测：路径全部 NFC 归一、无 Windows/macOS 非法字符、无保留设备名（`CON`/`NUL`/`COM1`…）、大小写折叠零冲突（Windows 的 `core.ignorecase=true` 会让只差大小写的两个文件互相覆盖）、最长相对路径 49 字符（Windows 260 上限内留足余量）。**中文文件名能正常上传 GitHub**，但只在人读的文档路径下允许；脚本 / profile / 图标 / 测试这些被程序消费的路径必须纯 ASCII —— 由 [`../skill/tests/check_portability.py`](../../tests/check_portability.py) 常驻守着（**18 条规则，不随文件数增长**） |
| 🤖 **agent 的入口** | [`skill/SKILL.md`](../../SKILL.md) 是 agent 技能包门面：按内核分支的语法知识、检查入口与引用面。判"不对"前先 grep `audit-waive`（明知故犯处都有豁免条目与理由）。改配置遵循 [`ops.md`](ops.md) 的标准动线 |
| 🧑‍💻 **换机器只做四件事** | ① `git clone https://github.com/RiverFlowsInUUU/self-conf.git`（公开仓读不需要登录）；② 配身份：`git config --global user.name` 与 `user.email`；③ 配推送凭据：`gh auth login` 或 Git 凭据管理器。**token 不写进仓内任何文件，也不写进 `git remote` 的 URL**——凭据是单机事实，仓不代管；④ `pip install pyyaml`（Egern 侧脚本依赖，Windows 的 Git Bash 不自带；缺它闸门前置就 rc=2） |
| 🔁 **改完的固定动作** | 五项检查全过 → 点名 stage、提交、push → CI 在线上把同一组检查再跑一遍，红了就修 |
| 🧊 **`git status` 里中文显示成八进制** | 看到 `docs/\345\233\276...` 是 git 的 `core.quotepath` 默认转义，**不是文件名坏了**。想看清：`git config --global core.quotepath false`。macOS 另建议 `git config --global core.precomposeunicode true`（文件系统以 NFD 落盘，否则同一个中文名会被认成两个文件） |
| 🔗 **中文文档的直链要百分号编码** | 仓库内部的 Markdown 链接由 GitHub 自动编码，点就行；中文路径直链需要百分号编码 —— 本仓因此把**全部路径（含文档）留成 ASCII**：四条订阅地址与所有 profile / 脚本 / 文档直址可用，不需要编码，也不受设备影响 |
| 🗑 **本地全删也不亏** | 仓内不存放任何「只存在于某台机器」的事实：判据、检查、升版脚本、详解、规则集清单全在仓里，clone 回来跑一条 `all.sh` 就是完整工作状态。刻意留在本机的只有凭据与订阅地址——这两样本来就不该进公开仓 |

### 移植改动时

两内核**分组已完全对齐（24/24 同名同序）**，分流版规则 24 条逐位对应，懒人版 2026-09-24 起也
逐位同构（各 10 条、同一顺序）；但**同构指位数与语义，不指字节** —— Surge 用内置 `SYSTEM`、
Egern 用本仓快照 `apple_system.list`，且若干内核级约束不可套用（`pre-matching`、`proxy_nameservers`、
内置 `LAN`/`SYSTEM`）。动手前读 [`cross-kernel-diff.md`](cross-kernel-diff.md)。

---

相关：[`rulesets.md`](rulesets.md) · [`cross-kernel-diff.md`](cross-kernel-diff.md)

## FAQ 与术语表

FAQ 从两侧 [`profile-anatomy`](../surge/profile-anatomy.md) · [`profile-anatomy`](../egern/profile-anatomy.md) 的问答节归并而来（答案与源文件同口径，冲突时以 `profile-anatomy` 为准）。
术语表是全手册的公共词汇，定义以本仓文档的实际用法为准。

### 10.1 FAQ

#### 配置与使用

**Q：照抄了，但国内网站慢、打不开。**（Surge）
先跑 `audit_routing_coverage.py`。国内探针没命中 `DIRECT` 就查两条：`direct.txt` 那条规则删没删；`GEOIP,CN` 有没有被挪到域名规则前面。

**Q：`GEOIP,CN` 加了 `no-resolve` 之后，国内 IP 还判得准吗？**（双侧）
判得准，但前提是它前面有域名类规则接住国内域名 —— `no-resolve` 只对"未解析的主机名"跳过，已是 IP 的连接照常判。

**Q：规则集里的 `no-resolve` 是必备的吗？**（Egern）
不是"所有规则集都要"，只有能匹配 IP 的规则才需要：纯域名规则集任何情况都不触发解析（写它是空操作）；含 IP 条目的规则集不带，就会给每个走到它的域名强制本地解析一次。一句话：`no-resolve` 是"IP 规则的开关"，与域名规则无关。

**Q：为什么广告拦截不指向 `AD` 组？**（Surge）
`pre-matching` 要求字面量策略（组可能运行时解析成 `DIRECT`，导致拒加载）。拦截走 `REJECT`，`AD` 组是独立手动开关，两层职责分开。想让 `AD` 接管可以，但要一并去掉 `pre-matching`。

**Q：`smart` 组一直换节点，我想固定。**（Surge）
把该组从 `smart` 换成 `select`，或给成员单独钉一个节点。Egern 侧同理：`fallback` 本来就只按顺序取第一个可用，想固定地区把目标写首位。

**Q：能不能只留 `encrypted-dns-server`，去掉 `dns-server`？**（Surge）
不建议。`dns-server` 承担引导与连通性测试职责；去掉后 Surge 用系统 DNS（运营商下发），正是出口 ①。

**Q：iOS 上怎么用？**（Surge）
Surge iOS 不支持本地文件配置 —— 把 profile 托管到可访问地址（Gist / 自己仓库）再 URL 导入。图标地址已是绝对 URL，不依赖本地路径。Egern 同理走订阅地址。

**Q：分流版还需要手工填节点吗？**（Egern）
不需要 —— 2026-10-06 起分流版 `proxies` 为空、`policy_groups` 也不含任何字面量节点名，只填 `Airport` 订阅滑槽的 URL 即可。此前版本带 2 条占位节点（`Node-A` / `Node-B`），需替换或连同组里的名字一并摘掉。懒人版 `lazy.yaml` 仍带占位节点。

**Q：为什么 `forward` 塌缩成一条兜底、不写节点域名？**（Egern）
配了 `proxy_nameservers` 后代理 DNS 跳过 `forward`（节点域名根本不走这里）；兜底 value 单值时，顺序与域名清单都无意义。写节点域名只会随订阅变化变成死代码。

**Q：兜底指向国内组，会不会让境外网站拿到污染答案？**（Egern）
不会。走代理的域名由节点远程解析，不经过本地 `dns` 段；且"泄露到运营商"（不可撤销）比"答案被污染"致命得多。兜底组唯一判据是直连可达。

**Q：`Foreign-DNS` 组去哪了？**（Egern）
当前模板整组注释保留（更早版本已删段）。要用：取消注释，并把 `forward` 兜底指过去 —— 但那会引入"先有代理才能解析"的启动期明文风险，f10 用国内组兜底正是为了避免它。

**Q：两个形态文件有什么区别？**（双侧）
内容一致、只差注释：完整版读与改，`.min` 导入用。一致由测试逐字节核对，`.min` 永远是生成的。

#### 维护与验收

**Q：我删了 `# audit-waive:` 那行，为什么突然报 HIGH？**（Surge）
`audit-waive` 是有语义的注释，不是说明文字。审计器真的会读它。

**Q：审计全绿就安全了吗？**（双侧）
不。本项目多次出现"脚本全绿、实测仍有问题"，根因都是审计维度缺失。每发现一次，就把那个维度补成可复跑脚本 —— 见本篇「7.5 母题：审计绿不等于配置可用」。

### 10.2 术语表

| 术语 | 定义（本仓用法） |
|:-----|:-----------------|
| 泄露面 / 出口 ①②③ | 明文 `:53` 的三类来源：① 引导解析（bootstrap）② 旁路设备（家庭网其他终端）③ 规则触发解析（IP 类规则为判归属而解析） |
| bootstrap | 客户端为"到达加密 DNS"而做的明文解析，兼作上游全失败的回退出口。安全形态 = 永远不被触发 |
| forward（Egern） | `dns.forward`：按域名把本地解析分派给不同上游组的分流表 |
| `proxy_nameservers`（Egern） | 代理侧解析的硬覆盖：一设即绕过 `forward`、强制直连、成为唯一出口 |
| 线格式（wire format） | RFC 8484 的 DoH 交换格式（`?dns=<base64url>`）。判 DoH 端点死活只认它；JSON API 是 Google 风格的可选扩展 |
| `no-resolve` / `no_resolve` | IP 类规则的"不触发解析"开关。Surge 条目尾后缀写法，Egern 规则级字段；同一开关两种拼写 |
| 成对交付 | 判据 A（IP 规则全带 no-resolve）与判据 B（兜底前有域名体量足够的国内直连集）必须同时成立 |
| `pre-matching` / `extended-matching`（Surge） | 规则在 DNS / SYN 阶段提前求值的能力；前者策略必须字面量 REJECT 族 |
| `hijack-dns` / `hijack_dns` | 把发往 `:53` 的查询收进本地（拦不住走 443 / 853 的 DoH、DoT） |
| Fake IP / `always-real-ip` / `real_ip_domains` | 接管 DNS 后返回假 IP 省一次握手；例外清单里的主机名拿真实 IP（游戏机 / NTP / APNs） |
| 直连可达 | 兜底上游组的判据：端点全 IP 字面量，且不经代理就能问到答案（`group_reach`） |
| 固定名 | 顶层四个永久订阅文件名，升版不改名；历史版本看 git |
| 完整版 / `.min` | 带注释的读改版 / 生成的纯配置导入版 |
| 闸门（gate） | CI（`.github/workflows/ci.yml`）+ 本地五项检查，失败即阻塞 |
| `audit-waive` | profile 里有语义的豁免注释：`# audit-waive: <编号> <理由>` |
| fixture / 判负用例 | 回归里期望被审计器报错的坏配置，用来证明审计器有判别力 |
| `lazy` / `routing` | 懒人版 / 分流版。分工关系，不是版本关系，二选一不叠加 |
| `flatten`（Egern）/ `include-other-group`（Surge） | 把组名展开成组内具体节点的两种写法，跨内核的语义对应物 |
| f 谱系 / v 版本 | `f1…f10` = 排查迭代历史；`routing_vX.Y.Z` = 文件版本。两套前缀刻意区分 |
| `direct.txt` 承重 | 国内域名直连的主承重规则集（Loyalsoldier，十一万级纯域名）；条数与来源见 [`rulesets.md`](rulesets.md) |
| 现算 | 期望值从源头（profile / 脚本源码）实时计算，禁止抄进文档 —— 本仓反漂移的第一纪律 |
| 已合并 | 2026-09-27 起旧手册与专题文档已并入 `skill/reference/`，原 `docs/` 与两侧 `DetailsReadme/` 已删除（git 历史可查） |

### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 名词背后的原理：三类明文出口 | [DNS 基础](dns-basics.md) |
| Surge 侧的操作动线 | [操作手册](ops.md) |
| 规则集的条数、体积、来源 | [规则集与素材](rulesets.md) |
| 改配置的标准动线与收尾顺序 | [操作手册 · 日常维护](ops.md) |
| 审计全绿后还要核什么 | 本篇「验证与自检」章 |
| 把结论带到另一个内核 | [跨内核移植](cross-kernel-diff.md) |
