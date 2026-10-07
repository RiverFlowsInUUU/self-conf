# 坑 · 事故复盘（mihomo / clash 侧）

> **何时读**：排查实际失效（拦截没了 / 分流变了 / 门禁红了），或**改动判据 / 规则集 / 生成流程之前**。
>
> 每一条都来自实测或 CI 暴露。摘要在前，详述在后。
> 判据演进史另见 [`checker.md`](checker.md)；配置结构见 [`profile-anatomy.md`](profile-anatomy.md)。
>
> 📌 **本文件的母题与姊妹仓一致：审计通过 ≠ 配置可用。**
> 但 mihomo 侧有它自己的第二条母题：**本地全绿 ≠ 线上能跑**。
> 本仓 15 条里有 5 条是"本地怎么跑都绿、换台机器或上 CI 就红"。

## 速查表

| # | 坑 | 一句话 | 判据固化在哪 |
|:-:|:---|:-------|:-------------|
| 1 | 远程规则集死链**静默降级** | `mihomo-white-guard.yaml` 404 了半年，没人知道 | `check_remote_urls.py` + CI 每周任务 |
| 2 | 静态 profile 被**纵向堆叠 7 份** | PyYAML 只取最后一份 ⇒ 全绿看不出 | `build_profiles.py` 的两条硬保证 |
| 3 | 门禁引用未定义的 `diff` | 恒一致时不触发，真漂移时 `NameError` 且无诊断 | `check_script_sync.py` 的 `diff()` 本体 |
| 4 | DNS 广告拦截**双条件缺一即失效** | 只写 `nameserver-policy` 不写 `fake-ip-filter` = 完全没效果，且不报错 | `check_structure.py` ③（a/b/c/d 四条）|
| 5 | IPv6 未关闭 | 只关一处 → 真实 IPv6 绕 TUN 出网，出口 IP 与节点不符 | `check_structure.py` ④（`is not False`）|
| 6 | 改了脚本忘重生成静态 profile / `.min` | 两边漂移，两边都不报错 | `build_profiles.py --check` + `check_min_pair.py` |
| 7 | Windows 中文环境 print 非 GBK 字符 | `UnicodeEncodeError` → 退出码 1 → 被读成「判负」 | 每脚本 import 时 `reconfigure` + CI 编码门 + E4 |
| 8 | 路径探测基于 `__file__` | 本地全绿，GitHub Actions 上报「缺文件」 | 四个 clash 门禁的 `_default_root()`（CWD 优先）|
| 9 | 复制文件丢 mtime | V7「一天一版」误判成当天升了 21 个版本 | `cp -p` + `SKIP_V7`（输出「未验证，不是通过」）|
| 10 | 两版 `AD` 组口径不同被套错 | 分流版 `REJECT`/`DIRECT`，懒人版单成员 `REJECT` | ⚠️ **仅靠注释与文档，无机器判据（挂账）** |
| 11 | 跨仓引用 → 本仓不自洽 | 2511 处 URL 仍指向外部仓库（图标 2311 + 规则集 200）| `check_selfcontained.py`（手动跑，不进 21 道）|
| 12 | 靠「高熵」判凭据 | 漏掉含 `@` 的密码（实测 `MyRealP@ssw0rd123` 漏过）| `check_secrets.py` 的**占位白名单制** |
| 13 | `198.18.0.1` 被判成真实 IP | 那是 mihomo fake-ip 段（RFC 6815），Surge/Egern 侧不认识 | `DOC_NETS` / `ALLOWED_IPS` 窄白名单（**两处**）|
| 14 | 只测「好配置通过」 | 恒返回 0 的脚本也能让现役配置全绿 | `checker.md` §9 的 15 个注入样例（⚠️ 无自动化回归）|
| 15 | CRLF 判负 | Clash 侧 3 个文件是 CRLF，按 `\n` 写的正则失配 | `.gitattributes`（`* text=auto eol=lf`）|

---

## 1 · 远程规则集死链：静默降级，不是报错

### 现象

Jinx 上游把 `*-white-guard.*` 改名为 `*-direct.*`。本仓脚本里那条
`mihomo-white-guard.yaml` 就此 404。**分流版改配置时碰巧发现并修了，
懒人版一直挂着死链没人察觉。**

实测（本次文档编写时现抓，三条一组）：

| URL | 实测 |
|:----|:----:|
| `…/Jinx/main/mihomo-white-guard.yaml` | **404** |
| `…/Jinx/main/mihomo-direct.yaml` | 200 |
| `…/Jinx/main/mihomo-ads.yaml` | 200 |

### 根因

两层，缺一不可：

1. **上游改名是无声的。** 它不发通知、不 deprecated、不重定向 —— 只是某天起返回 404。
   本仓没有任何机制会定期去问「这个 URL 还活着吗」。
2. **死链在客户端的表现不是报错，是静默降级。**

```
rule-provider 拉取失败
   → 该 provider 变成空集（不是报错，不是加载失败）
   → RULE-SET,Jinx-Ads,AD 永远不命中
   → 广告域名落到 MATCH,Proxy
   → 面板一切正常、配置"能跑"、没人报障
   ⇒ 拦截功能消失，且没有任何人收到通知
```

> ⚠️ 第二层才是这条坑的真正杀伤力：**它不会触发任何报警。**
> 一个"报不出来"的失效，只能靠主动探测发现。

**为什么当时没发现**：本仓**当时没有 CI**。死链的发现路径只有"有人正好改到那一行"。
分流版被改到了（所以修了），懒人版没被改到（所以一直挂着）。

### 修法

不是"记得去检查"，而是**把它变成一道会定期跑的闸门**：

```python
# skill/tests/clash/check_remote_urls.py
#   ① 纯文本扫 override/ 与 profiles/ 里的 http(s) URL
#   ② 真的执行一遍 override/*.js，取运行期生成的 URL
#   逐个 HEAD（不通则退化为 GET），非 2xx/3xx 即判负
```

⚠️ **第二条路径是关键设计，缺了它这道门等于半瞎**：

```javascript
// override/my_clash.js 里 MRS 是拼出来的
url: JS + "/geosite/" + c + ".mrs"
//         ↑ 基址常量 + 变量拼接 —— 纯文本扫描抓不到完整 URL
```

`collect_urls()`（文本扫）与 `collect_from_scripts()`（跑脚本）**两条收集路径必须都在**。

配合 CI 的两处设计（`.github/workflows/ci.yml`）：

```yaml
on:
  schedule:
    # 每周一 03:17 UTC —— 抓「上游规则集悄悄改名/删档」这类本仓无从感知的变化
    - cron: '17 3 * * 1'
…
- name: Remote ruleset reachability (mihomo)
  run: python skill/tests/clash/check_remote_urls.py --timeout 20
  continue-on-error: ${{ github.event_name == 'pull_request' }}
```

| 设计 | 理由 |
|:-----|:-----|
| **每周定时任务** | 上游改名是**时间驱动**的事件，不是 push 驱动。没有 `schedule`，死链可以躺到有人碰那行为止。 |
| **PR 时 `continue-on-error`** | 死链要拦在 `main` 上，但不该因为 CDN 抽风挡住一次无关 PR。这是**有意的非对称**，代价是 PR 上可能绿灯合并 —— 靠每周任务兜底。 |

**排除规则**（避免误判，都是实测踩出来的）：

| 排除项 | 为什么 |
|:-------|:-------|
| `PLACEHOLDER_PAT`（`example.com` / `REPLACE_WITH` / `127.0.0.1`）| 那是给用户替换的订阅槽位，**本来就不该可达** |
| `BASE_URLS`（3 个基址常量）| 拼接用的前缀本身不是可探测的资源 |
| `DOH_PAT`（`/dns-query$`）| 是解析器不是静态资源，HEAD 往往不通 |
| `HC_URLS`（`generate_204`）| 连通性探针 |
| `RESOURCE_SUFFIX` 白名单 | 只有 `.mrs`/`.yaml`/`.list`/`.txt`/`.json` 才算"规则集资源"，其它一概不探测 |

### 判据固化在哪

- **`skill/tests/clash/check_remote_urls.py`** —— 收集（两条路径）+ 探测（HEAD→GET 退化）+ 排除规则全在这里。
- **`.github/workflows/ci.yml`** 的 `Remote ruleset reachability (mihomo)` step（含每周 cron）。
- 判负样例：`checker.md` §9.2 第 15 条 —— 把某条 URL 改回 `mihomo-white-guard.yaml`（**即当年真实死链**），期望 `NG` + `死链 N 个` + exit 1。
- 文档：`profile-anatomy.md` §9.5 的警告块。

