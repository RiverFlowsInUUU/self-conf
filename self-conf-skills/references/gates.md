# 门禁 · 判据、纪律与公开仓交付


## 闸门纪律 —— 怎么证明一道闸门不是摆设

> 本仓全套闸门，唯一入口 `python self-conf-skills/gates/verify_all.py`。
> **数量不是风险，「永远绿」才是** —— 一道从不判红的闸门比没有更糟。
>
> **三内核共通**（下面各侧不再重复）：
> · 环境：Python 3.8+，仅标准库 + PyYAML；`check_script_sync` / `check_remote_urls` 另需 Node.js。
> · 退出码：**0 = 全过 · 1 = 判负 · 2 = 环境故障 · 3 = 未验证**。
>   ⚠️ 铁律：**审计器的故障绝不能被计成一次成功的判负** —— 所以 2 与 1 必须分开。
>   分界线只有一条：*没读到远端真值 = 3；读到了但不过 = 1。*
> · 各脚本的逐条判据写在其源码里（`self-conf-skills/run/<kern>/*.py`），**本节不复述** ——
>   复述就是制造第二份要同步的副本。

---

### 1 · 核心判据

**「跑一遍是绿的」≠「这道闸门有效」。**

跑一遍绿，只能证明**当前状态没问题**，证明不了**坏了它会叫**。
要证明后者，唯一办法是**注错**：故意把仓库改坏，看它红不红。

---

### 2 · 注错的三条铁律（都踩过）

#### 铁律一：先确认注错**生效**了，再判断闸门好坏

踩过的坑：改 `diff` 时第一遍写错了字符串（`replace` 没匹配上），
闸门没红 ⇒ 我差点得出「判据失灵」的结论。实际是注错根本没生效。

**每次注错后，先验证文件真的变了**（比对字节 / 回读计数），再跑闸门。

#### 铁律二：注错必须落在判据的**扫描面**内

⚠️ 这条最隐蔽。锚点存在 ≠ 落在扫描面里。

踩过的坑：测「地区组判别力·Surge」时，我把配置里的「香港」改成「香X港」，
锚点确实存在、文件确实改了 —— 但闸门**没红**。

我一度定性它是摆设。实际是：它守的是
「Other Regions 的负向断言里每个关键词都要有出处」，
而我改的那处**不在它扫的 61 个关键词里**（在注释里）。

改成「从 Other Regions 的负向断言里删掉『新加坡』」⇒ 立刻判负。

**结论：要照着判据的输出声明去设计破坏，不要瞎改。**

#### 铁律三：看**退出码语义**，别只看输出文本

踩过的坑：`audit_ruleset_refresh.py` 改了 25 处 `update_interval`，
它逐条打印「🟡 约定 ... 与本仓约定 604800 不同」—— 看着像在报错，
但 **exit=0 判通过**。

原因：它把偏离归为「约定」档，**默认不改退出码**，要 `--strict` 才判负。
头注里写了，我接闸门时没看到 ⇒ 等于给仓库加了两道假闸门。

**接第三方脚本进闸门前，先读头注的「退出码」一节，看有没有开关档。**

---

### 3 · 怎么跑判别力矩阵

```bash
cp -r self-conf _probe && cd _probe && rm -rf .git && git init && git add -A && git commit -m base

python self-conf-skills/gates/verify_all.py

```

⚠️ 两个坑：
- **Windows 中文环境**：子进程输出用 `bytes + errors="replace"` 读，
  别用 `text=True`（管道默认 GBK，读 UTF-8 会 UnicodeDecodeError）
- **多组串行跑会互相污染**（restore 不干净）⇒ 一次只改一处、只跑对应判据、
  立刻 `git checkout -- .` 还原。矩阵只用来**筛嫌疑**，逐个验证才下结论。

---

### 4 · 本仓已验证的判别力（2026-10-08）

#### 实测会判红的（有效）

| 闸门 | 用什么注错戳红的 |
|:-----|:----------------|
| 地区组判别力（三内核） | 从 Other Regions 负向断言里删一个关键词 |
| min-pair 一致 / clash min 版一致 | 改静态 profile 与脚本不一致 |
| 版本头注 | 改版本头注为 v9.9.9 |
| README 徽章 | 改徽章数字 |
| markdown 链接 | 把锚点改成不存在的 |
| 文档 AUTO 同步 | 改 AUTO 标记的值 |
| secrets 扫描 ×2 | 注入 `token=AbcDef123456789` |
| 规则集来源文档同步 | 改配置里 provider 的路径 |
| 自托管清单·裸IP检测 | 往 `.list` 里加 `IP-CIDR,1.2.3.4/32` |
| clash 头注数字新鲜度 | 改脚本头注的组数 |
| clash 脚本/静态对拍 | 改静态文件 interval |
| .min 漂移 | 改完整版注释 |
| 自洽性 | 把 URL 改回旧仓 |
| Egern / mihomo DNS 双份 | 改 DNS 段键名 |
| clash 结构 / 分流覆盖 | 改组名 / 改 MATCH |

#### 已发现并修好的假闸门

- **规则集刷新周期（Surge / Egern）**：默认不判负，要 `--strict`。
  接闸门时漏了 ⇒ 已补。

#### 逐个复验结果（8 道全部验完）

上一轮矩阵判「改了没红」的 8 道，**逐个复验后 6 道确认有效、2 道无法本地验证**：

| 闸门 | 复验用的注错 | 结果 |
|:-----|:-------------|:-----|
| Surge DNS lazy / routing | `dns-server = system`（判据 133 行 HIGH） | ❌ 判负 exit=1 |
| profile 结构 | 插入重复的 `[Host]` 段 | ❌ 判负 exit=1 |
| 自托管清单·裸IP检测(AI/emby) | 往 `.list` 追加 `IP-CIDR,1.2.3.4/32` | ❌ 判负 exit=1 |
| DNS 转发泄露·Egern | 删掉 `proxy_nameservers` | ❌ 判负 exit=1 |
| 分流覆盖·Surge | 把全部 `,DIRECT` 改成 `,Proxy` | ❌ 判负（国内探针 0/17） |
| smart 权重口径 | **改全部** `0.15`→`0.99`（改 1 处不够） | ❌ 判负 exit=1 |
| 规则集内容·Surge / mihomo | — | ⚠️ 需联网取规则集内容才能判，本地注错碰不到 |

⚠️ **8 道里没有一道是真摆设** —— 全是我注错没戳中扫描面。
典型：改「香港」不在地区组判据扫的 61 个关键词里；改 1 处权重会被其余值"平均"掉。
**「改了没红」的第一反应应该是「我的注错对不对」，不是「判据失灵」。**

#### 两个附带发现

1. **waive 机制会让 HIGH 不判负。**
   `check_surge_dns.py` 里 profile 带 `# audit-waive:` 声明时，HIGH 被降级为
   WAIVED、退出码不变。设计如此（有意豁免），但**验证时要避开被豁免的项** ——
   实测：删掉 `encrypted-dns-server` 不判负（被 waive），改 `dns-server = system` 才判负。

2. **依赖网络/缓存的判据本地验证不了。**
   `audit_ruleset_content.py` 要联网取规则集内容才能比对 behavior 与内容是否相符；
   本地有缓存 ⇒ 改配置也不重取 ⇒ 本地注错碰不到判据点。
   这类判据的判别力只能靠线上环境观察。

---

### 5 · 新增闸门时的自查清单

- [ ] 读头注的「退出码」一节，确认有没有开关档（如 `--strict`）
- [ ] 设计**至少一组**能让它红的注错，并验证注错生效
- [ ] 验证注错落在它的扫描面内（照着它的输出声明设计）
- [ ] 跑一遍确认红、还原后确认绿
- [ ] 更新本文档第 4 节的清单

---

### 6 · 一句总结

> 闸门的价值不在于它现在绿，而在于**它坏了会红**。
> 没验证过这一点的闸门，等同于没有。

---

## Surge · 判据与命令（surge 侧）

> **何时读**：跑审计脚本前（环境要求 / 命令）、或**要改判据时**。
>
> 逐条事故复盘见 [`pitfalls.md`](./pitfalls.md)。

#### 1 · 环境要求

| 项 | 要求 |
|:---|:-----|
| Python | 3.8+，**仅标准库** |
| 网络 | 只有 `audit_ruleset_content.py` / `audit_routing_coverage.py` 需要；其余脚本与两个 `.sh` 全离线 |
| 操作系统 | Windows（Git Bash）/ macOS / Linux 均可 |
| 磁盘 | 规则集缓存约 6 MB（`direct.txt` 一份十几万条） |
| 输出编码 | 无需设置 —— `_surge_common` 在 import 时把 stdout 钉成 UTF-8（中文 Windows 默认 GBK，emoji 会崩成**退出码 1**）|

⚠️ **Windows / Git Bash 的路径坑**：`pwd` 返回 `/c/Users/...`，
Windows 版 Python 打不开（报 `can't open file 'C:\c\Users\...'`）。
两个 `.sh` 脚本里都做了处理：

```bash
if command -v cygpath >/dev/null 2>&1; then
  PROFILES_W="$(cygpath -w "$PROFILES")"
else
  PROFILES_W="$PROFILES"
fi
```

⚠️ 拼接路径**一律用 `/`**，不要用 `\\` —— `cygpath -w` 给的是 `C:\Users\...`（反斜杠），
再拼 `\\check.py` 在 Linux 上会把反斜杠变成文件名的一部分 ⇒ file not found。

#### 2 · 命令

```bash
S=./self-conf-skills/run/surge

python "$S/check_surge_dns.py"  surge/profiles/lazy.conf              # 期望 exit 0
python "$S/check_surge_dns.py"  surge/profiles/lazy.conf --strict      # medium 也算失败
python "$S/check_surge_dns.py"  surge/profiles/lazy.conf --quiet       # 只打印计数
python "$S/audit_region_filters.py" surge/profiles/routing.conf       # 期望 3 项全过（出处 / 互斥 / 类型）
python "$S/audit_region_filters.py" surge/profiles/routing.conf -v    # 逐个组的关键词数
python "$S/audit_ruleset_refresh.py" surge/profiles/routing.conf --strict  # 期望 exit 0（全部钉在 604800）
python "$S/audit_ruleset_refresh.py" surge/profiles/*.conf --quiet           # 逐份计数（顶层固定名四件；归档不在通配里）
python ./self-conf-skills/gates/check_secrets.py                                # 期望 exit 0

python "$S/audit_ruleset_content.py"  surge/profiles/lazy.conf         # 期望 exit 0
python "$S/audit_ruleset_content.py"  surge/profiles/lazy.conf --show-domestic --force
python "$S/audit_routing_coverage.py" surge/profiles/lazy.conf         # 期望 39/39
python "$S/audit_routing_coverage.py" surge/profiles/routing.conf      # 期望 39/39（期望表自动切换）
python "$S/audit_routing_coverage.py" surge/profiles/lazy.conf --show-all

python ./self-conf-skills/gates/surge/check_surge_dns.py surge/profiles/lazy.conf
python ./self-conf-skills/gates/surge/check_surge_dns.py surge/profiles/routing.conf
```

⭐ **「当前版」是固定名，不是一堆版本号**（2026-09-24 起）：顶层恒为 `routing` / `lazy`
   四个文件名，阶段 2 的 `--strict` 名单、阶段 4 的联网审计、阶段 5 的正则对账、
   当前版本由 profile 头注 `#! version=` 标识。
   「哪一版」只剩 profile 头注 `#! version=routing_vX.Y(.Z)`，形状与两内核一致性由
   `check_min_pair.py` 判（V1–V6 ×2 + V7 一天一版 ×2 + 跨侧 2 条）。配套前置检查：固定名文件不存在 ⇒
   **退出码 2** —— 否则阶段 4 / 5 会对不存在的文件 `continue`，**静默少跑一整个阶段**还报绿。
   要复核历史版本：从 git 历史取出对应文件，带着路径直接调对应脚本。
   `.min` **不手工同步**：改完完整版跑 `python self-conf-skills/run/make_min.py --family routing|lazy|all`
   （默认只出计划，`--apply` 才写盘）—— 它 import 本文件的判据函数，正文重算、注释按锚点继承，
   所以 `# audit-waive:` 那行不用补回去。

⚠️ **顶层固定名四件都要过 `check_surge_dns.py` 与 `audit_ruleset_refresh.py`**
   （对 `profiles/*.conf` 逐份跑）。
分流版同样要求 `0 high / 0 medium`，标准与 `lazy.conf` 一致。

规则集缓存目录：

- Windows：`%TEMP%\surge-ruleset-cache`
- macOS / Linux：`/tmp/surge-ruleset-cache`

用 `--cache-dir` 指定别处；用 `--force` 忽略缓存重下。

#### 3 · 退出码约定

| 码 | 含义 |
|:--:|:-----|
| 0 | 通过 |
| 1 | 有发现（审计器）/ 有断言失败（测试） |
| 2 | **环境故障**：解释器不可用 / 文件缺失 / 用法错误 |

⭐ **退出码 2 是必须的。**

构造的反例**期望退出码 1**。如果解释器坏掉，脚本也返回 1
—— 会被误判成"判负通过"。前置检查把这个歧义消掉：

```bash
if ! "$PY" -c "import sys" >/dev/null 2>&1; then
  printf '\n❌ 前置检查失败：解释器不可用。PY=%s\n' "$PY" >&2
  exit 2
fi
```

> **铁律：审计器的故障绝不能被计成一次成功的判负。**

#### 4 · 12 项判据（`check_surge_dns.py`）

| # | 检查 | 判负级别 | 判据细节 |
|:-:|:-----|:--------:|:---------|
| 1 | 加密 DNS 端点是 IP 字面量 | **HIGH** / MEDIUM / OK | 每个端点过 `ip_literal`；非字面量的逐个列出。另有 MEDIUM：端点在国外（国内线路通常不可达，属取舍） |
| 2 | `dns-server` | **HIGH** / MEDIUM / OK | 缺失 → HIGH；含 `system` → **HIGH**；含主机名 → **HIGH**；国内解析器 < 2 → MEDIUM；否则 OK |
| 3 | `hijack-dns` | LOW / OK | 缺失 → **HIGH**。写 `*` 或 `0.0.0.0:53` → OK。否则算「**已知的**知名境外解析器里还有几个没覆盖」→ LOW（⚠️ **不是按条数判负**，见坑 6） |
| 4 | `encrypted-dns-follow-outbound-mode` | **HIGH** / OK | `true` → HIGH（会成环 / 回退明文）；未设置或 `false` → OK |
| 5 | `always-real-ip` / `use-local-host-item-for-proxy` | **HIGH** / LOW / OK | 缺 `always-real-ip` → LOW；`use-local-host-item-for-proxy = true` → **HIGH** |
| 6 | 测试端点域名归属（**提示性**） | LOW / OK | 逐个看 `internet-test-url` / `proxy-test-url` / `proxy-test-udp`：IP 字面量 → OK；国内域名 → OK；境外域名 → **LOW 提示**（性能取向取舍，见坑 14）；缺失 → LOW。⚠️ **不计入风险等级** |
| 7 | 策略组成员可解析 | **HIGH** / MEDIUM / OK | 空组 → HIGH；未知组类型 → MEDIUM；成员既不在 `[Proxy]` 也不是已知组 / 内置策略 → **HIGH**（Surge 会拒绝加载） |
| 8 | 规则策略可解析 | **HIGH** / MEDIUM / OK | 用 `policy_index` 定位策略字段；类型未识别或字段不足 → MEDIUM（跳过策略校验）；策略不在已知集合 → **HIGH** |
| 9 | 规则顺序 | **HIGH** / MEDIUM / OK | 无 `FINAL` → HIGH；`FINAL` 不在最后 → MEDIUM；IP 类排在域名类之前 → **HIGH** |
| 10 | `pre-matching` 的策略是字面量 | **HIGH** / LOW / OK | 无 `pre-matching` 规则 → LOW；有 `pre-matching` 但策略不是 `reject*` → **HIGH**；缺 `extended-matching` → LOW |
| 11 | `always-real-ip` 被前置域名规则接住 | MEDIUM / LOW / OK | 本地类主机名（`*.lan` 等）不计数。未接住：若文件里有 `RULE-SET` → LOW（远程内容无法静态判定）；否则 → MEDIUM |
| 12 | IP 类规则的 `no-resolve` | MEDIUM / LOW / OK | 无 IP 类规则 → OK；任一带缺 → **MEDIUM**（⚠️ 不是泄露补丁：走代理时解析在代理端；缺它只是多一次冗余解析。真正风险是连带——补它必须同时有域名类国内直连集）；`FINAL` 缺 `dns-failed` → LOW |

