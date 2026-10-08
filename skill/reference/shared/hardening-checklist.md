# 加固清单：Surge 14 项 · Egern 18 项 · mihomo 14 项

> 由原两侧 `docs/03` 合并，整合后增补 mihomo 侧。清单按内核分节，逐项对应各侧配置键。

## Surge 侧

> 📛 本文件 2026-09-25 前名为 `03-加固清单-12项.md`：**名字停在 12，而清单早已长到 14**
> （第 13/14 项是后加的，正文自己都引用了它们）—— 文件名里的数字此前**没有任何判据管**，

> 用法：从上到下逐条对照你的 profile。**每一项都给出判据与严重度**。
> 全部自动化：`python skill/scripts/surge/check_surge_dns.py Profile.conf` 覆盖第 1–12 项；
> [`audit_ruleset_content.py`](../../scripts/surge/audit_ruleset_content.py) 覆盖第 13 项；[`audit_routing_coverage.py`](../../scripts/surge/audit_routing_coverage.py) 覆盖第 14 项。

### 清单

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `encrypted-dns-server` 的端点是否 **IP 字面量** | 出现主机名端点 → 该主机名**必被明文解析一次**才能建连 | **高**（境外域名端点）；低（国内域名端点） |
| 2 | `dns-server` 是否显式、是否含 `system` | 写 `system` = 把引导交给运营商 DHCP；**绝不允许**。另要求 ≥2 个**不同机构**的国内解析器 IP | **高**（缺失或含 system） |
| 3 | `hijack-dns` 是否接管硬编码解析器 | 缺失 → 忽略 Surge DNS 的设备（HomePod / Apple TV / 智能音箱）明文 `:53` 裸奔 | **高**（缺失时） |
| 4 | `encrypted-dns-follow-outbound-mode` | 必须 `false`。`true` 时 DoH 连接遵循代理规则 ⇒ 解析代理本身要代理 ⇒ 启动期成环 / 回落明文 | **高**（为 true 时） |
| 5 | `use-local-host-item-for-proxy` | 保持 `false`。`true` 会把本地 DNS 结果变成硬性代理目标，破坏远端解析 | **高**（为 true 时） |
| 6 | 延迟测试端点（`internet-test-url` / `proxy-test-url` / `proxy-test-udp`） | **性能探针，非泄露通道**。官方 KB：走代理时解析在代理服务器进行。选址是性能取向：连通性检测宜国内，`smart` 打分宜境外（含国际段）。仅作提示 | 低 |
| 7 | 策略组引用的成员是否都存在 | 引用不存在的节点名 → Surge **拒绝加载整份配置** | **高** |
| 8 | ⭐ 规则引用的策略是否可解析 | ⚠️ 策略字段位置随类型而变：`DOMAIN-SUFFIX,x,POLICY` 与 `GEOIP,CN,DIRECT` 都在 index 2；只有 `FINAL,POLICY` 在 index 1。写错方向会报出**假 HIGH**（把 `CN` 当策略名） | **高** |
| 9 | ⭐ 规则顺序 | 白名单 → REJECT → 域名类直连 → IP 类 → FINAL。REJECT 排在 `direct.txt` / `GEOIP,CN` 之后 = 白加 | **高** |
| 10 | ⭐ 广告拦截的策略是否是**字面量** REJECT 族 | 写成策略组 → Surge 以「使用了非 REJECT 策略」拒绝加载（组在运行时可能解析成 DIRECT）。另建议带 `extended-matching` | **高** |
| 11 | `always-real-ip` 的主机名是否被兜底之前的域名规则接住 | 没接住 → 落兜底；若兜底依赖代理，启动期那次解析会回退明文 | 中（有远程规则集时降为低） |
| 12 | IP 类规则（`GEOIP` / `IP-CIDR` / `IP-ASN`）是否都带 `no-resolve` | 不带 → 规则匹配时会**额外触发一次本地解析**。⚠️ **定性**：走代理策略时解析本就在代理服务器进行（官方 KB），**这不是泄露补丁**；加它是去掉一次冗余解析 + 把约束固化 | 中 |
| 13 | ⭐⭐ **远程规则集里有没有"不带 `no-resolve` 的 IP 类条目"** | 缺陷藏在**别人仓库的 `.list`** 里，profile 写得再干净也看不见。一条启用的 `RULE-SET` 里只要有**一条**这种条目，**每个走到该规则的域名都会被强制本地解析一次**。必须逐个下载 + 数 | **高** |
| 14 | ⭐⭐ **国内域名有没有"域名类"规则兜底** | 给 IP 规则补 `no-resolve` 会**同时**关掉"靠解析判 IP 归属"这条直连路径。判据是**数域名条目**（不是看规则集名字）：`ChinaMax.list` 只有 64 条域名 / 12472 条 IP，名字叫 ChinaMax 但 99.5% 是 IP | **高** |

