# 规则集"重量"

> **何时读**：用户问「规则集是不是太重」、要换规则集、或想判断某个规则集能不能用。

## 1 · 问题成因

Surge 把被引用的规则集**在内存里展开成匹配表**。一份十几万条的规则集
和一份 4 千条的规则集，对启动时间与常驻内存的影响不是一个量级。

但**更大的坑不是总量，是构成** —— 见 §2。

## 2 · 核心判据：不是看条数，是看**类型分布**

本项目用到的三个「必须数的东西」：

| 判据 | 为什么 |
|:-----|:-------|
| **域名条目数** | 决定它能不能"接住国内域名"。IP 条目再多也接不住域名 |
| **IP 条目数** | 决定它会不会"触发解析"（不带 `no-resolve` 时） |
| **缺 `no-resolve` 的 IP 条目数** | 决定它会不会制造出口 ③ |

### 2.1 名字骗人的实例

| 规则集 | 名字看起来 | 实测域名条目 | 实测 IP 条目 |
|:-------|:-----------|:------------:|:------------:|
| `direct.txt`（Loyalsoldier） | 国内直连 | **十几万** | 0 |
| `ChinaMax.list` | 国内最大集 | **64** | 12472 |

`ChinaMax.list` 名字像国内域名集，实际 **99.5% 是 IP**。

**后果**：一份"加了 `no-resolve` 之后国内域名走代理"的配置，
用 `ChinaMax.list` 当主承重墙。因为：
- 它的 12472 条 IP 条目在 `no-resolve` 下**不再匹配域名**；
- 它的 64 条域名条目**接不住**国内的量。

⇒ **判据是「数域名条目」，不是看名字，也不是看 README 标题。**

### 2.2 本项目的构成

| 规则集 | 条数 | 域名 | IP | 缺 `no-resolve` 的 IP |
|:-------|:----:|:----:|:--:|:---------------------:|
| `surge-direct.list` | — | — | 0 | 0 |
| `surge-ads.list` | — | — | 0 | 0 |
| `AWAvenue-Ads-Rule-Surge-RULE-SET.list` | — | — | 0 | 0 |
| `AI.list` | — | — | 0 | 0 |
| `private.txt` | — | — | 0 | 0 |
| `direct.txt` | **十几万** | **十几万** | 0 | 0 |

> ⚠️ **条数一律不写死精确数字**：`—` = 现抓；`direct.txt` 那格写「十几万」只用于表达量级。
> 这些规则集都没锁 commit，上游每周更新，固定数字很快过期（本仓 lazy v1.1 起就是这个口径）。
> 要精确值现抓：`python skill/scripts/surge/audit_ruleset_content.py <profile>`。
> 这张表真正有意义的列是 **IP 列** —— IP 数才决定 `no-resolve` 风险，它与条数无关。

**六份加起来 IP 条目为 0** —— 所以本项目的 `no-resolve` 风险主要来自
「将来换规则集」，而不是当下。

⚠️ 这意味着 `audit_ruleset_content.py` 的判据 A（缺 `no-resolve` 的 IP 条目）
在当前配置下是**空过**的。这是**已知且可接受**的 —— 它是一道**防将来**的闸门。
不要因为"现在空过"就把它删掉。

## 3 · 数字的取得方式

```bash
python skill/scripts/surge/audit_ruleset_content.py surge/profiles/lazy.conf
```

输出里每条规则集都有：

```
── 第 193 行 · surge-ads.list （新下载） → REJECT
   共 <n> 条：域名类 <n> / IP 类 0 / 其他 0
   域名类型：{'DOMAIN-SUFFIX': <n>, 'DOMAIN-WILDCARD': <n>}

── 第 210 行 · AWAvenue-Ads-Rule-Surge-RULE-SET.list （新下载） → REJECT
   共 <n> 条：域名类 <n> / IP 类 0 / 其他 0
   域名类型：{'DOMAIN': <n>, 'DOMAIN-SUFFIX': <n>, 'DOMAIN-KEYWORD': <n>}
```

末尾还有直连集合的汇总：

```
直连（DIRECT）规则集的域名条目统计：
   surge-direct.list                            域名    <n> / IP      0
   apple.txt                                    域名    <n> / IP      0
   private.txt                                  域名    <n> / IP      0
   direct.txt                                   域名 <十几万> / IP      0

✅ 直连集合共 <合计> 条域名条目 —— 足以接住国内域名
```

