#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 Egern profile 的**分流覆盖**：给一批域名，看它们按规则顺序实际会落到哪条规则、哪个策略。

为什么必须有这个脚本
--------------------
`check_egern_dns.py` 只看 DNS 面，`audit_ruleset_noresolve.py` 只看"会不会强制解析"。
两者都看不见**路由本身对不对**。本项目第三类事故（2026-09-19 f8）正是栽在这里：

    f7 给 `geoip: CN` 加 `no_resolve: true` 治好了 DNS 泄露（官方语义：不再触发解析），
    但这同时让 geoip **不再匹配域名** —— 而那条 geoip 恰恰是原配置里
    "国内域名走直连"的唯一机制（收到域名 → 强制解析 → 判出 CN IP → DIRECT）。
    本该补位的 ChinaMax 规则兜不住：按 blackmatrix7 自己的 README，
    `ChinaMax.list` 只是 **IP 规则集**（实测 12614 条里 12472 条 IP-CIDR，域名只有 64 条），
    域名规则在同目录的 `ChinaMax_Domain.list` 里，两条"共同使用"。
    ⇒ 现象：「ChinaMax 里基本只有一些 IP 走直连，国内域名基本都走 final」。

结论：**修 DNS 泄露的动作会悄悄改掉分流**。凡是动了 `no_resolve` 或替换了规则集，
都必须复跑本脚本，对一批真实域名验证"命中规则 + 策略"。

用法
----
    python audit_routing_coverage.py profile.yaml
    python audit_routing_coverage.py profile.yaml --domain www.baidu.com --domain x.com
    python audit_routing_coverage.py profile.yaml --offline      # 只用规则集缓存

内置默认探针域名分两类（国内 / 境外），零命中率会直接暴露"国内域名整片落 default"。

