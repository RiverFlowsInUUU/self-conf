#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 clash（mihomo）侧地区组 `filter` 的**判别力** —— 太窄 / 太宽 / 拷贝不同步。

为什么必须有这个脚本
--------------------
mihomo 的地区组**不写成员表**，只靠 `filter` 正则在运行时从全池里筛节点名
（`include-all` / `include-all-proxies` 引入节点，`filter` 作用于**合并后**的成员列表）。
于是「某个节点归哪个地区」这件事实，完全由一条正则承担 —— 而正则写坏了
**没有任何报错**：组是空的、或节点落错组，面板上都只是"看起来少了几个节点"。

Surge / Egern 两侧各有一份 `audit_region_filters.py`，守的是「正向关键词有没有
逐字同步进 `Other Regions` 的负向断言」。mihomo 侧一直**没有**对应的审计器 ——
`reference/profiles/clash.md` §8.3 自己写过这句：
「mihomo 侧目前**没有**这个比对器 —— 改地区正则时六处要一起改」。
本脚本补的就是这个缺口，但判据**不止**"拷贝同步"一条：

判据（七条，编号用于 `# audit-waive:`）
--------------------------------------
  ① 结构：6 个地区组在场、都有 `filter`、都有节点来源开关
     （`include-all` / `include-all-proxies` / `include-all-providers` 之一）。
     没有来源开关 ⇒ 组内成员表是空的，`filter` 再对也筛不到任何节点。
     另外 `filter` 必须能被编译（编不了 = 配置缺陷，判负而不是当环境问题放过）。
  ② 必备关键词覆盖（**不太窄**）：每个地区组正向半串里必须有本地区的常见写法。
     香港 `港/HK/Hong`、台湾 `台/TW/Taiwan/Tai`、日本 `日/JP/Japan`、
     新加坡 `新加坡/狮城/SG/Singapore`、美国 `美/US/States/America`。
  ③ 本地区样本**实测**（不太窄）：拿一批真实机场常见命名喂进去，必须被本组匹配到。
     ⚠️ 这条与 ② 互补、不可互相替代：② 是"词在不在"，③ 是"整条正则跑起来对不对"
        （锚点写错、括号套错时 ② 全绿而 ③ 立刻红）。
  ④ 其它地区样本**实测**（**不太宽**）：本组**不得**匹配别的地区的样本。
     匹配到 ⇒ 同一节点会同时落进两个地区组，两组不再互斥。
  ⑤ 拷贝同步：5 个地区组的正向关键词，必须**全部**出现在 `Other Regions`
     的排除块里。`Other Regions` 是纯负向断言（"排除以上全部"），
     mihomo 的 `filter` 同样不支持引用变量 ⇒ 这份拷贝**在配置层面消灭不掉**。
     漏同步 ⇒ 该节点同时出现在自己的地区组和 `Other Regions`。
  ⑥ 孤儿排除词：`Other Regions` 排除块里的每个词都必须**有出处**
     （某地区组的正向关键词 ∪ 信息节点词 ∪ 机场城市/三字码白名单）。
     无出处 ⇒ 排除得过宽，含该词的节点会从**所有**地区组里消失。
  ⑦ `Other Regions` 自身判别力：必须**收下**真正的其它地区样本（英国 / 德国 / 韩国…），
     且必须**排除**五个主流地区样本与信息节点样本（剩余流量 / 到期 / 官网 / 订阅…）。

⚠️ 待确认（**故意不判负**，只打印）
----------------------------------
下面两处是**实测发现的真实疑点**，但把它们设成判负会让现役配置当场红 ——
而本脚本的第一职责是"现役放行 + fixture 判负"。故按本仓纪律**显式标注、不静默**：

  A. `Other Regions` 里有一批**机场城市名 / 机场三字码**（东京 / 大阪 / NRT / HND / KIX /
     洛杉矶 / 硅谷 / 西雅图 / 纽约 / LAX / SJC / SFO / SEA …），
     它们**只出现在负向排除块里，任何地区组的正向 filter 里都没有**。
     ⇒ 命名为「东京 01」的节点既不进 `Japan`、又被 `Other Regions` 排除 —— **无组可归**。
     （2026-10-07 实测确实如此：`东京 01` / `NRT 03` / `LAX 02` / `硅谷 03` 六组全不匹配。）
     判据 ⑥ 把它们列进白名单（否则现役直接红），但会以 ⚠️ 逐条点名。

