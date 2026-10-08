# 更新日志

本文件按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范编写。

---

## 2026-10-08（第十五轮 · 修掉两轮记账未修的判据盲区 + 一个潜伏真 bug）

> 本轮的起点是第十四轮留下的三行「已知边界（未修）」和一个被回滚的重写。
> 上一轮在同一个函数上打了 10 次补丁、最终因**过宽假红**整轮回滚，
> 教训写成了「改不动就早停、早回滚、早记账」。本轮把那笔账结了 ——
> 但换了做法：**先把反例固化成用例，再改判据**，而不是改完靠手测。

### 1. 环境变量 AST 扫描：7 种溜过的写法全部收口（第十四轮记账未修）

**病根不是漏了几个写法，是判据挂错了地方。** 上一版按**语法位置**判定
（`base.attr == 'environ' and base.value.id in os_names`）—— 只认「直接成员访问」，
把对象搬到一个新名字上就整类失明。

本轮改为**按名字 + 污点传播**：

| 曾经溜过的写法 | 现在 |
|:---|:--:|
| `E = os.environ; E.get("X")` | ✅ 抓到 |
| `environ = os.environ; environ.get("X")` | ✅ 抓到 |
| `g = os.getenv; g("X")` | ✅ 抓到 |
| `getattr(os,'environ')["X"]` | ✅ 抓到 |
| `getattr(os,'getenv')("X")` | ✅ 抓到 |
| `globals()['os'].environ.get("X")` | ✅ 抓到 |
| `from os import *` 后 `environ.get("X")` | ✅ 抓到 |

每个写法都**作为真实后门注入过一遍**（在 `check_badges.py` 里塞
`E.get("TOTALLY_NEW_ESCAPE")`），确认 `verify_all` 以 exit 1 报出、
并点名字所在文件。

### 2. 判据过宽与过窄同样是失效（第十四轮翻车的真因）

上一轮重写其实**已经抓全了 7 种**，却因把所有「碰过 `os.environ`」的写法
一律判为动态（`dict(os.environ)` 中招）⇒ 10 个文件假红 ⇒ 门禁判负 ⇒ **整轮回滚**。
本轮把这条边界**写死进判据与文档**（`release-rules.md` §4.2.3.1）：

| 写法 | 算不算读取 |
|:---|:--:|
| `os.environ.get("X")` / `E.get("X")` / `getenv("X")` / `["X"]` | ✅ 算 |
| `dict(os.environ)` / `os.environ.copy()` / `env = os.environ` | ❌ **不算**（只取快照或传引用，没取任何键）|

> 教训：**「过宽」更隐蔽** —— 它不会放过坏人，它会让好人受不了而把判据整个撤掉。

### 3. 注错用例固化进代码（本轮最重要的工程改动）

新增 `_ENV_SCAN_FIXTURES`（**24 条**：17 条正例 + 7 条防过宽反例）
与 `_selftest_env_scan()`，在 `main()` 里与两个 `_assert_*` 护栏并列执行。
**判据失效当场报错**，不再靠「改完手测一遍」—— 手测不留痕，下一轮重写时同样的洞会再开一次。

### 4. 抓到一个潜伏真 bug：`check_badges.py` 的 `NL` 未定义

`except`（profiles 解析失败）分支里写 `+ NL`，而该文件**从未定义过 `NL`**。

| | 本意 | 实际（修前）|
|:--|:--|:--|
| 退出码 | 2（环境不达标，先修环境）| **1（判负）** |
| 输出 | 「profiles 解析失败: …」 | `NameError` traceback |

⇒ **环境坏了被读成「判据判负」**，正是本仓全仓在防的那件事。
与 `check_script_sync.py` 的 `diff` 未定义是**同一类**（只在异常/判负路径上才炸）。
已实测复现（塞一份坏 YAML 进 `egern/profiles/routing.yaml`）并修复，退出码回到 2。

### 5. 新增闸门「未定义名扫描」：门禁 47 → 48 道

`skill/tests/check_undefined_names.py` —— 专扫上面那一类（F821 类）。

**为什么不用 pyflakes**：

1. 外部依赖 —— CI 只装 `pyyaml`；没装就只能 SKIP，而 SKIP = 未验证 = 这道门在 CI 上不存在。
2. **信噪比 1/29** —— pyflakes 对本仓报 29 条，**只有 1 条是真 bug**（`NL`），
   其余是 unused import / f-string 无占位符。真 bug 会被噪声淹没。
3. 本仓要的是判据，不是风格检查。