#### 4.1 `policy_index` —— 最容易写错的一处

```python
_RULE_TYPES_WITH_VALUE = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "DOMAIN-SET", "URL-REGEX", "USER-AGENT", "PROCESS-NAME",
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "SRC-IP", "DEST-PORT", "SRC-PORT", "PROTOCOL",
    "GEOIP", "IP-GEOIP", "ASN",
}
_RULE_TYPES_NO_VALUE = {"FINAL"}
```

| 形态 | 策略下标 | 例子 |
|:-----|:--------:|:-----|
| 有匹配值 | **2** | `DOMAIN-SUFFIX,x.com,POLICY` / `GEOIP,CN,DIRECT` / `RULE-SET,SET,POLICY` |
| 无匹配值 | **1** | `FINAL,POLICY` |

⚠️ `RULE-SET` 的 index 1 是**规则集标识**（URL / 内置集合名），不是策略。
⚠️ `GEOIP` 属于"有匹配值"（匹配值是 `CN`）。

**这两处各制造过一批假 HIGH**，合计 24 条。详见 [`pitfalls.md`](./pitfalls.md) 坑 4 / 坑 5。

#### 4.2 豁免机制

```
```

写在 **profile 里**，被 `load_waivers` 用正则抓出：

```python
r"#\s*audit-waive:\s*(\d+)\s+(.*)"
```

命中的 finding 降级为 `WAIVED:<原级别>`，**照常逐条打印**在报告末尾的
「⚪ 已豁免」区。它不改判定语义的前提是**它仍然可见**。

⚠️ 这意味着 **`.min.conf` 里也要保留这行** —— 它是**有语义的注释**，不是说明文字。

#### 4.3 报告格式

```
🔴 HIGH · N 条
   [ 1] 消息
        ↳ 细节
🟠 MEDIUM · N 条
...
🟡 LOW · N 条
...
✅ OK · N 条
...
⚪ 已豁免 · N 条（不改判定，但照样列出来）
   [ 1] 消息
        ↳ ⚠️ 已豁免（profile 内声明）：<理由>

──────────────────────────────────────────────────────────────
result: 0 high, 0 medium, 2 low, 12 ok, 2 waived
✅ 通过
```

`--quiet` 只打印最后两行。

#### 5 · 规则集内容判据（`audit_ruleset_content.py`）

对每条远程 `RULE-SET`：

#### A. 缺 `no-resolve` 的 IP 条目

```python
opts = [p.lower for p in parts[2:]]
if "no-resolve" not in opts:
    stats["ip_without_no_resolve"].append((i, s))
```

- 命中任一条 → **HIGH**，并打印前 5 条原文 + 剩余条数
- 有一条启用的 `RULE-SET` 里只要有**一条**这种条目，
  **每个走到该规则的域名都会被强制本地解析一次**

#### B. 直连集合的域名条目总量

把策略判给 `DIRECT` 的所有集合的**域名条目数**加总：

| 总量 | 判定 |
|:-----|:-----|
| < 1000 | **HIGH** —— 「足以接住国内域名的量级」不够 |
| ≥ 1000 | ✅ |

⚠️ **判据是「数域名条目」，不是看规则集名字，也不是看 README 标题。**
见 [`pitfalls.md`](./pitfalls.md) 坑 1 的 `ChinaMax.list` 反例。

#### C. 内置集合跳过

```python
BUILTIN_SETS = {"system", "lan", "direct", "proxy", "final", "reject",
                "domestic", "foreign", "cellular", "wifi"}
```

识别方式：标识里没有 `/`、没有 `\`、没有 `.`。

#### D. 下载失败

`URLError` / `HTTPError` / `OSError` → 计 `medium`（"结论未知"），**不判 HIGH**。
理由：网络抖动不该被报成一个配置缺陷。

#### 6 · 分流覆盖判据（`audit_routing_coverage.py`）

| 组 | 探针数 | 期望 |
|:--:|:------:|:-----|
| A · 国内 | 17 | 全部命中 `DIRECT` |
| B · 境外 | 8 | 命中 `PROXY` 或 `AI`，**不能落 `DIRECT`** |
| C · 误杀 | 8 | **绝不能命中 `REJECT`** |

#### A 的探针刻意混入非 `.cn`

```
www.baidu.com    www.qq.com       www.taobao.com    www.jd.com
www.bilibili.com www.163.com      www.zhihu.com     www.miui.com
connect.rom.miui.com               www.aliyun.com    www.huawei.com
www.iqiyi.com    www.douyin.com   www.meituan.com   www.12306.cn
www.gov.cn       www.people.com.cn
```

17 个里 14 个非 `.cn`。**只测 `.cn` 会假通过** —— 见 [`pitfalls.md`](./pitfalls.md) 坑 2。

#### B 的 `allow` 集合

```python
FOREIGN_PROBES = {
    "chat.openai.com":    {"AI", "PROXY"},
    "api.anthropic.com":  {"AI", "PROXY"},
    "gemini.google.com":  {"AI", "PROXY"},
    "github.com":         {"PROXY"},
    "www.google.com":     {"PROXY"},
    "www.youtube.com":    {"PROXY"},
    "t.me":               {"PROXY"},
    "x.com":              {"PROXY"},
}
```

⚠️ AI 类域名允许落 `AI` 或 `PROXY` —— 用户可能按需删掉 `AI` 组
（AI 流量合流进 `Proxy`）。判据要对"删了 `AI` 组"的配置也成立。

**分流版用另一套期望表**（`FOREIGN_PROBES_ROUTING`），精确到应用组名：

| 探针 | `lazy.conf` 期望 | `routing.conf` 期望 |
|:-----|:-----------------|:--------------------|
| `chat.openai.com` | `AI` / `PROXY` | **`CHATGPT`** |
| `api.anthropic.com` | `AI` / `PROXY` | **`CLAUDE`** |
| `gemini.google.com` | `AI` / `PROXY` | **`GEMINI`** |
| `github.com` | `PROXY` | **`GITHUB`** |
| `www.google.com` | `PROXY` | **`GOOGLE`** |
| `www.youtube.com` | `PROXY` | **`YOUTUBE`** |
| `t.me` | `PROXY` | **`TELEGRAM`** |
| `x.com` | `PROXY` | **`TWITTER`** |

选择哪套表由 `foreign_expectations` 判定，**判据是「文件里实际定义了哪些组」**
（存在 `ChatGPT` / `Claude` 组即为分流版），**不是文件名** ——
所以把分流版改名也不会让期望失配。

⚠️⚠️ **绝不能把判据放宽成「只要不是 DIRECT 就行」。**
那样"整片走兜底"的坏配置会**假通过** —— 而"整片走兜底"恰恰是 Egern 项目实测过的缺陷
（国内域名全落到 `Final → 代理`，两个审计脚本双双通过）。
期望值必须精确到**组名**，才能证明「按应用分流」真的接住了对应域名。

> 🔍 **这张表曾经是"漏项的证据"**：分流版最初只做了 ChatGPT / Claude / AI 三组，
> 于是 6 个探针的期望值被写成 `FINAL` —— 它如实记录了"这些域名没人接住"，
> 但当时被当成了预期行为（`FINAL` 也算"走了代理"，测试全绿）。
> 补上 10 个应用组后，期望值收紧到专属组名，这个坑由此闭合。
> **教训：期望值里出现兜底组名，就值得问一句"本该由谁接住"。**

#### D 的 Apple 探针

```python
APPLE_PROBES = [
    "www.apple.com", "swcdn.apple.com", "gs-loc.apple.com",
    "courier.push.apple.com", "apps.apple.com", "itunes.apple.com",
]
```

这 6 个必须命中 `DIRECT`，但接住它们的是三处不同来源：`gs-loc.apple.com` 与
`courier.push.apple.com` 由内置 `SYSTEM` 接住（`push.apple.com` 是后缀条目、`gs-loc` 是精确条目），
`www.apple.com` / `swcdn.apple.com` 由 `direct.txt` 的精确条目接住，`apps.apple.com` /
`itunes.apple.com` 靠分流版的 `apple.txt`。

⚠️ **2026-10-04 换源**：这条原本引 `Apple_All_No_Resolve.list`，探针里的 `developer.apple.com` /
`gateway.icloud.com` 靠它才直连；换成只含「在中国大陆可直连」的 `apple.txt` 后，这两个
（连同国际版 iCloud 端点、`apple-cloudkit.com`）**按设计改走代理**，故已从期望里移出。
要让它们回直连，得再补 `icloud.txt` 之类。

⚠️ 判据意义：Apple 流量走代理**不会报错**，只会「变慢 + 推送偶发延迟」——
属于用户不会主动报障、但体验确实变差的一类，所以必须靠审计钉住。

#### C 的意义

`github.com` / `jsdelivr.net` / `icloud.com` 这类高频域几乎必然出现在
广告黑名单的误杀面里。**提前发现误杀比等用户报障好。**

#### 匹配器实现的边界

`Matcher` 只能按**域名**判定。以下类型**跳过**（无法用域名判定）：

- IP 类（`IP-CIDR` / `GEOIP` / `IP-ASN`）
- `URL-REGEX` / `USER-AGENT` / `PROCESS-NAME` / `PROTOCOL` / 端口类
- `FINAL` —— 命中即返回，作为兜底
- **内置集合**（`SYSTEM` / `LAN`）—— 内容不可得，**视作不命中**

⚠️ 最后一条是个已知的保守近似：探针恰好落在 `SYSTEM` 集合里时会走 `FINAL`，
判据仍会通过（因为 `FINAL → Proxy` 对境外探针是正确的）。
若将来有探针因此误判，应改成显式枚举内置集合的已知内容。

#### 7 · 架构不变量

> ⚠️ **2026-10-08 更正**：本节原把「① 占位符纪律」与「② DNS 段一致性（3 条断言）」
> 都写成 `check_secrets.py` 的职责 —— 但**② 在代码里从来不存在**。
> 这是用「全新 AI 实测」发现的：**文档在为不存在的事实背书**。
> 现已补上实现（`gates/check_dns_parity.py`，进闸门），文档与代码对齐。

**① 占位符纪律** → `gates/check_secrets.py`
**② DNS 段一致性** → `gates/check_dns_parity.py`

#### ① 占位符纪律

| 判据 | 细节 |
|:-----|:-----|
| 扫描面 | **全仓** walk 到的 `*.conf` / `*.yaml` / `*.yml`（不是只有 `surge/profiles/`）。`LIVE` 当前版 / `FIXTURE` `self-conf-skills/gates/`，档位只决定报错怎么点名。跳过 `.` 开头目录 / `node_modules` / `__pycache__`；刻意不用 `git ls-files`（未提交的本地工作副本正是这道纪律要拦的东西） |
| 禁止子串 | `tange365.com` / `wangxinyu` —— **注释里也不许出现**（旧仓教训黑名单，条条有据；无据可考的串不入列） |
| IPv4 白名单 | 必须是 `192.0.2.` / `198.51.100.` / `203.0.113.` 开头，或在 `KNOWN_DNS` 集合里 |
| 凭据 | `password` / `username` / `auth` 的值必须以 `REPLACE_WITH_` 开头 |
| SNI | 必须 `REPLACE_WITH_*` / 文档段 IP / `example.com` 结尾 |
| 节点主机名 | `[Proxy]` 段里非 IPv4 的 `server` 必须在 `ALLOWED_DOMAINS` 里 |

⚠️ IPv4 判据只扫**有效行**（`strip_c` 剥掉整行注释与行尾注释）——
注释里出现私有网段是说明性文字，不是泄露。见 [`pitfalls.md`](./pitfalls.md) 坑 8。

⚠️ `strip_c` **只右裁、不左裁**：YAML 的行首缩进就是层级本身，连行首一起裁会让
`proxies:` 块提前关闭，①-d 对 Egern 侧整段静默失效（2026-09-25 实测踩到）。

#### ② DNS 段一致性（两组，共 3 条断言）

16 个键逐字比对：

```python
DNS_KEYS = [
    "dns-server", "encrypted-dns-server", "encrypted-dns-follow-outbound-mode",
    "hijack-dns", "allow-dns-svcb", "exclude-simple-hostnames", "read-etc-hosts",
    "use-local-host-item-for-proxy", "ipv6", "ipv6-vif",
    "geoip-maxmind-url", "disable-geoip-db-auto-update",
    "internet-test-url", "proxy-test-url", "proxy-test-udp",
    "always-real-ip",
]
```

| 断言 | 比对对象 | 理由 | 谁在守 |
|:-----|:---------|:-----|:--|
| ②-a | `lazy.conf` ↔ `lazy.min.conf` | `.min.conf` 的定位是「去掉注释」，不是「裁剪配置」 | `gates/check_min_pair.py` |
| ②-b | `routing.conf` ↔ `routing.min.conf` | 同上 | 同上 |
| ②-c | `lazy.conf` ↔ `routing.conf` | **防泄露标准不因分流粒度而变** | `gates/check_dns_parity.py` |

任一键只在一边存在、或值不同 → 失败。

⚠️ **②-c 对 mihomo 只守「底线键」，不要求端点字面相同**（实测校准）：
`fallback` / `fallback-filter` 懒人版**刻意不配**（§13.3）；
端点也不同（分流版 `doh.18bit.cn`、懒人版 `223.5.5.5`）——
差异在**脚本源头**就存在，是设计而非漂移。
该判据守的是「两边都加密、IPv6 都关、双层广告拦截都在」。

⚠️ ②-c 是这份测试里**唯一一条跨配置**的断言。它挡的是这种想法：
"反正这是分流版，DNS 段差不多就行"。两份配置的防泄露结构必须**完全相同** ——
差别只允许出现在 `[Proxy Group]` 与 `[Rule]` 的粒度上。

⚠️ 改 `DNS_KEYS` 时注意：它同时是 ②-a / ②-b / ②-c 的依据，
且 `routing.min.conf` 是用脚本从 `routing.conf` 生成的 —— 生成脚本会**丢掉注释**，
所以 profile 里的 `# audit-waive:` 行必须**手动补回 min 版**（否则豁免失效、
审计器会对 min 版报 HIGH）。这是已知缺陷，见 § 退出码约定上方的说明。

#### ③ 规则顺序铁律

| 断言 | 判据 |
|:-----|:-----|
| ③-a | `FINAL` 必须是最后一条 |
| ③-b (i) | 白名单 DIRECT 在第一条 REJECT 之前；且**只能有一条** |
| ③-b (ii) | 第一条 REJECT 之后**必须有** DIRECT 规则（否则国内流量整片走代理） |
| ③-c | 所有 IP 类规则在所有域名类规则之后 |
| ③-d | 所有 IP 类规则带 `no-resolve` |

⚠️ ③-b 的两条是**独立的约束**，不是「DIRECT 在 REJECT 之前」一条。
见 [`pitfalls.md`](./pitfalls.md) 坑 9。

#### 9 · 全绿 ≠ 可用

审计脚本覆盖的是**静态可判定**的部分。以下必须实测：

| 维度 | 为什么脚本做不到 | 怎么做 |
|:-----|:-----------------|:-------|
| 冷启动有无明文 `:53` | 需要抓包 | Charles / Stream / Wireshark |
| 拦截效果 | 需要真实访问 | 打开几个广告密集的站点看 |
| 误杀 | 需要真实访问 | `github.com` / `jsdelivr.net` / `icloud.com` 是否能开 |
| 节点可用性 | 需要真实网络 | 面板上逐个测 |
| NAT 类型 / 时间同步 | 需要真实设备 | 游戏机连一下 |

> ⚠️ 这是本项目的核心立场：**审计通过 ≠ 配置可用。**
> 每修好一次判据，都要假设「还存在审计器看不见的维度」。

---

## Egern · 判据与命令（egern 侧）

> **何时读**：跑审计脚本前（命令与环境要求），或要改判据时。

#### 1 · 环境要求