退出码：0 = 所有国内探针都命中 DIRECT 类策略；1 = 有国内探针落到代理/兜底。
"""
import argparse
import io
import os
import re
import sys
# 输出编码垫片：见 _egern_common.force_utf8_stdout —— GBK 控制台下 emoji 会崩成退出码 1
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _egern_common import (  # noqa: E402
    CACHE_MAX_AGE,
    fetch_cached,
    force_utf8_stdout,
)
from fnmatch import fnmatch

try:
    import yaml
except ImportError:
    print("需要 PyYAML：<venv>/Scripts/python -m pip install pyyaml", file=sys.stderr)
    sys.exit(2)

# 缓存目录与 7 天新鲜度窗口的**本体**都在 _egern_common.fetch_cached（2026-09-24 三份手抄收编到那一处）；
# CACHE_MAX_AGE 只留给末尾那行人读的窗口读数。

# 国内探针：全部是 .com/.net 等**不以 .cn 结尾**的常见站，专门用来暴露
# 「.cn 兜底掩盖了国内域名无覆盖」这种假象。
CN_PROBES = [
    "www.baidu.com", "www.taobao.com", "www.jd.com", "www.bilibili.com",
    "www.zhihu.com", "weibo.com", "www.163.com", "www.qq.com",
    "www.douyin.com", "www.iqiyi.com", "www.meituan.com", "www.xiaohongshu.com",
    "www.alipay.com", "www.12306.cn", "www.gov.cn",
]
FOREIGN_PROBES = [
    "www.google.com", "www.youtube.com", "github.com", "x.com",
    "api.openai.com", "www.netflix.com", "www.wikipedia.org",
]
DOMAIN_TYPES = ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX", "DOMAIN-WILDCARD")

# 按 URL 去重记缓存来源：同一个规则集在【一】和【二】两趟里都会被取到，不去重会把"几个
# 规则集来自缓存"这个数报成访问次数。
CACHE_SOURCES = {}


def _note(url, source):
    CACHE_SOURCES.setdefault(url, source)


def fetch(url, offline=False):
    """取规则集正文，带缓存新鲜度窗口 —— 窗口判据本体在 `_egern_common.fetch_cached`。
    缓存过窗口时**先试着重下**，重下失败才退回旧那份并出声（`stale`）——
    静默拿陈旧规则集判"国内域名有覆盖"是本脚本最坏的一种假绿。
    """
    body, path, source, _detail = fetch_cached(url, offline,
                                               user_agent="egern-routing-audit/1.0", timeout=90)
    if source == "stale":
        name = os.path.basename(path)
        print(f"⚠️  {name}：缓存已过 {CACHE_MAX_AGE // 86400} 天窗口"
              + ("，--offline 不重下 ⇒ 按陈旧那份判" if offline else "且重下失败 ⇒ 退回过期那份"))
    _note(url, "fail" if source == "error" else source)
    return body


def rule_set_domains(url, offline=False):
    """把远程规则集解析成 [(类型, 值)]，只保留域名类条目；返回 (域名条目, IP类条目, 缺no-resolve数)"""
    body = fetch(url, offline)
    if body is None:
        return None
    doms, ip, missing = [], 0, 0
    for raw in body.split("\n"):
        l = raw.strip()
        if not l or l.startswith(("#", "//", ";")):
            continue
        if l.startswith("- "):          # Clash YAML payload
            l = l[2:].strip().strip("'\"")
        if "," not in l and l.startswith("."):    # 裸域名（QuantumultX / Egern 写法）
            l = "DOMAIN-SUFFIX," + l.lstrip(".")
        parts = [p.strip() for p in l.split(",")]
        t = parts[0].upper()
        if t in DOMAIN_TYPES:
            doms.append((t, parts[1] if len(parts) > 1 else ""))
        elif t.startswith("IP-") or t in ("GEOIP",):
            ip += 1
            if "no-resolve" not in l.lower():
                missing += 1
    return doms, ip, missing


def dom_match(t, pat, host):
    host = host.lower()
    pat = pat.lower()
    if not pat:
        return False
    if t == "DOMAIN":
        return host == pat
    if t == "DOMAIN-SUFFIX":
        p = pat.lstrip("*.")
        return host == p or host.endswith("." + p)
    if t == "DOMAIN-KEYWORD":
        return pat in host
    if t == "DOMAIN-REGEX":
        try:
            return re.search(pat, host) is not None
        except re.error:
            return False
    if t == "DOMAIN-WILDCARD":
        return fnmatch(host, pat)
    return False


def first_hit(doc, host, sets_cache, offline):
    """按 Egern 语义走一遍 rules，返回 (序号, 规则描述, 策略) 或 (None,'无','-')"""
    rules = doc.get("rules") or []
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            continue
        for t, b in r.items():
            if not isinstance(b, dict):
                continue
            if b.get("disabled"):
                continue
            if t == "default":
                return i, "default(兜底)", b.get("policy")
            m = str(b.get("match") or "")
            if t in ("domain", "domain_suffix", "domain_keyword", "domain_regex", "domain_wildcard"):
                if dom_match({"domain": "DOMAIN", "domain_suffix": "DOMAIN-SUFFIX",
                              "domain_keyword": "DOMAIN-KEYWORD", "domain_regex": "DOMAIN-REGEX",
                              "domain_wildcard": "DOMAIN-WILDCARD"}[t], m, host):
                    return i, f"{t}:{m}", b.get("policy")
            elif t in ("rule_set", "proxy_rule_set") and m.startswith("http"):
                if m not in sets_cache:
                    sets_cache[m] = rule_set_domains(m, offline)
                got = sets_cache[m]
                if got:
                    for dt, dv in got[0]:
                        if dom_match(dt, dv, host):
                            return i, f"rule_set({m.rstrip('/').split('/')[-1]}):{dv}", b.get("policy")
    return None, "无", "-"


def main():
    ap = argparse.ArgumentParser(description="审计 Egern profile 的分流覆盖（域名 → 命中规则 → 策略）")
    ap.add_argument("profiles", nargs="+")
    ap.add_argument("--domain", action="append", default=[], help="追加探针域名，可重复")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    # 多文件：逐个跑，取最坏退出码（与「每文件各开一道闸门」等价）
    if len(a.profiles) > 1:
        worst = 0
        for p in a.profiles:
            print("\n%s\n◆ %s\n%s" % ("=" * 78, p, "=" * 78))
            worst = max(worst, _run_one(p, a))
        return worst
    return _run_one(a.profiles[0], a)


def _run_one(profile, a):
    doc = yaml.safe_load(io.open(profile, encoding="utf-8"))
    cache = {}

    # ---- Z0：应用段「组顺序 ↔ 规则顺序」必须逐位对齐（2026-10-05 立）----
    # 同 Surge 侧：两个列表由不同的手维护，极易各改各的。豁免 `Proxy`（总入口）与
    # `AD`（广告拦截组，规则在 ③④ 位、属白名单/黑名单段，不属应用段）。
    EXEMPT = {"PROXY", "AD"}
    app_groups = [list(g.values())[0]["name"] for g in (doc.get("policy_groups") or [])
                  if list(g.values())[0]["name"].upper() not in EXEMPT]
    rule_pols = []
    for r in (doc.get("rules") or []):
        if "rule_set" in r:
            pol = (r["rule_set"].get("policy") or "").strip()
            if pol and pol not in rule_pols:
                rule_pols.append(pol)
    seq = [x for x in rule_pols if x in app_groups]
    gseq = [g for g in app_groups if g in seq]
    print()
    print("【Z0】应用段「组顺序 ↔ 规则顺序」对齐")
    print("-" * 100)
    # ⚠️ 判据（2026-10-05 修正，同 Surge 侧）：**规则可前移，但不得乱序**。
    #    某些规则集**包含**另一集的条目（如 `YouTube.list` 内含 `YouTubeMusic.list` 的
    #    UA 规则）⇒ 被包含者必须前置，否则永远轮不到；而它的组在面板上排在后面。
    #    ⇒ 剔除「被前移的组」后，两个列表必须完全相同。
    promoted = {g for g in gseq if seq.index(g) < gseq.index(g)}
    g_rest = [g for g in gseq if g not in promoted]
    s_rest = [g for g in seq if g not in promoted]
    if g_rest == s_rest:
        if promoted:
            print(f"  ✅ 其余 {len(g_rest)} 个应用组顺序一致（{len(gseq)} 组）")
            print(f"     ℹ️  规则被**前移**的组：{'、'.join(sorted(promoted))}"
                  f" —— 因规则集包含关系，规则必须提前")
        else:
            print(f"  ✅ {len(gseq)} 个应用组逐位对齐")
    else:
        print("  ❌ 有组的相对先后被打乱：")
        for i in range(max(len(g_rest), len(s_rest))):
            a_ = g_rest[i] if i < len(g_rest) else "—"
            b_ = s_rest[i] if i < len(s_rest) else "—"
            print(f"     {i+1:>2}. 组 {a_:<16} | 规则 {b_:<16} {'✅' if a_==b_ else '❌'}")
        print("     ⇒ 仅当某规则集包含另一集的条目时，被包含者才可前移（如 YouTubeMusic 之于 YouTube）。")
        z0_bad = True

    # ---- 先盘一遍启用的 DIRECT 规则集里到底有多少域名条目（ChinaMax 那类坑）----
    print("=" * 100)
    print("【一】启用的 rule_set 的域名/IP 构成（DIRECT 规则集域名条目≈0 ⇒ 兜不住国内域名）")
    print("-" * 100)
    print(f"{'规则集':40s} {'策略':10s} {'域名条目':>9s} {'IP条目':>8s} {'缺no-resolve':>13s}")
    direct_domains = 0
    for i, r in enumerate(doc.get("rules") or []):
        if not isinstance(r, dict):
            continue
        for t, b in r.items():
            if t != "rule_set" or not isinstance(b, dict):
                continue
            m = str(b.get("match") or "")
            if not m.startswith("http"):
                continue
            if b.get("disabled"):
                continue
            got = rule_set_domains(m, a.offline)
            name = m.rstrip("/").split("/")[-1] or m
            if got is None:
                print(f"{name:40s} {'取失败':10s} {'-':>9s} {'-':>8s} {'-':>13s}")
                continue
            doms, ipn, miss = got
            pol = str(b.get("policy"))
            print(f"{name:40s} {pol:10s} {len(doms):>9d} {ipn:>8d} {miss:>13d}")
            if pol.upper() == "DIRECT":
                direct_domains += len(doms)

    # ⚠️ 前置：有规则集取不到 ⇒ 本轮的"覆盖结论"**不可信**，直接退退出码 2、不判配置对错。
    #    2026-09-25 实测：`--offline` + 冷缓存时 22 份规则集全 miss ⇒ 探针全落 `default(兜底)`
    #    ⇒ 本脚本报「CN 域名兜不住」并 rc=1 —— 那是**环境问题**，不是配置问题。
    #    与「没跑成 ≠ 跑绿」是同一条纪律的反面：**没跑成也 ≠ 判负**。
    #    放在【二】之前：判负表一旦印出来，读的人就会当成配置缺口去改配置。
    _missing = sorted(u for u, s in CACHE_SOURCES.items() if s in ("miss", "fail"))
    if _missing:
        print()
        print("=" * 100)
        print("❌ 前置不达标：%d 份被启用的规则集**取不到** ⇒ 本轮不判配置对错（退出码 2）"
              % len(_missing))
        for u in _missing[:6]:
            print("     · %s" % (u.rstrip("/").split("/")[-1] or u))
        if len(_missing) > 6:
            print("     · …另有 %d 份" % (len(_missing) - 6))
        print("   ⇒ 联网重跑一次把缓存填上，或确认这些规则集地址还有效。"
              "离线档应当**跳过本项**，而不是拿冷缓存判负。")
        return 2

    # ---- 再逐个探针域名走规则 ----
    probes = [("CN", h) for h in CN_PROBES] \
        + [("  ", d) for d in a.domain if d not in CN_PROBES] \
        + [("  ", h) for h in FOREIGN_PROBES if h not in CN_PROBES and h not in a.domain]
    print()
    print("=" * 100)
    print("【二】探针域名实际命中的规则（按 rules 顺序，首次命中即止）")
    print("-" * 100)
    print(f"{'类':3s} {'域名':30s} {'序':>3s} {'命中规则':52s} {'策略'}")
    bad, wrong_direct = [], []
    for kind, h in probes:
        idx, desc, pol = first_hit(doc, h, cache, a.offline)
        print(f"{kind:3s} {h:30s} {('' if idx is None else idx):>3} {desc:52s} {pol}")
        if kind == "CN" and str(pol).upper() != "DIRECT":
            bad.append((h, desc, pol))
        if h in FOREIGN_PROBES and str(pol).upper() == "DIRECT":
            wrong_direct.append((h, desc, pol))

    print()
    print("=" * 100)
    src = list(CACHE_SOURCES.values())
    print("缓存读数：%d 个规则集 —— 新下载 %d · 窗口内直用 %d · 过期退回 %d · 取不到 %d"
          "（窗口 %d 天；过期退回**只报不判**，要按最新规则集下就联网重跑）"
          % (len(src), src.count("fresh"), src.count("cache"), src.count("stale"),
             src.count("miss") + src.count("fail"), CACHE_MAX_AGE // 86400))
    print(f"启用的 DIRECT 规则集域名条目合计: {direct_domains}")
    if wrong_direct:
        print(f"注意 —— {len(wrong_direct)} 个境外探针被判给了 DIRECT（规则集覆盖过宽，需人工确认）：")
        for h, d, p in wrong_direct:
            print(f"  * {h:28s} -> {d}  (policy={p})")
        print()
    if bad:
        print(f"HIGH —— {len(bad)}/{len(CN_PROBES)} 个国内探针未被判给 DIRECT：")
        for h, d, p in bad:
            print(f"  * {h:28s} -> {d}  (policy={p})")
        print()
        print("诊断要点：国内域名整片落到 default/Final，通常是这两种原因之一 ——")
        print("  1) 那条 'geoip: CN' 带了 no_resolve（治 DNS 泄露的常规动作）⇒ geoip 不再匹配域名，")
        print("     而它原本正是国内域名走直连的唯一机制（靠强制解析判出 CN IP）。")
        print("  2) 用来补位的 DIRECT 规则集其实**不含域名规则**。著名例子：blackmatrix7 的")
        print("     `ChinaMax.list` 按仓库 README 只是 IP 规则集（实测 12472 IP / 64 域名），")
        print("     域名在 `ChinaMax_Domain.list` 里，两条需'共同使用'；")
        print("     直接换成 `ChinaMax_All_No_Resolve.list`（111k 域名 + 同份 IP，且全带 no-resolve）最省事。")
        return 1
    print(f"OK —— {len(CN_PROBES)} 个国内探针全部命中 DIRECT。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
