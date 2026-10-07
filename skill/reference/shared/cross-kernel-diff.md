# 跨内核差异对照

> 本仓库把 Surge 与 Egern 两套模板合到一处。**分组与规则已基本对齐**，但两款内核实现逻辑不同。
> 这一页是给"想把一侧的改动移植到另一侧"的人看的：哪些能直接照搬、哪些照搬就是错的。
> 结论均来自对 `surge/profiles/routing.conf` 与 `egern/profiles/routing.yaml` 的逐条比对。

## 1 · 语法映射

| 语义 | Surge | Egern | 移植时注意 |
|:-----|:------|:------|:-----------|
| 配置载体 | `.conf` INI 分段 | `.yaml` | — |
| 本地 DNS | `dns-server = a, b` | `dns.bootstrap` / `dns.upstreams` | Egern 分「默认 DNS / 代理 DNS」两条路，Surge 只有一条 |
| 加密 DNS | `encrypted-dns-server = https://…` | `dns.upstreams.<组名>` | 判据是写 **IP 字面量**；Surge 侧对 2 条主机名端点挂了显式豁免，见第 8 节 |
| 代理侧解析 | 无独立键（由 `dns-server` 承担） | `dns.proxy_nameservers` | ⚠️ Egern 一旦设它就**跳过 `forward`**，Surge 无此机制 |
| 接管明文 53 | `hijack-dns = 8.8.8.8:53, …` | `hijack_dns: ['*']` | Egern 支持通配全接管；Surge 侧只能列清单，判据是"还漏几个知名解析器" |
| 不解析 | `no-resolve`（规则行内） | `no_resolve: true`（规则字段） | ⚠️ Egern 仅对 `geoip`/`ip_cidr`/`ip_cidr6`/`asn` 四类生效，写在 `rule_set` 上不生效 |
| 远程规则集 | `RULE-SET,<URL>,<策略>` | `- rule_set: {match, policy}` | 两侧都可直接引用 Surge 格式 `.list` |
| 刷新间隔 | `"update-interval=604800"` | `update_interval: 604800` | 本仓**两侧统一一周、且都显式写死**；两侧显式写的**理由不同**，判据全文见 [`rulesets.md`](rulesets.md) §1 |
| 策略组 | `[Proxy Group]` | `policy_groups:` | 见下节，两组 26 项已对齐 |
| 组展开 | `include-other-group="X"` | `flatten: true` | 语义等价（复制的是 resolved member policies） |
| 组内正则筛选 | `policy-regex-filter` | `filter` | ⚠️ Surge 的 `policy-regex-filter` **对显式列出的成员无效**，需同时 `include-all-proxies=true` |
| 地理判定 | `GEOIP,CN,DIRECT,no-resolve` | `- geoip: {match: CN, …, no_resolve: true}` | — |
| 默认出口 | `FINAL,<组>,dns-failed` | `- default: {policy: <组>}` | Surge 可带 `dns-failed`；Egern 无此参数 |
| 解析阶段拒答 | `REJECT,pre-matching,extended-matching` | `dns.forward` 里 `value: reject` | ⚠️ 机制完全不同但**目的相同**：都在解析阶段掐断，不产生后续查询 |
| 内置 LAN | `RULE-SET,LAN` | 无内置 → 引用 `Lan.list` | 实测差异之一，见第 3 节 |
| 延迟测试端点 | `internet-test-url` = `connect.rom.miui.com`（国内 204）
`proxy-test-url` = `www.gstatic.com`（境外，给 `smart` 打分） | `direct_latency_test_url` = `connect.rom.miui.com`
`proxy_latency_test_url` = `www.gstatic.com` | **2026-10-05 起两内核同值**（此前 Egern 用 `cp.cloudflare.com` / `connectivitycheck.platform.hicloud.com`）；⚠️ 两个键在两侧都是**单值 URL**，官方均无 fallback 写法 |
| 内置系统进程 | `RULE-SET,SYSTEM` | 引用本仓快照 `apple_system.list`（= 内置集的时点内容，缺两条 `PROCESS-NAME`） | 2026-09-24 起两侧同位各一套；Egern 侧没有进程名匹配能力，那两条接不住 |
| 网络级暂停 | `[SSID Setting]` 段：`SSID:MyHome suspend=true`（匹配到名下 Surge 整机暂停、离开该网络自动恢复） | **无对等件**：只有 `rules` 的 `ssid` 条件项（该网络下命中流量走指定策略，隧道不暂停） | 刻意不移植：拿「全直连规则」硬凑会让两侧规则表分叉，且语义不等价（暂停 ≠ 直连） |