⇒ 自实现**窄判据**（仅未定义名，约 200 行），零依赖、零豁免、零假红。
与 `pyflakes` 的 F821 输出**逐条对拍一致**。已同时接进 `verify_all` 与 `ci.yml`
（独立 step，让 CI 日志里有一行一眼可见的结果）。

### 6. CHANGELOG 漂移闸门：两条「已知的宽」收口（第十四轮记账未修）

| 边界 | 修法 |
|:---|:---|
| 素材二选一回退 ⇒ 干净树上**新建未 add 的脚本完全隐形** | 改为 `git diff HEAD` **并集** `git ls-files --others --exclude-standard` |
| 文件名写进 **HTML 注释**也算「已记录」 | 当天段落先剥 HTML 注释 |

⚠️ **刻意不剥代码块与行内代码** —— 写成「新增 `X.py`」是最常见的**合法**写法，
剥了就变成过严（同 §2 的教训）。四个场景实测：A 未追踪抓到、B 注释不算、
C 行内代码算、D 代码块算。

**第三条边界刻意保留**（没有豁免/跳过路径）：本仓「没记账」已复发 3 次，
宁可每次人工写一句，也不给一个「按一下就当记过了」的开关。

### 7. 修掉两处「文档在为不存在的事实背书」

- `clash/checker.md` §15 演进表：`diff` 那行仍写「**（未修）**」，
  而 §6.2 正文与代码都已是「已修（commit `7d7250c`）」—— **同一事实两处相反**。
  已实测确认 `diff()` 定义在第 94 行、真实漂移时给出
  `rules[6] 不同: 脚本 '…' vs 静态 '…'` 精确诊断（**不是** `NameError`）⇒ 表格已对齐。
- `clash/checker.md` §16.4「四条已知挂账」：第 1 条（`diff`）已修、
  第 2 条（清单人工双写）已有 `check_gate_manifest.py` 机器对账 —— 两条均已消。

### 8. 道数同步：47 → 48（32 处散文）

上一轮新增闸门后**只改了 §11 表，约 30 处散文仍写 46**，本轮特别注意了这点。
`gen_gate_table.py --apply` 处理表头与近重复编号（编号 `#9/#43`、`#11/#47` 是现算的），
其余 32 处散文（`ci.yml` / `README` / `ops.md` / `checker.md` / `pitfalls.md` …）逐处同步。
**CHANGELOG 里的「门禁 24 → 47 道」是历史记录，刻意不改。**

### 本轮动过的文件

`skill/tests/verify_all.py`（AST 扫描重写 + 注错用例 + 新闸门）·
`skill/tests/check_undefined_names.py`（新增）·
`skill/tests/check_badges.py`（`NL` 真 bug）·
`skill/tests/check_changelog_drift.py`（两条边界）·
`skill/scripts/egern/probe_dns_endpoints.py`（联网重试）·
`skill/reference/shared/release-rules.md`（§4.2.3.1 判据边界）·
`skill/reference/clash/checker.md`（§15/§16.4 过时记录 + §11 表）·
`.github/workflows/ci.yml`（新 step）· 及 32 处道数散文。

### 已知边界（不改，记录在案）

- **名字不是字面量**（`os.environ.get(var)`）静态**本质上**判不出 ——
  仍靠 `§4.2.3` 白名单（登记 = 人工看过），不声称能自动抓。
- `_default_root()` 仍是**多份拷贝**（clash 侧已 6 份）。本轮的未定义名扫描
  能抓住「拷贝时漏了某个名字」，但抓不住「六份逻辑各自漂移」——
  抽公共模块会动 6 个文件的导入结构，收益与风险需单独评估。

### 9. 联网探测加重试：修掉 CI 「绿不绿看运气」的缺口

**事件**：推完本轮后 CI 红了 —— 红的不是本轮新增的 step，而是**原有**的
「Encrypted DNS endpoints reachability (Egern)」（push 事件下 `continue-on-error` 为 false）。
报 `https://120.53.53.53/dns-query` 两次都 `_ssl.c:993: The handshake operation timed out`。

**判定为偶发不可达，不是真失效**，三条证据：

1. 同一台服务器的 `tls://1.12.12.12`（853）在**同一次运行里正常** —— 域名解析出同一个 IP，
   只是 DoH 的 443 不通。
2. 历史两次成功 run 里该 DoH 端点**都是 HTTP 200**（`gh run view --log` 逐行核过）。
3. 本机直连该 IP:443 的 TLS **连测 4 次全成功（0.08s）**，但脚本里同一端点
   **第一次失败、第二次成功** ⇒ 典型冷连接/偶发丢包。

**根因不是网络，是设计不一致**：

