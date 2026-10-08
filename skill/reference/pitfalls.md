# 坑与排查 · 事故复盘


## 故障排查与 FAQ

> 由原手册 07、08、10 三章与「注意事项」合并。出问题了按顺序查这一篇。

### 故障排查

两条入口先分流："泄露了"（隐私面）与"国内网站走代理了"（分流面）。它们常常是同一处改动的两面，所以本章 7.5 节把"成对交付"的复盘放在两边共同的位置。

#### 7.0 动手前的第一个动作：确认链路

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

#### 7.1 leak test 结果的解读

| 现象 | 含义 |
|:-----|:-----|
| 出现运营商 DNS 或国内运营商出口 IP | 真泄露，往下查 |
| 出现境外公共解析器（`8.8.8.8` 等） | 也可能是泄露（你自己配的不算） |
| 出现节点出口城市的 IP | 不是泄露 —— 那是代理在工作的证据，别去"修" |

#### 7.2 定位三个出口（Surge 侧）

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

修法对照与"什么不该修"（可接受的一次性明文通路）见 [`ops.md`](./ops.md)。
Egern 侧网络层流程（IP 归属 `ipinfo.io`、`whoami.akamai.net` 问真实递归方、换 bootstrap IP 复测、查配置描述文件、路由器侧把 WAN DNS 改国内公共解析器）见 [`ops.md`](./ops.md)。

Egern 日志速读：

- `upstream: bootstrap` = 明文回退被触发，去找"哪条路径失败了"；
- `default → Final → Proxy` = 正常分流决策，不是泄露；
- 节点连不上，先注释 `proxy_nameservers`（硬覆盖，见 [操作手册](./ops.md)）。

#### 7.3 国内网站走代理了：排查序列

1. 跑分流覆盖审计（两侧都叫 `audit_routing_coverage.py`，联网）—— 国内探针是否命中 `DIRECT`；
2. 命中失败先看两条：`direct.txt` 那条规则还在不在；`GEOIP,CN` / `geoip: CN` 有没有被挪到域名规则前面；
3. 引用了新的国内规则集顶替？数它的域名条目，别看名字（ChinaMax 教训见 [成对交付篇](./dns.md)）；
4. 只测 `.cn` 通过不算数 —— 探针必须含 `jd.com` / `zhihu.com` 这类非 `.cn` 国内域名，否则一条后缀兜底就能造假通过。

#### 7.4 三内核症状速查（改配置前也先扫一眼）

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


更长的清单在原两侧坑档：[`pitfalls.md`](./pitfalls.md) ·
[`pitfalls.md`](./pitfalls.md)（速查表在各自文件顶部）。

#### 7.5 母题：审计绿不等于配置可用

本项目反复出现"脚本全绿、实测仍有问题"。每次的结论都一样：存在审计器看不见的维度，把它补成一个可复跑的脚本，而不是重跑同一个脚本、或只解释为什么脚本是对的。

两个里程碑（详细复盘见 [`dns.md`](./dns.md)）：

1. f7 事故：给 `geoip: CN` 补 `no_resolve` 后，两个 DNS 审计双双全绿，国内域名却整片落 `default → Proxy`。补上第三个维度：分流覆盖审计（`audit_routing_coverage.py`）。
2. 兜底判据失效：`group_ready` 只要求"端点全 IP + 至少一条被判路由"，没要求那一条是 `DIRECT`，于是 f5 假安心。收紧为 `group_reach`，后又因段 A 删除而双向化（见 [操作手册](./ops.md)）。判据的载体选错时，报红的不是配置而是判据本身 —— 这是同一条母题的反向应用。

由此固化的验收观：**"配置里写了什么"与"实际会发生什么"是两件事；结构正确不代表行为正确。**

#### 7.6 汇报纪律

给用户的结论必须带上三样：测试链路（设备 / 网络 / DNS）、复现命令、可证伪预期（"换上去之后应看到 X、不应看到 Y"）。缺任何一样，结论按未完成处理。

#### 7.7 mihomo（clash）侧排障

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

✅ **mihomo 侧此缺口已补**：已有分流覆盖审计脚本（闸门 #9）。（此处曾写「没有」，与事实相反；Surge / Egern 亦有）
`audit_routing_coverage.py`）。即「规则是否真的接住了该接的域名」在 mihomo 侧
**只能人工验证** —— 见 [`pitfalls.md`](./pitfalls.md) 的如实记录。
这与 [`dns.md`](./dns.md) 的母题一致：
审计绿不等于配置可用。

#### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| Surge 侧规则顺序与组写法 | [操作手册](./ops.md) |
| 怀疑规则集本身（条数、裸 IP 条目） | [规则集与素材](./rulesets.md) |
| 确定要改配置：标准动线与精简指引 | [操作手册 · 日常维护](./ops.md) |
| 跑闸门收敛、核对读数落点 | 本篇「验证与自检」章 |
| 名词不认识、常见疑问没解决 | 本篇「FAQ 与术语表」章 |

### 验证与自检

一切改动的收尾都是这里。原则：本地先跑绿，CI 再把同一组检查跑一遍（`.github/workflows/ci.yml`，push / PR 自动触发）。
本章只讲"用什么、怎么读"；读数一律以脚本当次输出为准，本文不抄数 —— 抄了就会漂。规则集条数与来源的权威清单在 [`rulesets.md`](./rulesets.md)。

#### 8.1 环境要求

| 项 | 要求 |
|:---|:-----|
| Python | 3.8+；Surge 侧脚本仅标准库；Egern 侧需 PyYAML |
| 网络 | 只有内容 / 覆盖 / 刷新类 `audit_*` 需要联网，其余全离线 |
| 磁盘 | 规则集缓存数 MB 级、随上游漂移（实测读数见 [`gates.md`](./gates.md) 「磁盘」行；`direct.txt` 一份十一万条，条数权威在 [`rulesets.md`](./rulesets.md)），在系统临时目录（`surge-ruleset-cache` / `egern-ruleset-cache`）；`--cache-dir` 可换，`--force` 忽略缓存重下 |
| Windows | 输出必须 UTF-8（脚本内部已钉；中文控制台默认 GBK 会把 emoji 崩成退出码 1，与"期望判负"撞码，造成假绿）。Git Bash 的 `pwd` 是 `/c/Users/...`，Windows 版 Python 打不开，`.sh` 里用 `cygpath -w` 转换；拼路径一律用 `/` |

#### 8.2 一条命令：全量闸门

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

#### 8.3 单侧回归与常用参数

```bash
python skill/scripts/surge/check_surge_dns.py surge/profiles/lazy.conf
python skill/scripts/surge/check_surge_dns.py surge/profiles/routing.conf
python skill/scripts/egern/check_egern_dns.py egern/profiles/lazy.yaml egern/profiles/routing.yaml
python skill/tests/make_min.py            # 计划模式：四份 .min 应全部「已同步」
```

> **说明**　判据构成以各脚本头注为准。"有一条红了"，先看输出点名的是哪份 profile、哪条判据。

#### 8.4 脚本清单（按"我想知道什么"选）

##### Surge 侧（`skill/scripts/surge/`）

| 想知道 | 脚本 | 联网 |
|:-------|:-----|:----:|
| 这份 profile 的 DNS 结构有没有泄露面（逐键判据） | `check_surge_dns.py`（`--strict` medium 也算失败；`--quiet` 只出计数） | 否 |
| 远程规则集里有没有缺 `no-resolve` 的 IP 条目 | `audit_ruleset_content.py`（`--show-domestic --force`） | 是 |
| 拿真实域名走一遍规则链，国内是否 DIRECT、境外是否各归其组 | `audit_routing_coverage.py`（`--show-all`；期望表按配置自动切换） | 是 |
| 规则集刷新参数是否都钉住了 | `audit_ruleset_refresh.py`（`--strict`） | 否 |
| 地区组关键词是否同步、是否互斥 | `audit_region_filters.py`（`-v` 逐组计数） | 否 |

##### Egern 侧（`skill/scripts/egern/`）

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

#### 8.5 什么在覆盖面之外

刻意的边界，不是遗漏：

- 抓包类结论（明文 `:53` 次数、leak test 复测）没有脚本，必须人工按本篇「故障排查」章的流程做 —— 审计脚本只覆盖静态可判定的部分；
- 提交前点名 stage，不一把 `git add -A` 扫进垃圾文件；
- 远程规则集明天会不会变，不可静态判定 —— 所以刷新参数与覆盖审计成对存在。

#### 8.6 判据自身的纪律

- 判据与命令：[`gates.md`](./gates.md)；
- 为让脚本变绿而改判据，可以，但必须留痕 —— 写清为什么退让、退让后还能抓住什么；
- 每条新判据要配能证伪它的坏 fixture（期望判负），否则它可能恒返回 0；
- 判据脚本（`skill/tests/` 四件）改动前按"两要素"自证：哪个反例会漏判、改后能抓住什么。

#### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 判据为什么长这样：泄露面全景 | [DNS 基础](./dns.md) |
| Surge 侧改完之后的验证对象 | [操作手册](./ops.md) |
| 引入或更换规则集前的预检 | [规则集与素材](./rulesets.md) |
| 改配置的标准动线与收尾顺序 | [操作手册 · 日常维护](./ops.md) |
| 把验证结论带到另一个内核 | [跨内核移植](./rulesets.md) |
| 验证结论汇报要带的三样 | 本篇「汇报纪律」小节 |

### 注意事项

> 使用前值得先看一遍的几条。订阅地址见 [`README`](../../README.md)。

#### 通用

| 项目 | 说明 |
|:----:|:-----|
| 🧩 **节点与订阅都得自己填** | 本仓库是**脱敏模板**：不含任何真实节点、订阅 token、凭据。懒人版自己填节点；分流版还需填订阅地址。不填则默认出口是断的——**所有走代理的流量都不通** |
| 🧭 **先选内核，再选分工** | 四份配置是「2 内核 × 2 分工」：`lazy`（至简，一个出口）与 `routing`（按应用 + 按地区）。**各选一份用，不要叠加** |
| 📄 **每份都有带注释版与 `.min` 版** | 内容一致、只差注释。**改配置改带注释那份，`.min` 交给 `python skill/tests/make_min.py --family <分工> --apply` 生成**（默认只出计划；判据与阶段 3 的对拍共用一份代码）——Surge 侧阶段 3 的架构检查会逐字比对两份的 DNS 段 |
| 🔄 **规则集刷新统一一周** | 全部远程规则集显式带 `604800`（一周）。Surge 缺省本就是 24 小时、写负值才关自动更新 ⇒ 不写也会刷新；**Egern 未文档化缺省值** ⇒ 不写等于把刷新行为交给未知。两侧统一写死，才是可预期的同一件事 |
| 🔐 **不要把真实节点提交回来** | 公开模板。本地用随意，push 前先过占位符与凭据扫描（`check_secrets.py` 扫全仓 `.conf` / `.yaml`） |
| 🧱 **本仓自包含** | 配置、图标、脚本与全部详解都部署在本仓，**不引用任何前身仓的地址**（它们可能转为私有）。需要外部参照时只指向内核官方文档；唯一的第三方依赖是社区规则集与图标来源，见 [`rulesets.md`](./rulesets.md) |
| 🧪 **五项核心检查** | 占位符/凭据（`check_secrets.py`）· 可移植性（`check_portability.py`）· `.min` 对拍（`check_min_pair.py`）· 链接与锚点（`check_links.py .`）· DNS 审计（两侧 `check_*_dns.py`）。push / PR 时由 CI 自动执行；本地随时可手动复跑同组命令。环境要 **Python 3**（Egern 侧脚本还需 **PyYAML**）。所有检查**只看本仓库的文件**，clone 到哪都能跑 |
| ⚠️ **「审计全绿」不等于「配置可用」** | 脚本只覆盖**静态可判定**的部分。拦截效果、误杀、节点可用性必须实测——这是 Egern 侧连续 5 次「脚本全绿、实测仍有问题」换来的结论 |

#### Surge 侧

| 项目 | 说明 |
|:----:|:-----|
| ✈️ **分流版的 `Airport` 组** | `policy-path=<订阅 URL>`，token 为占位符。不填则只能靠 `[Proxy]` 的本机节点（地区组按节点名关键词筛选，也能用） |
| 🌏 **地区组可能为空** | 靠 `policy-regex-filter` 匹配节点名里的地区关键词。没筛到节点时 Surge **不会**拒绝加载，但指向它的规则会断流。导入后到面板确认哪几个组是空的 |
| 🔁 **改地区关键词要改两处** | `Other Regions` 的负向断言把另外 5 个地区组的关键词抄了一遍。改完立刻跑 `python skill/scripts/surge/audit_region_filters.py surge/profiles/routing.conf` |
| 🚫 **`pre-matching` 策略不能写组** | 必须是字面量 `REJECT` 族，写成策略组会导致 **Surge 拒绝加载整份配置** |

#### Egern 侧

| 项目 | 说明 |
|:----:|:-----|
| 🧩 **`lazy` 两处占位至少填一处** | 它也有隐藏订阅槽位 `Airport`，另带 2 条占位节点（`Node-A` → `Proxy`、`Node-B` → `AI`）；两者都不填则所有走代理的流量不通（**分流版无此问题**：只填订阅即可） |
| ✈️ **分流版填 1 处订阅槽位** | 单一隐藏组 `Airport`（`routing_v3` 起把 A/B 合并为单入口） |
| 📜 **历史版本看 git** | 订阅地址用固定名，升版只改内容与头注 `#! version=`，不改名；当前版永远只有顶层那四件。**仓内不保留历史版本** —— 历史在 git 与 Releases |
| 🔒 **`proxy_nameservers` 一设就跳过 `forward`** | 这是硬覆盖。设了它之后，写在 `forward` 里的节点域名规则就是**死代码**（Egern [`坑 18`](./pitfalls.md)） |
| 🧷 **不要用 YAML dump 重写 profile** | 含数千字符的超长单行（如 CA 证书 base64），dump 会丢注释、改格式。按行读入 + 断言「全文恰好命中 1 行」 |