| 项 | 要求 |
|:---|:-----|
| Python | 3.8+，**仅标准库 + PyYAML** |
| Node.js | **仅 `check_script_sync.py` 与 `check_remote_urls.py` 需要**（要执行 `override/*.js`）。`_clash_common.find_node` 先 `shutil.which("node")`，再探测 `C:/Program Files/nodejs/node.exe` |
| curl | `check_remote_urls.py` 需要（HEAD / GET 探测） |
| 网络 | 只有 `check_remote_urls.py` 需要；其余 mihomo 门禁全离线 |
| 输出编码 | 无需设置 —— 每个脚本 import 时把 stdout/stderr 钉成 UTF-8（Windows 默认 cp936，emoji 会崩成**退出码 1**，而 1 恰是判负码）|

⚠️ **Windows 上 `subprocess` 不继承 Git Bash 扩展的 PATH**，直接 `subprocess.run(["node", ...])` 会 `WinError 2`。
这是 `_clash_common.find_node` 存在的唯一理由 —— 别"简化"掉它。

⚠️ **工作目录（CWD）优先**。所有 clash 门禁的 `_default_root` 都是同一段逻辑：

```python
def _default_root:
    """定位 clash 配置目录（含 profiles/ 与 override/）。

    两种布局都支持：
      · 整合仓 self-conf：配置在 <root>/clash/ 下
      · 单仓 Clash：配置就在 <root> 下
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

判据是「**同时含 `profiles/` 与 `override/`**」，不是目录名。

> 📌 这段是 2026-09-29 **CI 暴露后改的**：原实现基于 `__file__` 向上推算，
> 在 GitHub Actions 的调用方式下算错目录 ⇒ Linux 上全绿、CI 上报「缺文件」。
> **本地全绿 ≠ 线上能跑** —— 路径探测这类环境相关的东西，必须让 CI 跑一遍才算数。

⚠️ 千万别"顺手"把 CWD 优先改回 `__file__` 优先。那是已经踩过的坑（见 `AGENTS.md` §7）。

#### 2 · 命令

```bash
python self-conf-skills/gates/verify_all.py                  # 期望 exit 0
python self-conf-skills/gates/verify_all.py -v               # 无论红绿都打印每个闸门输出尾部
python self-conf-skills/gates/verify_all.py --index          # 只读列闸门清单（不跑、不判负、exit 0）

python self-conf-skills/gates/clash/check_structure.py       # 期望 exit 0
python self-conf-skills/gates/check_min_pair.py        # 期望 exit 0
python self-conf-skills/gates/clash/check_script_sync.py     # 期望 exit 0（需 node）
python self-conf-skills/run/clash/build_rules.py --check # 期望 exit 0（生成物新鲜度）

python self-conf-skills/gates/clash/check_remote_urls.py                 # 期望 exit 0
python self-conf-skills/gates/clash/check_remote_urls.py --skip-self     # 跳过本仓 raw 地址
python self-conf-skills/gates/clash/check_remote_urls.py --timeout 20    # 调超时（默认 15s）

python self-conf-skills/gates/check_secrets.py               # 占位符 / 凭据扫描（全仓）
python self-conf-skills/gates/check_selfcontained.py         # 整合仓自洽性
```

所有 clash 门禁都接受**可选的仓库根参数**：`python self-conf-skills/gates/clash/check_structure.py <根目录>`。
不传就用 `_default_root`。**这正是不带参数时在仓库根调用能工作的原因**（CWD → CWD/clash 命中）。

⚠️ `python self-conf-skills/gates/check_secrets.py` 与 `self-conf-skills/gates/clash/check_secrets.py` 是**两个不同的脚本**：

| 脚本 | 扫描面 | 判据 |
|:-----|:-------|:-----|
| `self-conf-skills/gates/check_secrets.py`（跨内核，进闸门）| 全仓 walk 到的 `.conf` / `.yaml` / `.yml`，**跳过 `icons/`** | 禁串 `tange365.com` / `wangxinyu`；IPv4 白名单；`YAML_CRED_KEYS` 值必须占位 |
| `self-conf-skills/gates/clash/check_secrets.py`（mihomo 版）| 全仓 walk 到的 `.js` / `.yaml` / `.yml` / `.md` / `.conf` / `.list` / `.txt` / `.json`，**跳过 `icons/` 与 `rules/` 的主机扫描** | 凭据字段非占位即报；IPv4 白名单；主机白名单；私钥头无条件报 |

两者互不可替代：mihomo 版能扫 `.js`（脚本里也有订阅 URL），跨内核版带禁串黑名单
（旧仓教训，条条有据）。**改名合并会同时丢掉两边的判据。**

#### 3 · 退出码约定

全仓统一（出处：`reference/pitfalls.md` §8.2）：

| 码 | 含义 | 处理 |
|:--:|:-----|:-----|
| 0 | 判据全过 | — |
| 1 | 有判负 | 看输出修配置 |
| 2 | **前置环境不达标**（缺解释器 / 缺 PyYAML / 文件缺失 / 用法错误）| ⚠️ **计入失败**，先修环境，别读判据 |
| 3 | **SKIP（未验证）** | 不计入失败，但汇总表**必须明示「未验证 ≠ 绿」** |

⭐ **退出码 2 必须与 1 分开。** 构造的反例期望退出码 1；解释器坏掉时脚本也返回 1
—— 会被误读成「判负成功」，即**假绿**。

> **铁律：审计器的故障绝不能被计成一次成功的判负。**

⭐ **3 的准入只有一条：「没读到远端真值」。**
两个方向都算滥用：① 故障 / 未知错误不许退 3（该退 2，退了会被当 SKIP 吞成假绿）；
② 读到远端、断言不过也不许退 3（该退 1，否则等于用「未验证」躲判定，同样是假绿）。

各 clash 脚本实际用到的码：

| 脚本 | 用得到的码 |
|:-----|:-----------|
| `clash/check_structure.py` | 0 / 1 / **2**（缺 PyYAML 时 `sys.exit(2)`）|
| `clash/check_min_pair.py` | 0 / 1 / **2**（缺 PyYAML）|
| `clash/check_script_sync.py` | 0 / 1 / **2**（缺 PyYAML）|
| `clash/check_remote_urls.py` | 0 / 1 / **2**（`未收集到任何远程 URL` ⇒ 收集规则坏了）|
| `self-conf-skills/gates/clash/check_secrets.py` | 0 / 1 |
| `scripts/clash/build_rules.py` | 0 / 1 |
| `check_selfcontained.py` | 0 / 1 |

#### 4 · 结构判据（`clash/check_structure.py`）

扫四份 profile（`lazy.yaml` / `lazy.min.yaml` / `routing.yaml` / `routing.min.yaml`），
**四份全过才算过**。守四类事：

#### ① 无悬空引用

```python
BUILTIN = {"DIRECT", "REJECT", "PASS", "GLOBAL", "PROXY"}
for g in groups:
    for m in (g.get("proxies") or []):
        if m not in gnames and m not in BUILTIN and m not in pnames:
            errs.append("悬空引用: 组 %s -> %s" % (g.get("name"), m))
```

合法成员三类：另一个已定义的组 / 内置策略 / **`proxies` 里定义的节点名**（含占位节点 `Node-A` / `Node-B`）。

⚠️ 为什么必须机器判：**mihomo 不报错，直接把无效成员当不存在略过** —— 该组的出口悄悄变了，
配置照常加载，用户只会觉得"这个组好像空的"。

#### ② 规则指向存在的组 + 规则集已定义

```python
for r in c.get("rules") or []:
    p = r.split(",")
    if p[0].strip == "RULE-SET":
        if len(p) < 3:
            errs.append("规则格式错: %s" % r); continue
        prov, pol = p[1].strip, p[2].strip
        if prov not in provs:  errs.append("规则引用了未定义的规则集: %s" % prov)
        if pol not in gnames and pol not in BUILTIN:
            errs.append("规则指向了不存在的组: %s" % pol)
    elif p[0].strip == "MATCH":
        pol = p[1].strip if len(p) > 1 else ""
        if pol not in gnames and pol not in BUILTIN:
            errs.append("MATCH 指向了不存在的组: %s" % pol)
```

⚠️ `len(p) < 3` 时 `continue` —— 少一个字段是**格式错**，不是"引用了空集"。
不 `continue` 会拿 `p[2]` 越界。

#### ③ DNS 广告拦截的两个必要条件

缺任一条拦截就不生效，且**不报错**，所以必须机器判：

| 条件 | 判据 |
|:-----|:-----|
| a) `nameserver-policy` 里有 `rule-set:<广告集>` → `rcode://success` | `ads_np = [k for k in npol if str(npol[k]).startswith("rcode://")]`；空 ⇒ 报错 |
| b) 同一个广告集在 `fake-ip-filter` 里也列了一遍 | `ads_ff = [x for x in ffil if x.startswith("rule-set:")]`；空 ⇒ 报错 |
| c) 两处集合**必须相等** | `{k.replace("rule-set:","") for k in ads_np} != ff_sets` ⇒ 报错「广告集两处不一致」|
| d) 广告项排在 `private,cn` **之前** | `min(ads_idx) > min(cn_idx)` ⇒ 报错「会先命中 cn 而拿不到空回答」|

判据 c 为什么要「相等」而不是「非空」：只在一处列出 ⇒ 广告域拿不到空回答（缺 b）
或拿到空回答却在 fake-ip 模式下不走真实解析（缺 a）**之一**成立，效果都是半截。
**两处是同一件事的两半**，缺一半等于没做。

判据 d 的理由：`nameserver-policy` 是**按顺序**匹配的。一旦 `geosite:private,cn` 先命中，
国内域名（含广告域）就被送到国内解析器拿真实 IP 了 —— `rcode://success` 永不再看。
本仓四份 profile 的实际顺序都是广告在前（见 `gates.md` 的「12 项判据」§4.1）。

##### 4.1 现役配置的实际值（`routing.yaml` 为例）

```yaml
nameserver-policy:
  rule-set:AWAvenue-Ads: rcode://success
  rule-set:Jinx-Ads: rcode://success
  rule-set:private,cn:
    - https://doh.18bit.cn/dns-query
    - https://dns.alidns.com/dns-query
fake-ip-filter:
  - '*.lan' … （15 条域名类）
  - rule-set:AWAvenue-Ads
  - rule-set:Jinx-Ads
```

⚠️ `lazy.yaml` 用的是 `geosite:private,cn`（带 `geosite:` 前缀），`routing.yaml` 用的是
`rule-set:private,cn`。两者都能命中 —— 判据 d 的 `cn_idx` 检测同时认 `"private,cn" in k`
与 `k.split(":")[-1] == "cn"`，**两种写法都覆盖**。

#### ④ IPv6 已显式关闭

```python
if c.get("ipv6") is not False:
    errs.append("顶层 ipv6 未显式关闭")
if dns.get("ipv6") is not False:
    errs.append("dns.ipv6 未显式关闭")
```

⚠️ 用的是 `is not False`，**不是** `!= False` 也不是 `if c.get("ipv6")`：
- 写成 `if c.get("ipv6")` ⇒ `ipv6` 键缺失时也"通过"（`None` 是 falsy）——**漏报**；
- 用 `is not False` ⇒ **缺失也判负**，符合"显式声明"的要求。

⚠️ 为什么要显式写：见 [`ops.md`](./ops.md) §6 ——
`dns.ipv6: true` 会返回 AAAA，而本机真实 IPv6 未被 TUN 完整接管 ⇒ **双栈站点绕过 TUN**。
`ipv6: false` 虽等于 mihomo 默认值也必须写（与姊妹仓对齐面的同一条纪律：
显式声明键不适用"默认值就不写"）。

#### 4.2 失败怎么修

| 报错 | 修法 |
|:-----|:-----|
| `悬空引用: 组 X -> Y` | 改对名字；或确认 `Y` 是 `proxies` 里的节点名 / 另一个组 / 内置策略 |
| `规则引用了未定义的规则集: X` | 在 `rule-providers` 里补定义，或改规则指向已有的键 |
| `规则指向了不存在的组: X` / `MATCH 指向了不存在的组: X` | 补组，或改指向（注意 `MATCH` 是兜底，策略必须是**已定义的组**，写节点名不行）|
| `DNS 层广告拦截缺失：nameserver-policy 无 rcode://success` | 给广告集加 `rcode://success` |
| `DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集` | 在 `fake-ip-filter` 里补 `rule-set:<同名>` |
| `广告集两处不一致：policy=[…] / fake-ip=[…]` | 两处补成同一组集合 |
| `广告 policy 排在 cn 之后` | 把 `rcode://success` 那几行移到 `nameserver-policy` 的**最前** |
| `顶层 ipv6 未显式关闭` / `dns.ipv6 未显式关闭` | 补 `ipv6: false`（顶层 + `dns:` 下各一处）|

⚠️ 四份 profile 都要改（`.min` 是同一份配置的另一种形态，见 §5）。
**只改完整版会让 `check_min_pair.py` 立刻判负。**

#### 5 · 两形态对拍（`clash/check_min_pair.py`）

#### 为什么单独要这一项

每份 profile 都有两份形态（`.yaml` 带注释 / `.min.yaml` 纯配置）。`.min` 的定位是
**同一份配置去掉注释**，不是"裁剪配置"。一旦两版配置本体漂移：

> 照着文档改完整版、实际导入的却是 `.min` ⇒ **改了个寂寞**，而且肉眼看不出来。

本仓踩过：`routing.yaml` 由脚本重新生成后忘了同步重生成 `.min`，两份不一致，
而静态文件**不会报错**。

#### 判据

```python
a = yaml.safe_load(open(pf, encoding="utf-8"))
b = yaml.safe_load(open(pm, encoding="utf-8"))
d = diff(a, b)
```

**比 Python 对象，不是比文本。** 因此注释、键顺序、缩进、引号风格**都不影响判定**，
只看配置本体。`diff` 递归：

| 情形 | 报告 |
|:-----|:-----|
| 类型不同（int/float 互转除外）| `X 类型不同: str vs int` |
| dict 键只在一侧 | `X.k 仅 min 有` / `X.k 仅完整版有` |
| list 长度不同 | `X 长度不同: 11 vs 12` |
| 逐元素递归 | `X[0] 值不同: 'A' vs 'B'` |

**任何一处不同即判负**。输出最多列 10 条，其余折叠为「另 N 处」。
比对对：`lazy ↔ lazy.min`、`routing ↔ routing.min`。

#### 5.1 `.min` 怎么同步

改完完整版，**同步 `.min`**：

⚠️ **mihomo 侧没有 `.min` 生成脚本。** `make_min.py --family` 的合法取值只有
`routing` / `lazy` / `all`，而它的 `FAMILIES` 表**只含 surge 与 egern 两族**
（`surge/profiles/*.conf`、`egern/profiles/*.yaml`）——
**`clash/profiles/*.min.yaml` 不在里面**。

⇒ 所以 `.min.yaml` 目前只能**手工同步**（去掉注释与空行）。
`check_min_pair.py` 就是用来兜住这件事的：它比 YAML 对象，注释不进比对，
所以手工同步只要保证**配置本体一致**即可。

> 📌 **这是已知的自动化缺口**（见 §16.4）：mihomo 侧的 `.min` 靠人工 + 对拍，
> 不靠生成器。要补的话是给 `make_min.py` 的 `FAMILIES` 加一族 clash。

⚠️ 与 surge 侧的另一个差异值得记：Surge 的 `routing.min.conf` 由脚本生成，
生成脚本会**丢掉注释** ⇒ `# audit-waive:` 行必须手动补回 min 版，否则豁免失效、
审计器会对 min 版报 HIGH（姊妹仓已知缺陷）。
**mihomo 侧不适用这条** —— 比的是 YAML 对象，注释根本不进比对，
`.min.yaml` 不需要保留任何有语义的注释。**别把 Surge 侧的注意事项搬过来。**

#### 5.2 失败怎么修

看到 `NG profiles/lazy.yaml vs profiles/lazy.min.yaml —— N 处差异`：

1. 确认哪一侧是"对"的（通常是刚改过的完整版）；
2. 按差异清单**同步 `.min`**（本仓没有生成器，只能手工，见 §5.1）；
   最省事的做法是用 `yaml.safe_load` + `yaml.safe_dump` 重出一份纯配置，
   再比对 —— 别逐行手改；
3. 再跑一次 `check_min_pair.py` 确认归零。

⚠️ 若差异集中在 `.dns.*`，先怀疑是**只改了完整版的 DNS 段** —— DNS 段在四份里必须完全一致。

#### 6 · 脚本 ↔ 静态对拍（`clash/check_script_sync.py`）

#### 为什么单独要这一项（本仓特有，姊妹仓没有）

mihomo 侧每份配置有**两个交付形态**：