⚠️ **已知文档漂移（待确认）**：`skill/reference/clash/ruleset-sources.md:76` 至今仍写
`mihomo-white-guard.yaml`。它不在 `check_remote_urls.py` 的扫描面内（是 Markdown），
`check_selfcontained.py` 也不扫 `.md` ⇒ **没有任何闸门会发现它**。
**改规则集 URL 时，文档表要手工同步 —— 这是个没有机器兜底的手工步骤。**

---

## 2 · 静态 profile 被重复粘贴（纵向堆叠 7 份）

### 现象

`clash/profiles/routing.yaml` 一度有 **3294 行**，里面纵向串了 **7 份完整的 YAML 配置**
—— 无 `---` 分隔、无注释说明，首尾相接。

逐块切片核对的结果：

| 块 | 行 | 组 / 规则 / 集 | 性质 |
|:-:|:--|:--|:--|
| 1–5 | 43–2804 | 23 组 · 24 条 · 22 集（各块略有差异，是演进中间态）| 过渡态 |
| 6–7 | 2805–3294 | **25 组 · 27 条 · 25 集** | 当前版 |

第 7 块与 `routing.min.yaml` **逐字节相同**。

### 根因

**这是我此前用临时脚本重生成时误用追加模式（`"a"`）写坏的。**

```python
# 当时的写法（错）
open(fp, "a", encoding="utf-8").write(new_content)   # ← 追加，不是覆盖
# 每重生成一次，文件里就多一份完整配置
```

而**它躲过了所有门禁**，因为：

| 门禁 | 为什么没抓到 |
|:-----|:-------------|
| `check_structure.py` | `yaml.safe_load()` 遇到重复顶层键**静默取最后一份** ⇒ 读到的就是"正确"的第 7 块，判据全过 |
| `check_min_pair.py` | 同样拿解析结果（= 第 7 块）与 `.min` 对拍 ⇒ 通过 |
| `check_script_sync.py` | 同上 ⇒ 通过 |
| 肉眼 | 3294 行里 7 份几乎一样的内容，扫过去看不出 |

> 🔴 **PyYAML 的"重复键取最后一份"是这次静默通过的直接原因。**
> 本仓所有 clash 门禁都是 PyYAML 系，它们**共享同一个盲区**。

三个后果（当时记录在 `profile-anatomy.md` §18.3）：

1. **重复顶层键** —— mihomo 用 `gopkg.in/yaml.v3` 解析，**v3 默认开启唯一键检查**，
   有**拒绝加载整份配置**的风险（未经实测）。这正是「本地全绿 ≠ 线上能跑」的同类：
   门禁侧（PyYAML）不报错，客户端侧（yaml.v3）可能直接起不来。
2. **在文件里 `grep -c` 会得到 7 倍的数字。**
3. **改文件极易改错块** —— 改到第 1 块等于没改，而且改完门禁还是绿的。

### 修法

不是"下次记得用 `w`"，而是**把手工步骤固化成脚本，并让脚本自带两条硬保证**：

```python
# skill/scripts/clash/build_profiles.py

# ① 硬保证：一律覆盖写，绝不追加
open(fp, "w", encoding="utf-8", newline="\n").write(want)

# ② 硬保证：生成后立即自检（防纵向堆叠这类畸形）
raw = open(fp, encoding="utf-8").read()
keys = [l.split(":")[0] for l in raw.split("\n")
        if l and not l[0].isspace() and not l.startswith("#") and ":" in l]
dup = {k for k in keys if keys.count(k) > 1}
if dup:
    print("  NG %s 顶层键重复（疑似重复粘贴）：%s" % (full_rel, sorted(dup)))
    bad += 1
    continue
…
if len(parsed.get("proxy-groups") or []) != ng or len(parsed.get("rules") or []) != nrl:
    print("  NG %s 自检不一致（解析结果与脚本输出不符）" % full_rel)
```

| 保证 | 挡住什么 |
|:-----|:---------|
| ① 覆盖写（`"w"` + `newline="\n"`）| **病根本身** —— 追加模式再也不会被用上 |
| ② 自检：顶层键不得重复 | 畸形文件（不管它是怎么产生的）|
| ② 自检：解析后组数/规则数 == 脚本输出 | 生成物与真源不一致 |

实测（commit `7d7250c`）：**注入重复堆叠 → 自检立刻报错 → 跑一次即修复。**
修复后 `routing.yaml` 从 3294 行回到 **493 行**。

> 📌 **通用教训**：靠"我记得用覆盖模式"是不可靠的 —— 但它和"靠注释提醒同步两份拷贝"
> 是**同一类**错误（见 `surge/pitfalls.md` 坑 11）。
> 正确做法是**让正确的做法成为唯一可执行的路径**（脚本只提供 `w`），
> 并**给结果配一个自检**（就算有人绕过去写坏了，也会被立刻抓出）。

### 判据固化在哪

- **`skill/scripts/clash/build_profiles.py`** —— 覆盖写 + 自检两段（约 217–236 行）。
- **`skill/tests/verify_all.py`** 的 `('clash 静态 profile 新鲜度', [PY, 'skill/scripts/clash/build_profiles.py', '--check'], {})` —— 第 17 道门。
- 判负样例：`checker.md` §9.2 第 14 条（往真源追加一行 → `--check` 报「已过期」）。
  ⚠️ `build_profiles.py --check` 的判负样例在 `checker.md` §9.2 里**尚未单列**（表里第 14 条是 `build_rules.py`），待补。

---

## 3 · 门禁脚本引用未定义的 `diff`：只在判负路径上才执行的代码从未被执行过

### 现象

`check_script_sync.py` 在**真正要判负的那一次**不是"报出差异"，而是崩在
`NameError: name 'diff' is not defined`，输出只有一段 traceback。

### 根因

`diff()` **在本文件被引用但未定义、也未导入**
（`check_min_pair.py` 里有同名函数，但没有共享模块）：

```python
# line 130
if out.get("rules") != (st.get("rules") or []):
    errs.extend(diff(out.get("rules") or [], st.get("rules") or [], "rules"))   # ← diff 未定义
# line 161
    errs.extend(diff(norm_dns(...), norm_dns(...), "dns"))                      # ← 同上
```

行为矩阵：

| 情形 | 实际行为 |
|:-----|:---------|
| 脚本与静态一致（现役状态）| ✅ 两个 `if` 都为假 ⇒ **`diff` 从未被调用** ⇒ `OK`，exit 0 |
| 脚本 `rules` 漂移 | 💥 `NameError`，以退出码 1 结束 |
| 脚本 `dns` 漂移 | 💥 同上 |

**为什么它一直没被发现**：现役配置恒一致 ⇒ **`diff` 从未被执行过**。
这是一个**只在失败分支上才执行、而失败分支从未被触发**的代码路径 ——
静态检查（`python -m py_compile`、import、flake8）**全都看不出来**，
因为 Python 的名字解析发生在**运行时**。

> 🔴 更糟的是那个"碰巧"：退出码**碰巧也是 1**，所以 `verify_all.py` 仍会标红 ——
> **闸门不会假绿，但它给不出任何诊断信息**。没有「第几条规则不同」、
> 没有「哪个 dns 键不同」，只有 traceback。使用者拿到它什么也做不了，
> 只能人工 `diff` 脚本输出与静态 profile 的 `rules` / `dns` 两段。

### 修法

补上 `diff()` 的定义（递归比对，产出可定位的差异描述）：

```python
def diff(a, b, path=""):
    """递归比对两个对象，返回差异描述列表。

    ⚠️ 本函数此前在本文件**被引用但未定义也未导入**：现役配置恒一致时
    从未被调用，一旦真实漂移就会 NameError —— 退出码碰巧是 1 所以不会假绿，
    但**一条诊断都给不出**。故补上定义，并在末尾加自检。
    """
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:   out.append("%s.%s 仅静态版有" % (path, k))
            elif k not in b: out.append("%s.%s 仅脚本有" % (path, k))
            else:            out.extend(diff(a[k], b[k], "%s.%s" % (path, k)))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append("%s 长度不同: 脚本 %d vs 静态 %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff(x, y, "%s[%d]" % (path, i)))
    elif a != b:
        out.append("%s 不同: 脚本 %r vs 静态 %r" % (path, a, b))
    return out
```

差异描述**带下标**（`rules[19]`、`dns.prefer-h3`），这是判负后能定位的前提。

实测（commit `7d7250c`）：**注入漂移后可精确定位到 `rules[19]`**。