### `no-resolve` 的位置：两个层级

| 层级 | 写法 | 作用范围 |
|---|---|---|
| **profile 规则级** | `GEOIP,CN,DIRECT,no-resolve` | 只影响这一条规则 |
| **规则集条目级** | `.list` 里的 `IP-CIDR,x/y,no-resolve` | **第三方 `.list` 走的就是这一层** —— 也是第 13 项缺陷最常藏身的地方，profile 管不到它 |

> ⚠️ 注意：`no-resolve` 写在 `RULE-SET` 那条 profile 规则上（如 `RULE-SET,foo.list,DIRECT,no-resolve`）
> 是**给规则集里所有条目加的默认值**，Surge 支持这个写法。但如果规则集里**条目自带** `no-resolve`
> 缺失，仅靠 profile 侧的写法并不能保证生效 —— 所以要**下载下来数**（第 13 项）。

### 验收标准（六条同时满足才算完）

1. `encrypted-dns-server` 里**没有**主机名端点（全部 IP 字面量或已知的 CDN 端点，后者需显式豁免）
2. `dns-server` 显式列出 ≥2 个不同机构的国内公共解析器 IP，**且不含 `system`**
3. `hijack-dns` 覆盖已知的硬编码解析器（建议直接 `*`）
4. 所有 IP 类规则（`GEOIP` / `IP-CIDR` / `IP-ASN`）**都带 `no-resolve`**
5. ⭐ **所有被启用的远程规则集，其 IP 类条目都带 `no-resolve`**
6. ⭐⭐ **分流仍然正确：国内域名仍判给 `DIRECT`**（17 个国内探针必须全绿，且**必须包含非 `.cn` 的域名**）
   **这一条是第 12 项的代价，必须成对交付** —— 给 IP 规则补 `no-resolve` 会同时关掉
   "靠解析判 IP 归属"那条直连路径。所以补 `no_resolve` 的同一时刻，必须确认
   `FINAL` 之前有一份**含大量域名条目**的国内规则集。

> ⚠️ **只检查 `.cn` 后缀会假通过** —— 那靠的是 `DOMAIN-SUFFIX,cn` 这条兜底，
> 而不是真的接住了国内域名。[`audit_routing_coverage.py`](../../scripts/surge/audit_routing_coverage.py) 的国内探针刻意混入了
> `qq.com` / `taobao.com` / `miui.com` / `bilibili.com` 这类非 `.cn` 域名。

## Egern 侧

> 用法：从上到下逐条对照你的 profile。**每一项都给出判据与严重度**，"⭐"标出本清单里最容易被跳过、也最容易只看字面就漏掉机理的关键项。
> 全部自动化：`python skill/scripts/egern/check_egern_dns.py Profile.yaml` 覆盖第 1–15 项；
> [`audit_ruleset_noresolve.py`](../../scripts/egern/audit_ruleset_noresolve.py) 覆盖第 16 项；[`audit_routing_coverage.py`](../../scripts/egern/audit_routing_coverage.py) 覆盖第 17 项；
> [`audit_dns_forward.py`](../../scripts/egern/audit_dns_forward.py) 覆盖第 18 项。