⚠️ 反向澄清：地区组的负向半串**是对的**，不要照字面误判
-------------------------------------------------------
负向半串写作 `^((?!(台|日|韩|新|美)).)*$` —— 那个 `.` 在分组**里面**（`)` 之后才 `.*`），
`*` 逐位推进 ⇒ 是**逐字符**排除，能挡住「香港 日本 01」这种双地区命名。
易看错成 `^((?!(…))).*$`（`.` 在分组**外**、只在字符串首位生效）—— 那才是错的写法。
2026-10-07 实测：现役六组对全部 20 个双地区组合样本**零双落组**，故判据 ④
直接把这些组合样本当**判据**跑（不是只靠猜形态），写错形态时它会立刻红。

正则语义（**近似**，待确认）
--------------------------
mihomo 用 Go 的 regexp2，`(?i)` 这类内联 flag 可以出现在**任意位置**、
作用于"所在分组的剩余部分"；Python 的 `re` 不接受非开头的全局 flag。
本脚本的做法是**剥掉所有 `(?i)` 再整条以 `re.IGNORECASE` 编译**：
方向是**略微放宽**（把 `港|HK` 也变成大小写不敏感），对本仓样本无影响，
但对"太宽"判据是**保守**的一侧（更容易报，不会漏报）。
⚠️ 本机无 Go 工具链，未能跑真值对拍 —— 这条近似**待确认**。

退出码：0 = 通过；1 = 有判负；2 = 环境/参数问题（文件缺失 / 解析失败）。

用法：
    python skill/scripts/clash/audit_region_filters.py clash/profiles/routing.yaml
    python skill/scripts/clash/audit_region_filters.py clash/profiles/routing.yaml -v
