# mihomo 配置模板 · 逐键语义与内核行为（profile-anatomy）

> **何时读**：改 mihomo 配置需要确认某个键 / 组 / 规则 / 规则的语义与边界时。
> 本文件是 `skill/reference/clash/` 的第一篇，专讲 mihomo（原 Clash.Meta）侧
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

## 0 · 目录

| # | 节 | # | 节 |
|:-:|:---|:-:|:---|
| 1 | 文件结构与两种交付形态 | 10 | 规则集三级选型与自托管清单 |
| 2 | 两种形态必须逐位一致 | 11 | `rules`：两版顺序与排序约束 |
| 3 | 与 Surge / Egern 的机制差异 | 12 | `no-resolve` 在 mihomo 侧的落点 |
| 4 | 顶层键与 IPv6 双写 | 13 | `dns` 段：五个解析器键 |
| 5 | 节点来源：`proxies` · `proxy-providers` | 14 | 双层广告拦截的两个必要条件 |
| 6 | 节点入组的三件套 | 15 | `fake-ip-filter` 的通配语义 |
| 7 | Smart 三档倍率 fallback | 16 | 已知取舍 |
| 8 | 策略组全表与 `filter` | 17 | FAQ |
| 9 | rule-providers：三种 format × 三种 behavior | 18 | 维护者须知 |

## 1 · 文件结构与两种交付形态

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
│   └── （文档已并入 skill/reference/clash/）
│   └── CHANGELOG.md
├── rules/                                    # 共享规则集真源（.list）+ 生成物（.yaml）
├── icons/                                    # 38 个图标 PNG，三内核共用
└── skill/                                    # AI 知识库
    ├── SKILL.md                              # 维护手册（分歧 / 踩过的坑）
    ├── reference/shared/ · surge/ · egern/ · clash/（本文）
    ├── scripts/clash/build_rules.py          # .list → .yaml 生成器
    └── tests/clash/                          # mihomo 专属门禁 5 个
```

**两份 profile 是分工关系，不是版本关系**：

| | 分流版 `routing` | 懒人版 `lazy` |
|:--|:--|:--|
| 策略组 | **25** | **3**（`Proxy` / `AI` / `AD`） |
| 规则 | **27** | **11** |
| rule-providers | **25**（20 `.mrs` + 5 `.yaml`） | **10**（6 `.mrs` + 4 `.yaml`） |
| 取向 | 按应用 + 按地区细分 | 全量流量一个出口 |

选一份用，不要叠加。

### 1.1 第二种交付形态：覆写脚本

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

### 1.2 两形态的结构差：不是同一套数字

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

> 📌 两份脚本与两份 profile 的头注里还写着旧数字
> （`routing.yaml` 头注「23 个策略组 / 22 份规则集 / 24 条规则」、
> `my_clash.js` 头注「20 个策略组 / 20 份规则集 / 26 条规则」），
> 与当前实际（25 / 25 / 27）不符 —— 见 §18.4。

## 2 · 两种形态必须逐位一致

### 2.1 为什么需要这条判据

静态文件与覆写脚本是**同一套配置**的两种交付形态。一旦漂移，用户会遇到：

> 「照文档用脚本订阅，效果跟直接导入配置文件不一样」

**而且两边都能正常跑、都不报错** —— 没有任何一个环节会提示你。这种漂移只能靠对拍发现。

这是本仓特有的一条判据：姊妹仓 `Self-Configuration` 的 Surge / Egern 侧
只有「完整版 ↔ .min 版」的对拍，没有「脚本 ↔ 静态」这一层。

### 2.2 判据（`skill/tests/clash/check_script_sync.py`）

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

### 2.3 「打印但不判负」的分寸

`Smart` 是唯一一处**已知且有意**的差异。脚本跑完会打印：

```
     ~ 已知差异 Smart: 模板三档 fallback vs 脚本单组 fallback（机制差异，非漂移）
  OK override/my_clash.js
  OK override/my_clash_lazy.js