| 形态 | 路径 | 用法 |
|:-----|:-----|:-----|
| 静态文件 | `clash/profiles/routing.yaml` | 下载即用 |
| 覆写脚本 | `clash/override/my_clash.js` | 挂到任意订阅上 |

两者是**同一套配置**的两种形态，脚本的输出就应该是静态文件的样子。一旦漂移：

> 用户会遇到「照文档用脚本订阅，效果跟直接导入配置不一样」，
> 而且**两边都能正常跑、都不报错** —— 只能靠对拍发现。

#### 判据

以**空订阅**执行脚本（`{proxies: [], proxy-groups: [], rules: [], dns: {}}`），
取 `proxy-groups` / `rule-providers` / `rules` / `dns` / `ipv6` 与静态 profile 比对：

| 字段 | 判据 |
|:-----|:-----|
| `rules` | **逐位一致**（顺序也算）|
| `rule-providers` | **URL 集合相等**（键名可差）|
| `proxy-groups` | `脚本组 ∪ 模板专属组 ⊇ 静态组`；非模板专属组的**子节点必须一致** |
| `dns` | 除 `listen` 外逐键一致 |
| `ipv6` | 必须相同 |

比对对：`my_clash.js ↔ routing.yaml`、`my_clash_lazy.js ↔ lazy.yaml`。

#### 6.1 两处有意差异（命中不判负，但打印提醒）

```python
TEMPLATE_ONLY_GROUPS = {"Low Mult.", "Auto", "High Mult."}
EXPECTED_DIFF = {
    "Smart": "模板三档 fallback vs 脚本单组 fallback（机制差异，非漂移）",
}
SKIP_DNS_KEYS = {"listen"}
```

- **Smart 三档**：模板能用 `filter` 在**运行时**按倍率分档，脚本在订阅加载时执行一次、
  看不到 provider 节点名 ⇒ 脚本侧只能是单组 fallback。这是**内核机制决定的**，
  不是漂移。故脚本侧 Smart 的子节点（`[Low Mult., Auto, High Mult.]` vs 单组）命中
  `EXPECTED_DIFF` ⇒ 只打印 `~ 已知差异 Smart: …`，不判负。
- **`listen`**：DNS 监听端口交给客户端决定，不参与比对。

⚠️ 别把 `EXPECTED_DIFF` 当成"可以往里加东西的豁免清单"。它只有一条，
理由是**机制不可能对齐**。任何"写起来麻烦"的差异都应该改脚本，不是加白名单。

#### 6.2 漂移分支的诊断（原 `NameError` 已修）

```python
if out.get("rules") != (st.get("rules") or []):
    errs.extend(diff(out.get("rules") or [], st.get("rules") or [], "rules"))
    errs.extend(diff(norm_dns(...), norm_dns(...), "dns"))
```

`check_script_sync.py` **没有定义也没有导入 `diff`**（`check_min_pair.py` 里有同名函数，
但没有共享模块）。因此：

| 情形 | 实际行为 |
|:-----|:---------|
| 脚本与静态一致（现役状态）| ✅ 走到 `if` 都为假，**`diff` 从未被调用** ⇒ `OK`，exit 0 |
| 脚本 `rules` 漂移 | 💥 `NameError: name 'diff' is not defined`，**以退出码 1 结束** |
| 脚本 `dns` 漂移 | 💥 同上 |

> 🔴 **这是一条必须记账的事实**：这道闸门在**真正要判负的那一次**不是"报出差异"，
> 而是崩在 `NameError`。退出码碰巧也是 1，所以 `verify_all.py` 仍会标红 ——
> **闸门不会假绿，但它给不出任何诊断信息**：没有「第几条规则不同」、没有「哪个 dns 键不同」，
> 只有一段 traceback。
>
> ✅ **已修（commit `7d7250c`）**：`diff` 现已定义在本文件第 94 行，判负时能给出
> 精确诊断（实测：注入一条额外规则 ⇒ 输出 `rules 长度不同: 脚本 12 vs 静态 11`），
> 不再是 `NameError` traceback。
>
> ⚠️ 文档滞后提示（2026-10-07 零信任自查）：本节标题与「修法（未做）」曾长期未同步，
> 让维护者误以为此坑仍在。改代码后请同步回头改这里的记录。
>
> **如需进一步定位**（哪一条规则不同而不是只报长度）：手工 diff 脚本输出与静态 profile 的
> `rules` / `dns` 两段（见 §6.3）。

#### 6.3 失败怎么修

1. 先分清是**哪种漂移**：读报错行（修好 `NameError` 前只能人工 diff）。
2. `rules` 漂移 ⇒ 改 `override/my_clash*.js` 里的规则数组，或改静态 profile。
   ⚠️ **规则是逐位比对的**，插一条/删一条/换顺序都会判负。
3. `dns` 漂移 ⇒ 两处的 `dns` 块除 `listen` 外必须逐键相同。
   常见是只改了一侧的端点。
4. `ipv6` 漂移 ⇒ 脚本里 `config.ipv6 = false` 与静态 `ipv6: false` 对齐。
5. 改完跑 `check_script_sync.py` 与 `check_structure.py`（后者会同时校验四份 profile）。

#### 7 · 远程集可达性（`clash/check_remote_urls.py`）

#### 为什么单独要这一项（本仓的切肤之痛）

> Jinx 上游把 `*-white-guard.*` 改名为 `*-direct.*`，本仓脚本里那条
> `mihomo-white-guard.yaml` 就此 404。分流版改配置时碰巧发现并修了，
> **懒人版一直挂着死链没人察觉** —— 因为本仓当时没有 CI，没人定期去问
> 「这个 URL 还活着吗」。

死链的后果**不是报错，是静默降级**：rule-provider 拉不到 ⇒ 变成空集 ⇒
该走 `AD` 的广告全进了兜底出口。**配置看着跑得挺好，其实拦截没了。**

#### 收集规则（两条路径，缺一不可）

| 路径 | 抓什么 | 为什么需要 |
|:-----|:-------|:-----------|
| `collect_urls`（纯文本扫）| `override/` 与 `profiles/` 里 `.js` / `.yaml` / `.yml` 中的 http(s) URL | 覆盖注释与字面量 |
| `collect_from_scripts`（**真的跑一遍脚本**）| `rule-providers` 的 `url`、策略组的 `icon` | 脚本里 MRS 是 `JS + "/geosite/" + c + ".mrs"` **拼接**出来的，纯文本扫描抓不到完整 URL |

⚠️ 第二条是关键设计：**不跑脚本就收集不到拼接出来的地址**。只做文本扫描这道门等于半瞎。

#### 排除规则（避免误判）

| 排除项 | 常量 / 条件 | 理由 |
|:-------|:------------|:-----|
| 占位地址 | `PLACEHOLDER_PAT`（`example.com` / `REPLACE_WITH` / `YOUR_TOKEN` / `localhost` / `127.0.0.1`）| 给用户替换的订阅槽位，**本来就不该可达** |
| 基址常量 | `BASE_URLS`（icons 目录 / 仓库根 / MetaCubeX geo 目录）| 是拼接用的前缀，不是可探测的资源 |
| DoH 端点 | `DOH_PAT`（`/dns-query$`）| 是解析器不是静态资源，HEAD 往往不通 |
| 健康检查探针 | `HC_URLS`（`www.gstatic.com/generate_204`）| 连通性探测用 |
| 非静态后缀 | `RESOURCE_SUFFIX = (".mrs", ".yaml", ".yml", ".list", ".txt", ".json")` | **只有这些后缀才探测** |

#### 探测与判据

```python
for method in ("HEAD", "GET"):
    cmd = ["curl", "-sS", "-L", "--max-time", str(timeout),
           "-o", os.devnull, "-w", "%{http_code}", "-X", method, url]
```

- **HEAD 不通则退化为 GET**（部分 CDN 不支持 HEAD）
- `200 <= code < 400` ⇒ 通过；否则判负并打印 URL 与出处
- `--skip-self` 跳过 `SELF_PREFIX`（本仓 raw 地址）—— 文件刚推送、CDN 未同步时会短暂 404

⚠️ 判据是「**非 2xx / 3xx 即判负**」，不是「连得上就行」。3xx 放行是因为 `-L` 已跟随、
且 jsDelivr 一类 CDN 常以 3xx 起手。

#### 7.1 失败怎么修

| 报错 | 修法 |
|:-----|:-----|
| `死链 N 个` + `出处: override/xxx.js (运行期)` | 改脚本里的拼接/常量；**同时**确认静态 profile 里的同款 URL 也改了 |
| `死链` + `出处: profiles/xxx.yaml` | 改静态 profile；若脚本也引用了同款，一并改 |
| 本仓 raw 地址 404 | 本地用 `--skip-self` 排除；CI 侧**用重跑而非跳过** |
| `未收集到任何远程 URL —— 检查收集规则`（exit 2）| 先看是不是**在没有 `profiles/`+`override/` 的目录**下跑的（`_default_root` 落到了 CWD）；其次看 `--skip-self` 是否把全部目标都跳过了 |

⚠️ **改 URL 后必须同时跑 `check_script_sync.py`** —— 它比对两侧 `rule-providers` 的 URL 集合，
只改一侧会立刻判负。

#### 8 · 生成物新鲜度（`build_rules.py`）

#### 为什么需要（合并项目最直接的收益）

此前三个内核**各存一份相同内容**的规则集，
一份 `.list`（Surge / Egern 原生）、一份 `.yaml`（mihomo payload）。内容逐条相同
（emby 4 / apple_system 18 / AI 272），只是格式不同 —— **双份维护，改一处忘一处就漂移**。

合并后：`.list` 是**唯一真源**，`.yaml` 由脚本生成。**单一真源，物理上不可能漂移。**

```python
TARGETS = [
    ("emby.list", "emby.yaml", "Emby 自用枚举域名 → Emby 组"),
    ("apple_system.list", "apple_system.yaml", "Apple 系统域 → DIRECT"),
    ("AI.list", "AI_Domains.yaml", "AI 伴生域 → AI 组"),
]
```

#### 判据

```python
rules = read_rules(sp)
want  = render(dst, src, desc, rules)
have  = open(dp, encoding="utf-8").read if os.path.exists(dp) else None
if have == want:      print("  OK … (已是最新)")
elif check:           print("  NG rules/%s 已过期（真源 %s 有更新）"); stale.append(dst)
else:                 open(dp, "w", …).write(want)   # 重新生成
```

**逐字节比对 `render` 的期望输出与磁盘内容**（含头部注释里的条数）。
真源缺失 ⇒ `NG 真源缺失` 并计 stale。

| 模式 | 行为 | 退出码 |
|:-----|:-----|:------:|
| 默认 | 重写出过期/缺失的生成物 | 0（除非真源缺失 ⇒ 1）|
| `--check`（CI 用）| **只检查**，过期即判负，不写盘 | 0 / 1 |

#### 8.1 头部注释是有语义的

生成物头部写明「本文件由 `build_rules.py` 自动生成，请勿手工编辑」与条数，
末尾一句尤其重要：

```
```

⇒ 这是 [`ops.md`](./ops.md) §4（规则判定触发的解析）的直接依据：
**零 IP 条目的规则集不需要 `no-resolve`**，写了反而有害（见下节）。

#### 8.2 失败怎么修

```bash
python self-conf-skills/run/clash/build_rules.py           # 重新生成（不是改 .yaml）
```

❌ **红线：不手工编辑 `rules/*.yaml`**（`AGENTS.md` §8）。改内容只改 `.list`，重跑脚本。

#### 9 · 判别力：怎么证明门禁真的会判负

#### 9.1 为什么"好配置通过"证明不了任何事

> 只测「好配置通过」是**证明不了判别力**的。
> 一个恒返回 0 的脚本也能让现役配置全绿。

本仓对判别力的要求（与 `check_region_filters.py` 同源）是**两侧合计**：
既放行现役配置、又拦住故意损坏的样例。判负侧的断言是**两条**，不是一条：

1. **退出码 == 1**；
2. **输出里出现那个故意注入的定位标记**（如组名 / 键名）。

⚠️ 第 2 条不是多余：审计器**崩了**（emoji 触发 `UnicodeEncodeError`）同样以退出码 1 结束
—— 而判负样例期望的**恰恰也是 1**。两者的区别只能在**输出**里看。
所以判负样例必须「能点名到这一条」，才能与「崩在别处」分开。

#### 9.2 每个门禁的坏样例构造方法

统一前置（**在仓库外做**，避免污染工作副本）：

```bash
SB=/tmp/clash-gate-probe          # macOS/Linux；Windows 用 C:/Users/<你>/AppData/Local/Temp/...
mkdir -p "$SB/profiles" "$SB/override"
cp clash/profiles/*.yaml "$SB/profiles/"
cp clash/override/*.js   "$SB/override/"
python self-conf-skills/gates/clash/check_structure.py   "$SB"   # 期望 0
python self-conf-skills/gates/check_min_pair.py    "$SB"   # 期望 0
python self-conf-skills/gates/clash/check_script_sync.py "$SB"   # 期望 0
```

> ⚠️ **基线必须先绿**。基线红时注入坏样例，判负可能来自原有缺陷 ⇒ 判别力结论无效。

##### `check_structure.py` —— 8 个坏样例，一个判据一个

| # | 注入手法（在副本的 `profiles/lazy.yaml` 上改）| 期望报错（定位标记）|
|:-:|:---------------------------------------------|:-------------------|
| 1 | 某组的 `proxies` 里加一个不存在的名字 `Nope-Group` | `悬空引用: 组 Proxy -> Nope-Group` |
| 2 | 规则首行插 `RULE-SET,ghost-set,DIRECT` | `规则引用了未定义的规则集: ghost-set` |
| 3 | 规则首行插 `RULE-SET,cn,NoSuchGroup` | `规则指向了不存在的组: NoSuchGroup` |
| 4 | 把 `MATCH,Proxy` 改成 `MATCH,NoSuchGroup` | `MATCH 指向了不存在的组: NoSuchGroup` |
| 5 | 删掉 `nameserver-policy` 里所有 `rcode://success` 项 | `DNS 层广告拦截缺失：nameserver-policy 无 rcode://success` |
| 6 | 从 `fake-ip-filter` 里删掉所有 `rule-set:` 项 | `DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集` |
| 7 | 把 `rcode://success` 那几行**挪到** `private,cn` 之后 | `广告 policy 排在 cn 之后` |
| 8 | `ipv6: false` → `true`（顶层 / `dns.ipv6` 各试一次）| `顶层 ipv6 未显式关闭` / `dns.ipv6 未显式关闭` |

补充两条**边界**样例，用来证明判据没写反：

| # | 注入 | 期望 | 为什么值得测 |
|:-:|:-----|:-----|:-------------|
| 9 | 只给 `nameserver-policy` 加 `rcode://`，`fake-ip-filter` 里列**另一个**集 | `广告集两处不一致` | 证明判据 c 是「相等」不是「非空」 |
| 10 | 把 `ipv6` 键**整个删掉** | 仍判负 | 证明用的是 `is not False`（缺失 ≠ 通过）|

> ✅ 以上 1–10 已实测：现役配置基线 exit 0；逐个注入后**全部 exit 1**，
> 报错文本与表中定位标记一致；恢复后基线回到 0。

##### `check_min_pair.py`

| # | 注入 | 期望报错 |
|:-:|:-----|:---------|
| 11 | 在 `lazy.min.yaml` 的 `rules` 首行插一条 `DOMAIN-SUFFIX,example.com,DIRECT` | `rules 长度不同: 11 vs 12` + `rules[0] 值不同` |
| 12 | 只改 `lazy.min.yaml` 的 `dns.prefer-h3` → `true` | `.dns.prefer-h3 值不同: False vs True` |

> ✅ 已实测：注入 11 ⇒ exit 1 且输出含 `rules 长度不同: 11 vs 12`；注入 12 ⇒ exit 1 且含
> `.dns.prefer-h3 值不同`。恢复后 exit 0。
>
> 📌 12 值得单独做：它证明**只动一个 DNS 键也会被抓到** —— 这正是「DNS 段必须四份一致」
> 那条纪律能落地的原因。

##### `check_script_sync.py`

| # | 注入 | 期望 | 实际（⚠️ 见 §6.2）|
|:-:|:-----|:-----|:------------------|
| 13 | 从 `override/my_clash_lazy.js` 的规则数组里删掉一条 `RULE-SET,Jinx-CN,DIRECT` | exit 1 + 报出 rules 差异 | **exit 1，但输出是 `NameError` traceback**，无差异明细 |

