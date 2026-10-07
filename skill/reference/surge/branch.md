# 分支 A · Surge 配置防 DNS 泄露

> 本文从 [`SKILL.md`](../../SKILL.md) 拆出 —— **Surge 单侧任务只读本文件，不读分支 B**。
> 共享骨架（泄露面五类 / 四条铁律 / 六条底线 / 标准动线 / 按需读取索引）在 SKILL.md §1–§4。

### 适用

用户给一份 Surge `.conf`（或要生成一份 Surge profile），要求「防 DNS 泄露 / 别让 DNS 裸奔 /
检查 DNS 配置」，或反馈「实测有 DNS 泄露」「国内网站不是直连」。也可用于交付前自检。

**不适用**：Clash / mihomo（`no-resolve` 语义不同，`fake-ip-filter` 是另一套）、
Egern（见分支 B）、Shadowrocket（`dns-server` 语义不同）。

### 引用文件（按需读取）

本文件是**主干**：三条出口模型、12 项审计清单、加固模板、坑索引、验收判据。
`reference/surge/` 七篇的「何时读」索引见 SKILL.md §4。**移植到 Egern 侧前必读
[`reference/shared/cross-kernel-diff.md`](../shared/cross-kernel-diff.md)**。

### Surge 的 DNS 模型（不理解这个就会改错地方）

与 Egern 的两条互不相通路径不同，**Surge 只有一条解析路径**，但有**三个明文出口**。
这是本技能的核心模型：

| 出口 | 触发条件 | 是否必然发生 | 收口手段 |
|---|---|---|---|
| ① **引导解析** | `encrypted-dns-server` / `dns-server` 里写了主机名 | 冷启动时**必然** | 端点写 IP 字面量 |
| ② **旁路设备** | 忽略 Surge DNS 的设备（HomePod / Apple TV / Chromecast / 智能音箱）直接发 `:53` | 设备在线时**必然** | `hijack-dns` |
| ③ **规则触发解析** | IP 类规则（`GEOIP` / `IP-CIDR` / `IP-ASN`）不带 `no-resolve` | 每个走到它的**域名**都触发 | 全部加 `no-resolve` |

⭐ **三个出口的严重度依次递减，但"必然性"依次递增。**
出口 ① 只在冷启动发生一次，但它 100% 会发生；出口 ③ 每次新域名都发生，
但只在规则命中时发生。**三者必须都堵** —— 堵两个剩一个，剩下的仍然是"必然通路"。

⭐ **`dns-server` 绝不能用 `system`。** 它承担引导与连通性测试职责。
写 `system` 等于把引导这一步交给运营商 DHCP 下发的那台解析器 —— 那正是出口 ①。

⭐ **`encrypted-dns-follow-outbound-mode` 必须 `false`。** 设 `true` 时 DoH 连接
自己也要遵循代理规则，形成「解析它 → 需要它 → 解析它」的环，Surge 会回退明文。

⭐ **`use-local-host-item-for-proxy` 必须 `false`。** 本地 DNS 映射只服务 DIRECT 路径；
开启会把本地结果变成**硬性的代理目标**，破坏远端解析（走代理的域名应该由节点侧
按地理就近解析，本地不该有它的答案）。

### 12 项审计清单

`scripts/surge/check_surge_dns.py` 自动跑这 12 项。逐条判据与检查号对应：

| # | 审什么 | 判负级别 |
|:-:|:-------|:--------:|
| 1 | `encrypted-dns-server` 端点是否为 IP 字面量 | HIGH（任一非字面量） |
| 2 | `dns-server` 是否显式、无 `system`、无主机名、≥2 个国内解析器 | HIGH / MEDIUM |
| 3 | `hijack-dns` 是否覆盖已知的知名硬编码解析器 | LOW |
| 4 | `encrypted-dns-follow-outbound-mode` 是否为 `false` | HIGH |
| 5 | `always-real-ip` 是否配置、`use-local-host-item-for-proxy` 是否为 `false` | HIGH / LOW |
| 6 | `internet-test-url` / `proxy-test-url` / `proxy-test-udp` 的域名归属（**提示性**） | LOW |
| 7 | 策略组引用的节点 / 组是否存在 | HIGH |
| 8 | 规则引用的策略是否可解析（`policy_index` 定位） | HIGH / MEDIUM |
| 9 | 规则顺序：域名类在 IP 类之前、FINAL 在最后、REJECT 位置 | HIGH / MEDIUM |
| 10 | 带 `pre-matching` 的规则策略是否为**字面量** REJECT 族 | HIGH |
| 11 | `always-real-ip` 主机名是否被前置域名规则接住 | MEDIUM / LOW |
| 12 | 所有 IP 类规则是否带 `no-resolve`；FINAL 是否带 `dns-failed` | MEDIUM / LOW |

