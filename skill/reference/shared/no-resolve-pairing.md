# 分流与 no-resolve 必须成对交付

> 核心命题：「DNS 不泄露」和「分流正确」是同一个机制的正面和反面。
> 由原 Surge / Egern 两侧 `docs/05` 合并，机制论述三侧同源，案例与落点按内核分节。

## Surge 侧

> 本文是一次真实事故的复盘，也是本项目**最重要的一条教训**。
> 事故经过：两份审计脚本**双双通过**，分流却**整片是坏的**。

### 1. 事故的成因

为了消掉"IP 类规则触发本地解析"这条泄露面，给所有 IP 规则补上了 `no-resolve`：

```
- GEOIP,CN,DIRECT,no-resolve        ← 补了 no-resolve
```

DNS 审计立刻全绿 —— 本地解析确实不再被触发了。**但国内网站全走代理了。**

### 2. 机制：`no-resolve` 是一把双刃刀

`GEOIP,CN,DIRECT` 这条规则的**全部能力**来自：

```
域名 --(解析)--> IP --(查 GeoIP 库)--> 属于 CN? --是--> DIRECT
```

`no-resolve` 砍掉的正是中间那一步。没有解析结果，IP 归属**无从判断**，
这条规则对域名就**完全失效了**。

于是国内域名走到了哪里？—— 一个**真正的域名类规则集**接不住它们，它们就整片落到
`FINAL → Proxy`（或 `default`）。

```
❌ 补 no-resolve 之后，国内域名无人接住：

   GEOIP,CN,DIRECT,no-resolve    ← 不再匹配域名，形同虚设
   FINAL,Proxy                   ← 国内域名全落这里 → 走代理
```

### 3. 审计脚本未捕获的原因

因为当时的审计脚本审的是**结构**：

| 当时的判据 | 判定 |
|---|---|
| "所有 IP 类规则都带 no-resolve 吗" | ✅ 都带了 |
| "规则顺序对吗" | ✅ `GEOIP` 在最后 |
| "策略名能解析吗" | ✅ 都能 |
| ⭐ "国内域名最终判给谁" | ❌ **当时根本没有这一项** |

⇒ **结构正确的配置可以是错的。** "配置里写了什么"与"实际会发生什么"是两件事。

### 4. 修法：两条判据成对交付

| 判据 | 检查什么 |
|---|---|
| **A** | 所有 IP 类规则带 `no-resolve` → 消灭"规则触发解析"这条泄露面 |
| **B** | `FINAL` 之前有一份**含大量域名条目**的国内规则集 → 国内域名仍判给 `DIRECT` |

**A 和 B 必须同时成立。** 只做 A = 分流坏；只做 B = 泄露面还在。

### 5. B 的判据是「数域名条目」，不是看名字

这是 B 最容易做错的地方。

| 规则集 | 名字暗示 | 实际内容 | 能不能独自承重 |
|---|---|:---:|:---:|
| `ChinaMax.list` | "中国大陆全量" | 64 条域名 / **12472 条 IP** | ❌ 99.5% 是 IP，而 IP 判定已被 `no-resolve` 关掉 |
| `direct.txt`（Loyalsoldier） | "直连清单" | **纯域名**（条数一律现抓） | ✅ |

`ChinaMax.list` 的仓库说明里写得很清楚：它与 `ChinaMax_Domain.list` **"需共同使用"**。
只看名字会以为一条搞定，实际上必须成对引用。

⇒ **判据必须落到"下载下来数一遍"上。** 这正是 `skill/scripts/surge/audit_ruleset_content.py`
存在的原因 —— 它会把每个 `DIRECT` 规则集的域名条目数与 IP 条目数都列出来。

### 6. 还有一个更隐蔽的坑：只测 `.cn` 会假通过

假设一份配置只靠这一条兜底：

```
DOMAIN-SUFFIX,cn,DIRECT
```

它会让**所有 `.cn` 域名**直连 —— 探针里如果全是 `.cn`，会显示 100% 通过。
但实际上 `qq.com`、`taobao.com`、`miui.com`、`bilibili.com` 这些**非 `.cn` 的国内域名**
全都走了代理。配置是坏的，测试却是绿的。

