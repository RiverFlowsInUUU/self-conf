# mihomo · 逐键语义与加固


## mihomo · 逐键语义（clash 侧）

> **何时读**：改 mihomo 配置需要确认某个键 / 组 / 规则 / 规则的语义与边界时。
> 本文件是 mihomo 侧的主文档，专讲 mihomo（原 Clash.Meta）侧
> Surge / Egern 两内核**没有**的机制。

> 面向想彻底弄明白「为什么这么写」的读者。
> 只想赶紧用起来 → 看 [`README`](../../../README.md) 的下载表（mihomo 一行是**两种形态**：静态 + 覆写脚本）。
>
> 目录
> [1 · 文件结构与两种交付形态](#1--文件结构与两种交付形态) ·
> [2 · 两种形态必须逐位一致](#2--两种形态必须逐位一致) ·
> [3 · 与 Surge / Egern 的机制差异](#3--与-surge--egern-的机制差异) ·
> [4 · 顶层键与 IPv6 双写](#4--顶层键与-ipv6-双写) ·
> [5 · 节点来源：proxies · proxy-providers](#5--节点来源proxies--proxy-providers) ·
> [6 · 节点入组的三件套：`use` / `include-all` / `include-all-proxies`](#6--节点入组的三件套use--include-all--include-all-proxies) ·
> [7 · Smart 三档倍率 fallback](#7--smart-三档倍率-fallback) ·
> [8 · 策略组全表与 `filter`](#8--策略组全表与-filter) ·
> [9 · rule-providers：三种 format × 三种 behavior](#9--rule-providers三种-format--三种-behavior) ·
> [10 · 规则集三级选型与自托管清单](#10--规则集三级选型与自托管清单) ·
> [11 · rules：两版顺序与排序约束](#11--rules两版顺序与排序约束) ·
> [12 · `no-resolve` 在 mihomo 侧的落点](#12--no-resolve-在-mihomo-侧的落点) ·
> [13 · `dns` 段：五个解析器键](#13--dns-段五个解析器键) ·
> [14 · 双层广告拦截的两个必要条件](#14--双层广告拦截的两个必要条件) ·
> [15 · `fake-ip-filter` 的通配语义](#15--fake-ip-filter-的通配语义) ·
> [16 · 已知取舍](#16--已知取舍) ·
> [17 · FAQ](#17--faq) ·
> [18 · 维护者须知](#18--维护者须知)

#### 1 · 文件结构与两种交付形态

```
self-conf/                                    # 三内核整合仓
├── clash/                                    # 本文档讲的这一侧
│   ├── profiles/                             # 静态 profile 四件
│   │   ├── routing.yaml · routing.min.yaml   # 分流版（带注释 / 纯配置）
│   │   └── lazy.yaml    · lazy.min.yaml      # 懒人版（带注释 / 纯配置）
│   ├── override/                             # 覆写脚本（第二种交付形态）
│   │   ├── my_clash.js                       # → 分流版结构
│   │   ├── my_clash_lazy.js                  # → 懒人版结构
│   │   └── README.md                         # 与静态模板的差别、用法、实测
│   ├── ruleset-sources.md                # 规则集清单与选型（门面层）
│   ├── （文档并入 skill/reference/profiles/clash.md）
│   ├── CHANGELOG.md
├── rules/                                    # 共享规则集真源（.list）+ 生成物（.yaml）
├── icons/                                    # 40 个图标 PNG + 1 个 SVG，三内核共用
└── skill/                                    # AI 知识库
    ├── AGENTS.md                            # Agent 入口（本仓根）（分歧 / 踩过的坑）
    ├── reference/profiles/{surge,egern,clash}.md · dns.md · rulesets.md · pitfalls.md · ops.md · gates.md
    ├── scripts/clash/build_rules.py          # .list → .yaml 生成器
    └── tests/clash/                          # mihomo 专属门禁 9 个
```

**两份 profile 是分工关系，不是版本关系**：

| | 分流版 `routing` | 懒人版 `lazy` |
|:--|:--|:--|
| 策略组 | **25** | **3**（`Proxy` / `AI` / `AD`） |
| 规则 | **27** | **11** |
| rule-providers | **25**（20 `.mrs` + 5 `.yaml`） | **10**（6 `.mrs` + 4 `.yaml`） |
| 取向 | 按应用 + 按地区细分 | 全量流量一个出口 |

选一份用，不要叠加。

#### 1.1 第二种交付形态：覆写脚本

这是 mihomo 侧**独有**的东西，Surge / Egern 都没有：

| 形态 | 给谁 | 怎么用 |
|:-----|:-----|:-------|
| 静态 `.yaml` | 下载即用的人 | 导入客户端 / 订阅这个文件的 raw 地址 |
| 覆写 `.js` | 想保留自己订阅的人 | 挂到**任意订阅**上，把订阅改造成同款结构 |

脚本做的事（`main(config)` 返回改写后的 config）：

| 段 | 处理 |
|:---|:-----|
| `proxies` | **保留**（订阅的节点原样） |
| `proxy-groups` | **整体替换** |
| `rule-providers` | **整体重建**（`config["rule-providers"] = {}` 先清空，避免残留无用 provider 与命名冲突） |
| `rules` | **整体替换** |
| `dns` | **整体替换**（含双层广告拦截） |
| `ipv6` | 显式置 `false` |
| 入站端口（`port` / `mixed-port` / `dns.listen`） | **不覆盖**，交给客户端决定 |

> ⚠️ 脚本**不设** `dns.listen`。早期版本写死 `0.0.0.0:7874`，会与客户端自身的 DNS 端口冲突
> （官方默认值为空，即不监听）。详见 §18.3。

#### 1.2 两形态的结构差：不是同一套数字

脚本与静态模板**不是**逐组相同 —— 差一处，且是有意的（§7）：

| | 静态 `routing.yaml` | 脚本 `my_clash.js` |
|:--|:--|:--|
| 策略组 | 25 | **22** |
| 规则 | 27 | 27 |
| rule-providers | 25 | 25 |
| 规则集 URL 集合 | 25 个 | 同一个 25 个 |

差的三个组是 `Low Mult.` / `Auto` / `High Mult.` —— 模板专属的三档子组，脚本侧
`Smart` 是单组 `fallback`。

懒人版则**完全同构**：脚本 3 组 / 11 条 / 10 份，与 `lazy.yaml` 逐位相同。

> ✅ 头注数字**已全部更正**（2026-10-07）：`routing.yaml` 为「25 组 / 25 份 / 27 条」、
> `my_clash.js` 为「22 组 / 25 份 / 27 条」、`my_clash_lazy.js` 为「3 组 / 10 份（6 MRS + 4 yaml）/ 11 条」，
> 均由 `check_header_numbers.py` 与脚本实际输出对拍守着 —— 见 §18.4。

#### 2 · 两种形态必须逐位一致

#### 2.1 为什么需要这条判据

静态文件与覆写脚本是**同一套配置**的两种交付形态。一旦漂移，用户会遇到：

> 「照文档用脚本订阅，效果跟直接导入配置文件不一样」

**而且两边都能正常跑、都不报错** —— 没有任何一个环节会提示你。这种漂移只能靠对拍发现。

这是本仓特有的一条判据：姊妹仓 `Self-Configuration` 的 Surge / Egern 侧
只有「完整版 ↔ .min 版」的对拍，没有「脚本 ↔ 静态」这一层。

#### 2.2 判据（`skill/tests/clash/check_script_sync.py`）

以**空订阅**（无 `proxies`、无 `proxy-providers`）执行脚本，取其输出与静态 profile 比对：

| 对象 | 判据 |
|:-----|:-----|
| `rules` | **逐位相等**（数组顺序也算） |
| `rule-providers` | **URL 集合相等**（键名可差，取 `url` 比） |
| `proxy-groups` | 脚本组 ∪ 模板专属组 ⊇ 静态组；其余组（非模板专属）的 `proxies` 成员表相等 |
| `dns` | 除 `listen` 外**逐键相等** |
| `ipv6` | 相等 |

两处白名单：

| 白名单 | 内容 | 为什么 |
|:-------|:-----|:-------|
| `TEMPLATE_ONLY_GROUPS` | `Low Mult.` / `Auto` / `High Mult.` | 模板能用 `filter` 在运行时分档，脚本做不到 |
| `EXPECTED_DIFF` | `Smart` —— 「模板三档 fallback vs 脚本单组 fallback」 | **命中则打印提醒但不判负** |
| `SKIP_DNS_KEYS` | `listen` | 交给客户端决定 |

#### 2.3 「打印但不判负」的分寸

`Smart` 是唯一一处**已知且有意**的差异。脚本跑完会打印：

```
     ~ 已知差异 Smart: 模板三档 fallback vs 脚本单组 fallback（机制差异，非漂移）
  OK override/my_clash.js
  OK override/my_clash_lazy.js
```

⚠️ 这条提醒必须**保留可见**。它若被静默吞掉，后来者会把「脚本侧没有三档」当成漏写，
于是去改脚本 —— 而那是改不动的（§7.2）。

#### 2.4 与「.min 对拍」是两条独立的判据

| 门禁 | 比对 | 判据 |
|:-----|:-----|:-----|
| `check_min_pair.py` | `routing.yaml` ↔ `routing.min.yaml`（`lazy` 同） | YAML 解析成对象后**直接比对象**，任何一处不同即判负 |
| `check_script_sync.py` | `my_clash.js` ↔ `routing.yaml`（`lazy` 同） | 见 §2.2 |

> `.min` 的定位是「**同一份配置去掉注释**」，不是「裁剪配置」。
> 本仓踩过：`routing.yaml` 由脚本重新生成后忘了同步重生成 `.min`，两份就不一致，
> 而静态文件**不会报错**。

两套判据都跳过注释 / 键序 / 缩进 / 引号风格 —— YAML 解析后比对象，
所以「改了个引号」不会被判负，「改了个值」才会。

#### 3 · 与 Surge / Egern 的机制差异

三内核共用 `rules/` 与 `icons/`，但机制差异决定了**不能互相照搬写法**。
完整对照见 [`rulesets.md`](../rulesets.md)（Surge ↔ Egern），
本表补 mihomo 这一列：

| 语义 | Surge | Egern | **mihomo** |
|:--|:--|:--|:--|
| 配置载体 | `.conf` INI 分段 | `.yaml` | `.yaml` |
| 本地 DNS | `dns-server = a, b` | `dns.bootstrap` / `dns.upstreams` | **`default-nameserver`（必须纯 IP）+ 四个分流键**（§13） |
| 加密 DNS | `encrypted-dns-server` | `dns.upstreams.<组名>` | **`nameserver` / `fallback` / `direct-nameserver` / `proxy-server-nameserver`** |
| 代理侧解析 | 无独立键 | `dns.proxy_nameservers` | **`proxy-server-nameserver`**（`respect-rules: true` 时**强制要求**，缺了直接报错） |
| 接管明文 53 | `hijack-dns = 8.8.8.8:53, …`（列清单） | `hijack_dns: ['*']`（通配） | **`tun.dns-hijack: any:53`**（不写协议前缀时默认 `udp://`） |
| Fake-IP | `fake-ip` 默认对代理域名 | 同 | **`dns.enhanced-mode: fake-ip` + `fake-ip-range`** |
| 不解析 | `no-resolve`（规则行尾） | `no_resolve: true`（仅 geoip/ip_cidr/ip_cidr6/asn 四类生效） | **`no-resolve`（规则行尾）**，行为与 Surge 同 |
| 远程规则集 | `RULE-SET,<URL>,<策略>`（URL 直接写在规则里） | `- rule_set: {match, policy}` | **`rule-providers` 先声明（带 `format` / `behavior` / `path`），`rules` 里按名字引用** |
| 刷新间隔 | `update-interval=604800` | `update_interval: 604800` | **`interval: 86400`**（§10.3） |
| 规则集格式 | `.list` | `.list` | **`.mrs` / `.yaml` / 文本**（§9） |
| 地理判定 | `GEOIP,CN,…`（内置 mmdb） | `- geoip: {match: CN}` | **`GEOIP` / `GEOSITE` 或等价的 `.mrs` 远程集**（本仓选后者，§10.2） |
| 订阅源 | `Airport` external 组 + `policy-path` | `Airport` external 组 + `hidden` | **`proxy-providers` 具名槽位 + `use`**（§5、§6） |
| 组展开 | `include-other-group="X"` | `flatten: true` | **无对应物** —— 靠 `use` / `include-all` 或把组名写进 `proxies` |
| 组内正则筛选 | `policy-regex-filter`（**对显式成员无效**） | `filter` | **`filter` / `exclude-filter`**（作用于合并后的成员列表，§6.3） |
| 自动选优组 | `smart`（首字节延迟 + TCP 重传率 + UDP 延迟，按站点记忆） | `smart` | ❌ **没有 `smart` 类型** —— 只有 `select` / `url-test` / `fallback` / `load-balance` |
| 倍率分档 | `policy-priority` 权重 | `policy-priority` 权重 | ❌ **无权重机制** —— 模板靠 `filter` 分三档（§7） |
| 兜底 | `FINAL,<组>,dns-failed` | `- default: {policy: <组>}` | **`MATCH,<组>`**（无 `dns-failed` 参数） |
| 解析阶段拒答 | `REJECT,pre-matching,extended-matching` | `dns.forward` 里 `value: reject` | **`nameserver-policy` 的 `rcode://success`**（§14） |
| 广告拦截落点 | 规则层，指向**字面量 `REJECT`**（`pre-matching` 要求字面量） | 规则层指向 `AD` 组 | **规则层指向 `AD` 组 + DNS 层 `rcode://success`（双层）** |
| 第二种交付形态 | ❌ 无 | ❌ 无 | ✅ **覆写脚本**（§1.1） |
| IPv6 关闭 | `ipv6 = false` + `ipv6-vif` | `ipv6: false` | **顶层 `ipv6: false` + `dns.ipv6: false`（两处，§4）** |

> ⚠️ 最容易误判的一条：**地区组的倍率分档**。
> 模板能用 `filter` 在运行时分档，脚本在订阅加载时执行一次、看不到 provider 节点名
> ⇒ 脚本侧是单组 fallback。`check_script_sync.py` 把它列为**已知差异**，打印提醒但不判负。
> 这不是漂移，是内核机制决定的。

> ⚠️ 第二条易误判：mihomo 的 `Airport` 是 `proxy-providers` 里的一个**具名槽位**，
> 不是 `proxy-groups` 里的一个组。Surge / Egern 侧它是**隐藏的策略组**。
> 把它当成「组」写进 `proxies` 会变成悬空引用（门禁 ① 会拦）。

#### 4 · 顶层键与 IPv6 双写

#### 4.1 顶层键清单

两份 profile 的顶层键完全相同（`routing` 与 `lazy` 只是顺序略有差别）：

```yaml
ipv6: false          # ← 第 ① 处
proxies: []          # 节点（空；节点来自订阅）
proxy-providers:     # 订阅槽位 Airport
proxy-groups:        # 策略组
rule-providers:      # 规则集
rules:               # 分流规则
dns:                 # DNS（含 ipv6: false ← 第 ② 处）
tun:                 # 流量接管 + :53 劫持（泄露面③）
```

#### 4.2 IPv6 必须关两处

| 处 | 键 | 作用 |
|:-:|:--|:-----|
| ① | 顶层 `ipv6: false` | 内核不处理 IPv6 流量本身 |
| ② | `dns.ipv6: false` | `AAAA` 查询由内核直接回**空应答**，不往外发 |

**只关一处会漏**：

- 只关 ①：DNS 仍在应答 `AAAA`，应用拿到地址后尝试建连，行为取决于系统栈；
- 只关 ②：`AAAA` 不回，但 IPv6 通路还在，本机真实 IPv6 可能**绕过 TUN 直接出网**
  ⇒ 站点测到的出口 IP 与节点不符。

两处都关，双栈站点一律回落 IPv4，封堵面与 Surge / Egern 两侧等效（两侧也都是显式关闭）。

判据由 `skill/tests/clash/check_structure.py` 的 ④ 守着：

```python
if c.get("ipv6") is not False:      errs.append("顶层 ipv6 未显式关闭")
if dns.get("ipv6") is not False:    errs.append("dns.ipv6 未显式关闭")
```

⚠️ 注意是 `is not False`，不是「未设置」—— 写成 `ipv6: no` / `ipv6: "false"` 都会被判负。
`false` 必须是布尔真值，不是字符串。

#### 4.3 `proxies: []` —— 空段是有意的

两份 profile 的 `proxies` 都是空数组，节点全部来自 `Airport` 订阅。
理由写在 `lazy.yaml` 头注里：**只填一个订阅 URL 即可导入，不需要手工补节点**。

> 如果你有自己的固定节点，直接写进 `proxies`，它们与订阅节点合并进各组。
> 节点 `server` 写 IP 字面量 ⇒ 不产生「解析节点域名」这一次查询（出口 ③，见
> [`clash.md`](../profiles/clash.md) §2.3）。

#### 5 · 节点来源：`proxies` · `proxy-providers`

#### 5.1 `proxy-providers`：订阅槽位

两份 profile 各有一个具名槽位 `Airport`：

```yaml
proxy-providers:
  Airport:
    type: http
    url: https://sub.example.com/api/v1/client/subscribe?token=REPLACE_WITH_YOUR_TOKEN
    path: ./proxy_provider/Airport.yaml
    interval: 86400
    health-check:
      enable: true
      url: https://www.gstatic.com/generate_204
      interval: 300
```

| 键 | 值 | 为什么 |
|:--|:--|:-------|
| `type` | `http` | 远程订阅 |
| `url` | 占位地址 | ⚠️ **导入前必须换成自己的订阅**，否则所有走代理的流量不通 |
| `path` | `./proxy_provider/Airport.yaml` | **先落盘再解析** —— 刷新失败时沿用本地副本，不会因为一次网络抖动丢掉全部节点 |
| `interval` | `86400` | 24 小时拉一次 |
| `health-check` | 开，300 秒 | 见下 |

> 🔎 **为什么要给 provider 单独开 `health-check`**：官方文档写明，策略组的 `url`
> 健康检查**只会检查 `proxies` 字段的代理，不会检查通过 `use` 引入的代理集合**。
> 而 `Proxy` 组的 `proxies` 是空的（节点全靠 `use`）⇒ 组级测速对象为零。
> 面板上的延迟读数因此由 **provider 自带的 `health-check`** 承担。
> 这也是懒人版 `Proxy`（`url-test` + `use: [Airport]` + `proxies: []`）能正常显示延迟的原因。

#### 5.2 占位符与脱敏

本仓是公开模板，**所有节点信息都是占位符**。判据由 `skill/tests/clash/check_secrets.py` 守：

| 字段 | 占位形式 |
|:-----|:---------|
| 订阅地址 / token | `sub.example.com` · `REPLACE_WITH_YOUR_TOKEN` |
| 凭据 | `REPLACE_WITH_*` |
| 节点 IP | RFC 5737 文档段（`192.0.2.0/24` · `198.51.100.0/24` · `203.0.113.0/24`） |

扫描范围是 `.js` / `.yaml` / `.yml` / `.md` / `.conf` / `.list` / `.txt` / `.json`
（跳过 `.git` / `node_modules` / `__pycache__` / `icons`）。

> 🔧 **整合仓特有的一条白名单**：`198.18.0.1`（fake-ip 段，RFC 6815 保留段）会被
> Surge / Egern 侧的 secrets 扫描判为「真实 IP」—— 那是 mihomo 的**合法保留段**，
> 但另两个内核不认识。整合时给它加了白名单。
> ⇒ 这类「各内核的常识不同」是合并必须处理的，不是误报。

#### 6 · 节点入组的三件套：`use` / `include-all` / `include-all-proxies`

这是 mihomo 最容易写错的一组键，三者**不是别名**：

| 键 | 引入什么 | 顺序 |
|:--|:---------|:-----|
| `use: [Airport]` | **指定名字的** proxy-provider（可多个） | 按 provider 内顺序 |
| `include-all-proxies: true` | 所有 `proxies` 段里的**内联节点** | **按名称排序** |
| `include-all: true` | 所有 `proxies` **+ 所有** proxy-providers | **按名称排序** |
| `include-all-providers: true` | 所有 proxy-providers | **按名称排序** |

#### 6.1 坑一：`include-all` 会覆盖 `use`

官方字段说明里 `include-all` = 引入**所有出站代理以及代理集合**。
所以一旦写了 `include-all: true`，`use` 指定的那一个 provider **也会被它包进去** ——
`use` 就变成了空转。

- 只有**一个** provider 时两者等价，看不出区别；
- 日后加了第二个 provider、又只想用其中一个，就必须**去掉 `include-all`、只留 `use`**。

这条已写进 `lazy.yaml` 策略组段的注释里。

#### 6.2 坑二：`include-all-proxies` 看不到 provider 里的节点

名字里有 `proxies`，它就**只**引入 `proxies` 段的内联节点。
订阅转换后的常见形态是「节点都放进 `proxies`」，此时 `include-all-proxies` 正好；
但如果订阅额外带了 `proxy-providers`，**那些节点会成为孤儿** —— 没有任何组引入它们。

覆写脚本对这个坑的处理（两份脚本同款）：

```js
const HAS_PROVIDERS =
  config["proxy-providers"] && Object.keys(config["proxy-providers"]).length > 0;
const ALL_KEY = HAS_PROVIDERS ? "include-all" : "include-all-proxies";
const allNodes = {};
allNodes[ALL_KEY] = true;
```

⇒ 「有 provider 就用 `include-all`，否则用 `include-all-proxies`」—— 这是**运行时判断**，
静态模板做不到（它只有一个 provider，所以直接 `include-all` 或 `use` 都行）。

#### 6.3 坑三：`filter` 作用于**合并后**的成员列表

按内核 `groupbase.go` 的 `GetProxies`，`filter` / `exclude-filter` 作用于
**最终合并后的成员列表** —— 也就是说，由 `include-all-proxies` / `use` 引入的节点**同样被筛**。

这正是地区组「不写成员表、只写 `filter`」能成立的原因（§8.3）。

对比 Surge：Surge 的 `policy-regex-filter` **对显式列在 `[Proxy Group]` 里的成员不生效**，
要让它生效必须同时开 `include-all-proxies=true`。**两内核这条规则正好相反**，移植时务必重查。

#### 6.4 两个筛选键的分工

| 键 | 方向 | 本仓用途 |
|:--|:-----|:---------|
| `filter` | 正向保留 | 地区组按节点名筛地区；`Smart` 三档按倍率筛 |
| `exclude-filter` | 反向排除 | 排掉机场常见的「剩余流量 / 套餐到期 / 官网」信息节点 |
| `exclude-type` | 按**节点类型**排除 | 本仓不用。⚠️ 官方明示它**不支持正则**（用 `|` 分割），且**仅作用于 `proxies` 字段引入的节点** |

`exclude-filter` 的取值（两份配置与两份脚本共用同一份口径）：

```
剩余|流量|到期|过期|官网|订阅|重置|续费|Traffic|Expire|GB
```

> 信息节点不可用，若不排除会进入 `url-test` 测速池、污染择优结果。
> 实测（含信息节点的模拟订阅）：3 个信息节点全部被排除。

#### 7 · Smart 三档倍率 fallback

> 🧠 这是**模板专属**结构，脚本侧没有。分流版才有（`lazy` 的 `Proxy` 是单组 `url-test`）。

#### 7.1 结构

```
Proxy (select)
  └── Smart (fallback)  ← 依次回落，不是择优
        ├── Low Mult.   (url-test, hidden)  ← 倍率 < 1 的节点（0.01 / 0.1 / 0.5 …）· 最省钱，优先
        ├── Auto        (url-test, hidden)  ← 正常倍率节点（节点名无倍率标记）
        └── High Mult.  (url-test, hidden)  ← 倍率 > 1 的节点（1.5倍 / 2倍 / 3.0x …）· 最贵，兜底
```

三个子组都是 `include-all: true` + `filter` + `hidden: true` ——
**成员表是空的**，全靠 `filter` 在运行时从全池里筛。

#### 7.2 为什么脚本做不到

| | 静态模板 | 覆写脚本 |
|:--|:---------|:---------|
| 分档时机 | **运行时**（`filter` 每次求值时筛） | 生成期（脚本执行一次） |
| 能看到节点名吗 | 能（provider 已加载） | **不能** —— 脚本在订阅加载时跑，`proxies` 里还没有 provider 的节点 |
| 结果 | 三档，倍率语义化 | 单组 `fallback`，成员顺序由 `sortedByRate` 按名排出 |

脚本侧的替代方案（`my_clash.js`）：

```js
function rateOf(name) {
  var m = String(name || "").match(/(?:^|[^\d.])(0\.\d*[1-9])/);
  return m ? parseFloat(m[1]) : null;
}
function sortedByRate(names) { /* 低倍率在前，无倍率排最后，同倍率保持订阅原顺序 */ }
// Smart 的 proxies = sortedByRate(usable)
```

⇒ **脚本只能排序，不能分档。** 而且它的 `rateOf` 只认低倍率（`0.` 开头），
抓不到「高倍率」那一档 —— 高倍率节点在脚本侧混在「无倍率」里排最后。
模板侧三档把这两种语义**显式分开**，这是二者真正的差距。

#### 7.3 倍率判据（消歧靠「倍率单位」）

| 档 | 判据 | 例 |
|:--|:-----|:---|
| 低倍率 | `0.xxx` —— 以 `0.` 开头、末位非零、前面不紧跟数字或小数点 | 「0.1倍」「0.1倍率」「0.1x」「0.5」✅；「香港 01」「1.5GB」「剩余流量」❌ |
| 高倍率 | 数值 ≥ 1 且**必须紧跟** `倍` / `倍率` / `x` / `X` / `*` | 「巴西 09 2倍」✅；序号「09」❌ |
| 其余 | 视为无倍率标记 → `Auto` | — |

三条正则（`routing.yaml`）：

```yaml
Low Mult.  : '^(?=.*(?:^|[^\d.])(0\.\d*[1-9]))((?!直连|DIRECT).)*$'
Auto       : '^(?!.*(?:^|[^\d.])(0\.\d*[1-9]))(?!.*(?:^|[^\d.])([1-9]\d*(?:\.\d+)?\s*(?:倍率|倍|x|X|\*)))((?!直连|DIRECT).)*$'
High Mult. : '^(?=.*(?:^|[^\d.])([1-9]\d*(?:\.\d+)?\s*(?:倍率|倍|x|X|\*)))((?!直连|DIRECT).)*$'
```

三者各带同一份 `exclude-filter`（§6.4）。18 例回归测试全通过。

> ⚠️ `Auto` 那条是**双负向断言**（既不含低倍率、也不含高倍率）——
> 它是「剩下的一档」，不是「默认的一档」。改动任一条正则时，`Auto` 必须同步改，
> 否则一个节点可能同时进两档或一档都不进（两档都不进 ⇒ 它在 `Smart` 里彻底消失）。

#### 7.4 `fallback` 与 `url-test` 的语义差

| 类型 | 语义 |
|:--|:-----|
| `url-test` | **择优** —— 定时测速，选延迟最低的（带 `tolerance: 50`，差距在 50 ms 内不换） |
| `fallback` | **回落** —— 按成员顺序取第一个可用的，**不比较延迟** |

⇒ `Smart` 用 `fallback` 是刻意的：**三档之间有明确优先级（省钱优先），不该按延迟打断这个顺序**；
档内才是 `url-test` 择优。

#### 8 · 策略组全表与 `filter`

#### 8.1 分流版 25 组

| 层 | 组 | 类型 | 成员 | 说明 |
|:---|:---|:----:|:-----|:-----|
| ① 总入口 | `Proxy` | `select` | `Smart` · 6 地区组 · `Other Regions` | 手动总出口，首项 `Smart` |
| ② 自动 | `Smart` | `fallback` | `Low Mult.` · `Auto` · `High Mult.` | §7 |
| ② 隐藏档 | `Low Mult.` / `Auto` / `High Mult.` | `url-test` | （空）+ `include-all` + `filter` | `hidden: true` |
| ③ AI | `ChatGPT` / `Gemini` | `select` | `United States` · `Taiwan` · `Japan` · `Singapore` | 美国优先 |
| ③ AI | `Claude` | `select` | `Taiwan` · `Japan` · `Singapore` · `United States` | 台湾优先（Claude 对台湾线路友好） |
| ③ AI | `AI` | `select` | `Smart` · `Taiwan` · `Japan` · `Singapore` · `United States` | 通用 AI 兜底 |
| ④ 媒体 | `YouTube` / `Emby` / `Telegram` / `Twitter` | `select` | `Smart` + 港 · 台 · 日 · 新 · 美 | 通用型，首项 `Smart` |
| ④ 媒体 | `YouTube Music` / `Spotify` | `select` | `United States` · 港 · 台 · 日 · 新 | **美国优先**（解锁地区） |
| ④ 开发 | `Google` | `select` | `Gemini` · `Smart` + 5 地区 | 首项是 `Gemini` 组 ⇒ 「Google 走 Gemini 链路」 |
| ⑤ 系统 | `Microsoft` | `select` | **`DIRECT`** · `Proxy` | 微软国内可直连，走代理反而慢 |
| ⑤ 系统 | `Apple Update` | `select` | **`DIRECT`** · `REJECT` | OTA 默认放行（早期版本是 `REJECT, PASS, DIRECT`，等于默认拒绝，下不动更新） |
| ⑤ 开关 | `AD` | `select` | **`REJECT`** · `DIRECT` | 广告拦截开关（§14.3） |
| ⑥ 地区 | `Hong Kong` / `Taiwan` / `Japan` / `Singapore` / `United States` | `url-test` | （空）+ `include-all` + `filter` | 按节点名筛 |
| ⑥ 地区 | `Other Regions` | `url-test` | （空）+ `include-all` + 负向 `filter` | 收尾，接住落单节点 |

> 📌 `Proxy` 的成员表**包含** `Other Regions` —— 它保证任何节点都不会因为
> 六个地区关键词全不匹配而变成孤儿。

#### 8.2 懒人版 3 组

```yaml
Proxy: url-test, proxies: [], use: [Airport]                       # 全池自动择优
AI   : select,   proxies: [Proxy], use: [Airport]                  # 默认随 Proxy，可手动钉
AD   : select,   proxies: [REJECT]                                 # 单成员，不留放行的口子
```

| 组 | 为什么这么写 |
|:--|:-------------|
| `Proxy` | `url-test` 近似 Surge 的 `smart`。⚠️ mihomo **没有 `smart` 类型、也没有节点权重机制**，只能纯延迟择优 |
| `AI` | `select` 手动钉死 —— 自动测速会让出口 IP 在订阅池里漂移，而 Google / OpenAI 的账号风控对出口频繁跳变极敏感 |
| `AD` | 单成员 `REJECT`（与姊妹仓懒人版同口径）。分流版才是 `REJECT` / `DIRECT` 二选一 |

> ⚠️ `AI` 的成员表**同时**有 `proxies: [Proxy]`（组名可当成员）和 `use: [Airport]`
> —— 前者是「默认随主出口」，后者是「面板上能手动挑具体节点」。两者并存不冲突。

#### 8.3 地区组靠 `filter` 筛，不写成员表

```yaml
- name: Hong Kong
  type: url-test
  include-all: true
  filter: '(?=.*(港|HK|(?i)Hong))^((?!(台|日|韩|新|美)).)*$'
  url: https://www.gstatic.com/generate_204
  interval: 300
  tolerance: 50
```

两条断言叠在一起：

- `(?=.*(…))` —— 正向：节点名里**有**本地区关键词；
- `^((?!(…)).)*$` —— 负向：整串里**没有**其它地区的关键词。

负向那半是必须的：「深港 01」这种中转节点同时含「港」和其它地区词，
只看正向会同时进两个地区组。

`Other Regions` 是**纯负向**：把 5 个地区组的关键词抄了一遍（外加机场城市码
`LAX` / `SJC` / `SFO` / `NRT` / `HND` …）+ 信息节点词，全部排除后剩下的收进来。

> ⚠️ 这份「抄一遍」是**结构上消灭不掉的拷贝**（`filter` 只吃字面正则、不支持变量）。
> 姊妹仓的兜底做法是**给拷贝配一个比对器**（`audit_region_filters.py`）。
> mihomo 侧**已有**这个比对器（`skill/scripts/clash/audit_region_filters.py`，2026-10-07 补）——
> 改地区正则时两侧各自六处，由它判一致，见 §18.2。

#### 8.4 `hidden: true` 只用于三档子组

三个倍率子组（`Low Mult.` / `Auto` / `High Mult.`）都带 `hidden: true` ——
它们是 `Smart` 的内部实现，不该出现在面板上让人手动选。

`Airport` 在 mihomo 侧是 `proxy-providers` 里的槽位，本来就不是一个组，
所以**没有** Surge / Egern 侧那个 `hidden=true` 的订阅组。

#### 9 · rule-providers：三种 format × 三种 behavior

Surge / Egern 只有一种规则集载体（`.list`，URL 直接写在规则行里）。
mihomo 要**先声明再引用**，声明时有两个关键字段：

```yaml
rule-providers:
  cn:
    type: http
    behavior: domain        # ← 怎么匹配
    format: mrs             # ← 文件什么格式
    url: https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo/geosite/cn.mrs
    path: ./rule_provider/cn.mrs
    interval: 86400
```

#### 9.1 `format`：三种

| format | 内容形态 | 优点 | 缺点 |
|:-------|:---------|:-----|:-----|
| `mrs` | mihomo **二进制**规则集（zstd 压缩，文件头 `28 b5 2f fd`） | 省流量、解析快 | 可读性差（要看内容得先转回文本） |
| `yaml` | `payload:` 下列规则行 | 可读、可 diff | 体积大 |
| 文本 | 一行一条规则 | 最简单 | 无结构 |

官方：`format` 可选 `yaml` / `text` / `mrs`，**默认 `yaml`**。

> 🔧 转换工具：`mihomo convert-ruleset domain/ipcidr yaml/text XXX.yaml XXX.mrs`

#### 9.2 `behavior`：三种

| behavior | 匹配方式 | 内容要求 |
|:---------|:---------|:---------|
| `domain` | 只做**域名**匹配 | 纯域名清单 |
| `ipcidr` | 只做 **IP 段**匹配 | 纯 IP-CIDR 清单 |
| `classical` | 走**完整规则语法**（`DOMAIN-SUFFIX,xxx` / `DOMAIN-KEYWORD,xxx` …） | 完整规则行 |

> ⚠️ **`format: mrs` 的 `behavior` 只支持 `domain` / `ipcidr`**（官方明示）。
> 想要 `classical` 语义就得用 `yaml` 或文本格式 —— 本仓 5 份 `classical` 集**全部**是 `format: yaml`，
> 这不是巧合，是 format 的能力边界决定的。

#### 9.3 本仓的实际组合

分流版 25 份：

| format × behavior | 份数 | 例 |
|:--|:-:|:--|
| `mrs` + `domain` | **16** | `apple-update` · `spotify` · `private` · `anthropic` · `category-ai-chat-!cn` · `github` · `youtube` · `google` · `microsoft` · `apple-cn` · `telegram` · `twitter` · `cn` · `openai` · `google-gemini` · `AWAvenue-Ads` |
| `mrs` + `ipcidr` | **4** | `geoip-private` · `geoip-google` · `geoip-telegram` · `geoip-cn` |
| `yaml` + `classical` | **5** | `Jinx-CN` · `Jinx-Ads` · `emby` · `AI_Domains` · `apple-system` |

懒人版 10 份：

| format × behavior | 份数 | 例 |
|:--|:-:|:--|
| `mrs` + `domain` | **4** | `private` · `cn` · `category-ai-chat-!cn` · `AWAvenue-Ads` |
| `mrs` + `ipcidr` | **2** | `geoip-private` · `geoip-cn` |
| `yaml` + `classical` | **4** | `Jinx-CN` · `Jinx-Ads` · `AI_Domains` · `apple-system` |

> ⚠️ `lazy.yaml` 头注写的是「5 份 MRS + 5 份 yaml」，实际是 **6 mrs + 4 yaml**（§18.4）。

#### 9.4 `behavior` 选错的后果

选错**不报错**，只是静默失配：

- `domain` 集合里混了 `DOMAIN-SUFFIX,xxx` 这种完整规则行 ⇒ 每行被当成一个**域名**，
  永远匹配不上 ⇒ 整份集变成空集；
- `classical` 写成 `domain` ⇒ 同上；
- `ipcidr` 集合里混了域名 ⇒ 域名不是合法 CIDR，整份集解析失败或退化成空集。

⇒ 判据：**先落一份样本看内容形态，再定 `behavior`**，不要照抄别人的配置。
`ruleset-sources.md` §0.1 记过一次这类纠偏（「Gemini / Claude 没有独立类别」是错的）。

#### 9.5 `path` 与 `interval`：为什么必须给

| 键 | 值 | 含义 |
|:--|:--|:-----|
| `path` | `./rule_provider/<文件名>` | **先落盘再解析** —— 刷新失败时沿用本地副本，不会因为一次网络抖动丢掉全部规则 |
| `interval` | `86400` | 24 小时刷新一次 |

两者都给 ⇒ 节点侧**不依赖在线下载**，离线重启也能起来。

> ⚠️ 死链的后果不是报错，是**静默降级**：rule-provider 拉不到就变成空集，
> 该走 `AD` 的广告全进了兜底出口，配置看着跑得挺好，其实拦截没了。
> 本仓踩过：Jinx 上游把 `*-white-guard.*` 改名成 `*-direct.*`，脚本里那条 URL 就此 404，
> **懒人版一直挂着死链没人察觉** —— 因为当时没有 CI 定期问「这个 URL 还活着吗」。
> ⇒ `skill/tests/clash/check_remote_urls.py` 就是那次之后加的（慢，按需跑）。

#### 10 · 规则集三级选型与自托管清单

#### 10.1 三级优先

两份配置统一按这一条原则选规则集：

| 层级 | 手段 | 何时用 |
|:----:|:-----|:-------|
| ① | **`GEOSITE` / `GEOIP`**（内核数据库） | 首选 —— 不挂远程、最快、最省流量 |
| ② | **内联 `DOMAIN-SUFFIX`** | 数据库确实没有的类别，用一条字面规则补上 |
| ③ | **远程规则集**（`rule-providers`） | 需要自定义清单（白名单 / 广告拦截 / 数据库缺的类别）时才挂 |

#### 10.2 一次转向：从原生 `GEOSITE` 改成远程 `.mrs`

分流版的历史形态是 17 条 `GEOSITE,xxx` / `GEOIP,xxx` 原生规则
（对应层级 ①）。后来**全部改成 `RULE-SET,xxx` 远程 `.mrs`**（层级 ③），
新增 13 份 geosite `.mrs` + 4 份 geoip `.mrs` 的 provider 定义。

现在的分流版 `rules` 里**没有一条** `GEOSITE` / `GEOIP` 字面规则 ——
25 份远程集全部走 `RULE-SET`。

⚠️ 因此 §10.1 的「三级优先」描述的是**选型思想**，不是当前文件的字面形态。
当前形态是「远程 MRS 为主 + 5 份自定义 classical + 1 条内联」。
这条差异也写进了 [`rulesets.md`](../rulesets.md) §1.3。

#### 10.3 `interval: 86400`（一天）

mihomo 侧所有远程规则集统一 `interval: 86400`。

> ⚠️ **这与姊妹仓的 604800（一周）不一致，是刻意的**：
> 两内核的键语义与缺省值都不同（Surge 官方写明 `RULE-SET` 缺省 86400、只有**负值**才关闭自动更新；
> Egern 缺省值未文档化）。本仓 mihomo 侧按自己的节奏钉一天，不强行对齐。

#### 10.4 本仓自托管清单（`rules/`，全部 `format: yaml` + `classical`）

| 文件 | 条数 | 去向 | 真源 |
|:-----|:----:|:-----|:-----|
| `emby.yaml` | **4** | `Emby` | `rules/emby.list` |
| `apple_system.yaml` | **18** | `DIRECT` | `rules/apple_system.list` |
| `AI_Domains.yaml` | **272** | `AI` | `rules/AI.list` |

**`.list` 是唯一真源**，`.yaml` 由脚本生成：

```bash
python skill/scripts/clash/build_rules.py           # 生成
python skill/scripts/clash/build_rules.py --check   # CI 用：过期即判负
```

> ❌ **不许手工编辑 `rules/*.yaml`** —— 它们是生成物，改了会被下次生成覆盖。
> 此前各内核各存一份（emby 4 / apple_system 18 / AI 272 条，逐条相同），双份维护
> ⇒ 单一真源后**物理上不可能漂移**。这是三仓合并最直接的收益之一。

三份都是**纯域名集、零 IP 条目** ⇒ 引用方**不写**规则级 `no-resolve`（§12）。

#### 10.5 唯一一条内联规则：`music.youtube.com`

`geosite.dat` 没有独立的 ytmusic 类别，而 `music.youtube.com` 是 `youtube.com` 的**子域**
—— 会被排在后面的 `RULE-SET,youtube,YouTube` 抢先命中。所以必须在它**之前**单独摘出来：

```yaml
- DOMAIN-SUFFIX,music.youtube.com,YouTube Music     # 位 13
- RULE-SET,youtube,YouTube                          # 位 15
```

它不依赖任何远程清单的新鲜度：YouTube Music 的入口域名是稳定的。

> 📌 脚本里也保留这条内联（注释写明：上游的 Clash 版清单也只有这一条，
> 与硬编码等效且无增益，挂远程反而多一次拉取）。

#### 11 · `rules`：两版顺序与排序约束

`rules` 是**有序的** —— 自上而下匹配，**第一条命中即决定去向**。

#### 11.1 分流版 27 条

| # | 规则 | 策略 |
|:-:|:-----|:----:|
| 1 | `RULE-SET,Jinx-CN` | `DIRECT` |
| 2 | `RULE-SET,Jinx-Ads` | `AD` |
| 3 | `RULE-SET,AWAvenue-Ads` | `AD` |
| 4 | `RULE-SET,apple-update` | `Apple Update` |
| 5 | `RULE-SET,apple-system` | `DIRECT` |
| 6 | `RULE-SET,geoip-private` | `DIRECT,no-resolve` |
| 7 | `RULE-SET,private` | `DIRECT` |
| 8 | `RULE-SET,openai` | `ChatGPT` |
| 9 | `RULE-SET,google-gemini` | `Gemini` |
| 10 | `RULE-SET,anthropic` | `Claude` |
| 11 | `RULE-SET,category-ai-chat-!cn` | `AI` |
| 12 | `RULE-SET,AI_Domains` | `AI` |
| 13 | `DOMAIN-SUFFIX,music.youtube.com` | `YouTube Music` |
| 14 | `RULE-SET,github` | `Proxy` |
| 15 | `RULE-SET,youtube` | `YouTube` |
| 16 | `RULE-SET,emby` | `Emby` |
| 17 | `RULE-SET,google` | `Google` |
| 18 | `RULE-SET,spotify` | `Spotify` |
| 19 | `RULE-SET,twitter` | `Twitter` |
| 20 | `RULE-SET,microsoft` | `Microsoft` |
| 21 | `RULE-SET,apple-cn` | `DIRECT` |
| 22 | `RULE-SET,telegram` | `Telegram` |
| 23 | `RULE-SET,geoip-google` | `Google` |
| 24 | `RULE-SET,geoip-telegram` | `Telegram` |
| 25 | `RULE-SET,cn` | `DIRECT` |
| 26 | `RULE-SET,geoip-cn` | `DIRECT` |
| 27 | `MATCH` | `Proxy` |

#### 11.2 懒人版 11 条

| # | 规则 | 策略 |
|:-:|:-----|:----:|
| 1 | `RULE-SET,Jinx-CN` | `DIRECT` |
| 2 | `RULE-SET,Jinx-Ads` | `AD` |
| 3 | `RULE-SET,AWAvenue-Ads` | `AD` |
| 4 | `RULE-SET,geoip-private` | `DIRECT,no-resolve` |
| 5 | `RULE-SET,private` | `DIRECT` |
| 6 | `RULE-SET,apple-system` | `DIRECT` |
| 7 | `RULE-SET,category-ai-chat-!cn` | `AI` |
| 8 | `RULE-SET,AI_Domains` | `AI` |
| 9 | `RULE-SET,cn` | `DIRECT` |
| 10 | `RULE-SET,geoip-cn` | `DIRECT,no-resolve` |
| 11 | `MATCH` | `Proxy` |

#### 11.3 五条排序约束

1. **白名单（位 1）必须排在两条广告规则之前** —— `AWAvenue-Ads` 与 `Jinx-Ads`
   存在重叠域名，顺序颠倒会把白名单里的功能域误杀。
2. **两条广告规则并列、同一出口 `AD`** —— 一起切才一致。
3. **AI 厂商专属规则（位 8–10）必须排在通用 AI 兜底（位 11）之前** ——
   否则 AI 域名先被 `category-ai-chat-!cn` 接走，`ChatGPT` / `Gemini` / `Claude` 组永远轮不到。
4. **`music.youtube.com`（位 13）必须排在 `RULE-SET,youtube`（位 15）之前** ——
   它是 `youtube.com` 的子域（§10.5）。
5. **应用分流（位 14–24）必须在国内直连（位 25–26）之前** ——
   否则「ChatGPT 但域名恰好被国内清单收录」会被直连接走。越具体的越靠前。

外加两条**铁律**（与 Surge / Egern 同）：

- **白名单 → REJECT → 常规分流** —— 广告拦截绝不能排在 `cn` / `geoip-cn` 之后，那等于白加；
- **`MATCH` 必须在最后** —— 它是唯一不带条件的规则，排在前面会吞掉后面全部。

#### 11.4 `Apple Update` 与 `apple-system` 的相对位置

位 4（`apple-update` → `Apple Update` 组）排在位 5（`apple-system` → `DIRECT`）**之前**。

两集有重叠域名（`configuration.apple.com` / `mesu.apple.com` / `xp.apple.com`），
`apple-system` 会先把它们接成 `DIRECT`；排在后面 `Apple Update` 组就永远轮不到那几条。

⇒ 这是「**因规则集包含关系而前移**」，与 `music.youtube.com` 同性质。

#### 12 · `no-resolve` 在 mihomo 侧的落点

#### 12.1 同一条原则，三个内核落点不同

原则是：**实测零 IP 条目的规则集不写 `no-resolve`，真含 IP 的必须写**。

| 内核 | 落点 |
|:--|:--|
| Surge | 写在**规则行末尾**（`GEOIP,CN,DIRECT,no-resolve`） |
| Egern | `no_resolve` 字段，**仅对 `geoip` / `ip_cidr` / `ip_cidr6` / `asn` 四类生效**，写在 `rule_set` 上**不生效** |
| **mihomo** | 写在**规则行末尾**（`RULE-SET,geoip-cn,DIRECT,no-resolve`），与 Surge 同 |

#### 12.2 双刃（与 Surge 同）

| 写法 | 后果 |
|:-----|:-----|
| 不带 `no-resolve` | 走到这条 IP 规则的域名会**先触发一次本地解析** |
| 带上 `no-resolve` | 对**尚未解析**的主机名直接跳过 ⇒ 「解析出来发现是国内 IP 就直连」这条路**也一起没了** |

⇒ 所以必须**成对交付**（见 [`dns.md`](../dns.md)）：

> **A** —— 真含 IP 的规则带 `no-resolve`
> **B** —— `MATCH` 之前有一个**域名体量足够**的国内直连规则集

本仓的 B 是 `cn`（`geosite:cn` 同源，10 万+ 条域名），排在 `geoip-cn` 之前。

#### 12.3 本仓的实际落点

| | 带 `no-resolve` 的规则 |
|:--|:--|
| 分流版 | **1 条**：位 6 `RULE-SET,geoip-private,DIRECT,no-resolve` |
| 懒人版 | **2 条**：位 4 `geoip-private` · 位 10 `geoip-cn` |

⚠️ 两处值得注意的不对称：

1. **分流版位 26 `RULE-SET,geoip-cn,DIRECT` 不带 `no-resolve`**，而懒人版位 10 带。
   同一条规则两版写法不同 ⇒ 分流版走到这里的域名会多触发一次本地解析。
   本地解析走的是加密解析器，不产生明文，代价只是首个请求多一次解析耗时。
2. **`lazy.yaml` 与 `docs/01` 里的注释写的是「两条 GEOIP **不带** `no-resolve`」，
   与当前配置（两条**都带**）相反** —— 注释随一次改动过期了，见 §18.4。

#### 13 · `dns` 段：五个解析器键

mihomo 的解析器不是一个，而是**各管一段路**。混用会让「本不该走代理的域名」
或「本不该在本机解析的域名」走错路。

| 键 | 管哪条路 | 分流版的值 | 懒人版的值 |
|:--|:---------|:-----------|:-----------|
| `nameserver` | 主解析器 —— 需要本地解析出真实 IP 的域名 | `dns.cloudflare.com` · `dns.google` | 同左 |
| `fallback` | 后备解析器（`fallback-filter` 判定污染时用） | 同 `nameserver` 两条 | ❌ **无** |
| `nameserver-policy` | 按域名换解析器（**优先于** `nameserver` / `fallback`） | 3 条（§14） | 3 条 |
| `proxy-server-nameserver` | **代理节点域名**（出口 ③，鸡生蛋） | `doh.18bit.cn` · `dns.alidns.com` | `223.5.5.5` · `120.53.53.53` |
| `direct-nameserver` | **`DIRECT` 出站**的域名 —— 直连流量也不碰系统 DNS | 同 `proxy-server-nameserver` | 同左 |
| `default-nameserver` | **引导**：解析其他 DNS 服务器自身的域名 | `223.5.5.5` · `119.29.29.29` | 同左 |

#### 13.1 `default-nameserver` 必须纯 IP

它本身就是「引导」用的。写成域名，就又需要一次解析，循环回来了。
内核对这个键做合法性检查（拆分端口后 host 必须是 IP），并显式跳过 `system`；该键**不允许为空**。

> 🔎 本段真正需要它的只有 `dns.cloudflare.com` 与 `dns.google` 两条
> （`nameserver` / `fallback` 写成主机名端点）。其余键都写成 IP 端点，不需要任何引导。
> ⇒ 把 `nameserver` 换成 IP 形式的端点（`https://1.1.1.1/dns-query`）即可做到**零明文**
> （实测见 `verification.md` §5：34 条明文 → 0 条）。

#### 13.2 `respect-rules: true` 的连带要求

打开后 DNS 查询自身也受路由规则管辖 —— 好处是发往境外 DoH 的查询会按规则经代理发出。
代价是内核**强制要求**同时给出 `proxy-server-nameserver`，缺了直接报错：

```
if "respect-rules" is turned on, "proxy-server-nameserver" cannot be empty
```

（离线门禁 `mihomo -t` 会拦下这一条。）

> ⚠️ 官方还写明：强烈不建议和 `prefer-h3` 一起使用。本仓 `prefer-h3: false`，无冲突。

#### 13.3 `fallback` / `fallback-filter` 只在分流版

分流版多两个键：

```yaml
fallback:
  - https://dns.cloudflare.com/dns-query
  - https://dns.google/dns-query
fallback-filter:
  geoip: true
```

配了 `fallback` 就默认启用 `fallback-filter`，`geoip-code` 默认 `CN`
（解析结果落在 `CN` 之外的 IP 被视为污染 ⇒ 改用 `fallback` 的结果）。

懒人版**不配** `fallback` —— 极简单出口，不做污染判定这一层。

#### 13.4 其余键

| 键 | 值 | 为什么 |
|:--|:--|:-------|
| `enable` | `true` | 启用内核 DNS 模块 |
| `enhanced-mode` | `fake-ip` | 代理域名只回假 IP，真实解析推给落地侧（出口 ②） |
| `fake-ip-range` | `198.18.0.1/16` | 假 IP 段（RFC 6815 保留段） |
| `prefer-h3` | `false` | DoH 只用 HTTP/1.1 与 HTTP/2，不尝试 HTTP/3 |
| `use-hosts` | `true` | 优先查配置里的 `hosts` |
| `use-system-hosts` | `false` | 不读系统 hosts 文件 |
| `listen` | `0.0.0.0:7874` | **仅懒人版有** —— 内核 DNS 服务的监听地址，供局域网设备直接指向。分流版不设（交给客户端） |

> ⚠️ `listen` 是 `check_script_sync.py` 里唯一的 DNS 豁免键（`SKIP_DNS_KEYS`）：
> 脚本整体替换 `dns` 时**不写**这个键，否则可能与客户端自身 DNS 端口冲突。

#### 14 · 双层广告拦截的两个必要条件

这是本仓**最容易静默失效**的一处 —— 缺一条就不生效，且**不报错**。

#### 14.1 两层怎么配合

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

`rcode://success` 的语义：返回**成功但空回答**的响应码
（而不是 `rcode://nameerror` 那种 NXDOMAIN）—— 应用拿到「查到了但没有记录」，
不会触发某些客户端的重试 / 报错逻辑。

#### 14.2 两个必要条件

> **A** —— `nameserver-policy` 里该广告集 → `rcode://success`
> **B** —— **同一个**广告集在 `fake-ip-filter` 里**再列一遍**

**缺 B 只留 A**：`withFakeIP` 中间件**先于** `withResolver` 返回
（内核 `dns/middleware.go`），对 A / AAAA 查询直接下发假 IP ⇒ 请求永远到不了 `nameserver-policy`。
DNS 层拦截**完全失效**，只剩规则层那条。

**缺 A 只留 B**：跳过假 IP 后走真实解析 ⇒ 广告域名拿到真实 IP。
DNS 层没有拦截，只剩规则层。

⇒ 两条都要。判据由 `skill/tests/clash/check_structure.py` 的 ③ 守着：

```python
ads_np = [k for k in npol if str(npol[k]).startswith("rcode://")]
ads_ff = [x for x in ffil if x.startswith("rule-set:")]
if not ads_np: errs.append("DNS 层广告拦截缺失：nameserver-policy 无 rcode://success")
if not ads_ff: errs.append("DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集")
np_sets = {k.replace("rule-set:", "") for k in ads_np}
ff_sets = {x.replace("rule-set:", "") for x in ads_ff}
if np_sets != ff_sets: errs.append("广告集两处不一致：…")
```

> ⚠️ 注意最后一条比的是**集合相等** —— 两处的广告集必须**一一对应**，
> 多一个少一个都判负。加第三份广告清单时两处都要加。

#### 14.3 第三个条件：顺序

`nameserver-policy` 里广告两项**必须排在** `private,cn` 之前 ——
否则先命中 `cn` 就拿不到空回答（广告域名里有一批是 `.cn`）。

门禁也守这一条：

```python
if cn_idx and ads_idx and min(ads_idx) > min(cn_idx):
    errs.append("广告 policy 排在 cn 之后 —— 会先命中 cn 而拿不到空回答")
```

#### 14.4 两处的键名形态不同

| 配置 | 第三个 policy 键 |
|:-----|:-----------------|
| 分流版 | `rule-set:private,cn` |
| 懒人版 | `geosite:private,cn` |

两者都能工作（`rule-set:` 引用本仓已声明的 provider；`geosite:` 直接查内核数据库），
但**写法不统一**。改这两份时别互相照抄 —— 见 §18.2。

#### 14.5 与 Surge / Egern 的对比

| | Surge | Egern | **mihomo** |
|:--|:--|:--|:--|
| 广告拦截落点 | 规则层，指向**字面量 `REJECT`** | 规则层，指向 `AD` 组 | 规则层指向 `AD` 组 **+ DNS 层 `rcode://success`** |
| 解析阶段拒答 | `REJECT,pre-matching,extended-matching` | `dns.forward` 里 `value: reject` | `nameserver-policy: rcode://success` |
| 能不能指向组 | ❌ `pre-matching` 要求字面量 REJECT 族，**写成组会拒绝加载整份配置** | ✅ | ✅ |

> ⚠️ 反方向移植才是安全的：mihomo 的「广告指向 `AD` 组」照搬到 Surge 的
> `pre-matching` 规则上，后果不是效果差一点，而是**整份配置加载失败**。

> 📌 `AD` 组的成员：分流版 `REJECT` / `DIRECT`（可放行）；懒人版只有 `REJECT`（单成员，不留口子）。
> ⚠️ 脚本注释写明**不设 `PASS`** —— `PASS` 语义为「绕过代理直连」，
> 与「拦截 / 放行」二选一的口径不符，易误操作。

#### 15 · `fake-ip-filter` 的通配语义

#### 15.1 17 条：15 条功能域 + 2 条广告集

| 类 | 条目 | 拿到假 IP 的后果 |
|:--|:-----|:-----------------|
| 🏠 局域网 | `*.lan` · `*.local` · `*.localdomain` · `*.home.arpa` | 局域网设备不在代理链路里，假 IP 直接连不上 |
| 🪟 微软联网探测 | `+.msftconnecttest.com` · `+.msftncsi.com` | 探测失败 → 系统判定「无 Internet」并限制联网 |
| 🎮 游戏机 | `+.srv.nintendo.net` · `+.stun.playstation.net` · `+.xboxlive.com` | 联网检测与 NAT 类型判定失败 |
| 🕐 NTP / STUN | `stun.*` · `time.*.com` · `ntp.*.com` · `+.pool.ntp.org` | 时间同步走假 IP 直接失败 |
| 🧩 其他 | `localhost.ptlogin2.qq.com` · `+.market.xiaomi.com` | 登录与应用商店的本地连通性检测 |
| 🚫 广告 | `rule-set:AWAvenue-Ads` · `rule-set:Jinx-Ads` | **必须与 `nameserver-policy` 一一对应**（§14.2） |

#### 15.2 三种通配符的语义（v1.19.31 实测）

| 模式 | 命中 | 不命中 | 结论 |
|:--|:--|:--|:--|
| `+.example.com` | `example.com` · `a.example.com` · `a.b.example.com` | — | 本域**与**任意层子域 |
| `time.*.com` | `time.a.com` | `time.a.b.com` | `*` 只匹配**一层** |
| `*.lan` | `x.lan` | `a.b.lan` | `*.` 只匹配**一层** |

> ⚠️ 由此得到一条边界：`*.lan` / `*.local` 只覆盖一层子域，
> 像 `a.b.lan` 这样的多层名字**不会**被过滤 ⇒ 需要时用 `+.lan`。

> ⚠️ 官方还定义了 `.example.com`（匹配子域但**不含**本域）。本仓不用这种写法。

#### 15.3 `rule-set:` 前缀的能力边界

官方明示：**`rule-set` 仅支持 `behavior` 为 `domain` / `classical`**。

本仓两份广告集正好落在这两类上：

| 集 | behavior | 可用 |
|:--|:---------|:--:|
| `AWAvenue-Ads` | `domain` | ✅ |
| `Jinx-Ads` | `classical` | ✅（classical 时**仅生效其中的域名类规则**） |
| `geoip-cn` 之类 | `ipcidr` | ❌ 放进 `fake-ip-filter` 无意义 |

#### 15.4 命中的代价

命中的域名会**真的去走一次本地真实解析**（用的是主解析器，即加密端点）
—— 这是「出口 ②」的代价面，属于设计已知。

#### 15.5 与 Surge `always-real-ip` 的关系

Surge 的 `always-real-ip` 与 mihomo 的 `fake-ip-filter` 是**同一件事的两种载体**，
但有一处关键差异：

| | Surge `always-real-ip` | mihomo `fake-ip-filter` |
|:--|:-----------------------|:------------------------|
| 改变流量目的地吗 | ❌ 只改变返回真实 IP 还是 Fake-IP，**不参与分流** | ❌ 同 |
| 额外能力 | — | ✅ 可挂 `rule-set:` 引用整个规则集（Surge 只能列举） |

⇒ mihomo 侧把「广告集跳过 fake-ip」也挂进了同一个键，这是 Surge 做不到的
（Surge 必须靠 `pre-matching` 在规则层拦）。

#### 16 · 已知取舍

#### 16.1 一份配置两种交付形态，靠对拍兜底

静态文件与覆写脚本必须逐位一致（§2）。这带来一条持续成本：
**任何一处改动都要写两遍**（`.yaml` 与 `.js`），只改一处会被 `check_script_sync.py` 拦下。

代价换来的是：用户既能「下载即用」，也能「保留自己的订阅」。
这是 mihomo 生态特有的能力（JS 覆写），Surge / Egern 都没有对应物。

#### 16.2 Smart 三档只存在于模板

脚本侧做不到倍率分档（§7.2），只能用 `sortedByRate` 排出一个顺序。
`check_script_sync.py` 把它列为**已知差异**，打印提醒但不判负。

⇒ 用户用脚本订阅时，`Smart` 是单组 `fallback`（按倍率升序排列的节点），
而不是三档。这是**机制决定的**，不是漏实现。

#### 16.3 `no-resolve` 只给真含 IP 的规则

分流版只给 `geoip-private` 一条带上 `no-resolve`，`geoip-cn` 不带（§12.3）。
走到 `geoip-cn` 的域名会多触发一次本地解析 —— 本地解析走的是加密解析器，
不产生明文，代价只是首个请求多一次解析耗时。

#### 16.4 规则集全面远程化（.mrs）

17 条原生 `GEOSITE` / `GEOIP` 改成远程 `.mrs`（§10.2），换来的是：

| | 原生 `GEOSITE` | 远程 `.mrs` |
|:--|:--|:--|
| 依赖 | 依赖 `geosite.dat` / `geoip.dat` 数据库文件与 `geox-url` | 只依赖一次 HTTP 拉取 |
| 新鲜度 | 跟着数据库更新 | 跟着 `interval` 与上游 |
| 落盘 | 无 | ✅ `path` 落盘，离线可用 |
| 体量 | 数据库全量加载 | 按需、zstd 压缩 |

代价：多一次网络依赖（死链会静默降级成空集，§9.5）。

#### 16.5 IPv6 关两处，不是一处

见 §4.2。只关一处会漏 —— 这是 mihomo 与另两个内核的结构差异
（Surge 是 `ipv6` + `ipv6-vif`，Egern 只要 `ipv6`）。

#### 16.6 `dns-hijack: any:53` 只收 UDP

官方语义：不写协议前缀时默认 `udp://` ⇒ `any:53` 收的是 **UDP**:53。
要把 `TCP:53` 也收进来，需要另外加一条 `tcp://any:53`（本配置**未加**）。

理由：明文 TCP 查询在现代客户端里已属罕见，加了会多接管一条通路。
需要覆盖时加一行即可。

#### 16.7 `stack: mips`

mihomo 自研的 IP 协议栈（可选 `system` / `gvisor` / `mixed` / `mips`）。
常规使用足够；遇到兼容性问题换成 `gvisor` 即可。

#### 16.8 刷新周期与姊妹仓不同（86400 vs 604800）

见 §10.3。mihomo 侧钉一天，Surge / Egern 侧钉一周。
**不强行对齐** —— 两内核的键语义与缺省值都不同，对齐只是徒增困惑。

#### 17 · FAQ

**Q：导入后所有走代理的流量都不通。**

大概率是订阅地址没换。`proxy-providers.Airport.url` 是占位地址
（`sub.example.com` + `REPLACE_WITH_YOUR_TOKEN`），不换就一定不通。
`proxies: []` 是空段，节点全来自订阅 —— 所以至少要让订阅可用。

**Q：我想用自己的订阅，但不想改配置文件。**

用覆写脚本：`clash/override/my_clash.js`（分流版）或 `my_clash_lazy.js`（懒人版）。
把它托管到一个 URL，在客户端的「覆写」里导入，再绑到目标订阅上（§1.1）。

**Q：脚本和静态配置的效果一样吗？**

规则 / 规则集 / DNS **逐位一致**（由 `check_script_sync.py` 兜底）。
唯一差异是 `Smart`：模板是三档 `fallback`，脚本是单组 `fallback`（§7）。

**Q：为什么 `Smart` 用 `fallback` 而不是 `url-test`？**

三档之间有明确优先级（省钱优先），不该按延迟打断这个顺序。`fallback` 按成员顺序
取第一个可用的、**不比较延迟**；档内才是 `url-test` 择优（§7.4）。

**Q：我加了倍率节点，为什么没进 `Low Mult.`？**

只有**静态模板**才有三档子组。用脚本订阅的话，倍率只影响 `Smart` 的成员**顺序**
（且脚本的 `rateOf` 只认低倍率 `0.xxx`，高倍率节点混在「无倍率」里排最后）。

**Q：广告拦截加了清单，但没生效。**

查三件事：① `nameserver-policy` 里有 `rcode://success`；
② **同一个**集在 `fake-ip-filter` 里也列了一遍；
③ 广告 policy 排在 `private,cn` **之前**。三条缺一即失效，且**不报错**（§14）。

**Q：`include-all` 和 `use` 能一起写吗？**

能写，但 `include-all` 会**覆盖** `use`（它引入所有 providers）。
只有一个 provider 时看不出区别；加了第二个就想清楚要哪个（§6.1）。

**Q：为什么 `Proxy` 组的 `url` 健康检查看起来没测速？**

官方明示：策略组的 `url` **只检查 `proxies` 字段的代理，不检查通过 `use` 引入的
代理集合**。本仓 `Proxy` 的 `proxies` 是空的 ⇒ 延迟读数由 `proxy-providers.Airport.health-check` 承担（§5.1）。

**Q：节点名里带「港」却没进 `Hong Kong` 组？**

地区组的 `filter` 是**双断言**：正向要含本地区词，负向要**不含**其它地区词。
「深港 01」这种中转命名会同时含两个地区词 ⇒ 两档都不进，落 `Other Regions`（§8.3）。

**Q：`198.18.0.1` 为什么不是真实 IP？**

它是 mihomo 的 `fake-ip-range`（`198.18.0.1/16`，RFC 6815 保留段）。
Surge / Egern 侧的 secrets 扫描不认识它，整合时加了白名单（§5.2）。

**Q：`routing.yaml` 为什么这么长（3294 行）？**

里面有 7 份首尾相接的完整配置（无 `---` 分隔、无注释），是生成/拼接残留，
最后一份才是当前版。详见 §18.1 —— 这是个待清理的坑，不是设计。

#### 18 · 维护者须知

#### 18.1 改动前必须知道的四条

1. **一处改动要写（最多）四处**：静态 `.yaml` + `.min.yaml` + 覆写 `.js` + （若动规则集内容）`rules/*.list`。
   前三者由两个门禁兜底：`check_min_pair.py`（.min 对拍）与 `check_script_sync.py`（脚本对拍）。
2. **规则顺序铁律不许破**：白名单 → REJECT → 应用分流 → 国内域名 → 国内 IP → `MATCH`（§11.3）。
3. **节点不许提交真实值**：`check_secrets.py` 会拦（§5.2）。
4. **`rules/*.yaml` 是生成物**：改真源 `.list` 后重跑 `build_rules.py`（§10.4）。

#### 18.2 一处已知的文档 / 配置漂移（改之前先读）

| 位置 | 写的 | 实际 | 性质 |
|:--|:--|:--|:--|
| `routing.yaml` 头注 | ~~23 / 22 / 24~~ → **25 / 25 / 27** | 25 / 25 / 27 | ✅ 已更正 |
| `my_clash.js` 头注 | ~~20 / 20 / 26~~ → **22 / 25 / 27** | 22 / 25 / 27 | ✅ 已更正 |
| `my_clash_lazy.js` 头注 | ~~5 MRS + 5 yaml~~ → **6 MRS + 4 yaml** | 6 mrs + 4 yaml | ✅ 已更正 |
| `lazy.yaml` 规则注释 | 「两条 GEOIP **不带** `no-resolve`」 | 两条**都带** | 注释过期 |
| 分流版 vs 懒人版 | `nameserver-policy` 第三个键 `rule-set:private,cn` vs `geosite:private,cn` | 两版写法不同 | 见 §14.4 |
| 分流版位 26 | `geoip-cn` **不带** `no-resolve`；懒人版位 10 **带** | 两版不同 | 见 §12.3 |

> ⚠️ 判据**以配置文件为准**，注释与文档是辅助。改配置时顺手把这些过期文字一起改掉。

#### 18.3 `routing.yaml` 的拼接残留（**必须先清理再改**）

`clash/profiles/routing.yaml` 里纵向串了 **7 份完整的 YAML 配置**，
无 `---` 分隔、也无注释说明。逐块切片核对的结果：

| 块 | 行 | 组 / 规则 / 集 | 性质 |
|:-:|:--|:--|:--|
| 1–5 | 43–2804 | 23 组 · 24 条 · 22 集（各块略有差异，是演进中间态） | 过渡态 |
| 6–7 | 2805–3294 | **25 组 · 27 条 · 25 集** | 当前版 |

第 7 块与 `clash/profiles/routing.min.yaml` **逐字节相同**（已核对）。

⚠️ 三个后果：

1. **重复顶层键**。PyYAML 静默取最后一份 ⇒ 本仓门禁（PyYAML 系）**全绿**，看不出问题；
   `check_min_pair.py` 也是拿最后一块与 `.min` 对拍，同样通过。
   mihomo 用 `gopkg.in/yaml.v3` 解析（v3 默认开启唯一键检查），**有报错风险，未经实测** ——
   这正是 [`AGENTS.md`](../../../AGENTS.md) §7 那条「**本地全绿 ≠ 线上能跑**」的同类。
2. **在文件里搜索会命中多处**，`grep -c` 得到的数字是 7 倍。
   本文所有数字（25 / 27 / 25）取的是**解析后的结果**与**最后一块**，不是 grep 计数。
3. **改文件时极易改错块** —— 改到第 1 块等于没改。

⇒ 处理办法：重新生成一次 `routing.yaml`（内容取最后一块），再重跑全部门禁。
**在清理之前，任何对 `routing.yaml` 的编辑都要先确认自己改的是最后一块。**

#### 18.4 门禁清单与跑法

```bash
python skill/tests/clash/check_structure.py      # 悬空引用 / 规则指向 / 双条件 / IPv6
python skill/tests/check_min_pair.py       # .yaml ↔ .min.yaml 对象对拍
python skill/tests/clash/check_script_sync.py    # 脚本 ↔ 静态 profile 对拍
python skill/scripts/clash/build_rules.py --check # 规则集生成物是否过期

python skill/tests/clash/check_remote_urls.py    # 慢，按需：远程 URL 可达性
python skill/tests/clash/check_secrets.py        # 占位符纪律
```

`check_structure.py` 对**四份** profile 都跑（`lazy` / `lazy.min` / `routing` / `routing.min`）。

退出码：`0` = 通过 · `1` = 有判负 · `2` = 环境/用法问题。

> ⚠️ `2` 与 `1` 必须分开：解释器坏掉、文件缺失、编码炸掉都属于 `2`，
> **绝不能被读成一次成功的判负**。Windows 中文控制台默认 cp936，
> `print` 一个中文就可能 `UnicodeEncodeError`、进程以退出码 1 结束
> —— 而 1 恰是「判负」的码。`_clash_common.utf8_stdout` 就是为这个存在的。

#### 18.5 路径探测用 CWD 优先

四个 clash 门禁的 `_default_root` 都是「**当前工作目录 → 逐级向上 + `/clash`**」，
找到同时含 `profiles/` 与 `override/` 的目录为止。

原因写在每个脚本的注释里：**CI 上 `__file__` 探测会算错目录**
（实测 GitHub Actions 上基于 `__file__` 向上推算失败，报「缺文件」而本地全过）。
⇒ 从仓库根调用，不要从脚本所在目录调用。

#### 18.6 与姊妹仓的边界

- ❌ 不为了本仓测试变绿去改其他仓库；
- ⚠️ `rules/` 是三内核共享真源，改 `.list` 会影响 Surge / Egern 两侧；
- ⚠️ 结构性调整需先补判据，不靠"再跑一遍"。

---

相关：[`rulesets.md`](../rulesets.md) ·
[`dns.md`](../dns.md) ·
[`rulesets.md`](../rulesets.md) ·
[`clash.md`](../profiles/clash.md) ·
[`AGENTS.md`](../../../AGENTS.md)

---

## mihomo · 加固模板（clash 侧）

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
> 相关：[`profiles/<kern>.md`](../profiles/clash.md)（逐键语义）·
> [`ops.md`](../ops.md)（泄露面定位）·
> [`pitfalls.md`](../pitfalls.md)（踩过的坑）

#### 1 · 结构总览与顺序语义

```
ipv6: false                  # ① 顶层开关（与 dns.ipv6 成对，见 §3.6）
proxy-providers:             # 订阅槽位，唯一需要用户填的东西
proxy-groups:                # 25 个策略组
rule-providers:              # 25 份规则集（19 MRS + 1 AWAvenue + 2 Jinx + 3 自托管）
rules:                       # 27 条，自上而下
dns:                         # 防泄露本体
tun:                         # 流量接管 + :53 劫持（见下）
```

**顺序有语义**：`rules` 自上而下匹配，第一条命中即决定去向。

⚠️ 本仓的生成顺序由 `skill/scripts/clash/build_profiles.py` 固定（见该脚本的 `order`），
手工调整 YAML 顶层键顺序会在下次重新生成时被覆盖 —— 想改顺序改脚本，不要改文件。

#### 2 · `tun` 段：流量接管与 `:53` 劫持

> ⚠️ **本仓配置不带 `tun` 段** —— 静态 profile 与覆写脚本输出都不带。
>
> 理由：本仓只管 **DNS 防泄露**（由 `dns` 段完成）；是否开 TUN、怎么设置
> （`stack` / 路由 / 劫持端口）交给客户端或系统决定，不替用户做选择。
>
> 那「旁路设备直发 `:53`」（泄露面③）谁管？两种接管方式，**都不在本仓配置内**：
>
> | 方式 | 怎么做 | 典型场景 |
> |:--|:--|:--|
> | **TUN 模式** | `tun.dns-hijack` 劫持 `:53` | 桌面客户端（Mihomo Party / Clash Verge），TUN 默认开启 |
> | **透明代理模式** | `iptables`/`nftables` 把 `:53` 重定向到 mihomo 的 DNS 监听端口 | 软路由 / OpenClash（**实测：未开 TUN，仅靠 `dns` 段即防泄露**）|
>
> 两者殊途同归 —— 都把明文 `:53` 送进本仓的 `dns` 段处理。

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

#### 2.1 它防的是哪一条泄露面

**TUN 不是「防 DNS 泄露」的必要条件** —— 这点常被说大，要写清：

| | 防的是什么 | 靠什么 |
|:--|:--|:--|
| **DNS 防泄露（本体）** | 本地解析不外泄：查询走加密通道、代理域名不给真答案、不为判定而多余解析 | `dns` 段 —— 加密解析器 / `fake-ip` / IPv6 两处关闭 / `no-resolve` / 广告拦截双条件 |
| **泄露面③（旁路设备）** | 应用**不理** DNS 设置、直接向 `:53` 发明文查询 | `tun.dns-hijack` 接管 |

⇒ 覆写脚本形态**没有** `tun`，但 `dns` 段齐全 —— 所以**照样防 DNS 泄露**。
   它缺的只是「接管旁路设备」这一条，而那一条由客户端自己的 TUN 负责。

⇒ 反过来，**只写 `tun` 而 `dns` 段不加密**，该漏还是漏 —— TUN 兜不住解析行为。

#### 2.2 这一段本仓真的丢过


由脚本重建**静态 profile** 时，直接用了脚本输出（其中本就没有 tun），
于是四份静态配置全没了 tun —— 防线破了而门禁全绿，因为当时没有任何判据检查它。

注意这不是「脚本少了 tun」的问题（脚本本就不该有），
而是「拿脚本输出当静态 profile 用」时**漏了继承**的问题。

现在有两道守门：

1. `skill/scripts/clash/build_profiles.py` 会从静态版**继承** tun，且自检要求它存在
2. `skill/tests/clash/check_structure.py` 第 ④ 项检查 `enable` / `dns-hijack` /
   `auto-route` / `strict-route` 四键

删掉 tun 实测会报 4 处并判负。

#### 3 · `dns` 段：四个键各管一段路

mihomo 的 dns 段比 Surge / Egern 分得细，**四个键不要混用**：

| 键 | 管什么 | 本仓取值 |
|:--|:--|:--|
| `default-nameserver` | **引导解析器**：只用于解析 DoH 端点自身的域名 | `223.5.5.5` / `119.29.29.29`（纯 IP） |
| `proxy-server-nameserver` | 只解析**代理节点域名**（连节点前还没有代理可用，鸡生蛋） | `doh.18bit.cn` / `dns.alidns.com` |
| `direct-nameserver` | 只解析 **DIRECT 出站**的域名 —— 直连流量也不碰系统 DNS | 同上 |
| `nameserver` | **主解析器**：需要本地解析出真实 IP 的域名 | `1.1.1.1` / `8.8.8.8`（**IP 字面量**，见 §5）|

#### 3.1 `enhanced-mode: fake-ip`

```yaml
enhanced-mode: fake-ip
fake-ip-range: 198.18.0.1/16
```

代理域名只回假 IP，**真实解析在落地侧完成** —— 本地不留答案。

`198.18.0.0/15` 是 RFC 6815 保留段。⚠️ 这个地址曾被 Surge 侧的凭据扫描
判成「真实 IP」（那个内核不认识这个段），已加入 `DOC_NETS` 白名单。
两个内核的「常识」不同，整合时必须处理这类分歧。

#### 3.2 `respect-rules: true`

DNS 查询自己也受路由规则管辖 —— 发往境外 DoH 的查询会按规则经代理发出。

#### 3.3 `prefer-h3: false`

不优先 HTTP/3，只用 HTTP/1.1 + HTTP/2。

#### 3.4 `use-hosts: true` / `use-system-hosts: false`

读配置里的 hosts，**不读系统 hosts 文件**（避免被本机污染）。

#### 3.5 `fallback` 与 `fallback-filter`

```yaml
fallback:
  - https://1.1.1.1/dns-query
  - https://8.8.8.8/dns-query
fallback-filter:
  geoip: true
```

（与 `nameserver` 相同，同样写 IP 字面量 —— 理由见 §5。）

主解析器失败时的退路。`geoip: true` 让回退只在 geoip 判定需要时才用。

#### 3.6 IPv6：两处都要关

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

#### 4 · `default-nameserver`：引导解析器

```yaml
default-nameserver:
  - 223.5.5.5
  - 119.29.29.29
```

**只用于解析 DoH 端点自身的域名**。内核要求必须是**纯 IP**，不能写域名 ——
否则「解析解析器」这件事本身又需要一次明文解析，形成鸡生蛋。

本仓其余端点都写成 DoH URL 或 IP 字面量，引导需求只有极少数条目。

#### 5 · `nameserver` / `fallback`：主解析


```yaml
nameserver:
  - https://1.1.1.1/dns-query      # Cloudflare
  - https://8.8.8.8/dns-query      # Google
```

✅ **已确认并修正（2026-10-07）**：必须写 **IP 字面量**，不能写主机名。

为什么：官方明确 `default-nameserver`「必须为 IP」，它的用途就是
**解析 DNS 服务器的域名**。若 `nameserver` 写成主机名（如
`https://dns.cloudflare.com/dns-query`），就要靠 `default-nameserver`
去解析它 —— 那是一次**必然发生**的明文引导查询（泄露面①：
冷启动 100% 触发，虽然只发生一次，但它是「必然通路」不是「可能通路」）。

写成 IP 字面量即消除该面。现由 `check_structure.py` 第 ⑥ 项守着
（注入主机名会判负）。

`fallback` 同理，本仓设为与 `nameserver` 相同的两个端点，
配 `fallback-filter.geoip: true`。

#### 6 · `nameserver-policy`：按域换解析器


```yaml
nameserver-policy:
  "rule-set:AWAvenue-Ads": rcode://success
  "rule-set:Jinx-Ads": rcode://success
  "rule-set:private":
    - https://doh.18bit.cn/dns-query
    - https://dns.alidns.com/dns-query
  "rule-set:cn":
    - https://doh.18bit.cn/dns-query
    - https://dns.alidns.com/dns-query
```

- 私有域 + 中国大陆域名交回**国内 DoH**（解析结果准、延迟低）
- 两条广告清单返回 `rcode://success`（空回答）—— 见 §8

⚠️ **顺序有语义**：广告项**必须排在 `rule-set:private` / `rule-set:cn` 之前**，
否则先命中 `cn` 就拿不到空回答。

✅ **已确认并统一（2026-10-07）**：键用**单名**形式，不用逗号多值。

依据：官方文档的示例只有单名（`'rule-set:cn'`、`geosite:xxx`），
**逗号分隔多值没有任何官方依据**。此前分流版写 `rule-set:private,cn`、
懒人版写 `geosite:private,cn`，两版既不一致也无据可依。
拆成两条后语义明确，且两版统一用 `rule-set:` 前缀
（本仓规则集都是 rule-provider，`geosite:` 无对应）。

#### 7 · `fake-ip-filter`：谁必须跳过假 IP

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

#### 8 · 广告拦截的两个必要条件

DNS 层拦截比规则层早（连接根本建立不起来），但要**两个条件同时满足**：

| 条件 | 配置 | 缺了会怎样 |
|:--|:--|:--|
| ① | `nameserver-policy` 里 `rule-set:<广告集>: rcode://success` | 域名被正常解析，拦截不生效 |
| ② | 同一个广告集在 `fake-ip-filter` 里再列一遍 | `withFakeIP` 中间件对 A/AAAA **直接返回假 IP**，请求永远到不了 ① |

**缺任一条件拦截就完全失效，而且不报错。** 这是本仓最隐蔽的一类坑。

还有第三个条件：**① 中的广告项必须排在 `private,cn` 之前**（见 §6）。

规则层 `AD` 组保留作兜底 —— DNS 拦截覆盖不到 IP 直连、DoH/DoT 与客户端缓存命中。

#### 9 · 规则层：顺序铁律与 `no-resolve`

#### 9.1 顺序铁律

白名单 → 广告 → Apple 更新/系统 → 内网 → AI → 应用 → 国内 → 兜底。

⚠️ 白名单**必须留在两条广告清单之前** —— 两份黑名单存在重叠域名，
顺序颠倒会把白名单里的功能域误杀。

#### 9.2 `no-resolve`

IP 类规则（geoip-\*）原则上应带 `no-resolve`，避免为判定而触发一次本地解析。
纯域名规则集**不写**（没有 IP 规则，写了无意义）。

✅ **已确认并统一（2026-10-07）**：两版 `geoip-*` **全部带** `no-resolve`。

**RULE-SET 是否支持该参数** —— 此前存疑，现已取到源码级证据：

```go
// rules/parser.go
case "RULE-SET":
    isSrc, noResolve := RC.ParseParams(params)
    parsed, parseErr = RP.NewRuleSet(payload, target, isSrc, noResolve)
```

即 RULE-SET 确实解析 `no-resolve` 并传给 `NewRuleSet`。
而 `geoip-*` 的 behavior 是 `ipcidr`（IP 规则），不带就会为判定
「目标 IP 是否命中」先触发一次本地解析（泄露面④）。

现由 `check_structure.py` 第 ⑤ 项守着（缺了会判负）。

> 附带纠正：`verification.md`（原 DetailsReadme）曾声称
> 「两条 GEOIP 都不带 no-resolve」，与懒人版实际写法矛盾 —— 已统一。


#### 10 · 订阅槽位：导入前必改的一处

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

#### 11 · 逐项验证：用哪个脚本

| 加固项 | 用什么验证 |
|:--|:--|
| **禁止** `tun` 段（4c4bc56 起反转；原为「要求四键」，文档曾长期说反）| `python skill/tests/clash/check_structure.py` |
| IPv6 两处关闭 | 同上 |
| 广告拦截双条件 + 顺序 | 同上 |
| 无悬空引用、规则指向存在 | 同上 |
| `.min` 与完整版一致 | `python skill/tests/check_min_pair.py` |
| 脚本输出 = 静态文件 | `python skill/tests/clash/check_script_sync.py` |
| 规则集 URL 全可达 | `python skill/tests/clash/check_remote_urls.py` |
| 无真实凭据 | `python skill/tests/clash/check_secrets.py` |
| 不引用外部仓库资源 | `python skill/tests/check_selfcontained.py` |
| 生成物未过期 | `python skill/scripts/clash/build_rules.py --check`<br>`python skill/scripts/clash/build_profiles.py --check` |
| 全跑 | `python skill/tests/verify_all.py`（全套闸门） |

#### 12 · FAQ

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

#### 13 · 维护者须知

- **改配置改脚本**，不要手工改 `profiles/*.yaml` —— 它们由 `build_profiles.py` 生成，
  手工改会在下次生成时被覆盖（而追加写会堆叠）
- **改规则集改真源** `rules/*.list`，不要改 `rules/*.yaml`（生成物）
- **新增加固项时同步加判据** —— 本仓丢 tun 那次就是因为只有配置没有判据
- **判别力要验证**：注入坏样例确认门禁真的会判负，只测「好配置通过」证明不了
- **两版口径不同的地方**（`AD` 组、`no-resolve`、`nameserver-policy` 键名）
  先确认再统一，不要想当然对齐

---

## mihomo · 分支与变体（clash 侧）

> **何时读**：准备选择、切换或新增 Surge / Egern / mihomo 配置时；评审一个改动究竟是
> 「新内核」「新产品线」还是「同一产品的另一种交付形态」时。
>
> 本文只讨论**分支形态与维护边界**。具体键语义见各内核的 `profiles/<kern>.md`，
> 门禁命令与判据见 [`gates.md`](../gates.md)。仓库总览与纪律以
> [`AGENTS.md`](../../../AGENTS.md) 为准。
>
> 当前仓库不是把三份配置揉成一份“万能配置”，而是把它们放在同一个验证框架里：
> **产品目标尽量一致，内核语义允许不同，共享资产只保留一份。**

#### 1 · 三层分支模型

本仓的“分支”不是 Git branch，而是三个正交维度。先分清维度，才能避免复制出一堆
名称相近、职责重叠、无人维护的文件。

| 维度 | 当前取值 | 回答的问题 | 是否可以叠加 |
|:-----|:---------|:-----------|:-------------|
| **内核** | Surge / Egern / mihomo | 哪个客户端、哪套配置语义负责运行 | ❌ 三选一 |
| **产品线** | `lazy` / `routing` | 要极简出口，还是按应用与地区细分 | ❌ 二选一 |
| **交付形态** | 完整版 / `.min`；mihomo 另有覆写脚本 | 配置如何被阅读、导入或挂到订阅上 | 同一产品的替代入口，不是叠加层 |

因此，“mihomo 分流版覆写脚本”可以完整描述成：

> 内核 = mihomo；产品线 = `routing`；交付形态 = JavaScript 覆写。

而 `routing.yaml` 与 `routing.min.yaml` **不是两条产品线**。它们解析后的配置对象必须相同，
区别仅是前者带说明、后者用于直接导入。同理，Surge / Egern 的完整版与 `.min` 版也不是版本分叉。

#### 1.1 当前文件树

```text
self-conf/
├── surge/profiles/
│   ├── lazy.conf · lazy.min.conf
│   ├── routing.conf · routing.min.conf
├── egern/profiles/
│   ├── lazy.yaml · lazy.min.yaml
│   ├── routing.yaml · routing.min.yaml
├── clash/
│   ├── profiles/
│   │   ├── lazy.yaml · lazy.min.yaml
│   │   └── routing.yaml · routing.min.yaml
│   └── override/
│       ├── my_clash_lazy.js
│       └── my_clash.js
├── icons/                         # 三内核共用
├── rules/                         # .list 真源 + mihomo .yaml 生成物
└── skill/
    ├── reference/{shared,surge,egern,clash}/
    ├── scripts/{surge,egern,clash}/
    └── tests/ · tests/clash/
```

#### 1.2 “版本”放在哪里

- 现役入口使用稳定文件名 `lazy.*` / `routing.*`，订阅地址不随版本变化；
- mihomo 当前以脚本生成现役静态 profile，演进记录主要看 Git 历史与 `CHANGELOG.md`（本目录）；
- 不要为了保留旧行为在现役目录里再造 `routing-new`、`routing-final`、`routing-fixed`。

**判据**：能由旧配置升级得到的是“版本”；服务不同用户任务的才是“产品线”。

#### 2 · 三个内核怎么选

#### 2.1 定位总表

| 内核 | 原生载体 | 本仓定位 | 适用场景 | 主要维护风险 |
|:-----|:---------|:---------|:---------|:-------------|
| **Surge** | `.conf` | Apple 平台上的显式 profile；规则与策略组可读性强 | 已使用 Surge、需要其策略组与规则语义、希望直接订阅 profile | `pre-matching`、`no-resolve`、内置 `SYSTEM` / `LAN` 等语义不能照搬到别处 |
| **Egern** | `.yaml` | Apple 平台的 YAML profile；DNS 有默认 DNS 与代理 DNS 两条路径 | 已使用 Egern、需要其 DNS forward / `proxy_nameservers` 模型 | `rule_set`、`no_resolve` 与 Surge 同名近义但落点不同；节点域名解析路径独立 |
| **mihomo** | `.yaml` + `.js` | Clash.Meta 生态；既给静态 profile，也给可挂任意订阅的覆写脚本 | 桌面、路由器或支持 mihomo 覆写的客户端；希望保留订阅自身节点 | provider、`filter`、`fake-ip-filter`、DNS 双层广告拦截和脚本/静态同步面更多 |

#### 2.2 选择原则

1. **先按客户端选内核，不按配置长相选。** `.yaml` 只是语法外壳，Egern YAML 与 mihomo YAML
   不是互换格式。
2. **再按控制粒度选产品线。** 只想有一个代理出口和一个 AI 出口，用懒人版；需要应用、地区、
   更新开关或独立出口，用分流版。
3. **最后按导入方式选形态。** mihomo 用户若要保留订阅内节点，用覆写脚本；若要一份可审计、
   可离线检查的完整对象，用静态 profile。
4. 不以“组数更多”判断安全性。两条产品线保留同一类 DNS / IPv6 / 广告防护底线；
   分流版多出来的是控制面，不是额外的安全等级。

#### 2.3 不能跨内核复制的典型概念

| 需求 | Surge / Egern | mihomo | 为什么不能机械对齐 |
|:-----|:--------------|:-------|:-------------------|
| 地区自动选优 | `smart` + filter | `url-test` + filter | 组类型、成员展开与健康检查语义不同 |
| 订阅入口 | `Airport` external 组 | `proxy-provider` 或订阅自带 `proxies` | 一个是组，一个是 provider / 节点池 |
| 倍率分档 | `policy-priority` 权重 | 静态模板用三个 `filter` 子组 | 覆写脚本执行时看不到 provider 节点名，不能做同样分档 |
| 规则集 | `.list` | `.mrs` / `.yaml` | format 与 behavior 必须配对，不能只改扩展名 |
| DNS 拦截 | 各自的 DNS / 规则阶段机制 | `nameserver-policy` + `fake-ip-filter` 双条件 | 同一句“拦广告”在三个内核中的执行阶段不同 |

跨内核移植前先读 [`rulesets.md`](../rulesets.md)。
“目标一致”只允许复用验收结果，不允许复用未经翻译的键。

#### 3 · 两条产品线：懒人版与分流版

#### 3.1 当前规模

下表的数字来自**解析现役完整版后的对象**：不把注释算规则，不把 `.min` 再算一遍。

| 内核 / 形态 | 懒人版 | 分流版 | 计数说明 |
|:------------|:-------|:-------|:---------|
| Surge 静态 | **4 组 / 11 条规则** | **23 组 / 26 条规则** | 组数含订阅槽位 `Airport` |
| Egern 静态 | **4 组 / 11 条规则** | **23 组 / 26 条规则** | 组数含隐藏订阅槽位 `Airport` |
| mihomo 静态 | **3 组 / 11 条规则** | **<!-- auto:clash-group-count -->22<!-- /auto:clash-group-count --> 组 / <!-- auto:clash-rule-count -->27<!-- /auto:clash-rule-count --> 条规则 | provider 不算策略组；分流版另含 3 个倍率子组 |
| mihomo 覆写 | **3 组 / 11 条规则** | **22 组 / 27 条规则** | 分流脚本没有静态模板专属的 3 个倍率子组 |

这里最容易误读两件事：

- Surge / Egern 懒人版看似比 mihomo 多一组，是因为 `Airport` 在前两者中是组，
  在 mihomo 中是 `proxy-provider`，不是功能多一层；
- mihomo 分流静态版比脚本多 `Low Mult.` / `Auto` / `High Mult.` 三个隐藏子组，
  所以是 25 对 22。规则仍同为 27 条，不能据组数判断脚本少了分流规则。

#### 3.2 懒人版

懒人版保留最小的可操作面：

- 订阅 / 节点入口；
- 总代理出口 `Proxy`；
- AI 独立出口；
- 广告处理出口 `AD`（Surge 规则侧可直接使用字面量 REJECT）；
- 白名单、广告、系统 / 内网、AI、国内直连、最终兜底这条主链。

**得到什么**：面板简单、选择少、规则链短，适合“只要稳定代理，不想维护应用级策略”的用户。

**放弃什么**：不能分别指定 ChatGPT、Gemini、Claude、流媒体、社交应用与不同地区；
遇到单个应用风控或区域限制时，只能调整总出口或升级到分流版。

#### 3.3 分流版

分流版把同一条安全骨架展开成应用组与地区组：AI 厂商、媒体、社交、系统更新、
地区测速、最终出口均可独立选择。Surge / Egern 当前是 23 组 / 26 条；mihomo 静态版
因倍率三档为 25 组 / 27 条。

**得到什么**：能为不同应用固定地区、绕开区域限制、把更新与广告处理变成可见开关，
也更容易定位“哪条规则把流量送错组”。

**付出什么**：

- 组名成为规则、图标、筛选正则和文档共同引用的接口；
- 上游规则集更多，死链、误收和内容漂移的攻击面更大；
- 地区正则可能产生空组或交叉命中；
- 改动必须同时验证规则顺序、组引用与远程集可达性。

#### 3.4 两线共用的底线

懒人版不是“删到只剩能跑”。以下能力不能因精简而删除：

- 占位订阅和占位凭据，不携带真实节点；
- 加密 DNS、明文入口收口、fake-ip / real-ip 例外的完整设计；
- IPv6 显式关闭；
- 白名单先于广告、应用规则先于宽泛国内规则、最终规则最后；
- 国内域名直连集与 IP 类 `no-resolve` / `no_resolve` 成对考虑；
- 完整版与 `.min` 版行为一致。

#### 4 · mihomo 的第三种形态：覆写脚本

Surge / Egern 各有“完整版 + `.min`”两种文件表现；mihomo 在此之外多一层**运行时覆写**：

| 产品线 | 静态入口 | 覆写入口 |
|:-------|:---------|:---------|
| 懒人版 | `clash/profiles/lazy.yaml` | `clash/override/my_clash_lazy.js` |
| 分流版 | `clash/profiles/routing.yaml` | `clash/override/my_clash.js` |

#### 4.1 静态版与脚本版分别适合谁

| 维度 | 静态 profile | 覆写脚本 |
|:-----|:-------------|:---------|
| 节点来源 | `proxy-providers.Airport.url`，用户替换占位订阅 | 保留目标订阅已有 `proxies`；有 provider 时自动使用 `include-all` |
| 使用方式 | 下载或订阅完整 YAML | 把脚本绑定到现有订阅 |
| 可审计性 | 高：完整对象可直接解析、diff、离线检查 | 需执行 `main(config)` 后才能看到最终对象 |
| 客户端兼容 | 支持 mihomo profile 即可 | 还要求客户端支持 JavaScript 覆写 |
| 入站端口 | 静态文件可明确给出 | 脚本故意不覆盖，交给客户端 |
| DNS 监听口 | 静态文件可带 `listen` | 脚本不设，避免与客户端端口冲突 |
| 分流版倍率 | 三档隐藏子组 | 单组 fallback；这是已知机制差异 |

#### 4.2 脚本到底改什么

覆写脚本保留订阅节点，整体重建 `proxy-groups`、`rule-providers`、`rules` 与 `dns`，
并显式关闭 IPv6；它不应顺手接管客户端的入站端口。对“已有一份机场订阅，只想套本仓规则”的用户，
这是摩擦最小的入口。

#### 4.3 当前生成关系

mihomo 侧现以覆写脚本为结构源，经
`skill/scripts/clash/build_profiles.py` 生成完整版与 `.min`：

```bash
python skill/scripts/clash/build_profiles.py          # 重生成静态文件
python skill/scripts/clash/build_profiles.py --check  # 只检查是否新鲜
```

生成器强制覆盖写并检查重复顶层键，原因是本仓曾用追加模式把多份 YAML 纵向堆进同一文件；
PyYAML 只取最后一份，门禁看似全绿，真实文件却已畸形。**因此不要手工把脚本输出追加到 profile。**

`check_script_sync.py` 继续对拍规则、规则集 URL、组成员、DNS 与 IPv6；
三档倍率组和 `dns.listen` 是明示白名单，不算漂移。

#### 5 · 选择与切换流程

#### 5.1 决策树

```text
客户端使用哪个内核？
├─ Surge  → surge/
├─ Egern  → egern/
└─ mihomo → clash/
             ├─ 客户端支持覆写、要保留现有订阅节点 → override/*.js
             └─ 要完整 YAML / 客户端不支持覆写       → profiles/*.min.yaml

进入内核后：
├─ 只需 Proxy + AI + 广告处理 → lazy
└─ 要应用组 / 地区组 / 独立开关 → routing
```

#### 5.2 从懒人版切到分流版

1. 备份客户端当前配置和手工策略选择；
2. 选择**同一内核**的 `routing`，不要把两份文件拼接或同时启用；
3. 把占位订阅 / 节点参数替换为自己的本地值，但不要把替换后的文件回推公开仓；
4. 检查地区筛选是否得到非空组；节点命名不匹配时，先调正则，不要改规则出口名；
5. 重新选择应用组出口。很多客户端不会把旧配置里的 UI 选择迁移到新组；
6. 跑内核门禁，并在真实客户端做导入与关键域名冒烟。

#### 5.3 从分流版切回懒人版

切回不是“删除几个组”，而是换用 `lazy` 产品线。应用规则会折叠到 `AI`、`Proxy`、`DIRECT`
与广告出口；原先每个应用组的手工选择不会保留。这样做能显著减少日常操作面，但也意味着
某个应用出问题时不能只切它一个。

#### 5.4 静态版与覆写脚本之间切换

- 从静态转脚本：绑定原订阅，确认脚本确实被客户端执行；不要再把静态 profile 作为第二层覆写；
- 从脚本转静态：在 `proxy-providers.Airport.url` 填本地订阅，取消原脚本绑定；
- 切换后比较最终组数 / 规则数。分流版 25 ↔ 22 的差值应只来自倍率三档；
- 若 DNS、规则顺序或规则集 URL 不同，不是正常形态差异，应由 `check_script_sync.py` 判负。

#### 6 · 各形态取舍总表

| 形态 | 控制粒度 | 节点接入 | 维护成本 | 主要优点 | 主要代价 |
|:-----|:---------|:---------|:---------|:---------|:---------|
| Surge 懒人 | 低 | `Airport` external 组 | 低 | Apple 平台、配置短、出口少 | 无应用 / 地区独立选择 |
| Surge 分流 | 高 | `Airport` external 组 | 中高 | 23 组细分，Surge 原生策略能力完整 | 规则顺序、Smart 与 filter 约束更多 |
| Egern 懒人 | 低 | 隐藏 `Airport` 槽位 | 中 | YAML 可读，保留完整双轨 DNS 收口 | Egern DNS 路径仍需独立理解 |
| Egern 分流 | 高 | 隐藏 `Airport` 槽位 | 高 | 与 Surge 产品目标对齐、应用和地区可控 | `proxy_nameservers` / forward / rule_set 的维护面大 |
| mihomo 懒人静态 | 低 | 单个 provider 占位 | 低 | 下载即用，3 组 / 11 规则 | 需要在文件中填订阅 |
| mihomo 分流静态 | 最高 | provider + 运行时 filter | 高 | 25 组，含倍率三档 | profile、生成器、规则集三者都要同步 |
| mihomo 懒人脚本 | 低 | 复用订阅节点 | 中 | 不改订阅即可套规则；与静态版同构 | 依赖客户端覆写能力 |
| mihomo 分流脚本 | 高 | 复用订阅节点 | 高 | 22 组 / 27 规则，适合动态订阅 | 无静态三档倍率；最终结果需执行后审计 |

#### 7 · 共享什么，不共享什么

#### 7.1 共享资产是单一真源

| 资产 | 真源 | 消费方式 | 维护纪律 |
|:-----|:-----|:---------|:---------|
| 图标 | `icons/` | 三内核都引用本仓同一目录 | 已有同义图标就复用；不要为每个内核复制一份 |
| AI / Apple 系统 / Emby 清单 | `rules/*.list` | Surge / Egern 直接读 `.list` | 只改 `.list` |
| mihomo 规则集 | `rules/*.yaml` | mihomo 以 classical provider 使用 | 由 `build_rules.py` 生成，禁止手改 |
| 机制结论 | `skill/reference/` | 三内核共同引用 | 只放真正跨内核成立的结论 |

整合前，同内容的规则集以 `.list` 与 `.yaml` 各维护一份；现在 `.list` 是真源，
`.yaml` 只是可重建产物。这个边界比“文件看起来一样”更重要。

#### 7.2 内核分歧必须留在各自目录

以下内容不要提炼成伪共享层：

- 语法解析器与重复键行为；
- DNS 生命周期、bootstrap 与 fallback 路径；
- 策略组类型和成员展开；
- `no-resolve` / `no_resolve` 的生效位置；
- 规则集格式、behavior 与缓存方式；
- 覆写脚本可见的输入对象。

共享的是**目标与测试意图**，不是实现文本。例如“三内核都要关闭 IPv6 绕行”是共享目标，
但具体键数量与落点仍由各内核门禁负责。

#### 8 · 新增一个变体要改什么

先回答：它是否服务一个现有两线都无法覆盖的稳定用户任务？若只是“同配置换一套组名”、
“少几条注释”或“一次试验”，不要新增产品线。

确认要新增后，至少完成以下清单：

1. **产品文件**：在对应 `profiles/` 增加完整版与 `.min`；需要历史归档时同步定义 已删除的归档目录 规则；
2. **生成关系**：明确谁是真源。mihomo 若有脚本形态，要扩展 `build_profiles.py` 的目标表；
3. **最小对拍**：把新 pair 加进对应 `check_min_pair.py`，不能靠文件名“看起来成对”；
4. **结构门禁**：让 `check_structure.py` 枚举到新文件，检查组引用、规则指向、IPv6 与 DNS 条件；
5. **脚本对拍**：若有覆写脚本，加入 `check_script_sync.py` 的 pair，并把差异写成最窄白名单；
6. **凭据扫描**：确认后缀在 `check_secrets` 扫描面内；新凭据键加入敏感键集合；
7. **远程资源**：让 URL 收集器能看见字面 URL，也能执行脚本拿到运行期拼接 URL；
8. **共享规则**：能复用 `rules/*.list` 就不复制；需要新格式时增加确定性生成器与 `--check`；
9. **图标**：优先复用 `icons/`，新增文件后检查所有引用均指向本仓；
10. **文档**：更新根 README 下载矩阵、`AGENTS.md`、对应 anatomy / checker / 本文的规模与取舍；
11. **CI**：把门禁挂入 `verify_all.py`，再确认 `.github/workflows/ci.yml` 的线上步骤确实执行；
12. **实机验收**：导入客户端、检查空组、关键规则落点、DNS 与断网重启行为。

**能被现有总入口漏掉的新文件，不算完成接入。**

#### 9 · 新增一个内核要改什么

新增内核不是“再放一个配置文件”，而是新增一条可独立维护的纵向切片。

| 层 | 必须新增 / 修改 | 验收问题 |
|:---|:----------------|:---------|
| 产品目录 | `<kernel>/profiles/`；若生态支持覆写则另设 `override/` | 用户能否只拿这一层独立使用 |
| 版本 / 归档 | 稳定入口名、完整版 / `.min` 关系、历史策略 | 更新是否会破坏固定订阅地址 |
| 内核脚本 | `skill/scripts/<kernel>/` | 能否解析该内核，不借别的内核“猜” |
| 内核门禁 | `skill/tests/<kernel>/` | 坏样例是否真的判负，而非只测现役绿样例 |
| 知识库 | `skill/reference/<kernel>/` | anatomy、checker、泄露定位、坑与公开仓纪律是否齐全 |
| 共享差异 | `reference/rulesets.md` | 同名概念的不同落点是否写清 |
| 共享图标 | `icons/` | 是否复用现有文件；URL 是否指向 `self-conf` |
| 共享规则 | `rules/` + 格式转换器 | 真源是否仍唯一；生成物是否可判陈旧 |
| 脱敏 | 两层 `check_secrets` 或新内核专用扫描 | 新协议字段、保留地址段、证书与 token 是否覆盖 |
| 自洽 | `check_selfcontained.py` 的禁用清单与扫描后缀 | 配置是否引用了本仓之外的在线资源 |
| 总入口 / CI | `verify_all.py` + workflow | 本地、Linux CI、cp936 路径是否都跑到 |
| 门面 | 根 README 的内核矩阵、徽章和适用说明 | 用户能否找到正确入口，不把它误当兼容格式 |

路径探测优先以仓库根 CWD 为锚点，再向上寻找内核特征目录；不要只按 `__file__` 固定上推层数。
本仓已在 Linux CI 上遇到“本地全绿、线上找错目录”的真实事故。

另外要检查新内核的保留地址常识。mihomo 的 fake-ip 保留段曾被 Surge / Egern 的 secrets 判据
当成真实节点地址；正确做法是用规范依据增加**窄白名单**，不是关闭 IPv4 扫描。

#### 10 · 本仓的定位与纪律

三个内核在本仓是**并列关系**，不是主次关系。各自保留实现逻辑与语法，
共享的只有 `icons/` 与 `rules/` 的内容。

几条长线纪律：

- 三个内核各有独立的审计器，验证深度对等（DNS 防泄露 / 地区组 / 分流覆盖 / 规则集内容）；
- 共享资产**单一真源**：改 `rules/*.list` 一处，mihomo 侧的 `.yaml` 由生成器产出；
- 门禁统一在 `verify_all.py`，三个内核一视同仁；
- 判据不足时先补判据，不靠"再跑一遍"或解释为什么脚本是对的。

本仓可以做结构性调整（统一图标 URL、改生成链、改判据形态），代价是结论需要额外证据支撑 —— 见下一节。


#### 11 · 改动何时算稳定（验收清单）

「跑通一次」不等于稳定。建议同时满足以下条件：

1. **机制成立**：有内核文档或最小实测证明，不是因为两个解析器碰巧接受了同一写法；
2. **正向门禁通过**：现役完整 / `.min` / 脚本形态全部绿；
3. **反向判别有效**：注入悬空组、漂移、死链或真实凭据时，对应门禁能稳定判负；
4. **跨环境通过**：本地与 Linux CI 一致，cp936 编码闸门不崩；
5. **生成可复现**：同一真源重复生成得到逐字节相同产物，不依赖个人目录或未入仓脚本；
6. **外部依赖稳定**：至少经过一次计划刷新或定时 CI，确认上游不是瞬时可达；
7. **实机通过**：目标客户端能导入，关键组非空，规则落点与 DNS 行为符合预期；
8. **边界清楚**：明确改动的是规则内容、生成器、判据还是文档结论，不动目录结构。

落地应采用**最小可审查改动**：附上测试命令、坏样例、实机版本和已知差异。
涉及多个内核时，各内核独立验收（各自的审计器跑一遍），而不是「一侧过了就算过」。
共享资产仍要指定唯一真源，不要重新制造双份手工维护。

#### 12 · FAQ

**Q：我同时导入懒人版和分流版，按需切换可以吗？**

可以在客户端保存两份独立配置，但不要把两份合并、叠加或互相 include。切换时要重新确认订阅、
策略选择与地区组是否有效；它们是两套完整产品。

**Q：`.min` 更小，是不是功能也更少？**

不是。`.min` 只去掉注释与空行，解析对象必须与完整版一致。任何行为差异都是 bug。

**Q：mihomo 为什么 README 的组数可能看到 22，而静态分流版是 25？**

22 是覆写脚本的分流结构；静态模板多三个倍率子组，所以是 25。两者规则同为 27 条。

**Q：为什么不让三内核的组数和规则数完全一样？**

因为组、provider、内置集合和规则语义不同。强行对齐数字会制造空组、死规则或错误 DNS 行为。
应对齐用户可观察的结果与安全底线，而不是表面计数。

**Q：我只改了 `rules/AI.list`，还要改三个内核吗？**

Surge / Egern 直接消费 `.list`；mihomo 消费生成的 `.yaml`。因此只改真源，然后运行
`build_rules.py` 生成并检查 mihomo 产物，不要手工改两份。

**Q：新客户端声称兼容 Clash，可以直接用 mihomo 目录吗？**

不能只看“兼容”二字。至少核对 provider format、覆写 API、策略组 filter、fake-ip 与 DNS 键，
再做真实导入。语法能解析不等于行为一致。

#### 13 · 维护者须知

1. **先分类，再改文件**：内核、产品线、交付形态三层中，只改真正变化的那一层。
2. **数字以解析结果为准**：不要用 `grep` 数 YAML，也不要相信可能过期的头注；生成器输出才是当前规模。
3. **mihomo 改脚本后重生成**：运行 `build_profiles.py`，禁止追加写或手改生成出的静态文件。
4. **共享规则只改 `.list`**：随后运行 `build_rules.py`；`.yaml` 是生成物。
5. **本地绿后仍等 CI**：路径、换行、文件时间与控制台编码都曾只在线上暴露。
6. **结论要有证据**：满足 §11 的证据门槛，再提交最小改动。
7. **新增变体或内核必须扩门禁枚举**：未被测试发现的文件，就是无人负责的分叉。

---

相关：[`profiles/<kern>.md`](../profiles/clash.md) · [`gates.md`](../gates.md) ·
[`rulesets.md`](../rulesets.md) · [`AGENTS.md`](../../../AGENTS.md) ·
[`../../../README.md`](../../../README.md)

---

## mihomo · 防泄露推导与实测（clash 侧）

> **何时读**：想彻底弄明白「为什么这么写」时。
> 本文件原为 `clash/DetailsReadme/DetailsReadme.md`，整合进 self-conf 后并入 skill，
> 与 Egern 侧的做法一致（见 [`profiles/egern.md`](./egern.md)）。
>
> ⚠️ **与同目录新文档的分工**：`profiles/<kern>.md` / `hardening-template.md` 是
> 按 SC 规格重写的**现役**文档；本文件是**原始推导与实测读数**，
> §5「明文泄露面实测」与 §6「已知代价与取舍」为本文件独有，其余章节已被新文档覆盖。
>
> 面向想彻底弄明白「为什么这么写」的读者。
> 只想赶紧用起来 → 直接看 [`README`](../../../README.md) 的两份配置。
>
> 目录
> [1 · 先定义「泄露」](#1--先定义泄露) ·
> [2 · 明文查询从哪来：三条出口](#2--明文查询从哪来三条出口) ·
> [3 · `dns` 段逐键](#3--dns-段逐键) ·
> [4 · `tun` 段：收口装置](#4--tun-段收口装置) ·
> [5 · 明文泄露面实测](#5--明文泄露面实测) ·
> [6 · 已知代价与取舍](#6--已知代价与取舍)
>
> 🔜 本文目前覆盖 `dns` / `tun` 两段（防泄露本体）。分流版设计、占位符与脱敏规则等章节随配置落地补齐；
> 规则集清单、来源与刷新机制已由 [`rulesets.md`](../rulesets.md) 承接。

---

#### 1 · 先定义「泄露」

本文所说的 DNS 泄露，**不是**「请求加密了没有」，也不是「权威服务器知道你是谁」。定义收紧到一条：

> 设备发出的、能被链路上的第三方（运营商 / Wi-Fi 提供者 / 旁路设备）直接读到的
> **明文 DNS 查询**，存在任何一条「必然会被走到」的通路。

「必然会被走到」是关键。一个只在极端条件下才发生的明文查询，和每 5 分钟发生一次的明文查询，风险量级完全不同 —— 但配置语法上它们看起来一样。

---

#### 2 · 明文查询从哪来：三条出口

mihomo 的 DNS 是**内核内建**型：解析器在 `dns` 段指定，查询入口在 `tun` 段收口。明文 `UDP:53` 的出口有三条。

#### 2.1 出口 ①：应用直发明文查询

应用（尤其是移动端 App 与 IoT 设备）无视系统设置，直接向 `8.8.8.8:53` 发查询。这既是泄露，也常常是「设备能用但很慢」的原因 —— 境外解析器在国内链路上时通时不通。

**对策**

```
tun:
  auto-route: true        # 自动接管路由表
  strict-route: true      # 流量无法绕开 TUN
  dns-hijack:
    - any:53              # 命中 :53 的连接交给内核 DNS 模块，而不是往外发
```

三者叠加，应用自己发的明文查询会被内核接管并就地应答。语义细节见 §4。

#### 2.2 出口 ②：代理域名的本地真实解析

`enhanced-mode: real-ip`（mihomo 默认）下，本机自己把域名解析成真实 IP，再把 IP 交给代理 —— 那么「本机向谁解析」本身就是泄露面。

**对策**

```
enhanced-mode: fake-ip
fake-ip-range: 198.18.0.1/16
```

命中代理的域名只回一个 `198.18.0.0/16` 段的**假 IP**，真实解析在落地侧（代理出口）完成，本地压根不产生这次真实查询。假 IP 与域名的映射由内核维护，回程按映射表还原，应用侧无感。

**例外**：部分域名拿到假 IP 会直接失效 —— NTP、游戏机联网探测、局域网域名、微软连通性探测。这些需要在 `fake-ip-filter` 里逐个列出，让它们跳过 fake-ip、走真实解析。见 §3.2。

#### 2.3 出口 ③：节点域名解析打转

代理节点的 `server` 写成域名时有个死循环：

```
要连代理 → 得先解析节点域名 → 但这时候还没有代理可用 → 只能明文解析
```

**对策**：`proxy-server-nameserver` 单独承担这件事，与主解析器分离，避免「连节点的解析」和「走节点的解析」互相污染。见 §3.1。

#### 2.4 三处收口之后

| 出口 | 收口手段 |
|:----:|:---------|
| ① 应用直发 | `auto-route` + `strict-route` + `dns-hijack` |
| ② 本地真实解析 | `enhanced-mode: fake-ip` |
| ③ 节点域名 | `proxy-server-nameserver` 单列 |

再加一条结构保障：需要解析的键全部写成加密端点（见 §3.1），所以「为了解析某个 DNS 端点而先发明文查询」这条引导通路只可能落在 `default-nameserver` 上（见 §6）。

注意措辞：是「没有必然通路」，不是「绝对零明文」。一个从没访问过的域名、一次极端网络切换，仍可能产生零星明文。**任何声称「绝对零泄露」的配置都在夸大。**

---

#### 3 · `dns` 段逐键

| 键 | 值 | 作用 |
|:--|:--|:--|
| `enable` | `true` | 启用内核 DNS 模块 |
| `ipv6` | `false` | `AAAA` 查询由内核直接回**空应答**，不往外发 |
| `listen` | `0.0.0.0:7874` | 内核 DNS 服务的监听地址，供局域网设备直接指向 |
| `enhanced-mode` | `fake-ip` | 代理域名只回假 IP |
| `fake-ip-range` | `198.18.0.1/16` | 假 IP 段 |
| `prefer-h3` | `false` | DoH 只用 HTTP/1.1 与 HTTP/2，不尝试 HTTP/3 |
| `respect-rules` | `true` | DNS 查询自身也走路由规则 |
| `use-hosts` | `true` | 优先查配置里的 `hosts` |
| `use-system-hosts` | `false` | 不读系统 hosts 文件 |
| `fake-ip-filter` | 15 条 | 跳过滤假的域名清单 |
| `default-nameserver` | `223.5.5.5` · `119.29.29.29` | 引导解析器 |
| `proxy-server-nameserver` | 国内 DoH ×2 | 节点域名 |
| `direct-nameserver` | 国内 DoH ×2 | `DIRECT` 出站域名 |
| `nameserver` | 境外 DoH ×2 | 主解析器 |
| `nameserver-policy` | `geosite:private,cn` → 国内 DoH | 按域名换解析器 |

#### 3.1 五个解析器键的分工

mihomo 的解析器不是一个，而是各管一段路。混用会让「本不该走代理的域名」或「本不该在本机解析的域名」走错路。

| 键 | 管哪条路 | 本配置的值 |
|:--|:--|:--|
| `nameserver` | 主解析器 —— 需要本地解析出真实 IP 的域名 | 境外 DoH：`dns.cloudflare.com` · `dns.google` |
| `nameserver-policy` | 按域名换解析器（优先于 `nameserver`） | `geosite:private,cn` → 国内 DoH |
| `proxy-server-nameserver` | 代理节点域名（出口 ③） | 国内 DoH：`223.5.5.5` · `120.53.53.53` |
| `direct-nameserver` | `DIRECT` 出站的域名 —— 直连流量也不碰系统 DNS | 国内 DoH：同上 |
| `default-nameserver` | 解析**其他 DNS 服务器自身的域名** | 纯 IP：`223.5.5.5` · `119.29.29.29` |

**为什么 `default-nameserver` 必须是纯 IP**：它本身就是「引导」用的。写成域名，就又需要一次解析，循环回来了。内核对这个键做合法性检查（拆分端口后 host 必须是 IP），并且显式跳过 `system`；该键也不允许为空。

**为什么需要 `nameserver-policy` 这条**：主解析器是境外 DoH，而 `geosite:private,cn`（私有域 + 中国大陆域名）交给境外解析会得到不合用的答案（CDN 调度到境外节点、甚至解析失败），所以这一档单列回国内 DoH。

#### 3.2 `fake-ip-filter`：15 条过滤项与通配语义

| 类 | 条目 | 拿到假 IP 的后果 |
|:--|:--|:--|
| 🏠 局域网 | `*.lan` · `*.local` · `*.localdomain` · `*.home.arpa` | 局域网设备不在代理链路里，假 IP 直接连不上 |
| 🪟 微软联网探测 | `+.msftconnecttest.com` · `+.msftncsi.com` | 探测失败 → 系统判定「无 Internet」并限制联网 |
| 🎮 游戏机 | `+.srv.nintendo.net` · `+.stun.playstation.net` · `+.xboxlive.com` | 联网检测与 NAT 类型判定失败 |
| 🕐 NTP / STUN | `stun.*` · `time.*.com` · `ntp.*.com` · `+.pool.ntp.org` | 时间同步走假 IP 直接失败 |
| 🧩 其他 | `localhost.ptlogin2.qq.com` · `+.market.xiaomi.com` | 登录与应用商店的本地连通性检测 |

**通配语义**（mihomo v1.19.31 实测，`fake-ip-filter` 置入 `+.example.com` / `time.*.com` / `*.lan` 后逐名查询）：

| 模式 | 命中 | 不命中 | 结论 |
|:--|:--|:--|:--|
| `+.example.com` | `example.com` · `a.example.com` · `a.b.example.com` | — | 本域**与**任意层子域 |
| `time.*.com` | `time.a.com` | `time.a.b.com` | `*` 只匹配**一层** |
| `*.lan` | `x.lan` | `a.b.lan` | `*.` 只匹配**一层** |

⚠️ 由此得到一条边界：`*.lan` / `*.local` 只覆盖一层子域，像 `a.b.lan` 这样的多层名字**不会**被过滤。局域网里若有嵌套域名，需要按需补 `+.lan` 这类写法。

命中的域名会**真的去走一次本地真实解析**（用的是主解析器，即加密端点）—— 这是「出口 ②」的代价面，属于设计已知。

#### 3.3 `respect-rules: true` 的连带要求

打开后 DNS 查询自身也受路由规则管辖 —— 好处是发往境外 DoH 的查询会按规则经代理发出。代价是内核**强制要求**同时给出 `proxy-server-nameserver`，缺了直接报错：

```
if "respect-rules" is turned on, "proxy-server-nameserver" cannot be empty
```

（离线门禁 `mihomo -t` 会拦下这一条。）

---

#### 4 · `tun` 段：收口装置

| 键 | 值 | 作用 |
|:--|:--|:--|
| `enable` | `true` | 启用 TUN |
| `stack` | `mips` | IP 协议栈实现，可选 `system` / `gvisor` / `mixed` / `mips` |
| `auto-route` | `true` | 自动接管路由表 |
| `auto-detect-interface` | `true` | 自动识别出接口 |
| `strict-route` | `true` | 流量无法绕开 TUN |
| `dns-hijack` | `any:53` | 命中 `:53` 的连接交给内核 DNS 模块 |

**`dns-hijack` 的语义细节**：不写协议前缀时默认 `udp://`，即 `any:53` 收的是 **UDP**:53。要把 `TCP:53` 也收进来，需要另外加一条 `tcp://any:53`（本配置未加 —— 明文 TCP 查询在现代客户端里已属罕见）。

---

#### 5 · 明文泄露面实测

**方法**：`default-nameserver` 是本配置里唯一还会走明文 `UDP:53` 的键（见 §6）。把它顶到一个本机 DNS sink 上（`127.0.0.1`，记录每个查询的名字与类型）再跑真实解析 —— 内核每一次明文引导都会落到 sink，明文泄露面就变成一份**可枚举的域名清单**。全程 TUN 关闭、只监听回环地址，明文查询不出网。

| 用例 | sink 收到的明文查询 | 涉及域名 |
|:--|:--|:--|
| 基线（`nameserver` 为域名形式 DoH） | 34 条 | 只有 `dns.google` · `dns.cloudflare.com` |
| 重跑（复现性） | 34 条 | 同上 |
| `nameserver` 改为 IP 形式 DoH | 0 条 | 无 |
| DoH 端点不可达 | 0 条 | 无 —— 业务域名解析失败，**不回退明文** |

内核日志里两条并排出现，就是结论本身：

```
[DNS] resolve dns.google A from udp://127.0.0.1:15353                               ← 明文，只有端点自己
[DNS] resolve www.google.com A from https://dns.cloudflare.com:443/dns-query        ← 业务域名，加密
```

**判定**：明文只剩「解析 DoH 端点自身」这一条设计上已知的引导，不含任何业务域名、节点域名、内网域名；把 `nameserver` 换成 IP 形式的端点可做到**零明文**；DoH 全部不可用时不回落明文。

> 两项与泄露无关的观测：`AAAA` 查询会被内核对同一域名重复发起（噪音，不是泄露）；`192.0.2.0/24`（TEST-NET-1）会被内核的 GeoIP 库判为 `private`、命中 `GEOIP,private` 走 `DIRECT` —— 拿保留段做「黑洞」故障注入不干净，要造不可达得用真连不上的公网端口。

---

#### 6 · 已知代价与取舍

| 项 | 代价 | 为什么接受 |
|:--|:--|:--|
| `default-nameserver` 走明文 UDP | 明文暴露「在用哪家 DoH」，不含业务域名 | 它是引导解析，端点写成域名时必然需要一次明文；把 `nameserver` 换成 IP 形式端点可完全消除 |
| `GEOIP,private` / `GEOIP,cn` 不带 `no-resolve` | 走到这两条规则的域名会多触发一次本地解析 | 本地解析走的是加密解析器，不产生明文；代价只是首个请求多一次解析耗时 |
| `stack: mips` | mihomo 自研协议栈，有些场景不如 `gvisor` 稳 | 常规使用足够；遇到兼容性问题换成 `gvisor` 即可 |
| `*.lan` / `*.local` 只覆盖一层子域 | 多层局域网名字不走过滤、会拿到假 IP | 常见 mDNS 名字是单层；需要时改用 `+.lan` |

---

## mihomo · 规则集来源（clash 侧）

> **何时读**：想知道某个规则集为什么选它、以及选型过程中纠正过哪些错误判断时。
> 本文件原为 `clash/docs/01-规则集与来源.md`，整合进 self-conf 后并入 skill。
>
> ⚠️ **与 `ruleset-weight.md` 的分工**：本文件讲**来源与选型决策**
> （§0 三级优先、纠偏记录、为什么移除 blackmatrix7、微信为什么走 `.mrs`）；
> `ruleset-weight.md` 讲**体量与覆盖度**（份数、条目数、AI 覆盖度实测差集）。
>
> 首页只讲「能实现怎样的分流」。这一页是组件清单：用了哪些规则集、各自从哪来、按什么顺序生效。

#### 0 · 选型原则：三级优先

两份配置统一按这一条原则选规则集：

| 层级 | 手段 | 何时用 |
|:----:|:-----|:-------|
| ① | **GEOSITE**（内核数据库） | 首选 —— 不挂远程、最快、最省流量 |
| ② | **内联 `DOMAIN-SUFFIX`** | GeoSite.dat 确实没有的类别，用一条字面规则补上 |
| ③ | **远程规则集**（`rule-providers`） | 需要自定义清单（白名单 / 广告拦截 / 数据库缺的类别）时才挂 |

`GEOSITE` / `GEOIP` 的数据源是 mihomo 内置 `geox-url` 的默认值 ——
[MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) 的官方 release，**每日更新**。

#### 0.1 一次纠偏：Gemini / Claude / 微信到底有没有 GEOSITE 类别

早先的判断是「这三类 GeoSite.dat 里没有独立条目，得退回第三方 classical YAML」——
后半句对 Gemini / Claude 是**错的**，对微信却**是对的**。逐类实测：

| 要分流的东西 | GeoSite.dat 类别 | 记录数 | 现在的走法 |
|:-----|:-----|:--:|:-----|
| Gemini | `google-gemini` | 46 | `GEOSITE,google-gemini` |
| Claude / Anthropic | `anthropic` | 8 | `GEOSITE,anthropic` |
| 腾讯全家桶 | `tencent` | 682 | **不用** —— 会把 QQ / 腾讯云 / 腾讯视频一并收进来 |
| YouTube Music | **无此类别** | — | 内联 `DOMAIN-SUFFIX,music.youtube.com`（详见 §1.2） |

> ⚠️ 判类别是否存在时注意**大小写**：`geosite.dat` 里的类别名是**全大写**（`GOOGLE-GEMINI` / `ANTHROPIC` /
> `TENCENT`），拿小写去比会全部落空、误判成「没有」。

#### 0.2 为什么移除 blackmatrix7

该仓整体仍在更新（`Apple_All_No_Resolve.list` 昨天还动过），但**应用类目早就冻结**：

| 文件 | 最后更新 |
|:-----|:-----|
| `rule/Clash/Gemini/Gemini.yaml` | 2025-06-17 |
| `rule/Clash/Claude/Claude.yaml` | 2025-06-17 |
| `rule/Clash/YouTubeMusic/YouTubeMusic.yaml` | 2025-06-17 |
| `rule/Clash/WeChat/WeChat.yaml` | 2025-06-17 |
| `rule/Surge/Anthropic/Anthropic.list` | **2024-02-02** |

⇒ Gemini / Claude / YouTubeMusic 三类改由 GeoSite.dat 原生承接，零远程依赖、跟着数据库日更；
WeChat 换到上游活跃维护的 `.mrs`（原因见 §0.3）。
分流版的远程规则集因此从 7 份降到 **3 份**，再加回微信那 1 份 = **4 份**。

#### 0.3 微信为什么走远程 `.mrs`，而不是 `GEOSITE,tencent`

`MetaCubeX/meta-rules-dat` 的 `geo/geosite` 目录共 1904 个类别（每个含 `.yaml` / `.mrs` / `.list` 三份），
逐个核过：`wechat` / `weixin` / `wx*` **一个都没有**。最接近的只有 `tencent`（682 条）——
但它是靠 `+.qq.com` 泛化兜住微信的，微信专属域名在里头只有 10 条。
用它就等于把 QQ、腾讯云、腾讯视频一并拖进 `WeChat` 组。

所以 `WeChat` 组改用一份 **30 条纯微信域名**的 `.mrs`：

| 候选源 | 文件更新 | 格式 | 结论 |
|:---|:---|:---|:---|
| [`Lanlan13-14/Rules`](https://github.com/Lanlan13-14/Rules) · `rules/Domain/WeChat.mrs` | 2025-10-28 | `.mrs` | **采用** —— 被大量第三方配置模板引用，生态引用面最广 |
| `Keviin560/Shunt_Rules` · `rule/Mihomo/WeChat.mrs` | 2026-02-12 | `.mrs` | 内容同源（`+.` 形态被内核展开成 60 行） |
| `7ac9d42/Rules` · `rules/Domain/WeChat.mrs` | 2026-08-02 | `.mrs` | 内容同源，29 条 |
| [`ACL4SSR/ACL4SSR`](https://github.com/ACL4SSR/ACL4SSR) · `Clash/Ruleset/Wechat.list` | 2026-01-24 | list | 不提供 `.mrs`，要用得走 `behavior: classical` |

实测三份 `.mrs` 反解并去重后是**同一套域名** —— `weixin.qq.com` / `wx.qq.com` / `wechat.com` /
`weixin.com` / `tenpay.com` / `servicewechat.com` / `qlogo.cn` / `qpic.cn` / `map.qq.com` …，
**不含 `qq.com` 泛化**。微信入口域名本身极稳定，故按生态引用面选 `Lanlan13-14`。

> 内核实测（不是读文档）：`type: http` + `format: mrs` 加载后 `ruleCount = 30`、`behavior = Domain`、`vehicle = HTTP`。

#### 1 · 全部规则集

| 规则集 | 格式 | 行为 | 去向 | 用在哪 | 来源 |
|:-------|:-----|:-----|:-----|:--:|:-----|
| `Jinx-CN` | YAML | `classical` | `DIRECT` | 两份 | [Jinx](https://github.com/RiverFlowsInUUU/Jinx) · `mihomo-direct.yaml`（上游 2026-10-04 由 `*-white-guard.*` 改名而来，旧名已 404） |
| `Jinx-Ads` | YAML | `classical` | `AD` | 两份 | [Jinx](https://github.com/RiverFlowsInUUU/Jinx) · `mihomo-ads.yaml` |
| `AWAvenue-Ads` | `.mrs` | `domain` | `AD` | 两份 | [TG-Twilight/AWAvenue-Ads-Rule](https://github.com/TG-Twilight/AWAvenue-Ads-Rule) · `Filters/AWAvenue-Ads-Rule-Clash.mrs` |
| `AI-Domains` | text | `classical` | `AI` | 仅懒人版 | [self-conf](https://github.com/RiverFlowsInUUU/self-conf) · `rules/AI.list` |
| `apple-system` | text | `classical` | `DIRECT` | 仅懒人版 | [self-conf](https://github.com/RiverFlowsInUUU/self-conf) · `rules/apple_system.list` |

**分流版走的是另一条路**：它不用 `AI-Domains` 与 `apple-system` 这两份自托管清单，
改用数据库里的替代品 —— AI 伴生域由 `GEOSITE,category-ai-chat-!cn` + 各厂商专属类承接，
Apple 则由 `GEOSITE,apple`（1792 条）做**全量直连**（懒人版只要「系统服务」这一精确切面）。

#### 1.1 原生规则（不挂远程，由数据库直接支撑）

| 规则 | 作用 | 懒人版去向 | 分流版去向 |
|:-----|:-----|:-----|:-----|
| `GEOIP,private` / `GEOSITE,private` | 私有 IP 段与私有域名 | `DIRECT` | `DIRECT` |
| `GEOSITE,category-ai-chat-!cn` | 非中国大陆的 AI 服务（188 条） | `AI` | `AI` |
| `GEOSITE,openai` | OpenAI / ChatGPT | - | `ChatGPT` |
| `GEOSITE,google-gemini` | Google 的 AI 服务 | - | `Gemini` |
| `GEOSITE,anthropic` | Anthropic / Claude | - | `Claude` |
| `GEOSITE,spotify` / `youtube` | 媒体 | - | `Spotify` / `YouTube` |
| `GEOSITE,github` / `google` / `microsoft` | 开发与系统 | - | 各自应用组 |
| `GEOSITE,telegram` / `twitter` | 社交 | - | 各自应用组 |
| `GEOSITE,apple` | Apple 全量（1792 条） | - | `DIRECT` |
| `GEOSITE,cn` / `GEOIP,cn` | 国内域名（111224 条）/ 国内 IP 段 | `DIRECT` | `DIRECT` |
| `MATCH` | 兜底 | `Proxy` | `Final` |

> 微信不在这一层 —— 数据库里没有对应类别，它由远程的 `Lanlan-WeChat` 承接（§0.3）。

#### 1.2 唯一一条内联规则：`music.youtube.com`

`geosite.dat` 没有独立的 ytmusic 类别，而 `music.youtube.com` 是 `youtube.com` 的**子域** ——
会被排在后面的 `GEOSITE,youtube` 抢先命中。所以必须在它**之前**单独摘出来：

```yaml
- DOMAIN-SUFFIX,music.youtube.com,YouTubeMusic
- GEOSITE,youtube,YouTube
```

这条不依赖任何远程清单的新鲜度：YouTube Music 的入口域名是稳定的。

#### 1.3 刷新与落盘（Clash 特有）

远程规则集都是 `type: http`，配置里同时给出 `path` 与 `interval`：

| 项 | 值 | 含义 |
|:---|:---|:-----|
| `path` | `./rule_provider/<文件名>` | **先落盘再解析** —— 刷新失败时沿用本地副本，不会因为一次网络抖动丢掉全部规则 |
| `interval` | `86400` | 24 小时刷新一次 |

`.mrs` 是 mihomo 的规则集二进制格式（zstd 压缩，文件头 `28 b5 2f fd`）：省流量、解析更快，代价是可读性差（要看内容得先转回文本）。`behavior` 决定匹配方式 —— `classical` 走完整规则语法，`domain` 只做域名匹配。

#### 2 · 匹配顺序

自上而下，第一条命中即决定去向。懒人版 11 条、分流版 22 条。

**懒人版**：

| # | 规则 | 层级 | 去向 |
|:-:|:-----|:-----|:-----|
| ① | `RULE-SET,jinx-white-guard` | 白名单 | `DIRECT` |
| ② | `RULE-SET,jinx-ads` | 广告拦截 | `AD` |
| ③ | `RULE-SET,AWAvenue-Ads` | 广告拦截 | `AD` |
| ④ | `GEOIP,private` | 内网 | `DIRECT` |
| ⑤ | `GEOSITE,private` | 内网 | `DIRECT` |
| ⑥ | `RULE-SET,apple-system` | Apple 系统服务 | `DIRECT` |
| ⑦ | `GEOSITE,category-ai-chat-!cn` | AI 分流 | `AI` |
| ⑧ | `RULE-SET,AI-Domains` | AI 伴生域 | `AI` |
| ⑨ | `GEOSITE,cn` | 国内域名 | `DIRECT` |
| ⑩ | `GEOIP,cn` | 国内 IP | `DIRECT` |
| ⑪ | `MATCH` | 兜底 | `Proxy` |

**分流版**（把「AI 分流」拆成应用级精细分组，其余结构与懒人版一致）：

| # | 规则 | 层级 | 去向 |
|:-:|:-----|:-----|:-----|
| ①–③ | 白名单 + 广告拦截 ×2 | 同懒人版 | 同上 |
| ④–⑤ | 内网 ×2 | 同懒人版 | `DIRECT` |
| ⑥ | `GEOSITE,openai` | AI 厂商 | `ChatGPT` |
| ⑦ | `GEOSITE,google-gemini` | AI 厂商 | `Gemini` |
| ⑧ | `GEOSITE,anthropic` | AI 厂商 | `Claude` |
| ⑨ | `GEOSITE,category-ai-chat-!cn` | AI 兜底 | `AI` |
| ⑩–⑫ | `spotify` / `music.youtube.com`（内联）/ `youtube` | 媒体 | 各自应用组 |
| ⑬–⑮ | `github` / `google` / `microsoft` | 开发与系统 | 各自应用组 |
| ⑯–⑰ | `telegram` / `twitter` | 社交 | 各自应用组 |
| ⑱ | `GEOSITE,apple` | Apple 全量 | `DIRECT` |
| ⑳–㉑ | `GEOSITE,cn` / `GEOIP,cn` | 国内 | `DIRECT` |
| ㉒ | `MATCH` | 兜底 | `Final` |

#### 3 · 排序约束

1. **白名单必须排在两条广告规则之前** —— `AWAvenue-Ads` 与 `jinx-ads` 存在重叠域名，顺序颠倒会把白名单里的功能域误杀。
2. **两条广告规则并列、同出口** —— 都指向 `AD` 组，一起切才一致（两份配置的 `AD` 组都只有一个 `REJECT` 子策略）。
3. **内网判定（`private`）排在 AI 与国内之前** —— 私有网段与私有域名不应落到任何代理出口。
4. **应用分流必须在国内直连之前** —— 否则「ChatGPT 但域名恰好被国内清单收录」会被直连接走；越具体的越靠前。
5. **AI 厂商专属规则（openai / google-gemini / anthropic）排在通用 AI 兜底（category-ai-chat-!cn）之前** —— 否则 AI 域名会先被兜底接走，轮不到专属组。
6. **`music.youtube.com` 内联规则必须排在 `GEOSITE,youtube` 之前** —— 它是 `youtube.com` 的子域，否则永远轮不到 `YouTubeMusic` 组。
7. **`RULE-SET,Lanlan-WeChat` 必须排在 `GEOSITE,cn` 之前** —— 微信域名同属 `cn` 类，靠前才能落进 `WeChat` 组（出口同为直连，只是把微信从兜底里摘出来）。
8. **国内部分「域名集在前、IP 集在后」** —— 域名命中优先，避免先做一次 IP 判定。
9. **兜底 `MATCH` 必须在最后** —— 它是唯一不带条件的规则，排在前面会吞掉后面全部。

> ⚠️ 两条 `GEOIP` **不带 `no-resolve`**：走到它们的域名会多触发一次本地解析。本地解析走的是加密解析器，不产生明文，代价只是首个请求多一次解析耗时。取舍依据见 [`clash.md`](../profiles/clash.md)（`GEOIP` 行）。

#### 4 · 素材与许可

| 素材 | 用途 | 来源 |
|:-----|:-----|:-----|
| 策略组图标 | 面板图标（引用本仓 `icons/`，40 个，与各内核组名一一对应） | [icons](https://github.com/RiverFlowsInUUU/self-conf/tree/main/icons) |
| 微信规则集 | `WeChat` 组的域名清单（30 条） | [Lanlan13-14/Rules](https://github.com/Lanlan13-14/Rules) · `rules/Domain/WeChat.mrs` |
| `GEOIP` / `GEOSITE` 数据库 | 原生规则的地域判定 | [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) |
| 许可 | 本仓库 | MIT · 见 [`../LICENSE`](../../../LICENSE) |

---

相关：[`clash.md`](../profiles/clash.md) · [`README.md`](../../../README.md)