### 清单

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `upstreams` / `proxy_nameservers` 的加密 DNS 端点是否为 **IP 字面量**（或已钉 `hosts`） | 出现主机名端点 → **必定被 `bootstrap` 明文解析一次** | **高**（境外域名端点）；低（国内域名端点） |
| 2 | ⭐ `proxies[].server` 是**域名**的节点，**代理 DNS 那条路**有没有落在国内加密组上 | 没有 → 代理 DNS 强制直连、问不到境外解析器 → 回退明文 `bootstrap`（国内解析器）→ **节点域名明文暴露**。判据看 `proxy_nameservers` **或** `forward` 兜底（二者任一即可，见 2b）；根治手段是把节点 `server` 改写成 IP 字面量。⚠️ **"在 `forward` 里为节点域名加一条 `domain_suffix`"是错的查法/修法** —— 设了 `proxy_nameservers` 后代理 DNS **跳过** `forward`，该规则永不命中（f7 起即为死代码） | **高** |
| 2b | `proxy_nameservers` 是否存在 | 它是**硬覆盖**：一设就跳过 `forward`、强制直连。**两种写法都成立，但必须二选一、不要叠加**：① **不设置** —— 代理 DNS 与默认 DNS 共用 `forward`，靠兜底接住节点域名；② **设置** —— 把"未命中回退 `bootstrap`"这条分支从结构上消掉，且强制直连 ⇒ 不依赖代理就绪。**本模板采用 ②，理由即此。** ⚠️ 设置后 `forward` 对节点域名失效 | 中（设了要说明理由 —— 本模板已在 `dns` 段注释里说明） |
| 3 | ⭐ DNS 端点是否有**显式路由** | `geoip` 加了 `no_resolve` 就**不再匹配域名**；主机名形式的端点会落到 `default` → 国内端点被绕到境外出口 / 境外端点直连被阻断。**国内端点必须显式 → `DIRECT`，境外端点必须显式 → `Proxy`** | **高** |
| 4 | ⭐ `forward` 里是否存在「捕获一切」的兜底，**且该兜底组「直连可达」** | 兜底存在的意义只有一个：让未命中的域名不回退 `bootstrap` 明文。**判据是「这组在代理没起来时能不能工作」** —— 组内端点必须全是 IP 字面量，**且满足下面两条之一**：<br>**判据 A** 至少一个端点在 `rules` 里被判给 `DIRECT`；<br>**判据 B** 至少一个是已知的**国内**公共解析器 IP（`223.5.5.5` / `223.6.6.6` / `119.29.29.29` / `1.12.12.12` / `120.53.53.53` …）—— 其归属与服务商是公开事实，在国内任何链路上都直连可达，与"在 `rules` 里判给 `DIRECT`"等价，且不需要在配置里写装饰性规则。<br>⚠️ 判据 B 是 f10 引入的：模板删掉那 15 条 DNS 端点路由规则后，正是靠它通过验收。脚本 [`check_egern_dns.py`](../../scripts/egern/check_egern_dns.py) 的 `group_reach()` 同时实现了 A 与 B。<br>只判给 `Proxy` 的组 = 依赖代理 = 启动期会掉进明文。**写法要认全**：`domain_wildcard: '*'` **和** `domain_regex: '.'`（官方 PCRE2 find 式）都算兜底 —— 推荐**两条都写** | **高** |
| 5 | `geoip` / `ip_cidr` / `ip_cidr6` / `asn` 是否带 `no_resolve` | 官方：`no_resolve` **仅适用这四类**；不加则规则会**触发解析** | **高** |
| 6 | ⭐ 规则引用的**策略名能否解析** | `policy` 嵌在类型字典里（`{domain: {match, policy}}`）—— 要读 `r[type]['policy']`。抓 `负载均衡` 这类笔误 | **高** |
| 7 | 硬编码 DoH IP（`8.8.8.8` / `1.1.1.1` / `9.9.9.9` / OpenDNS…）是否有**启用**的规则 → 代理 | `hijack_dns` 只覆盖 **:53**，App 自带 DoH on **:443** 会绕过 | 中 |
| 8 | ⭐ `rule_set.match` 是否为 **URL 或文件路径** | 写成 `AI` / `抓取` / `Apple push` 这种名字 → 无法加载，等同**死规则** | 中 |
| 9 | `block_ips` | 未设 → `0.0.0.0` 这类空路由式污染应答照单全收 | 低 |
| 10 | `real_ip_domains` | 为空 → 走不到隧道的流量（APNs / 内网）也拿 Fake IP，推送/内网会异常 | 低 |
| 11 | `ipv6` | `true` → AAAA 可绕过 IPv4 侧封堵 | 中 |
| 12 | `hijack_dns` 是否覆盖全部 | 官方示例值即 `['*']`（接管 `:53` 并返回 Fake IP） | **高**（缺失时） |
| 13 | `public_ip_lookup_url` | **不配置**才不发 ECS（不把公网 IP 交给 DNS 服务器） | 配了才是问题 |
| 14 | `skip_tls_verify` | 应为未设置 / `false` | 低 |
| 15 | ⭐ **profile 自身必需解析的名字**（两个 latency test URL 的域名 + 策略组 `icon` 的域名）是否被"兜底之前"的 `forward` 规则接住 | 没接住 → 落兜底；一旦这次解析发生在直连侧，境外组不可达 → 回退明文 → 再落 `system` = 运营商。**延迟测试端点 = 高**（每轮测速都触发，持续泄露）；**图标 = 低**（失败只是图标不显示；硬钉到国内解析器反而可能拿到污染/`0.0.0.0` 应答，收益 < 风险，可故意不动） | **高** |
| 16 | ⭐⭐ **远程规则集里有没有"不带 `no-resolve` 的 IP 类条目"** | 缺陷藏在**别人仓库的 `.list`** 里，profile 写得再干净也看不见。官方：`no_resolve` 为 `true` 才"不触发 DNS 解析" ⇒ **不带就触发**。一条启用的 `rule_set` 规则里只要有**一条**这种条目，**每个走到该规则的域名都会被强制本地解析一次**。实测 `Apple_All.list` 有 13 条。**必须逐个下载 + 数** | **高** |
| 17 | ⭐⭐ **国内域名有没有"域名类"规则兜底**（不是"有没有一条叫 China 的规则"） | 给 IP 规则补 `no_resolve` 会**同时**关掉"靠解析判 IP 归属"这条直连路径。若没有一个**真正的域名规则集**接住国内域名，它们会整片落到 `default → Final → 代理`。判据：把规则集**下载下来数域名条目**，再用 [`audit_routing_coverage.py`](../../scripts/egern/audit_routing_coverage.py) 拿真实域名走一遍 | **高** |
| 18 | ⭐ `forward` 的 **`value` 是否单值**、以及**订阅耦合度**（`forward` 里有没有把节点域名写死） | `value` 单值时，**规则顺序与域名清单都不影响结果** ⇒ 可塌缩为纯兜底、与订阅解耦。判据：`value` 集合只有 1 个元素 + `proxies[].server` 的域名在 `forward` 里出现 0 次。用 [`audit_dns_forward.py`](../../scripts/egern/audit_dns_forward.py)` --drill` 拿**合成的"未来订阅"域名**演练验证 | 中 |