> ✅ 已实测：基线 `my_clash.js` / `my_clash_lazy.js` 双双 `OK`（exit 0）；
> 删掉一条规则后 exit 1 —— **闸门会红，不会假绿**，但诊断信息缺失（§6.2）。

⚠️ 因此这道门的判别力是**"半条"**：能判负（1 对），给不出定位（2 不成立）。
**修好 `diff` 之后，第 2 条才成立。** 在那之前不要声称这道门"判别力完整"。

##### `build_rules.py --check`

| # | 注入 | 期望 |
|:-:|:-----|:-----|
| 14 | 往 `rules/AI.list` 末尾追加一行（任意域名）后跑 `--check` | `NG rules/AI_Domains.yaml 已过期（真源 AI.list 有更新）` + exit 1 |

> ✅ 已实测：追加一行后 `--check` 输出 `NG rules/AI_Domains.yaml 已过期（真源 AI.list 有更新）`、
> exit 1；恢复真源后 exit 0。
>
> ⚠️ **做这个实验前先备份真源**（`cp rules/AI.list $SB/AI.list.bak`），做完立刻还原，
> 并跑一次 `git diff rules/` 确认为空。**别让探针污染真源。**

##### `check_remote_urls.py`

| # | 注入 | 期望 |
|:-:|:-----|:-----|
| 15 | 把副本里某条 rule-provider URL 的后缀改成一个必死的名字（如 `mihomo-direct.yaml` → `mihomo-white-guard.yaml`，即当年真实死链）| 该 URL 标 `NG` + 末尾 `死链 N 个` + exit 1 |

⚠️ 这道门**需要联网**，且要跑完整个 URL 列表（数十个，每个最多 2×timeout）。
本地验证时用 `--timeout 8` 加速；CI 上用 `--timeout 20`。

##### `check_secrets.py` / `check_selfcontained.py`

坏样例**不要在副本里做**，直接看它们的判据：

| 脚本 | 最小判负样例 | 定位标记 |
|:-----|:-------------|:---------|
| `self-conf-skills/gates/clash/check_secrets.py` | 任意 `.yaml` 里写 `password: MyRealP@ssw0rd123`（非占位、含数字）| `非占位凭据:` |
| `self-conf-skills/gates/clash/check_secrets.py` | 任意文件里出现白名单外 IPv4，如 `10.0.0.1` | `非常见 IP: 10.0.0.1` |
| `check_selfcontained.py` | 任意**非注释行**出现 `https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/...` | `外部依赖 N 处` |

#### 9.3 判别力回归的现状（诚实口径）

| 门禁 | 判负样例已实测 | 有自动化回归 |
|:-----|:--------------|:------------|
| `check_structure.py` | ✅ 10 个，逐个 exit 1 + 定位标记 | ❌ 无（人工跑）|
| `check_min_pair.py` | ✅ 2 个 | ❌ 无 |
| `check_script_sync.py` | ⚠️ 1 个，能判负但无诊断（§6.2）| ❌ 无 |
| `build_rules.py --check` | ✅ 1 个 | ❌ 无 |
| `check_remote_urls.py` | ⚠️ 联网依赖，未逐个固定 | ❌ 无 |
| `check_region_filters.py`（跨内核）| ✅ | ✅ **有**（唯一定期跑判负 fixture 的闸门）|

> 📌 跨内核的 `check_region_filters.py` 是**唯一**把「判负 fixture」做进闸门的闸门，
> 且它对每个判负用例断言**退出码 + 输出标记**两条。mihomo 侧**还没有对应的自动化回归** ——
> 上表前五行的"已实测"是**本次文档编写时人工跑出来的**，不是常驻 CI 的保证。
>
> **已知缺口**：mihomo 侧门禁的判别力靠"人记得跑"，不是靠机器守住（见 §16.4）。
> 一旦出现「门禁逻辑改坏、判据不再判负、现役配置仍全绿」，本仓**没有闸门会发现**。

#### 10 · 已知豁免项（豁免 ≠ 通过）

本仓的 git 历史从整合完成起算，Release 亦从本仓发布。
因此对依赖这两者的判据做**显式豁免**（不是静默跳过）。

#### 10.1 V7「一天一版」

```python
_skip_v7 = {'SKIP_V7': '1'}
('min-pair 一致', [PY, 'self-conf-skills/gates/check_min_pair.py'], _skip_v7),
```

| 项 | 说明 |
|:---|:-----|
| 判据原意 | 归档里同一天不能出现多版（曾一天升 21 个版本）|
| 为什么豁免 | 判据依赖**完整 git 历史**（mtime / 提交日期分组）。复制文件时 mtime 丢失，历史归档全变成复制当天 ⇒ **分组不成立** |
| 实际输出 | `⚠️  V7 routing 一天一版   已跳过（SKIP_V7=1）：… ⇒ **未验证，不是通过**`（2026-10-08 起：显示 ⚠️，且**不计入 passed**，本道以 exit 3 结束） |

> 🔴 **豁免 ≠ 通过。** 输出里写的是「**未验证，不是通过**」，标记是 ⚠️ 而非 ✅（2026-10-08 修正：此前返回 True 会显示 ✅ 冒充通过）。
> 汇总表上它是 **⚠️ 标记**（2026-10-08 起：不再是 ✅），文字明确声明「未验证，不是通过」，
> 且**不计入 passed**、本道以 exit 3 结束。
> 引用这道门的结果时，必须连同这句声明一起引用。

⚠️ 配套处理：`cp -p` 保留 mtime（减缓 mtime 丢失），另加 `SKIP_V7` 开关应对
"本就不继承 git 历史"。CI 里仍 `fetch-depth: 0` 保留完整历史 —— 不是给 V7 用，
是给其它归档判据留底。

#### 10.2 releases 方案

```python
```

直接从 `build_gates` 里**注释掉**，不是跑完跳过。理由：
检查对象是「本仓自己的 Release 发布纪律」。✅ **已于 2026-10-08 启用**（首个 Release `v2026-10-08` 已发布），已进入闸门。

⚠️ 这道门在姊妹仓是有效判据（需 `GITHUB_TOKEN`，缺省回退 `gh auth token`；
都没读到、或 API 离线/限流/上游 5xx/非 JSON 时返回 **3**）。
✅ **已于 2026-10-08 启用**（首个 Release `v2026-10-08` 发布后）—— 现为「Release 断言」闸门，不再是豁免项。

#### 10.3 豁免的三条纪律

1. **豁免必须点名**，不冒充通过 —— 输出里要能读出「未验证」。
2. **豁免要写理由**，理由要能被证伪（"没有 Release"是可验证的事实，不是"太麻烦"）。
3. **豁免项要么进 `build_gates` 带 SKIP 标记、要么显式注释掉**。
   绝不允许"跑一遍然后无视结果" —— 那是静默假绿。

#### 12 · CI 怎么跑（`.github/workflows/ci.yml`）

```yaml
on:
  push:            branches: [main]
  pull_request:
  schedule:
    - cron: '17 3 * * 1'      # 每周一 03:17 UTC
  workflow_dispatch:
```

⭐ **定时任务是必须的，不是装饰。** 它抓的是「上游规则集悄悄改名 / 删档」这类
**本仓无从感知、本地永远绿**的变化 —— §7 那个 `white-guard → direct` 死链正是这一类。

#### Steps

| # | Step | 说明 |
|:-:|:-----|:-----|
| 1 | `actions/checkout@v4`（`fetch-depth: 0`）| 保留完整历史（V7 虽豁免仍保留）|
| 2 | `setup-python@v5` → 3.12 | |
| 3 | `setup-node@v4` → 20 | **mihomo 两道门要跑 JS** |
| 4 | Install deps：`pip install pyyaml` | 缺 PyYAML ⇒ 三道 clash 门直接 exit 2 |
| 5 | **Gates (Surge + Egern + mihomo)** | `python self-conf-skills/gates/verify_all.py` |
| 6 | **Encoding gate (cp936)** | 同上命令，但 `PYTHONIOENCODING: cp936` |
| 7 | **Remote ruleset reachability (mihomo)** | `check_remote_urls.py --timeout 20`，PR 时 `continue-on-error: true` |
| 8 | **Encrypted DNS endpoints reachability (Egern)** | `probe_dns_endpoints.py`；需联网，PR 时 `continue-on-error: true` |

#### 12.1 两处必须理解的设计

**① 编码门（ci.yml「Gates」之后那步，按本文件的「CI 怎么跑」8 行表为 Step 6、按 verify_all 脚注的 5 项清单为第 3 项）**

```
中文 Windows 下 print 非 GBK 字符会 UnicodeEncodeError 并以退出码 1 结束，
而 1 恰是判负码 ⇒ 崩溃会被读成「判负」，整轮看着对其实判据没跑。
```

以 `PYTHONIOENCODING=cp936` 在 Linux 上**等价复现** Windows(ACP=936) 的管道路径。
它与 `check_portability.py` 的 E4 **互补、不可互相替代**：

| | 覆盖 | 假阳性 |
|:--|:-----|:-------|
| 编码门（运行时）| 只覆盖 `build_gates` 跑到的脚本、且只覆盖**执行到的分支** | **零** |
| E4（静态）| 全覆盖（含 CI 不跑的审计脚本）| 有漏报也有假阳性 |

⚠️ 前提是 `run_one` 对 `PYTHONIOENCODING` 用 **`setdefault`**：

```python
env.setdefault('PYTHONIOENCODING', 'utf-8')
```

**不可写成硬赋值** `env['PYTHONIOENCODING'] = 'utf-8'` —— 那会把 CI 从父进程传下来的
`cp936` 抹成 `utf-8` ⇒ 编码门**永远绿（空操作）**。这是 2026-10-02 实测推翻过的错误写法。

**② Step 7 的 PR 宽容**

```yaml
continue-on-error: ${{ github.event_name == 'pull_request' }}
```

push 时严格，PR 时网络抖动不阻塞。⚠️ 这是**有意的非对称**：
死链要拦在 main 上，但不该因为 CDN 抽风挡住一次无关 PR。
**代价是 PR 上的死链可能绿灯合并** —— 靠 `schedule` 那个每周任务兜底。

#### 12.2 与本地的关系

> **与 CI 同源是铁律** —— 本地绿但 CI 红属于竞态 / 环境差，不允许有"第三套判据"。

**同源靠纪律，不靠门禁。**
`ci.yml` 的 Gates step 直接调 `verify_all.py`，而 `verify_all.py` 的 `build_gates()`
是清单的唯一真源 —— 不存在第二份手抄清单，因此不需要「对账门禁」去守两份一致。
（改革前确有 `check_gate_manifest.py` 做机器对账，那是为了守「ci.yml ↔ verify_all 双写」
这个自造的问题；双写消除后它一并删除。）

引用清单时用 `--index` 现抓：

```bash
python self-conf-skills/gates/verify_all.py --index
```

⚠️ **独立 step（不进 build_gates）**：`check_remote_urls.py`（慢、需联网）、
`probe_dns_endpoints.py`（需联网实测加密 DNS 端点，抖动会假红）。
两者都在 `ci.yml` 里各有独立 step，并在 PR 事件上 `continue-on-error`。


⚠️ 本地与 CI 对**退出码 3** 的口径**有意不同**：本地允许 SKIP（可能真离线 → exit 0 + ⚠️），
CI 侧 3 视为失败（CI 带 token，读不到远端即 CI 环境异常）。这是**严格化**，不是第三套判据。
CI 偶发 3（共享 runner IP 被限流）→ 重跑即可。

#### 14 · 全绿 ≠ 可用

同 Surge 侧 §9 —— 但 mihomo 侧**多两条必须实测的维度**：

| 维度 | 为什么脚本做不到 | 怎么做 |
|:-----|:-----------------|:-------|
| 冷启动有无明文 `:53` | 需要抓包 | 本地 DNS sink + mihomo 内核实测 |
| IPv6 是否真的不通 | 需要真实双栈环境 | 见 [`ops.md`](./ops.md) 的泄露定位章 |

> ⚠️ 核心立场：**审计通过 ≠ 配置可用。** 每修好一次判据，都要假设
> 「还存在审计器看不见的维度」。

#### 15 · FAQ

**Q：`self-conf-skills/gates/clash/check_secrets.py` 和 `self-conf-skills/gates/check_secrets.py` 该跑哪个？**

两个都跑 —— 进闸门的是**跨内核版**（`self-conf-skills/gates/check_secrets.py`，带禁串黑名单）。
mihomo 版（`self-conf-skills/gates/clash/check_secrets.py`）覆盖 `.js`、且跳过 `rules/` 的主机扫描
（那目录内容本身就是域名清单，扫了全是误报）。**两者判据不同，互不可替代，别合并。**

**Q：门禁报「缺文件」但我明明有。**

先看在哪个目录下跑的。`_default_root` 的判据是「**同时含 `profiles/` 与 `override/`**」，
顺序是 CWD → `CWD/clash` → `__file__` 逐级向上。在仓库根跑会命中 `<root>/clash`。
若在某处跑导致落到了 CWD 而 CWD 不是 clash 目录，就会报缺文件。显式传参最稳：
`python self-conf-skills/gates/clash/check_structure.py clash`。

**Q：`ipv6: false` 是默认值，为什么写了还要求写、不写还判负？**

两个原因：① `dns.ipv6` 不写就返回 AAAA，而真实 IPv6 未被 TUN 完整接管 ⇒ 绕过（见
`ops.md` §6）；② 与 Surge/Egern 的对齐面键**一律显式声明**，
让"对拍看文件即知"，不用查各内核默认值。判据用 `is not False` ⇒ **缺失也算不过**。

**Q：`.min.yaml` 怎么同步？能手工改吗？**

**mihomo 侧只能手工 —— 没有生成器**（`make_min.py` 的 `FAMILIES` 只含 surge / egern，
见 §5.1）。推荐做法是 `yaml.safe_load` + `yaml.safe_dump` 重出一份纯配置再比对，
**别逐行手改**（容易漏、也容易改错本体）。
`check_min_pair.py` 比的是 YAML 对象（注释不参与），所以只要配置本体一致就过。

**Q：为什么 Smart 组的差异不算漂移？**

模板能用 `filter` 在**运行时**按倍率分档，脚本在订阅加载时执行一次、看不到 provider 节点名
⇒ 脚本侧只能是单组 fallback。**这是内核机制决定的，不可能对齐**。故列为 `EXPECTED_DIFF`，
打印 `~ 已知差异 Smart: …` 提醒但不判负。别往这个白名单里加别的差异。

**Q：`check_script_sync.py` 报 `NameError: name 'diff' is not defined` 是什么意思？**

它**确实判负了**（脚本与静态不一致），但脚本里 `diff` 未定义也未导入 ⇒
在要打印差异明细时崩溃。见 §6.2。退出码仍是 1，所以 CI 会红。
**修法在脚本侧**（补 `diff`）；在那之前要人工 diff `rules` / `dns` 两段。

**Q：我把上游规则集 URL 改了，为什么 `check_script_sync.py` 立刻红了？**

它比对两侧 `rule-providers` 的 **URL 集合**。只改静态 profile 或只改脚本都会判负 ——
**两边一起改**。

**Q：V7 / releases 显示 ✅ 或 ⚠️，是真的过了吗？**

**不是，是豁免。** 输出文字写的是「已跳过（SKIP_V7=1）…⇒ 未验证，不是通过」。
汇总表上的 ✅ 只是"这道门没红"。引用时必须连同这句声明一起引用 ——
**豁免 ≠ 通过。**

**Q：CI 绿了但本地红，或者反过来？**

先看是不是退出码 2（环境）—— 最常见是 CI 缺 `pyyaml`（Step 4 装了，但改 workflow 时别删）
或本地缺 node（`check_script_sync` / `check_remote_urls` 需要）。
其次看 3：本地允许 SKIP，CI 侧 3 视为失败（CI 带 token）。**这是有意的严格化。**

#### 16 · 维护者须知

#### 16.1 改 mihomo 配置的最小闭环

```bash
vim clash/profiles/routing.yaml
python self-conf-skills/run/clash/build_rules.py            # 若动了 rules/*.list

python -c "import yaml;c=yaml.safe_load(open('clash/profiles/routing.yaml',encoding='utf-8'));yaml.safe_dump(c,open('clash/profiles/routing.min.yaml','w',encoding='utf-8'),allow_unicode=True,sort_keys=False)"

python self-conf-skills/gates/clash/check_structure.py
python self-conf-skills/gates/check_min_pair.py
python self-conf-skills/gates/clash/check_script_sync.py
python self-conf-skills/run/clash/build_rules.py --check

python self-conf-skills/gates/verify_all.py

python self-conf-skills/gates/clash/check_remote_urls.py
```