## 2 · 分组：已完全对齐

现役两侧各 **<!-- auto:group-count -->23<!-- /auto:group-count --> 个分组，名称与顺序逐位相同**（`routing_v3.4` 起实测逐行 diff 无差异，2026-09-29 随 v4.0 复核；2026-10-04 两侧同步删去 `WeChat` 组，2026-10-05 两侧同步删去 `Korea` 组与 `GitHub` 组，2026-10-06 两侧同步新增 `Apple Update` 组）：

```
<!-- auto:group-list -->
Proxy · Smart · ChatGPT · Gemini · Claude · AI · YouTube · Emby · Google
Telegram · YouTube Music · Spotify · Twitter · Airport · Microsoft · Apple Update
AD · Hong Kong · Taiwan · Japan · Singapore · United States · Other Regions
<!-- /auto:group-list -->
```

移植分组改动时唯一要换的是写法：Surge 用 `include-other-group` + `policy-regex-filter`，
Egern 用 `policies` + `flatten` + `filter`。地区组倍率筛选的正则两侧共用同一份
（`(?<![\d.])0\.\d*[1-9]` 收所有倍率 < 1 的节点）。

## 3 · 规则：<!-- auto:rule-count -->26<!-- /auto:rule-count --> 条位位对应，三处引擎差异

顺序两侧一致（广告白名单 → 广告拦截 → Apple 更新 → 系统域 → 内网 → 应用组 → 国内兜底 → 地理 → 默认）。三处**不是疏漏、而是内核能力差异**：

⚠️ 上表的「Apple 更新」位（④）**仅分流版有**：懒人版不设 `Apple Update` 组，其位序为
「广告白名单 → 广告拦截 ×2 → 系统域 → 内网 → AI → 国内 → 地理 → 默认」（11 条）。

| 位 | Surge | Egern | 性质 |
|:-:|:------|:------|:-----|
| ⑥ | `RULE-SET,LAN`（内置） | `Lan.list`（blackmatrix7） | 内置规则集的有无 |
| ⑤ | `RULE-SET,SYSTEM`（内置）→ `DIRECT` | `apple_system.list`（**本仓自托管**快照）→ `DIRECT` | 同一套系统域名规则的两种载体。快照删了 Egern 不支持的两条 `PROCESS-NAME`（`trustd` / `netbiosd`）⇒ Surge Mac 上那两条还额外接住两个系统进程的请求，Egern 侧接不住。两侧都不再占位给 `Proxy.list`（它已改成注释态，两边同写法） |
| ②③ | 两条广告清单 → `REJECT`（字面量） | 两条 → `AD`（策略组） | ⚠️ **方向相反**：Surge 侧 `pre-matching` 的规则**策略必须是字面量 REJECT 族**，写成策略组会导致 Surge **拒绝加载整份配置**；Egern 无此限制，故用 `AD` 组以便面板上开关 |

> 移植提醒：把 Egern 的"广告指向 `AD` 组"照搬到 Surge 的 `pre-matching` 规则上，
> 后果不是效果差一点，而是**整份配置加载失败**。
>
> 📏 **禁用一条规则也只能各自按内核的写法来**：Surge 的 `RULE-SET` 只认 `no-resolve` /
> `extended-matching` / `update-interval` / `pre-matching` 四个参数，**没有 disabled 字段**，
> 不想要的行只能注释掉；Egern 有 `disabled: true`，但它**仍占 `rules` 数组的一位** ⇒
> 想保持逐位对齐就得两边都用注释。本仓 `Proxy.list` 即按此统一（2026-09-24）。
>
> 🧪 **规则级 `no-resolve` 的同一条原则，两内核落点不同**：原则是「实测零 IP 条目的规则集不写，
> 真含 IP 的必须写」。Surge 写在规则行末尾；Egern 的 `no_resolve` 只适用 `geoip`/`ip_cidr`/
> `ip_cidr6`/`asn`，**写在 `rule_set` 上不生效** ⇒ 它的同层防线落在规则集文件里（条目级
> `,no-resolve`），由 `audit_ruleset_noresolve.py` 逐个下载核对。

## 4 · 懒人版：对齐程度明显低于分流版