### `no_resolve` 的三个层级

| 层级 | 写法 | 作用范围 |
|---|---|---|
| **规则级** | `rules:` 里的 `- geoip: {match: CN, policy: DIRECT, no_resolve: true}` | 官方明说**只适用 `geoip`/`ip_cidr`/`ip_cidr6`/`asn` 四类**；写在 `rule_set` 规则上**不生效** |
| **规则集文件顶层** | Egern 原生 YAML 规则集里的 `no_resolve: true` | 影响该文件内所有 IP 相关规则 |
| **规则集条目级** | Surge `.list` 里的 `IP-CIDR,x/y,no-resolve` | **第三方 `.list` 走的就是这一层** —— 也是第 16 项缺陷最常藏身的地方，profile 管不到它 |

### 验收标准（六条同时满足才算完）

1. `upstreams` 与 `proxy_nameservers` 里**没有任何主机名端点**（全部 IP 字面量，或已钉 `hosts`）
   → 消灭 `bootstrap` 用途①。
2. `forward` 有兜底，**且兜底组直连可达**（端点全为 IP 字面量 + 满足**判据 A 或判据 B**，见清单第 4 项）
   → 消灭 `bootstrap` 用途②，且不依赖"代理已就绪"。
3. 所有 IP 类规则（`geoip` / `ip_cidr` / `ip_cidr6` / `asn`）**都带 `no_resolve`**。
4. ⭐ **所有被启用的 `rule_set` / `proxy_rule_set`，其规则集文件里的 IP 类条目都带 `no-resolve`**。
5. `bootstrap` 显式列 2 个以上国内公共 DNS 的 IP，**且不含 `system`**
   → 把"全失败 → 系统 DNS"这一最坏分支的概率压到最低。
   ⚠️ **前 4 条是"让它不被用到"；第 5 条只是把最坏分支的概率压小。** `bootstrap` 是明文 UDP:53，在运营商线路上无论指向哪个 IP 都可能被接管 —— **它唯一安全的形态是"永远不被触发"。**
6. ⭐⭐ **分流仍然正确：国内域名仍判给 `DIRECT`**（15 个国内探针必须全绿）。
   **这一条是第 3 条的代价，必须成对交付** —— 给 IP 规则补 `no_resolve` 会同时关掉"靠解析判 IP 归属"那条直连路径。
   所以补 `no_resolve` 的同一时刻，必须确认 `default` 之前有一份**含大量域名条目**的国内规则集。
   **"DNS 审计全绿"不等于"配置可用"** —— f7 时两个审计脚本双双通过，分流却整片是坏的。

### 五个脚本的定位与分工