#### 换设备 / 双端一致

目标写死在这里：**任何一台机器 clone → 直接改 → 推上去，线上线下逐字一致；本地目录删掉也不亏。**

| 项目 | 说明 |
|:----:|:-----|
| 🧮 **磁盘字节 = 提交字节 = 线上字节** | 根在 [`.gitattributes`](../../.gitattributes)：`* text=auto eol=lf`。Windows 版 Git 安装器会把 `core.autocrlf=true` 写进**系统级**配置，没有这个文件时同一个 commit 在 Windows 上落盘成 CRLF、在 Linux / macOS 上落盘成 LF ⇒ 换台机器磁盘内容就变了，按 `\n` 写的正则也可能失配。`eol=lf` 的优先级高于 `core.autocrlf`，**不需要任何人改自己机器的 git 配置** |
| 🪟 **bash 双引号内的 `\n` 被 MSYS 静默扭曲** | Windows Git Bash 独有（Linux / macOS 无此参数转换层）：多行 `python -c` / heredoc 经 MSYS 参数传递后 `\n` 变字面 `/n`，锚点匹配 count=0 **静默失败**（2026-09-28 实测）。解法与平台无关：多行代码一律写 `.py` 脚本文件执行，单行无转义才用内联；锚点替换必带 `assert count==1`，写盘后 grep 抽查 |
| 🩹 **今天之前 clone 的旧克隆要手动重检出一次** | `.gitattributes` 只约束 git **写盘的那一刻**，不会回头改写已经在磁盘上的文件。老克隆 `git pull` 之后：磁盘仍是 CRLF，而 `git status` **照样干净**（比对时 git 会先把工作树归一回 LF）⇒ 这是一处隐形差异，只有检查会抓到。两种解法任选：`git rm -r --cached . && git reset --hard`（实测 CRLF 94 → 0、`all.sh` 第 4 项 17 → 18 全绿），或干脆**删掉整个目录重新 clone** —— 反正仓内不留任何单机事实 |
| 🔤 **文件名不构成风险** | 全树实测：路径全部 NFC 归一、无 Windows/macOS 非法字符、无保留设备名（`CON`/`NUL`/`COM1`…）、大小写折叠零冲突（Windows 的 `core.ignorecase=true` 会让只差大小写的两个文件互相覆盖）、最长相对路径 49 字符（Windows 260 上限内留足余量）。**中文文件名能正常上传 GitHub**，但只在人读的文档路径下允许；脚本 / profile / 图标 / 测试这些被程序消费的路径必须纯 ASCII —— 由 [`../skill/tests/check_portability.py`](../tests/check_portability.py) 常驻守着（**18 条规则，不随文件数增长**） |
| 🤖 **agent 的入口** | [`AGENTS.md`](../../AGENTS.md) 是 agent 技能包门面：按内核分支的语法知识、检查入口与引用面。判"不对"前先 grep `audit-waive`（明知故犯处都有豁免条目与理由）。改配置遵循 [`ops.md`](./ops.md) 的标准动线 |
| 🧑‍💻 **换机器只做四件事** | ① `git clone https://github.com/RiverFlowsInUUU/self-conf.git`（公开仓读不需要登录）；② 配身份：`git config --global user.name` 与 `user.email`；③ 配推送凭据：`gh auth login` 或 Git 凭据管理器。**token 不写进仓内任何文件，也不写进 `git remote` 的 URL**——凭据是单机事实，仓不代管；④ `pip install pyyaml`（Egern 侧脚本依赖，Windows 的 Git Bash 不自带；缺它闸门前置就 rc=2） |
| 🔁 **改完的固定动作** | 五项检查全过 → 点名 stage、提交、push → CI 在线上把同一组检查再跑一遍，红了就修 |
| 🧊 **`git status` 里中文显示成八进制** | 看到 `docs/\345\233\276...` 是 git 的 `core.quotepath` 默认转义，**不是文件名坏了**。想看清：`git config --global core.quotepath false`。macOS 另建议 `git config --global core.precomposeunicode true`（文件系统以 NFD 落盘，否则同一个中文名会被认成两个文件） |
| 🔗 **中文文档的直链要百分号编码** | 仓库内部的 Markdown 链接由 GitHub 自动编码，点就行；中文路径直链需要百分号编码 —— 本仓因此把**全部路径（含文档）留成 ASCII**：四条订阅地址与所有 profile / 脚本 / 文档直址可用，不需要编码，也不受设备影响 |
| 🗑 **本地全删也不亏** | 仓内不存放任何「只存在于某台机器」的事实：判据、检查、升版脚本、详解、规则集清单全在仓里，clone 回来跑一条 `all.sh` 就是完整工作状态。刻意留在本机的只有凭据与订阅地址——这两样本来就不该进公开仓 |

#### 移植改动时

两内核**分组已完全对齐（24/24 同名同序）**，分流版规则 24 条逐位对应，懒人版 2026-09-24 起也
逐位同构（各 10 条、同一顺序）；但**同构指位数与语义，不指字节** —— Surge 用内置 `SYSTEM`、
Egern 用本仓快照 `apple_system.list`，且若干内核级约束不可套用（`pre-matching`、`proxy_nameservers`、
内置 `LAN`/`SYSTEM`）。动手前读 [`rulesets.md`](./rulesets.md)。

---

相关：[`rulesets.md`](./rulesets.md) · [`rulesets.md`](./rulesets.md)

### FAQ 与术语表

FAQ 从两侧 [`profile-anatomy`](./profiles/surge.md) · [`profile-anatomy`](./profiles/egern.md) 的问答节归并而来（答案与源文件同口径，冲突时以 `profile-anatomy` 为准）。
术语表是全手册的公共词汇，定义以本仓文档的实际用法为准。

#### 10.1 FAQ

##### 配置与使用

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

##### 维护与验收

**Q：我删了 `# audit-waive:` 那行，为什么突然报 HIGH？**（Surge）
`audit-waive` 是有语义的注释，不是说明文字。审计器真的会读它。

**Q：审计全绿就安全了吗？**（双侧）
不。本项目多次出现"脚本全绿、实测仍有问题"，根因都是审计维度缺失。每发现一次，就把那个维度补成可复跑脚本 —— 见本篇「7.5 母题：审计绿不等于配置可用」。

#### 10.2 术语表

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
| `direct.txt` 承重 | 国内域名直连的主承重规则集（Loyalsoldier，十一万级纯域名）；条数与来源见 [`rulesets.md`](./rulesets.md) |
| 现算 | 期望值从源头（profile / 脚本源码）实时计算，禁止抄进文档 —— 本仓反漂移的第一纪律 |
| 已合并 | 2026-09-27 起旧手册与专题文档已并入 `skill/reference/`，原 `docs/` 与两侧 `DetailsReadme/` 已删除（git 历史可查） |

#### 相关页面

| 下一步 | 去处 |
|:-------|:-----|
| 名词背后的原理：三类明文出口 | [DNS 基础](./dns.md) |
| Surge 侧的操作动线 | [操作手册](./ops.md) |
| 规则集的条数、体积、来源 | [规则集与素材](./rulesets.md) |
| 改配置的标准动线与收尾顺序 | [操作手册 · 日常维护](./ops.md) |
| 审计全绿后还要核什么 | 本篇「验证与自检」章 |
| 把结论带到另一个内核 | [跨内核移植](./rulesets.md) |

---

## Surge · 坑（surge 侧）

> **何时读**：排查实际泄露、或**改动判据 / 规则集之前**。
>
> 每一条都来自实测。摘要在前，详述在后。
> 判据见 [`gates.md`](./gates.md)。

#### 速查表

| # | 坑 | 一句话 |
|:-:|:---|:-------|
| 1 | `no-resolve` 与国内直连集**必须成对** | 只加 `no-resolve` → 国内域名整片走代理 |
| 2 | 只测 `.cn` 会**假通过** | 配置靠 `DOMAIN-SUFFIX,cn` 兜底，不是真接住国内域名 |
| 3 | `pre-matching` 指向策略组 → **加载失败** | 组在运行时可能解析成 `DIRECT` |
| 4 | 审计器把 `GEOIP` 的策略位置取错 → **假 HIGH** | 策略恒在 index 2，不是 index 1 |
| 5 | 审计器 `RULE-SET` 也取错位置 → 12 个假 HIGH | index 1 是规则集标识，不是策略 |
| 6 | 审计器按"条数"判 `hijack-dns` → 判据本身错 | `:53` 地址空间无限，永远列不全 |
| 7 | 国内域名判据只认 `.cn` → 把 `miui.com` 当境外 | 要用显式后缀清单 |
| 8 | 把注释里的网段当真实 IP → 假 HIGH | 只扫有效（非注释）行 |
| 9 | "DIRECT 在 REJECT 之前"这条不变量**本身是错的** | 白名单就是 DIRECT 且必须在 REJECT 前 |
| 10 | 不变量一刀切套到「精简版配置」上 → 要求它改名成完整版 | 更好的修法是**消灭分叉**（已随架构变更消失） |
| 11 | 同一判据两份拷贝 → 两脚本结论相反 | 靠注释提醒同步是不可靠的 |
| 12 | 审计脚本扫注释行 → "没有任何 RULE-SET 规则" | 先 `strip_comment` |
| 13 | 退出码 1 既表示"判负通过"又表示"环境坏了" | 环境故障必须用 2 |
| 14 | 把"性能探针"误当"泄露通道" → 无谓改 `proxy-test-url` | 职责是"测准"，不能用"藏解析"去改它 |
| 15 | 为让脚本变绿而改判据 | 判据可以退让，**但退让必须留痕** |
| 16 | 负向断言把正向关键词抄了一遍 → 漏同步即静默退化 | 消灭不掉就**用脚本守**，并给判别力配一个判负 fixture |

#### 1 · `no-resolve` 与国内直连集必须成对交付

**症状**：给所有 IP 类规则补上 `no-resolve` 之后，国内网站整片走代理。
访问 `taobao.com` 要绕一圈出境再回来，慢得离谱。

**根因**：

```
GEOIP,CN,DIRECT              # 解析 → 拿到 IP → 查 GeoIP → 国内 → 直连
GEOIP,CN,DIRECT,no-resolve   # 未解析的主机名 → 跳过
```

第二条把**两个功能**一起关掉了：

- ✅ 关掉了「触发解析」（想要的）
- ❌ 也关掉了「解析后判 IP 归属」（**不想要的**）

于是国内域名不再被 `GEOIP,CN` 接住，全部落到 `FINAL → Proxy`。

**为什么当时没发现**：两个审计脚本**双双通过**。

- `check_surge_dns.py` 审的是**结构**（顺序、`no-resolve`、策略可解析）；
- `audit_ruleset_content.py` 数的是**规则集条目类型**。

两者都不会问「一个国内域名走完这份规则，最后去哪」。

**修法**：不是把 `no-resolve` 撤回去（那会把漏放回来），而是**补上缺失的另一半**：
在 `GEOIP,CN` 之前放一个**域名体量足够**的国内直连规则集。

> **A** —— 所有 IP 类规则带 `no-resolve`
> **B** —— `FINAL` 之前有一个域名体量足够的国内直连规则集
>
> **只交 A 会漏分流，只交 B 会漏 DNS。必须一起。**

**判据是「数域名条目」，不是看规则集名字。** 反例：

| 规则集 | 名字看起来 | 实测域名条目 | 实测 IP 条目 |
|:-------|:-----------|:------------:|:------------:|
| `direct.txt` | 国内直连 | **十几万** | 0 |
| `ChinaMax.list` | 国内最大集 | **64** | 12472 |

（`direct.txt` 的条数一律现抓：上游每周更新；这里只表达量级。）

`ChinaMax.list` 名字像国内域名集，实际 99.5% 是 IP。单独引用它 =
国内域名全靠 IP 判定 = 加了 `no-resolve` 就坏。

**已固化为测试**：`skill/tests/check_secrets.py` 把这条写成判据。
**口头纪律会忘，测试不会。**

#### 2 · 只测 `.cn` 会假通过

**症状**：审计显示「国内探针 15/15 全部命中 DIRECT」，实际国内网站有一半走代理。

**根因**：探针清单全是 `.cn` 域名。而配置里有一条 `DOMAIN-SUFFIX,cn,DIRECT`
（或某个规则集包含它）—— 于是所有 `.cn` 都被兜住，看着全绿。
**但它靠的是后缀兜底，不是真的接住了国内域名。**

**修法**：探针里**刻意混入非 `.cn`** 的国内域名：

```
www.qq.com    www.taobao.com   www.jd.com      www.bilibili.com
www.163.com   www.zhihu.com    www.miui.com    www.aliyun.com
www.huawei.com  www.iqiyi.com  www.douyin.com  www.meituan.com
```

⚠️ 这些是**真会用到**的域名 —— 它们跑不出来，用户一定报障。

**已固化**：`audit_routing_coverage.py` 的 17 个国内探针里有 14 个是非 `.cn`，
脚本注释里写明了这条理由。

#### 3 · `pre-matching` 指向策略组 → 拒绝加载

**症状**：Surge 报「策略无法解析」/ 直接拒绝加载整份配置。

**根因**：

```
RULE-SET,<ads.list>,AD,pre-matching      # ❌ AD 是策略组
```

`pre-matching` 要求策略在**连接层启动之前**就确定，而策略组在运行时
**可以解析成 `DIRECT`**（被切走 / 成员动态变化），Surge 无法保证"一定拦得住"。

**修法**：

```
RULE-SET,<ads.list>,REJECT,pre-matching,extended-matching    # ✅ 字面量
```

⇒ 这正是「`AD` 组独立于规则链路」的原因，是**刻意的分层设计**。