"""
import argparse
import io
import os
import re
import sys

# 输出编码垫片：Windows cp936 控制台下 print 一个 ✅ 就抛 UnicodeEncodeError，
# 进程以**退出码 1** 结束 —— 而 1 恰是「判负」的码，会被读成"判负其实没跑"。
# ⚠️ 必须是**模块级**执行（写在函数里不调用 = 没保护，本仓 E4 门禁专门抓这个）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

try:
    import yaml
except ImportError:
    print("需要 PyYAML：<venv>/Scripts/python -m pip install pyyaml", file=sys.stderr)
    sys.exit(2)

# ============================================================================
# 常量
# ============================================================================

REGION_GROUPS = ["Hong Kong", "Taiwan", "Japan", "Singapore", "United States"]
OTHER_GROUP = "Other Regions"
ALL_GROUPS = REGION_GROUPS + [OTHER_GROUP]

# 节点来源三件套 —— 任一为真即可把节点拉进组内（缺了则 filter 无米下锅）
SOURCE_KEYS = ("include-all", "include-all-proxies", "include-all-providers")

# 判据 ⑥ 的白名单之一：刻意加在 `Other Regions` 里的「信息节点过滤词」。
# 它们不属于任何地区组，用来排除订阅里的「剩余流量：100GB」这类假节点。
# 与 Surge 侧 `audit_region_filters.py` 的 INFO_WORDS 同源、多两个 mihomo 侧用词。
INFO_WORDS = (
    "剩余", "流量", "到期", "过期", "官网", "订阅", "重置", "续费",
    "Traffic", "Expire", "GB", "倍率", "测试", "有效", "禁止",
    "邮箱", "客服", "地址", "网站", "群组",
)

# 判据 ⑥ 的白名单之二：机场城市名 / 机场三字码。
# 它们只出现在 `Other Regions` 的排除块里、地区组正向 filter 里没有 —— 见头注 ⚠️ A。
GEO_EXTRA_WORDS = (
    "洛杉矶", "硅谷", "西雅图", "纽约", "东京", "大阪",
    "LAX", "SJC", "SFO", "SEA", "ORD", "JFK", "DFW", "IAD", "PHX", "ATL",
    "BOS", "MIA", "NRT", "HND", "KIX", "FUK", "TPE", "SIN",
)

# 判据 ②：每个地区的**必备**关键词（"常见写法"的最低集合）。
# ⚠️ 必备词含**机场三字码与城市名**（对齐姊妹仓写法）。
#    只写国家简称（日/JP/Japan、美/US/States）是不够的 ——
#    那样「东京 01」「NRT 03」「LAX 02」「硅谷 03」会既进不了本地区组、
#    又被 Other Regions 排除 ⇒ **无组可归**（2026-10-07 实测确认的真 bug）。
REQUIRED = {
    "Hong Kong": ("港", "HK", "Hong"),
    "Taiwan": ("台", "TW", "Taiwan", "Tai"),
    "Japan": ("日本", "东京", "大阪", "日", "JP", "Japan",
              "NRT", "HND", "KIX", "FUK", "NGO", "OSA", "CTS", "SDJ", "OKA"),
    "Singapore": ("新加坡", "狮城", "SG", "Singapore"),
    "United States": ("美国", "洛杉矶", "硅谷", "西雅图", "纽约", "美", "US",
                      "States", "America", "LAX", "SJC", "SFO", "SEA",
                      "ORD", "JFK", "DFW", "IAD", "PHX", "ATL", "BOS", "MIA"),
}

# 判据 ③：本地区常见命名，**必须**被本组匹配到。
MUST_MATCH = {
    "Hong Kong": ("香港 01", "Hong Kong 02", "HK-03", "深港 04", "HongKong-05"),
    "Taiwan": ("台湾 01", "台北 02", "TW-03", "Taiwan 04", "TaiPei-05"),
    # 含机场三字码与城市名样本（见 REQUIRED 处的说明）
    "Japan": ("日本 01", "JP-02", "Japan 03", "东京 04", "大阪 05",
              "NRT 06", "HND 07", "KIX 08"),
    "Singapore": ("新加坡 01", "狮城 02", "SG-03", "Singapore 04"),
    "United States": ("美国 01", "US-02", "United States 03", "America 04",
                      "洛杉矶 05", "硅谷 06", "西雅图 07", "LAX 08", "SFO 09"),
}

# 判据 ④：每个地区的**代表命名** —— 其它地区组一律**不得**匹配它。
CANON = {
    "Hong Kong": "香港 01",
    "Taiwan": "台湾 01",
    "Japan": "日本 01",
    "Singapore": "新加坡 01",
    "United States": "美国 01",
}
# 中立地区命名：不属于 5 个主流地区，任何地区组都不该匹配它（它归 `Other Regions`）。
NEUTRAL = "韩国 01"

# 各地区的**代表词**（判据 ⚠️C 用：某组的负向半串应当排除它）
CANON_WORD = {
    "Hong Kong": "港",
    "Taiwan": "台",
    "Japan": "日",
    "Singapore": "新加坡",
    "United States": "美",
}

# 判据 ④ 的第二半：**双地区组合样本**（"香港 日本 01" 这种中转节点命名）。
# ⚠️ 这是判据 ④ 里**真正有判别力**的一半 —— 它实测「负向半串有没有挡住别的地区」；
#    单地区样本只能测"太宽"，测不出"别的地区词出现在**非首位**时还挡不挡得住"。
#    （形态写错成 `^((?!(…))).*$` 时，本样本会让 ④ 当场红 —— 单地区样本不会。）
CROSS_SAMPLES = tuple(
    "%s %s" % (CANON[a].rsplit(" ", 1)[0], CANON[b])   # 如「香港 日本 01」
    for a in REGION_GROUPS for b in REGION_GROUPS if a != b
)

# 判据 ⑦：`Other Regions` 自己的判别力样本。
OTHER_MUST_MATCH = ("英国 01", "德国 02", "韩国 03", "France 04", "莫斯科 05")
OTHER_MUST_NOT = ("香港 01", "台湾 01", "日本 01", "新加坡 01", "美国 01",
                  "剩余流量：100GB", "套餐到期提醒", "官网订阅", "Traffic 1GB")

# 内联 flag：`(?i)` / `(?s)` … —— `(?:` 不受影响（`:` 不是字母，后面也没有紧跟 `)`）
FLAG_RE = re.compile(r"\(\?[a-zA-Z]+\)")

# 前瞻开括号：`(?=` / `(?!`（不误伤 `(?:` / `(?<=`）
LA_OPEN_RE = re.compile(r"\(\?([=!])")

# mihomo 文档：`filter` 里可用 **反引号** 分隔多条正则，命中任一条即算匹配
BACKTICK = "`"


# ============================================================================
# 正则处理
# ============================================================================

def strip_inline_flags(pattern):
    """剥掉内联 flag（mihomo 的 `(?i)` 可出现在任意位置，Python `re` 不接受）。

    剥掉后整条以 `re.IGNORECASE` 编译 —— 详见头注「正则语义（近似，待确认）」。
    """
    return FLAG_RE.sub("", pattern)


def balanced_group(s, i):
    """`s[i] == '('` ⇒ 返回 (分组内容, 配对 `)` 的下标)；不配对返回 (None, -1)。"""
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j
        j += 1
    return None, -1


def split_top_level_alt(s):
    """按**顶层** `|` 切分，`(...)` 内部的 `|` 不切（否则 `(?:深|沪)港` 会被撕碎）。"""
    out, buf, depth = [], [], 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            buf.append(s[i:i + 2])
            i += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "|" and depth == 0:
            out.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf).strip())
    return [t for t in out if t]


def _unwrap_group(body):
    """反复剥掉一层「`.*` 前缀 + 外层括号」，取回真正装关键词的那个分组。

    mihomo 侧三种写法都要认（"剥到最里层"是它们的公共形状）：

        (?=.*(港|HK|Hong))            正向半串      → 港 | HK | Hong
        (?!(台|日|韩|新|美))          地区组负向    → 台 | 日 | 韩 | 新 | 美
        (?!(.*(港|…)))                Other Regions → 港 | …（**套了两层**）

    ⚠️ 不剥这层的话，第三种的 token 会是整个 `.*(港|…)` —— 一个"孤儿词"，
       判据 ⑥ 会把它当成无出处排除词，现役配置当场假红（2026-10-07 实测）。
    返回剥不动为止的 body（可能是整条，也可能是最里层分组的内容）。
    """
    for _ in range(6):
        stripped = re.sub(r"^\.\*\+?\??", "", body.strip())
        if stripped != body.strip():
            body = stripped
            continue
        if body.startswith("("):
            inner, end = balanced_group(body, 0)
            if inner is not None and end == len(body) - 1:
                body = inner
                continue
        break
    return body


def lookahead_tokens(pattern):
    """抽出一条 filter 里所有前瞻的关键词。

    返回 (正向 tokens, 负向 tokens)。同时覆盖三种写法：
      · 正向半串 `(?=.*(港|HK|Hong))`   → 取 `.*` 后那个分组
      · 地区组负向 `^((?!(台|日|韩|新|美))).*$`
      · `Other Regions` 的 `(?!(.*(港|…)))` → 剥两层
    """
    pos, neg = [], []
    for m in LA_OPEN_RE.finditer(pattern):
        content, _ = balanced_group(pattern, m.start())
        if content is None:
            continue
        body = content[2:]                      # 去掉 `?=` / `?!`
        toks = split_top_level_alt(_unwrap_group(body))
        (pos if m.group(1) == "=" else neg).extend(toks)
    return pos, neg


def compile_filter(raw_filter):
    """mihomo `filter` → 可调用的 `match(name)`。

    · 先按反引号切成多条正则（任一条命中即算匹配）；
    · 每条剥掉内联 flag 后以 `re.IGNORECASE` 编译。
    返回 (matcher, error)；error 非 None 时 matcher 恒为 False。
    """
    subs = [s for s in (raw_filter or "").split(BACKTICK) if s.strip()]
    if not subs:
        return (lambda _name: False), "filter 为空"
    compiled = []
    for sub in subs:
        try:
            compiled.append(re.compile(strip_inline_flags(sub), re.IGNORECASE))
        except re.error as e:  # noqa: BLE001
            return (lambda _name: False), "filter 无法编译：%s（片段 `%s`）" % (e, sub[:60])

    def matcher(name):
        return any(r.search(name) for r in compiled)

    return matcher, None


def covers(token_set, word):
    """必备词 `word` 是否被 token 集合覆盖。

    先求**逐字相等**，再退回**大小写不敏感的子串**（`Taiwan` 覆盖 `Tai`、
    `TWN` 覆盖 `TW` —— 判据② 问的是"常见写法有没有被认出来"，不是"字面是否相同"）。
    """
    if word in token_set:
        return True
    low = word.lower()
    return any(low in t.lower() for t in token_set)


# ============================================================================
# 发现收集 + 豁免
# ============================================================================

_OKS = []
_FAILS = []
_NOTES = []          # ⚠️ 待确认（不判负，但必须打印）
_WAIVERS = {}        # 判据号 -> 理由（来自被审对象里的 `# audit-waive:` 行）

# 豁免**必须写在被审对象里**，不能写在审计器里：
#   · 写在审计器里 = 判据被永久削弱，别的 profile 也享受不到这层保护；
#   · 写在 profile 里 = 每一次豁免都在被审对象上留痕、可被 grep、可被复核。
# 豁免不消除打印 —— 它只让该条不再使整轮判负。
_WAIVE_RE = re.compile(r"#\s*audit-waive:\s*(\d+)\s+(.*)")


def load_waivers(text):
    _WAIVERS.clear()
    for m in _WAIVE_RE.finditer(text):
        _WAIVERS[int(m.group(1))] = m.group(2).strip()


def ok(cid, msg):
    _OKS.append((cid, msg))


def fail(cid, msg, detail=""):
    """登记一条判负；该判据号被豁免时降级为 ⚠️ 打印、不计入判负。"""
    if cid in _WAIVERS:
        _OKS.append((cid, "⚠️ 已豁免（profile 内声明）：%s —— %s" % (msg, _WAIVERS[cid])))
        return
    _FAILS.append((cid, msg, detail))


def note(msg):
    _NOTES.append(msg)


# ============================================================================
# 主流程
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description="clash（mihomo）地区组 filter 判别力审计器")
    ap.add_argument("profile", help="mihomo profile YAML 路径")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="打印逐组的正向/负向关键词与比对串")
    a = ap.parse_args()

    if not os.path.isfile(a.profile):
        print("❌ 找不到文件：%s" % a.profile, file=sys.stderr)
        return 2

    try:
        text = io.open(a.profile, encoding="utf-8").read()
        doc = yaml.safe_load(text)
    except Exception as e:  # noqa: BLE001
        print("❌ 无法解析 %s：%s" % (a.profile, e), file=sys.stderr)
        return 2

    if not isinstance(doc, dict):
        print("❌ %s 顶层不是映射（不是一份 mihomo profile）" % a.profile, file=sys.stderr)
        return 2

    load_waivers(text)

    groups = {}
    for g in doc.get("proxy-groups") or []:
        if isinstance(g, dict) and g.get("name"):
            groups[g["name"]] = g

    present = [g for g in ALL_GROUPS if g in groups]
    if not present:
        print("✅ 本 profile 没有「5 个地区组 + Other Regions」结构，无需校验。")
        print("   （懒人版 / 无地区组的配置属预期情形，不判负）")
        return 0

    print("=" * 78)
    print("clash 地区组 filter 判别力审计")
    print("profile: %s" % a.profile)
    print("=" * 78)

    # ── 预处理：每个组的 filter / matcher / 关键词 ────────────────────────────
    info = {}
    for name in ALL_GROUPS:
        body = groups.get(name, {})
        raw = body.get("filter")
        matcher, err = compile_filter(raw) if raw else ((lambda _n: False), "没有 `filter`")
        pos, neg = lookahead_tokens(strip_inline_flags(raw or ""))
        info[name] = {
            "raw": raw, "matcher": matcher, "err": err,
            "pos": pos, "neg": neg,
            "source": [k for k in SOURCE_KEYS if body.get(k)],
        }

    # ── 判据 ① 结构 ──────────────────────────────────────────────────────────
    struct_bad = []
    for name in ALL_GROUPS:
        it = info[name]
        if name not in groups:
            fail(1, "缺少地区组 `%s`" % name)
            struct_bad.append(name)
            continue
        if not it["raw"]:
            fail(1, "地区组 `%s` 没有 `filter`" % name,
                 "没有 filter 就筛不出任何节点 —— 该组恒为空")
            struct_bad.append(name)
            continue
        if it["err"]:
            fail(1, "地区组 `%s` 的 filter 无法编译" % name, it["err"])
            struct_bad.append(name)
            continue
        if not it["source"]:
            fail(1, "地区组 `%s` 没有节点来源开关（%s 之一）" % (name, " / ".join(SOURCE_KEYS)),
                 "成员表为空 ⇒ filter 再对也没有节点可筛，该组恒为空")
            struct_bad.append(name)
    if not struct_bad:
        ok(1, "%d 个地区组结构齐全（filter 在场、可编译、有节点来源开关）" % len(ALL_GROUPS))

    # ── 判据 ② 必备关键词覆盖（不太窄）────────────────────────────────────────
    for name in REGION_GROUPS:
        it = info[name]
        if name in struct_bad:
            continue      # 结构已判负，不再叠加语义判负（否则一处坏 = 满屏红，看不出主因）
        if not it["pos"]:
            fail(2, "`%s` 的 filter 里解析不出正向关键词（`(?=.*(…))` 形态）" % name)
            continue
        miss = [w for w in REQUIRED[name] if not covers(it["pos"], w)]
        if miss:
            fail(2, "`%s` 漏了 %d 个必备关键词：%s" % (name, len(miss), " / ".join(miss)),
                 "含这些词的节点进不了 `%s`，又可能被 `Other Regions` 排除 ⇒ 无组可归" % name)
        else:
            ok(2, "`%s` 必备关键词全覆盖（%s）" % (name, " / ".join(REQUIRED[name])))
        if a.verbose:
            print("        %s 正向词：%s" % (name, " | ".join(it["pos"])))
            print("        %s 负向词：%s" % (name, " | ".join(it["neg"]) or "（无）"))

    # ── 判据 ③ 本地区样本实测（不太窄）────────────────────────────────────────
    for name in REGION_GROUPS:
        it = info[name]
        if name in struct_bad:
            continue
        miss = [s for s in MUST_MATCH[name] if not it["matcher"](s)]
        if miss:
            fail(3, "`%s` 匹配不到本地区样本 %d 个：%s"
                 % (name, len(miss), " / ".join(miss)),
                 "filter 太窄 ⇒ 这些常见命名进不了 `%s`" % name)
        else:
            ok(3, "`%s` 命中全部 %d 个本地区样本" % (name, len(MUST_MATCH[name])))

    # ── 判据 ④ 其它地区样本实测（不太宽）──────────────────────────────────────
    for name in REGION_GROUPS:
        it = info[name]
        if name in struct_bad:
            continue
        # ④-a 单地区代表命名 + 中立地区：本组不该吃
        others = [v for k, v in CANON.items() if k != name] + [NEUTRAL]
        hit = [s for s in others if it["matcher"](s)]
        if hit:
            fail(4, "`%s` 错吃了 %d 个其它地区样本：%s"
                 % (name, len(hit), " / ".join(hit)),
                 "filter 太宽 ⇒ 同一节点会同时落进两个地区组，两组不再互斥")
        else:
            ok(4, "`%s` 不吃任何其它地区样本（%d 个）" % (name, len(others)))

    # ④-b **双地区组合**：每个组合样本**最多落进一个组**（双落组 = 两组不再互斥）。
    #      ⚠️ 判的是"每样本命中组数 ≤ 1"，不是"某组不得命中" ——
    #        后者会把「一个组收下、另一个组排除」的健康情形误判成违规。
    #      （形态若被改成 `^((?!(…))).*$`（只在首位生效），两个组会同时命中
    #        ⇒ 本判据当场红 —— 这就是它对形态的兜底作用。）
    #  ⚠️ 整段只算一次，与 ④-a 的逐组循环**并列**而非嵌套（否则同一条报 5 遍）。
    if not [n for n in REGION_GROUPS if n in struct_bad]:
        cross_bad = []
        for s in CROSS_SAMPLES:
            hit_groups = [g for g in REGION_GROUPS if info[g]["matcher"](s)]
            if len(hit_groups) > 1:
                cross_bad.append("%s（同时落进 %s）" % (s, " + ".join(hit_groups)))
        if cross_bad:
            fail(4, "%d 个双地区组合样本**同时落进多个地区组**：%s"
                 % (len(cross_bad), "；".join(cross_bad)),
                 "负向半串没挡住 ⇒ 中转节点（如「香港 日本 01」）会同时属于两个地区组。"
                 "（若是 `^((?!(…))).*$` 而非 `^((?!(…)).)*$`，就会在这里红）")
        else:
            ok(4, "%d 个双地区组合样本每个最多落进一个地区组" % len(CROSS_SAMPLES))

    # ── 判据 ⑤ 拷贝同步：正向词 ⊆ Other Regions 排除块 ───────────────────────
    neg_other = info[OTHER_GROUP]["neg"]
    neg_set = set(neg_other)
    if OTHER_GROUP in struct_bad:
        pass        # 结构已判负，语义判据不再叠加（同判据 ②/③ 的处理）
    elif not neg_other:
        fail(5, "`%s` 的 filter 里解析不出负向排除块（`(?!(.*(…)))` 形态）" % OTHER_GROUP,
             "解析不出来 = 校验没做，宁可报错也不静默通过")
    else:
        for name in REGION_GROUPS:
            miss = [t for t in info[name]["pos"] if not covers(neg_set, t)]
            if miss:
                fail(5, "`%s` 的负向排除块漏了 `%s` 的 %d 个关键词：%s"
                     % (OTHER_GROUP, name, len(miss), " / ".join(miss)),
                     "这些节点会同时出现在 `%s` 与 `%s`，两组不再互斥" % (name, OTHER_GROUP))
        if not any(cid == 5 for cid, _, _ in _FAILS):
            ok(5, "%d 个地区组的 %d 个正向关键词全部在 `%s` 的排除块里"
               % (len(REGION_GROUPS), sum(len(info[n]["pos"]) for n in REGION_GROUPS),
                  OTHER_GROUP))

    # ── 判据 ⑥ 孤儿排除词 ────────────────────────────────────────────────────
    declared = set()
    for name in REGION_GROUPS:
        declared.update(info[name]["pos"])
    allowed = set(INFO_WORDS) | set(GEO_EXTRA_WORDS)
    orphan = [t for t in neg_other if not covers(declared, t) and t not in allowed] \
        if OTHER_GROUP not in struct_bad else []
    if orphan:
        fail(6, "`%s` 的排除块里有 %d 个无出处（孤儿）关键词：%s"
             % (OTHER_GROUP, len(orphan), " / ".join(orphan)),
             "排除得过宽 ⇒ 含这些词的节点会从**所有**地区组里消失")
    elif neg_other:
        ok(6, "`%s` 的 %d 个排除词全部有出处（地区组正向词 + 信息节点词 + 机场码白名单）"
           % (OTHER_GROUP, len(neg_other)))

    # ⚠️ 待确认 A：只在 Other Regions 里、地区组正向 filter 里没有的词 ⇒ 无组可归
    nowhere = [t for t in neg_other if t in set(GEO_EXTRA_WORDS) and not covers(declared, t)]
    if nowhere:
        note("`%s` 里有 %d 个机场城市名/三字码**只出现在排除块里**、任何地区组的正向 "
             "filter 里都没有：%s\n      ⇒ 命名为这些词的节点既不进自己的地区组、又被 "
             "`%s` 排除 —— **无组可归**。\n      （判据 ⑥ 已把它们列进白名单故不判负；"
             "修法：补进对应地区组的正向半串）"
             % (OTHER_GROUP, len(nowhere), " / ".join(nowhere), OTHER_GROUP))

    # ⚠️ 待确认 C：负向半串的**覆盖不对称** —— 某组的负向半串漏掉了另一个地区的
    #    代表词。单边漏不会造成双落组（对面那组会挡住），故按本仓纪律**只点名不判负**；
    #    但它是真实的脆弱点：一旦对面那组也漏，立刻双落组（判据 ④-b 会红）。
    for name in REGION_GROUPS:
        if name in struct_bad:
            continue
        neg_set = set(info[name]["neg"])
        leak = [k for k in REGION_GROUPS
                if k != name and not covers(neg_set, CANON_WORD[k])]
        if leak:
            note("`%s` 的负向半串没排除 %d 个地区的代表词：%s\n"
                 "      ⇒ 单边漏词暂未造成双落组（对面那组挡住了），但对面若也漏就会双落组。"
                 "（修法：把缺的词补进负向半串）"
                 % (name, len(leak),
                    " / ".join("%s→%s" % (k, CANON_WORD[k]) for k in leak)))

    # ⚠️ 待确认：负向半串的**逐字符**形态（`)` 之后才是 `.*`，`.` 在分组**内**）。
    #    若哪天被改成 `^((?!(…))).*$`（`.` 在分组外、只在首位生效），这里会点名；
    #    但真正的兜底是判据 ④ 的双地区组合**实测** —— 形态改动会让 ④ 当场红。
    anchored = []
    for name in REGION_GROUPS:
        if name in struct_bad:
            continue
        raw = strip_inline_flags(info[name]["raw"] or "")
        if re.search(r"\^\(\(\?!\(", raw) and not re.search(r"\)\)\.\)\*\$", raw):
            anchored.append(name)
    if anchored:
        note("%d 个地区组的负向半串不是 `^((?!(…)).)*$` 的**逐字符**形态（`.` 应在分组**内**、"
             "随 `*` 逐位推进），只在字符串首位生效的写法挡不住「香港 日本 01」这类双地区命名。"
             "涉及：%s" % (len(anchored), " / ".join(anchored)))

    # ── 判据 ⑦ Other Regions 自身判别力 ──────────────────────────────────────
    om = info[OTHER_GROUP]["matcher"]
    if OTHER_GROUP in struct_bad:
        pass        # 结构已判负，语义判据不再叠加
    else:
        miss_in = [s for s in OTHER_MUST_MATCH if not om(s)]
        if miss_in:
            fail(7, "`%s` 收不下 %d 个「其它地区」样本：%s"
                 % (OTHER_GROUP, len(miss_in), " / ".join(miss_in)),
                 "排除得过宽 ⇒ 这些节点会从**所有**组里消失")
        hit_out = [s for s in OTHER_MUST_NOT if om(s)]
        if hit_out:
            fail(7, "`%s` 没排除掉 %d 个本该排除的样本：%s"
                 % (OTHER_GROUP, len(hit_out), " / ".join(hit_out)),
                 "五个主流地区 / 信息节点漏进 `Other Regions` ⇒ 两组不再互斥")
        if not miss_in and not hit_out:
            ok(7, "`%s` 判别力成立：收下 %d 个其它地区样本、排除 %d 个主流地区与信息节点样本"
               % (OTHER_GROUP, len(OTHER_MUST_MATCH), len(OTHER_MUST_NOT)))

    # ── 输出 ────────────────────────────────────────────────────────────────
    print()
    for _cid, msg in _OKS:
        print("   ✅ %s" % msg)
    for cid, msg, detail in _FAILS:
        print("   ❌ [判据 %d] %s" % (cid, msg))
        if detail:
            for ln in detail.splitlines():
                print("        %s" % ln)
    if _NOTES:
        print()
        print("   ⚠️  待确认（不判负，但逐条点名）：")
        for n in _NOTES:
            print("        · %s" % n)

    print()
    print("=" * 78)
    if _FAILS:
        print("❌ %d 条判据不成立：" % len(_FAILS))
        for cid, msg, _d in _FAILS:
            print("      · [判据 %d] %s" % (cid, msg))
        print("=" * 78)
        return 1
    print("✅ 全部通过：%d 条判据成立，%d 个地区组判别力正常。"
          % (len(_OKS), len(ALL_GROUPS)))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