📌 **更通用的修法（本项目未采用，记录在此）**：把 `diff()` 提进
`skill/scripts/clash/_clash_common.py`，两个脚本共用 —— 否则它是
**同一判据的两份拷贝**，会重演「改了一个、另一个没改」的旧病。
（现状：`check_min_pair.py` 与 `check_script_sync.py` 各有一份 `diff`。）

### 判据固化在哪

- **`skill/tests/clash/check_script_sync.py`** 的 `diff()` 函数本体（含记录本坑的 docstring）。
- 判负样例：`checker.md` §9.2 第 13 条 —— 从 `my_clash_lazy.js` 删掉一条规则
  ⇒ exit 1，且（修好后）输出含 `rules[…] 长度不同` 之类的定位标记。

⚠️ **两处文档滞后（待确认，改动时请一并核对）**：

1. `checker.md` §6.2 仍把这条记为「⚠️ 已知挂账 … **修法（未做，待维护者决定）**」——
   commit `7d7250c` 已修，文档未同步。
2. 函数 docstring 写「并在末尾加自检」，但文件末尾只有 `if __name__ == "__main__": sys.exit(main())`，
   **未见自检代码**。即「判负样例」仍需人工跑，不是常驻保证。

---

## 4 · DNS 广告拦截：双条件缺一即失效，且不报错

### 现象

配好了 `nameserver-policy` 里的 `rcode://success`，广告**一个也没拦住**。
配置能加载、面板无告警、日志无错误、规则层那条 `RULE-SET,xxx,AD` 也还在 ——
**只是 DNS 层那半完全没工作。**

### 根因

mihomo 的双层广告拦截是**两个必要条件**，它们是同一件事的两半：

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

**缺 B 只留 A**：内核 `dns/middleware.go` 里 `withFakeIP` 中间件**先于** `withResolver`
返回 —— 对 A / AAAA 查询直接下发假 IP ⇒ **请求永远到不了 `nameserver-policy`**。
（社区有先例：[Discussion #668](https://github.com/MetaCubeX/mihomo/discussions/668)。）

**缺 A 只留 B**：跳过假 IP 后走真实解析 ⇒ 广告域名拿到真实 IP，DNS 层没有拦截。

⇒ **两条都要。** 还有**第三个条件**（顺序）：`nameserver-policy` 是**按顺序**匹配的，
一旦 `geosite:private,cn` 先命中，国内域名（含广告域）就被送到国内解析器拿真实 IP，
`rcode://success` 永不再看。

> 🔴 **这条坑的杀伤力在于它完全静默。** 没有报错、没有告警、没有日志 ——
> 只有"广告还在"。**凡是"缺一半等于没做"的结构，都必须机器判。**

### 修法

把四个条件写成判据（不是写成注释）：

| 条件 | 判据 |
|:-----|:-----|
| a) `nameserver-policy` 里有 `rule-set:<广告集>` → `rcode://success` | `ads_np` 空 ⇒ 报错 |
| b) **同一个**广告集在 `fake-ip-filter` 里也列了一遍 | `ads_ff` 空 ⇒ 报错 |
| c) 两处集合**必须相等** | `{…} != ff_sets` ⇒ 报错「广告集两处不一致」|
| d) 广告项排在 `private,cn` **之前** | `min(ads_idx) > min(cn_idx)` ⇒ 报错 |

⚠️ **判据 c 为什么是「相等」而不是「非空」**：只在一处列出 ⇒ (缺 b) 或 (缺 a)
**之一**成立，效果都是半截。**两处是同一件事的两半，缺一半等于没做。**

```python
ads_np = [k for k in npol if str(npol[k]).startswith("rcode://")]
ads_ff = [x for x in ffil if x.startswith("rule-set:")]
if not ads_np: errs.append("DNS 层广告拦截缺失：nameserver-policy 无 rcode://success")
if not ads_ff: errs.append("DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集")
else:
    np_sets = {k.replace("rule-set:", "") for k in ads_np}
    ff_sets = {x.replace("rule-set:", "") for x in ads_ff}
    if np_sets != ff_sets:
        errs.append("广告集两处不一致：policy=%s / fake-ip=%s" % (sorted(np_sets), sorted(ff_sets)))
```

> 💡 判据写成"把两处的集合取出来比相等"，就**顺手挡住了第四种错法**：
> 两处列了**不同的**集（比如 AWAvenue 和 Jinx 写反了）—— 那也是半截。

### 判据固化在哪

- **`skill/tests/clash/check_structure.py`** 的 ③（含 a/b/c/d 四条），对**四份 profile**
  （`lazy` / `lazy.min` / `routing` / `routing.min`）逐份生效。
- 判负样例：`checker.md` §9.2 第 **5 / 6 / 7 / 9** 条：

| # | 注入 | 期望定位标记 |
|:-:|:-----|:-------------|
| 5 | 删掉所有 `rcode://success` 项 | `DNS 层广告拦截缺失：nameserver-policy 无 rcode://success` |
| 6 | 从 `fake-ip-filter` 删掉所有 `rule-set:` 项 | `DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集` |
| 7 | 把 `rcode://` 几行挪到 `private,cn` 之后 | `广告 policy 排在 cn 之后` |
| 9 | 只加 `rcode://`，`fake-ip-filter` 里列**另一个**集 | `广告集两处不一致` ← **证明判据 c 是「相等」不是「非空」** |

- 文档：`profile-anatomy.md` §14（含 §14.4 两版本写法差异：`rule-set:private,cn` vs `geosite:private,cn`）。
- FAQ 入口：`profile-anatomy.md` 「Q：广告拦截加了清单，但没生效」→ 查三件事。

---

## 5 · IPv6 未关闭 → 出口 IP 与节点不符

### 现象

明明挂着节点，`whatismyip` 显示的出口 IP **不是节点的**；
或者同一站点时好时坏 —— 取决于该站点有没有 AAAA 记录。

### 根因

mihomo 的 IPv6 有**两个独立的开关**，管的是两件不同的事：

| 处 | 键 | 作用 |
|:-:|:--|:-----|
| ① | 顶层 `ipv6: false` | 内核**不处理 IPv6 流量本身** |
| ② | `dns.ipv6: false` | `AAAA` 查询由内核直接回**空应答**，不往外发 |

**只关一处会漏，而且两个方向漏的东西不一样**：

- **只关 ①**：DNS 仍在应答 `AAAA` ⇒ 应用拿到 IPv6 地址后尝试建连，
  行为取决于系统栈（可能失败、可能走本机真实 IPv6）。
- **只关 ②**：`AAAA` 不回了，但 **IPv6 通路还在** ⇒
  本机真实 IPv6 可能**绕过 TUN 直接出网** —— **站点测到的出口 IP 与节点不符**。

⇒ 两处都关，双栈站点一律回落 IPv4，封堵面与 Surge / Egern 两侧等效
（Surge 是 `ipv6` + `ipv6-vif`，Egern 只要 `ipv6`）。

> ⚠️ 这条在 `leak-localization.md` 里被单列为**面 ③′** —— mihomo 侧**特有**的一条泄露面，
> 它**不走 `:53`**，所以"我只堵了明文 DNS"的排查思路会漏掉它。

### 修法

两份 profile 都显式写死两处，并由判据守着：

```python
if c.get("ipv6") is not False:      errs.append("顶层 ipv6 未显式关闭")
if dns.get("ipv6") is not False:    errs.append("dns.ipv6 未显式关闭")
```

⚠️ **必须是 `is not False`，不能写成 `if not c.get("ipv6")`**。
差别很实在：

| 写法 | `ipv6: false` | `ipv6` 键缺失 | `ipv6: "false"`（字符串）| `ipv6: no` |
|:-----|:-------------:|:-------------:|:------------------------:|:----------:|
| `is not False` ✅ | 过 | **判负** | **判负** | **判负** |
| `not c.get("ipv6")` ❌ | 过 | 判负 | **通过（假绿）** | **通过（假绿）** |

> 📌 **判据要判"是不是那个布尔假值"，不要判"是不是 falsy"。**
> YAML 里 `"false"` 与 `no` 都是真值非空的字符串/真值，语义上不是"关闭"。
> 同理，**键缺失也必须判负** —— "没说"不等于"关了"。

### 判据固化在哪

- **`skill/tests/clash/check_structure.py`** 的 ④。
- 判负样例：`checker.md` §9.2 第 **8** 条（`false` → `true`，顶层与 `dns.ipv6` 各试一次）
  与第 **10** 条（**把 `ipv6` 键整个删掉 ⇒ 仍判负**，证明用的是 `is not False`）。