⇒ 所以 `audit_routing_coverage.py` 的国内探针**刻意混入非 `.cn` 域名**：

```
www.baidu.com     www.qq.com        www.taobao.com    www.jd.com
www.bilibili.com  www.163.com       www.zhihu.com     www.miui.com
connect.rom.miui.com                www.aliyun.com    www.huawei.com
www.iqiyi.com     www.douyin.com    www.meituan.com   …（共 17 个）
```

**测试集必须包含"能证伪配置"的样本**，否则它只是在复述配置里的假设。

### 7. 推广：本条教训适用于任何"改动判据"的场景

事故的根因不是 `no-resolve` 这个具体参数，而是一个通用的思维错误：

> **以为"我加了一条规则"等于"我解决了问题"，而没有检查"这条规则同时破坏了什么"。**

同类风险清单（本项目已全部纳入审计）：

| 改动 | 顺带破坏了什么 | 补偿判据 |
|---|---|---|
| 给 IP 规则加 `no-resolve` | "靠解析判 IP 归属"这条直连路径 | 必须有域名类国内规则集 |
| 广告拦截改成 `pre-matching` | 策略必须**字面量** REJECT 族（不能用组） | `check_surge_dns.py` 第 10 项 |
| 端点全改成 IP 字面量 | 失去"按域名走 CDN 就近解析" | 显式豁免 + 记录取舍 |
| 移除 `always-real-ip` 的域名规则 | 游戏机 / NTP / STUN 拿假 IP | `check_surge_dns.py` 第 11 项 |

⇒ **凡是"补一个开关"，都要问一句"它同时关掉了什么"。**

## Egern 侧

> **这是本项目最贵的一条教训。**
> 「DNS 不泄露」和「分流正确」不是两个独立目标 —— 它们是**同一个机制的正面和反面**。
> 一份配置可以做到 DNS 审计全绿，同时国内网站全部走代理。

> **模板现状更新**：本文记录的是 f8 时期用 `ChinaMax_All_No_Resolve.list` 完成这次修复的实测与推导。
> 当前模板已把该规则集的 URL 换成 Loyalsoldier **`direct.txt`**（**纯域名**，零 IP 条目；数字随上游更新变动）；
> 原理完全一致 —— 「IP 规则带 `no_resolve`」必须与「一份域名条目足够多的国内直连规则集」成对交付。
> 换用纯域名规则集后，它自身不触发解析，`no-resolve` 那一半由 `geoip: CN` 承担。

### 1. 机制：`no_resolve` 是"用解析换分流"的开关

官方 `rules` 文档原文：

> `no_resolve (bool)`，可选 —— 仅适用于 IP 类规则（`geoip`、`ip_cidr`、`ip_cidr6`、`asn`）。
> **设为 `true` 时仅匹配已解析的 IP 地址，不会触发 DNS 解析。**