```

⚠️ 这条提醒必须**保留可见**。它若被静默吞掉，后来者会把「脚本侧没有三档」当成漏写，
于是去改脚本 —— 而那是改不动的（§7.2）。

### 2.4 与「.min 对拍」是两条独立的判据

| 门禁 | 比对 | 判据 |
|:-----|:-----|:-----|
| `check_min_pair.py` | `routing.yaml` ↔ `routing.min.yaml`（`lazy` 同） | YAML 解析成对象后**直接比对象**，任何一处不同即判负 |
| `check_script_sync.py` | `my_clash.js` ↔ `routing.yaml`（`lazy` 同） | 见 §2.2 |

> `.min` 的定位是「**同一份配置去掉注释**」，不是「裁剪配置」。
> 本仓踩过：`routing.yaml` 由脚本重新生成后忘了同步重生成 `.min`，两份就不一致，
> 而静态文件**不会报错**。

两套判据都跳过注释 / 键序 / 缩进 / 引号风格 —— YAML 解析后比对象，
所以「改了个引号」不会被判负，「改了个值」才会。

## 3 · 与 Surge / Egern 的机制差异

三内核共用 `rules/` 与 `icons/`，但机制差异决定了**不能互相照搬写法**。
完整对照见 [`../shared/cross-kernel-diff.md`](../shared/cross-kernel-diff.md)（Surge ↔ Egern），
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

## 4 · 顶层键与 IPv6 双写

### 4.1 顶层键清单

两份 profile 的顶层键完全相同（`routing` 与 `lazy` 只是顺序略有差别）：

```yaml
ipv6: false          # ← 第 ① 处
proxies: []          # 节点（空；节点来自订阅）
proxy-providers:     # 订阅槽位 Airport
proxy-groups:        # 策略组
rule-providers:      # 规则集
rules:               # 分流规则
dns:                 # DNS（含 ipv6: false ← 第 ② 处）
tun:                 # TUN 收口装置
```

### 4.2 IPv6 必须关两处

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

### 4.3 `proxies: []` —— 空段是有意的

两份 profile 的 `proxies` 都是空数组，节点全部来自 `Airport` 订阅。
理由写在 `lazy.yaml` 头注里：**只填一个订阅 URL 即可导入，不需要手工补节点**。

> 如果你有自己的固定节点，直接写进 `proxies`，它们与订阅节点合并进各组。
> 节点 `server` 写 IP 字面量 ⇒ 不产生「解析节点域名」这一次查询（出口 ③，见
> [`verification.md`](../../../skill/reference/clash/verification.md) §2.3）。

## 5 · 节点来源：`proxies` · `proxy-providers`

### 5.1 `proxy-providers`：订阅槽位

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

### 5.2 占位符与脱敏

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

## 6 · 节点入组的三件套：`use` / `include-all` / `include-all-proxies`

这是 mihomo 最容易写错的一组键，三者**不是别名**：

| 键 | 引入什么 | 顺序 |
|:--|:---------|:-----|
| `use: [Airport]` | **指定名字的** proxy-provider（可多个） | 按 provider 内顺序 |
| `include-all-proxies: true` | 所有 `proxies` 段里的**内联节点** | **按名称排序** |
| `include-all: true` | 所有 `proxies` **+ 所有** proxy-providers | **按名称排序** |
| `include-all-providers: true` | 所有 proxy-providers | **按名称排序** |

### 6.1 坑一：`include-all` 会覆盖 `use`

官方字段说明里 `include-all` = 引入**所有出站代理以及代理集合**。
所以一旦写了 `include-all: true`，`use` 指定的那一个 provider **也会被它包进去** ——
`use` 就变成了空转。

- 只有**一个** provider 时两者等价，看不出区别；
- 日后加了第二个 provider、又只想用其中一个，就必须**去掉 `include-all`、只留 `use`**。

这条已写进 `lazy.yaml` 策略组段的注释里。

### 6.2 坑二：`include-all-proxies` 看不到 provider 里的节点

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

### 6.3 坑三：`filter` 作用于**合并后**的成员列表

按内核 `groupbase.go` 的 `GetProxies()`，`filter` / `exclude-filter` 作用于
**最终合并后的成员列表** —— 也就是说，由 `include-all-proxies` / `use` 引入的节点**同样被筛**。

这正是地区组「不写成员表、只写 `filter`」能成立的原因（§8.3）。

对比 Surge：Surge 的 `policy-regex-filter` **对显式列在 `[Proxy Group]` 里的成员不生效**，
要让它生效必须同时开 `include-all-proxies=true`。**两内核这条规则正好相反**，移植时务必重查。

### 6.4 两个筛选键的分工

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

## 7 · Smart 三档倍率 fallback

> 🧠 这是**模板专属**结构，脚本侧没有。分流版才有（`lazy` 的 `Proxy` 是单组 `url-test`）。

### 7.1 结构

```
Proxy (select)
  └── Smart (fallback)  ← 依次回落，不是择优
        ├── Low Mult.   (url-test, hidden)  ← 倍率 < 1 的节点（0.01 / 0.1 / 0.5 …）· 最省钱，优先
        ├── Auto        (url-test, hidden)  ← 正常倍率节点（节点名无倍率标记）
        └── High Mult.  (url-test, hidden)  ← 倍率 > 1 的节点（1.5倍 / 2倍 / 3.0x …）· 最贵，兜底