| 脚本 | 看哪一层 | 关键点 |
|---|---|---|
| `check_egern_dns.py` | **profile 文本** | 能验证的只有"你自己编码进去的假设" |
| `audit_ruleset_noresolve.py` | **被引用的规则集文件** | 缺陷不在 profile 里 —— 不下载就永远看不见 |
| `audit_routing_coverage.py` | **域名 → 命中规则 → 策略** | 验证"防泄露"没把"分流"一起干掉 |
| `audit_dns_forward.py` | **`forward` 的结构**（单值性 / 订阅耦合 / 换订阅演练） | 验证"换订阅后还能不能防泄露" |
| `audit_region_filters.py` | **地区组 filter 的「两份拷贝」** | 负向断言（"排除以上全部"）必须逐字重抄关键词，Egern 不支持 `filter` 引用 ⇒ 只能靠脚本守同步 |

> ⭐ **本项目最贵的一条工程教训：审计通过 ≠ 配置可用。**
> 这条线上连续出现过 5 次"脚本 0 high、用户实测仍有问题"：有的是靠加配置压指标、有的是审计维度缺失（只看 profile、没看它引用的规则集）、有的是两个脚本双双全绿而分流整片是坏的。
> **固化规则：任何一次「审计绿了但实测有问题」，都必须假设"存在审计器看不见的维度"，并把这个维度补成一个可复跑的脚本 —— 而不是重跑同一个脚本。**

## mihomo 侧

> 用法：从上到下逐条对照你的 profile。**14 项判据与 `check_clash_dns.py` 一一对应**（编号即脚本里的判据号）；
> 另有 `check_structure.py` 8 项结构判据与之互补（见文末的分工表）。
> 逐键语义与边界的权威是 [`clash/reference/profile-anatomy.md`](../clash/profile-anatomy.md)，
> 本章只列清单与判据，不重复逐键解释。

**自动化**：

```bash
# 防泄露语义（14 项，分级发现）
python skill/scripts/clash/check_clash_dns.py clash/profiles/routing.yaml
python skill/scripts/clash/check_clash_dns.py clash/profiles/lazy.yaml
python skill/scripts/clash/check_clash_dns.py out.yaml --override   # 覆写脚本输出形态：不要求 tun 段
python skill/scripts/clash/check_clash_dns.py clash/profiles/routing.yaml --strict   # medium 也算失败

# 结构（8 项，四份 profile 一起判）
python skill/tests/clash/check_structure.py
```

退出码：`0` = 无 high（`--strict` 下还要求无 medium）· `1` = 有 high · `2` = 用法错误 / 读不到 / YAML 坏 / 缺 pyyaml。
⚠️ `2` 与 `1` 必须分开：环境炸掉**绝不能被读成一次成功的判负**（Windows cp936 下 `print` 一个中文就可能让进程以 1 退出 —— 而 1 恰是"判负"的码）。

### 清单（14 项，与 `check_clash_dns.py` 判据号一致）

