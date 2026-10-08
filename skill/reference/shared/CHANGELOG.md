# 更新日志

本文件按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范编写。

---

## 2026-10-08（第十三轮 · 补记第十二轮 + 本轮修复）

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
