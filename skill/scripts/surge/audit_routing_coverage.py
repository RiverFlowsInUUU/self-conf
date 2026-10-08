#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分流覆盖审计 —— 拿真实域名把 [Rule] 段从头走一遍，看它最终命中哪条规则。

为什么必须有这个脚本：
    `check_surge_dns.py` 只审文件内部的**结构**（顺序、no-resolve、策略可解析）。
    结构全绿**不等于**分流正确 —— Egern 项目实测过：两个审计脚本双双通过，
    分流却整片是坏的（`ChinaMax.list` 里 99.5% 是 IP，国内域名全落到了 Final → 代理）。

    判据必须是「拿真实域名走一遍」，**不是**「有没有一条叫 China 的规则」，
    也**不是**「规则集名叫 direct.txt」。

它做两件事：
    A. **国内探针**（15 个非 `.cn` 的国内域名 + 若干 `.cn`）必须命中 DIRECT。
       ⚠️ 刻意包含非 `.cn` 的国内域名（`qq.com` / `taobao.com` / `miui.com` …）：
          只有 `.cn` 后缀能直连的配置是**假通过** —— 它靠的是 `DOMAIN-SUFFIX,cn`
          这条兜底，而不是真的接住了国内域名。
    B. **境外探针**（OpenAI / GitHub / Google …）必须命中代理或 AI 组，
       且**绝不能被广告规则误杀**（提前发现误杀比等用户报障好）。
    C. **误杀探针**：广告清单不能把功能域（GitHub / iCloud / Apple 那 8 个）拦掉。
    D. **Apple 探针**：Apple 系统服务域必须直连 —— 懒人版与分流版两套期望
       （懒人版 2026-09-24 起不引用 Apple 规则集，`apps` / `itunes` 那两条归分流版；
        分流版 2026-10-04 起该条由 `Apple_All_No_Resolve.list` 换成 `apple.txt`，
        `developer.apple.com` / `gateway.icloud.com` 随之按设计改走代理，已从期望移出）。
       内置 `SYSTEM` 的内容按本仓快照近似（见 `BUILTIN_SET_SNAPSHOTS`）：早先它是
       "内容不可得 ⇒ 视作不命中"，等于那条规则在审计里根本不存在 —— 现在补上了。

退出码：0 = 全部符合预期；1 = 有探针落错；2 = 用法 / 网络错误。

用法：
    python audit_routing_coverage.py Profile.conf
    python audit_routing_coverage.py Profile.conf --show-all    # 打印全部探针明细