```

三个子组都是 `include-all: true` + `filter` + `hidden: true` ——
**成员表是空的**，全靠 `filter` 在运行时从全池里筛。

### 7.2 为什么脚本做不到

| | 静态模板 | 覆写脚本 |
|:--|:---------|:---------|
| 分档时机 | **运行时**（`filter` 每次求值时筛） | 生成期（脚本执行一次） |
| 能看到节点名吗 | 能（provider 已加载） | **不能** —— 脚本在订阅加载时跑，`proxies` 里还没有 provider 的节点 |
| 结果 | 三档，倍率语义化 | 单组 `fallback`，成员顺序由 `sortedByRate()` 按名排出 |

脚本侧的替代方案（`my_clash.js`）：

```js
function rateOf(name) {
  var m = String(name || "").match(/(?:^|[^\d.])(0\.\d*[1-9])/);
  return m ? parseFloat(m[1]) : null;
}
function sortedByRate(names) { /* 低倍率在前，无倍率排最后，同倍率保持订阅原顺序 */ }
// Smart 的 proxies = sortedByRate(usable)
```

⇒ **脚本只能排序，不能分档。** 而且它的 `rateOf()` 只认低倍率（`0.` 开头），
抓不到「高倍率」那一档 —— 高倍率节点在脚本侧混在「无倍率」里排最后。
模板侧三档把这两种语义**显式分开**，这是二者真正的差距。

### 7.3 倍率判据（消歧靠「倍率单位」）

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

### 7.4 `fallback` 与 `url-test` 的语义差

| 类型 | 语义 |
|:--|:-----|
| `url-test` | **择优** —— 定时测速，选延迟最低的（带 `tolerance: 50`，差距在 50 ms 内不换） |
| `fallback` | **回落** —— 按成员顺序取第一个可用的，**不比较延迟** |

⇒ `Smart` 用 `fallback` 是刻意的：**三档之间有明确优先级（省钱优先），不该按延迟打断这个顺序**；
档内才是 `url-test` 择优。

## 8 · 策略组全表与 `filter`

### 8.1 分流版 25 组

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

### 8.2 懒人版 3 组

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

### 8.3 地区组靠 `filter` 筛，不写成员表

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
> mihomo 侧目前**没有**这个比对器 —— 改地区正则时六处要一起改，见 §18.2。

### 8.4 `hidden: true` 只用于三档子组

三个倍率子组（`Low Mult.` / `Auto` / `High Mult.`）都带 `hidden: true` ——
它们是 `Smart` 的内部实现，不该出现在面板上让人手动选。

`Airport` 在 mihomo 侧是 `proxy-providers` 里的槽位，本来就不是一个组，
所以**没有** Surge / Egern 侧那个 `hidden=true` 的订阅组。

## 9 · rule-providers：三种 format × 三种 behavior

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

### 9.1 `format`：三种

| format | 内容形态 | 优点 | 缺点 |
|:-------|:---------|:-----|:-----|
| `mrs` | mihomo **二进制**规则集（zstd 压缩，文件头 `28 b5 2f fd`） | 省流量、解析快 | 可读性差（要看内容得先转回文本） |
| `yaml` | `payload:` 下列规则行 | 可读、可 diff | 体积大 |
| 文本 | 一行一条规则 | 最简单 | 无结构 |

官方：`format` 可选 `yaml` / `text` / `mrs`，**默认 `yaml`**。

> 🔧 转换工具：`mihomo convert-ruleset domain/ipcidr yaml/text XXX.yaml XXX.mrs`

### 9.2 `behavior`：三种

| behavior | 匹配方式 | 内容要求 |
|:---------|:---------|:---------|
| `domain` | 只做**域名**匹配 | 纯域名清单 |
| `ipcidr` | 只做 **IP 段**匹配 | 纯 IP-CIDR 清单 |
| `classical` | 走**完整规则语法**（`DOMAIN-SUFFIX,xxx` / `DOMAIN-KEYWORD,xxx` …） | 完整规则行 |

> ⚠️ **`format: mrs` 的 `behavior` 只支持 `domain` / `ipcidr`**（官方明示）。
> 想要 `classical` 语义就得用 `yaml` 或文本格式 —— 本仓 5 份 `classical` 集**全部**是 `format: yaml`，
> 这不是巧合，是 format 的能力边界决定的。

### 9.3 本仓的实际组合

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

### 9.4 `behavior` 选错的后果

选错**不报错**，只是静默失配：

- `domain` 集合里混了 `DOMAIN-SUFFIX,xxx` 这种完整规则行 ⇒ 每行被当成一个**域名**，
  永远匹配不上 ⇒ 整份集变成空集；
- `classical` 写成 `domain` ⇒ 同上；
- `ipcidr` 集合里混了域名 ⇒ 域名不是合法 CIDR，整份集解析失败或退化成空集。

⇒ 判据：**先落一份样本看内容形态，再定 `behavior`**，不要照抄别人的配置。
`ruleset-sources.md` §0.1 记过一次这类纠偏（「Gemini / Claude 没有独立类别」是错的）。

### 9.5 `path` 与 `interval`：为什么必须给

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

## 10 · 规则集三级选型与自托管清单

### 10.1 三级优先

两份配置统一按这一条原则选规则集：

| 层级 | 手段 | 何时用 |
|:----:|:-----|:-------|
| ① | **`GEOSITE` / `GEOIP`**（内核数据库） | 首选 —— 不挂远程、最快、最省流量 |
| ② | **内联 `DOMAIN-SUFFIX`** | 数据库确实没有的类别，用一条字面规则补上 |
| ③ | **远程规则集**（`rule-providers`） | 需要自定义清单（白名单 / 广告拦截 / 数据库缺的类别）时才挂 |

### 10.2 一次转向：从原生 `GEOSITE` 改成远程 `.mrs`

分流版的历史形态是 17 条 `GEOSITE,xxx` / `GEOIP,xxx` 原生规则
（对应层级 ①）。后来**全部改成 `RULE-SET,xxx` 远程 `.mrs`**（层级 ③），
新增 13 份 geosite `.mrs` + 4 份 geoip `.mrs` 的 provider 定义。

现在的分流版 `rules` 里**没有一条** `GEOSITE` / `GEOIP` 字面规则 ——
25 份远程集全部走 `RULE-SET`。

⚠️ 因此 §10.1 的「三级优先」描述的是**选型思想**，不是当前文件的字面形态。
当前形态是「远程 MRS 为主 + 5 份自定义 classical + 1 条内联」。
这条差异也写进了 [`ruleset-sources.md`](../../../skill/reference/clash/ruleset-sources.md) §1.3。

### 10.3 `interval: 86400`（一天）

mihomo 侧所有远程规则集统一 `interval: 86400`。

> ⚠️ **这与姊妹仓的 604800（一周）不一致，是刻意的**：
> 两内核的键语义与缺省值都不同（Surge 官方写明 `RULE-SET` 缺省 86400、只有**负值**才关闭自动更新；
> Egern 缺省值未文档化）。本仓 mihomo 侧按自己的节奏钉一天，不强行对齐。

### 10.4 本仓自托管清单（`rules/`，全部 `format: yaml` + `classical`）

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

### 10.5 唯一一条内联规则：`music.youtube.com`

`geosite.dat` 没有独立的 ytmusic 类别，而 `music.youtube.com` 是 `youtube.com` 的**子域**
—— 会被排在后面的 `RULE-SET,youtube,YouTube` 抢先命中。所以必须在它**之前**单独摘出来：

```yaml
- DOMAIN-SUFFIX,music.youtube.com,YouTube Music     # 位 13
- RULE-SET,youtube,YouTube                          # 位 15
```

它不依赖任何远程清单的新鲜度：YouTube Music 的入口域名是稳定的。

> 📌 脚本里也保留这条内联（注释写明：上游的 Clash 版清单也只有这一条，
> 与硬编码等效且无增益，挂远程反而多一次拉取）。

## 11 · `rules`：两版顺序与排序约束

`rules` 是**有序的** —— 自上而下匹配，**第一条命中即决定去向**。

### 11.1 分流版 27 条

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

### 11.2 懒人版 11 条

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

### 11.3 五条排序约束

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

### 11.4 `Apple Update` 与 `apple-system` 的相对位置

位 4（`apple-update` → `Apple Update` 组）排在位 5（`apple-system` → `DIRECT`）**之前**。

两集有重叠域名（`configuration.apple.com` / `mesu.apple.com` / `xp.apple.com`），
`apple-system` 会先把它们接成 `DIRECT`；排在后面 `Apple Update` 组就永远轮不到那几条。

⇒ 这是「**因规则集包含关系而前移**」，与 `music.youtube.com` 同性质。

## 12 · `no-resolve` 在 mihomo 侧的落点

### 12.1 同一条原则，三个内核落点不同

原则是：**实测零 IP 条目的规则集不写 `no-resolve`，真含 IP 的必须写**。

| 内核 | 落点 |
|:--|:--|
| Surge | 写在**规则行末尾**（`GEOIP,CN,DIRECT,no-resolve`） |
| Egern | `no_resolve` 字段，**仅对 `geoip` / `ip_cidr` / `ip_cidr6` / `asn` 四类生效**，写在 `rule_set` 上**不生效** |
| **mihomo** | 写在**规则行末尾**（`RULE-SET,geoip-cn,DIRECT,no-resolve`），与 Surge 同 |

### 12.2 双刃（与 Surge 同）

| 写法 | 后果 |
|:-----|:-----|
| 不带 `no-resolve` | 走到这条 IP 规则的域名会**先触发一次本地解析** |
| 带上 `no-resolve` | 对**尚未解析**的主机名直接跳过 ⇒ 「解析出来发现是国内 IP 就直连」这条路**也一起没了** |

⇒ 所以必须**成对交付**（姊妹仓 `surge/profile-anatomy.md` §12.4）：

> **A** —— 真含 IP 的规则带 `no-resolve`
> **B** —— `MATCH` 之前有一个**域名体量足够**的国内直连规则集

本仓的 B 是 `cn`（`geosite:cn` 同源，10 万+ 条域名），排在 `geoip-cn` 之前。

### 12.3 本仓的实际落点

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

## 13 · `dns` 段：五个解析器键

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

### 13.1 `default-nameserver` 必须纯 IP

它本身就是「引导」用的。写成域名，就又需要一次解析，循环回来了。
内核对这个键做合法性检查（拆分端口后 host 必须是 IP），并显式跳过 `system`；该键**不允许为空**。

> 🔎 本段真正需要它的只有 `dns.cloudflare.com` 与 `dns.google` 两条
> （`nameserver` / `fallback` 写成主机名端点）。其余键都写成 IP 端点，不需要任何引导。
> ⇒ 把 `nameserver` 换成 IP 形式的端点（`https://1.1.1.1/dns-query`）即可做到**零明文**
> （实测见 `verification.md` §5：34 条明文 → 0 条）。