| 脚本 | 有重试？ |
|:--|:--:|
| `clash/check_remote_urls.py`（姊妹门禁）| ✅ `for method in ("HEAD", "GET")` |
| `egern/probe_dns_endpoints.py` | ❌ **单发，零重试** |

更矛盾的是：这个 step 当初**不进 48 道**的理由写的正是「抖动会假红」——
却在 CI 里以最严的方式判红。⇒ 已对齐：`RETRIES = 3` + 递减退避。

⚠️ **只对异常重试，拿到应答不重试** —— 后者是真判据问题，不该被重试掩盖。
真失败时输出明写「已重试 3 次」，不假装一次就通。
**双向验证过**：把 `TIMEOUT` 压成 `0.001` 强制失败 ⇒ 报
`FAIL timed out（已重试 3 次）` 且 exit 1；还原后 exit 0。

---

## 2026-10-08（第十三轮 · 补记第十二轮 + 本轮修复）
---


> ⚠️ 上一轮（第十二轮）的五条**当时一条都没记进 CHANGELOG** —— 补的段落写的是
> **第十一轮**的内容。本仓第三次栽在"改了没落 CHANGELOG"上，根因是自检口径错位
> （只验"存在今日条目"，不验内容）。本段起由 `check_changelog_drift.py` 自动拦截。

### 第十二轮修复（补记）

- **逃生门护栏方向做反了**（核心）。原实现遍历 `GATE_CHANGING` 三个硬编码名字查登记，
  **不是**全量差集 ⇒ 新加的放行类后门只要不叫这三个名字就抓不到 ——
  护栏自己正在放过它声称要防的事。改为 `candidates = alive - input_ok`。
- `import os as _os` 别名 ⇒ 护栏"看不见" `SKIP_V7`（两头都错：删登记不判负 +
  反向自检常态化误报）。改为按文件收集 `os` 的别名集合。
- `_token()` 的 `except Exception: pass` 把 gh 返回非零/超时/token 过期全吞了。
  现分情况打 ⚠️，能分清"没装 gh"和"装了但失败"。
- `print_index()` 脚注原写"末位那个 Encoding gate"（错）。
- 写 CHANGELOG 时 `\bin` 里的 `\b` 被当退格符写进文件 —— 已清干净，并统一路径斜杠。

### 第十三轮修复（本轮）

- **`_collect_env_reads()` 的 AST 扫描重写**（第十三轮问题 1）。上一轮只补了
  `import os as _os` 一种，**整类常见写法仍然不可见**：`os.getenv` /
  `from os import environ[ as e]` / `from os import getenv` / `getattr(os.environ,"get")` /
  二次别名 `_oo = _o` / **名字存在变量里** —— 逐个实测全部能溜过去。
  现按文件做局部符号解析（别名链 + from-import），覆盖上述全部形态；
  **剩下的动态形态静态本质上判不出** ⇒ 不假装能抓，改为 **fail-closed**：
  新增 `§4.2.3 动态读取白名单`，未登记即报错（`verify_all.py` 自己第 ~77 行
  的 `os.environ.get(env)` 就是这种，已显式登记为"仅读路径类变量"）。
  ⇒ `release-rules.md` 那句"反查**每一个**环境变量名"现在名副其实。
- **`print_index()` 脚注序号再修正**：那个列表里 Install=1、Gates=2、
  **Encoding gate=3** —— 上一轮改的"第 2 个"仍是错的（把一个错数字换成另一个错数字）。
- **新增 `check_changelog_drift.py`**（第十三轮问题 3）——把"逐内容验证"落进脚本：
  取未提交改动（或最近 N 条 commit）作为素材，要求 CHANGELOG 最新条目至少点名其一，
  **一个都没提 ⇒ 判负**。已接进 verify_all、gc CI。

### 已知边界（不改，记录在案）

- 真机验证（Surge / Egern 闭源且仅苹果系统；mihomo 需真内核二进制）**客观无法自动化**。
- **名字存在变量里**（如 `_KEY="X"; os.environ.get(_KEY)`）静态**本质上**判不出具体名字；
  本仓用 §4.2.3 白名单兜底 —— 登记即表示人工逐行看过，不是声称能自动抓到。

---

## 2026-10-08

<!-- check_badges.py 只在注释里提一下 -->

### 判据与闸门
- 三内核现役版本统一 `v1.0.0`；新增 `check_version_header.py` 的 **V5 断言**守着它。
- 发布首个 Release `v2026-10-08`（12 份资产），`check_releases.py` R1–R5 随之启用。
- `release_publish.py` 适配三内核（11 处硬编码 → `KERNS`/`kern_ext()` 单一真源）。
- 新增闸门：规则集来源文档同步、`make_min` 自检、脚本对拍 diff 自检、
  闸门清单对账（含孤儿探测）、闸门总览表同步、自托管清单裸 IP 检测。
