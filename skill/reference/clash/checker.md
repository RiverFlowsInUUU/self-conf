# 核对器 · 命令与判据

> **何时读**：跑 mihomo 侧门禁前（环境要求 / 命令）、门禁判负要修时（逐条判据）、
> 或**要改判据时**（判据演进史与已知挂账）。
>
> 本仓立场（与姊妹仓一致）：**审计通过 ≠ 配置可用**。详见 §9。

## 0 · 目录

| # | 节 | # | 节 |
|:-:|:---|:-:|:---|
| 1 | 环境要求 | 8 | 生成物新鲜度（`build_rules.py`） |
| 2 | 命令 | 9 | 判别力：怎么证明门禁真的会判负 |
| 3 | 退出码约定 | 10 | 已知豁免项（豁免 ≠ 通过） |
| 4 | 结构判据（`clash/check_structure.py`） | 11 | 47 道总览表 |
| 5 | 两形态对拍（`clash/check_min_pair.py`） | 12 | CI 怎么跑 |
| 6 | 脚本 ↔ 静态对拍（`clash/check_script_sync.py`） | 13 | 判据演进史 |
| 7 | 远程集可达性（`clash/check_remote_urls.py`） | 14 | 全绿 ≠ 可用 · FAQ · 维护者须知 |

---

## 1 · 环境要求

| 项 | 要求 |
|:---|:-----|
| Python | 3.8+，**仅标准库 + PyYAML** |
| Node.js | **仅 `check_script_sync.py` 与 `check_remote_urls.py` 需要**（要执行 `override/*.js`）。`_clash_common.find_node()` 先 `shutil.which("node")`，再探测 `C:/Program Files/nodejs/node.exe` |
| curl | `check_remote_urls.py` 需要（HEAD / GET 探测） |
| 网络 | 只有 `check_remote_urls.py` 需要；其余 mihomo 门禁全离线 |
| 输出编码 | 无需设置 —— 每个脚本 import 时把 stdout/stderr 钉成 UTF-8（Windows 默认 cp936，emoji 会崩成**退出码 1**，而 1 恰是判负码）|

⚠️ **Windows 上 `subprocess` 不继承 Git Bash 扩展的 PATH**，直接 `subprocess.run(["node", ...])` 会 `WinError 2`。
这是 `_clash_common.find_node()` 存在的唯一理由 —— 别"简化"掉它。

⚠️ **工作目录（CWD）优先**。所有 clash 门禁的 `_default_root()` 都是同一段逻辑：

```python
def _default_root():
    """定位 clash 配置目录（含 profiles/ 与 override/）。

    两种布局都支持：
      · 整合仓 self-conf：配置在 <root>/clash/ 下
      · 单仓 Clash：配置就在 <root> 下
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

判据是「**同时含 `profiles/` 与 `override/`**」，不是目录名。

> 📌 这段是 2026-09-29 **CI 暴露后改的**：原实现基于 `__file__` 向上推算，
> 在 GitHub Actions 的调用方式下算错目录 ⇒ Linux 上全绿、CI 上报「缺文件」。
> **本地全绿 ≠ 线上能跑** —— 路径探测这类环境相关的东西，必须让 CI 跑一遍才算数。

⚠️ 千万别"顺手"把 CWD 优先改回 `__file__` 优先。那是已经踩过的坑（见 `SKILL.md` §7）。

## 2 · 命令

```bash
# ── 一键总入口（47 道并行，含三内核）────────────────────────────
python skill/tests/verify_all.py                  # 期望 exit 0
python skill/tests/verify_all.py -v               # 无论红绿都打印每个闸门输出尾部
python skill/tests/verify_all.py --index          # 只读列闸门清单（不跑、不判负、exit 0）

# ── mihomo 专属四道（离线，快）─────────────────────────────────
python skill/tests/clash/check_structure.py       # 期望 exit 0
python skill/tests/clash/check_min_pair.py        # 期望 exit 0
python skill/tests/clash/check_script_sync.py     # 期望 exit 0（需 node）
python skill/scripts/clash/build_rules.py --check # 期望 exit 0（生成物新鲜度）

# ── mihomo 专属一道（联网，慢）─────────────────────────────────
python skill/tests/clash/check_remote_urls.py                 # 期望 exit 0
python skill/tests/clash/check_remote_urls.py --skip-self     # 跳过本仓 raw 地址
python skill/tests/clash/check_remote_urls.py --timeout 20    # 调超时（默认 15s）

# ── 跨内核（也守 clash 侧）────────────────────────────────────
python skill/tests/check_secrets.py               # 占位符 / 凭据扫描（全仓）
python skill/tests/check_selfcontained.py         # 整合仓自洽性
```

所有 clash 门禁都接受**可选的仓库根参数**：`python skill/tests/clash/check_structure.py <根目录>`。
不传就用 `_default_root()`。**这正是不带参数时在仓库根调用能工作的原因**（CWD → CWD/clash 命中）。

⚠️ `python skill/tests/check_secrets.py` 与 `skill/tests/clash/check_secrets.py` 是**两个不同的脚本**：

| 脚本 | 扫描面 | 判据 |
|:-----|:-------|:-----|
| `skill/tests/check_secrets.py`（跨内核，进 47 道）| 全仓 walk 到的 `.conf` / `.yaml` / `.yml`，**跳过 `icons/`** | 禁串 `tange365.com` / `wangxinyu`；IPv4 白名单；`YAML_CRED_KEYS` 值必须占位 |
| `skill/tests/clash/check_secrets.py`（mihomo 版）| 全仓 walk 到的 `.js` / `.yaml` / `.yml` / `.md` / `.conf` / `.list` / `.txt` / `.json`，**跳过 `icons/` 与 `rules/` 的主机扫描** | 凭据字段非占位即报；IPv4 白名单；主机白名单；私钥头无条件报 |

两者互不可替代：mihomo 版能扫 `.js`（脚本里也有订阅 URL），跨内核版带禁串黑名单
（旧仓教训，条条有据）。**改名合并会同时丢掉两边的判据。**

## 3 · 退出码约定

全仓统一（出处：`reference/shared/troubleshoot-faq.md` §8.2）：

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
| `skill/tests/clash/check_secrets.py` | 0 / 1 |
| `scripts/clash/build_rules.py` | 0 / 1 |
| `check_selfcontained.py` | 0 / 1 |

## 4 · 结构判据（`clash/check_structure.py`）

扫四份 profile（`lazy.yaml` / `lazy.min.yaml` / `routing.yaml` / `routing.min.yaml`），
**四份全过才算过**。守四类事：

### ① 无悬空引用

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

### ② 规则指向存在的组 + 规则集已定义

```python
for r in c.get("rules") or []:
    p = r.split(",")
    if p[0].strip() == "RULE-SET":
        if len(p) < 3:
            errs.append("规则格式错: %s" % r); continue
        prov, pol = p[1].strip(), p[2].strip()
        if prov not in provs:  errs.append("规则引用了未定义的规则集: %s" % prov)
        if pol not in gnames and pol not in BUILTIN:
            errs.append("规则指向了不存在的组: %s" % pol)
    elif p[0].strip() == "MATCH":
        pol = p[1].strip() if len(p) > 1 else ""
        if pol not in gnames and pol not in BUILTIN:
            errs.append("MATCH 指向了不存在的组: %s" % pol)
