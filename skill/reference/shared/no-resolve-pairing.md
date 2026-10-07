# 分流与 no-resolve 必须成对交付

> 核心命题：「DNS 不泄露」和「分流正确」是同一个机制的正面和反面。
> 由原两侧 `docs/05` 合并，机制论述两侧同源，案例按内核分节。

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

---

下一步：[操作：Surge · Egern · 日常维护](ops.md)。