另有三个**不在清单里但必须查**的审计脚本（+ 规则集刷新参数 `audit_ruleset_refresh.py`，见 `reference/surge/checker.md`）：

| 脚本 | 查什么 | 联网 |
|---|---|---|
| [`audit_ruleset_content.py`](../../scripts/surge/audit_ruleset_content.py) | ① 远程规则集里有没有**不带 `no-resolve` 的 IP 条目**；② 判给 DIRECT 的规则集**域名条目总量**是否够（判据是数域名条目，**不是**看规则集名字） | ✅ |
| [`audit_routing_coverage.py`](../../scripts/surge/audit_routing_coverage.py) | 拿真实域名**走一遍** `[Rule]`，看最终命中哪条。期望表按 profile 自动切换；**不得**放宽成"只要不是 DIRECT" | ✅ |
| [`audit_region_filters.py`](../../scripts/surge/audit_region_filters.py) | 分流配置里 6 个地区组的 `policy-regex-filter` 关键词是否同步（负向断言那份拷贝）、是否互斥、类型是否 `smart`。见坑 16 | ❌ |

⚠️ **分流配置（按应用 / 按地区分组）另有三条 Surge 特有的硬约束**，
与 Egern 等客户端的写法**不通用**：

| 约束 | 官方依据 | 正确写法 |
|:-----|:---------|:---------|
| Surge **没有** `flatten` | — | 用 `include-other-group="X"`，它复制的是"resolved member policies"，语义等价 |
| **Smart 组不能拿组名当子策略** | [Smart 智能策略组](https://kb.nssurge.com/surge-knowledge-base/zh/guidelines/smart-group) | 要 `smart` 自动选优 → `include-other-group`；要在面板点进地区 → 用 `select` + 组名作成员 |
| `policy-regex-filter` **对显式列出的成员无效** | [Policy Including](https://manual.nssurge.com/policy-groups/policy-including.html) | 想筛 `[Proxy]` 里的本机节点，必须同时写 `include-all-proxies=true` |

⚠️ 空组是允许的（正则没筛到任何节点）—— Surge **不会**因此拒绝加载，
但指向它的规则会断流。分流配置导入后要确认哪几个组是空的。

### 加固模板

完整模板见 [`reference/surge/hardening-template.md`](hardening-template.md)。最小可用骨架：

```
[General]
dns-server = 223.5.5.5, 119.29.29.29, 1.1.1.1, 8.8.8.8
encrypted-dns-server = https://1.1.1.1/dns-query, https://dns.google/dns-query, https://dns.alidns.com/dns-query
encrypted-dns-follow-outbound-mode = false
hijack-dns = 8.8.8.8:53, 8.8.4.4:53, 1.1.1.1:53, 1.0.0.1:53, 9.9.9.9:53, 208.67.222.222:53
use-local-host-item-for-proxy = false
test-timeout = 5
internet-test-url = http://connect.rom.miui.com/generate_204
proxy-test-url = http://www.gstatic.com/generate_204
proxy-test-udp = apple.com@1.1.1.1

[Rule]
RULE-SET,<白名单>,DIRECT
RULE-SET,<广告黑名单>,REJECT,pre-matching,extended-matching
RULE-SET,SYSTEM,DIRECT
RULE-SET,LAN,DIRECT,no-resolve
RULE-SET,<private.txt>,DIRECT       ← 实测零 IP ⇒ 不写规则级开关
RULE-SET,<direct.txt>,DIRECT        ← 主承重墙，见下方铁律（实测零 IP ⇒ 不写开关）
GEOIP,CN,DIRECT,no-resolve
FINAL,Proxy,dns-failed
```

#### 三条铁律

1. **白名单(DIRECT) → 黑名单(REJECT) → 常规分流（`direct.txt` / `GEOIP,CN`）。**
   REJECT 绝不能排在 `direct.txt` / `GEOIP,CN` **之后** —— 那等于白加，
   因为国内广告域名会先被 `direct.txt` 接走。
2. **`no-resolve` 与「域名体量足够的国内直连规则集」必须成对交付。**
   给 IP 规则补 `no-resolve` 会**同时**关掉「解析后判 IP 归属」这条直连路径。
   只交一半 → 国内域名整片落 `FINAL → Proxy`。判据是「数**域名**条目」，
   **不是**看规则集名字（`ChinaMax.list` 名字像国内域名集，实测 IP 类 12472 条、域名类只有 64 条）。
3. **`pre-matching` 的规则策略必须是字面量 REJECT 族**，不能是策略组。
   策略组在运行时可能解析成 DIRECT，Surge 会**拒绝加载整份配置**。

#### 验收判据（7 条，全过才算可用）

- [ ] `check_surge_dns.py` 退出码 0（无 HIGH）—— `surge/profiles/*.conf` **顶层固定名四件**都要过
- [ ] `audit_ruleset_content.py` 通过（远程规则集无缺 `no-resolve` 的 IP 条目；直连集合域名条目 ≥1000）
- [ ] `audit_routing_coverage.py` 通过（国内探针全部 DIRECT、境外探针**命中预期的组**、误杀探针不被 REJECT）
- [ ] `audit_region_filters.py` 通过（仅分流配置：关键词同步 / 互斥 / 类型 smart）
- [ ] `check_secrets.py` 通过（占位符纪律 / 订阅 token 纪律）
- [ ] 手工实测：抓包确认冷启动无明文 `:53`
- [ ] 手工实测：游戏机 / NAT 检测 / 时间同步正常（`always-real-ip` 生效）

### 坑索引

完整复盘见 [`reference/surge/pitfalls.md`](pitfalls.md)。**高频坑速查**：

| 症状 | 根因 | 修法 |
|---|---|---|
| 国内网站整片走代理 | IP 规则加了 `no-resolve`，但 `FINAL` 前没有域名类国内直连集 | 加 `direct.txt`，见铁律 2 |
| 配置加载失败「策略无法解析」 | `pre-matching` 策略写成了策略组；或 `underlying-proxy` 指向不存在的节点 | 改字面量 / 先建被引用的节点 |
| 报「规则引用了未定义的策略 `CN`」 | 审计器把 `GEOIP` 当成"无匹配值"类型，策略取到了 index 1 | `GEOIP` / `IP-GEOIP` / `ASN` 的策略恒在 index 2（`RULE-SET` 同理，index 1 是规则集标识） |
| 冷启动抓包有明文 `:53` | `encrypted-dns-server` 里有主机名端点；或 `dns-server` 写了 `system` | 端点换 IP 字面量 |
| 每个新域名首访卡一下 | `GEOIP,CN` 或其他 IP 规则缺 `no-resolve` | 全部加 `no-resolve`（注意同时补铁律 2） |
| 端点选境内还是境外 | 是**性能取向**还是泄露问题？ | 它是**性能探针**：官方 KB 明确走代理时解析在代理服务器进行。`internet-test-url` 宜国内，`proxy-test-url` 宜境外（含国际段）。**别把境外端点当缺陷报** |
| 游戏机 NAT 检测坏掉 | `always-real-ip` 缺游戏机主机名，或它们没被前置域名规则接住 | 补 `always-real-ip` + `DOMAIN-SUFFIX` 规则 |
| 审计器把 `miui.com` 当境外域 | 国内域名判据只认 `.cn` 后缀 | 用显式后缀清单，见 `check_surge_dns.py` 里的 `DOMESTIC_TEST_SUFFIXES` |
| 审计器说「hijack-dns 只覆盖 6 个」 | 判据是"条数"，但 `:53` 地址空间无限、永远列不全 | 判据改成「还有多少**已知的**知名境外解析器没覆盖」 |
| 只测 `.cn` 域名时全绿，实际分流是坏的 | 配置靠 `DOMAIN-SUFFIX,cn` 兜底，不是真的接住了国内域名 | 探针里**刻意混入非 `.cn`** 的国内域名（`qq.com`/`taobao.com`/`miui.com`） |

### 引用文件与官方文档

- Surge 官方文档：<https://manual.nssurge.com/>
  - DNS 服务器与语法：<https://manual.nssurge.com/dns/dns-server.html>
  - 加密 DNS（`encrypted-dns-server`）：<https://manual.nssurge.com/dns/encrypted-dns.html>
  - `hijack-dns` / `always-real-ip` / DNS 阶段 REJECT：<https://manual.nssurge.com/dns/advanced.html>
  - `[Rule]` 类型与选项：<https://manual.nssurge.com/rules/overview.html>
  - `[Proxy Group]` 类型与参数：<https://manual.nssurge.com/policy-groups/overview.html> · <https://manual.nssurge.com/policy-groups/parameters.html>
  - Proxy 类型与参数：<https://manual.nssurge.com/policies/overview.html> · <https://manual.nssurge.com/policies/parameters.html>

> ⚠️ Surge 是闭源商业软件，**很多行为没有文档，只能实测**。
> 本技能里凡是写「实测」的地方都请当作经验值 —— 版本更新后需重新验证。