```

⚠️ `len(p) < 3` 时 `continue` —— 少一个字段是**格式错**，不是"引用了空集"。
不 `continue` 会拿 `p[2]` 越界。

### ③ DNS 广告拦截的两个必要条件

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
本仓四份 profile 的实际顺序都是广告在前（见 §4.1）。

#### 4.1 现役配置的实际值（`routing.yaml` 为例）

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

### ④ IPv6 已显式关闭

```python
if c.get("ipv6") is not False:
    errs.append("顶层 ipv6 未显式关闭")
if dns.get("ipv6") is not False:
    errs.append("dns.ipv6 未显式关闭")
```

⚠️ 用的是 `is not False`，**不是** `!= False` 也不是 `if c.get("ipv6")`：
- 写成 `if c.get("ipv6")` ⇒ `ipv6` 键缺失时也"通过"（`None` 是 falsy）——**漏报**；
- 用 `is not False` ⇒ **缺失也判负**，符合"显式声明"的要求。

⚠️ 为什么要显式写：见 [`leak-localization.md`](leak-localization.md) §6 ——
`dns.ipv6: true` 会返回 AAAA，而本机真实 IPv6 未被 TUN 完整接管 ⇒ **双栈站点绕过 TUN**。
`ipv6: false` 虽等于 mihomo 默认值也必须写（与姊妹仓对齐面的同一条纪律：
显式声明键不适用"默认值就不写"）。

### 4.2 失败怎么修

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

## 5 · 两形态对拍（`clash/check_min_pair.py`）

### 为什么单独要这一项

每份 profile 都有两份形态（`.yaml` 带注释 / `.min.yaml` 纯配置）。`.min` 的定位是
**同一份配置去掉注释**，不是"裁剪配置"。一旦两版配置本体漂移：

> 照着文档改完整版、实际导入的却是 `.min` ⇒ **改了个寂寞**，而且肉眼看不出来。

本仓踩过：`routing.yaml` 由脚本重新生成后忘了同步重生成 `.min`，两份不一致，
而静态文件**不会报错**。

### 判据

```python
a = yaml.safe_load(open(pf, encoding="utf-8"))
b = yaml.safe_load(open(pm, encoding="utf-8"))
d = diff(a, b)
```

**比 Python 对象，不是比文本。** 因此注释、键顺序、缩进、引号风格**都不影响判定**，
只看配置本体。`diff()` 递归：

| 情形 | 报告 |
|:-----|:-----|
| 类型不同（int/float 互转除外）| `X 类型不同: str vs int` |
| dict 键只在一侧 | `X.k 仅 min 有` / `X.k 仅完整版有` |
| list 长度不同 | `X 长度不同: 11 vs 12` |
| 逐元素递归 | `X[0] 值不同: 'A' vs 'B'` |

**任何一处不同即判负**。输出最多列 10 条，其余折叠为「另 N 处」。
比对对：`lazy ↔ lazy.min`、`routing ↔ routing.min`。

### 5.1 `.min` 怎么同步

改完完整版，**同步 `.min`**：

⚠️ **mihomo 侧没有 `.min` 生成脚本。** `make_min.py --family` 的合法取值只有
`routing` / `lazy` / `all`，而它的 `FAMILIES` 表**只含 surge 与 egern 两族**
（`surge/profiles/*.conf`、`egern/profiles/*.yaml`）——
**`clash/profiles/*.min.yaml` 不在里面**。

⇒ 所以 `.min.yaml` 目前只能**手工同步**（去掉注释与空行）。
`check_min_pair.py` 就是用来兜住这件事的：它比 YAML 对象，注释不进比对，
所以手工同步只要保证**配置本体一致**即可。

> 📌 **这是已知的自动化缺口**，与 §9.3 的挂账同源：mihomo 侧的 `.min` 靠人工 + 对拍，
> 不靠生成器。要补的话是给 `make_min.py` 的 `FAMILIES` 加一族 clash。

⚠️ 与 surge 侧的另一个差异值得记：Surge 的 `routing.min.conf` 由脚本生成，
生成脚本会**丢掉注释** ⇒ `# audit-waive:` 行必须手动补回 min 版，否则豁免失效、
审计器会对 min 版报 HIGH（姊妹仓已知缺陷）。
**mihomo 侧不适用这条** —— 比的是 YAML 对象，注释根本不进比对，
`.min.yaml` 不需要保留任何有语义的注释。**别把 Surge 侧的注意事项搬过来。**

### 5.2 失败怎么修

看到 `NG profiles/lazy.yaml vs profiles/lazy.min.yaml —— N 处差异`：

1. 确认哪一侧是"对"的（通常是刚改过的完整版）；
2. 按差异清单**同步 `.min`**（本仓没有生成器，只能手工，见 §5.1）；
   最省事的做法是用 `yaml.safe_load` + `yaml.safe_dump` 重出一份纯配置，
   再比对 —— 别逐行手改；
3. 再跑一次 `check_min_pair.py` 确认归零。

⚠️ 若差异集中在 `.dns.*`，先怀疑是**只改了完整版的 DNS 段** —— DNS 段在四份里必须完全一致。

## 6 · 脚本 ↔ 静态对拍（`clash/check_script_sync.py`）

### 为什么单独要这一项（本仓特有，姊妹仓没有）

mihomo 侧每份配置有**两个交付形态**：

| 形态 | 路径 | 用法 |
|:-----|:-----|:-----|
| 静态文件 | `clash/profiles/routing.yaml` | 下载即用 |
| 覆写脚本 | `clash/override/my_clash.js` | 挂到任意订阅上 |

两者是**同一套配置**的两种形态，脚本的输出就应该是静态文件的样子。一旦漂移：

> 用户会遇到「照文档用脚本订阅，效果跟直接导入配置不一样」，
> 而且**两边都能正常跑、都不报错** —— 只能靠对拍发现。

### 判据

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

### 6.1 两处有意差异（命中不判负，但打印提醒）

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

### 6.2 ✅ 已修（原挂账：漂移分支会 `NameError`）

```python
# line 130
if out.get("rules") != (st.get("rules") or []):
    errs.extend(diff(out.get("rules") or [], st.get("rules") or [], "rules"))
# line 161
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
> ✅ **已修（commit `7d7250c`）**：`diff()` 现已定义在本文件第 94 行，判负时能给出
> 精确诊断（实测：注入一条额外规则 ⇒ 输出 `rules 长度不同: 脚本 12 vs 静态 11`），
> 不再是 `NameError` traceback。
>
> ⚠️ 文档滞后提示（2026-10-07 零信任自查）：本节标题与「修法（未做）」曾长期未同步，
> 让维护者误以为此坑仍在。改代码后请同步回头改这里的挂账记录。
>
> **如需进一步定位**（哪一条规则不同而不是只报长度）：手工 diff 脚本输出与静态 profile 的
> `rules` / `dns` 两段（见 §6.3）。

### 6.3 失败怎么修

1. 先分清是**哪种漂移**：读报错行（修好 `NameError` 前只能人工 diff）。
2. `rules` 漂移 ⇒ 改 `override/my_clash*.js` 里的规则数组，或改静态 profile。
   ⚠️ **规则是逐位比对的**，插一条/删一条/换顺序都会判负。
3. `dns` 漂移 ⇒ 两处的 `dns` 块除 `listen` 外必须逐键相同。
   常见是只改了一侧的端点。
4. `ipv6` 漂移 ⇒ 脚本里 `config.ipv6 = false` 与静态 `ipv6: false` 对齐。
5. 改完跑 `check_script_sync.py` 与 `check_structure.py`（后者会同时校验四份 profile）。

## 7 · 远程集可达性（`clash/check_remote_urls.py`）

### 为什么单独要这一项（本仓的切肤之痛）

> Jinx 上游把 `*-white-guard.*` 改名为 `*-direct.*`，本仓脚本里那条
> `mihomo-white-guard.yaml` 就此 404。分流版改配置时碰巧发现并修了，
> **懒人版一直挂着死链没人察觉** —— 因为本仓当时没有 CI，没人定期去问
> 「这个 URL 还活着吗」。

死链的后果**不是报错，是静默降级**：rule-provider 拉不到 ⇒ 变成空集 ⇒
该走 `AD` 的广告全进了兜底出口。**配置看着跑得挺好，其实拦截没了。**

### 收集规则（两条路径，缺一不可）

| 路径 | 抓什么 | 为什么需要 |
|:-----|:-------|:-----------|
| `collect_urls()`（纯文本扫）| `override/` 与 `profiles/` 里 `.js` / `.yaml` / `.yml` 中的 http(s) URL | 覆盖注释与字面量 |
| `collect_from_scripts()`（**真的跑一遍脚本**）| `rule-providers` 的 `url`、策略组的 `icon` | 脚本里 MRS 是 `JS + "/geosite/" + c + ".mrs"` **拼接**出来的，纯文本扫描抓不到完整 URL |

⚠️ 第二条是关键设计：**不跑脚本就收集不到拼接出来的地址**。只做文本扫描这道门等于半瞎。

### 排除规则（避免误判）

| 排除项 | 常量 / 条件 | 理由 |
|:-------|:------------|:-----|
| 占位地址 | `PLACEHOLDER_PAT`（`example.com` / `REPLACE_WITH` / `YOUR_TOKEN` / `localhost` / `127.0.0.1`）| 给用户替换的订阅槽位，**本来就不该可达** |
| 基址常量 | `BASE_URLS`（icons 目录 / 仓库根 / MetaCubeX geo 目录）| 是拼接用的前缀，不是可探测的资源 |
| DoH 端点 | `DOH_PAT`（`/dns-query$`）| 是解析器不是静态资源，HEAD 往往不通 |
| 健康检查探针 | `HC_URLS`（`www.gstatic.com/generate_204`）| 连通性探测用 |
| 非静态后缀 | `RESOURCE_SUFFIX = (".mrs", ".yaml", ".yml", ".list", ".txt", ".json")` | **只有这些后缀才探测** |

### 探测与判据

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

### 7.1 失败怎么修

| 报错 | 修法 |
|:-----|:-----|
| `死链 N 个` + `出处: override/xxx.js (运行期)` | 改脚本里的拼接/常量；**同时**确认静态 profile 里的同款 URL 也改了 |
| `死链` + `出处: profiles/xxx.yaml` | 改静态 profile；若脚本也引用了同款，一并改 |
| 本仓 raw 地址 404 | 本地用 `--skip-self` 排除；CI 侧**用重跑而非跳过** |
| `未收集到任何远程 URL —— 检查收集规则`（exit 2）| 先看是不是**在没有 `profiles/`+`override/` 的目录**下跑的（`_default_root()` 落到了 CWD）；其次看 `--skip-self` 是否把全部目标都跳过了 |

⚠️ **改 URL 后必须同时跑 `check_script_sync.py`** —— 它比对两侧 `rule-providers` 的 URL 集合，
只改一侧会立刻判负。

## 8 · 生成物新鲜度（`build_rules.py`）

### 为什么需要（合并项目最直接的收益）

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

### 判据

```python
rules = read_rules(sp)
want  = render(dst, src, desc, rules)
have  = open(dp, encoding="utf-8").read() if os.path.exists(dp) else None
if have == want:      print("  OK … (已是最新)")
elif check:           print("  NG rules/%s 已过期（真源 %s 有更新）"); stale.append(dst)
else:                 open(dp, "w", …).write(want)   # 重新生成
```

**逐字节比对 `render()` 的期望输出与磁盘内容**（含头部注释里的条数）。
真源缺失 ⇒ `NG 真源缺失` 并计 stale。

| 模式 | 行为 | 退出码 |
|:-----|:-----|:------:|
| 默认 | 重写出过期/缺失的生成物 | 0（除非真源缺失 ⇒ 1）|
| `--check`（CI 用）| **只检查**，过期即判负，不写盘 | 0 / 1 |

### 8.1 头部注释是有语义的

生成物头部写明「本文件由 `build_rules.py` 自动生成，请勿手工编辑」与条数，
末尾一句尤其重要：

```
# ⚠️ 纯域名集、零 IP 条目 ⇒ 引用方**不写**规则级 no-resolve。
```

⇒ 这是 [`leak-localization.md`](leak-localization.md) §4（规则判定触发的解析）的直接依据：
**零 IP 条目的规则集不需要 `no-resolve`**，写了反而有害（见下节）。

### 8.2 失败怎么修

```bash
python skill/scripts/clash/build_rules.py           # 重新生成（不是改 .yaml）
```

❌ **红线：不手工编辑 `rules/*.yaml`**（`SKILL.md` §8）。改内容只改 `.list`，重跑脚本。

## 9 · 判别力：怎么证明门禁真的会判负

### 9.1 为什么"好配置通过"证明不了任何事

> 只测「好配置通过」是**证明不了判别力**的。
> 一个恒返回 0 的脚本也能让现役配置全绿。

本仓对判别力的要求（与 `check_region_filters.py` 同源）是**两侧合计**：
既放行现役配置、又拦住故意损坏的样例。判负侧的断言是**两条**，不是一条：

1. **退出码 == 1**；
2. **输出里出现那个故意注入的定位标记**（如组名 / 键名）。

⚠️ 第 2 条不是多余：审计器**崩了**（emoji 触发 `UnicodeEncodeError`）同样以退出码 1 结束
—— 而判负样例期望的**恰恰也是 1**。两者的区别只能在**输出**里看。
所以判负样例必须「能点名到这一条」，才能与「崩在别处」分开。

### 9.2 每个门禁的坏样例构造方法

统一前置（**在仓库外做**，避免污染工作副本）：

```bash
SB=/tmp/clash-gate-probe          # macOS/Linux；Windows 用 C:/Users/<你>/AppData/Local/Temp/...
mkdir -p "$SB/profiles" "$SB/override"
cp clash/profiles/*.yaml "$SB/profiles/"
cp clash/override/*.js   "$SB/override/"
# 先确认基线是绿的（否则后面的判负不可信）
python skill/tests/clash/check_structure.py   "$SB"   # 期望 0
python skill/tests/clash/check_min_pair.py    "$SB"   # 期望 0
python skill/tests/clash/check_script_sync.py "$SB"   # 期望 0
```

> ⚠️ **基线必须先绿**。基线红时注入坏样例，判负可能来自原有缺陷 ⇒ 判别力结论无效。

#### `check_structure.py` —— 8 个坏样例，一个判据一个

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

#### `check_min_pair.py`

| # | 注入 | 期望报错 |
|:-:|:-----|:---------|
| 11 | 在 `lazy.min.yaml` 的 `rules` 首行插一条 `DOMAIN-SUFFIX,example.com,DIRECT` | `rules 长度不同: 11 vs 12` + `rules[0] 值不同` |
| 12 | 只改 `lazy.min.yaml` 的 `dns.prefer-h3` → `true` | `.dns.prefer-h3 值不同: False vs True` |

> ✅ 已实测：注入 11 ⇒ exit 1 且输出含 `rules 长度不同: 11 vs 12`；注入 12 ⇒ exit 1 且含
> `.dns.prefer-h3 值不同`。恢复后 exit 0。
>
> 📌 12 值得单独做：它证明**只动一个 DNS 键也会被抓到** —— 这正是「DNS 段必须四份一致」
> 那条纪律能落地的原因。

#### `check_script_sync.py`

| # | 注入 | 期望 | 实际（⚠️ 见 §6.2）|
|:-:|:-----|:-----|:------------------|
| 13 | 从 `override/my_clash_lazy.js` 的规则数组里删掉一条 `RULE-SET,Jinx-CN,DIRECT` | exit 1 + 报出 rules 差异 | **exit 1，但输出是 `NameError` traceback**，无差异明细 |

> ✅ 已实测：基线 `my_clash.js` / `my_clash_lazy.js` 双双 `OK`（exit 0）；
> 删掉一条规则后 exit 1 —— **闸门会红，不会假绿**，但诊断信息缺失（挂账 §6.2）。

⚠️ 因此这道门的判别力是**"半条"**：能判负（1 对），给不出定位（2 不成立）。
**修好 `diff` 之后，第 2 条才成立。** 在那之前不要声称这道门"判别力完整"。

#### `build_rules.py --check`

| # | 注入 | 期望 |
|:-:|:-----|:-----|
| 14 | 往 `rules/AI.list` 末尾追加一行（任意域名）后跑 `--check` | `NG rules/AI_Domains.yaml 已过期（真源 AI.list 有更新）` + exit 1 |

> ✅ 已实测：追加一行后 `--check` 输出 `NG rules/AI_Domains.yaml 已过期（真源 AI.list 有更新）`、
> exit 1；恢复真源后 exit 0。
>
> ⚠️ **做这个实验前先备份真源**（`cp rules/AI.list $SB/AI.list.bak`），做完立刻还原，
> 并跑一次 `git diff rules/` 确认为空。**别让探针污染真源。**

#### `check_remote_urls.py`

| # | 注入 | 期望 |
|:-:|:-----|:-----|
| 15 | 把副本里某条 rule-provider URL 的后缀改成一个必死的名字（如 `mihomo-direct.yaml` → `mihomo-white-guard.yaml`，即当年真实死链）| 该 URL 标 `NG` + 末尾 `死链 N 个` + exit 1 |

⚠️ 这道门**需要联网**，且要跑完整个 URL 列表（数十个，每个最多 2×timeout）。
本地验证时用 `--timeout 8` 加速；CI 上用 `--timeout 20`。

#### `check_secrets.py` / `check_selfcontained.py`

坏样例**不要在副本里做**，直接看它们的判据：

| 脚本 | 最小判负样例 | 定位标记 |
|:-----|:-------------|:---------|
| `skill/tests/clash/check_secrets.py` | 任意 `.yaml` 里写 `password: MyRealP@ssw0rd123`（非占位、含数字）| `非占位凭据:` |
| `skill/tests/clash/check_secrets.py` | 任意文件里出现白名单外 IPv4，如 `10.0.0.1` | `非常见 IP: 10.0.0.1` |
| `check_selfcontained.py` | 任意**非注释行**出现 `https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/...` | `外部依赖 N 处` |

### 9.3 判别力回归的现状（诚实口径）

| 门禁 | 判负样例已实测 | 有自动化回归 |
|:-----|:--------------|:------------|
| `check_structure.py` | ✅ 10 个，逐个 exit 1 + 定位标记 | ❌ 无（人工跑）|
| `check_min_pair.py` | ✅ 2 个 | ❌ 无 |
| `check_script_sync.py` | ⚠️ 1 个，能判负但无诊断（§6.2）| ❌ 无 |
| `build_rules.py --check` | ✅ 1 个 | ❌ 无 |
| `check_remote_urls.py` | ⚠️ 联网依赖，未逐个固定 | ❌ 无 |
| `check_region_filters.py`（跨内核）| ✅ | ✅ **有**（唯一定期跑判负 fixture 的闸门）|

> 📌 跨内核的 `check_region_filters.py` 是**唯一**把「判负 fixture」做进 47 道的闸门，
> 且它对每个判负用例断言**退出码 + 输出标记**两条。mihomo 侧**还没有对应的自动化回归** ——
> 上表前五行的"已实测"是**本次文档编写时人工跑出来的**，不是常驻 CI 的保证。
>
> **这是已知挂账**：mihomo 侧门禁的判别力目前靠"人记得跑"，不是靠机器守住。
> 一旦出现「门禁逻辑改坏、判据不再判负、现役配置仍全绿」，本仓**没有闸门会发现**。

## 10 · 已知豁免项（豁免 ≠ 通过）

本仓的 git 历史从整合完成起算，Release 亦从本仓发布。
因此对依赖这两者的判据做**显式豁免**（不是静默跳过）。

### 10.1 V7「一天一版」

```python
_skip_v7 = {'SKIP_V7': '1'}
('min-pair 一致', [PY, 'skill/tests/check_min_pair.py'], _skip_v7),
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

### 10.2 releases 方案

```python
# ⚠️ self-conf 豁免：检查的是「本仓自己的 Release 发布纪律」，
#    ~~整合仓没有对应的 Release，查也无意义~~ ⇒ 已于 2026-10-08 发布首个 Release
#    （v2026-10-08）并启用第 22 道「Release 断言」，现在是活的判据。
# ('releases 方案', [PY, 'skill/tests/check_releases.py'],
#  {'GITHUB_TOKEN': _token() or ''}),
```

直接从 `build_gates()` 里**注释掉**，不是跑完跳过。理由：
检查对象是「本仓自己的 Release 发布纪律」。✅ **已于 2026-10-08 启用**（首个 Release `v2026-10-08` 已发布），现为闸门第 22 道。

⚠️ 这道门在姊妹仓是有效判据（需 `GITHUB_TOKEN`，缺省回退 `gh auth token`；
都没读到、或 API 离线/限流/上游 5xx/非 JSON 时返回 **3**）。
✅ **已于 2026-10-08 启用**（首个 Release `v2026-10-08` 发布后）—— 现为闸门第 22 道「Release 断言」，不再是豁免项。

### 10.3 豁免的三条纪律

1. **豁免必须点名**，不冒充通过 —— 输出里要能读出「未验证」。
2. **豁免要写理由**，理由要能被证伪（"没有 Release"是可验证的事实，不是"太麻烦"）。
3. **豁免项要么进 `build_gates()` 带 SKIP 标记、要么显式注释掉**。
   绝不允许"跑一遍然后无视结果" —— 那是静默假绿。

## 11 · 47 道总览表

> ⚠️ **关于道数（含近重复，对外说数量时心里有数）**：
> 47 道里有 2 组近重复 —— #9 与 #42（分流覆盖·mihomo|clash 分流覆盖）；#11 与 #46（规则集内容·mihomo|clash 规则集内容）。**刻意保留**：双档覆盖能让分流版与
> 懒人版都查到；合并会让其中一档漏检。故这个数**含重复劳动**，不是 47 种独立检查。
>
> ✅ **本表由 `python skill/scripts/gen_gate_table.py --apply` 生成**，
> 真源是 `verify_all.py --index`，**不要手抄**。
> 漂移由同一脚本的 `--check` 判负（已接闸门），不再靠人记得更新。
>
> 历史：此表曾长期是手抄死表 —— 表头自称「现抓、勿手抄」，实际编号与
> `--index` 全对不上（Release 写 27 实为 18、地区组 28–30 实为 2–4），
> 还把 `check_selfcontained` 同时列为「第 21 道」和「不进闸门」。（第三轮审查第 6 条）

| # | 闸门 | 命令 |
|:--|:-----|:-----|
| 1 | secrets 扫描 | `skill/tests/check_secrets.py` |
| 2 | make_min 自检 | `skill/tests/make_min.py --selftest` |
| 3 | 脚本对拍 diff 自检 | `skill/tests/clash/check_script_sync.py --self-test` |
| 4 | 地区组判别力·Surge | `skill/scripts/surge/audit_region_filters.py surge/profiles/routing.conf` |
| 5 | 地区组判别力·Egern | `skill/scripts/egern/audit_region_filters.py egern/profiles/routing.yaml` |
| 6 | 地区组判别力·mihomo | `skill/scripts/clash/audit_region_filters.py clash/profiles/routing.yaml` |
| 7 | 分流覆盖·Surge | `skill/scripts/surge/audit_routing_coverage.py surge/profiles/routing.conf` |
| 8 | 分流覆盖·Egern | `skill/scripts/egern/audit_routing_coverage.py egern/profiles/routing.yaml` |
| 9 | 分流覆盖·mihomo | `skill/scripts/clash/audit_routing_coverage.py clash/profiles/routing.yaml` |
| 10 | 规则集内容·Surge | `skill/scripts/surge/audit_ruleset_content.py surge/profiles/routing.conf` |
| 11 | 规则集内容·mihomo | `skill/scripts/clash/audit_ruleset_content.py clash/profiles/routing.yaml` |
| 12 | 规则集刷新周期·Surge | `skill/scripts/surge/audit_ruleset_refresh.py --strict surge/profiles/routing.conf` |
| 13 | 规则集刷新周期·Egern | `skill/scripts/egern/audit_ruleset_refresh.py --strict egern/profiles/routing.yaml` |
| 14 | DNS 转发泄露·Egern | `skill/scripts/egern/audit_dns_forward.py egern/profiles/routing.yaml` |
| 15 | no-resolve 配对·Egern | `skill/scripts/egern/audit_ruleset_noresolve.py egern/profiles/routing.yaml` |
| 16 | 规则集来源文档同步 | `skill/tests/clash/check_ruleset_doc_sync.py` |
| 17 | 自托管清单·裸IP检测(AI) | `skill/scripts/egern/profile_ruleset.py --offline rules/AI.list` |
| 18 | 自托管清单·裸IP检测(apple-system) | `skill/scripts/egern/profile_ruleset.py --offline rules/apple_system.list` |
| 19 | 自托管清单·裸IP检测(emby) | `skill/scripts/egern/profile_ruleset.py --offline rules/emby.list` |
| 20 | 闸门总览表同步 | `skill/scripts/gen_gate_table.py` |
| 21 | 闸门清单对账 | `skill/tests/check_gate_manifest.py` |
| 22 | CHANGELOG 漂移 | `skill/tests/check_changelog_drift.py` |
| 23 | Release 断言  [需 GITHUB_TOKEN] | `skill/tests/check_releases.py` |
| 24 | clash secrets 扫描 | `skill/tests/clash/check_secrets.py` |
| 25 | portability | `skill/tests/check_portability.py` |
| 26 | min-pair 一致 | `skill/tests/check_min_pair.py` |
| 27 | README 徽章 | `skill/tests/check_badges.py` |
| 28 | markdown 链接 | `skill/tests/check_links.py .` |
| 29 | Surge DNS lazy | `skill/scripts/surge/check_surge_dns.py surge/profiles/lazy.conf` |
| 30 | Surge DNS routing | `skill/scripts/surge/check_surge_dns.py surge/profiles/routing.conf` |
| 31 | Egern DNS 双份 | `skill/scripts/egern/check_egern_dns.py egern/profiles/lazy.yaml egern/profiles/routing.yaml` |
| 32 | mihomo DNS 双份 | `skill/scripts/clash/check_clash_dns.py clash/profiles/lazy.yaml clash/profiles/routing.yaml` |
| 33 | .min 漂移 | `skill/tests/make_min.py --check` |
| 34 | 地区组判别力 | `skill/tests/check_region_filters.py` |
| 35 | profile 结构 | `skill/tests/check_structure.py` |
| 36 | 文档 AUTO 同步 | `skill/tests/sync_docs.py --check` |
| 37 | clash 结构 | `skill/tests/clash/check_structure.py` |
| 38 | clash min 版一致 | `skill/tests/clash/check_min_pair.py` |
| 39 | clash 脚本/静态对拍 | `skill/tests/clash/check_script_sync.py` |
| 40 | clash 规则集生成物 | `skill/scripts/clash/build_rules.py --check` |
| 41 | clash 头注数字新鲜度 | `skill/tests/clash/check_header_numbers.py` |
| 42 | clash 分流覆盖 | `skill/scripts/clash/audit_routing_coverage.py clash/profiles/routing.yaml clash/profiles/lazy.yaml` |
| 43 | 自洽性 | `skill/tests/check_selfcontained.py` |
| 44 | smart 权重口径 | `skill/tests/check_priority_weight.py` |
| 45 | 版本头注 | `skill/tests/clash/check_version_header.py` |
| 46 | clash 规则集内容 | `skill/scripts/clash/audit_ruleset_content.py clash/profiles/routing.yaml clash/profiles/lazy.yaml` |
| 47 | clash 静态 profile 新鲜度 | `skill/scripts/clash/build_profiles.py --check` |

另有**不进闸门**的 4 项 —— 下表由 `check_gate_manifest.KNOWN_SEPARATE` **直接生成**，
> 与它不会分叉（第九轮问题 1：此前硬编码且谎称对账，两边曾不一致）：

| 项 | 位置 | 为什么不进 |
|:---|:-----|:-----------|
| `check_real_kernel.py` | 手动（不在任何闸门） | 需真内核 + 真网络，仅本地人工跑（ops.md §6.8.1） |
| `check_remote_urls.py` | CI 独立 step | CI 独立 step（慢，需联网探测数十个 URL） |
| `probe_dns_endpoints.py` | CI 独立 step | CI 独立 step —— 需联网实测加密 DNS 端点，有判负语义但抖动会假红，故不进 47 道 |
| `verify_all.py` | CI 独立 step（总入口本身） | 它自己就是总入口，不是被调的判据 |
⚠️ `min-pair 一致` 一道含 V7「一天至多一版」两条断言；本仓以 `SKIP_V7=1` 豁免
⇒ 该两条记为 **未验证**（⚠️）而非通过，本道以 exit 3 结束，上层显示 ⚠️。
详见 `release-rules.md` §4.1。

### 11.1 汇总表怎么读



```
闸门                        结果  耗时
────────────────────────────────────
clash 结构                  ✅   0.7s
clash min 版一致            ✅   0.6s
clash 脚本/静态对拍          ✅   2.1s
clash 规则集生成物           ✅   0.5s
```

| 标记 | 退出码 | 含义 |
|:----:|:------:|:-----|
| ✅ | 0 | 判据全过 |
| ⚠️ | 3 | **SKIP（未验证 ≠ 绿）** —— 汇总下方会点名 |
| 🔧 | 2 | 前置环境不达标 —— 汇总下方会点名，**先修环境** |
| ❌ | 其它（含 1）| 有判负 |

红的才展开输出尾部（最后 30 行）；`-v` 则无论红绿全展开。

## 12 · CI 怎么跑（`.github/workflows/ci.yml`）

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

### Steps

| # | Step | 说明 |
|:-:|:-----|:-----|
| 1 | `actions/checkout@v4`（`fetch-depth: 0`）| 保留完整历史（V7 虽豁免仍保留）|
| 2 | `setup-python@v5` → 3.12 | |
| 3 | `setup-node@v4` → 20 | **mihomo 两道门要跑 JS** |
| 4 | Install deps：`pip install pyyaml` | 缺 PyYAML ⇒ 三道 clash 门直接 exit 2 |
| 5 | **Gates (Surge + Egern + mihomo)** | `python skill/tests/verify_all.py` |
| 6 | **Encoding gate (cp936)** | 同上命令，但 `PYTHONIOENCODING: cp936` |
| 7 | **Remote ruleset reachability (mihomo)** | `check_remote_urls.py --timeout 20`，PR 时 `continue-on-error: true` |
| 8 | **Encrypted DNS endpoints reachability (Egern)** | `probe_dns_endpoints.py`；需联网，PR 时 `continue-on-error: true` |

### 12.1 两处必须理解的设计

**① 编码门（ci.yml「Gates」之后那步，按§11 8 行表为 Step 6、按 verify_all 脚注的 5 项清单为第 3 项）**

```
中文 Windows 下 print 非 GBK 字符会 UnicodeEncodeError 并以退出码 1 结束，
而 1 恰是判负码 ⇒ 崩溃会被读成「判负」，整轮看着对其实判据没跑。
```

以 `PYTHONIOENCODING=cp936` 在 Linux 上**等价复现** Windows(ACP=936) 的管道路径。
它与 `check_portability.py` 的 E4 **互补、不可互相替代**：

| | 覆盖 | 假阳性 |
|:--|:-----|:-------|
| 编码门（运行时）| 只覆盖 `build_gates()` 跑到的脚本、且只覆盖**执行到的分支** | **零** |
| E4（静态）| 全覆盖（含 CI 不跑的审计脚本）| 有漏报也有假阳性 |

⚠️ 前提是 `run_one()` 对 `PYTHONIOENCODING` 用 **`setdefault`**：

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

### 12.2 与本地的关系

> **与 CI 同源是铁律** —— 本地绿但 CI 红属于竞态 / 环境差，不允许有"第三套判据"。

✅ **挂账已消（2026-10-07）**：新增 `skill/tests/check_gate_manifest.py` 做机器对账，
**已进 47 道**（`闸门清单对账`）。它判四件事（前三件 + 第四轮新增的孤儿检查）：
① `ci.yml` 里被调用的判据必须在 `verify_all` 清单里（豁免项逐条点名）；
② `verify_all` 列出的每一道，文件必须真实存在；
③ `skill/tests/` 下既没进闸门、也没登记在 `ops.md` §6.8.1 的脚本 ⇒ 报「永远不会跑」。
-④ **孤儿探测**：同一文件名，在某内核被闸门引用、另一内核有文件却没引用 ⇒ 报。
   ⚠️ 边界：**独有名字**的新脚本不报（有意为之 —— 全扫 `skill/scripts/` 会假报十几处）。

⚠️ 豁免项**必须显式登记**，不能静默放行：现为 `check_remote_urls.py`（CI 独立 step，慢）、
`check_real_kernel.py`（需真内核 + 真网络）、~~`check_releases.py`（本仓未发布 Release）~~ ⇒ 已启用（第 22 道）、
`verify_all.py`（它自己就是入口）。

引用清单时仍建议用 `--index` 现抓 —— 但即使手抄，这份对账会兜住漂移。

> **推翻挂账的触发条件**：一旦出现「一侧增删闸门、另一侧未同步」且事后确认是人工漏同步
> 造成的本地/CI 结论分歧，就必须补上清单对账断言。

⚠️ 本地与 CI 对**退出码 3** 的口径**有意不同**：本地允许 SKIP（可能真离线 → exit 0 + ⚠️），
CI 侧 3 视为失败（CI 带 token，读不到远端即 CI 环境异常）。这是**严格化**，不是第三套判据。
CI 偶发 3（共享 runner IP 被限流）→ 重跑即可。

## 13 · 判据演进史

| 版本 | 改动 | 原因 |
|:----:|:-----|:-----|
| v1 | clash 门禁的 `_default_root()` 基于 `__file__` 向上推算 | 初版 |
| v2 | 改为 **CWD 优先** + 逐级向上探测（找同时含 `profiles/` 与 `override/` 的目录）| **CI 暴露**：Linux 上报「缺文件」，本地全绿（2026-09-29）|
| v1 | mihomo 侧门禁未纳入总入口，要单独跑 | 整合前 |
| v2 | 追加 `clash 结构` / `clash min 版一致` / `clash 脚本/静态对拍` / `clash 规则集生成物` 四道 | 整合后「三内核一视同仁」（2026-10-07）|
| v1 | 各内核各存一份 `.list` 与 `.yaml` | 此前：双份维护，改一处忘一处就漂移 |
| v2 | `.list` 为唯一真源，`build_rules.py` 生成 `.yaml` | **单一真源，物理上不可能漂移** |
| v1 | `check_remote_urls.py` 只做文本扫描 | 初版 |
| v2 | 增加 `collect_from_scripts()` —— **真的跑一遍脚本**收集 | 脚本里 URL 是拼接出来的，文本扫不到 |
| v1 | 无远程可达性门禁 | 本仓当时没有 CI |
| v2 | 加 `check_remote_urls.py` + CI `schedule` 每周任务 | **Jinx 上游改名致死链，懒人版挂了死链没人察觉** |
| v1 | `check_script_sync.py` 引用未定义的 `diff` | 初版即存在 |
| v2 | （未修）| 现役配置恒一致 ⇒ `diff` 从未被调用 ⇒ bug 潜伏；**判负时才 `NameError`**（2026-10-07 文档编写实测发现，见 §6.2）|
| v1 | `198.18.0.1` 被跨内核 secrets 扫描判为真实 IP | 那是 mihomo 的 fake-ip 段（RFC 6815），Surge/Egern 侧不认识 |
| v2 | 给 `DOC_NETS` 加 `198.18.` | 整合必须处理这类"各内核的常识不同" |
| v1 | Clash 侧 3 个文件是 CRLF，门禁判负 | 初版 |
| v2 | 转 LF + 搬入 `.gitattributes` | 全仓统一 |
| v1 | V7「一天一版」在整合仓判负 | 复制文件 mtime 丢失，历史归档全变成复制当天 |
| v2 | `cp -p` 保留 mtime + 加 `SKIP_V7` 开关，输出明示「未验证，不是通过」| 复制仓本就不继承 git 历史，**判据在此不成立** |
| v1 | `check_releases` 在总入口里 | 姊妹仓 |
| v2 | 从 `build_gates()` 注释掉 + 写明理由 | 整合仓没有自己的 Release，查也无意义 |

### 一条贯穿的规律

> 每一轮修订，都不是「发现漏了某个检查」，
> 而是**原来那条判据的方向写错了**（漏报 / 不可能满足 / 覆盖了不该覆盖的）。

mihomo 侧的实例：

- `_default_root()` 的 v1 **不是漏了 clash 目录**，是探测方向写错了（信 `__file__` 不信 CWD）；
- `198.18.0.1` 的 v1 **不是规则集真有泄露**，是判据不认识另一内核的合法保留段；
- `check_script_sync` 的 `diff` **不是判据错**，是**只在判负路径上才执行的代码从未被执行过** ——
  这类 bug 静态看不出来，只有注入坏样例才暴露。

⇒ **假 HIGH 比漏报危害更大**：漏报只是少发现一个问题；
假 HIGH 会让使用者去改一条**本来正确的**规则，然后把配置改坏。

⇒ 因此每一条判据都要求：**能说清"怎么做才算过"**，且**不能说清的就是判据没写好**。

## 14 · 全绿 ≠ 可用

审计脚本覆盖的是**静态可判定**的部分。以下必须实测：

| 维度 | 为什么脚本做不到 | 怎么做 |
|:-----|:-----------------|:-------|
| 冷启动有无明文 `:53` | 需要抓包 | 本地 DNS sink + mihomo 内核实测（CHANGELOG 记过一次） |
| IPv6 是否真的不通 | 需要真实双栈环境 | 见 [`leak-localization.md`](leak-localization.md) §6 |
| 拦截效果 | 需要真实访问 | 打开几个广告密集的站点看 |
| 误杀 | 需要真实访问 | `github.com` / `jsdelivr.net` / `icloud.com` 是否能开 |
| 节点可用性 | 需要真实网络 | 面板上逐个测 |
| NAT 类型 / 时间同步 | 需要真实设备 | 游戏机连一下 |
| 远程规则集内容 | 脚本只看 URL 活不活 | 拉下来数（IP 条目是否带 `no-resolve`）|

> ⚠️ 这是本项目的核心立场：**审计通过 ≠ 配置可用。**
> 每修好一次判据，都要假设「还存在审计器看不见的维度」。

---

## 15 · FAQ

**Q：`skill/tests/clash/check_secrets.py` 和 `skill/tests/check_secrets.py` 该跑哪个？**

两个都跑 —— 47 道里进的是**跨内核版**（`skill/tests/check_secrets.py`，带禁串黑名单）。
mihomo 版（`skill/tests/clash/check_secrets.py`）覆盖 `.js`、且跳过 `rules/` 的主机扫描
（那目录内容本身就是域名清单，扫了全是误报）。**两者判据不同，互不可替代，别合并。**

**Q：门禁报「缺文件」但我明明有。**

先看在哪个目录下跑的。`_default_root()` 的判据是「**同时含 `profiles/` 与 `override/`**」，
顺序是 CWD → `CWD/clash` → `__file__` 逐级向上。在仓库根跑会命中 `<root>/clash`。
若在某处跑导致落到了 CWD 而 CWD 不是 clash 目录，就会报缺文件。显式传参最稳：
`python skill/tests/clash/check_structure.py clash`。

**Q：`ipv6: false` 是默认值，为什么写了还要求写、不写还判负？**

两个原因：① `dns.ipv6` 不写就返回 AAAA，而真实 IPv6 未被 TUN 完整接管 ⇒ 绕过（见
`leak-localization.md` §6）；② 与 Surge/Egern 的对齐面键**一律显式声明**，
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

## 16 · 维护者须知

### 16.1 改 mihomo 配置的最小闭环

```bash
# 1. 改完整版（改 .list 真源的话先重生成）
vim clash/profiles/routing.yaml
python skill/scripts/clash/build_rules.py            # 若动了 rules/*.list

# 2. 同步 .min（⚠️ 无生成器，手工；用 yaml 重出一份再比对最省事）
python -c "import yaml;c=yaml.safe_load(open('clash/profiles/routing.yaml',encoding='utf-8'));yaml.safe_dump(c,open('clash/profiles/routing.min.yaml','w',encoding='utf-8'),allow_unicode=True,sort_keys=False)"

# 3. mihomo 四道
python skill/tests/clash/check_structure.py
python skill/tests/clash/check_min_pair.py
python skill/tests/clash/check_script_sync.py
python skill/scripts/clash/build_rules.py --check

# 4. 总入口（47 道）
python skill/tests/verify_all.py

# 5. 慢门，按需（联网）
python skill/tests/clash/check_remote_urls.py
```

### 16.2 改动前必须知道的四条

1. **四份 profile 都要改。** `lazy` / `routing` × `.yaml` / `.min.yaml`。
   只改完整版 ⇒ `check_min_pair.py` 立刻判负。
2. **脚本与静态是同一套配置的两个形态。** 改 `override/*.js` 必须同步改 `profiles/*.yaml`
   （反之亦然）—— `check_script_sync.py` 逐位比对 `rules`、比对 `rule-providers` URL 集合。
3. **不手工编辑 `rules/*.yaml`。** 那是生成物，改真源 `.list` 后重跑 `build_rules.py`。
4. **不提交真实地址 / 凭据 / token。** `check_secrets.py` 两份都会拦。

### 16.3 改判据时要做的事

1. **先注入坏样例，确认它会红**（§9.2）。判据改完之后再注入一次，确认它**还**会红。
2. **确认基线仍绿** —— 否则判负可能来自原有缺陷。
3. **探针做在仓库外**（`/tmp` 或 `%TEMP%` 下的副本 + 显式传 ROOT 参数），
   做完还原并 `git status` 确认没多出改动。
4. **动 `rules/*.list` 做实验前先备份真源**，做完立刻还原并 `git diff rules/` 确认为空。
5. **改 `build_gates()` 就要改 `ci.yml`**（同源铁律）。引用清单用 `--index` 现抓，别手抄。

### 16.4 四条已知挂账（接手时先看这里）

| # | 挂账 | 触发修补的条件 |
|:-:|:-----|:---------------|
| 1 | `check_script_sync.py` 的 `diff` 未定义 ⇒ 判负时 `NameError`，无诊断 | 出现第一次真实漂移且需要定位时，必须修 |
| 2 | 闸门清单 `ci.yml` ↔ `verify_all.py` 人工双写、机器对账未做 | 出现一侧增删而另一侧未同步、且造成本地/CI 结论分歧时 |
| 3 | mihomo 侧门禁**没有常驻的判负 fixture 回归**（判别力靠人记得跑）| 出现「判据改坏、不再判负、现役仍全绿」时 |
| 4 | **clash 侧没有 `.min` 生成器**（`make_min.py` 只含 surge / egern 两族）⇒ `.min.yaml` 靠手工同步 + 对拍兜底 | 出现第一次「手工同步漏改、对拍才发现」时；修法是给 `FAMILIES` 加一族 clash |

### 16.5 退出码速查

| 码 | 含义 | 见到怎么办 |
|:--:|:-----|:-----------|
| 0 | 判据全过 | — |
| 1 | 有判负 | 读输出修配置 |
| 2 | 前置环境不达标 | **先修环境，别读判据**（最常见：缺 PyYAML / 缺 node / 目录不对）|
| 3 | SKIP（未验证）| 不计失败，但**输出必须写「未验证」**，不得当成绿 |