**职责边界**：拦截动作走字面量 `REJECT`（换取 `pre-matching` 的 DNS 阶段拦截），
`AD` 组作为独立的手动开关存在。改默认行为改规则那一行；想让 `AD` 接管开关，
把策略改成 `AD` 并一并去掉 `pre-matching`。

#### 4 · 审计器把 `GEOIP` 的策略位置取错 → 假 HIGH

**症状**：审计器报「规则引用了未定义的策略 `CN`」，12 条。

**根因**：把规则类型按「有没有匹配值」分类时，`GEOIP` 被归进了"无匹配值"一组，
于是策略取了 index 1 —— 而 `GEOIP,CN,DIRECT` 的 index 1 是 `CN`（匹配值），
策略在 index 2。

**修法**：把 `GEOIP` / `IP-GEOIP` / `ASN` 移进"有匹配值"组。

> ⚠️ **判据写错方向比漏报更危险** —— 它会让使用者去改一条**本来正确的**规则。
> 漏报只是少发现一个问题；假 HIGH 会把人引向错误的修改。

**已固化**：`_surge_common.policy_index` 集中实现，并在注释里写明这条坑。

#### 5 · 审计器 `RULE-SET` 也取错位置 → 12 个假 HIGH

**症状**：审计器报「规则引用了未定义的策略
`https://…/surge-white-guard.list`」。（规则集 2026-10-04 由 Jinx 更名为
`surge-direct.list`，此处保留当时的原文；根因与具体文件名无关。）

**根因**：`RULE-SET,<标识>,<策略>` 的 index 1 是**规则集标识**（URL / 内置集合名），
不是策略。第一版把 index 1 当策略读了。

**修法**：`RULE-SET` 的策略也在 index 2。

**与坑 4 同一处**：两者都是「策略字段位置」这一个判据的两个方向。
**必须一起修，且只能有一份实现。**

#### 6 · 审计器按"条数"判 `hijack-dns` → 判据本身错

**症状**：审计器报 MEDIUM「`hijack-dns` 只列了 6 个地址，没有覆盖所有 `:53`」。

**根因**：**判据本身不可能被满足。** `:53` 的地址空间是无限的
（任何 IPv4 都是潜在的解析器地址），列举永远不可能"列全"。

**修法**：判据改成「**还有多少已知的知名境外解析器没被覆盖**」，且只报 LOW。

**教训**：一条**永远不可能满足**的判据不是"严格"，是"写错了"。
审计器的每一条判据都必须能给出"怎么做才算过"。

#### 7 · 国内域名判据只认 `.cn` → 把 `miui.com` 当境外

**症状**：审计器报 MEDIUM「`proxy-test-url` 的域名是境外域（`connect.rom.miui.com`）」。

**根因**：判据写的是 `endswith('.cn') or endswith('.com.cn')`。
`connect.rom.miui.com` 是小米的域名，是国内的，但**不以 `.cn` 结尾**。

**修法**：用**显式后缀清单**：

```python
DOMESTIC_TEST_SUFFIXES = (
    ".cn",
    ".miui.com", ".xiaomi.com", ".mifans.com",
    ".qq.com", ".tencent.com", ".weixin.qq.com",
    ".baidu.com", ".bdstatic.com",
    ".alibaba.com", ".aliyun.com", ".alicdn.com", ".taobao.com", ".tmall.com",
    ".huawei.com", ".hicloud.com",
    ".jd.com", ".360.cn", ".so.com",
    ".netease.com", ".163.com",
    ".bilibili.com", ".zhihu.com",
)
```

⚠️ **不要用".cn 结尾即国内"或"含 china 即国内"这类近似判据** ——
`.com` / `.net` 的归属无法从后缀判断，只能列。

#### 8 · 把注释里的网段当真实 IP → 假 HIGH

**症状**：架构检查报「出现非占位 IPv4 `10.0.0.0`」。

**根因**：那行是**注释**：

```
```

判据扫了全文，包括注释。

**修法**：只扫**有效配置行**（非注释、非行尾注释）。

> ⚠️ 但注意反例：**其他一些判据必须扫注释**。比如"禁止出现的敏感子串"
> —— 真实凭据残留在注释里同样危险。**判据要按目的选扫描面，不能一刀切。**

#### 9 · "DIRECT 在 REJECT 之前"这条不变量本身是错的

**症状**：架构检查报「DIRECT 排在 REJECT 之前」—— 但那条 DIRECT 就是**白名单**，
它**必须**排在 REJECT 之前。

**根因**：不变量写成了「第一条 DIRECT 不能在第一条 REJECT 之前」，
把白名单当成了违规。

**真实的铁律是两条独立的约束**：

1. **白名单 DIRECT 在本文件的第一条 REJECT 之前**（否则白名单形同虚设）
2. **第一条 REJECT 在第一条"域名类直连规则"之前**（否则国内广告域名被
   `direct.txt` 接走，REJECT 永远轮不到）

⚠️ 约束 2 没法用"策略 == DIRECT"表达 —— `direct.txt` 是 `RULE-SET` 也是 `DIRECT`。

**教训**：写不变量时先问「这条规则**为什么**该在那个位置」，
而不是「它看起来该在哪」。位置的理由不同，判据就不同。

#### 10 · 不变量一刀切套到「精简版配置」上 → 要求它改名成完整版

> 📌 **该坑的"版本分叉"形态已消失**（`v0` 已删除，`lazy` / `routing` 是分工不是版本，
> 见 git 历史）。**但教训仍然成立** ——
> 留着防止下次又冒出"精简版"，或者又有人问"能不能给 routing 也来个极简的"。

**症状**（当时）：架构检查报「`v0.conf` 没有白名单」。

**根因**：`v0` 是**刻意**移除白名单的（定位是"极简懒人版"，代价写在文件末尾）。
把 `v1` 的不变量套到 `v0` 上，等于要求 `v0` 改名成 `v1`。

**修法**（当时）：对 `v0*` 豁免这条，且输出一行**说明性的 OK**：

```
✅ v0.conf: v0 刻意不含白名单（代价见文件末尾说明）
```

> ⚠️ **不要静默跳过** —— 静默跳过会让人以为"测过了"。
> 打印一行说明，读者才知道"这是刻意的"。
>
> 📌 **更好的修法是消灭分叉本身**：把"两个版本"降级成"两种形态"
> （带注释 / 纯配置），不变量就自然对所有人成立，不需要豁免。

#### 11 · 同一判据两份拷贝 → 两脚本结论相反

**症状**（来自 Egern 项目的同型事故）：`check_*.py` 与 `audit_*.py`
对同一份配置给出相反结论。

**根因**：两个脚本各自实现了一份「端点主机名解析 + 是否为 IP 字面量」逻辑，
**靠注释互相提醒同步**。结果判据本体同步了，**喂给判据的 helper 没同步**。

另一个同型症状：端点写 `HTTPS://…`（大写）时，白名单式判据失配，
主机名被误判成 `HTTPS`，读数从 0 high 翻成 9 high。

**修法**：把共用逻辑收编到 `_surge_common.py`，**所有脚本从这里 import**。

> 💡 **靠注释提醒同步两份拷贝是不可靠的。** 要靠结构。

**已固化**：`policy_index` / `_RULE_TYPES_*` / 端点判据 / INI 解析
全部在 `_surge_common.py`，且文件里写明**禁止再写一份**。

#### 12 · 审计脚本扫注释行 → "没有任何 RULE-SET 规则"

**症状**：`audit_ruleset_content.py` 报「这份 profile 没有任何 RULE-SET 规则」，
但 profile 里明明有 7 条。

**根因**：收集 `RULE-SET` 引用时遍历的是原始行，注释里的
`# RULE-SET,…`（被注释掉的规则）也被当成引用，或者反过来被 `#` 开头的行卡住。

**修法**：先 `strip_comment` 再 `split_csv`。

**通用规则**：**任何"取出规则/条目"的代码都必须先剥注释。**
拿原始行做正则匹配的写法，早晚会踩。

#### 13 · 退出码 1 既表示"判负通过"又表示"环境坏了"

**症状**：测试报告「3 passed」，但实际审计器根本没跑起来。

**根因**：构造的反例 **期望退出码 1**。
而解释器/依赖坏掉时，脚本**也返回 1** —— 于是它们全被算成"判负通过"。

**修法**：加「解释器与依赖」前置检查，**环境故障用退出码 2**。

```
0 = 通过
1 = 有发现（审计器）/ 有断言失败（测试）
2 = 环境故障（解释器坏、文件缺失、用法错误）
```

> ⚠️ **审计器的故障绝不能被计成一次成功的判负。**
> 任何"期望失败"的测试都必须能区分"如期失败"和"根本没跑"。

#### 14 · 把"性能探针"误当"泄露通道" → 无谓改动 `proxy-test-url`

**此例值得留档。**

**曾经的判断**：`proxy-test-url = http://www.gstatic.com/generate_204` 是境外端点，
每个策略组每 5 分钟跑一次 → 判定为"持续型泄露面"，改成境内 204。

**为什么错**：

1. 官方 KB 明确：「当使用代理策略时…Surge 总是会使用域名向代理服务器发起请求，
   也就是说 **DNS 解析永远在代理服务器进行**」。本地解析只在命中 DIRECT 时发生。
   ⇒ 端点域名**根本不是泄露通道**。
2. `proxy-test-url` 的职责是**给 `smart` 打分**。换成境内端点测出的是境内 RTT，
   节点在境外时「节点→境内端点」那段路由与真实路径不同 —— **不是更准，是测了另一个东西**。

**正确做法**：**按用途分工**，别一律求境内 ——

| 键 | 用途 | 选址 |
|:---|:-----|:-----|
| `internet-test-url` | 连通性检测 | 国内 204 |
| `proxy-test-url` | `smart` 打分 | 境外（含国际段才反映真实路径） |
| `proxy-test-udp` | UDP 评分 | IP 字面量（如 `1.1.1.1`） |

审计器 `check_6` 对境外端点**只报 LOW 提示，不计入风险等级**。

> 📌 **通用教训**：判一条改动是否成立，先问「**这个字段的职责是什么**」。
> 职责是"测准"的字段，不能用"藏掉解析"去改它 —— 那是原则误套用。

⚠️ 注意区分 `proxy-test-url`（TCP 测速）与 `proxy-test-udp`（UDP 测速）。

#### 15 · 为让脚本变绿而改判据

这是最危险的一类，因为它**看起来是"修 bug"**。

**症状**：审计器对某个配置报 HIGH，结论是"这是刻意的取舍，不是缺陷"。

**三种处理方式**：

| 做法 | 后果 |
|:-----|:-----|
| ❌ 把判据改松 | 判据被**永久**削弱，别的 profile 也失去保护 —— 等于自欺 |
| ❌ 把豁免写死在脚本里 | 没人知道为什么这个不算问题，将来也没法复核 |
| ✅ **把豁免写在被审对象里** | 每一次豁免都在被豁免的东西**旁边**，可 grep、可追溯 |

本项目的做法：`# audit-waive: <检查号> <理由>` 写在 **profile 里**。

```python
def add(level, cid, msg, detail=""):
    if cid in _waivers and _RANK.get(level, 0) > 0:
        findings.append((f"WAIVED:{level}", cid, msg, f"⚠️ 已豁免（profile 内声明）：…"))
        return
    findings.append((level, cid, msg, detail))
```

豁免**不改判定语义的前提是它仍然可见** —— 降级为 `WAIVED:` 并照常逐条打印。

> 📌 **判据可以退让，但退让必须留痕。**

#### 16 · 负向断言里的关键词拷贝（浮层互斥性静默失效）

**背景**：Surge 与 Egern 的策略组都支持用正则筛节点（`policy-regex-filter` / `filter`）。
"其它地区"这类组没法用正向断言表达（"不在以上任何一个地区"），只能写**负向断言**：

```ini
Other Regions = smart, …, policy-regex-filter=(?xi)^(?!.*(?:🇭🇰|香港|…|群组)).+$
```

**问题**：那个 `(?:...)` 里的关键词，是**把另外 5 个地区组的关键词逐字抄了一遍**。
Surge 的 filter 不支持引用变量（filter 是字面正则），所以这份拷贝**在配置层面消灭不掉**。

**漏同步的后果 —— 它不会报任何错**：

1. 某个地区组新增了关键词 K，`Other Regions` 没同步；
2. K 不再被负向断言排除；
3. 含 K 的节点**同时**出现在它自己的地区组和 `Other Regions` 里；
4. 两个组的内容不再互斥 —— 但面板上看不出异常，Surge 也不报错。

这是"**静默退化**"：配置能加载、能跑、看起来一切正常，只是某个分区的候选集悄悄多了一批
不该在那儿的节点。

**为什么不能靠肉眼扫一遍**：关键词里有 emoji（🇭🇰 / 🇯🇵）、中文、`\b` 边界、
`(?:...)` 非捕获组，几十个 token 逐个比对一定会漏，而漏一个不报错。

#### 修法：用脚本守，并给判别力配 fixture

`skill/scripts/surge/audit_region_filters.py` 做三条**绝对判据**（不是模糊匹配）：

| # | 判据 | 挡住的退化 |
|:-:|:-----|:-----------|
| ① | 每个地区组的关键词必须**逐字出现**在负向断言里 | 漏同步 |
| ② | 负向断言里不得有**无出处**的多余关键词（信息行过滤词白名单除外） | 排除过宽，节点从所有组消失 |
| ③ | 地区组之间关键词**不得重叠** | 同一节点落进两个组 |

⚠️ 判据 ② 需要一份"白名单"：负向断言末尾那串
`倍率|剩余|到期|流量|官网|订阅|测试|有效|禁止|邮箱|客服|地址|网站|群组`
是**刻意多加**的（过滤订阅里的"信息行假节点"），不属于任何地区组。
脚本把它当已知例外放行，而不是当成"多余关键词"报错。