#### 16.2 改动前必须知道的四条

1. **四份 profile 都要改。** `lazy` / `routing` × `.yaml` / `.min.yaml`。
   只改完整版 ⇒ `check_min_pair.py` 立刻判负。
2. **脚本与静态是同一套配置的两个形态。** 改 `override/*.js` 必须同步改 `profiles/*.yaml`
   （反之亦然）—— `check_script_sync.py` 逐位比对 `rules`、比对 `rule-providers` URL 集合。
3. **不手工编辑 `rules/*.yaml`。** 那是生成物，改真源 `.list` 后重跑 `build_rules.py`。
4. **不提交真实地址 / 凭据 / token。** `check_secrets.py` 两份都会拦。

#### 16.3 改判据时要做的事

1. **先注入坏样例，确认它会红**（§9.2）。判据改完之后再注入一次，确认它**还**会红。
2. **确认基线仍绿** —— 否则判负可能来自原有缺陷。
3. **探针做在仓库外**（`/tmp` 或 `%TEMP%` 下的副本 + 显式传 ROOT 参数），
   做完还原并 `git status` 确认没多出改动。
4. **动 `rules/*.list` 做实验前先备份真源**，做完立刻还原并 `git diff rules/` 确认为空。
5. **改 `build_gates` 就要改 `ci.yml`**（同源铁律）。引用清单用 `--index` 现抓，别手抄。

#### 16.4 已知缺口（接手时先看这里）

**只列仍然存在的** —— 修好就删行，不保留历史（那会让读者以为坑还在）。
历史在 git。

| # | 缺口 | 触发修补的条件 |
|:-:|:-----|:---------------|
| 1 | mihomo 侧**其余**门禁没有常驻的判负 fixture 回归（判别力靠人记得跑）| 出现「判据改坏、不再判负、现役仍全绿」时。注：地区组那块已有 fixture（闸门「地区组判别力·mihomo」）|
| 2 | **clash 侧没有 `.min` 生成器**（`make_min.py` 只有 surge / egern 两族）⇒ `.min.yaml` 靠手工同步 + 对拍兜底 | 出现第一次「手工同步漏改、对拍才发现」时；修法是给 `make_min.py` 加一族 clash |
| 3 | `_default_root()` 在 clash 侧有 **6 份拷贝**（`check_structure` / `check_min_pair` / `check_script_sync` / `check_remote_urls` / `check_header_numbers` / `audit_ruleset_content`）| 六份逻辑出现分歧时。未定义名扫描能抓住「拷贝时漏了名字」，抓不住「逻辑各自漂移」 |
| 4 | **「一天一版」无机器判据** —— 改革删掉归档后，V7 一并删除。现在它靠 §6.1 的纪律，**没有闸门守** | 出现真的「同一天升了两个号」且造成困扰时 |

#### 16.5 退出码速查

| 码 | 含义 | 见到怎么办 |
|:--:|:-----|:-----------|
| 0 | 判据全过 | — |
| 1 | 有判负 | 读输出修配置 |
| 2 | 前置环境不达标 | **先修环境，别读判据**（最常见：缺 PyYAML / 缺 node / 目录不对）|
| 3 | SKIP（未验证）| 不计失败，但**输出必须写「未验证」**，不得当成绿 |

---

## Surge · 公开仓交付（surge 侧）

> **何时读**：要更新模板、了解仓库结构或门面纪律时。

#### 1 · 交付物清单

```
self-conf/
├── README.md                    # 门面（人类看的唯一文档）：订阅地址 / 组表 / 隐私对照 / AI 指路
├── LICENSE                      # MIT
├── .gitattributes · .gitignore
├── icons/                       # 图标 PNG + icons.json / icons-full.json —— 两内核共用
├── self-conf-skills/                       # ★ AI 驱动的唯一知识库与工具集（无人类文档）
│   ├── AGENTS.md                 # 单一入口：底线与纪律 → §0 判内核 → 分支 A(Surge) / 分支 B(Egern)
│   ├── reference/               # 8 篇：profiles/*.md · dns · rulesets · pitfalls · ops · gates ·
│   │                            #   no-resolve-pairing · dns-basics · ops · troubleshoot-faq
│   ├── reference/profiles/ # 单侧主题：profile-anatomy（逐键权威）· hardening-template · pitfalls ·
│   │                            #   leak-localization · checker · ruleset-weight · public-repo（本文）
│   ├── scripts/{surge,egern}/   # 审计脚本（Surge 5+1 共享模块 / Egern 10+1 共享模块）
│   └── tests/                   # check_secrets · check_portability · check_min_pair · check_links · make_min
└── surge/                       ── Surge 全部产品物 ──
    ├── profiles/                # 顶层固定名四件 = 2 种分工 × 2 种形态（订阅地址永久不变）
    │   ├── lazy.conf            # 懒人版（带注释）—— 改这份
    │   ├── lazy.min.conf        # 懒人版（纯配置）—— 导入用
    │   ├── routing.conf         # 分流版（带注释）—— 改这份
    │   ├── routing.min.conf     # 分流版（纯配置）—— 导入用
    └── apple_system.list        # （在 egern/ 侧）本仓自托管的 Apple 系统域名规则集
```


#### 1.1 各层的职责边界

| 层 | 装在什么 | **不装什么** |
|:---|:---------|:-------------|
| `README.md` | 能用起来所需的一切（产品结论） | 原理推导、逐行理由 |
| `AGENTS.md` | AI 的工作手册：底线、归档动线、审计清单、验收判据 | 逐键细节（下沉 reference） |
| `self-conf-skills/references/` | 机制推导、逐键语义、实测读数、已知取舍、FAQ、事故复盘 | 面向使用者的说明 |

⚠️ **不要把工作过程倒进产品文档。** 内部重构、仓库运维、行尾规范化 —— 使用者无感，
不进 README。改动历史看 git log（备份 tag：`pre-cleanup-20260927`）。

#### 2 · README 门面纪律

README 是**产品介绍**：读者要知道「这东西是什么、怎么用」。已定下的规矩：

- 🚫 **只讲产品，不讲改动过程。**「为什么这样归类」「原写 X 属误标」这类话不进 README。
  实测反例（2026-09-22）：在组表下补一段 📌 解释「为什么这样归类」，用户一句打回 ——
  「readme 是产品介绍，不是自说自话的地方」。
- 🚫 **门面只写「得到什么」—— 标题里不出现「原理」二字。**
  功能清单写两列：「防的是什么 · 得到什么」。内核实现键（`fake-ip` / `dns-hijack`…）不进首页。
- 🚫 **首页不列规则集。**「`OpenAI.list` → `ChatGPT`」对读者没有意义；
  「AI 应用走 `AI` 组，面板上可改道」才有意义。规则集清单在 `reference/rulesets.md`。
- 🚫 **三端（Surge / Egern / Clash）各写各的，不许互抄 DNS 防泄露的表述** ——
  机制不同，照抄等于把不存在的机制写进别人的仓。
- 📐 **清单类内容用列表不用表格**（GitHub 表格宽度不可控）；emoji 只放条目最前面，句中零个。
  ⚠️ **例外**：二维对应关系可用表格（首页「内核 × 产品线」的下载地址即此例，2026-10-01 改版）——
  但**长 URL 不进单元格**：单元格只放短文本链接、完整 URL 走链接目标。放裸 URL 会把表格撑宽、
  窄屏横向滚动，正是本条要避的情况。
- 📐 **相对链接必须能解析**；改标题后必须重算锚点并同步所有引用处
  （中文/emoji 标题的 GitHub 锚点规则见 git 历史里的 `self-conf-skills/references/gates.md` §2.3）。

**自查**：README 里出现「为什么…」「不算」「误标」「判据」「原写」，八成是改动记录漏出来了。

#### 3 · 文件组织

#### 3.1 分工关系，不是版本关系

本仓库有**两份配置**：`lazy.conf`（懒人版）与 `routing.conf`（分流版）。
这是分工关系（基础款 / 进阶款），不是版本关系。选一份用，不要叠加。
想让你手头那份更轻，就在**它上面直接删**，不另开第三份。

#### 3.2 两种形态

`.conf`（带注释，给人读）+ `.min.conf`（纯配置，导入用）。
**内容必须一致，只差注释** —— 由 `check_min_pair.py` 对拍兜底。
⚠️ `.min.conf` 里**必须保留 `# audit-waive:` 行** —— 那是有语义的注释。
`make_min.py` 按锚点把这类注释继承过去，`--apply` 写盘；不要手工同步 `.min`。

#### 3.3 想加第三份配置的 6 条清单

**先问：这是新分工，还是老配置的另一种写法？** 后者不推荐（那是版本分叉）。
确认是新分工后，必须同时满足：

1. **DNS 段与 `lazy.conf` 逐字节一致**（跨配置断言 ②-c；若确实必须不同，要说明理由并改测试）
2. 规则顺序符合铁律：白名单 → 黑名单 → 常规分流
3. `FINAL` 之前有域名体量足够的国内直连规则集
4. 所有 IP 类规则带 `no-resolve`
5. 节点全部占位化（`203.0.113.x` + `REPLACE_WITH_*`），订阅 token 用 `REPLACE_WITH_YOUR_TOKEN`
6. 若有豁免，`# audit-waive:` 写在文件里

**能过测试的才叫一份新配置，否则只是一个改坏了的副本。**

#### 4 · 脱敏规则（公开模板的底线）

| 字段 | 占位形式 |
|:-----|:---------|
| 节点 IP | RFC 5737 文档段：`192.0.2.0/24` / `198.51.100.0/24` / `203.0.113.0/24` |
| 中转域名 | `cdn-relay.example.com`（RFC 2606 保留域） |
| 密码 / 用户名 | `REPLACE_WITH_YOUR_PASSWORD` / `REPLACE_WITH_USERNAME` |
| SNI | `REPLACE_WITH_YOUR_SNI` 或与 server 相同 |
| 订阅 URL（含 token） | `REPLACE_WITH_YOUR_TOKEN` |

#### 4.1 push 前必跑

```bash
python self-conf-skills/gates/check_secrets.py        # 占位符纪律（全仓 .conf + .yaml）
```

它会拦住：非文档段 IPv4（真实节点 IP）、非 `REPLACE_WITH_*` 的凭据、
不在允许清单的节点主机名、若干禁止出现的敏感子串（**注释里也不许出现**）。

#### 4.2 全仓扫描（补一道）

`check_secrets.py` 只认 `.conf` / `.yaml` —— markdown 与 Python 需另扫：

```bash
grep -rn -iE '<你的私有域名|你的密码片段|你的用户名>' . \
  --exclude-dir=.git --exclude-dir=icons
```

> ⚠️ 不要用 `grep -rn 'github'` 这类宽泛关键词 —— 规则集 URL 全含
> `githubusercontent`，几百条假阳性会淹没真命中。

#### 5 · 验证

CI（根 `.github/workflows/ci.yml`）在 push / PR 自动跑：占位符扫描 → 可移植性 → `.min` 对拍 →
链接锚点 → 两侧 DNS 审计 → `.min` 漂移检查。本地同组命令见 [`AGENTS.md`](../../AGENTS.md) §3 动线第 ⑤ 步。

#### 5.1 改 markdown 版式前：先问 GitHub 本人

README（及任何 GitHub 渲染的 markdown）的**最终长相由 GitHub 的渲染管线决定，不由本地预览决定**：
本地预览有完整 CSS 自由，GitHub 却会**剥掉 `style` 属性**、丢弃废弃属性 —— 两者"能做/不能做"的
边界不同，凭本地预览判断版式，会把真机上办不到的效果当成可行（2026-10-01 实测踩过）。

推送前用 GitHub 自己的渲染接口拿真机答案：

```bash
MSYS_NO_PATHCONV=1 gh api --method POST /markdown \
  -f mode=gfm \
  -f context=RiverFlowsInUUU/self-conf \
  -f text='| | <div align="center">Surge</div> | <div align="center">Egern</div> |
|:--|:------|:------|'
```

输出即 **GitHub 渲染后的 HTML**，一眼看出某写法保不保留。实证：

- `<th align="left"><div align="center" dir="auto">Surge</div></th>` ⇒ `div` 与 `align` **被保留**
  （对比 `style` 会被剥）；同表体仍是 `<td align="left">` ⇒ 「只居中表头、不动表体」可行。
- ⚠️ Git Bash 下漏了 `MSYS_NO_PATHCONV=1`，`/markdown` 会被当文件路径改写、报 `invalid API endpoint`。

> ⚠️ 表头居中只能给单元格包 `<div align="center">`；**不能**改用列对齐 `:--:` —— 它按列生效，
> 会把表体的长句一并居中（取向见 §2「清单类内容用列表不用表格」）。

#### 6 · 这个仓库最容易被改坏的地方

按风险排序：

| # | 位置 | 改坏的症状 | 守它的东西 |
|:-:|:-----|:-----------|:-----------|
| 1 | `[Proxy]` 段的节点（填成真实值） | 隐私泄露 | `check_secrets.py` |
| 2 | `[Rule]` 的顺序（`direct.txt` 挪到 REJECT 前） | 广告拦截失效 | 人工核对 + `check_surge_dns.py` 第 9 项 |
| 3 | IP 类规则的 `no-resolve`（删掉） | DNS 泄露 | `check_surge_dns.py` 第 12 项 |
| 4 | 只改 `.conf` 或只改 `.min.conf` | 两份行为不一致 | `check_min_pair.py` |
| 5 | `pre-matching` 的策略（改成策略组） | **Surge 拒绝加载** | `check_10` |
| 6 | `underlying-proxy` 指向的名字 | **Surge 拒绝加载** | `check_7` |
| 7 | `# audit-waive:` 行（删掉） | 从 2 waived 变 2 high | 无（靠"知道它是有语义的"） |

> ⚠️ 第 4 条的覆盖是部分的：`check_min_pair.py` 对拍整份去注释正文，
> `.min.conf` 里其余部分（规则、组、节点）改歪了不会被拦住。
> 第 7 条完全没有自动化覆盖。这两条是**已知的测试盲区**，靠纪律补：改配置时两份一起改。

---

## Egern · 公开仓交付（egern 侧）

> 本文是 [`AGENTS.md`](../../AGENTS.md) 的引用文件。 **何时读**：要更新模板 / 了解公开仓库结构时。

---

自用配置已脱敏发布为公开模板 + 本 skill：

**https://github.com/RiverFlowsInUUU/self-conf**（Egern 分支在 `egern/`，与 Surge / mihomo 同仓）

```
README.md                                   # 门面（人类看的唯一文档）：订阅地址 + 分组表 + 隐私对照 + AI 指路
LICENSE · .gitattributes · .gitignore
icons/                                      # 图标 PNG + icons.json / icons-full.json —— 两内核共用
rules/                                      # 本仓自托管的规则集（当前 1 份：Egern 用的 apple_system.list）
self-conf-skills/                                      # ★ AI 驱动的唯一知识库与工具集
  AGENTS.md                                  # 单一入口：底线与纪律 → §0 判内核 → 分支 A/B
  reference/                                # 8 篇：profiles/{surge,egern,clash}.md · dns.md · rulesets.md
                                            #        pitfalls.md · ops.md · gates.md
  scripts/<kern>/ · tests/                  # 审计脚本 + 门禁（唯一入口 tests/verify_all.py）
egern/profiles/lazy.yaml / lazy.min.yaml    # 懒人版 · 可选（4 组 / 10 条规则；隐藏订阅槽位 Airport）
egern/profiles/routing.yaml / .min.yaml     # 分流版 · 推荐（脱敏模板：2 条占位节点 + 1 个机场槽位，凭据与订阅均为占位符）
.github/workflows/ci.yml                    # CI：六步检查（push / PR 自动）
```


> **可选版本只有两个** —— `routing`（分流版 · 推荐）与 `lazy`（懒人版），文件名不带版本号；
> 当前是第哪一版写在头注 `#! version=` 里，三内核同号。**仓内不保留历史版本**（历史在 git 与 Releases）。