### 13.2 `respect-rules: true` 的连带要求

打开后 DNS 查询自身也受路由规则管辖 —— 好处是发往境外 DoH 的查询会按规则经代理发出。
代价是内核**强制要求**同时给出 `proxy-server-nameserver`，缺了直接报错：

```
if "respect-rules" is turned on, "proxy-server-nameserver" cannot be empty
```

（离线门禁 `mihomo -t` 会拦下这一条。）

> ⚠️ 官方还写明：强烈不建议和 `prefer-h3` 一起使用。本仓 `prefer-h3: false`，无冲突。

### 13.3 `fallback` / `fallback-filter` 只在分流版

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

### 13.4 其余键

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

## 14 · 双层广告拦截的两个必要条件

这是本仓**最容易静默失效**的一处 —— 缺一条就不生效，且**不报错**。

### 14.1 两层怎么配合

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

### 14.2 两个必要条件

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

### 14.3 第三个条件：顺序

`nameserver-policy` 里广告两项**必须排在** `private,cn` 之前 ——
否则先命中 `cn` 就拿不到空回答（广告域名里有一批是 `.cn`）。

门禁也守这一条：

```python
if cn_idx and ads_idx and min(ads_idx) > min(cn_idx):
    errs.append("广告 policy 排在 cn 之后 —— 会先命中 cn 而拿不到空回答")
```