`lazy` 两侧**并未逐条对齐**，这是现状而非缺陷，移植时务必按实际来：

| | Surge `lazy.conf` | Egern `lazy.yaml` |
|:--|:-----------------|:-------------------|
| 规则条数 | 11 | 11 |
| 广告拦在哪一层 | `pre-matching` + `extended-matching` → **DNS 与 TCP-SYN 阶段** | `dns.forward` 两条 `value: reject` → 同样在**解析阶段**拒答（2026-09-23 补齐） |
| 系统域名集 | ✅ 内置 `SYSTEM`（位 ④，在两条广告拦截之后） | ✅ 本仓快照 `apple_system.list`（缺两条 `PROCESS-NAME`；同位） |
| Apple 更新集 | ❌ 无（`Apple Update` 组**仅分流版有**；OTA 域名由 `SYSTEM` 接成 DIRECT） | ❌ 同左 |
| 远程 Apple 规则集 | ❌ 无（2026-09-24 删，只留内置 `SYSTEM`） | ❌ 无（Apple 流量部分由 `direct.txt` 兜住，`iCloud` 系走节点） |
| 内网两条 | ✅ `LAN`（内置）+ `private.txt` | ✅ `Lan.list` + `Private`（2026-09-23 补，与分流版同源同策略） |
| `.cn` 后缀兜底 | ❌ 无 | ❌ 无（2026-09-24 删：`direct.txt` 本身含 `DOMAIN-SUFFIX,cn`） |
| 内网规则位置 | 排在 `AI` 之前（2026-09-24 与 Egern 拉平） | `Lan` / `Private` 排在 `AI` 之前 |
| 默认出口 | `FINAL,Proxy,dns-failed` | `default` 规则 `policy: Proxy`（两侧都无 `Final` 中间组，2026-09-23 拉平） |
| 分组数 | 4 | 4 |
| 组的构成 | `Proxy` / `AI` / `AD` + 隐藏订阅槽位 `Airport` | 同左（`Airport` 为 `external` + `hidden: true`） |
| 本机占位节点（懒人版） | 2 条：`Node-A` → `Proxy`、`Node-B` → `AI` | 2 条同名同归属，协议同为 `hysteria2` |

分流版做过逐行对齐，**懒人版历史上没有** —— 2026-09-23 补齐三项（`dns.forward` 四层、`Private` 规则集、
`AI` 组的 `flatten: true`）并把 Egern 的兜底组 `Final` 整块移除（`default.policy` 直写 `Proxy`）；
**2026-09-24 补齐最后两处**：Surge 侧删 Apple 全量集并把内网段提前（两侧同为 10 条、同一顺序），
Egern 侧删 `domain_suffix: cn` 并补上系统域名集。
⇒ 现在改一侧懒人版**可以**假设另一侧同构，但改动仍要两边各写一次：同构指「位数与语义」，不指「字节」。

## 5 · 版本保留策略

- `profiles/` 顶层只有固定名四件 —— `routing` 分流版 + `lazy` 懒人版，各含带注释版与 `.min` 版；订阅地址就是这个永久文件名，升版不改名。
- 「当前是哪一版」只写在 profile 头注 `#! version=` 里；配置变动时，变动前的旧配置归档进 `profiles/config_old/`：归档版本号 = 该目录内此分工最新号的下一位（2026-09-29 起三段制 X.Y.Z：Z=小修、Y=中改、X=大改，每位满 10 进 1，4.0.10 合法；历史两段号不回改），完整版与 `.min` 成对，现役头注同步升为下一位；更早历史看 git（备份 tag：`pre-cleanup-20260927`）。

## 6 · 脚本与测试