#### 关键：给审计器配一个**判负** fixture

只测"好配置通过"是不够的 —— 那证明不了脚本有判别力。
两侧各一份**故意损坏**的 fixture（把 `Hong Kong` 组的 filter 末尾注入一个未同步的
关键词 `港区`，其余逐字同步），**期望审计器报出并判负**：

| 内核 | fixture | 期望 |
|:--|:--|:--|
| Surge | `skill/tests/surge/fixtures/bad_region_filter.conf` | `audit_region_filters.py` 退出码 1 |
| Egern | `skill/tests/egern/fixtures/bad_region_filter.yaml` | `audit_region_filters.py` 退出码 1 |

由 `skill/tests/check_region_filters.py` 守（同时在 `verify_all.py` 与 CI 里跑）。
⚠️ 它不只断言退出码：还断言输出里出现定位标记 —— 因为审计器**崩了也是退出码 1**
（见 `_surge_common.force_utf8_stdout` 记录的事故），只看退出码区分不开
「报出这一条」与「崩在别处」。

> 📌 **通用教训**：当一份数据必须在两处保持一致、而**结构上又消灭不掉拷贝**时
> （语言不支持引用、格式不允许变量），正确做法是**给这份拷贝配一个比对器**，
> 并且**给比对器配一个判负样本** ——
> 否则你无法区分"真的同步了"和"比对器根本没在工作"。
>
> 更优先的方案仍然是**消灭分叉本身**（见坑 10）；只有当消灭不掉时才退到"用脚本守"。

---

## Egern · 坑（egern 侧）

> 本文是 [`AGENTS.md`](../../AGENTS.md) 的引用文件。 **何时读**：排查实际泄露、或改动审计判据 / 规则集之前。

每条都是真实事故复盘。**「审计通过 ≠ 配置可用」是贯穿全部 18 条的母题** ——
连续 5 次出现「脚本全绿、实测仍有问题」，每次的结论都一样：
必须假设「存在审计器看不见的维度」，并把它补成一个可复跑的脚本。

#### 速查表

| # | 坑 | 一句话 | 判据固化在哪 |
|:-:|:---|:-------|:-------------|
| 1 | 远程规则集死链**静默降级** | `mihomo-white-guard.yaml` 404 了半年，没人知道 | `check_remote_urls.py` + CI 每周任务 |
| 2 | 静态 profile 被**纵向堆叠 7 份** | PyYAML 只取最后一份 ⇒ 全绿看不出 | `build_profiles.py` 的两条硬保证 |
| 3 | 门禁引用未定义的 `diff` | 恒一致时不触发，真漂移时 `NameError` 且无诊断 | `check_script_sync.py` 的 `diff` 本体 |
| 4 | DNS 广告拦截**双条件缺一即失效** | 只写 `nameserver-policy` 不写 `fake-ip-filter` = 完全没效果，且不报错 | `check_structure.py` ③（a/b/c/d 四条）|
| 5 | IPv6 未关闭 | 只关一处 → 真实 IPv6 绕 TUN 出网，出口 IP 与节点不符 | `check_structure.py` ④（`is not False`）|
| 6 | 改了脚本忘重生成静态 profile / `.min` | 两边漂移，两边都不报错 | `build_profiles.py --check` + `check_min_pair.py` |
| 7 | Windows 中文环境 print 非 GBK 字符 | `UnicodeEncodeError` → 退出码 1 → 被读成「判负」 | 每脚本 import 时 `reconfigure` + CI 编码门 + E4 |
| 8 | 路径探测基于 `__file__` | 本地全绿，GitHub Actions 上报「缺文件」 | 四个 clash 门禁的 `_default_root`（CWD 优先）|
| 9 | 复制文件丢 mtime | V7「一天一版」误判成当天升了 21 个版本 | `cp -p` + `SKIP_V7`（输出「未验证，不是通过」）|
| 10 | 两版 `AD` 组口径不同被套错 | 分流版 `REJECT`/`DIRECT`，懒人版单成员 `REJECT` | ⚠️ **仅靠注释与文档，无机器判据（无机器判据）** |
| 11 | 跨仓引用 → 本仓不自洽 | 2511 处 URL 仍指向外部仓库（图标 2311 + 规则集 200）| `check_selfcontained.py`（闸门 **#42 自洽性**，在 CI 里跑）|
| 12 | 靠「高熵」判凭据 | 漏掉含 `@` 的密码（实测 `MyRealP@ssw0rd123` 漏过）| `check_secrets.py` 的**占位白名单制** |
| 13 | `198.18.0.1` 被判成真实 IP | 那是 mihomo fake-ip 段（RFC 6815），Surge/Egern 侧不认识 | `DOC_NETS` / `ALLOWED_IPS` 窄白名单（**两处**）|
| 14 | 只测「好配置通过」 | 恒返回 0 的脚本也能让现役配置全绿 | `gates.md` §9 的 15 个注入样例（⚠️ 无自动化回归）|
| 15 | CRLF 判负 | Clash 侧 3 个文件是 CRLF，按 `\n` 写的正则失配 | `.gitattributes`（`* text=auto eol=lf`）|

---

#### 1 · 远程规则集死链：静默降级，不是报错

#### 现象

Jinx 上游把 `*-white-guard.*` 改名为 `*-direct.*`。本仓脚本里那条
`mihomo-white-guard.yaml` 就此 404。**分流版改配置时碰巧发现并修了，
懒人版一直挂着死链没人察觉。**

实测（本次文档编写时现抓，三条一组）：

| URL | 实测 |
|:----|:----:|
| `…/Jinx/main/mihomo-white-guard.yaml` | **404** |
| `…/Jinx/main/mihomo-direct.yaml` | 200 |
| `…/Jinx/main/mihomo-ads.yaml` | 200 |

#### 根因

两层，缺一不可：

1. **上游改名是无声的。** 它不发通知、不 deprecated、不重定向 —— 只是某天起返回 404。
   本仓没有任何机制会定期去问「这个 URL 还活着吗」。
2. **死链在客户端的表现不是报错，是静默降级。**

```
rule-provider 拉取失败
   → 该 provider 变成空集（不是报错，不是加载失败）
   → RULE-SET,Jinx-Ads,AD 永远不命中
   → 广告域名落到 MATCH,Proxy
   → 面板一切正常、配置"能跑"、没人报障
   ⇒ 拦截功能消失，且没有任何人收到通知
```

> ⚠️ 第二层才是这条坑的真正杀伤力：**它不会触发任何报警。**
> 一个"报不出来"的失效，只能靠主动探测发现。

**为什么当时没发现**：本仓**当时没有 CI**。死链的发现路径只有"有人正好改到那一行"。
分流版被改到了（所以修了），懒人版没被改到（所以一直挂着）。

#### 修法

不是"记得去检查"，而是**把它变成一道会定期跑的闸门**：

```python
```

⚠️ **第二条路径是关键设计，缺了它这道门等于半瞎**：

```javascript
// override/my_clash.js 里 MRS 是拼出来的
url: JS + "/geosite/" + c + ".mrs"
//         ↑ 基址常量 + 变量拼接 —— 纯文本扫描抓不到完整 URL
```

`collect_urls`（文本扫）与 `collect_from_scripts`（跑脚本）**两条收集路径必须都在**。

配合 CI 的两处设计（`.github/workflows/ci.yml`）：

```yaml
on:
  schedule:
    # 每周一 03:17 UTC —— 抓「上游规则集悄悄改名/删档」这类本仓无从感知的变化
    - cron: '17 3 * * 1'
…
- name: Remote ruleset reachability (mihomo)
  run: python skill/tests/clash/check_remote_urls.py --timeout 20
  continue-on-error: ${{ github.event_name == 'pull_request' }}
```

| 设计 | 理由 |
|:-----|:-----|
| **每周定时任务** | 上游改名是**时间驱动**的事件，不是 push 驱动。没有 `schedule`，死链可以躺到有人碰那行为止。 |
| **PR 时 `continue-on-error`** | 死链要拦在 `main` 上，但不该因为 CDN 抽风挡住一次无关 PR。这是**有意的非对称**，代价是 PR 上可能绿灯合并 —— 靠每周任务兜底。 |

**排除规则**（避免误判，都是实测踩出来的）：

| 排除项 | 为什么 |
|:-------|:-------|
| `PLACEHOLDER_PAT`（`example.com` / `REPLACE_WITH` / `127.0.0.1`）| 那是给用户替换的订阅槽位，**本来就不该可达** |
| `BASE_URLS`（3 个基址常量）| 拼接用的前缀本身不是可探测的资源 |
| `DOH_PAT`（`/dns-query$`）| 是解析器不是静态资源，HEAD 往往不通 |
| `HC_URLS`（`generate_204`）| 连通性探针 |
| `RESOURCE_SUFFIX` 白名单 | 只有 `.mrs`/`.yaml`/`.list`/`.txt`/`.json` 才算"规则集资源"，其它一概不探测 |

#### 判据固化在哪

- **`skill/tests/clash/check_remote_urls.py`** —— 收集（两条路径）+ 探测（HEAD→GET 退化）+ 排除规则全在这里。
- **`.github/workflows/ci.yml`** 的 `Remote ruleset reachability (mihomo)` step（含每周 cron）。
- 判负样例：`gates.md` §9.2 第 15 条 —— 把某条 URL 改回 `mihomo-white-guard.yaml`（**即当年真实死链**），期望 `NG` + `死链 N 个` + exit 1。
- 文档：`profiles/<kern>.md` §9.5 的警告块。

✅ **已核（2026-10-07 零信任自查）**：`ruleset-sources.md` 里**已无** `mihomo-white-guard.yaml`
（现存提及只在 git 历史里，属沿革）。

⚠️ **但这段警告的机理仍然成立**：改规则集 URL 时，Markdown 文档表**确实没有机器兜底** ——
`check_remote_urls.py` 扫的是配置里的 URL，不扫 `.md`；`check_selfcontained.py` 同样不扫 `.md`。
⇒ 这仍是**手工同步步骤**，改 URL 时请一并核 `ruleset-sources.md` 的表。

---

#### 2 · 静态 profile 被重复粘贴（纵向堆叠 7 份）

#### 现象

`clash/profiles/routing.yaml` 一度有 **3294 行**，里面纵向串了 **7 份完整的 YAML 配置**
—— 无 `---` 分隔、无注释说明，首尾相接。

逐块切片核对的结果：

| 块 | 行 | 组 / 规则 / 集 | 性质 |
|:-:|:--|:--|:--|
| 1–5 | 43–2804 | 23 组 · 24 条 · 22 集（各块略有差异，是演进中间态）| 过渡态 |
| 6–7 | 2805–3294 | **25 组 · 27 条 · 25 集** | 当前版 |

第 7 块与 `routing.min.yaml` **逐字节相同**。

#### 根因

**这是我此前用临时脚本重生成时误用追加模式（`"a"`）写坏的。**

```python
open(fp, "a", encoding="utf-8").write(new_content)   # ← 追加，不是覆盖
```

而**它躲过了所有门禁**，因为：

| 门禁 | 为什么没抓到 |
|:-----|:-------------|
| `check_structure.py` | `yaml.safe_load` 遇到重复顶层键**静默取最后一份** ⇒ 读到的就是"正确"的第 7 块，判据全过 |
| `check_min_pair.py` | 同样拿解析结果（= 第 7 块）与 `.min` 对拍 ⇒ 通过 |
| `check_script_sync.py` | 同上 ⇒ 通过 |
| 肉眼 | 3294 行里 7 份几乎一样的内容，扫过去看不出 |

> 🔴 **PyYAML 的"重复键取最后一份"是这次静默通过的直接原因。**
> 本仓所有 clash 门禁都是 PyYAML 系，它们**共享同一个盲区**。

三个后果（当时记录在 `profiles/<kern>.md` §18.3）：

1. **重复顶层键** —— mihomo 用 `gopkg.in/yaml.v3` 解析，**v3 默认开启唯一键检查**，
   有**拒绝加载整份配置**的风险（未经实测）。这正是「本地全绿 ≠ 线上能跑」的同类：
   门禁侧（PyYAML）不报错，客户端侧（yaml.v3）可能直接起不来。
2. **在文件里 `grep -c` 会得到 7 倍的数字。**
3. **改文件极易改错块** —— 改到第 1 块等于没改，而且改完门禁还是绿的。

#### 修法

不是"下次记得用 `w`"，而是**把手工步骤固化成脚本，并让脚本自带两条硬保证**：

```python

open(fp, "w", encoding="utf-8", newline="\n").write(want)

raw = open(fp, encoding="utf-8").read
keys = [l.split(":")[0] for l in raw.split("\n")
        if l and not l[0].isspace and not l.startswith("#") and ":" in l]
dup = {k for k in keys if keys.count(k) > 1}
if dup:
    print("  NG %s 顶层键重复（疑似重复粘贴）：%s" % (full_rel, sorted(dup)))
    bad += 1
    continue
…
if len(parsed.get("proxy-groups") or []) != ng or len(parsed.get("rules") or []) != nrl:
    print("  NG %s 自检不一致（解析结果与脚本输出不符）" % full_rel)
```

| 保证 | 挡住什么 |
|:-----|:---------|
| ① 覆盖写（`"w"` + `newline="\n"`）| **病根本身** —— 追加模式再也不会被用上 |
| ② 自检：顶层键不得重复 | 畸形文件（不管它是怎么产生的）|
| ② 自检：解析后组数/规则数 == 脚本输出 | 生成物与真源不一致 |

实测（commit `7d7250c`）：**注入重复堆叠 → 自检立刻报错 → 跑一次即修复。**
修复后 `routing.yaml` 从 3294 行回到 **493 行**。