- 文档：`profile-anatomy.md` §4.2；`leak-localization.md` §6（面 ③′）。

---

## 6 · 改了脚本忘重生成静态 profile / `.min` → 两边漂移，都不报错

### 现象

改了 `override/my_clash.js` 里的规则，跑门禁**全绿**，但用户拿到的静态
`profiles/routing.yaml` **还是旧的**。反之亦然。两种形态的行为不一致 ——
用户遇到「照文档用脚本订阅，效果跟直接导入配置不一样」。

### 根因

本仓每份 profile 都有**两个交付形态**：

```
静态文件   clash/profiles/routing.yaml    —— 下载即用
覆写脚本   clash/override/my_clash.js     —— 挂到任意订阅上
```

它们是**同一套配置**的两种形态 —— 脚本的输出就应该是静态文件的样子。

而 `.min` 又是**第三/第四份**：`routing.min.yaml` 的定位是
「**同一份配置去掉注释**」，不是"裁剪配置"。

**漂移的根源是一个纯手工步骤**：改脚本 → （人记得）→ 重生成静态 → （人记得）→ 重生成 `.min`。
静态文件不会报错，脚本也不会报错 —— **两边都能正常跑，只能靠对拍发现。**

> 📌 `profile-anatomy.md` §18.1 把这条写成纪律：**一处改动要写（最多）四处** ——
> 静态 `.yaml` + `.min.yaml` + 覆写 `.js` + （若动规则集内容）`rules/*.list`。

### 修法

**把手工步骤固化成脚本，并把"是否最新"变成一道闸门**：

```bash
python skill/scripts/clash/build_profiles.py            # 重生成（覆盖写 + 自检）
python skill/scripts/clash/build_profiles.py --check    # CI 用：过期即判负
```

`--check` 的语义是**内容比对**而不是时间戳比对：把脚本输出渲染成目标文本，
与磁盘上的现有内容**逐字节比**，不同即判负。这是它比任何"记得跑"都可靠的原因。

两侧对拍则由另一个脚本守（`check_min_pair.py`）：用 YAML 解析两侧成 Python 对象后
**直接比对象** —— 注释、键顺序、缩进、引号风格都不影响判定，**只看配置本体**。

⚠️ `.min` 与完整版的漂移有一处**刻意的例外**：`dns.listen`。
`check_script_sync.py` 的 `SKIP_DNS_KEYS = {"listen"}` —— 脚本整体替换 `dns` 时
**不写**这个键（否则可能与客户端自身 DNS 端口冲突）。
懒人版有 `listen: 0.0.0.0:7874`，分流版不设。

⚠️ 另有一处**刻意的差异**必须打印但不判负：`Smart` 三档。
模板能用 `filter` 在**运行时**按倍率分档，脚本在订阅加载时执行一次、看不到 provider 节点名
⇒ 脚本侧只能是单组 fallback。这是**内核机制决定的，不是漂移**，故进 `EXPECTED_DIFF`：

```
~ 已知差异 Smart: 模板三档 fallback vs 脚本单组 fallback（机制差异，非漂移）
```

> 🔴 **别把 `EXPECTED_DIFF` / `TEMPLATE_ONLY_GROUPS` 当成"可以往里加东西的豁免清单"。**
> 它们的准入条件是「**机制不可能对齐**」。任何"写起来麻烦"的差异都应该改脚本，不是加白名单。

### 判据固化在哪

| 漂移方向 | 守门脚本 | 在 16/17 道里 |
|:---------|:---------|:-------------|
| 脚本 ↔ 静态 | `skill/tests/clash/check_script_sync.py` | ✅ 第 15 道 |
| 完整版 ↔ `.min` | `skill/tests/clash/check_min_pair.py` | ✅ 第 14 道 |
| 静态是否过期（脚本有更新未重生成）| `skill/scripts/clash/build_profiles.py --check` | ✅ 第 17 道 |
| `rules/*.yaml` 是否过期（真源 `.list` 有更新）| `skill/scripts/clash/build_rules.py --check` | ✅ 第 16 道 |

- 判负样例：`checker.md` §9.2 第 11 / 12 / 14 条。

⚠️ **判别力现状**：这四道门的判负样例都是**人工跑出来的**，不是常驻 CI 的保证（见坑 14）。

---

## 7 · Windows 中文环境 print 非 GBK 字符 → 退出码 1 被读成「判负」

### 现象

脚本在 Windows 中文控制台上崩在 `UnicodeEncodeError`，**以退出码 1 结束**。
汇总表把它标成 ❌「有判负」—— 看起来像是配置有问题。

**本次文档编写时就实测撞上了一次**（在同一个仓库、同一台机器上）：

```
$ python -c "print(open('...').read()[i:i+2500])"
UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 774
```

（⚠️ 那个字符是 `build_gates()` docstring 里的 ⚠️。**读本文档时它就在仓库里，一直都在。**）

### 根因

两层，缺一不可：

1. **中文 Windows 控制台默认 cp936（GBK）**。`print` 一个 emoji / `⇒` / `↔` / `⚠️`
   就会 `UnicodeEncodeError`。
2. **退出码 1 有两个含义**：「有判负」**和**「崩了」。
   本项目的退出码约定是 `0 = 通过 · 1 = 有判负 · 2 = 环境故障` ——
   **而崩溃不会给出 2，它给出 1。**

⇒ 于是「判据根本没跑」被读成「判据跑了并判负」。
**这是假绿的反面：假红。** 它比假绿隐蔽得多 —— 假绿让人安心，假红让人去改一个本来正确的东西。

> 🔴 最危险的一种形态：一个**判负样例**期望的退出码"恰恰也是 1"。
> 「如期判负」与「崩在别处」**只看退出码分不开**。

### 修法

三道防线，**互补、不可互相替代**：

**① 每个脚本在 import 时把 stdout/stderr 钉成 UTF-8**（运行时真相）：

```python
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
```

四个 clash 门禁 + `_clash_common.utf8_stdout()` 都是这一招。
⚠️ `errors="replace"` 是刻意的：宁可输出 `?` 也不要崩。

**② CI 的「Encoding gate (cp936)」**（在 Linux 上等价复现 Windows 的管道路径）：

```yaml
- name: Encoding gate (cp936)
  run: python skill/tests/verify_all.py
  env:
    PYTHONIOENCODING: cp936
```

⚠️ **前提是 `run_one()` 对 `PYTHONIOENCODING` 用 `setdefault`，不是硬赋值**：

```python
env.setdefault('PYTHONIOENCODING', 'utf-8')     # ✅ 父进程传下来的 cp936 会被原样继承
# env['PYTHONIOENCODING'] = 'utf-8'             # ❌ 会把 cp936 抹成 utf-8 ⇒ 编码门永远绿（空操作）
```

（这个错误写法在 2026-10-02 被实测推翻过 —— 它把一道门变成永久空转。）

**③ `check_portability.py` 的 E4**（静态判据，覆盖 CI 不跑的审计脚本）：
「脚本 print 非 GBK 字符者必有输出编码保护」。

| | 覆盖 | 假阳性 |
|:--|:-----|:-------|
| 编码门（运行时）| 只覆盖 `build_gates()` 跑到的脚本，且只覆盖**执行到的分支** | **零** |
| E4（静态）| 全覆盖（含 CI 不跑的审计脚本）| 有漏报也有假阳性 |

⚠️ E4 自己的两个已知边界（都是**宁严勿宽**的刻意保守）：

- 不要退回 `"reconfigure" not in src` 这类**子串判断** —— 光在注释里写一句
  `# 需要 reconfigure 保护` 就会被误判成「已有保护」。**假保护比漏报更坏。**
- `def setup(): sys.stdout.reconfigure(...)` **定义了却从未调用** ⇒ 判负（正确）；
  但保护被**包了两层以上**（`boot()` → `force_utf8_stdout()` → `reconfigure`）
  会被**误判为无保护**（真实运行不崩，E4 却判负）。修法：把保护写在模块级，
  或让**中间层**在模块级被调用。

### 判据固化在哪

- **每个 clash 脚本**顶部的 `reconfigure` 循环 + `skill/scripts/clash/_clash_common.py` 的 `utf8_stdout()`。
- **`.github/workflows/ci.yml`** 的 `Encoding gate (cp936)` step。
- **`skill/tests/check_portability.py`** 的 E4（含它自己的自检样例：只护 `stderr`、只写注释、
  只定义不调用 —— 三个都期望判负）。
- 判负样例纪律：`checker.md` §9.1 —— **判负断言是两条，不是一条**：退出码 == 1 **且**
  输出里出现那个注入的定位标记。后者正是为了把「判负」与「崩了」分开。