| 能力 | Surge 脚本 | Egern 脚本 | 说明 |
|:-----|:-----------|:-----------|:-----|
| DNS 泄露审计 | `check_surge_dns.py` | `check_egern_dns.py` | 判据面不同，逐项见各脚本头注 |
| 地区组正则同步 | `audit_region_filters.py` | `audit_region_filters.py` | 同名同职责，各自解析自己的格式 |
| 分流覆盖实测 | `audit_routing_coverage.py` | `audit_routing_coverage.py` | 都用真实域名走一遍规则链 |
| 规则集内容审计 | `audit_ruleset_content.py` | `audit_ruleset_noresolve.py` | 同一坑（裸 IP 条目缺 `no-resolve`），Egern 侧另查域名条目总量 |
| `forward` 死代码/耦合审计 | — | `audit_dns_forward.py` | Egern 独有（`proxy_nameservers` 跳过 `forward` 所致） |
| 端点连通性探测 | — | `probe_doh.py` · `probe_dns_endpoints.py` | Egern 独有 |
| 规则集体量称重 | — | `weigh_ruleset.py` · `profile_ruleset.py` | Egern 独有 |
| 占位符 / 凭据扫描 | `check_secrets.py`（共享，全仓 `.conf` + `.yaml`） | 同左 | 节点必须是 RFC 5737 / example.com，凭据必须 `REPLACE_WITH_*` |
| 刷新参数审计 | `audit_ruleset_refresh.py` | `audit_ruleset_refresh.py` | **同名同职责、依据不同**：Surge 缺省 86400 仍刷新，Egern 缺省未文档化 |
| `.min` 生成与对拍 | `make_min.py` · `check_min_pair.py`（共享） | 同左 | 生成器与对拍器共用同一份规则 |
| 全仓链接与锚点 | `check_links.py`（共享） | 同左 | 相对链接 + 中文/emoji 锚点逐条可解析 |
| 换设备可移植性 | `check_portability.py`（共享） | 同左 | 行尾 / BOM / 命名 / 单机残留 |

以上检查由根目录 `.github/workflows/ci.yml` 在每次 push / PR 自动执行；本地手动跑同一组命令即可复现（见 [`skill/SKILL.md`](../../SKILL.md)）。

## 7 · 合并后共享的东西

- **图标**：全部 png 合并为根级 `icons/` 一份，两侧模板都指向这里；另附两个图标订阅 JSON（`icons.json` 纯本仓 · `icons-full.json` 大集成）。
- **许可与 LICENSE 文件**：两侧相同，共享一份。
- **规则集清单**：分流版 21 个远程规则集两侧**逐字共用**（同一批 URL，含两侧都注释掉的 `Proxy.list`）；
  Egern 另有 2 个独有项 —— `Lan.list`（补内置 `LAN`）与 `apple_system.list`（补内置 `SYSTEM`，本仓自托管）
  —— 见 [`rulesets.md`](rulesets.md)。
- **排序约束**：以 [`SKILL 门面`](../../SKILL.md) §2 的四条共同铁律 + 一条内核专属为准；逐条确认面见 [`rulesets.md`](rulesets.md) §4。

## 8 · 保持原样的差异

1. **加固清单项数不同**（Surge 14 项 / Egern 18 项）。两侧各有对方判据没覆盖到的面，
   保持各自原状，见 [`hardening-checklist.md`](hardening-checklist.md)。
2. **同一判据、两处不同取舍：加密 DNS 端点的写法。**
   Surge 侧 `encrypted-dns-server` 三条端点里有 2 条写的是**主机名**
   （`https://dns.google/dns-query` / `https://dns.alidns.com/dns-query`），会被引导解析一次；
   Egern 侧 `upstreams` 四条端点**全部 IP 字面量**，无引导解析。
   这**不是 Surge 侧的疏漏**：两侧模板头部各写明判据，Surge 侧在 profile 里显式挂了豁免
   （`# audit-waive: 1 加密 DNS 端点保留 2 个主机名形式`），换来的是 CDN 就近解析与 ECS 合规两项收益。
   移植时不应把"全 IP 字面量"当作硬指标 —— 先确认自己要不要那两项收益。
   审计器的豁免只把 finding 降级成 `WAIVED:` 并照常打印，不改判据本身；判据写在 profile 里，可 grep、可复核。
3. **规则集刷新参数**：Surge 官方文档写明 `RULE-SET` 缺省 `86400`、**负值才关闭自动更新**；
   Egern 官方只在示例里出现 `update_interval: 86400`，字段节未写缺省值 ⇒ 两侧都显式写死一周。
4. **换设备一致性**：仓根 [`.gitattributes`](../../../.gitattributes) 钉死 `* text=auto eol=lf`，
   优先级高于任何人本机的 `core.autocrlf`；`check_portability.py` 守行尾 / BOM / 命名。
   老克隆若磁盘仍是 CRLF 而 `git status` 干净，解法：`git rm -r --cached . && git reset --hard` 或重 clone。

---

相关：[`rulesets.md`](rulesets.md) · [`troubleshoot-faq.md`](troubleshoot-faq.md) · [`../skill/SKILL.md`](../../SKILL.md)