**要更新模板时**：**直接在仓库里改 `profiles/*.yaml` 即可。** 这份模板早已完成脱敏
（2 条占位节点 + 1 个占位订阅，全都连不出去，无真实证书），改它不需要"从自用配置重新生成"。
改完按 [`AGENTS.md`](../../AGENTS.md) 的标准动线走（改完整版 → `make_min.py` → 闸门 → 推送）。

> 📦 **历史做法（已不再使用）**：早期由维护者本地的 `outputs/` 脚本链生成 ——
> `_build_public_template.py`（带断言的行级替换 + 38 个敏感串零残留自检）、
> `_transform_template.py`、`_make_min.py`、`_fetch_icons.py`、
> `_publish_to_github.py`（Git Data API 单次提交；空仓库需先落初始化提交，
> 否则 `POST /git/blobs` 报 `409 Git Repository is empty`）。
> ⚠️ 这些脚本**不在本仓库**（避免暴露构建侧私人路径）。"不要手改仓库里的 yaml"这条老规矩**已作废**：
> 现在的版本就是在仓库里直接改出来的。若将来要恢复"从自用配置生成"的流程，方法论见 skill
> `github-publish-sanitized-repo`，需按它重建脚本。

📌 **验证 = CI（`.github/workflows/ci.yml`，push / PR 自动）+ 本地同组命令复现**
（命令清单见 [`AGENTS.md`](../../AGENTS.md) §3）；探针 / 量测类脚本（`probe_*` / `weigh_*` / `profile_ruleset`）不在验证链上，是手工工具。

**脱敏清单（这五类必须洗）**：节点 server/凭据/sni/reality 公钥 → 占位；
机场订阅 URL（含 token）→ 占位；`mitm.ca_p12` + `ca_passphrase`（个人 CA 私钥）→ **注释掉**；
机场组名/节点名 → `Airport-A` / `Node-1`；`dns.forward` 里的**节点域名** → `example-node.com`。

#### README 的边界：只讲产品，不讲改动过程

README 是**产品介绍** —— 读者要知道「这东西是什么、怎么用」。以下三类**不属于**它：

- 🚫 **归类 / 设计自述** —— 「某组为什么不算开关」「**上面是分类顺序**」这类解释我们怎么想的话。
- 🚫 **与评审 / 工单的对话** —— 「原写 X 属误标，已按功能拆开」。
- 🚫 **内部判据与断言名** —— 「由某脚本某断言守着」。

判据与原理 → `self-conf-skills/references/`（对应主题文件）。改动历史看 git log。

> 改 README 的 **markdown 版式**前先问 GitHub 本人（`POST /markdown` 接口，推送前就能看出某写法
> 会不会被 sanitizer 剥掉）：见 [`gates.md`](./gates.md) §5.1。

**自查**：README 里出现「为什么…」「不算」「误标」「判据」「原写」「上面是…顺序」，
八成就是改动记录漏出来了。

同一事实要用**使用者视角的性质**表述：`不被规则引用`（内部判据）→ `独立于规则链路`（读者能懂）。

实测反例（2026-09-22）：在 README 里补「我们为什么这样归类 / 上面是分类顺序」这类说明，
用户一句打回 —— 「readme 是产品介绍，不是自说自话的地方」。

#### 首页不列规则集

规则集属**实现侧**：用了哪些 `.list`、从哪个仓库拉、顺序怎么排。使用者关心的是**分流结果**。

| | 首页（`README.md`） | `reference/rulesets.md` |
|:--|:--|:--|
| 顺序表 | 「匹配什么 → 去向」（白名单 / 广告 / 按应用 / 国内…） | 逐条列出规则集名与参数 |
| 规则集清单 | ❌ 一个都不出现 | ✅ 文件名 · 去向 · 来源 URL |
| 来源仓库 | ❌ | ✅ 含图标、数据库、许可 |

**判据**：首页上这句话，对读者**用**这份配置有没有帮助？
「`OpenAI.list` → `ChatGPT`」没有意义 —— 使用者不能按规则集文件名分流；
「ChatGPT 走 `ChatGPT` 组，面板上可改道」才有意义。

实测（2026-09-22）：首页原挂着「📚 规则来源」段 + 「分流版的应用规则」表 + 「排序约束」，
用户连判两次 —— 先要求来源段下沉，随即补充：「不仅是规则集的来源，而且是有哪些规则集……
我认为都没必要放在首页的 README 里面。」

闸门：`verify_readme_tone.py`（维护者本地的装配闸门，不进公开仓）的「首页无规则集文件与来源仓库」一项。
⚠️ 只对**配置模板仓**生效 —— `jinx` 本身是规则集仓，README 讲规则集是它的产品，不适用这条。

---

## mihomo · 公开仓交付（clash 侧）

> **何时读**：准备把配置、日志、规则集或截图提交到公开仓；新增第三方上游；
> 修改 secrets / 自洽性门禁；或处理疑似泄露事件时。
>
> 本仓交付的是**公开模板**，不是维护者的自用配置备份。公开仓最严重的失败不是 YAML
> 解析报错，而是两类“看起来还能用”的静默事故：**真实秘密进入历史**，以及**本仓仍依赖外部仓库**。
> 前者伤害隐私，后者让本仓在被依赖的外部仓库删除、改名或限流后失效。
>
> 安全事件的正式报告通道以 [`SECURITY.md`](../../SECURITY.md) 为准；
> 自动化命令与退出码见 [`gates.md`](./gates.md)。

#### 1 · 公开模板的威胁模型

本仓没有运行中的服务，也没有传统意义上的服务端依赖；主要风险集中在三类数据与一类供应链：

| 风险面 | 典型载体 | 后果 | 首要防线 |
|:-------|:---------|:-----|:---------|
| **节点与凭据泄露** | profile、覆写脚本、注释、fixture、生成物 | 节点被盗用、账号关联、订阅被接管 | 占位符 + secrets 扫描 |
| **诊断信息泄露** | issue、PR、Actions 日志、截图 | token、内网拓扑、用户名或私有域名公开 | 提交前打码 + 私密安全通告 |
| **依赖外部仓库** | 图标 URL、规则集 URL、脚本常量 | 外部仓库一失效，本仓静默缺图标或空规则集 | `check_selfcontained.py` |
| **第三方上游漂移** | 移动分支、raw URL、`.mrs`、数据库 | 误分流、误拦截、死链、规则集变空 | 来源评估 + 缓存 + 可达性与内容审计 |

必须把两个“外部依赖”概念分开：

- **不允许的依赖**：本仓自己的图标、规则和脚本仍指向外部仓库，导致本仓不能独立存在；
- **允许但要登记的依赖**：MetaCubeX、blackmatrix7 等第三方规则源。它们是产品设计的一部分，
  不能被伪装成本仓资产，也不能因为“允许”就跳过供应链评估。

#### 2 · 占位符纪律

#### 2.1 一条总规则

> **所有节点地址、认证材料、订阅 token 必须是假值。公开仓内不存在“临时放一下真实值”。**

建议形式：

| 数据类型 | 公开模板中的写法 | 禁止做法 |
|:---------|:-----------------|:---------|
| 节点 IPv4 | RFC 5737 文档地址段 | 家庭、VPS、机场或公司出口的真实地址 |
| 节点域名 | `example.com` / `sub.example.com` 下的示例名 | 自有域名、机场域名、内网 DNS 名 |
| 密码 | `REPLACE_WITH_YOUR_PASSWORD` | “弱密码也是假值”的自创字符串 |
| 用户名 | `REPLACE_WITH_YOUR_USERNAME` | 真实账号、邮箱、本机用户名 |
| UUID / secret / auth | `REPLACE_WITH_YOUR_UUID` 等同前缀形式 | 任意看似随机、可能可用的长串 |
| SNI / servername | `REPLACE_WITH_YOUR_SNI` 或示例域 | 真实中转 SNI、私有证书域名 |
| 订阅参数 | `token=REPLACE_WITH_YOUR_TOKEN` | 完整订阅链接、短期 token、已失效 token |
| 私钥 / 证书 | 不提交；模板只说明由用户本地提供 | PEM 私钥、个人 CA 容器、解密口令 |

占位符统一使用 `REPLACE_WITH_YOUR_*`，不是为了美观，而是让机器能做白名单判断。
`changeme123`、随机 UUID、打乱一位的真实密码都不合格：审计器无法证明它们不可用，
后来者也无法区分“示例”与“泄露”。

#### 2.2 节点地址的合法假值

- IPv4 使用 RFC 5737 文档段；
- 域名使用 RFC 2606 示例域；
- mihomo 的 fake-ip 保留段是运行机制，不是节点地址。它曾被跨内核扫描器误判，
  现以窄范围白名单放行；
- 公共 DNS 地址可以进入允许清单，但“是公共 IP”不代表“任意 IP 都可提交”。

新增一个合法保留段时，PR 必须写明 RFC / 内核用途和最小范围。不能因为一次误报就把整个私网、
整个云厂商网段或“所有 IP”加入白名单。

#### 2.3 注释、文档与 fixture 也不是保险箱

真实秘密不能以任何形式留在：

- 注释掉的节点；
- 测试坏样例与 fixture；
- Markdown 命令示例；
- 生成器常量或本地路径；
- CI 输出、截图和录屏。

跨内核 `self-conf-skills/gates/check_secrets.py` 对普通注释行会减少结构性误报，但订阅参数和已知禁串仍按原文检查；
`self-conf-skills/gates/clash/check_secrets.py` 的扫描面更广，包含 Markdown、JavaScript 与文本。
**“当前脚本没扫到”从来不是允许提交的理由。**

#### 2.4 建议的本地工作方式

1. 仓内只保留模板假值；
2. 自用值通过客户端本地编辑、未跟踪文件或仓外私有存储注入；
3. 生成公开文件时从假值模板出发，不从自用配置“删秘密”；
4. 提交前先看 `git diff --cached`，再跑 secrets 扫描；
5. 不用全局 ignore 规则掩盖一个本应被审计的配置目录。

从假模板填入真实值，失败通常是“漏填，连接不上”；从真实配置反向脱敏，失败则是“漏删一个，永久公开”。
公开仓应选择前者。

#### 3 · 为什么真实值推上来不可回收

#### 3.1 删除文件不等于删除秘密

秘密进入公开 commit 后，至少可能存在于：

- 当前分支与旧 commit 对象；
- tag、PR merge commit、Actions artifact 或日志；
- fork、镜像、搜索索引和 CDN 缓存；
- 已经执行过 `git fetch` 的第三方 clone；
- 用户下载到本地的 profile 与客户端缓存。

后续 commit 删除该行，只能让**最新树**看不见，不能证明任何副本已消失。即使改写 Git 历史并强推，
也只能处理自己可控的引用；外部 clone 与缓存无法被强制回收。

#### 3.2 正确的事故顺序

发现真实 token、凭据或节点地址后：

1. **先撤销 / 轮换秘密**，不要先花时间美化 commit；
2. 暂停相关订阅、节点或账户，检查异常使用；
3. 通过私密安全通告通知维护者，避免在公开 issue 再复制一次；
4. 清理工作树、当前分支、tag、PR 与 CI 日志中的副本；
5. 评估是否需要历史改写，并通知协作者重新 clone / rebase；
6. 向托管平台申请清理可清理的缓存或 artifact；
7. 给门禁补一个**脱敏坏样例**，证明同类秘密以后会判负；
8. 在不复述秘密原文的前提下记录事件范围与处置状态。

**历史改写是清理动作，不是恢复秘密性的证明。** 一旦公开，应按“已泄露”处理并轮换。

#### 4 · 自洽性纪律与 2511 处事故

#### 4.1 自洽的定义

整合仓的第一方资源必须形成闭环：

- 配置里的图标 URL 指向本仓 `icons/`；
- 自托管规则 URL 指向本仓 `rules/`；
- 生成脚本、覆写脚本和静态 profile 不再读取外部仓库；
- 删除或冻结被依赖的外部仓库后，本仓仍能加载自身的第一方资源。

这不等于禁止所有第三方 URL。第三方规则集仍可在线引用，但必须在文档中登记来源、用途、
刷新周期和失效策略。

#### 4.2 2511 处不是“批量替换小问题”

本仓曾有 **2511 处 URL 仍指向外部仓库**：

| 类型 | 数量 | 表面症状 | 实际后果 |
|:-----|-----:|:---------|:---------|
| 图标引用 | 2311 | 外部仓库仍在线时一切正常 | 外部仓库改名 / 删除后，大量面板图标同时失效 |
| 规则集引用 | 200 | profile 仍能加载 | 远程集拉取失败后可能静默变空，分流与广告拦截退化 |

这类缺陷危险在于：语法检查、客户端导入和本地缓存都可能继续成功。只有把外部仓库看作“随时会消失”，
才能验证整合是否真的完成。

#### 4.3 `check_selfcontained.py` 的判据

`self-conf-skills/gates/check_selfcontained.py`：

- 扫描 `.yaml` / `.yml` / `.conf` / `.js` / `.list` / `.txt` / `.json` 中的 HTTP(S) URL；
- 跳过纯注释行，避免把“来源说明”误当运行时依赖；
- 跳过 `.git`、`__pycache__`、`icons`；
- 非注释 URL 一旦出现 `Self-Configuration` 或 `RiverFlowsInUUU/Clash` 即判负；
- MetaCubeX、blackmatrix7、Jinx、TG-Twilight 等登记过的第三方来源允许存在。

运行：

```bash
python self-conf-skills/gates/check_selfcontained.py .
```

边界也要写清：它按仓库名识别已知的外部仓库，不是通用的“零外链证明器”；纯注释、Markdown 与跳过目录
不在当前扫描面。新增外部仓库、镜像域名或新文件后缀时，必须同步扩判据。

#### 5 · 自动化守门各自负责什么

#### 5.1 两道 secrets 扫描不要混为一个

| 脚本 | 主要扫描面 | 守什么 | 主要盲区 |
|:-----|:-----------|:-------|:---------|
| `self-conf-skills/gates/check_secrets.py` | 全仓 `.conf` / `.yaml` / `.yml`，包含未提交工作副本 | 文档段 IP、YAML / Surge 凭据、SNI、订阅参数、已知禁串；同时要求能找到现役 profile | 不读 Markdown / JavaScript；普通注释多数被剥离 |
| `self-conf-skills/gates/clash/check_secrets.py` | `.js` / `.yaml` / `.yml` / `.md` / `.conf` / `.list` / `.txt` / `.json` | 凭据字段、token、主机白名单、IPv4 白名单、PEM 私钥头 | 白名单需要维护；规则集目录跳过主机扫描；启发式仍可能误报 / 漏报 |

建议从仓库根显式执行：

```bash
python self-conf-skills/gates/check_secrets.py
python self-conf-skills/gates/clash/check_secrets.py clash
```

第二条显式传 `clash`，限定在 mihomo 交付目录并让审计范围一眼可见。两道有重叠是故意的：跨内核脚本更懂现役 profile 结构，
mihomo 脚本覆盖更多扩展名与 URL 主机。

#### 5.2 `check_selfcontained.py`

它不判断凭据是否真实，只判断**运行时第一方 URL 是否还回指外部仓库**。一个文件可以同时满足：

- secrets 扫描全绿，但图标仍来自外部仓库；
- 自洽检查全绿，但订阅 token 是真实值。

所以两道必须都跑，任何一个都不能替代另一个。

#### 5.3 其他相关门禁

| 门禁 | 与公开仓纪律的关系 |
|:-----|:-------------------|
| `check_min_pair.py` | 防止完整版已经脱敏而 `.min` 仍残留旧值，或两者行为漂移 |
| `check_script_sync.py` | 防止静态 profile 已修、覆写脚本仍带旧 URL / 旧规则 |
| `build_rules.py --check` | 防止 `.list` 真源与 mihomo `.yaml` 生成物漂移 |
| `build_profiles.py --check` | 防止脚本与静态产物漂移、重复顶层键和追加写事故 |
| `check_remote_urls.py` | 发现 404 / 改名 / 删除；不能证明内容可信 |
| `check_links.py` | 守 Markdown 相对链接与锚点；不验证规则内容 |

#### 5.4 白名单是代码，不是垃圾桶

secrets 扫描发现新的主机或 IP 时，只有两种正确处理：

1. 它是秘密或不必要依赖：删掉 / 占位化；
2. 它是有规范依据的公共资源：以最窄范围加入允许清单，并在 PR 说明用途。

禁止把整段地址、任意域名后缀或“所有 GitHub raw”当作绕过手段。白名单越宽，未来真实泄露越容易假绿。