### 14.4 两处的键名形态不同

| 配置 | 第三个 policy 键 |
|:-----|:-----------------|
| 分流版 | `rule-set:private,cn` |
| 懒人版 | `geosite:private,cn` |

两者都能工作（`rule-set:` 引用本仓已声明的 provider；`geosite:` 直接查内核数据库），
但**写法不统一**。改这两份时别互相照抄 —— 见 §18.2。

### 14.5 与 Surge / Egern 的对比

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

## 15 · `fake-ip-filter` 的通配语义

### 15.1 17 条：15 条功能域 + 2 条广告集

| 类 | 条目 | 拿到假 IP 的后果 |
|:--|:-----|:-----------------|
| 🏠 局域网 | `*.lan` · `*.local` · `*.localdomain` · `*.home.arpa` | 局域网设备不在代理链路里，假 IP 直接连不上 |
| 🪟 微软联网探测 | `+.msftconnecttest.com` · `+.msftncsi.com` | 探测失败 → 系统判定「无 Internet」并限制联网 |
| 🎮 游戏机 | `+.srv.nintendo.net` · `+.stun.playstation.net` · `+.xboxlive.com` | 联网检测与 NAT 类型判定失败 |
| 🕐 NTP / STUN | `stun.*` · `time.*.com` · `ntp.*.com` · `+.pool.ntp.org` | 时间同步走假 IP 直接失败 |
| 🧩 其他 | `localhost.ptlogin2.qq.com` · `+.market.xiaomi.com` | 登录与应用商店的本地连通性检测 |
| 🚫 广告 | `rule-set:AWAvenue-Ads` · `rule-set:Jinx-Ads` | **必须与 `nameserver-policy` 一一对应**（§14.2） |