> 📌 **通用教训**：靠"我记得用覆盖模式"是不可靠的 —— 但它和"靠注释提醒同步两份拷贝"
> 是**同一类**错误（见 `surge/pitfalls.md` 坑 11）。
> 正确做法是**让正确的做法成为唯一可执行的路径**（脚本只提供 `w`），
> 并**给结果配一个自检**（就算有人绕过去写坏了，也会被立刻抓出）。

#### 判据固化在哪

- **`skill/scripts/clash/build_profiles.py`** —— 覆盖写 + 自检两段（约 217–236 行）。
- **`skill/tests/verify_all.py`** 的 `('clash 静态 profile 新鲜度', [PY, 'skill/scripts/clash/build_profiles.py', '--check'], {})` —— 闸门 #46（clash 静态 profile 新鲜度）。
- 判负样例：`gates.md` §9.2 第 14 条（往真源追加一行 → `--check` 报「已过期」）。
  ⚠️ `build_profiles.py --check` 的判负样例在 `gates.md` §9.2 里**尚未单列**（表里第 14 条是 `build_rules.py`），待补。

---

#### 3 · 门禁脚本引用未定义的 `diff`：只在判负路径上才执行的代码从未被执行过

#### 现象

`check_script_sync.py` 在**真正要判负的那一次**不是"报出差异"，而是崩在
`NameError: name 'diff' is not defined`，输出只有一段 traceback。

#### 根因

`diff` **在本文件被引用但未定义、也未导入**
（`check_min_pair.py` 里有同名函数，但没有共享模块）：

```python
if out.get("rules") != (st.get("rules") or []):
    errs.extend(diff(out.get("rules") or [], st.get("rules") or [], "rules"))   # ← diff 未定义
    errs.extend(diff(norm_dns(...), norm_dns(...), "dns"))                      # ← 同上
```

行为矩阵：

| 情形 | 实际行为 |
|:-----|:---------|
| 脚本与静态一致（现役状态）| ✅ 两个 `if` 都为假 ⇒ **`diff` 从未被调用** ⇒ `OK`，exit 0 |
| 脚本 `rules` 漂移 | 💥 `NameError`，以退出码 1 结束 |
| 脚本 `dns` 漂移 | 💥 同上 |

**为什么它一直没被发现**：现役配置恒一致 ⇒ **`diff` 从未被执行过**。
这是一个**只在失败分支上才执行、而失败分支从未被触发**的代码路径 ——
静态检查（`python -m py_compile`、import、flake8）**全都看不出来**，
因为 Python 的名字解析发生在**运行时**。

> 🔴 更糟的是那个"碰巧"：退出码**碰巧也是 1**，所以 `verify_all.py` 仍会标红 ——
> **闸门不会假绿，但它给不出任何诊断信息**。没有「第几条规则不同」、
> 没有「哪个 dns 键不同」，只有 traceback。使用者拿到它什么也做不了，
> 只能人工 `diff` 脚本输出与静态 profile 的 `rules` / `dns` 两段。

#### 修法

补上 `diff` 的定义（递归比对，产出可定位的差异描述）：

```python
def diff(a, b, path=""):
    """递归比对两个对象，返回差异描述列表。

    ⚠️ 本函数此前在本文件**被引用但未定义也未导入**：现役配置恒一致时
    从未被调用，一旦真实漂移就会 NameError —— 退出码碰巧是 1 所以不会假绿，
    但**一条诊断都给不出**。故补上定义，并在末尾加自检。
    """
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:   out.append("%s.%s 仅静态版有" % (path, k))
            elif k not in b: out.append("%s.%s 仅脚本有" % (path, k))
            else:            out.extend(diff(a[k], b[k], "%s.%s" % (path, k)))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append("%s 长度不同: 脚本 %d vs 静态 %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff(x, y, "%s[%d]" % (path, i)))
    elif a != b:
        out.append("%s 不同: 脚本 %r vs 静态 %r" % (path, a, b))
    return out
```

差异描述**带下标**（`rules[19]`、`dns.prefer-h3`），这是判负后能定位的前提。

实测（commit `7d7250c`）：**注入漂移后可精确定位到 `rules[19]`**。

📌 **更通用的修法（本项目未采用，记录在此）**：把 `diff` 提进
`skill/scripts/clash/_clash_common.py`，两个脚本共用 —— 否则它是
**同一判据的两份拷贝**，会重演「改了一个、另一个没改」的旧病。
（现状：`check_min_pair.py` 与 `check_script_sync.py` 各有一份 `diff`。）

#### 判据固化在哪

- **`skill/tests/clash/check_script_sync.py`** 的 `diff` 函数本体（含记录本坑的 docstring）。
- 判负样例：`gates.md` §9.2 第 13 条 —— 从 `my_clash_lazy.js` 删掉一条规则
  ⇒ exit 1，且（修好后）输出含 `rules[…] 长度不同` 之类的定位标记。

✅ **已核并修（2026-10-07 零信任自查）**：

1. `gates.md` §6.2 已同步：该处标记为「已修」，
   并附实测证据（注入一条规则 ⇒ 输出 `rules 长度不同: 脚本 12 vs 静态 11`，不再是 `NameError`）。
2. `diff` 现定义于 `check_script_sync.py` 第 94 行 —— 判负时能给出精确诊断。
   ⚠️ 仍**未做到的**：docstring 提到的「末尾自检」确实没有，判负样例仍需人工跑。

---

#### 4 · DNS 广告拦截：双条件缺一即失效，且不报错

#### 现象

配好了 `nameserver-policy` 里的 `rcode://success`，广告**一个也没拦住**。
配置能加载、面板无告警、日志无错误、规则层那条 `RULE-SET,xxx,AD` 也还在 ——
**只是 DNS 层那半完全没工作。**

#### 根因

mihomo 的双层广告拦截是**两个必要条件**，它们是同一件事的两半：

```
广告域名查询
    ↓
① dns.fake-ip-filter: "rule-set:AWAvenue-Ads" / "rule-set:Jinx-Ads"
   → 跳过 fake-ip（否则 withFakeIP 对 A/AAAA 直接返回假 IP，请求永远到不了 ②）
    ↓
② dns.nameserver-policy: "rule-set:xxx": rcode://success
   → 返回空回答（rcode=0, answer=0），DNS 层拦截
    ↓
③ rules: RULE-SET,xxx,AD  →  REJECT
   → 连接层兜底（IP 直连 / DoH / 已被缓存的解析结果）
```

**缺 B 只留 A**：内核 `dns/middleware.go` 里 `withFakeIP` 中间件**先于** `withResolver`
返回 —— 对 A / AAAA 查询直接下发假 IP ⇒ **请求永远到不了 `nameserver-policy`**。
（社区有先例：[Discussion #668](https://github.com/MetaCubeX/mihomo/discussions/668)。）

**缺 A 只留 B**：跳过假 IP 后走真实解析 ⇒ 广告域名拿到真实 IP，DNS 层没有拦截。

⇒ **两条都要。** 还有**第三个条件**（顺序）：`nameserver-policy` 是**按顺序**匹配的，
一旦 `geosite:private,cn` 先命中，国内域名（含广告域）就被送到国内解析器拿真实 IP，
`rcode://success` 永不再看。

> 🔴 **这条坑的杀伤力在于它完全静默。** 没有报错、没有告警、没有日志 ——
> 只有"广告还在"。**凡是"缺一半等于没做"的结构，都必须机器判。**

#### 修法

把四个条件写成判据（不是写成注释）：

| 条件 | 判据 |
|:-----|:-----|
| a) `nameserver-policy` 里有 `rule-set:<广告集>` → `rcode://success` | `ads_np` 空 ⇒ 报错 |
| b) **同一个**广告集在 `fake-ip-filter` 里也列了一遍 | `ads_ff` 空 ⇒ 报错 |
| c) 两处集合**必须相等** | `{…} != ff_sets` ⇒ 报错「广告集两处不一致」|
| d) 广告项排在 `private,cn` **之前** | `min(ads_idx) > min(cn_idx)` ⇒ 报错 |

⚠️ **判据 c 为什么是「相等」而不是「非空」**：只在一处列出 ⇒ (缺 b) 或 (缺 a)
**之一**成立，效果都是半截。**两处是同一件事的两半，缺一半等于没做。**

```python
ads_np = [k for k in npol if str(npol[k]).startswith("rcode://")]
ads_ff = [x for x in ffil if x.startswith("rule-set:")]
if not ads_np: errs.append("DNS 层广告拦截缺失：nameserver-policy 无 rcode://success")
if not ads_ff: errs.append("DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集")
else:
    np_sets = {k.replace("rule-set:", "") for k in ads_np}
    ff_sets = {x.replace("rule-set:", "") for x in ads_ff}
    if np_sets != ff_sets:
        errs.append("广告集两处不一致：policy=%s / fake-ip=%s" % (sorted(np_sets), sorted(ff_sets)))
```

> 💡 判据写成"把两处的集合取出来比相等"，就**顺手挡住了第四种错法**：
> 两处列了**不同的**集（比如 AWAvenue 和 Jinx 写反了）—— 那也是半截。

#### 判据固化在哪

- **`skill/tests/clash/check_structure.py`** 的 ③（含 a/b/c/d 四条），对**四份 profile**
  （`lazy` / `lazy.min` / `routing` / `routing.min`）逐份生效。
- 判负样例：`gates.md` §9.2 第 **5 / 6 / 7 / 9** 条：

| # | 注入 | 期望定位标记 |
|:-:|:-----|:-------------|
| 5 | 删掉所有 `rcode://success` 项 | `DNS 层广告拦截缺失：nameserver-policy 无 rcode://success` |
| 6 | 从 `fake-ip-filter` 删掉所有 `rule-set:` 项 | `DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集` |
| 7 | 把 `rcode://` 几行挪到 `private,cn` 之后 | `广告 policy 排在 cn 之后` |
| 9 | 只加 `rcode://`，`fake-ip-filter` 里列**另一个**集 | `广告集两处不一致` ← **证明判据 c 是「相等」不是「非空」** |

- 文档：`profiles/<kern>.md` §14（含 §14.4 两版本写法差异：`rule-set:private,cn` vs `geosite:private,cn`）。
- FAQ 入口：`profiles/<kern>.md` 「Q：广告拦截加了清单，但没生效」→ 查三件事。

---

#### 5 · IPv6 未关闭 → 出口 IP 与节点不符

#### 现象

明明挂着节点，`whatismyip` 显示的出口 IP **不是节点的**；
或者同一站点时好时坏 —— 取决于该站点有没有 AAAA 记录。

#### 根因

mihomo 的 IPv6 有**两个独立的开关**，管的是两件不同的事：

| 处 | 键 | 作用 |
|:-:|:--|:-----|
| ① | 顶层 `ipv6: false` | 内核**不处理 IPv6 流量本身** |
| ② | `dns.ipv6: false` | `AAAA` 查询由内核直接回**空应答**，不往外发 |

**只关一处会漏，而且两个方向漏的东西不一样**：

- **只关 ①**：DNS 仍在应答 `AAAA` ⇒ 应用拿到 IPv6 地址后尝试建连，
  行为取决于系统栈（可能失败、可能走本机真实 IPv6）。
- **只关 ②**：`AAAA` 不回了，但 **IPv6 通路还在** ⇒
  本机真实 IPv6 可能**绕过 TUN 直接出网** —— **站点测到的出口 IP 与节点不符**。

⇒ 两处都关，双栈站点一律回落 IPv4，封堵面与 Surge / Egern 两侧等效
（Surge 是 `ipv6` + `ipv6-vif`，Egern 只要 `ipv6`）。

> ⚠️ 这条在 `ops.md` 里被单列为**面 ③′** —— mihomo 侧**特有**的一条泄露面，
> 它**不走 `:53`**，所以"我只堵了明文 DNS"的排查思路会漏掉它。

#### 修法

两份 profile 都显式写死两处，并由判据守着：

```python
if c.get("ipv6") is not False:      errs.append("顶层 ipv6 未显式关闭")
if dns.get("ipv6") is not False:    errs.append("dns.ipv6 未显式关闭")
```

⚠️ **必须是 `is not False`，不能写成 `if not c.get("ipv6")`**。
差别很实在：

| 写法 | `ipv6: false` | `ipv6` 键缺失 | `ipv6: "false"`（字符串）| `ipv6: no` |
|:-----|:-------------:|:-------------:|:------------------------:|:----------:|
| `is not False` ✅ | 过 | **判负** | **判负** | **判负** |
| `not c.get("ipv6")` ❌ | 过 | 判负 | **通过（假绿）** | **通过（假绿）** |

> 📌 **判据要判"是不是那个布尔假值"，不要判"是不是 falsy"。**
> YAML 里 `"false"` 与 `no` 都是真值非空的字符串/真值，语义上不是"关闭"。
> 同理，**键缺失也必须判负** —— "没说"不等于"关了"。

#### 判据固化在哪

- **`skill/tests/clash/check_structure.py`** 的 ④。
- 判负样例：`gates.md` §9.2 第 **8** 条（`false` → `true`，顶层与 `dns.ipv6` 各试一次）
  与第 **10** 条（**把 `ipv6` 键整个删掉 ⇒ 仍判负**，证明用的是 `is not False`）。
- 文档：`profiles/<kern>.md` §4.2；`ops.md` §6（面 ③′）。

---

#### 6 · 改了脚本忘重生成静态 profile / `.min` → 两边漂移，都不报错

#### 现象

改了 `override/my_clash.js` 里的规则，跑门禁**全绿**，但用户拿到的静态
`profiles/routing.yaml` **还是旧的**。反之亦然。两种形态的行为不一致 ——
用户遇到「照文档用脚本订阅，效果跟直接导入配置不一样」。

#### 根因

本仓每份 profile 都有**两个交付形态**：

```
静态文件   clash/profiles/routing.yaml    —— 下载即用
覆写脚本   clash/override/my_clash.js     —— 挂到任意订阅上
```

它们是**同一套配置**的两种形态 —— 脚本的输出就应该是静态文件的样子。