---

## 8 · 路径探测基于 `__file__` → 本地全绿，CI 上报「缺文件」

### 现象

Linux CI 上 clash 的两个门禁（`check_structure.py` / `check_script_sync.py`）
报「缺文件」，**本地全过**。

```
  NG 缺文件: override/my_clash.js 或 profiles/routing.yaml
```

### 根因

`_default_root()` 的 v1 **基于 `__file__` 向上推算**仓库根：

```python
# v1（错）
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, "..", "..", ".."))
```

而整合仓有两种布局：

```
整合仓 self-conf：配置在 <root>/clash/ 下     ← __file__ 要上推 3 层再进 clash/
单仓 Clash：      配置就在 <root> 下          ← __file__ 要上推 3 层
```

`__file__` 在**符号链接 / 不同调用方式**下会算错（实测 GitHub Actions 上的调用方式就踩了）。
算错之后，脚本在一个不含 `profiles/` 与 `override/` 的目录里找文件 ⇒ 「缺文件」。

> 🔴 **这类 bug 的本质是"环境相关的东西只有一种环境被测过"。**
> 本地永远是对的，因为它一直在同一个环境里跑。**CI 的价值就在于此** ——
> 它是唯一会去跑"另一种调用方式"的地方。

### 修法

**CWD 优先 + 逐级向上探测，以"特征目录"为准**（不是以"上推层数"为准）：

```python
def _default_root():
    """定位 clash 配置目录（含 profiles/ 与 override/）。

    探测顺序：当前工作目录 → 脚本自身位置。
    优先用 CWD 是因为 CI 从仓库根调用，而 __file__ 在符号链接 /
    不同调用方式下可能算错（实测 GitHub Actions 上 __file__ 探测失败）。
    """
    cands = []
    cwd = os.getcwd()
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

| 设计点 | 理由 |
|:-------|:-----|
| **CWD 优先** | CI 从仓库根调用，CWD 是**唯一可靠**的锚 |
| **以特征目录为准**（同时含 `profiles/` + `override/`）| 两种布局都支持，**不依赖"上推几层"这个魔法数** |
| 每层都试 `<dir>` 与 `<dir>/clash` | 覆盖"配置在子目录"与"配置在根"两种布局 |
| 兜底返回 CWD | 找不到就退回 CWD，**至少路径是确定的**（比返回一个不存在的目录好诊断）|

⚠️ 使用纪律：**从仓库根调用，不要从脚本所在目录调用。**

### 判据固化在哪

- **四个 clash 门禁各自的 `_default_root()`**：`check_structure.py` · `check_min_pair.py` ·
  `check_script_sync.py` · `check_remote_urls.py`（同一段逻辑，四处拷贝 —— 见下方挂账）。
- **CI**：`Gates (Surge + Egern + mihomo)` step 从仓库根跑 `verify_all.py` ⇒ 每 push 都在验证这条。
- 文档：`checker.md` §1 环境要求块；`profile-anatomy.md` §18.5；`branch.md` 的移植清单
  （「路径探测优先以仓库根 CWD 为锚点，再向上寻找内核特征目录；不要只按 `__file__` 固定上推层数」）。
- commit：`d2b3caa fix: clash 门禁路径探测改为 CWD 优先（CI 暴露）`。

⚠️ **挂账**：这四份 `_default_root()` 是**同一判据的四份拷贝**，靠"复制粘贴"保持一致
（正是 `surge/pitfalls.md` 坑 11 的形态）。修法是提进 `_clash_common.py`，**目前未做**。

---

## 9 · 复制文件丢 mtime → V7「一天一版」误判成当天升了 21 个版本

### 现象

V7「一天一版」判据报：某一天升了 **21 个版本**。

```
V7 routing 一天一版  ❌ 2026-10-07 有 21 个版本（v1.0→v1.1→…→v2.0）
```

而实际上那是**几十个历史版本的归档文件**，跨了好几个月。

### 根因

**版本诞生日期的来源有两个**（由 `release_publish.build_days()` 现算）：

| 对象 | 日期来源 |
|:-----|:---------|
| **现役版** | 版本号首现日 `number_birth`（git 提交历史）|
| **归档版**（`config_old/`）| 快照 blob 诞生日 `version_date`（git 历史 / **文件 mtime**）|

本仓的 git 历史从整合完成起算 —— 于是归档文件的
git 日期查不到，判据退化到用 **mtime**。

而 `cp`（不带 `-p`）**不保留 mtime**：

```
复制前的归档文件：  v1.0 (09-24) · v1.1 (09-26) · v1.2 (09-27) … v2.0 (10-04)
cp 之后的归档文件： v1.0 (10-07) · v1.1 (10-07) · v1.2 (10-07) … v2.0 (10-07)
                                    ↑ 全部退化成复制当天
⇒ V7 看到「10-07 这一天有 21 个版本」
```

> 🔴 **这是"判据正确、输入失真"的经典形态。**
> 判据没有写错，是**喂给它的日期是假的**。`ops.md` §6.8 把它写成通用姿势：
> **断言报红时，先问「它依赖的输入是否齐全」（历史深度 / 网络 / 凭据 / 前置文件），
> 再问「是不是真的不过」。**

⚠️ **反向也成立**：不得因为"可能是前置问题"就把红当噪声放过。
判据与 CI 结论冲突时（CI 绿、本地红），**先查两边跑法差异**（历史深度、工作目录、环境变量）。

### 修法

两件事一起做（commit `3006cf8`）：

1. **`cp -p` 重拷 `config_old/`** —— 保留 mtime，让日期分组至少还能用文件系统时间重建。
   （这是**减缓**，不是根治：本仓的 git 历史本就从整合完成起算。）
2. **`SKIP_V7=1` 开关** —— 承认「本就不继承 git 历史」这个局限，但
   **输出必须写明"未验证"，不能冒充通过**：

```python
if _os.environ.get("SKIP_V7") == "1":
    for fam in ("routing", "lazy"):
        out.append(("V7 %s 一天一版" % fam, True,
                    "已跳过（SKIP_V7=1）：日期分组不成立 "
                    "⇒ 未验证，不是通过"))
    return out
```

> 🔴 **豁免 ≠ 通过。** 汇总表上它是 ✅ 标记（退出码 0），但**文字明确声明了不验证**。
> **引用这道门的结果时，必须连同这句声明一起引用。**

配套：CI 里仍 `fetch-depth: 0` 保留完整历史 —— 不是给 V7 用，是给**其它归档判据**（V3–V6）留底。

📌 **豁免的三条纪律**（`checker.md` §10.3）：

1. **豁免必须点名**，不冒充通过 —— 输出里要能读出「未验证」。
2. **豁免要写理由**，理由要能被证伪（"日期分组不成立"是可验证的事实，不是"太麻烦"）。
3. **豁免项要么进 `build_gates()` 带 SKIP 标记、要么显式注释掉**。

### 判据固化在哪

- **`skill/tests/check_min_pair.py`**（跨内核版）的 `_cadence()` 与 `CADENCE_FROM`（2026-10-04）。
- **`skill/tests/verify_all.py`** 的 `_skip_v7 = {'SKIP_V7': '1'}` 传给 `('min-pair 一致', …)`。
- 文档：`checker.md` §10.1；`boundaries.md`（「一天一版」只从 2026-10-04 起算，历史不回改不追溯）。
- commit：`3006cf8`。

⚠️ 注意区分：**clash 侧的 `skill/tests/clash/check_min_pair.py` 不含 V7**（它没有
`SKIP_V7` 分支，只做完整版 ↔ `.min` 的对象对拍）。V7 挂在**跨内核那道**上。

---

## 10 · 两版 `AD` 组口径不同被套错

### 现象

两版都叫 `AD`、都指向两条广告清单、规则行也长得一样 —— 但**成员表不一样**：

```yaml
# clash/profiles/routing.yaml（分流版）
- name: AD
  type: select
  proxies:
    - REJECT
    - DIRECT          # ← 可以手动放行

# clash/profiles/lazy.yaml（懒人版）
- name: AD
  type: select
  proxies:
    - REJECT          # ← 单成员，没有放行的口子
```

把分流版的写法套到懒人版上（或反过来），**配置照样能加载、门禁照样全绿** ——
只是懒人版从此多了一个"广告放行"开关。

### 根因

这是**刻意的差异，不是漂移**。出处写在代码注释里：

```javascript
// clash/override/my_clash.js（分流版）
{
  name: "AD",
  type: "select",
  // 对齐 SC 的 AD：REJECT / DIRECT 二选一（不设 PASS ——
  // PASS 语义为「绕过代理直连」，与二选一的拦截口径不符，易误操作）
  proxies: ["REJECT", "DIRECT"],
}