### 15.2 三种通配符的语义（v1.19.31 实测）

| 模式 | 命中 | 不命中 | 结论 |
|:--|:--|:--|:--|
| `+.example.com` | `example.com` · `a.example.com` · `a.b.example.com` | — | 本域**与**任意层子域 |
| `time.*.com` | `time.a.com` | `time.a.b.com` | `*` 只匹配**一层** |
| `*.lan` | `x.lan` | `a.b.lan` | `*.` 只匹配**一层** |

> ⚠️ 由此得到一条边界：`*.lan` / `*.local` 只覆盖一层子域，
> 像 `a.b.lan` 这样的多层名字**不会**被过滤 ⇒ 需要时用 `+.lan`。

> ⚠️ 官方还定义了 `.example.com`（匹配子域但**不含**本域）。本仓不用这种写法。

### 15.3 `rule-set:` 前缀的能力边界

官方明示：**`rule-set` 仅支持 `behavior` 为 `domain` / `classical`**。

本仓两份广告集正好落在这两类上：

| 集 | behavior | 可用 |
|:--|:---------|:--:|
| `AWAvenue-Ads` | `domain` | ✅ |
| `Jinx-Ads` | `classical` | ✅（classical 时**仅生效其中的域名类规则**） |
| `geoip-cn` 之类 | `ipcidr` | ❌ 放进 `fake-ip-filter` 无意义 |

### 15.4 命中的代价

命中的域名会**真的去走一次本地真实解析**（用的是主解析器，即加密端点）
—— 这是「出口 ②」的代价面，属于设计已知。

### 15.5 与 Surge `always-real-ip` 的关系

Surge 的 `always-real-ip` 与 mihomo 的 `fake-ip-filter` 是**同一件事的两种载体**，
但有一处关键差异：