而 `.min` 又是**第三/第四份**：`routing.min.yaml` 的定位是
「**同一份配置去掉注释**」，不是"裁剪配置"。

**漂移的根源是一个纯手工步骤**：改脚本 → （人记得）→ 重生成静态 → （人记得）→ 重生成 `.min`。
静态文件不会报错，脚本也不会报错 —— **两边都能正常跑，只能靠对拍发现。**

> 📌 `profiles/<kern>.md` §18.1 把这条写成纪律：**一处改动要写（最多）四处** ——
> 静态 `.yaml` + `.min.yaml` + 覆写 `.js` + （若动规则集内容）`rules/*.list`。

#### 修法

**把手工步骤固化成脚本，并把"是否最新"变成一道闸门**：

```bash
python skill/scripts/clash/build_profiles.py            # 重生成（覆盖写 + 自检）
python skill/scripts/clash/build_profiles.py --check    # CI 用：过期即判负
```

`--check` 的语义是**内容比对**而不是时间戳比对：把脚本输出渲染成目标文本，
与磁盘上的现有内容**逐字节比**，不同即判负。这是它比任何"记得跑"都可靠的原因。

两侧对拍则由另一个脚本守（`check_min_pair.py`）：用 YAML 解析两侧成 Python 对象后
**直接比对象** —— 注释、键顺序、缩进、引号风格都不影响判定，**只看配置本体**。

⚠️ `.min` 与完整版的漂移有一处**刻意的例外**：`dns.listen`。
`check_script_sync.py` 的 `SKIP_DNS_KEYS = {"listen"}` —— 脚本整体替换 `dns` 时
**不写**这个键（否则可能与客户端自身 DNS 端口冲突）。
懒人版有 `listen: 0.0.0.0:7874`，分流版不设。

⚠️ 另有一处**刻意的差异**必须打印但不判负：`Smart` 三档。
模板能用 `filter` 在**运行时**按倍率分档，脚本在订阅加载时执行一次、看不到 provider 节点名
⇒ 脚本侧只能是单组 fallback。这是**内核机制决定的，不是漂移**，故进 `EXPECTED_DIFF`：

```
~ 已知差异 Smart: 模板三档 fallback vs 脚本单组 fallback（机制差异，非漂移）
```

> 🔴 **别把 `EXPECTED_DIFF` / `TEMPLATE_ONLY_GROUPS` 当成"可以往里加东西的豁免清单"。**
> 它们的准入条件是「**机制不可能对齐**」。任何"写起来麻烦"的差异都应该改脚本，不是加白名单。

#### 判据固化在哪

| 漂移方向 | 守门脚本 | 在闸门里 |
|:---------|:---------|:-------------|
| 脚本 ↔ 静态 | `skill/tests/clash/check_script_sync.py` | ✅ 闸门 #38 |
| 完整版 ↔ `.min` | `skill/tests/check_min_pair.py` | ✅ 闸门 #37 |
| 静态是否过期（脚本有更新未重生成）| `skill/scripts/clash/build_profiles.py --check` | ✅ 闸门之一 |
| `rules/*.yaml` 是否过期（真源 `.list` 有更新）| `skill/scripts/clash/build_rules.py --check` | ✅ 闸门 #39 |

- 判负样例：`gates.md` §9.2 第 11 / 12 / 14 条。

⚠️ **判别力现状**：这四道门的判负样例都是**人工跑出来的**，不是常驻 CI 的保证（见坑 14）。

---

#### 7 · Windows 中文环境 print 非 GBK 字符 → 退出码 1 被读成「判负」

#### 现象

脚本在 Windows 中文控制台上崩在 `UnicodeEncodeError`，**以退出码 1 结束**。
汇总表把它标成 ❌「有判负」—— 看起来像是配置有问题。

**本次文档编写时就实测撞上了一次**（在同一个仓库、同一台机器上）：

```
$ python -c "print(open('...').read[i:i+2500])"
UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 774
```

（⚠️ 那个字符是 `build_gates` docstring 里的 ⚠️。**读本文档时它就在仓库里，一直都在。**）

#### 根因

两层，缺一不可：

1. **中文 Windows 控制台默认 cp936（GBK）**。`print` 一个 emoji / `⇒` / `↔` / `⚠️`
   就会 `UnicodeEncodeError`。
2. **退出码 1 有两个含义**：「有判负」**和**「崩了」。
   本项目的退出码约定是 `0 = 通过 · 1 = 有判负 · 2 = 环境故障` ——
   **而崩溃不会给出 2，它给出 1。**

⇒ 于是「判据根本没跑」被读成「判据跑了并判负」。
**这是假绿的反面：假红。** 它比假绿隐蔽得多 —— 假绿让人安心，假红让人去改一个本来正确的东西。

> 🔴 最危险的一种形态：一个**判负样例**期望的退出码"恰恰也是 1"。
> 「如期判负」与「崩在别处」**只看退出码分不开**。

#### 修法

三道防线，**互补、不可互相替代**：

**① 每个脚本在 import 时把 stdout/stderr 钉成 UTF-8**（运行时真相）：

```python
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
```

四个 clash 门禁 + `_clash_common.utf8_stdout` 都是这一招。
⚠️ `errors="replace"` 是刻意的：宁可输出 `?` 也不要崩。

**② CI 的「Encoding gate (cp936)」**（在 Linux 上等价复现 Windows 的管道路径）：

```yaml
- name: Encoding gate (cp936)
  run: python skill/tests/verify_all.py
  env:
    PYTHONIOENCODING: cp936
```

⚠️ **前提是 `run_one` 对 `PYTHONIOENCODING` 用 `setdefault`，不是硬赋值**：

```python
env.setdefault('PYTHONIOENCODING', 'utf-8')     # ✅ 父进程传下来的 cp936 会被原样继承
```

（这个错误写法在 2026-10-02 被实测推翻过 —— 它把一道门变成永久空转。）

**③ `check_portability.py` 的 E4**（静态判据，覆盖 CI 不跑的审计脚本）：
「脚本 print 非 GBK 字符者必有输出编码保护」。

| | 覆盖 | 假阳性 |
|:--|:-----|:-------|
| 编码门（运行时）| 只覆盖 `build_gates` 跑到的脚本，且只覆盖**执行到的分支** | **零** |
| E4（静态）| 全覆盖（含 CI 不跑的审计脚本）| 有漏报也有假阳性 |

⚠️ E4 自己的两个已知边界（都是**宁严勿宽**的刻意保守）：

- 不要退回 `"reconfigure" not in src` 这类**子串判断** —— 光在注释里写一句
  `# 需要 reconfigure 保护` 就会被误判成「已有保护」。**假保护比漏报更坏。**
- `def setup: sys.stdout.reconfigure(...)` **定义了却从未调用** ⇒ 判负（正确）；
  但保护被**包了两层以上**（`boot` → `force_utf8_stdout` → `reconfigure`）
  会被**误判为无保护**（真实运行不崩，E4 却判负）。修法：把保护写在模块级，
  或让**中间层**在模块级被调用。

#### 判据固化在哪

- **每个 clash 脚本**顶部的 `reconfigure` 循环 + `skill/scripts/clash/_clash_common.py` 的 `utf8_stdout`。
- **`.github/workflows/ci.yml`** 的 `Encoding gate (cp936)` step。
- **`skill/tests/check_portability.py`** 的 E4（含它自己的自检样例：只护 `stderr`、只写注释、
  只定义不调用 —— 三个都期望判负）。
- 判负样例纪律：`gates.md` §9.1 —— **判负断言是两条，不是一条**：退出码 == 1 **且**
  输出里出现那个注入的定位标记。后者正是为了把「判负」与「崩了」分开。

---

#### 8 · 路径探测基于 `__file__` → 本地全绿，CI 上报「缺文件」

#### 现象

Linux CI 上 clash 的两个门禁（`check_structure.py` / `check_script_sync.py`）
报「缺文件」，**本地全过**。

```
  NG 缺文件: override/my_clash.js 或 profiles/routing.yaml
```

#### 根因

`_default_root` 的 v1 **基于 `__file__` 向上推算**仓库根：

```python
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, "..", "..", ".."))
```

而整合仓有两种布局：

```
整合仓 self-conf：配置在 <root>/clash/ 下     ← __file__ 要上推 3 层再进 clash/
单仓 Clash：      配置就在 <root> 下          ← __file__ 要上推 3 层
```

`__file__` 在**符号链接 / 不同调用方式**下会算错（实测 GitHub Actions 上的调用方式就踩了）。
算错之后，脚本在一个不含 `profiles/` 与 `override/` 的目录里找文件 ⇒ 「缺文件」。

> 🔴 **这类 bug 的本质是"环境相关的东西只有一种环境被测过"。**
> 本地永远是对的，因为它一直在同一个环境里跑。**CI 的价值就在于此** ——
> 它是唯一会去跑"另一种调用方式"的地方。

#### 修法

**CWD 优先 + 逐级向上探测，以"特征目录"为准**（不是以"上推层数"为准）：

```python
def _default_root:
    """定位 clash 配置目录（含 profiles/ 与 override/）。

    探测顺序：当前工作目录 → 脚本自身位置。
    优先用 CWD 是因为 CI 从仓库根调用，而 __file__ 在符号链接 /
    不同调用方式下可能算错（实测 GitHub Actions 上 __file__ 探测失败）。
    """
    cands = []
    cwd = os.getcwd
    cands.append(cwd)
    cands.append(os.path.join(cwd, "clash"))
    here = os.path.dirname(os.path.abspath(__file__))
    up = here
    for _ in range(5):
        cands.append(up)
        cands.append(os.path.join(up, "clash"))
        up = os.path.dirname(up)
    for c in cands:
        if os.path.isdir(os.path.join(c, "profiles")) and os.path.isdir(os.path.join(c, "override")):
            return os.path.abspath(c)
    return os.path.abspath(cwd)
```

| 设计点 | 理由 |
|:-------|:-----|
| **CWD 优先** | CI 从仓库根调用，CWD 是**唯一可靠**的锚 |
| **以特征目录为准**（同时含 `profiles/` + `override/`）| 两种布局都支持，**不依赖"上推几层"这个魔法数** |
| 每层都试 `<dir>` 与 `<dir>/clash` | 覆盖"配置在子目录"与"配置在根"两种布局 |
| 兜底返回 CWD | 找不到就退回 CWD，**至少路径是确定的**（比返回一个不存在的目录好诊断）|

⚠️ 使用纪律：**从仓库根调用，不要从脚本所在目录调用。**

#### 判据固化在哪

- **四个 clash 门禁各自的 `_default_root`**：`check_structure.py` · `check_min_pair.py` ·
  `check_script_sync.py` · `check_remote_urls.py`（同一段逻辑，四处拷贝 —— 见 `gates.md` §16.4）。
- **CI**：`Gates (Surge + Egern + mihomo)` step 从仓库根跑 `verify_all.py` ⇒ 每 push 都在验证这条。
- 文档：`gates.md` §1 环境要求块；`profiles/<kern>.md`；`profiles/<kern>.md` 的移植清单
  （「路径探测优先以仓库根 CWD 为锚点，再向上寻找内核特征目录；不要只按 `__file__` 固定上推层数」）。
- commit：`d2b3caa fix: clash 门禁路径探测改为 CWD 优先（CI 暴露）`。

⚠️ **已知缺口**：这四份 `_default_root` 是**同一判据的四份拷贝**，靠"复制粘贴"保持一致
（正是 `surge/pitfalls.md` 坑 11 的形态）。修法是提进 `_clash_common.py`，**目前未做**。

---

#### 9 · 复制文件丢 mtime → V7「一天一版」误判成当天升了 21 个版本

#### 现象

V7「一天一版」判据报：某一天升了 **21 个版本**。

```
V7 routing 一天一版  ❌ 2026-10-07 有 21 个版本（v1.0→v1.1→…→v2.0）
```

而实际上那是**几十个历史版本的归档文件**，跨了好几个月。

#### 根因

**版本诞生日期的来源有两个**（由 `release_publish.build_days` 现算）：

| 对象 | 日期来源 |
|:-----|:---------|
| **现役版** | 版本号首现日 `number_birth`（git 提交历史）|
| **归档版**（已删除的归档目录）| 快照 blob 诞生日 `version_date`（git 历史 / **文件 mtime**）|

本仓的 git 历史从整合完成起算 —— 于是归档文件的
git 日期查不到，判据退化到用 **mtime**。

而 `cp`（不带 `-p`）**不保留 mtime**：

```
复制前的归档文件：  v1.0 (09-24) · v1.1 (09-26) · v1.2 (09-27) … v2.0 (10-04)
cp 之后的归档文件： v1.0 (10-07) · v1.1 (10-07) · v1.2 (10-07) … v2.0 (10-07)
                                    ↑ 全部退化成复制当天
⇒ V7 看到「10-07 这一天有 21 个版本」
```

> 🔴 **这是"判据正确、输入失真"的经典形态。**
> 判据没有写错，是**喂给它的日期是假的**。`ops.md` §6.8 把它写成通用姿势：
> **断言报红时，先问「它依赖的输入是否齐全」（历史深度 / 网络 / 凭据 / 前置文件），
> 再问「是不是真的不过」。**

⚠️ **反向也成立**：不得因为"可能是前置问题"就把红当噪声放过。
判据与 CI 结论冲突时（CI 绿、本地红），**先查两边跑法差异**（历史深度、工作目录、环境变量）。

#### 修法

两件事一起做（commit `3006cf8`）：

1. **`cp -p` 重拷 已删除的归档目录** —— 保留 mtime，让日期分组至少还能用文件系统时间重建。
   （这是**减缓**，不是根治：本仓的 git 历史本就从整合完成起算。）
2. **`SKIP_V7=1` 开关** —— 承认「本就不继承 git 历史」这个局限，但
   **输出必须写明"未验证"，不能冒充通过**：