- 门禁 24 → **47 道**（含两对刻意的双档覆盖：#9/#41、#11/#45）。

### 判据有效性（本轮重点）
- V7 豁免改为「未验证」（⚠️，不计入 passed，本道 exit 3），不再冒充通过。
- V6 前代版本线豁免改为**白名单区间**（上界 v4.0.4），超界判负。
- 修掉三处「假绿/假信心」：`audit_routing_coverage` 离线档补静态策略校验、
  `profile_ruleset` 空清单判负、`audit_ruleset_content` 零 provider 判负。
- `checker.md` §11 总览表改为 `gen_gate_table.py` 现抓生成；近重复与「不进闸门」
  两张表均由真源动态计算，不再手抄。
- CI 侧 SKIP(3) 判失败，并区分「已登记豁免」（白名单，与 release-rules §4.1 交叉校验）
  与「环境异常」。

### 修掉的文档漂移
- `tun`：四处文档曾要求四键，与代码（禁止 tun）相反 ⇒ 全部改正。
- 图标数 → 实际 40 PNG + 1 SVG；各处「16/17/21/27/42/44 道」→ 46。
- 六处「mihomo 没有分流覆盖审计脚本」→ 已有（闸门 #9）。
- 多处过期闸门编号按 `--index` 校正。

### 已知边界（不改，记录在案）
- 真机验证（Surge/Egern 闭源且仅苹果系统；mihomo 需真内核）**客观无法自动化**。
- `check_gate_manifest` 的孤儿探测只覆盖「同名跨内核」，独有名字的新脚本不报。
- SKIP_V7 是**无条件**豁免 ⇒ 将来真出现「同一天连升两号」V7 抓不到。

---

## 2026-10-08（下午第二轮 · 第十一轮审查修复）

### 修复

- **`_token()` 的 gh 回落真能用了**（第十一轮问题 1）。上一轮只是"代码形状对"
  （写了 `subprocess.run(['gh', ...])`），但 `gh.exe` 不在 Python 的 PATH 上 ⇒
  异常被 `except Exception: pass` 吞掉 ⇒ **本机实际永远返回 None**，而 docstring
  却写着"自动回退 gh auth token" —— 文档在为**不存在的回落**背书。
  新增 `_gh_exe()`：PATH + `%LOCALAPPDATA%\Programs/GitHub CLI/bin\gh.exe` +
  `%PROGRAMFILES%` + `/usr/bin` 等候选逐个定位；`_token()` 改用绝对路径调用。
  实测：`_gh_exe()` 定位成功，`_token()` 真取到 token。

- **逃生门登记建立 `§4.2`**（第十一轮问题 4）。`UNIFIED_VERSION` 此前是**未登记**的
  逃生门（能改 V5 的期望值），与 `SKIP_V7` / `STRICT_ARCHIVE` 都登记了的自律不一致。
  分两类：**4.2.1 放行类**（必须登记，缺失即判负）／**4.2.2 输入类**（仅备查，
  `GITHUB_TOKEN` / `GITHUB_REPO` / `GITHUB_ACTIONS` / `CI`）。
  分界线：动它会不会改变"该判负还是判通过"。
  配套 `_assert_escapes_registered()`：AST 扫 `skill/**/*.py` 的 `os.environ` 读取，
  与 §4.2.1 表格做差集，未登记 ⇒ 启动即报错。

### 修掉的文档漂移

- `public-repo.md`：标题写"仍在闸门之外"，代码块里两项**当时已经在跑**
  （#42 自洽性 / #23 clash secrets 扫描），末句也称"不得声称 CI 已覆盖" ——
  三者自相矛盾。改为表格写明编号，结论改为"CI 强制，无需人工补跑"。
- `checker.md` 的 CI 步骤表补第 8 行「Encrypted DNS endpoints reachability (Egern)」
  （`print_index()` 和 §11 都知道它，只有这张表漏了）。
- `gen_gate_table`：`reasons{}` 与 `check_gate_manifest.KNOWN_SEPARATE` 是两份拷贝、
  措辞还不一样（而 §11 正宣称"不会分叉"）⇒ 删掉本地拷贝，单一真源。
- "位置"列由 `_where_of()` 动态判定（是否出现在 ci.yml 的**非注释行**、
  且为真实调用形态），不再写死成 `—`。