反过来说：**不带 `no_resolve` 的 IP 类规则会触发一次解析** —— 这正是泄露源（见 [DNS 为什么会泄露](dns-basics.md#dns-为什么会泄露)）。

但很多人没注意到的是这条的**另一半**：

> **`no_resolve: true` 之后，`geoip` 不再匹配域名。**

于是产生了一个隐蔽的连锁反应：

```
原始配置的国内直连机制：
    收到域名 → 强制本地解析一次 → 判出 CN IP → DIRECT
                    ▲
                    └── 这次解析就是泄露源

加上 no_resolve: true 之后：
    ✅ 不再有强制解析  → 泄露治好
    ❌ geoip 不再匹配域名 → 这条直连路径**一起消失**
                            → 国内域名整片落到 default → 走代理
```

⇒ **补 `no_resolve` 的同一时刻，必须确认 `default` 之前有一份"域名条目足够多"的国内 DIRECT 规则集。**
这就是"成对交付"的含义。

### 2. 事故复盘：治好泄露的那一手，把分流搞坏了

| 阶段 | 改动 | DNS 审计 | 分流 | 说明 |
|---|---|---|---|---|
| **f7** | 给 `geoip: CN` 补 `no_resolve`；换用 `Apple_All_No_Resolve.list`；显式写 `proxy_nameservers` | ✅ `check_egern_dns.py` → `0 high / 3 low / 43 ok`<br>✅ `audit_ruleset_noresolve.py` → `OK (20/20)` | ❌ **国内域名整片落 `default → Final → Proxy`** | **两个脚本双双全绿，配置却不可用** |
| **f8** | 只改一条：`ChinaMax.list` → `ChinaMax_All_No_Resolve.list` | ✅ 同上（无退化） | ✅ **15/15 国内探针命中 `DIRECT`** | 补回国内域名直连 |

**用户的原始反馈是这样的：**

> 「没有 dns 泄露了，可是国内外的分流好像出了问题……国内的网站怎么都不是直连 反而走了代理，chinamax 基本都是一些 ip 走了直连，而国内域名基本都走了 final」

这句话里其实**已经把根因说出来了**：`ChinaMax` 里"基本都是一些 IP"，所以只有 IP 形式的连接走了直连。
问题不在 DNS，而在**被引用规则集的构成**。

### 3. 根因：规则集的名字会骗人

`ChinaMax.list` —— 这个名字听起来**最像**一份"中国域名表"。实测数据（GitHub API / `raw` / jsDelivr 三处交叉核对，均为 453,982 字节）：

| 类型 | 条数 |
|---|---|
| `IP-CIDR` | 8,251 |
| `IP-CIDR6` | 4,221 |
| `USER-AGENT` | 65 |
| **`DOMAIN-SUFFIX`** | **51** |
| **`DOMAIN-KEYWORD`** | **13** |
| `PROCESS-NAME`（Egern 未文档化） | 12 |
| `IP-ASN` | 1 |
| **合计** | **12,614** |

⇒ **IP 类 12,473 条 / 域名类只有 64 条（0.5%）。**

仓库自己的 README 写得很清楚：

> `ChinaMax.list`、`ChinaMax_Domain.list` **共同使用**。

同目录下另有：

| 文件 | 大小 | 内容 |
|---|---|---|
| `ChinaMax.list` | 454 KB | IP 为主（上面那张表） |
| `ChinaMax_Domain.list` | 1.5 MB | 纯域名 |
| **`ChinaMax_All_No_Resolve.list`** | **3.42 MB** | **111,332 域名 + 同份 12,472 IP（全带 `no-resolve`）** |

**⇒ 判据是「数域名条目」，不是看文件名，也不是看 README 标题。**

### 4. 替换的安全性：覆盖面无损失

换规则集之前必须核对两件事：**IP 覆盖面没变**、**旧版域名全被包含**。

```bash
# IP 段归一化比对（去掉 ,no-resolve 后逐条比）
grep -E '^IP-CIDR' 旧.list | sed 's/,no-resolve$//' | sort -u > ipA.txt
grep -E '^IP-CIDR' 新.list | sed 's/,no-resolve$//' | sort -u > ipB.txt
diff ipA.txt ipB.txt && echo "IP 段逐条相同 ✅"

# 域名段：旧的是不是新的子集
grep -E '^DOMAIN' 旧.list | sort -u > dA.txt
grep -E '^DOMAIN' 新.list | sort -u > dB.txt
comm -23 dA.txt dB.txt | wc -l    # 期望 0
```

实测结果：

| 核对项 | 结果 |
|---|---|
| IP 段（去 `,no-resolve` 后） | **12,472 条逐条相同** ✅ |
| 旧版 64 条域名 | **全部被新版包含**（差集 0）✅ |
| 新版域名条目 | **64 → 111,332** |
| 新版 IP 条目是否带 `no-resolve` | **12,473 条全部带** ⇒ 不会重新引入"为判定而强制解析" ✅ |

### 5. 验证：一个能复现用户现象的脚本

光比对文件不够 —— 必须**拿真实域名走一遍规则链**，看它到底命中哪条、被判给什么策略。

`audit_routing_coverage.py` 就是干这个的。它的设计有两个关键点：

1. **探针域名必须"不以 `.cn` 结尾"。**
   如果探针全是 `xx.cn`，那么一条 `domain_suffix: cn` 兜底就会把它们全部救成 `DIRECT`，从而**掩盖"规则集没有域名覆盖"这个事实**。
   （懒人版原先正是这条兜底的存在地 —— 2026-09-24 已删，理由同上：`direct.txt` 本身含 `DOMAIN-SUFFIX,cn`。）
   所以脚本用的是 `jd.com` / `zhihu.com` / `163.com` / `qq.com` / `douyin.com` / `meituan.com` / `xiaohongshu.com` 这类**国内但非 `.cn`** 的域名。
2. **同时跑境外探针**，确认没有把境外域名误判成直连。

实测结果（同一份脚本跑两个版本）：

| 探针 | f7（问题版） | f8（修复版） |
|---|---|---|
| `jd.com` / `zhihu.com` / `163.com` / `qq.com` / `douyin.com` / `meituan.com` / `xiaohongshu.com` | `default → Final` ❌ | `ChinaMax_All_No_Resolve` → **`DIRECT`** ✅ |
| 国内合计 | **7/15 落 `Final`** | **15/15 `DIRECT`** |
| 境外（google / youtube / github / x / openai / netflix / wikipedia） | — | 各归其组或落 `Final`，**无误判直连** ✅ |

### 6. 代价与取舍

| 项 | 旧 | 新 |
|---|---|---|
| 规则集大小 | 454 KB | **3.42 MB** |
| 首次加载/更新时间 | — | 略微增加（之后走缓存） |
| 内存 | — | 略微增加 |

如果感知明显变慢，有两条更轻的路子（**但都必须重跑分流审计**）：

1. 改用 `ChinaMax_Domain.list`（纯域名，1.5 MB）+ 保留 `geoip: CN` 的 IP 判定；
2. 只保留 `ChinaMax_All_No_Resolve.list`，并撤掉额外加的 `domain_suffix: cn` 那条兜底。

**回滚**：把第 44 条规则的 URL 改回 `ChinaMax.list` 即可（一行）。

### 7. 固化下来的规则

> **任何一次动 `no_resolve`、换 `rule_set`，都必须同时跑「分流覆盖审计」。**
> 判据是**数域名条目**，不是看规则集名字。
> 三个脚本里，`check_egern_dns.py` 和 `audit_ruleset_noresolve.py` 全绿**不代表配置可用** —— 它们不检查分流。

这条规则现在写进了 `skill/SKILL.md` 的「加固结束的验收标准」第 6 条。

## mihomo 侧

> mihomo 侧没有留下一次可核实的、与 Surge / Egern 同量级的「审计双绿但国内分流整片坏掉」
> 独立事故；不能把姊妹内核的事故改写成 mihomo 事故。
> 可核实的历史问题是**两版漂移**：懒人版两条 `geoip-*` 都带 `no-resolve`，
> 分流版四条里只有 `geoip-private` 带，`geoip-google` / `geoip-telegram` / `geoip-cn`
> 三条缺失。当前六个规则落点（分流版 4 条、懒人版 2 条）已经全部补齐，
> 并用两道静态判据守住 `no-resolve` 落点，避免同类配置漂移重演。

### 1. 落点：写在 `RULE-SET` 规则行尾

mihomo 把「规则集是什么」和「引用时怎么判」拆成两层：

```yaml
rule-providers:
  geoip-cn:
    behavior: ipcidr
    format: mrs
    # url / path 省略

rules:
  - RULE-SET,geoip-cn,DIRECT,no-resolve
```

这里有三个不能混淆的事实：

1. `behavior: ipcidr` 才是「这是一份 IP 段规则集」的语义依据；
2. `format: mrs` 只是远程集的存储格式，不会自动赋予 `no-resolve`；
3. `no-resolve` 写在消费 provider 的 `RULE-SET` 规则行末尾，不写进 provider 定义，
   也不是只看 `geoip-` 名字就能推断内核已经启用。

因此本仓的标准写法是：

```yaml
- RULE-SET,geoip-cn,DIRECT,no-resolve
```

不是只写：

```yaml
- RULE-SET,geoip-cn,DIRECT
```

### 2. 源码证据：`RULE-SET` 确实接收并传递参数

此前本仓对「`no-resolve` 写在 `RULE-SET` 上是否真的有效」存疑；现在已经有
[mihomo `rules/parser.go`](https://github.com/MetaCubeX/mihomo/blob/Meta/rules/parser.go)
的源码级证据：

```go
case "RULE-SET":
    isSrc, noResolve := RC.ParseParams(params)
    parsed, parseErr = RP.NewRuleSet(payload, target, isSrc, noResolve)
```

`RC.ParseParams(params)` 解析出了 `noResolve`，随后原样传给 `RP.NewRuleSet`。
所以这不是「照搬 Clash 语法」或「待确认的猜测」：**对 `RULE-SET` 的行尾写法有效。**
同一结论也已经写入 [`hardening-template.md` §9.2](../clash/hardening-template.md)。

### 3. 为什么必须带：它收的是泄露面④

[`leak-localization.md` §4](../clash/leak-localization.md) 把 mihomo 的泄露路径拆成五个面；
其中面④就是**规则判定触发的解析**：

```
收到域名
  ↓
走到 behavior: ipcidr 的 RULE-SET
  ↓
为了判断「目标 IP 是否落在这份网段里」先解析域名
  ↓
这次额外解析暴露了用户正要访问的站点
```

不带 `no-resolve`，IP 规则为了完成判定会主动补出目标 IP；带上以后，它只匹配已经拿到的
IP，不再为了规则判定另起一次解析。分流版的 `geoip-private` / `geoip-google` /
`geoip-telegram` / `geoip-cn`，以及懒人版的 `geoip-private` / `geoip-cn`，
provider 均为 `behavior: ipcidr`、`format: mrs`，所以六个引用落点都必须带。

但双刃刀的另一面没有改变：`no-resolve` 也会切断「先把域名解析成 IP，再靠 IP 集分流」
这条路径。对国内直连而言，正确结构仍然必须是：

```yaml
- RULE-SET,cn,DIRECT
- RULE-SET,geoip-cn,DIRECT,no-resolve
- MATCH,Proxy
```

`cn` 是域名类 provider，负责接住域名；`geoip-cn` 是 IP 类 provider，只兜已经是 IP 的连接；
`MATCH` 才是最终兜底。两者分工后，才同时得到：

| 判据 | mihomo 侧的落地 |
|---|---|
| **A · 不泄露** | 所有 `behavior: ipcidr` 的引用都带 `no-resolve` |
| **B · 分流不坏** | `MATCH` 前保留域名类国内直连集 `RULE-SET,cn,DIRECT` |

**只满足 A，仍可能复刻 Surge / Egern 的事故；只满足 B，面④仍然开着。**

### 4. 本仓现状：4 条 + 2 条，已经统一

逐项核对现役 [`routing.yaml`](../../../clash/profiles/routing.yaml) 与
[`lazy.yaml`](../../../clash/profiles/lazy.yaml)：

| profile | provider | behavior / format | 现役规则 | 结果 |
|---|---|---|---|:---:|
| 分流版 | `geoip-private` | `ipcidr` / `mrs` | `RULE-SET,geoip-private,DIRECT,no-resolve` | ✅ |
| 分流版 | `geoip-google` | `ipcidr` / `mrs` | `RULE-SET,geoip-google,Google,no-resolve` | ✅ |
| 分流版 | `geoip-telegram` | `ipcidr` / `mrs` | `RULE-SET,geoip-telegram,Telegram,no-resolve` | ✅ |
| 分流版 | `geoip-cn` | `ipcidr` / `mrs` | `RULE-SET,geoip-cn,DIRECT,no-resolve` | ✅ |
| 懒人版 | `geoip-private` | `ipcidr` / `mrs` | `RULE-SET,geoip-private,DIRECT,no-resolve` | ✅ |
| 懒人版 | `geoip-cn` | `ipcidr` / `mrs` | `RULE-SET,geoip-cn,DIRECT,no-resolve` | ✅ |

数字口径是**每份 profile 内的规则行数**：分流版 4 条，懒人版 2 条；不是把同名 provider
跨版本去重后的数量。此前的差异也要准确表述：分流版不是「4 条全缺」，而是
`geoip-private` 已带、其余 **3 条缺**；懒人版 **2 条一直都带**。现在两版规则已统一为
「凡 `geoip-*` / `ipcidr` 引用，全部带 `no-resolve`」。

### 5. 判据固化：一层看名字，一层看真实语义

本仓没有靠文档提醒维持现状，而是把缺口写进了两个门禁：

1. [`check_structure.py`](../../tests/clash/check_structure.py) **第 ⑤ 项**：
   遍历 `RULE-SET,geoip-*`，任一规则缺 `no-resolve` 就判负。它针对本仓命名约定，
   能直接阻止「分流版又漏三条」这类漂移。
2. [`check_clash_dns.py`](../../scripts/clash/check_clash_dns.py) **判据 10**：
   判断 IP 类规则时以 provider 的 `behavior` 为第一依据；`behavior: ipcidr` 必须带，
   `behavior: domain` 不该带，`behavior: classical` 则标成内容无法静态判定。
   只有 provider 没声明 `behavior` 时，才退回 `geoip-` 名字前缀兜底。

这两层不是重复劳动：第 ⑤ 项守本仓结构约定，判据 10 守实际匹配语义。
当前实跑结果为：结构门禁四份 profile 全部通过；DNS 审计中分流版报告
「4 条 IP 类规则全部带 `no-resolve`」，懒人版对应为 2 条，两版均为 `0 high`。

但这里必须保留事故复盘最重要的边界：**这两道静态门禁只证明 A，不自动证明 B。**
本仓目前没有 mihomo 侧的专用分流覆盖审计脚本；因此每次增删 `no-resolve`、替换 `cn`
provider 或移动 `MATCH` 前规则时，还必须同时核对：

- `cn` 仍是 `behavior: domain` 的国内域名集；
- `RULE-SET,cn,DIRECT` 仍在 `MATCH,Proxy` 之前；
- 用国内非 `.cn` 域名做分流验证，不能只测会被后缀兜底救活的样本。

不能把「两道门禁全绿」再次误读成「配置一定可用」—— 这正是本文要跨内核保留下来的教训。

## 三侧对照：语法不同，成对交付的机制相同

| 内核 | 开关拼写与落点 | IP 侧示例 | 域名补偿必须落在 |
|---|---|---|---|
| Surge | 连字符 `no-resolve`，写在 IP 规则行尾 | `GEOIP,CN,DIRECT,no-resolve` | `FINAL` 前的国内域名规则集 |
| Egern | 下划线 `no_resolve: true`，写在结构化 IP 规则对象内 | `- geoip: {match: CN, policy: DIRECT, no_resolve: true}` | `default` 前的国内域名 `rule_set` |
| mihomo | 连字符 `no-resolve`，写在消费 provider 的 `RULE-SET` 行尾 | `RULE-SET,geoip-cn,DIRECT,no-resolve` | `MATCH` 前的 `RULE-SET,cn,DIRECT` |

三侧共同的机制可以压成一句话：

> **IP 规则不得为判定主动解析；关掉这条路以后，域名分流必须由真正的域名规则集接手。**

因此评审任何一侧时，都不能只搜开关字符串。必须同时问：

1. 这个开关是否落在内核真正读取的位置？
2. 被关掉的「域名 → IP → 归属」路径，由哪份域名规则集补回？
3. 审计是在检查结构，还是已经用能证伪的域名验证了最终去向？

---

下一步：[操作：Surge · Egern · 日常维护](ops.md)。