```python
if _os.environ.get("SKIP_V7") == "1":
    for fam in ("routing", "lazy"):
        out.append(("V7 %s 一天一版" % fam, True,
                    "已跳过（SKIP_V7=1）：日期分组不成立 "
                    "⇒ 未验证，不是通过"))
    return out
```

> 🔴 **豁免 ≠ 通过。** 汇总表上它是 ✅ 标记（退出码 0），但**文字明确声明了不验证**。
> **引用这道门的结果时，必须连同这句声明一起引用。**

配套：CI 里仍 `fetch-depth: 0` 保留完整历史 —— 不是给 V7 用，是给**其它归档判据**（V3–V6）留底。

📌 **豁免的三条纪律**（`gates.md` §10.3）：

1. **豁免必须点名**，不冒充通过 —— 输出里要能读出「未验证」。
2. **豁免要写理由**，理由要能被证伪（"日期分组不成立"是可验证的事实，不是"太麻烦"）。
3. **豁免项要么进 `build_gates` 带 SKIP 标记、要么显式注释掉**。

#### 判据固化在哪

- **`skill/tests/check_min_pair.py`**（跨内核版）的 `_cadence` 与 `CADENCE_FROM`（2026-10-04）。
- **`skill/tests/verify_all.py`** 的 `_skip_v7 = {'SKIP_V7': '1'}` 传给 `('min-pair 一致', …)`。
- 文档：`gates.md` §10.1；`gates.md`（「一天一版」只从 2026-10-04 起算，历史不回改不追溯）。
- commit：`3006cf8`。

⚠️ 注意区分：**clash 侧的 `skill/tests/check_min_pair.py` 不含 V7**（它没有
`SKIP_V7` 分支，只做完整版 ↔ `.min` 的对象对拍）。V7 挂在**跨内核那道**上。

---

#### 10 · 两版 `AD` 组口径不同被套错

#### 现象

两版都叫 `AD`、都指向两条广告清单、规则行也长得一样 —— 但**成员表不一样**：

```yaml
- name: AD
  type: select
  proxies:
    - REJECT
    - DIRECT          # ← 可以手动放行

- name: AD
  type: select
  proxies:
    - REJECT          # ← 单成员，没有放行的口子
```

把分流版的写法套到懒人版上（或反过来），**配置照样能加载、门禁照样全绿** ——
只是懒人版从此多了一个"广告放行"开关。

#### 根因

这是**刻意的差异，不是漂移**。出处写在代码注释里：

```javascript
// clash/override/my_clash.js（分流版）
{
  name: "AD",
  type: "select",
  // 对齐 SC 的 AD：REJECT / DIRECT 二选一（不设 PASS ——
  // PASS 语义为「绕过代理直连」，与二选一的拦截口径不符，易误操作）
  proxies: ["REJECT", "DIRECT"],
}

// clash/override/my_clash_lazy.js（懒人版）
{
  name: "AD",
  type: "select",
  // 单成员 REJECT —— 与姊妹仓懒人版同口径（该仓 893b406 有意收敛）。
  // 分流版脚本才是 REJECT / DIRECT 二选一。
  proxies: ["REJECT"],
}
```

两个产品的定位不同：

| 版本 | 组数 | `AD` 口径 | 理由 |
|:-----|:----:|:----------|:-----|
| 分流版 `routing` | 25 | `REJECT` / `DIRECT` | 面向会调配置的人，需要手动放行的口子 |
| 懒人版 `lazy` | 3（`Proxy` / `AI` / `AD`）| 单成员 `REJECT` | 「不留放行的口子」—— 目标用户不需要、也不该有这个开关 |

⚠️ 顺带记一条：`AD` **不设 `PASS`**。`PASS` 的语义是「绕过代理直连」，
与"拦截与否"的二选一口径不符，容易误操作 —— 这是**语义层面**的选择，不是随手写的。

**为什么机器抓不到**：

| 门禁 | 能抓到吗 | 为什么 |
|:-----|:--------:|:-------|
| `check_structure.py` ①（悬空引用）| ❌ | `REJECT` / `DIRECT` 都在 `BUILTIN` 里，两个成员表都合法 |
| `check_script_sync.py`（脚本↔静态）| ✅（但只对**同一版内部**）| 它会逐位比子节点 ⇒ 脚本与静态之间不会漂。**但两版之间的口径差它不管** |
| 任何其它门 | ❌ | 没有一条判据表达「懒人版的 AD 必须只有一个成员」 |

#### 修法

现状：靠**注释 + 文档**（`my_clash_lazy.js:90-91` 的注释、`profiles/<kern>.md` §8.2 的表格）。
这是**本仓目前唯一一条"有意差异"没有机器判据的**。

📌 若要补判据，正确的写法是**按版本分表断言**（不是"AD 必须有几个成员"这种一刀切）：

```python
AD_CALIBER = {
    "routing": {"REJECT", "DIRECT"},   # 可放行
    "lazy":    {"REJECT"},             # 单成员，不留口子
}
```

⚠️ 且必须**按版本名取口径**，不能写成"AD 必须有 ≥1 个成员" —— 那等于没判。
⚠️ 更不要一刀切写成"AD 必须含 DIRECT" —— 那会要求懒人版改名成分流版
（同 `surge/pitfalls.md` 坑 10 的形态：不变量一刀切套到另一种形态上）。

> 💡 **更优先的方案是消灭分叉本身**：若将来两版合并成"带注释 / 纯配置"两种形态
> （而不是两种**配置**），这条判据就自然对所有形态成立，不需要版本分表。

#### 判据固化在哪

- ⚠️ **无机器判据（无机器判据）。** 目前只有：
  - `clash/override/my_clash_lazy.js:90-91` 的注释（含姊妹仓 commit `893b406` 出处）；
  - `skill/reference/profiles/clash.md` §8.2 的「为什么这么写」表格与 §14.3；
  - `check_script_sync.py` **间接**守住「同一版内脚本↔静态不漂移」（`EXPECTED_DIFF` 不含 `AD`，
    所以 `AD` 的成员表是**逐位比对**的 —— 脚本改了静态没改会立刻红）。

---

#### 11 · 跨仓引用 → 整合仓不自洽（2511 处）

#### 现象

整合"完成"了：文件都搬进了新仓，门禁全绿，配置能加载。
但**里面的 URL 还指着别的仓库** —— 共 **2511 处**：

| 类型 | 数量 | 表面症状 | 实际后果 |
|:-----|-----:|:---------|:---------|
| 图标引用 | **2311** | 外部仓库仍在线时一切正常 | 外部仓库改名 / 删除后，大量面板图标同时失效 |
| 规则集引用 | **200** | profile 仍能加载 | 远程集拉取失败后可能静默变空，分流与广告拦截退化 |

#### 根因

**"复制文件"不等于"整合仓库"。** 文件搬过来了，文件里的 URL 没有跟着改。

这类缺陷的危险在于它的**三重静默**：

1. **语法检查通过** —— YAML 合法、JSON 合法。
2. **客户端导入成功** —— URL 是对的，只是指向别人家。
3. **本地缓存继续生效** —— 图标已经下过一次了，短期内看不出问题。

⇒ **只有把外部仓库看作"随时会消失"，才能验证自洽性是否真的成立。**

> 📌 它的失效模式和坑 1（死链）**是同一种**：静默降级。
> 区别只在于触发者 —— 坑 1 是上游规则集改名，本坑是被引用的外部仓库改名。
> **两者都只能靠主动扫描发现。**

（实测：本仓 `icons/` 40 个图标 PNG + 1 个 SVG中 34 个同名文件整合时**内容字节完全一致**，零冲突 ——
所以这件事做起来不痛苦，痛苦的是**没人去做**。现役 `routing.yaml` 里的图标 URL
已全部指向 `raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/`。）

#### 修法

```python
FORBIDDEN_REPOS = ("Self-Configuration", "RiverFlowsInUUU/Clash")
COMMENT_PREFIX = ("#", "//", ";")          # 纯注释行跳过
SKIP_DIRS = {".git", "__pycache__", "icons"}
EXTS = (".yaml", ".conf", ".js", ".list", ".txt", ".json", ".yml")
```

| 设计点 | 理由 |
|:-------|:-----|
| **跳过纯注释行** | 注释里提及来源是**记录**，不是运行时引用 —— 不跳会把说明文字误判成依赖 |
| **`SKIP_DIRS` 含 `icons` / 已删除的归档目录** | `icons/` 是**资源本身**（不是引用）；已删除的归档目录 是历史归档，改它没有意义 |
| **上游第三方放行** | MetaCubeX / blackmatrix7 / Jinx / TG-Twilight 是**登记过的第三方**，本就不属于"本仓应自持"的部分 |
| 按**仓库名**识别 | 简单、可审计。⚠️ 代价：**新增外部仓库 / 镜像域名 / 新文件后缀时必须同步扩判据** |

⚠️ 边界要写清：**它不是通用的"零外链证明器"**，是按仓库名识别已知外部仓库的专项检查；
纯注释、Markdown（`.md`）、以及 `SKIP_DIRS` 里的目录**不在当前扫描面**。

#### 判据固化在哪

- **`skill/tests/check_selfcontained.py`**（手动跑：`python skill/tests/check_selfcontained.py .`）。
- 文档：`gates.md` §4（含 2511 处的分解表）；`profiles/<kern>.md` 的移植清单（「自洽」一行）。
- 判负样例：`gates.md` §9.2 —— 任意**非注释行**出现
  `https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/...` ⇒ `外部依赖 N 处` + exit 1。

⚠️ **已知缺口**：它**不进 16（现 17）道**，理由是"整合期的一次性检查，通过后不再变化"。
这个理由**可被证伪** —— 一旦有人新增了一个指向外部仓库的图标或规则集，它就不会再是"已通过"状态。
**建议**：至少把它挂到每周 cron 那个 job 上（与 `check_remote_urls.py` 同批），成本几乎为零。

---

#### 12 · 靠「高熵」判定凭据 → 漏掉含 `@` 的密码

#### 现象

配置里写了一个真实密码 `MyRealP@ssw0rd123`，secrets 扫描**没报**。

#### 根因

v1 的判据是「高熵串」：

```python
HIGH_ENTROPY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z0-9+/=_\-]{16,}$")
```

`MyRealP@ssw0rd123` 的问题：

```
字符类 [A-Za-z0-9+/=_\-] 里面没有 @
                              ↑
⇒ 整个正则失配 ⇒ 判据说"这不是凭据"
```

**真实密码恰恰经常带 `@` / `!` / 空格。** 用"看起来像随机串"去判"是不是凭据"，
等于**把最常见的一类真实密码排除在扫描之外**。

> 🔴 **方向性错误**：高熵判据的隐含假设是"凭据长得很随机"。
> 这个假设对 **API key** 成立，对**用户自己设的密码**完全不成立 ——
> 而后者才是配置里最常见的东西（`password:` / `auth:` 字段）。

⚠️ **附带发现（实测）**：这个 `HIGH_ENTROPY` 常量在
`skill/tests/clash/check_secrets.py` 里**只出现 1 次 —— 就是它的定义处**，
**从未被使用**。即它是一个**死常量**：既没起到作用，又让"我们有高熵判定"
这个错觉留在代码里。**死判据比没有判据更坏** —— 它会让人以为这一项被守住了。

#### 修法

**换成占位白名单制**：不在白名单里的可疑物即报警。

```python
for m in TOKEN_RE.finditer(txt):
    v = m.group(1)
    if is_placeholder(v):
        continue
    if v.lower in ("true", "false", "null", "none", "direct", "reject"):
        continue
    # 代码里的常量/变量名（如 ALL_KEY = HAS_PROVIDERS）不含数字 ——
    # 真实凭据几乎必含数字，以此区分。
    if not any(ch.isdigit for ch in v):
        continue
    hits.append((rel, "非占位凭据: %s" % m.group(0)[:60]))
```

| 设计点 | 理由 |
|:-------|:-----|
| **默认判负**（不在白名单即报警）| 本仓是**公开模板仓**，配置里根本不该出现非占位凭据。**默认放行的判据在这里是不适用的。** |
| `PLACEHOLDER_VALUES`（`REPLACE_WITH_YOUR_PASSWORD` / `YOUR_TOKEN` / `changeme` / `example` …）| 明确列出哪些算"假值" |
| 放过 `true/false/null/direct/reject` | 布尔与内置策略名不是凭据 |
| **"必须含数字"启发式** | 区分代码常量（`ALL_KEY = HAS_PROVIDERS`）与真实凭据（几乎必含数字）|

> 📌 **判据的方向要跟着"被审对象的性质"走。**
> 通用 secrets 扫描器必须靠熵（它面对的是"海量未知文本"）；
> **模板仓**面对的是"我自己的配置，我知道它应该长什么样" ⇒ **白名单制是更强的判据**。

#### 判据固化在哪

- **`skill/tests/clash/check_secrets.py`** 的 `TOKEN_RE` + `is_placeholder` + `PLACEHOLDER_VALUES`
  （含记录 `MyRealP@ssw0rd123` 实测的注释）。
- 判负样例：`gates.md` §9.2 —— 任意 `.yaml` 里写 `password: MyRealP…` ⇒ `非占位凭据:`。
- 文档：`gates.md` §5.1「两道 secrets 扫描不要混为一个」。

✅ **已核并修（2026-10-07 零信任自查）**：

1. `HIGH_ENTROPY` 已加注释说明其定位（此前定义了但从未使用，属死代码，
   容易让人误以为「高熵密码已被扫描」）。