| | Surge `always-real-ip` | mihomo `fake-ip-filter` |
|:--|:-----------------------|:------------------------|
| 改变流量目的地吗 | ❌ 只改变返回真实 IP 还是 Fake-IP，**不参与分流** | ❌ 同 |
| 额外能力 | — | ✅ 可挂 `rule-set:` 引用整个规则集（Surge 只能列举） |

⇒ mihomo 侧把「广告集跳过 fake-ip」也挂进了同一个键，这是 Surge 做不到的
（Surge 必须靠 `pre-matching` 在规则层拦）。

## 16 · 已知取舍

### 16.1 一份配置两种交付形态，靠对拍兜底

静态文件与覆写脚本必须逐位一致（§2）。这带来一条持续成本：
**任何一处改动都要写两遍**（`.yaml` 与 `.js`），只改一处会被 `check_script_sync.py` 拦下。

代价换来的是：用户既能「下载即用」，也能「保留自己的订阅」。
这是 mihomo 生态特有的能力（JS 覆写），Surge / Egern 都没有对应物。

### 16.2 Smart 三档只存在于模板

脚本侧做不到倍率分档（§7.2），只能用 `sortedByRate()` 排出一个顺序。
`check_script_sync.py` 把它列为**已知差异**，打印提醒但不判负。

⇒ 用户用脚本订阅时，`Smart` 是单组 `fallback`（按倍率升序排列的节点），
而不是三档。这是**机制决定的**，不是漏实现。

### 16.3 `no-resolve` 只给真含 IP 的规则

分流版只给 `geoip-private` 一条带上 `no-resolve`，`geoip-cn` 不带（§12.3）。
走到 `geoip-cn` 的域名会多触发一次本地解析 —— 本地解析走的是加密解析器，
不产生明文，代价只是首个请求多一次解析耗时。

### 16.4 规则集全面远程化（.mrs）

17 条原生 `GEOSITE` / `GEOIP` 改成远程 `.mrs`（§10.2），换来的是：

| | 原生 `GEOSITE` | 远程 `.mrs` |
|:--|:--|:--|
| 依赖 | 依赖 `geosite.dat` / `geoip.dat` 数据库文件与 `geox-url` | 只依赖一次 HTTP 拉取 |
| 新鲜度 | 跟着数据库更新 | 跟着 `interval` 与上游 |
| 落盘 | 无 | ✅ `path` 落盘，离线可用 |
| 体量 | 数据库全量加载 | 按需、zstd 压缩 |

代价：多一次网络依赖（死链会静默降级成空集，§9.5）。

### 16.5 IPv6 关两处，不是一处

见 §4.2。只关一处会漏 —— 这是 mihomo 与另两个内核的结构差异
（Surge 是 `ipv6` + `ipv6-vif`，Egern 只要 `ipv6`）。

### 16.6 `dns-hijack: any:53` 只收 UDP

官方语义：不写协议前缀时默认 `udp://` ⇒ `any:53` 收的是 **UDP**:53。
要把 `TCP:53` 也收进来，需要另外加一条 `tcp://any:53`（本配置**未加**）。

理由：明文 TCP 查询在现代客户端里已属罕见，加了会多接管一条通路。
需要覆盖时加一行即可。

### 16.7 `stack: mips`

mihomo 自研的 IP 协议栈（可选 `system` / `gvisor` / `mixed` / `mips`）。
常规使用足够；遇到兼容性问题换成 `gvisor` 即可。

### 16.8 刷新周期与姊妹仓不同（86400 vs 604800）

见 §10.3。mihomo 侧钉一天，Surge / Egern 侧钉一周。
**不强行对齐** —— 两内核的键语义与缺省值都不同，对齐只是徒增困惑。

## 17 · FAQ

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
（且脚本的 `rateOf()` 只认低倍率 `0.xxx`，高倍率节点混在「无倍率」里排最后）。

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

## 18 · 维护者须知

### 18.1 改动前必须知道的四条

1. **一处改动要写（最多）四处**：静态 `.yaml` + `.min.yaml` + 覆写 `.js` + （若动规则集内容）`rules/*.list`。
   前三者由两个门禁兜底：`check_min_pair.py`（.min 对拍）与 `check_script_sync.py`（脚本对拍）。