| # | 检查 | 判据 | 严重度 |
|---|---|---|---|
| 1 | `dns` 段存在且 `enable: true` | 没有 `dns` 段 ⇒ 全部查询走**系统 DNS**（运营商 DHCP 下发的那台）；`enable` 不为 true ⇒ DNS 劫持与 fake-ip 全部失效 | **高** |
| 2 | ⭐ `default-nameserver` 是否全为 **IP 字面量** | 官方硬性要求。这一层**唯一**用途是解析其余 DNS 端点**自己的域名**（引导），它必然是明文 UDP:53（不能再依赖加密解析器，否则成环）⇒ 它自己写主机名 = "解析解析器"又要一次明文解析 = **鸡生蛋**。带 scheme 的写法（如 `https://223.5.5.5/dns-query`）判 MEDIUM（引导层成环）。当前两版均为 `223.5.5.5` / `119.29.29.29` 纯 IP | **高**（主机名）／中（带 scheme） |
| 3 | ⭐ `nameserver` / `fallback` 端点必须是「**IP 字面量** **且** **加密 scheme**」的**合取** | 两条独立的坏法对应两个面：**写主机名** ⇒ 冷启动必然用 `default-nameserver` 明文解析一次（面①）；**写裸 IP**（如 `nameserver: 8.8.8.8`）⇒ **每一笔查询都是明文 UDP:53**（面②，比面①严重得多 —— 带的是业务域名）。⚠️ 只判"是不是 IP"会把最坏写法判成通过 | **高** |
| 4 | ⭐ `proxy-server-nameserver` 必须存在（节点域名解析的鸡蛋问题） | 缺它 ⇒ 代理节点自己的域名走主路径（本仓是境外 DoH）⇒ "要先有代理才能解析出节点地址"，失败时退回明文 / 系统 DNS，**节点域名明文暴露**（与 Egern 侧 `proxy_nameservers` 同一条判据）。缺 `direct-nameserver` ⇒ `DIRECT` 出站的域名也去问境外主解析器（答案不准 + 多一次境外查询，非明文 ⇒ MEDIUM）。当前分流版两个端点写的是**主机名**（`doh.18bit.cn` / `dns.alidns.com`）⇒ 4 条 LOW：国内端点、信号弱，是取舍不是缺陷 | **高**（缺前者）／中（缺后者）／低（端点用主机名） |
| 5 | `enhanced-mode: fake-ip` 且 `fake-ip-range` 落在 **RFC 6815 保留段** | `redir-host` / 未设置 ⇒ 每个域名都真实解析一次（本地留答案）；`fake-ip-range` 不在 `198.18.0.0/15` ⇒ 拿假 IP 去连真实网络。当前 `198.18.0.1/16` ✅ | **高**（段不对）／中（模式不对） |
| 6 | ⭐ IPv6 **两处**都要显式关闭：顶层 `ipv6` **与** `dns.ipv6` | 判据用 `is not False` ⇒ **键缺失也算不过**。`dns.ipv6: true` ⇒ 应用拿到真实 AAAA；顶层 `ipv6: false` ⇒ IPv6 流量不被 TUN 接管；两者叠加 = 双栈站点直连出去、绕过代理。⚠️ 只关一处比两处都开更隐蔽 | **高** |
| 7 | ⭐ `tun` 是否接管 `:53`（旁路设备面③）+ `strict-route` | ⭐ 判据不是"列了几条"，而是**是否覆盖 `:53` 的整个地址空间** —— 地址空间无限，逐个列举永远列不全（Surge 侧第 3 项踩过同一个坑：按条数判负是错的）。只有 `any:53` / `0.0.0.0:53` 才叫收口。另要求 `enable` / `auto-route` / `strict-route` 三键。<br>⚠️ **形态差异**：覆写脚本（`override/*.js`）的输出**不该有** `tun`（客户端自己管 TUN）⇒ `--override` 下本项整体跳过；当前也未接管 TCP:53（不写协议前缀默认 `udp://`，LOW，是已知取舍） | **高** |
| 8 | ⭐⭐ **DNS 层广告拦截的两个必要条件**（缺任一 ⇒ 静默失效、且不报错） | ① `nameserver-policy` 里 `rule-set:<广告集>: rcode://success`；② **同一个广告集在 `fake-ip-filter` 里再列一遍** —— 否则 `withFakeIP` 中间件对 A / AAAA **直接返回假 IP**，请求永远走不到 ①。另：两处广告集**必须一致**，且都**不得引用未定义**的 `rule-set:`（死引用 ⇒ 静默消失）。当前两版均为 `AWAvenue-Ads` + `Jinx-Ads`，两处一致 ✅ | **高** |
| 9 | `nameserver-policy` 的**广告项必须排在 `cn` / `private` 之前** | YAML mapping 在 Python 3.7+ 保持插入顺序，而这个顺序**就是 mihomo 的匹配顺序**：先命中 `rule-set:cn` ⇒ 拿国内答案，永远走不到后面的 `rcode://success` | **高** |
| 10 | ⭐⭐ IP 类规则必须带 `no-resolve`（面④），域名类不该写 | ⭐ 判"是不是 IP 类规则"的**第一依据是 provider 的 `behavior`**，不是名字前缀：`ipcidr` ⇒ 不带会为判定而强制解析；`domain` ⇒ 写了无意义；`classical` ⇒ 内容混合、**无法静态判定**（单独归组提示）。只有 provider 未声明 `behavior` 时才退回 `geoip-` 名字前缀兜底。<br>⚠️ **双刃与另两侧同**：给 IP 规则补 `no-resolve` 会同时关掉"靠解析判 IP 归属"那条直连路径 ⇒ 必须与域名补偿**成对交付**（见 [no-resolve-pairing.md](no-resolve-pairing.md)）。当前分流版 4 条 / 懒人版 2 条全部带 ✅ | **高**（IP 类缺）／低（域名类写了） |
| 11 | ⭐ **零 dat 依赖** | 顶层出现 `geox-url` / `geo-auto-update` / `geo-update-interval` ⇒ mihomo 会去下载并加载 `GeoSite.dat` / `GeoIP.dat`；规则写原生 `GEOSITE,` / `GEOIP,` ⇒ 直接查那两个库；`nameserver-policy` 键用 `geosite:` 同理；provider 引 `.dat` 文件同样判负。<br>⚠️ **这不排斥 `.mrs`**：`geoip-private` / `geoip-cn` 等是 MetaCubeX 的**独立远程集文件**（`format: mrs`），与 dat 数据库无关 —— 正是本仓想要的形态。判据只拦 dat，不拦 mrs（注入测试专门验过不误伤） | **高** |
| 12 | `rule-provider` 形态（**不做网络探测**） | 既无 `url` 也无 `path` ⇒ 永远加载不出来 ⇒ 引用它的规则**静默变成空集**（死规则），门禁看不出来。一个 provider 都没有 ⇒ MEDIUM。可达性归 `check_remote_urls.py` | **高**（缺 url+path）／中（零 provider） |
| 13 | ⭐ 规则引用的名字必须**能解析**（provider / 策略组） | 引用不存在的东西**不会让 mihomo 拒绝启动** —— 它只是静默不生效。对防泄露而言这最危险：那正是收口装置所在的位置（广告集 / 国内集 / 兜底）。策略名笔误（如 `负载均衡`）同判 | **高** |
| 14 | 其余 DNS 开关（提示性） | `respect-rules` 未开 ⇒ DNS 查询自己不按路由规则走；`use-system-hosts: true` ⇒ 读本机 hosts；`prefer-h3: true` ⇒ 优先 HTTP/3；`dns.listen` 设了 ⇒ 内核对外开明文 `:53` 端口（脚本**不设**它，早期写死 `0.0.0.0:7874` 会与客户端 DNS 端口冲突） | 低 |