// clash/override/my_clash_lazy.js（懒人版）
{
  name: "AD",
  type: "select",
  // 单成员 REJECT —— 与姊妹仓懒人版同口径（该仓 893b406 有意收敛）。
  // 分流版脚本才是 REJECT / DIRECT 二选一。
  proxies: ["REJECT"],
}
```

两个产品的定位不同：

| 版本 | 组数 | `AD` 口径 | 理由 |
|:-----|:----:|:----------|:-----|
| 分流版 `routing` | 25 | `REJECT` / `DIRECT` | 面向会调配置的人，需要手动放行的口子 |
| 懒人版 `lazy` | 3（`Proxy` / `AI` / `AD`）| 单成员 `REJECT` | 「不留放行的口子」—— 目标用户不需要、也不该有这个开关 |

⚠️ 顺带记一条：`AD` **不设 `PASS`**。`PASS` 的语义是「绕过代理直连」，
与"拦截与否"的二选一口径不符，容易误操作 —— 这是**语义层面**的选择，不是随手写的。

**为什么机器抓不到**：

| 门禁 | 能抓到吗 | 为什么 |
|:-----|:--------:|:-------|
| `check_structure.py` ①（悬空引用）| ❌ | `REJECT` / `DIRECT` 都在 `BUILTIN` 里，两个成员表都合法 |
| `check_script_sync.py`（脚本↔静态）| ✅（但只对**同一版内部**）| 它会逐位比子节点 ⇒ 脚本与静态之间不会漂。**但两版之间的口径差它不管** |
| 任何其它门 | ❌ | 没有一条判据表达「懒人版的 AD 必须只有一个成员」 |

### 修法

现状：靠**注释 + 文档**（`my_clash_lazy.js:90-91` 的注释、`profile-anatomy.md` §8.2 的表格）。
这是**本仓目前唯一一条"有意差异"没有机器判据的**。

📌 若要补判据，正确的写法是**按版本分表断言**（不是"AD 必须有几个成员"这种一刀切）：

```python
# 示意，未实现
AD_CALIBER = {
    "routing": {"REJECT", "DIRECT"},   # 可放行
    "lazy":    {"REJECT"},             # 单成员，不留口子
}
```

⚠️ 且必须**按版本名取口径**，不能写成"AD 必须有 ≥1 个成员" —— 那等于没判。
⚠️ 更不要一刀切写成"AD 必须含 DIRECT" —— 那会要求懒人版改名成分流版
（同 `surge/pitfalls.md` 坑 10 的形态：不变量一刀切套到另一种形态上）。

> 💡 **更优先的方案是消灭分叉本身**：若将来两版合并成"带注释 / 纯配置"两种形态
> （而不是两种**配置**），这条判据就自然对所有形态成立，不需要版本分表。

### 判据固化在哪

- ⚠️ **无机器判据（挂账）。** 目前只有：
  - `clash/override/my_clash_lazy.js:90-91` 的注释（含姊妹仓 commit `893b406` 出处）；
  - `skill/reference/clash/profile-anatomy.md` §8.2 的「为什么这么写」表格与 §14.3；
  - `check_script_sync.py` **间接**守住「同一版内脚本↔静态不漂移」（`EXPECTED_DIFF` 不含 `AD`，
    所以 `AD` 的成员表是**逐位比对**的 —— 脚本改了静态没改会立刻红）。

---

## 11 · 跨仓引用 → 整合仓不自洽（2511 处）

### 现象

整合"完成"了：文件都搬进了新仓，门禁全绿，配置能加载。
但**里面的 URL 还指着别的仓库** —— 共 **2511 处**：

| 类型 | 数量 | 表面症状 | 实际后果 |
|:-----|-----:|:---------|:---------|
| 图标引用 | **2311** | 外部仓库仍在线时一切正常 | 外部仓库改名 / 删除后，大量面板图标同时失效 |
| 规则集引用 | **200** | profile 仍能加载 | 远程集拉取失败后可能静默变空，分流与广告拦截退化 |

### 根因

**"复制文件"不等于"整合仓库"。** 文件搬过来了，文件里的 URL 没有跟着改。

这类缺陷的危险在于它的**三重静默**：

1. **语法检查通过** —— YAML 合法、JSON 合法。
2. **客户端导入成功** —— URL 是对的，只是指向别人家。
3. **本地缓存继续生效** —— 图标已经下过一次了，短期内看不出问题。

⇒ **只有把外部仓库看作"随时会消失"，才能验证自洽性是否真的成立。**

> 📌 它的失效模式和坑 1（死链）**是同一种**：静默降级。
> 区别只在于触发者 —— 坑 1 是上游规则集改名，本坑是被引用的外部仓库改名。
> **两者都只能靠主动扫描发现。**

（实测：本仓 `icons/` 38 个图标中 34 个同名文件整合时**内容字节完全一致**，零冲突 ——
所以这件事做起来不痛苦，痛苦的是**没人去做**。现役 `routing.yaml` 里的图标 URL
已全部指向 `raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/`。）

### 修法

```python
# skill/tests/check_selfcontained.py
FORBIDDEN_REPOS = ("Self-Configuration", "RiverFlowsInUUU/Clash")
COMMENT_PREFIX = ("#", "//", ";")          # 纯注释行跳过
SKIP_DIRS = {".git", "__pycache__", "icons", "config_old"}
EXTS = (".yaml", ".conf", ".js", ".list", ".txt", ".json", ".yml")
```

| 设计点 | 理由 |
|:-------|:-----|
| **跳过纯注释行** | 注释里提及来源是**记录**，不是运行时引用 —— 不跳会把说明文字误判成依赖 |
| **`SKIP_DIRS` 含 `icons` / `config_old`** | `icons/` 是**资源本身**（不是引用）；`config_old/` 是历史归档，改它没有意义 |
| **上游第三方放行** | MetaCubeX / blackmatrix7 / Jinx / TG-Twilight 是**登记过的第三方**，本就不属于"本仓应自持"的部分 |
| 按**仓库名**识别 | 简单、可审计。⚠️ 代价：**新增外部仓库 / 镜像域名 / 新文件后缀时必须同步扩判据** |

⚠️ 边界要写清：**它不是通用的"零外链证明器"**，是按仓库名识别已知外部仓库的专项检查；
纯注释、Markdown（`.md`）、以及 `SKIP_DIRS` 里的目录**不在当前扫描面**。

### 判据固化在哪

- **`skill/tests/check_selfcontained.py`**（手动跑：`python skill/tests/check_selfcontained.py .`）。
- 文档：`public-repo.md` §4（含 2511 处的分解表）；`branch.md` 的移植清单（「自洽」一行）。
- 判负样例：`checker.md` §9.2 —— 任意**非注释行**出现
  `https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/...` ⇒ `外部依赖 N 处` + exit 1。

⚠️ **挂账**：它**不进 16（现 17）道**，理由是"整合期的一次性检查，通过后不再变化"。
这个理由**可被证伪** —— 一旦有人新增了一个指向外部仓库的图标或规则集，它就不会再是"已通过"状态。
**建议**：至少把它挂到每周 cron 那个 job 上（与 `check_remote_urls.py` 同批），成本几乎为零。

---

## 12 · 靠「高熵」判定凭据 → 漏掉含 `@` 的密码

### 现象

配置里写了一个真实密码 `MyRealP@ssw0rd123`，secrets 扫描**没报**。

### 根因

v1 的判据是「高熵串」：

```python
# 高熵判定：混合大小写+数字且长度够，或全是长 hex
HIGH_ENTROPY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z0-9+/=_\-]{16,}$")
```

`MyRealP@ssw0rd123` 的问题：

```
字符类 [A-Za-z0-9+/=_\-] 里面没有 @
                              ↑