### 已知边界（不改，记录在案）

- 真机验证（Surge / Egern 闭源且仅苹果系统；mihomo 需真内核二进制）**客观无法自动化**。

---

## 2026-10-07

### 新增

- 🧭 **三内核并列** —— `surge/`（Surge）、`egern/`（Egern）、`clash/`（mihomo）各占一个顶层目录，互不干扰。
  clash 侧另有 `clash/override/`，是本仓独有的**覆写脚本**形态（挂到任意订阅上，输出与静态 profile 逐位一致）。
- 🔗 **共享资产单源化**
  - `icons/` 三内核引用同一份（38 个）。
  - `rules/` 以 `.list` 为唯一真源，mihomo 用的 `.yaml` 由 `skill/scripts/clash/build_rules.py` 生成 —— 单一真源，不会漂移。
- 🛡️ **clash 侧补齐四个审计器**（此前为零，是最大的对标缺口）
  - `check_clash_dns.py`：DNS 防泄露审计，14 项判据（与 `check_surge_dns.py` / `check_egern_dns.py` 同职责）。
  - `audit_region_filters.py`：地区组判别力审计，7 条判据。
  - `audit_routing_coverage.py`：分流覆盖审计，含**联网档**（离线档为默认，CI 友好）。
  - `audit_ruleset_content.py`：规则集内容审计（behavior 与实际内容是否相符、裸 IP 条目）。
- ✅ **真机验证脚本** `skill/tests/clash/check_real_kernel.py`
  用真实 mihomo 二进制跑 `-t -f`；找不到二进制退 2（未验证，不是通过）。
  实测 mihomo Meta alpha-9f053c4：四份静态配置 + 脚本输出形态全部 `test is successful`。
- 📝 **clash 侧文档 11 篇**，规格对齐另两个内核的 8 篇。
- 📚 **共享层 8 篇全部扩到三内核**：`cross-kernel-diff.md`（三内核移植边界）、`ops.md`、`dns-basics.md`、
  `rulesets.md`、`hardening-checklist.md`、`no-resolve-pairing.md`、`boundaries.md`、`troubleshoot-faq.md`。

### 修复

- 🧱 `routing.yaml` 被**纵向堆叠 7 份**（3294 行）—— 重生成时用了追加模式。已修复并加自检。
- 📡 两份静态 profile 的 `proxy-providers` **整段丢失** —— 用户导入后无从填订阅。已改为从静态版继承。
- ⚙️ `Smart` **未接上三档** —— 声明了 `Low Mult./Auto/High Mult.` 但 `Smart.proxies` 仍是 `["DIRECT"]`，
  三档形同虚设（声明了却没连，比不声明更隐蔽）。
- ✈️ **机场城市名/三字码无组可归** —— 「东京 01」「NRT 03」「LAX 02」「硅谷 03」六地区组全不匹配：
  城市名只存在于 `Other Regions` 的排除块，而日本/美国组的正向 filter 只有国家简称。按姊妹仓写法补全。
- 🔗 远程规则集死链静默降级 —— Jinx 上游把 `*-white-guard.*` 改名 `*-direct.*`，懒人版一直挂着 404。
- 🛑 两版 `AD` 组口径不一致（分流版 `REJECT,DIRECT` / 懒人版单成员 `REJECT`）—— 已统一。
- 🔒 IPv6 未显式关闭（顶层 + `dns.ipv6` 两处都要 false）；`nameserver` 写主机名导致明文引导查询；
  `nameserver-policy` 用了无依据的逗号多值；`geoip-*` 缺 `no-resolve`。均已取得官方/源码依据后修正。
- 🔢 头注里的规模数字过期（`my_clash.js` 写 20 组/20 集/26 条，实际 22/25/27）。

### 变更

- 🧪 判据从 17 道扩到 **21 道**，CI 全绿。
- 📖 文档去除「实验性 / 原仓 / 两仓」等来源表述 —— 本仓是三内核并列的新仓库，不是 1+1=2。
- 🏷️ 仓库描述改为「Surge · Egern · mihomo 三内核配置模板 · 殊途同归 · 久用如一」。

### 已知取舍（不是缺陷）

- `Jinx-Ads` 等 `classical` 规则集只生效域名类规则（真机 warning 确认）。
- `tun.dns-hijack: any:53` 按官方语义只收 UDP:53（收 TCP 需另加 `tcp://any:53`）。
- 覆盖审计联网档对 `.mrs` 是退化为文本版判的，未逆向二进制正文。
- 地区组正则用 Python 近似（mihomo 用 Go regexp2，支持 `(?i)` 在任意位置）。