### `no_resolve` 的位置：两个层级

| 层级 | 写法 | 作用范围 |
|---|---|---|
| **规则级** | `RULE-SET,geoip-cn,DIRECT,no-resolve` | 只影响这一条规则。mihomo 的 `RULE-SET` 确实解析该参数并传给 `NewRuleSet`（源码：`rules/parser.go` 的 `case "RULE-SET": isSrc, noResolve := RC.ParseParams(params)`） |
| **provider 的 `behavior`** | `behavior: ipcidr` | **判定"这条规则是不是 IP 类"的第一依据** —— 比名字前缀可靠，也是 `check_clash_dns.py` 判据 10 的落点 |

> ⚠️ 与 Egern 相反的一点是：**写在 `rule-set` 规则对象上（Egern 的 `no_resolve: true`）不生效**，
> mihomo 的 `no-resolve` 写在规则行尾。三侧落点对照见 [no-resolve-pairing.md](no-resolve-pairing.md)。

### 验收标准（六条同时满足才算完）

1. `dns` 段存在且 `enable: true`；`default-nameserver` **全部 IP 字面量**（不带 scheme）。
2. `nameserver`（及 `fallback`，若开启）端点全部「**IP 字面量 + 加密 scheme`**」的合取 ——
   消灭面①（引导解析）与面②（明文回退链）。
3. `proxy-server-nameserver` **存在**（节点域名有独立出口，不依赖代理）—— 消灭面③ 的鸡蛋问题；
   另 `direct-nameserver` 存在 ⇒ 直连域名不碰境外解析器。
4. ~~`tun` 收口~~ ⇒ **2026-10-08 起本仓不带 `tun` 段**（见下条与代码）；TUN 由客户端接管，配置不写。
   —— 消灭面③（旁路设备）。⚠️ 覆写脚本形态下这一条换成"客户端自己管 TUN"，用 `--override` 审。
5. 顶层 `ipv6: false` **与** `dns.ipv6: false` —— 两处，少一处都不算完（面③′）。
6. ⭐⭐ **分流仍然正确：国内域名仍判给 `DIRECT`** —— `RULE-SET,cn,DIRECT` 必须在 `MATCH,Proxy` **之前**，
   且它必须是 `behavior: domain` 的真正域名集。
   **这一条是第 10 项的代价，必须成对交付**：给 IP 规则补 `no-resolve` 会同时关掉
   "靠解析判 IP 归属"那条直连路径。
   ✅ **mihomo 侧已有专用分流覆盖审计脚本** `skill/scripts/clash/audit_routing_coverage.py`（2026-10-07 补出，已进闸门 #9）—— 前 5 条自动化后，这一条**先跑闸门 #9**；但离线档按规则集名+实际策略校验，**不能证明真实域名命中** ⇒ 仍需实测兜底，别把闸门绿当充分条件。（此处曾长期写「没有」，与实际相反。）
   且要用**国内非 `.cn` 域名**验证（只测 `.cn` 会被后缀兜底救活，假通过）。

### 两个脚本的定位与分工

| 脚本 | 看哪一层 | 关键点 |
|---|---|---|
| `check_clash_dns.py`（`skill/scripts/clash/`） | **profile 文本 + provider 语义** | 14 项防泄露判据，分级（🔴/🟠/🟡/✅）。判据是**实测推导**而非字符串匹配；**不做网络探测**；豁免写在**被审对象**里（`# audit-waive: <判据号> <理由>`） |
| `check_structure.py`（`skill/tests/clash/`） | **结构 / 引用 / 形态** | 8 项：① 无悬空引用 ② 规则指向的 provider 与策略组存在 ③ 广告双条件 + 广告项排在 `cn` 之前 ④ **禁止** `tun` 段（4c4bc56 起反转；原为「要求四键」，文档曾长期说反）⑤ `geoip-*` 规则带 `no-resolve` ⑥ `nameserver` 必须 IP 字面量 ⑦ 零 dat 依赖 ⑧ IPv6 两处显式关闭 |
| `check_min_pair.py`（`skill/tests/clash/`） | **`.min` ↔ 完整版** | 去掉注释后配置本体必须逐字相同 |
| `check_script_sync.py`（`skill/tests/clash/`） | **脚本输出 ↔ 静态 profile** | 同一套配置的两种交付形态必须逐位一致（需 node）；Smart 三档是**已知差异**，打印提醒不判负 |
| `build_profiles.py --check`（`skill/scripts/clash/`） | **生成物新鲜度** | 改了 `override/*.js` 没重生成 ⇒ 判负；内含自检（防"纵向堆叠 7 份"那类畸形） |
| `build_rules.py --check`（`skill/scripts/clash/`） | **`rules/*.yaml` ↔ `.list` 真源** | 生成物过期即判负；❌ 不手工编辑 `rules/*.yaml` |
| `check_remote_urls.py`（`skill/tests/clash/`） | **远程集可达性**（联网，慢） | 死链不是报错，是**静默降级** —— provider 拉不到就变空集，广告全进兜底出口而配置看着跑得挺好 |