⇒ 整个正则失配 ⇒ 判据说"这不是凭据"
```

**真实密码恰恰经常带 `@` / `!` / 空格。** 用"看起来像随机串"去判"是不是凭据"，
等于**把最常见的一类真实密码排除在扫描之外**。

> 🔴 **方向性错误**：高熵判据的隐含假设是"凭据长得很随机"。
> 这个假设对 **API key** 成立，对**用户自己设的密码**完全不成立 ——
> 而后者才是配置里最常见的东西（`password:` / `auth:` 字段）。

⚠️ **附带发现（实测）**：这个 `HIGH_ENTROPY` 常量在
`skill/tests/clash/check_secrets.py` 里**只出现 1 次 —— 就是它的定义处**，
**从未被使用**。即它是一个**死常量**：既没起到作用，又让"我们有高熵判定"
这个错觉留在代码里。**死判据比没有判据更坏** —— 它会让人以为这一项被守住了。

### 修法

**换成占位白名单制**：不在白名单里的可疑物即报警。

```python
# 凭据字段：值**不是占位符就报警**。
# 不用"高熵"判定 —— 本仓是模板仓，配置里根本不该出现非占位的凭据；
# 靠熵判定会漏掉含 @/!/空格 的真实密码（实测 MyRealP@ssw0rd123 就漏过）。
for m in TOKEN_RE.finditer(txt):
    v = m.group(1)
    if is_placeholder(v):
        continue
    if v.lower() in ("true", "false", "null", "none", "direct", "reject"):
        continue
    # 代码里的常量/变量名（如 ALL_KEY = HAS_PROVIDERS）不含数字 ——
    # 真实凭据几乎必含数字，以此区分。
    if not any(ch.isdigit() for ch in v):
        continue
    hits.append((rel, "非占位凭据: %s" % m.group(0)[:60]))
```

| 设计点 | 理由 |
|:-------|:-----|
| **默认判负**（不在白名单即报警）| 本仓是**公开模板仓**，配置里根本不该出现非占位凭据。**默认放行的判据在这里是不适用的。** |
| `PLACEHOLDER_VALUES`（`REPLACE_WITH_YOUR_PASSWORD` / `YOUR_TOKEN` / `changeme` / `example` …）| 明确列出哪些算"假值" |
| 放过 `true/false/null/direct/reject` | 布尔与内置策略名不是凭据 |
| **"必须含数字"启发式** | 区分代码常量（`ALL_KEY = HAS_PROVIDERS`）与真实凭据（几乎必含数字）|

> 📌 **判据的方向要跟着"被审对象的性质"走。**
> 通用 secrets 扫描器必须靠熵（它面对的是"海量未知文本"）；
> **模板仓**面对的是"我自己的配置，我知道它应该长什么样" ⇒ **白名单制是更强的判据**。

### 判据固化在哪

- **`skill/tests/clash/check_secrets.py`** 的 `TOKEN_RE` + `is_placeholder()` + `PLACEHOLDER_VALUES`
  （含记录 `MyRealP@ssw0rd123` 实测的注释）。
- 判负样例：`checker.md` §9.2 —— 任意 `.yaml` 里写 `password: MyRealP…` ⇒ `非占位凭据:`。
- 文档：`public-repo.md` §5.1「两道 secrets 扫描不要混为一个」。

⚠️ **两处挂账（待确认）**：

1. `HIGH_ENTROPY` 常量**仍在文件里、仍未被使用** —— 建议删除或接上，别留着误导。
2. **`skill/tests/clash/check_secrets.py` 不在 `verify_all.build_gates()` 里**
   （17 道里只有**跨内核**的 `skill/tests/check_secrets.py`）。
   ⇒ Clash 侧的凭据扫描**目前靠人记得跑**。

---

## 13 · `198.18.0.1`（mihomo fake-ip 段）被 Surge 侧扫描判成真实 IP

### 现象

整合后，跨内核的 secrets 扫描报：

```
NG clash/profiles/routing.yaml —— 出现非占位 IPv4 `198.18.0.1`
```

而 `198.18.0.1` **不是节点地址**。

### 根因

它是 **mihomo 的 fake-ip 段**：

```yaml
dns:
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16        # RFC 6815 保留段（Benchmarking）
```

| 内核 | 认不认识 `198.18.x` |
|:-----|:-------------------|
| mihomo | ✅ 这是**自己的** fake-ip 段，见到它说明查询被内核接住了 |
| Surge / Egern | ❌ 它们的词汇表里没有这个概念 ⇒ 按"非常见 IPv4"处理 |

⇒ **这是"各内核的常识不同"**。`198.18.0.1` 在 mihomo 侧是**合法保留段**，
在 Surge/Egern 侧的判据里是"一个不在白名单里的 IPv4"。

> ⚠️ 反过来看，**这个误报是"好事"** —— 判据在按它自己的标准正确地工作。
> 问题不在判据，在于**整合两个内核时，一方的合法值在另一方眼里是异常值**。
> 这类冲突**只能靠整合者识别出来**，任何单侧判据都发现不了。

📌 同一段地址还有**第二个语义**（`leak-localization.md` §1）：
做泄露测试时检测到 `198.18.x.x` **不是泄露** —— 它恰恰说明查询
**被 mihomo 接住了**、只是没做真实解析。**别把它当成新发现的泄露面去"修"。**

### 修法

**加窄白名单，不是关闭 IPv4 扫描**（`branch.md` 明确写了这条原则）：

```python
# skill/tests/check_secrets.py（跨内核版）
# RFC 5737 文档段 + mihomo 的 fake-ip 保留段（198.18.0.0/15，RFC 6815）。
# 后者是整合 mihomo 内核后新增的：fake-ip-range 默认 198.18.0.1/16，
DOC_NETS = ("192.0.2.", "198.51.100.", "203.0.113.", "198.18.")
```

```python
# skill/tests/clash/check_secrets.py（Clash 版）
ALLOWED_IPS = {…, "198.18.0.1", …}
…
if ip.startswith("198.18."):
    continue
```

| 原则 | 说明 |
|:-----|:-----|
| **窄** | 加的是 `198.18.` 这个**前缀**（RFC 6815 的保留段），不是"放行所有私有地址" |
| **有规范依据** | 引 RFC 6815 / RFC 5737，不写"不知道为什么但这几个要放行" |
| **不关扫描** | 关掉 IPv4 扫描会**同时丢掉真正的节点地址检测** —— 那是本扫描的主要职责 |

### 判据固化在哪

- **`skill/tests/check_secrets.py`（跨内核）的 `DOC_NETS`** —— 含 `198.18.`。
- **`skill/tests/clash/check_secrets.py`（Clash 版）的 `ALLOWED_IPS` + `ip.startswith("198.18.")`**。
- 文档：`profile-anatomy.md` §5.2 与 FAQ「Q：`198.18.0.1` 为什么不是真实 IP？」；
  `leak-localization.md` §1（不是泄露）；`branch.md` 移植清单（"另外要检查新内核的保留地址常识"）。

⚠️ **同一判据两份拷贝 —— 改必须两处一起改。**
两个 `check_secrets.py`（跨内核版 / Clash 版）**各自维护了一份 IP 白名单**，
且写法不同（一个是 `DOC_NETS` 元组 + `startswith`，一个是 `ALLOWED_IPS` 集合 + 单独 `startswith`）。
这正是 `surge/pitfalls.md` 坑 11 的形态。**只改一个，两个脚本会给出相反结论 —— 比没有脚本更糟。**

---

## 14 · 只测「好配置通过」证明不了判别力 —— 必须注入坏样例

### 现象

门禁全绿，于是认为"配置没问题"。

### 根因

**一个恒返回 0 的脚本也能让现役配置全绿。**

```
现役配置 → check_structure.py → exit 0  ✅
        ↑
        这条路径对它自己是不是在工作，一个字的信息都没提供。