> ⚠️ **上面两个块是「输出长什么样」的样例，不是信得过的现行读数** ——
> 块里每一个数字都是写作时点的快照，上游每周更新后就变了，所以用占位符/量级表示。
> 要真数就跑一次命令。

加 `--show-domestic` 打印明细，加 `--force` 忽略缓存重下。

> ⚠️ **读数会被缓存带偏**：默认缓存在系统临时目录（`<tmp>/surge-ruleset-cache`），
> **跨会话保留**。上游改过条目后，不带 `--force` 会一直报旧条数。
> 对不上就加 `--force` 重跑一次再下结论 —— 别把旧缓存读数当成上游漂移。

## 4 · 类型分布的读法

`parse_ruleset()` 把条目分成三类：

```python
_DOMAIN_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "DOMAIN-SET", "DOMAIN-REGEX", "HOST", "HOST-SUFFIX", "HOST-KEYWORD",
    "HOST-WILDCARD",
}
_IP_TYPES = {"IP-CIDR", "IP-CIDR6", "IP6-CIDR", "SRC-IP", "DEST-IP", "IP-ASN"}
_OTHER_TYPES = {"URL-REGEX", "USER-AGENT", "PROCESS-NAME", "PROTOCOL",
                "DEST-PORT", "SRC-PORT"}
```

⚠️ **裸域名**（没有逗号的行，如 `example.com`）也按 `DOMAIN-SUFFIX` 计入 ——
部分社区的 `.list` 这么写。判据里同时记进 `<裸域名>` 与 `DOMAIN-SUFFIX` 两个桶，
前者便于看出"这份集用的是裸格式"。

⚠️ **`_OTHER_TYPES` 不参与任何判负。** `URL-REGEX` / `USER-AGENT` 这类
在 Surge 里是**不可预匹配**的（需要在 HTTP 层求值），也不会触发 DNS 解析。
但它们**不能带 `pre-matching`** —— 这是另一个话题，见
[`hardening-template.md`](hardening-template.md) §4.4。

## 5 · 超重时的处置

### 5.1 先量，再判断

不要凭感觉换规则集。先跑一次上面的命令，看：

| 观察 | 结论 |
|:-----|:-----|
| 域名条目数 ≥ 10 万 | 内存占用会明显，但**这是国内直连的必要成本** |
| 域名条目里重复率高（多个集重叠） | 可以合并 |
| IP 条目占多数且判给 DIRECT | ⚠️ 检查 `no-resolve` 与"域名条目是否够" |
| 有 `URL-REGEX` / `USER-AGENT` | 不能用 `pre-matching`，但也不影响 DNS |

### 5.2 本项目的取舍

`direct.txt` 这十几万条是**刻意保留**的。理由：

- 它是"`no-resolve` 之后国内域名还能直连"的**唯一承重墙**；
- 砍到 1 万条以内 → 大量国内域名落到 `FINAL → Proxy`，用户一定报障；
- 它这十几万条**全是域名**，所以不会制造出口 ③。

**结论：这份"重"是必须付的代价。** 想优化就从别处省，不要动它。

### 5.3 真要减重

按这个顺序试：

1. **合并重叠的直连集** —— 去掉重复条目，不减少覆盖面
2. **换 IP 类规则集为域名类** —— 前提是域名条目够
3. **砍掉用不到的分流** —— 例如不要 AI 分流就删掉 `AI` 组与 `AI.list` 那条规则，
   少两个成员与一处分流
4. **给远程集加 `update-interval` 拉长** —— 减少刷新频率（新广告域名要等一个刷新周期才命得中；本仓取一周，再长就要在文件里写明理由）

⚠️ **不要**为了"轻"而把 `direct.txt` 换成一个名字像国内域名集、
实际以 IP 为主的规则集。那是本项目最典型的坑。

## 6 · 缓存

规则集下载后会缓存在系统临时目录（约 6 MB）：

- Windows：`%TEMP%\surge-ruleset-cache`
- macOS / Linux：`/tmp/surge-ruleset-cache`

缓存文件名的生成：

```python
key = re.sub(r"[^A-Za-z0-9._-]", "_", url)[-120:]
```

**取 URL 的末尾 120 字符**并替换非法字符 —— 这样同一份规则集的不同 commit
（URL 只在末尾的 hash 处不同）会落成不同的缓存键。同时避免超长路径。

⚠️ 缓存**没有过期机制**。想拿最新内容用 `--force`。