2. **规则顺序铁律不许破**：白名单 → REJECT → 应用分流 → 国内域名 → 国内 IP → `MATCH`（§11.3）。
3. **节点不许提交真实值**：`check_secrets.py` 会拦（§5.2）。
4. **`rules/*.yaml` 是生成物**：改真源 `.list` 后重跑 `build_rules.py`（§10.4）。

### 18.2 一处已知的文档 / 配置漂移（改之前先读）

| 位置 | 写的 | 实际 | 性质 |
|:--|:--|:--|:--|
| `routing.yaml` 头注 | 23 个策略组 / 22 份规则集 / 24 条规则 | **25 / 25 / 27** | 头注过期 |
| `my_clash.js` 头注 | 20 个策略组 / 20 份规则集 / 26 条规则 | **22 / 25 / 27** | 头注过期 |
| `lazy.yaml` 头注 | 5 份 MRS + 5 份 yaml | **6 mrs + 4 yaml** | 头注过期 |
| `lazy.yaml` 规则注释 | 「两条 GEOIP **不带** `no-resolve`」 | 两条**都带** | 注释过期 |
| `override/README.md` 表格 | 「整体替换为 20 组」「26 条」 | 22 组 / 27 条 | 文档过期 |
| 分流版 vs 懒人版 | `nameserver-policy` 第三个键 `rule-set:private,cn` vs `geosite:private,cn` | 两版写法不同 | 见 §14.4 |
| 分流版位 26 | `geoip-cn` **不带** `no-resolve`；懒人版位 10 **带** | 两版不同 | 见 §12.3 |

> ⚠️ 判据**以配置文件为准**，注释与文档是辅助。改配置时顺手把这些过期文字一起改掉。

### 18.3 `routing.yaml` 的拼接残留（**必须先清理再改**）

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
   这正是 [`SKILL.md`](../../SKILL.md) §7 那条「**本地全绿 ≠ 线上能跑**」的同类。
2. **在文件里搜索会命中多处**，`grep -c` 得到的数字是 7 倍。
   本文所有数字（25 / 27 / 25）取的是**解析后的结果**与**最后一块**，不是 grep 计数。
3. **改文件时极易改错块** —— 改到第 1 块等于没改。

⇒ 处理办法：重新生成一次 `routing.yaml`（内容取最后一块），再重跑全部门禁。
**在清理之前，任何对 `routing.yaml` 的编辑都要先确认自己改的是最后一块。**

### 18.4 门禁清单与跑法

```bash
python skill/tests/clash/check_structure.py      # 悬空引用 / 规则指向 / 双条件 / IPv6
python skill/tests/clash/check_min_pair.py       # .yaml ↔ .min.yaml 对象对拍
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
> —— 而 1 恰是「判负」的码。`_clash_common.utf8_stdout()` 就是为这个存在的。

### 18.5 路径探测用 CWD 优先

四个 clash 门禁的 `_default_root()` 都是「**当前工作目录 → 逐级向上 + `/clash`**」，
找到同时含 `profiles/` 与 `override/` 的目录为止。

原因写在每个脚本的注释里：**CI 上 `__file__` 探测会算错目录**
（实测 GitHub Actions 上基于 `__file__` 向上推算失败，报「缺文件」而本地全过）。
⇒ 从仓库根调用，不要从脚本所在目录调用。

### 18.6 与姊妹仓的边界

- ❌ 不为了本仓测试变绿去改其他仓库；
- ⚠️ `rules/` 是三内核共享真源，改 `.list` 会影响 Surge / Egern 两侧；
- ⚠️ 结构性调整需先补判据，不靠"再跑一遍"。

---

相关：[`../shared/cross-kernel-diff.md`](../shared/cross-kernel-diff.md) ·
[`../shared/no-resolve-pairing.md`](../shared/no-resolve-pairing.md) ·
[`../../../clash/override/README.md`](../../../clash/override/README.md) ·
[`../../../skill/reference/clash/ruleset-sources.md`](../../../skill/reference/clash/ruleset-sources.md) ·
[`../../../skill/reference/clash/verification.md`](../../../skill/reference/clash/verification.md) ·
[`../../SKILL.md`](../../SKILL.md)