```

本仓 17 道门**全部**是"跑现役配置、期望 0"。**没有任何一道常驻 CI 的闸门会验证
「判据自己还判不判负」。** ⇒ 一旦出现「门禁逻辑改坏、判据不再判负、现役配置仍全绿」，
**本仓没有闸门会发现。**

（坑 3 就是这件事的实证：`diff` 未定义这件事，只有**注入漂移**才暴露得出来。
静态检查、import、跑绿样例 —— 全都看不出来。）

### 修法

本仓对判别力的要求是**两侧合计**：既放行现役配置、又拦住故意损坏的样例。
且判负侧的断言是**两条，不是一条**：

1. **退出码 == 1**；
2. **输出里出现那个故意注入的定位标记**（如组名 / 键名）。

> ⚠️ **第 2 条不是多余**：审计器**崩了**（emoji 触发 `UnicodeEncodeError`，见坑 7）
> 同样以退出码 1 结束 —— 而判负样例期望的**恰恰也是 1**。
> 两者的区别**只能在输出里看**。所以判负样例必须「能点名到这一条」。

统一前置（**在仓库外做**，避免污染工作副本）：

```bash
SB=/tmp/clash-gate-probe          # Windows 用 C:/Users/<你>/AppData/Local/Temp/...
mkdir -p "$SB/profiles" "$SB/override"
cp clash/profiles/*.yaml "$SB/profiles/"
cp clash/override/*.js   "$SB/override/"
# 先确认基线是绿的（否则后面的判负不可信）
python skill/tests/clash/check_structure.py   "$SB"   # 期望 0
python skill/tests/clash/check_min_pair.py    "$SB"   # 期望 0
python skill/tests/clash/check_script_sync.py "$SB"   # 期望 0
```

> ⚠️ **基线必须先绿。** 基线红时注入坏样例，判负可能来自原有缺陷 ⇒ 判别力结论无效。

`checker.md` §9.2 登记的注入样例（**15 个，逐个已实测**）：

| # | 门 | 注入 | 定位标记 |
|:-:|:--|:-----|:---------|
| 1–4 | `check_structure` | 悬空引用 / 未定义规则集 / 不存在的组 / `MATCH` 指向不存在的组 | `悬空引用: 组 Proxy -> Nope-Group` … |
| 5–7 | `check_structure` | 删 `rcode://` / 删 `rule-set:` / 挪到 `cn` 之后 | 见坑 4 |
| 8 | `check_structure` | `ipv6: false` → `true` | `顶层 ipv6 未显式关闭` / `dns.ipv6 未显式关闭` |
| 9 | `check_structure` | 两处列**不同的**集 | `广告集两处不一致` ← 证明是「相等」不是「非空」 |
| 10 | `check_structure` | **删掉 `ipv6` 键** | 仍判负 ← 证明 `is not False`（缺失 ≠ 通过）|
| 11–12 | `check_min_pair` | `.min` 插一条规则 / 只改 `dns.prefer-h3` | `rules 长度不同: 11 vs 12` / `.dns.prefer-h3 值不同` |
| 13 | `check_script_sync` | 从脚本删一条 `RULE-SET,Jinx-CN,DIRECT` | `rules[…]` 定位标记 |
| 14 | `build_rules --check` | 往 `rules/AI.list` 追加一行 | `NG rules/AI_Domains.yaml 已过期` |
| 15 | `check_remote_urls` | URL 改成 `mihomo-white-guard.yaml`（**当年真实死链**）| `死链 N 个` |

⚠️ 第 14 条做之前**先备份真源**（`cp rules/AI.list $SB/AI.list.bak`），做完立刻还原，
并跑一次 `git diff rules/` 确认为空。**别让探针污染真源。**

📌 **9 与 10 这两条"边界样例"尤其值得做** —— 它们证明的是**判据没写反**
（是"相等"不是"非空"；是 `is not False` 不是 falsy）。**只测"明显坏了"证明不了判据的方向。**

### 判别力回归的现状（诚实口径）

| 门禁 | 判负样例已实测 | 有自动化回归 |
|:-----|:--------------|:------------|
| `check_structure.py` | ✅ 10 个，逐个 exit 1 + 定位标记 | ❌ 无（人工跑）|
| `check_min_pair.py` | ✅ 2 个 | ❌ 无 |
| `check_script_sync.py` | ⚠️ 1 个，能判负但诊断曾缺失 | ❌ 无 |
| `build_rules.py --check` | ✅ 1 个 | ❌ 无 |
| `check_remote_urls.py` | ⚠️ 联网依赖，未逐个固定 | ❌ 无 |
| **`check_region_filters.py`（跨内核）** | ✅ | ✅ **有** —— 唯一定期跑判负 fixture 的闸门 |

> 📌 跨内核的 `check_region_filters.py` 是**唯一**把「判负 fixture」做进总入口的闸门，
> 且它对每个判负用例断言**退出码 + 输出标记**两条。
> **mihomo 侧还没有对应的自动化回归** —— 上表前五行的"已实测"是文档编写时
> **人工跑出来的**，不是常驻 CI 的保证。
>
> **这是已知挂账**：mihomo 侧门禁的判别力目前靠"人记得跑"，不是靠机器守住。

### 判据固化在哪

- **`skill/reference/clash/checker.md` §9**（整节：为什么 / 每个门的注入手法 / 现状表）。
- **跨内核参考实现**：`skill/tests/check_region_filters.py` —— 它给每个判负用例
  断言「退出码 + 输出标记」两条，是 mihomo 侧要照抄的样板。
- `surge/pitfalls.md` 坑 16 —— 同源纪律（「给这份拷贝配一个比对器，并给比对器配一个判负样本」）。

---

## 15 · CRLF 判负（行尾不一致）

### 现象

同一个 commit，在 Windows 上检出是 CRLF，在 Linux / macOS 上是 LF。
于是"线上线下逐字一致"在**字节层面无法成立** —— 按 `\n` 写的正则在 CRLF 工作区上失配。

本项目真实踩过一次：**剥 YAML 头的正则按 LF 写，CRLF 工作区上失配 ⇒
源头部整段漏进正文。**

### 根因

**Windows 版 Git 安装器会把 `core.autocrlf=true` 写到系统级配置**
（`git config --system core.autocrlf` 可查）。它让 checkout 时把 LF 换成 CRLF
⇒ 换一台机器，磁盘内容就变了。

这是**环境差异**，不是配置差异 —— 靠"大家统一改一下自己机器的 git 配置"是不可靠的
（每个人都得知道这件事，且每个人都会忘）。

### 修法

把规矩**写进仓**，让每台机器自动生效：

```gitattributes
# .gitattributes（沿用 SC 原文件）
* text=auto eol=lf

# 二进制资产：禁止任何换行改写
*.png   binary
*.mmdb  binary
*.p12   binary
…

# 明确列出常见文本类型，避免 `text=auto` 因内容启发式误判成二进制
*.conf  text eol=lf
*.yaml  text eol=lf
*.yml   text eol=lf
*.list  text eol=lf
*.py    text eol=lf
*.js    text eol=lf
…
```

| 设计点 | 理由 |
|:-------|:-----|
| `eol=lf` **优先级高于** `core.autocrlf` | 写进仓就等于每台机器自动生效，**不需要任何人去改自己的 git 配置** |
| 显式列出文本类型 | 避免 `text=auto` 因内容启发式把某些文件误判成二进制 |
| 二进制资产标 `binary` | 禁止任何换行改写（`.p12` / `.pem` / `.mmdb` 改一个字节就废了）|

配套：整合时把 Clash 侧 3 个 CRLF 文件（verification.md / ruleset-sources.md / `lazy.yaml`）转成 LF。

### 判据固化在哪

- **`.gitattributes`**（沿用 SC 原文件，含逐条理由注释）。
- 检测：跨内核的 `skill/tests/check_portability.py`（LF/CRLF 属它的检查面）。
- commit：`3006cf8`（补 `.gitattributes` + 3 个 Clash 文件 CRLF → LF）。
- 纪律：**新增文件类型时若它必须保持原始字节（新的二进制资产），在 `.gitattributes` 下面加一行 `binary`。**

---

## 附 · 三条横向规律

把 15 条按**失效模式**归类，比按编号记更有用：

| 模式 | 涉及条目 | 共同点 |
|:-----|:---------|:-------|
| **静默失效**（不报错，只是功能没了）| 1 · 2 · 4 · 6 · 11 | 客户端能加载、门禁全绿、用户不报障。**只能靠主动探测 / 对拍 / 双条件判据发现。** |
| **判据自己坏了但看起来在跑** | 3 · 12 · 14 | 只在**失败分支**上执行的代码从未被执行；死常量；只测绿样例。**共同修法：注入坏样例。** |
| **本地全绿 ≠ 线上能跑** | 7 · 8 · 9 · 15 · 2 | 环境相关的东西（编码 / 路径 / mtime / 行尾 / 解析器实现）**只有一种环境被测过**。**共同修法：让 CI 跑一遍。** |

> ⚠️ 三类里最该警惕的是**第二类**。第一类和第三类至少还有"某个地方会红"的可能，
> 第二类是**连红都不会红** —— 它安静地躺在那里，直到某天真的需要它判负。

### 相关

[`checker.md`](checker.md)（判据与命令 · 判据演进史）·
[`profile-anatomy.md`](profile-anatomy.md)（配置结构 · §18 维护者须知）·
[`leak-localization.md`](leak-localization.md)（泄露定位 · 面 ③′ IPv6）·
[`public-repo.md`](public-repo.md)（公开仓纪律 · 2511 处事故）·
[`branch.md`](branch.md)（移植新内核的清单）·
[`../shared/cross-kernel-diff.md`](../shared/cross-kernel-diff.md)（同名概念的三内核落点）·
[`../../SKILL.md`](../../SKILL.md)（§7 踩过的坑 · §8 红线）