2. **`skill/tests/clash/check_secrets.py` 现已进 `verify_all`（闸门 #23（clash secrets 扫描））**。
   此前它有 289 处误报，根因有三，均已修：
   · `ROOT` 只往上三级 ⇒ 落在 `skill/` 文档区 ⇒ 改成往上四级（仓库根）并排除 `skill/`；
   · 已在 `ALLOWED_IPS` 里的 IP（如 `1.1.1.1`）被 `HOST_RE` 再当主机报一次；
   · 注释里的 IP / 域名也被扫（`# 刻意不放 10.0.0.0/8` 这类）⇒ IP/HOST 判据改为只扫非注释行
     （凭据字段与私钥头仍扫全文 —— 注释里写真密码同样该报警）。
   修后误报归零，注错验证有效（注入 `token=AbcDef123456789` ⇒ 报警；还原 ⇒ 干净）。

---

#### 13 · `198.18.0.1`（mihomo fake-ip 段）被 Surge 侧扫描判成真实 IP

#### 现象

整合后，跨内核的 secrets 扫描报：

```
NG clash/profiles/routing.yaml —— 出现非占位 IPv4 `198.18.0.1`
```

而 `198.18.0.1` **不是节点地址**。

#### 根因

它是 **mihomo 的 fake-ip 段**：

```yaml
dns:
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16        # RFC 6815 保留段（Benchmarking）
```

| 内核 | 认不认识 `198.18.x` |
|:-----|:-------------------|
| mihomo | ✅ 这是**自己的** fake-ip 段，见到它说明查询被内核接住了 |
| Surge / Egern | ❌ 它们的词汇表里没有这个概念 ⇒ 按"非常见 IPv4"处理 |

⇒ **这是"各内核的常识不同"**。`198.18.0.1` 在 mihomo 侧是**合法保留段**，
在 Surge/Egern 侧的判据里是"一个不在白名单里的 IPv4"。

> ⚠️ 反过来看，**这个误报是"好事"** —— 判据在按它自己的标准正确地工作。
> 问题不在判据，在于**整合两个内核时，一方的合法值在另一方眼里是异常值**。
> 这类冲突**只能靠整合者识别出来**，任何单侧判据都发现不了。

📌 同一段地址还有**第二个语义**（`ops.md` §1）：
做泄露测试时检测到 `198.18.x.x` **不是泄露** —— 它恰恰说明查询
**被 mihomo 接住了**、只是没做真实解析。**别把它当成新发现的泄露面去"修"。**

#### 修法

**加窄白名单，不是关闭 IPv4 扫描**（`profiles/<kern>.md` 明确写了这条原则）：

```python
DOC_NETS = ("192.0.2.", "198.51.100.", "203.0.113.", "198.18.")
```

```python
ALLOWED_IPS = {…, "198.18.0.1", …}
…
if ip.startswith("198.18."):
    continue
```

| 原则 | 说明 |
|:-----|:-----|
| **窄** | 加的是 `198.18.` 这个**前缀**（RFC 6815 的保留段），不是"放行所有私有地址" |
| **有规范依据** | 引 RFC 6815 / RFC 5737，不写"不知道为什么但这几个要放行" |
| **不关扫描** | 关掉 IPv4 扫描会**同时丢掉真正的节点地址检测** —— 那是本扫描的主要职责 |

#### 判据固化在哪

- **`skill/tests/check_secrets.py`（跨内核）的 `DOC_NETS`** —— 含 `198.18.`。
- **`skill/tests/clash/check_secrets.py`（Clash 版）的 `ALLOWED_IPS` + `ip.startswith("198.18.")`**。
- 文档：`profiles/<kern>.md` §5.2 与 FAQ「Q：`198.18.0.1` 为什么不是真实 IP？」；
  `ops.md` §1（不是泄露）；`profiles/<kern>.md` 移植清单（"另外要检查新内核的保留地址常识"）。

⚠️ **同一判据两份拷贝 —— 改必须两处一起改。**
两个 `check_secrets.py`（跨内核版 / Clash 版）**各自维护了一份 IP 白名单**，
且写法不同（一个是 `DOC_NETS` 元组 + `startswith`，一个是 `ALLOWED_IPS` 集合 + 单独 `startswith`）。
这正是 `surge/pitfalls.md` 坑 11 的形态。**只改一个，两个脚本会给出相反结论 —— 比没有脚本更糟。**

---

#### 14 · 只测「好配置通过」证明不了判别力 —— 必须注入坏样例

#### 现象

门禁全绿，于是认为"配置没问题"。

#### 根因

**一个恒返回 0 的脚本也能让现役配置全绿。**

```
现役配置 → check_structure.py → exit 0  ✅
        ↑
        这条路径对它自己是不是在工作，一个字的信息都没提供。
```

本仓全部闸门**全部**是"跑现役配置、期望 0"。**没有任何一道常驻 CI 的闸门会验证
「判据自己还判不判负」。** ⇒ 一旦出现「门禁逻辑改坏、判据不再判负、现役配置仍全绿」，
**本仓没有闸门会发现。**

（坑 3 就是这件事的实证：`diff` 未定义这件事，只有**注入漂移**才暴露得出来。
静态检查、import、跑绿样例 —— 全都看不出来。）

#### 修法

本仓对判别力的要求是**两侧合计**：既放行现役配置、又拦住故意损坏的样例。
且判负侧的断言是**两条，不是一条**：

1. **退出码 == 1**；
2. **输出里出现那个故意注入的定位标记**（如组名 / 键名）。

> ⚠️ **第 2 条不是多余**：审计器**崩了**（emoji 触发 `UnicodeEncodeError`，见坑 7）
> 同样以退出码 1 结束 —— 而判负样例期望的**恰恰也是 1**。
> 两者的区别**只能在输出里看**。所以判负样例必须「能点名到这一条」。

统一前置（**在仓库外做**，避免污染工作副本）：

```bash
SB=/tmp/clash-gate-probe          # Windows 用 C:/Users/<你>/AppData/Local/Temp/...
mkdir -p "$SB/profiles" "$SB/override"
cp clash/profiles/*.yaml "$SB/profiles/"
cp clash/override/*.js   "$SB/override/"
python skill/tests/clash/check_structure.py   "$SB"   # 期望 0
python skill/tests/check_min_pair.py    "$SB"   # 期望 0
python skill/tests/clash/check_script_sync.py "$SB"   # 期望 0
```

> ⚠️ **基线必须先绿。** 基线红时注入坏样例，判负可能来自原有缺陷 ⇒ 判别力结论无效。

`gates.md` §9.2 登记的注入样例（**15 个，逐个已实测**）：

| # | 门 | 注入 | 定位标记 |
|:-:|:--|:-----|:---------|
| 1–4 | `check_structure` | 悬空引用 / 未定义规则集 / 不存在的组 / `MATCH` 指向不存在的组 | `悬空引用: 组 Proxy -> Nope-Group` … |
| 5–7 | `check_structure` | 删 `rcode://` / 删 `rule-set:` / 挪到 `cn` 之后 | 见坑 4 |
| 8 | `check_structure` | `ipv6: false` → `true` | `顶层 ipv6 未显式关闭` / `dns.ipv6 未显式关闭` |
| 9 | `check_structure` | 两处列**不同的**集 | `广告集两处不一致` ← 证明是「相等」不是「非空」 |
| 10 | `check_structure` | **删掉 `ipv6` 键** | 仍判负 ← 证明 `is not False`（缺失 ≠ 通过）|
| 11–12 | `check_min_pair` | `.min` 插一条规则 / 只改 `dns.prefer-h3` | `rules 长度不同: 11 vs 12` / `.dns.prefer-h3 值不同` |
| 13 | `check_script_sync` | 从脚本删一条 `RULE-SET,Jinx-CN,DIRECT` | `rules[…]` 定位标记 |
| 14 | `build_rules --check` | 往 `rules/AI.list` 追加一行 | `NG rules/AI_Domains.yaml 已过期` |
| 15 | `check_remote_urls` | URL 改成 `mihomo-white-guard.yaml`（**当年真实死链**）| `死链 N 个` |

⚠️ 第 14 条做之前**先备份真源**（`cp rules/AI.list $SB/AI.list.bak`），做完立刻还原，
并跑一次 `git diff rules/` 确认为空。**别让探针污染真源。**

📌 **9 与 10 这两条"边界样例"尤其值得做** —— 它们证明的是**判据没写反**
（是"相等"不是"非空"；是 `is not False` 不是 falsy）。**只测"明显坏了"证明不了判据的方向。**

#### 判别力回归的现状（诚实口径）

| 门禁 | 判负样例已实测 | 有自动化回归 |
|:-----|:--------------|:------------|
| `check_structure.py` | ✅ 10 个，逐个 exit 1 + 定位标记 | ❌ 无（人工跑）|
| `check_min_pair.py` | ✅ 2 个 | ❌ 无 |
| `check_script_sync.py` | ⚠️ 1 个，能判负但诊断曾缺失 | ❌ 无 |
| `build_rules.py --check` | ✅ 1 个 | ❌ 无 |
| `check_remote_urls.py` | ⚠️ 联网依赖，未逐个固定 | ❌ 无 |
| **`check_region_filters.py`（跨内核）** | ✅ | ✅ **有** —— 唯一定期跑判负 fixture 的闸门 |

> 📌 跨内核的 `check_region_filters.py` 是**唯一**把「判负 fixture」做进总入口的闸门，
> 且它对每个判负用例断言**退出码 + 输出标记**两条。
> **mihomo 侧还没有对应的自动化回归** —— 上表前五行的"已实测"是文档编写时
> **人工跑出来的**，不是常驻 CI 的保证。
>
> **这是已知挂账**：mihomo 侧门禁的判别力目前靠"人记得跑"，不是靠机器守住。

#### 判据固化在哪

- **`skill/reference/gates.md` §9**（整节：为什么 / 每个门的注入手法 / 现状表）。
- **跨内核参考实现**：`skill/tests/check_region_filters.py` —— 它给每个判负用例
  断言「退出码 + 输出标记」两条，是 mihomo 侧要照抄的样板。
- `surge/pitfalls.md` 坑 16 —— 同源纪律（「给这份拷贝配一个比对器，并给比对器配一个判负样本」）。

---

#### 15 · CRLF 判负（行尾不一致）

#### 现象

同一个 commit，在 Windows 上检出是 CRLF，在 Linux / macOS 上是 LF。
于是"线上线下逐字一致"在**字节层面无法成立** —— 按 `\n` 写的正则在 CRLF 工作区上失配。

本项目真实踩过一次：**剥 YAML 头的正则按 LF 写，CRLF 工作区上失配 ⇒
源头部整段漏进正文。**

#### 根因

**Windows 版 Git 安装器会把 `core.autocrlf=true` 写到系统级配置**
（`git config --system core.autocrlf` 可查）。它让 checkout 时把 LF 换成 CRLF
⇒ 换一台机器，磁盘内容就变了。

这是**环境差异**，不是配置差异 —— 靠"大家统一改一下自己机器的 git 配置"是不可靠的
（每个人都得知道这件事，且每个人都会忘）。

#### 修法

把规矩**写进仓**，让每台机器自动生效：

```gitattributes
* text=auto eol=lf

*.png   binary
*.mmdb  binary
*.p12   binary
…

*.conf  text eol=lf
*.yaml  text eol=lf
*.yml   text eol=lf
*.list  text eol=lf
*.py    text eol=lf
*.js    text eol=lf
…
```

| 设计点 | 理由 |
|:-------|:-----|
| `eol=lf` **优先级高于** `core.autocrlf` | 写进仓就等于每台机器自动生效，**不需要任何人去改自己的 git 配置** |
| 显式列出文本类型 | 避免 `text=auto` 因内容启发式把某些文件误判成二进制 |
| 二进制资产标 `binary` | 禁止任何换行改写（`.p12` / `.pem` / `.mmdb` 改一个字节就废了）|

配套：整合时把 Clash 侧 3 个 CRLF 文件（verification.md / ruleset-sources.md / `lazy.yaml`）转成 LF。

#### 判据固化在哪

- **`.gitattributes`**（沿用 SC 原文件，含逐条理由注释）。
- 检测：跨内核的 `skill/tests/check_portability.py`（LF/CRLF 属它的检查面）。
- commit：`3006cf8`（补 `.gitattributes` + 3 个 Clash 文件 CRLF → LF）。
- 纪律：**新增文件类型时若它必须保持原始字节（新的二进制资产），在 `.gitattributes` 下面加一行 `binary`。**

---

#### 附 · 三条横向规律

把 15 条按**失效模式**归类，比按编号记更有用：

| 模式 | 涉及条目 | 共同点 |
|:-----|:---------|:-------|
| **静默失效**（不报错，只是功能没了）| 1 · 2 · 4 · 6 · 11 | 客户端能加载、门禁全绿、用户不报障。**只能靠主动探测 / 对拍 / 双条件判据发现。** |
| **判据自己坏了但看起来在跑** | 3 · 12 · 14 | 只在**失败分支**上执行的代码从未被执行；死常量；只测绿样例。**共同修法：注入坏样例。** |
| **本地全绿 ≠ 线上能跑** | 7 · 8 · 9 · 15 · 2 | 环境相关的东西（编码 / 路径 / mtime / 行尾 / 解析器实现）**只有一种环境被测过**。**共同修法：让 CI 跑一遍。** |

> ⚠️ 三类里最该警惕的是**第二类**。第一类和第三类至少还有"某个地方会红"的可能，
> 第二类是**连红都不会红** —— 它安静地躺在那里，直到某天真的需要它判负。

#### 相关

[`gates.md`](./gates.md)（判据与命令）·
[`profiles/<kern>.md`](./profiles/clash.md)（配置结构 · §18 维护者须知）·
[`ops.md`](./ops.md)（泄露定位 · 面 ③′ IPv6）·
[`gates.md`](./gates.md)（公开仓纪律 · 2511 处事故）·
[`profiles/<kern>.md`](./profiles/clash.md)（移植新内核的清单）·
[`rulesets.md`](./rulesets.md)（同名概念的三内核落点）·
[`AGENTS.md`](../../AGENTS.md)（§7 踩过的坑 · §8 红线）