#### 6 · CI 能证明什么、不能证明什么

#### 6.1 当前流水线

根 `.github/workflows/ci.yml` 在 main push、PR、每周定时与手工触发时执行：

1. `python self-conf-skills/gates/verify_all.py`：三内核的 secrets、可移植性、min 对拍、链接、DNS、结构、
   地区组、文档同步、mihomo 脚本 / 静态对拍与生成物新鲜度；
2. 以 `PYTHONIOENCODING=cp936` 再跑总入口：防止 Windows 中文环境输出崩溃被误读为普通判负；
3. `check_remote_urls.py` 联网探测 mihomo 远程规则集：push / 定时严格，PR 因网络抖动允许不阻塞。

#### 6.2 必须诚实写出的缺口

- ~~`check_selfcontained.py` 当前是手动门禁，没有列入 verify_all / CI~~ ⇒ **已接入**：现为闸门 **#42「自洽性」**，在 `verify_all.py` 与 CI 里都跑
- mihomo 专用 `self-conf-skills/gates/clash/check_secrets.py` 也不是总入口里那道 secrets 的替代名；
- 远程可达只说明 HTTP 成功，不说明内容、许可、behavior 与排序正确；
- PR 中远程可达步骤允许失败，合并者必须读结果，不能把黄色当绿色；
- CI 读取的是提交后的仓库，抓不到未提交的本地私密文件；
- 所有门禁都可能只有“绿样例”，若没有坏样例证明判负能力，绿色可信度有限。

~~因此公开发布前仍要显式补跑~~ ⇒ **下面这两项也都已进闸门**：

| 命令 | 闸门 | 编号 |
|:-----|:----:|:----:|
| `python self-conf-skills/gates/check_selfcontained.py .` | 自洽性 | **#42** |
| `python self-conf-skills/gates/clash/check_secrets.py clash` | clash secrets 扫描 | **#23** |

⇒ 二者均由 CI **强制**执行，无需人工补跑；本地既然是同一个 `verify_all.py`，
  也不用单独手敲。编号以 `python self-conf-skills/gates/verify_all.py --index` 现抓为准。

#### 7 · Issue、日志与截图纪律

#### 7.1 公开 issue 里不能贴什么

- 完整订阅 URL 或查询参数；
- 节点 server、端口与认证字段的真实组合；
- UUID、密码、密钥、证书内容；
- 内网地址、内部域名、设备名、用户名和本地绝对路径；
- 客户端导出的整份配置；
- 含二维码、订阅页、代理面板或网络拓扑的未打码截图；
- 会在报错上下文中回显上述内容的完整日志。

即使 token 已失效、节点已下线，也按秘密处理。失效不等于从历史、日志与搜索索引中消失。

#### 7.2 怎么打码才仍有诊断价值

保留**字段名、协议类型、错误码与结构**，替换值：

```yaml
server: node.example.com
password: REPLACE_WITH_YOUR_PASSWORD
uuid: REPLACE_WITH_YOUR_UUID
```

订阅 URL 只保留示例域、路径形状和 `REPLACE_WITH_YOUR_TOKEN`。截图要覆盖整块敏感区域，
不要只在图片上画半透明色块；文本日志先复制到本地编辑器搜索 token、auth、password、server、
内网域名和用户名，再贴最小复现片段。

#### 7.3 自动化输出也可能二次泄露

扫描器为了定位问题可能打印命中的片段。若它发现真实秘密：

- 不要把完整终端输出贴进 issue；
- 不要打开会把同一值再次上传的公开 CI；
- 在本地记录文件名与行号，轮换后再提交脱敏结果；
- 维护者在修扫描器时使用不可用的合成坏样例。

#### 8 · 漏洞报告与泄露处置

以下问题走 GitHub **Security → Report a vulnerability** 的私密安全通告，不发公开 issue：

- 仓内出现非占位节点、凭据或订阅 token；
- secrets / 自洽性门禁存在“全绿但实际未扫描”的路径；
- 远程规则集 URL 被替换到不可控镜像；
- CI、Release 或 artifact 暴露敏感材料。

一般性的分流建议、客户端兼容、文档笔误可以走普通 issue，但日志必须先脱敏。

报告内容应包括：受影响文件与 commit、秘密类型、是否仍有效、首次 / 最后出现范围、
已执行的轮换动作。**不要在通告标题或正文重复完整秘密。**

处置优先级：轮换凭据 > 阻止继续分发 > 清理当前树与历史 > 修门禁 > 复盘。

#### 9 · 第三方规则集供应链

#### 9.1 当前六类主要上游

“刷新周期”分两层：**上游多久发布**与**本地客户端多久拉取**。前者是来源特征，后者才是本仓可控参数。
当前 Surge / Egern 规则集通常显式为 `604800` 秒（一周），mihomo provider 统一为 `86400` 秒（一天）。

| 上游 | 本仓用途 | 本地刷新 | 主要风险 | 维护关注点 |
|:-----|:---------|:---------|:---------|:-----------|
| **MetaCubeX / meta-rules-dat** | mihomo 的 geosite / geoip `.mrs`；也是 `rules/AI.list` 的构建来源之一 | mihomo **1 天**；本地 AI 源快照需人工重抓再生成 | `meta` 移动分支持续变化；CDN 缓存有延迟；`.mrs` 不便人工审阅；format / behavior 配错会静默失配 | 核对 domain / ipcidr 类型、抽样反解、观察类别增删；上游标称日构建不等于本仓快照自动更新 |
| **blackmatrix7 / ios_rule_script** | Surge / Egern 分流应用集、LAN 补位；AI 整合器的多个源快照 | 现役规则集 **1 周**；构建快照人工刷新 | 大仓整体活跃不代表每个分类都活跃；集合可能混入 IP 条目；类别语义可能扩大 | 每次刷新重新数 IP / 域名条目，检查 `no-resolve`；不能只看文件名。历史上 Apple 集曾暴露裸 IP 条目问题 |
| **Jinx** | 三内核广告白名单与广告主清单 | Surge / Egern **1 周**；mihomo **1 天** | 白名单和黑名单都处在规则链最前，误收影响大；文件改名会造成死链静默降级 | 白名单必须先于广告；双广告出口参数一致；本仓曾因上游 `white-guard` 改名为 `direct` 留下 404 |
| **TG-Twilight / AWAvenue-Ads-Rule** | 第二条广告清单；mihomo 使用 `.mrs`，另两核使用 Surge list | Surge / Egern **1 周**；mihomo **1 天** | 广告规则误杀、与 Jinx 重叠；`.mrs` 内容不可直接 diff；镜像或产物链异常时影响 DNS 拦截 | 做白名单交集与误杀探针；mihomo 同一广告集必须同时进入 `nameserver-policy` 与 `fake-ip-filter` |
| **Loyalsoldier** | `private.txt`、`direct.txt`、`apple.txt`；Egern 的 GeoIP / ASN 数据库 | 规则集 **1 周**；数据库刷新周期在当前 profile 中未以同一 `update_interval` 明示，**待确认** | `direct.txt` 是国内直连主承重墙，误收会绕过代理；数据库漂移改变地理判断；release 路径仍是移动内容 | 下载后数内容类型与体量；审计国内探针；规则文件与数据库分开评估，不用“同仓可信”替代验证 |
| **Repcz / Tool** | Surge / Egern 的滚动 AI 集；也是本仓 AI 静态整合的参考源 | 现役规则集 **1 周**；本地快照人工刷新 | `X` 分支是移动目标；AI 类可能收进共享登录、CDN、遥测域，改变非 AI 流量出口 | 厂商专属集放在通用 AI 前；与自托管伴生域清单做重叠 / 误伤审计；记录抓取时间 |

#### 9.2 风险不能用“知名度”抵消

即使上游知名、长期活跃，也仍可能发生：

- 仓库转移、分支改名、文件删除；
- 自动构建成功但内容为空；
- 域名集混入 IP，或 classical 集被当成 domain；
- 清单范围扩大，把共享基础设施域收入应用专组；
- 许可改变或根本没有明确许可；
- 账号失陷、release 资产被替换；
- CDN 返回旧内容，而 raw 与 release 已更新。

所以“URL 可达”“仓库有星标”“昨天有 commit”都只是信号，不是信任结论。

#### 9.3 刷新周期的取舍

| 周期 | 优点 | 风险 | 适合 |
|:-----|:-----|:-----|:-----|
| 1 天 | 新域名与修复更快到达 | 上游误改也更快传播；请求更频繁 | mihomo 落盘 provider、变化快的 MRS |
| 1 周 | 给人工发现上游事故留缓冲；请求少 | 新域名生效慢 | Surge / Egern 当前远程规则集 |
| 锁 commit / 本地快照 | 可复现、可审计 | 会陈旧，需要主动更新流程 | 高风险或长期不变的小集合 |

刷新更快不是天然更安全。广告、DIRECT 与 DNS 相关清单的 blast radius 大，若没有内容门禁，
一天刷新只是把上游错误更快送到所有客户端。

#### 10 · 新增上游的评估流程

#### 10.1 准入前十问

1. **来源是谁**：仓库所有者、维护历史、是否有被接管或频繁迁移迹象？
2. **许可是什么**：允许引用、再分发、转换成 `.mrs` / `.yaml` 吗？不明确就标风险，不能默认 MIT；
3. **URL 稳不稳定**：release、固定 commit、移动分支、第三方镜像分别有什么取舍？
4. **内容是什么**：domain、ipcidr、classical 还是混合？扩展名不能替代内容检查；
5. **规模是否合理**：条目数骤增 / 骤减、空文件、HTML 错页能否被发现？
6. **语义是否过宽**：DIRECT、REJECT、AI 等高影响出口是否会收进共享基础设施域？
7. **与现有集怎样重叠**：白名单与黑名单、专属集与兜底集的顺序是否仍正确？
8. **失败时怎样退化**：有落盘缓存吗？拉取失败是报错、沿用旧版还是静默空集？
9. **多久刷新**：按变化速度与爆炸半径决定，不照抄别的内核；
10. **谁来守**：哪个脚本检查可达、内容、排序、生成物与文档登记？

#### 10.2 最小证据包

新增上游的 PR 至少应带：

| 证据 | 最低要求 |
|:-----|:---------|
| 来源记录 | 所有者、仓库、分支 / release、文件路径、许可、抓取日期 |
| 内容画像 | 总条目、域名 / IP / 其它规则类型数量、重复与无效行 |
| 行为声明 | format、behavior、目标策略、在规则链中的位置 |
| 风险分析 | 误杀、绕过、死链、移动分支、镜像与账号接管风险 |
| 更新策略 | 客户端刷新周期、是否落盘、是否锁版本、回滚方法 |
| 自动化 | 可达性检查、结构检查、生成物检查；至少一个判负坏样例 |
| 实测 | 代表性命中、误杀探针、断网 / 404 时的退化结果 |

#### 10.3 接入步骤

1. 在临时目录下载并保存哈希，不直接把未知内容喂给现役配置；
2. 检查状态码、Content-Type、文件头与解析类型，排除“200 但返回 HTML”；
3. 统计条目类型、体量、重复、私网 / 保留地址与高风险宽后缀；
4. 与白名单、广告集、国内直连集和更具体的应用集做交集；
5. 决定远程引用还是本仓快照。需要跨内核复用时，以 `.list` 为真源并生成其他格式；
6. 为各内核分别设置 format / behavior / `no-resolve` 落点和刷新周期；
7. 更新 URL 可达性收集器、secrets 主机白名单与自洽性分类；
8. 把规则插入正确顺序，运行路由探针与 DNS 审计；
9. 模拟 URL 404、空文件和内容混型，确认门禁能判负或客户端能安全沿用缓存；
10. 更新规则来源文档，不把实现清单堆到根 README。

#### 10.4 拒绝准入的情形

- 来源无法确认、短链或个人临时文件托管；
- 没有许可且需要再分发 / 修改；
- 内容类型与声明不一致；
- 高影响 DIRECT / REJECT 集无法抽样审阅；
- 只能通过扩大 secrets 白名单或关闭门禁才能接入；
- 与现有来源高度重复，却没有覆盖增益或故障隔离价值；
- 无法说明失效与回滚路径。

#### 11 · 发布前检查单

#### 11.1 提交前

- [ ] `git diff --cached` 中没有真实节点、凭据、token、证书、私有路径与内网标识；
- [ ] 所有可替换值使用 `REPLACE_WITH_YOUR_*`；
- [ ] 完整版、`.min` 与覆写脚本都检查过，不只看当前入口；
- [ ] 第一方图标 / 规则 URL 指向 `self-conf`；
- [ ] 第三方上游已登记用途、许可风险、刷新周期和回滚；
- [ ] 新增文件后缀和运行期拼接 URL 已进入扫描面。

#### 11.2 本地命令

```bash
python self-conf-skills/gates/check_secrets.py
python self-conf-skills/gates/clash/check_secrets.py clash
python self-conf-skills/gates/check_selfcontained.py .
python self-conf-skills/gates/verify_all.py
python self-conf-skills/gates/clash/check_remote_urls.py --timeout 20
```

远程检查会受网络抖动影响；失败时要区分超时、限流、证书错误与真实 404，不能为了过门禁直接删规则。
本地全绿后仍需等 GitHub Actions，因为路径、换行与输出编码问题曾只在 CI 暴露。

#### 11.3 发布后

- [ ] 查看 CI 每一步，而不是只看总 badge；
- [ ] PR 中远程可达若为允许失败，人工确认结果；
- [ ] 随机打开一条本仓 raw 图标和一条本仓规则生成物；
- [ ] 用匿名 / 未登录窗口确认公开面看不到不应公开的日志或 artifact；
- [ ] 定时任务首次运行后复查上游可达性。

#### 12 · FAQ

**Q：把真实 token 改成失效 token 后可以留在历史里吗？**

不可以。失效值仍会暴露订阅 URL 结构、账户关联和历史使用痕迹，也可能被误恢复。
轮换后仍要从当前树移除，并评估历史清理。

**Q：只要 `check_secrets.py` 通过，就能公开吗？**

不能。它不证明仓库自洽、上游可信、截图已打码，也不证明启发式没有漏报。
至少还要跑自洽检查、总门禁，并人工看 staged diff。

**Q：为什么允许第三方规则 URL，却禁止被依赖仓库的 URL？**

第三方是登记过的产品依赖；而图标与自托管规则已属于本仓，继续回指说明迁移未完成。
二者的所有权、替代路径和故障语义不同。

**Q：上游改名造成 404，客户端会马上报错吗？**

未必。mihomo rule-provider 可能沿用缓存，也可能退化为空集；症状常是“还能联网但广告或分流失效”。
这就是定时可达性检查存在的原因。

**Q：能把所有第三方规则都复制进本仓，彻底离线吗？**

技术上可行，但会承担再分发许可、更新、来源追踪与安全响应责任。只有当许可允许、快照价值明确且有
生成 / 更新流程时才这样做；否则保留远程引用并做好缓存与监控更诚实。

**Q：issue 里必须给完整配置才能排查怎么办？**

先制作最小复现：保留键与规则顺序，把所有地址、凭据、节点名和订阅换成占位符。
若问题本身就是泄露或门禁绕过，改走私密安全通告。

#### 13 · 维护者须知

1. **秘密先轮换，后清历史。** 不要把强推当成撤回能力。
2. **占位符必须可机器识别。** 新凭据键出现时，同一 PR 扩扫描器和坏样例。
3. ~~自洽检查目前仍是手动门禁~~ ⇒ **已于 2026-10-08 接入 CI**（闸门 #42），口径已更新。
4. **可达不等于可信。** 新增上游必须完成 §10 的内容、许可、排序与失败模式评估。
5. **刷新周期按爆炸半径决定。** DIRECT、REJECT、DNS 清单优先可审计与可回滚，不盲目追快。
6. **白名单保持最窄。** 每个允许主机、地址段和已知差异都要有来源与用途。
7. **README 只写产品结果。** 上游清单、判据与事故复盘放在 `self-conf-skills/references/`，不要污染门面。
8. **公开 issue 永不收秘密。** 发现泄露立即转私密通告，并删除公开副本。

---

相关：[`gates.md`](./gates.md) · [`profiles/<kern>.md`](./profiles/clash.md) ·
[`rulesets.md`](./rulesets.md) · [`AGENTS.md`](../../AGENTS.md) ·
[`../../../SECURITY.md`](../../SECURITY.md)