"""

import argparse
import os
import sys
import tempfile
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _surge_common import (  # noqa: E402
    parse_conf,
    policy_index,
    split_csv,
    strip_comment,
)
from audit_ruleset_content import fetch  # noqa: E402

# 仓库定位：靠标志物上溯，不依赖目录层数（见 tools/lib/paths.py）
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../lib'))
from paths import repo_root as _repo_root  # noqa: E402


# 本文件位于 <仓库根>/skill/scripts/surge/ ⇒ 上溯三级即仓库根（不假设 cwd，也不出本仓取文件）
REPO_ROOT = _repo_root()
# ── 探针清单 ────────────────────────────────────────────────────────────────
# ⭐ 国内探针刻意混入**非 .cn** 的域名 —— 这是本脚本的核心判据之一。
#    只靠 `DOMAIN-SUFFIX,cn` 兜住的配置会在这些域名上暴露。
DOMESTIC_PROBES = [
    "www.baidu.com", "www.qq.com", "www.taobao.com", "www.jd.com",
    "www.bilibili.com", "www.163.com", "www.zhihu.com", "www.miui.com",
    "connect.rom.miui.com", "www.aliyun.com", "www.huawei.com",
    "www.iqiyi.com", "www.douyin.com", "www.meituan.com", "www.12306.cn",
    "www.gov.cn", "www.people.com.cn",
]

# 境外探针：期望走代理（不落到 DIRECT）。allow = 允许命中的策略名集合。
#
# ⚠️ 为什么这里要按 profile 分两套期望，而不是放宽成"只要不是 DIRECT 就行"：
#    "不是 DIRECT" 会让一个**整片走兜底**的坏配置假通过 —— 而"整片走兜底"
#    恰恰是 Egern 项目实测踩过的那个坑（国内域名全落到 Final → 代理）。
#    期望值必须精确到**组名**，才能证明「按应用分流」真的接住了对应域名。
#
#    两套期望的差别只在于组名：lazy.conf 只有一个 AI 组，
#    routing.conf（分流版，当前版本号见头注）把它拆成了 ChatGPT / Gemini / Claude / AI 四个组，
#    并把 Spotify / YouTube / GitHub / Google / Microsoft / Telegram / Twitter
#    这些也各自单列。
#    ⚠️ 这不是"顺手放宽"—— 它是**分流版新增能力**的验收条件：
#       chat.openai.com 必须落进 ChatGPT，而不只是"随便落进某个代理组"。
#       如果只看"不是 DIRECT"，把四个组全指向 Proxy 也能假过。
FOREIGN_PROBES = {
    "chat.openai.com": {"AI", "PROXY"},
    "api.anthropic.com": {"AI", "PROXY"},
    "gemini.google.com": {"AI", "PROXY"},
    "github.com": {"PROXY"},
    "www.google.com": {"PROXY"},
    "www.youtube.com": {"PROXY"},
    "t.me": {"PROXY"},
    "x.com": {"PROXY"},
}

# 分流版（routing.conf，当前版本号见头注）—— 精确到应用组名。
#
# ⚠️ 这张表的作用是**反向证明「按应用分流」真的接住了域名**：
#    每个探针必须落进它**专属**的那个组，落到兜底（Final）就算失败。
#    曾经有 6 个探针是期望 FINAL 的（那时本版确实没有 Spotify / Google /
#    YouTube / Telegram / Twitter / GitHub 这些组）—— 这恰恰就是漏了分流的证据。
#    补齐这些组之后，期望值同步收紧到专属组名，防止将来有人删组而无人发现。
FOREIGN_PROBES_ROUTING = {
    "chat.openai.com":   {"CHATGPT"},
    "api.anthropic.com": {"CLAUDE"},
    "gemini.google.com": {"GEMINI"},
    "github.com":        {"PROXY"},
    "www.google.com":    {"GOOGLE"},
    "www.youtube.com":   {"YOUTUBE"},
    "t.me":              {"TELEGRAM"},
    "x.com":             {"TWITTER"},
}


def foreign_expectations(path):
    """按 profile 选择境外探针的期望表。

    判据是**文件里实际定义了哪些组**，不是文件名 ——
    这样即使有人把分流版改名，期望仍然正确。
    """
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return FOREIGN_PROBES
    sections, _ = parse_conf(path)
    names = set()
    for _ln, raw in sections.get("proxy group", []):
        s = strip_comment(raw)
        if s and "=" in s:
            names.add(s.split("=", 1)[0].strip().upper())
    # 分流版的标志：存在 ChatGPT / Claude 这类应用级组
    if {"CHATGPT", "CLAUDE"} & names:
        return FOREIGN_PROBES_ROUTING
    return FOREIGN_PROBES

# ⭐ 误杀探针：这些域名**一定不能**被广告规则拦。
#    它们几乎必然出现在广告黑名单的误杀面里（Egern 项目的 jinx-surge-direct
#    —— 2026-10-04 前名 jinx-surge-white-guard —— 就是为它们准备的）。
FALSE_POSITIVE_PROBES = [
    "github.com", "objects.githubusercontent.com", "cdn.jsdelivr.net",
    "www.icloud.com", "gateway.icloud.com", "swcdn.apple.com",
    "www.apple.com", "api.github.com",
]

# ⭐ Apple 探针：这些是**必须直连**的 Apple 服务域。
#    ⚠️ 判据意义：Apple 流量走代理**不会报错**，只会「变慢 + 偶尔推送延迟」——
#       属于用户不会主动报障、但体验确实变差的一类。所以要靠审计钉住。
#       当年 Egern 把这条规则集写成不带 no-resolve 的版本，泄露就是从这类"看不见的解析"来的。
#    两套期望的差别只在**懒人版 2026-09-24 起不引用 Apple 规则集**：
#      · `courier.push.apple.com` 与 `gs-loc.apple.com` 由内置 `SYSTEM` 接住
#        （`push.apple.com` 是后缀条目、`gs-loc` 是精确条目 —— 见 BUILTIN_SET_SNAPSHOTS）；
#      · `www.apple.com` 由 `direct.txt` 的 Apple 精确条目接住；
#      · `apps.apple.com` / `itunes.apple.com` **只有**分流版那条 Apple 规则集里有 ⇒ 归分流版。
#        懒人版按设计让这类走代理（写进 lazy.conf §4 的取舍里），所以不进懒人版期望。
#      · `swcdn.apple.com` **2026-10-06 起从本表移出**：它同时被 `SystemOTA.list` 收录 ⇒
#        在分流版命中 `Apple Update` 组（默认 DIRECT），改由 `APPLE_OTA_PROBES` 断言。
#        ⚠️ 懒人版无 `Apple Update` 组 ⇒ 它仍命中 `SYSTEM` → `DIRECT`，与旧期望一致。
#    ⚠️ 2026-10-04 换源（`Apple_All_No_Resolve.list` -> `apple.txt`，1,616 条 -> 165 条纯域名）：
#       `apple.txt` 只含「在中国大陆可直连」的域，原先靠全量集才直连的 `developer.apple.com` /
#       `gateway.icloud.com`（连同国际版 iCloud 端点、`apple-cloudkit.com`、裸 `apple.com`）
#       **按设计改走代理** ⇒ 已从 ROUTING 期望里移出。要改回直连就得另补 `icloud.txt` 之类。
APPLE_PROBES_ROUTING = [
    "www.apple.com", "gs-loc.apple.com",
    "courier.push.apple.com", "apps.apple.com", "itunes.apple.com",
]
APPLE_PROBES_LAZY = [
    "www.apple.com", "gs-loc.apple.com", "courier.push.apple.com",
]
APPLE_PROBES = APPLE_PROBES_ROUTING          # t5-keep: 「兼容旧提法」的别名，删否由维护者点名（本仓无人用这个旧提法）

# ⭐ OTA 探针（2026-10-06 立）：这些是 `SystemOTA.list` 独有的系统更新域，
#    必须命中 `Apple Update` 组（而不是 DIRECT、也不是被广告规则 REJECT）。
#    ⚠️ **仅分流版启用**（2026-10-06 定）：`Apple Update` 组只在分流版提供，
#       懒人版无此组，它的 OTA 域名由 `SYSTEM` 接成 `DIRECT` ⇒ 对懒人版跑本组必红。
#    ⚠️ 为什么要单立：分流版位 ④ 的 `SystemOTA` 必须排在位 ⑤ 的 `SYSTEM` **之前** ——
#       两集有 3 条重叠（`configuration` / `mesu` / `xp` .apple.com），`SYSTEM` 会把它们接成
#       `DIRECT`。顺序一旦被改回去（比如有人又把系统域“置顶”），`Apple Update` 组就静默失效。
#       `swcdn.apple.com` 就是这样的探针：它同时被 `SystemOTA.list` 与 `apple.txt` 收录，
#       在旧顺序下命中 `SYSTEM`/`apple.txt` 判 DIRECT（**旧期望就是这么写的**）。
#    ⇒ 判据：命中策略必须等于 `Apple Update`（组名硬断言）。
APPLE_OTA_PROBES = [
    "swcdn.apple.com", "mesu.apple.com", "xp.apple.com", "ocsp.apple.com",
]
OTA_GROUP = "APPLE UPDATE"


def ota_probes_for(path):
    """分流版才有 `Apple Update` 组 ⇒ 懒人版返回空表（不判该项）。

    判据与 `foreign_expectations` 同源：**看文件里实际定义了哪些组**，不看文件名 ——
    这样即使有人把分流版改名，期望仍然正确。
    """
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    sections, _ = parse_conf(path)
    for _ln, raw in sections.get("proxy group", []):
        s = strip_comment(raw)
        if s and "=" in s and s.split("=", 1)[0].strip().upper() == OTA_GROUP:
            return APPLE_OTA_PROBES
    return []


def apple_probes_for(path):
    """按 profile 里实际定义了哪些组，选 Apple 探针表（判据在文件里，不在文件名里）。"""
    return APPLE_PROBES_LAZY if foreign_expectations(path) is FOREIGN_PROBES else APPLE_PROBES_ROUTING


# ── 内置规则集的本地时点快照 ────────────────────────────────────────────────
# Surge 的内置集合（`SYSTEM` / `LAN`）没有可下载的 URL，早先的模拟器只能"视作不命中"
# —— 那是**已知的仿真盲区**：`RULE-SET,SYSTEM,DIRECT` 这条规则在审计里等于不存在。
# 现在 `SYSTEM` 的内容有了一份本仓自维护的快照（给 Egern 用的那份，两者内容同源），
# 借它把这个盲区补上：SYSTEM 参与的判定从此可测。
# ⚠️ 快照是**时点**内容，Surge 内置集会随版本变；对不上时以 Surge 客户端里的实际列表为准。
#    找不到快照时退回旧行为（视作不命中）并打印一行提示，不静默。
BUILTIN_SET_SNAPSHOTS = {
    "SYSTEM": os.path.join(REPO_ROOT, "rules", "apple_system.list"),
    # ⚠️ 2026-10-04 修：原先写的是 `egern/apple_system.list` —— 那份 2026-09-27 已提升到顶层
    #    `rules/`（见 rulesets.md「只有一侧有的」）。旧路径 `os.path.isfile` 恒为假 ⇒ 这段
    #    「借快照补上 SYSTEM 盲区」的机制自搬家起就一直静默退回旧行为（SYSTEM 视作不命中），
    #    连注释里「现在补上了」都不成立。由换 Apple 规则集时 D 组探针报错暴露。
}


class Matcher:
    """按 [Rule] 段顺序，对给定域名逐条判定。"""

    def __init__(self, profile_path, cache_dir):
        self.cache = cache_dir
        sections, _ = parse_conf(profile_path)
        self.rules = []
        for lineno, raw in sections.get("rule", []):
            s = strip_comment(raw)
            if not s:
                continue
            parts = split_csv(s)
            if not parts:
                continue
            t = parts[0].strip().upper()
            pi = policy_index(parts)
            pol = parts[pi].strip() if pi is not None and len(parts) > pi else "?"
            arg = parts[1].strip() if len(parts) > 1 else ""
            self.rules.append({"lineno": lineno, "type": t, "arg": arg,
                               "policy": pol, "parts": parts})
        # [Proxy Group] 的组名，按文件出现顺序（Z0 对齐检查用）
        self.group_names = []
        for _ln, raw in sections.get("proxy group", []):
            s = strip_comment(raw)
            if not s or "=" not in s:
                continue
            nm, rhs = s.split("=", 1)
            parts = split_csv(rhs)
            if parts and parts[0].strip().lower() in ("select", "smart", "external"):
                self.group_names.append(nm.strip())
        self._sets = {}          # ident -> {"DOMAIN": set(), "SUFFIX": set(), ...}

    # -- 规则集懒加载 ---------------------------------------------------------
    def _load_set(self, ident):
        if ident in self._sets:
            return self._sets[ident]
        store = {"DOMAIN": set(), "DOMAIN-SUFFIX": set(), "DOMAIN-KEYWORD": set(),
                 "DOMAIN-WILDCARD": set()}
        if "/" not in ident and "." not in ident:
            snap = BUILTIN_SET_SNAPSHOTS.get(ident.upper())
            if not (snap and os.path.isfile(snap)):
                if snap:
                    # 登记了快照却找不到文件 = 配置漂移（文件被搬走/改名）⇒ 会静默失明。
                    # 必须喊出来：2026-09-27 快照搬到 rules/ 后，这里一直按"不命中"跑了七天。
                    print(f"   ⚠️  内置集合 {ident} 的快照不存在："
                          f"{os.path.relpath(snap, REPO_ROOT)} ⇒ 本集合按不命中处理",
                          file=sys.stderr)
                # 未登记快照的内置集合（`LAN`）一直是"视作不命中"的口径，不打印以免变噪音。
                self._sets[ident] = store
                return store
            with open(snap, encoding="utf-8", errors="replace") as f:
                text = f.read()
            print(f"   ℹ️  内置集合 {ident} 按本仓快照近似判定：{os.path.relpath(snap, REPO_ROOT)}")
        else:
            try:
                text, _ = fetch(ident, self.cache)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
                print(f"   ⚠️  规则集下载失败 {ident.split('/')[-1]}：{e}", file=sys.stderr)
                self._sets[ident] = store
                return store
        for ln, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#") or s.startswith(";") or s.startswith("//"):
                continue
            p = [x.strip() for x in s.split(",")]
            tt = p[0].upper()
            val = p[1] if len(p) > 1 else ""
            if tt == "DOMAIN":
                store["DOMAIN"].add(val.lower())
            elif tt == "DOMAIN-SUFFIX":
                store["DOMAIN-SUFFIX"].add(val.lower())
            elif tt == "DOMAIN-KEYWORD":
                store["DOMAIN-KEYWORD"].add(val.lower())
            elif tt == "DOMAIN-WILDCARD":
                store["DOMAIN-WILDCARD"].add(val.lower())
            elif "," not in s:
                store["DOMAIN-SUFFIX"].add(s.lower())
        self._sets[ident] = store
        return store

    # -- 单条规则的匹配 -------------------------------------------------------
    @staticmethod
    def _suffix_hit(domain, suffix):
        d, sf = domain.lower(), suffix.lower().lstrip(".")
        return d == sf or d.endswith("." + sf)

    def _domain_in_store(self, store, domain):
        d = domain.lower()
        if d in store["DOMAIN"]:
            return True
        for sf in store["DOMAIN-SUFFIX"]:
            if self._suffix_hit(d, sf):
                return True
        for kw in store["DOMAIN-KEYWORD"]:
            if kw in d:
                return True
        for w in store["DOMAIN-WILDCARD"]:
            # Surge 通配：`*` 跨点、`?` 单字符 —— 转成正则保守实现
            import re as _re
            pat = "^" + _re.escape(w).replace(r"\*", ".*").replace(r"\?", ".") + "$"
            if _re.match(pat, d):
                return True
        return False

    def match(self, domain):
        """返回命中的规则 dict，或 None（没有任何规则命中）。"""
        for r in self.rules:
            t, arg = r["type"], r["arg"]
            if t == "RULE-SET":
                store = self._load_set(arg)
                if self._domain_in_store(store, domain):
                    return r
            elif t == "DOMAIN":
                if domain.lower() == arg.lower():
                    return r
            elif t == "DOMAIN-SUFFIX":
                if self._suffix_hit(domain, arg):
                    return r
            elif t == "DOMAIN-KEYWORD":
                if arg.lower() in domain.lower():
                    return r
            elif t == "DOMAIN-WILDCARD":
                import re as _re
                pat = "^" + _re.escape(arg).replace(r"\*", ".*").replace(r"\?", ".") + "$"
                if _re.match(pat, domain.lower()):
                    return r
            elif t == "FINAL":
                return r
            # IP 类 / URL-REGEX / USER-AGENT 等无法用"域名"判定 —— 跳过
        return None


def main():
    ap = argparse.ArgumentParser(description="分流覆盖审计（真实域名走一遍）")
    ap.add_argument("profiles", nargs="+", help="Surge .conf 文件路径（可多个）")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--show-all", action="store_true", help="打印全部探针明细")
    a = ap.parse_args()

    for p in a.profiles:
        if not os.path.isfile(p):
            print(f"❌ 找不到文件：{p}", file=sys.stderr)
            return 2
    if len(a.profiles) > 1:
        worst = 0
        for p in a.profiles:
            print(f"\n{'=' * 78}\n◆ {p}\n{'=' * 78}")
            worst = max(worst, _run_one(p, a))
        return worst
    a.profile = a.profiles[0]
    return _run_one(a.profile, a)


def _run_one(profile, a):
    cache = a.cache_dir or os.path.join(tempfile.gettempdir(), "surge-ruleset-cache")
    print(f"规则集缓存：{cache}")
    m = Matcher(profile, cache)
    print(f"[Rule] 段共 {len(m.rules)} 条规则\n")

    fails = []

    # ── Z0. 应用段「组顺序 ↔ 规则顺序」一致性（2026-10-05 立 · 同日修正）────────
    # 为什么单立一条：两个列表由不同的手维护（组顺序看面板体验、规则顺序看匹配优先级），
    # 极易各改各的 —— 2026-10-05 实测就漂了 4 处（Google/YouTube/Telegram/Spotify）。
    #
    # ⚠️ 判据修正（2026-10-05，用户实测指出）：**规则顺序不能要求与组顺序严格逐位相同**。
    #    某些规则集之间存在**包含关系**，被包含者必须**前置**，否则永远轮不到它：
    #    实例：`YouTube.list`（190 条）**内含** `YouTubeMusic.list` 的 UA 规则
    #    （`USER-AGENT,*YouTubeMusic*` 等）⇒ YouTube Music 必须排在 YouTube **之前**，
    #    而它的组在面板上排在 YouTube **之后** —— 两者**本就不该相同**。
    #    ⇒ 判据改为：**组顺序必须是规则顺序的子序列**（规则可把某些组提前，但不得打乱
    #       其余组的相对先后）。这样既能抓住「各改各的」造成的乱序，又容许必要的前置。
    #
    # 豁免：`Proxy`（总入口，被 GitHub 规则指向，但不是自己的规则）、
    #       `AD`（广告拦截组，规则在 ③④ 位、属白名单/黑名单段，不属应用段）。
    EXEMPT = {"PROXY", "AD"}
    app_groups = [g for g in m.group_names if g.upper() not in EXEMPT]
    rule_pols = []
    for r in m.rules:
        if r.get("type") == "RULE-SET":
            p_ = (r.get("policy") or "").strip()
            if p_ and p_ not in rule_pols:
                rule_pols.append(p_)
    seq = [p_ for p_ in rule_pols if p_ in app_groups]
    gseq = [g for g in app_groups if g in seq]

    print("── Z0 · 应用段「组顺序 ↔ 规则顺序」一致性")
    # 「前移」= 该组的规则位置早于它的组位置（规则集包含关系所致，合法）。
    promoted = {g for g in gseq if seq.index(g) < gseq.index(g)}
    # 去掉被前移的组后，两个列表必须**完全相同**（其余组的相对先后不得乱）。
    g_rest = [g for g in gseq if g not in promoted]
    s_rest = [g for g in seq if g not in promoted]
    if g_rest == s_rest:
        if promoted:
            print(f"   ✅ 其余 {len(g_rest)} 个应用组顺序一致（{len(gseq)} 组）")
            print(f"      ℹ️  规则被**前移**的组：{'、'.join(sorted(promoted))}"
                  f" —— 组在面板上排在后面，规则因**规则集包含关系**必须提前")
        else:
            print(f"   ✅ {len(gseq)} 个应用组逐位对齐")
    else:
        print("   ❌ 有组的相对先后被打乱（既非对齐、也非规则集包含所致的前移）：")
        for i in range(max(len(g_rest), len(s_rest))):
            a_ = g_rest[i] if i < len(g_rest) else "—"
            b_ = s_rest[i] if i < len(s_rest) else "—"
            print(f"      {i+1:>2}. 组 {a_:<16} | 规则 {b_:<16} {'✅' if a_==b_ else '❌'}")
        print("   ⇒ 修法：让 [Rule] 应用段的先后与 [Proxy Group] 同名组的先后一致；")
        print("      仅当某规则集**包含**另一规则集的条目时，被包含者才可前移（如 YouTubeMusic 之于 YouTube）。")
        fails.append(("应用段顺序", "组/规则相对顺序不一致", None))

    # ── A. 国内探针必须 DIRECT ──────────────────────────────────────────────
    print("── A · 国内探针（期望命中 DIRECT）")
    ok_dom = 0
    for d in DOMESTIC_PROBES:
        r = m.match(d)
        pol = r["policy"] if r else "（无规则命中）"
        if pol.strip().upper() == "DIRECT":
            ok_dom += 1
            if a.show_all:
                print(f"   ✅ {d:<32} → {pol}   (第 {r['lineno']} 行 {r['type']})")
        else:
            fails.append((d, pol, r))
            print(f"   ❌ {d:<32} → {pol}   "
                  f"(第 {r['lineno'] if r else '—'} 行 {r['type'] if r else '—'})")
    print(f"   {ok_dom}/{len(DOMESTIC_PROBES)} 命中 DIRECT\n")

    # ── B. 境外探针不能落 DIRECT ────────────────────────────────────────────
    expectations = foreign_expectations(profile)
    print("── B · 境外探针（期望走对应应用组 / 代理组，不能落 DIRECT）")
    ok_for = 0
    for d, allow in expectations.items():
        r = m.match(d)
        pol = r["policy"] if r else "（无规则命中）"
        if pol.strip().upper() in allow:
            ok_for += 1
            if a.show_all:
                print(f"   ✅ {d:<32} → {pol}")
        else:
            fails.append((d, pol, r))
            print(f"   ❌ {d:<32} → {pol}（期望 {sorted(allow)}）")
    print(f"   {ok_for}/{len(expectations)} 符合预期\n")

    # ── C. 误杀探针不能被广告规则拦 ─────────────────────────────────────────
    print("── C · 误杀探针（绝不能命中 REJECT）")
    ok_fp = 0
    for d in FALSE_POSITIVE_PROBES:
        r = m.match(d)
        pol = r["policy"] if r else "（无规则命中）"
        if pol.strip().upper().startswith("REJECT"):
            fails.append((d, pol, r))
            print(f"   ❌ {d:<32} → {pol}（被广告规则误杀！）")
        else:
            ok_fp += 1
            if a.show_all:
                print(f"   ✅ {d:<32} → {pol}")
    print(f"   {ok_fp}/{len(FALSE_POSITIVE_PROBES)} 未被误杀\n")

    # ── D. Apple 探针必须 DIRECT ────────────────────────────────────────────
    print("── D · Apple 探针（期望命中 DIRECT）")
    ok_ap = 0
    apple_probes = apple_probes_for(profile)
    for d in apple_probes:
        r = m.match(d)
        pol = r["policy"] if r else "（无规则命中）"
        if pol.strip().upper() == "DIRECT":
            ok_ap += 1
            if a.show_all:
                print(f"   ✅ {d:<32} → DIRECT   (第 {r['lineno']} 行 {r['type']})")
        else:
            fails.append((d, pol, r))
            print(f"   ❌ {d:<32} → {pol}（Apple 服务应直连）")
    print(f"   {ok_ap}/{len(apple_probes)} 命中 DIRECT\n")

    # ── E. OTA 探针必须命中 `Apple Update` 组（2026-10-06 立）────────────────
    #    守住分流版位 ④ 在 `SYSTEM` 之前这个顺序：改回去就静默失效（详见 APPLE_OTA_PROBES 注释）。
    #    ⚠️ 懒人版无 `Apple Update` 组 ⇒ 本组为空，不参与计数与判定。
    ota_probes = ota_probes_for(profile)
    if ota_probes:
        print(f"── E · OTA 探针（期望命中 `Apple Update` 组）")
        ok_ota = 0
        for d in ota_probes:
            r = m.match(d)
            pol = r["policy"] if r else "（无规则命中）"
            if pol.strip().upper() == OTA_GROUP:
                ok_ota += 1
                if a.show_all:
                    print(f"   ✅ {d:<32} → {pol}   (第 {r['lineno']} 行)")
            else:
                fails.append((d, pol, r))
                print(f"   ❌ {d:<32} → {pol}（期望 `Apple Update`；"
                      f"若成了 DIRECT 说明 `SystemOTA` 被排到 `SYSTEM` 之后）")
        print(f"   {ok_ota}/{len(ota_probes)} 命中 `Apple Update`\n")
    else:
        print("── E · OTA 探针 —— 本 profile 无 `Apple Update` 组（懒人版），跳过\n")

    print("─" * 62)
    total = (len(DOMESTIC_PROBES) + len(expectations)
             + len(FALSE_POSITIVE_PROBES) + len(apple_probes) + len(ota_probes) + 1)   # +1 = Z0 对齐检查
    print(f"result: {total - len(fails)} passed, {len(fails)} failed")
    if fails:
        print("❌ 未通过")
        return 1
    print("✅ 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