> ⭐ **审计通过 ≠ 配置可用**（三侧共通的母题）。mihomo 侧**已有**分流覆盖审计脚本（闸门 #9），但审计通过仍不等于真机可用 —— 这句母题对三侧都成立。
> （三内核均有 `audit_routing_coverage.py`，闸门 #7/#8/#9）—— 第 6 条验收标准**先跑它们**，但注意离线档按规则集名推演、不读实际策略（第五轮审查问题 7），**仍需实测兜底**，别把闸门绿当充分条件。
> 这正是 `no-resolve-pairing.md` 要跨内核保留下来的教训：**不得因为两道静态门禁全绿就跳过它。**

### 已知取舍（LOW 不是缺陷）

当前基线（2026-10-07 实测）：分流版 **0 high / 0 medium / 7 LOW / 21 OK**，懒人版 **0 high / 0 medium / 2 LOW / 21 OK**。
那些 LOW 都是刻意留下的取舍，改之前先问"我真的需要吗"：

| LOW | 来源 | 为什么留着 |
|:----|:-----|:-----------|
| `proxy-server-nameserver` / `direct-nameserver` 端点是主机名（`doh.18bit.cn` / `dns.alidns.com`） | 判据 4 | 国内端点：只带出"本机在用哪个 DoH"，信号弱；改成 IP 字面量需自建端点 |
| `dns-hijack` 未接管 TCP:53 | 判据 7 | 不写协议前缀时默认 `udp://`；明文 TCP 查询在现代客户端里罕见（要覆盖得写 `tcp://any:53`） |
| 5 个 `classical` 规则集内容无法静态判定 | 判据 10 | 面⑤：远程集里的裸 IP 条目**不在本文件里**，本地静态门禁看不见，必须拉下来数；本仓自托管的 `rules/*.list` 实测 **0 条 IP 条目** |
| `fallback-filter.geoip: true` | 判据 3 | 两端都是 DoH 时不是泄露，是**双倍延迟**；懒人版干脆不开 `fallback` 就是同一个判断 |

---

下一步：[分流与 no-resolve 必须成对交付](no-resolve-pairing.md)。
