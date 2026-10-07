#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surge profile 防 DNS 泄露审计器。

对一份 Surge .conf 跑 12 项检查，输出分级发现，退出码：
    0 = 无 high
    1 = 有 high（或 --strict 下的 medium）
    2 = 用法错误 / 文件读不到

用法：
    python check_surge_dns.py Profile.conf
    python check_surge_dns.py Profile.conf --strict     # medium 也算失败
    python check_surge_dns.py Profile.conf --quiet      # 只打印计数

⚠️ 本工具审的是**防 DNS 泄露**与**规则结构**，不审以下内容：
    - 节点是否可用（需要真实网络）
    - 规则集内容是否合理（交给 audit_ruleset_noresolve.py / audit_routing_coverage.py）
    - 拦截效果与误杀（无法静态判定）
   审计通过 ≠ 配置可用 —— 这条是 Egern 项目付出 5 次事故换来的结论。
"""

import argparse
import os
import sys

# 输出含 emoji（🟡🟠🔴）：非 UTF-8 控制台（Windows 默认代码页）会 UnicodeEncodeError，
# 与其余收尾脚本统一强制 UTF-8（0929 外部审查指出本脚本缺此保护）。
try:
    for _s in (sys.stdout, sys.stderr):
        _s.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _surge_common import (  # noqa: E402
    FOREIGN_RESOLVER_IPS,
    endpoint_kind,
    hostpart,
    ip_literal,
    kv_dict,
    parse_conf,
    policy_index,
    split_csv,
    strip_comment,
)

# ============================================================================
# 发现收集
# ============================================================================

HIGH, MEDIUM, LOW, OK = "HIGH", "MEDIUM", "LOW", "OK"
_RANK = {OK: 0, LOW: 1, MEDIUM: 2, HIGH: 3}

findings = []  # (level, check_id, message, detail)
_waivers = {}  # check_id -> 理由（来自 profile 里的 # audit-waive: 行）


def add(level, cid, msg, detail=""):
    if cid in _waivers and _RANK.get(level, 0) > 0:
        findings.append((f"WAIVED:{level}", cid, msg,
                         f"⚠️ 已豁免（profile 内声明）：{_waivers[cid]}\n        ↳ {detail}"
                         if detail else f"⚠️ 已豁免（profile 内声明）：{_waivers[cid]}"))
        return
    findings.append((level, cid, msg, detail))


# ---------------------------------------------------------------------------
# 豁免机制
# ---------------------------------------------------------------------------
# 为什么要有它：本模板有两处是**刻意的设计取舍**，不是缺陷 ——
#   ① `encrypted-dns-server` 里带 `https://dns.google/dns-query` / `dns.alidns.com`：
#      这两个端点的主机名会被引导解析一次。换成纯 IP 字面量能消除它，但会失去
#      "按域名走 CDN 就近解析" 与 "ECS 合规" 这两项收益。
#   ② 兜底指 `Proxy` 而非国内组：本模板不做分流兜底的境内/境外切分。
#
# 豁免**必须写在 profile 里**（`# audit-waive: <检查号> <理由>`），不能写在审计器里：
#   · 写在审计器里 = 判据被永久削弱，将来别的 profile 也享受不到这层保护；
#   · 写在 profile 里 = 每一次豁免都在被审对象上留痕、可被 grep、可被复核。
# 豁免不改变退出码语义的**前提**是：它把 finding 降级为 `WAIVED:`，
# 在报告里照样逐条打印 —— 它只是不再让整轮判负，不是"看不见"。
def load_waivers(path):
    import re as _re
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    for m in _re.finditer(r"#\s*audit-waive:\s*(\d+)\s+(.*)", text):
        cid = int(m.group(1))
        _waivers[cid] = m.group(2).strip()


# ============================================================================
# 各项检查
# ============================================================================

BUILTIN_POLICIES = {
    "direct", "reject", "reject-tinygif", "reject-dict", "reject-array",
    "reject-no-drop", "reject-drop", "reject-tinygif-no-drop",
    "proxy", "final", "system",
}


def check_1_endpoints(sections, cfg):
    """1 · 加密 DNS 端点是否为 IP 字面量（会触发引导明文解析）。"""
    raw = cfg.get("encrypted-dns-server")
    if not raw:
        add(HIGH, 1, "[General] 缺少 encrypted-dns-server",
            "没有加密 DNS 端点 ⇒ 所有查询走 dns-server 明文 UDP:53")
        return
    eps = split_csv(raw[1])
    bad = [e for e in eps if not ip_literal(e)]
    foreign = [e for e in eps if endpoint_kind(e)[0] == "foreign-ip"]
    if bad:
        add(HIGH, 1, f"{len(bad)} 个加密 DNS 端点不是 IP 字面量",
            "这些端点的**主机名**必须先被明文解析一次才能建连：" + ", ".join(bad))
    else:
        add(OK, 1, f"{len(eps)} 个加密 DNS 端点全部是 IP 字面量", ", ".join(eps))
    if foreign:
        add(MEDIUM, 1, f"{len(foreign)} 个加密 DNS 端点在国外",
            f"{', '.join(foreign)} —— 国内线路上通常不可达；"
            "只保留国内端点更稳（但会失去对境外域名的解析准确性，属取舍）")


def check_2_bootstrap(cfg):
    """2 · dns-server 是否显式、是否含 system、是否≥2 个国内端点。"""
    raw = cfg.get("dns-server")
    if not raw:
        add(HIGH, 2, "[General] 缺少 dns-server",
            "未配置时 Surge 使用系统 DNS = 运营商 DHCP 下发的那台")
        return
    items = split_csv(raw[1])
    kinds = [endpoint_kind(x) for x in items]
    hosts = [k[1] for k in kinds]
    if any(h.lower() == "system" for h in hosts):
        add(HIGH, 2, "dns-server 里出现 `system`",
            "引导解析器绝不能写成 system —— 那正是要消除的那条明文通路")
    domestic = [k[1] for k in kinds if k[0] == "domestic-ip"]
    hostnames = [k[1] for k in kinds if k[0] == "hostname"]
    if hostnames:
        add(HIGH, 2, f"dns-server 里有主机名条目", ", ".join(hostnames))
    if len(domestic) < 2:
        add(MEDIUM, 2, f"dns-server 里的国内解析器少于 2 个（{len(domestic)} 个）",
            "任一机构故障时就没有退路了；建议至少 2 个不同机构")
    else:
        add(OK, 2, f"dns-server 有 {len(domestic)} 个国内解析器：{', '.join(domestic)}")


def check_3_hijack(cfg):
    """3 · hijack-dns 是否接管硬编码解析器。"""
    raw = cfg.get("hijack-dns")
    if not raw:
        add(HIGH, 3, "[General] 缺少 hijack-dns",
            "忽略 Surge DNS 的设备（HomePod / Apple TV / Chromecast / 智能音箱）"
            "发出的明文 :53 查询会直接裸奔到硬编码解析器")
        return
    items = split_csv(raw[1])
    if "*" in items or "0.0.0.0:53" in items:
        add(OK, 3, f"hijack-dns 为全量接管（{raw[1]}）")
        return
    # ⭐ 判据不是"列了几个"，而是"还有多少知名硬编码解析器没被覆盖"。
    #    :53 的地址空间是无限的，列举永远不可能"列全" —— 第一版按条数判负是错的。
    covered = set()
    for it in items:
        covered.add(hostpart(it))
    uncovered = sorted(ip for ip in FOREIGN_RESOLVER_IPS if ":" not in ip and ip not in covered)
    if uncovered:
        add(LOW, 3, f"hijack-dns 未覆盖 {len(uncovered)} 个知名境外解析器",
            f"未覆盖：{', '.join(uncovered)}。它们仍会以明文 :53 外发；"
            "要一网打尽就写 `hijack-dns = *`（官方示例值）")
    else:
        add(OK, 3, f"hijack-dns 已覆盖全部已知的知名硬编码解析器（{len(items)} 条）")


def check_4_follow_mode(cfg):
    """4 · encrypted-dns-follow-outbound-mode 是否会形成环。"""
    raw = cfg.get("encrypted-dns-follow-outbound-mode")
    if not raw:
        add(OK, 4, "encrypted-dns-follow-outbound-mode 未设置（默认 false = 直连）")
        return
    if raw[1].strip().lower() in ("true", "1", "yes"):
        add(HIGH, 4, "encrypted-dns-follow-outbound-mode = true",
            "DoH 连接会遵循代理规则 ⇒ 解析代理解析器本身需要代理 ⇒ 启动期形成环 / "
            "回退明文。必须保持 false")
    else:
        add(OK, 4, "encrypted-dns-follow-outbound-mode = false（直连，无环）")


def check_5_system_dns(cfg):
    """5 · always-real-ip / Host 段里有没有 server:system 之外的隐式系统 DNS。"""
    raw = cfg.get("always-real-ip")
    if not raw:
        add(LOW, 5, "[General] 缺少 always-real-ip",
            "游戏机 / NTP / STUN 主机名会拿到 fake-IP，NAT 类型检测与时间同步可能异常")
    else:
        add(OK, 5, f"always-real-ip 已配置（{len(split_csv(raw[1]))} 项）")
    if cfg.get("use-local-host-item-for-proxy") and \
            cfg["use-local-host-item-for-proxy"][1].strip().lower() in ("true", "1"):
        add(HIGH, 5, "use-local-host-item-for-proxy = true",
            "本地 DNS 映射会成为硬性代理目标 ⇒ 破坏远端解析（走代理的域名不该有本地答案）")


def check_6_latency_urls(cfg):
    """6 · 延迟测试端点的域名归属（提示性检查，不构成泄露面）。

    ⚠️ 重要定性：`proxy-test-url` / `internet-test-url` 是**性能探针**，不是泄露通道。

      · `proxy-test-url` 决定 `smart` / `url-test` 组拿什么打分。测的是
        「本机 → 测试地址 → 节点 → 回来」这一整圈。**用境内端点测境外节点，
        测出来的是境内 RTT，与你要走的国际路径相关性弱** —— 所以这里
        **不把境外端点判为问题**，只做 LOW 提示，把选点权留给使用者。
      · 它确实会周期性解析该域名，但：走代理策略时解析发生在**代理服务器**
        （官方 KB：「DNS 解析永远在代理服务器进行」），本地不解析；
        只有命中 DIRECT 才本地解析 —— 而国内 204 端点会被 `direct.txt` 接住。

    ⇒ 结论：端点选境内还是境外，是**性能取向**的取舍，不是安全对错。
       本项只提示，不计入风险等级。
    """
    for key in ("internet-test-url", "proxy-test-url", "proxy-test-udp"):
        raw = cfg.get(key)
        if not raw:
            add(LOW, 6, f"[General] 缺少 {key}")
            continue
        url = raw[1].strip()
        host = url.split("://", 1)[-1].split("/")[0].split("@")[-1]
        host = host.split(":")[0]
        if ip_literal(host):
            add(OK, 6, f"{key} 用 IP 字面量（{host}）—— 不产生解析")
        elif is_domestic_name(host):
            add(OK, 6, f"{key} 的域名在国内（{host}）—— 由 direct.txt 接住")
        else:
            # 刻意只报 LOW：境外端点测的是含国际段的真实路径，对 smart 打分可能
            # 更贴近体感；这是性能取舍，不是配置缺陷。
            add(LOW, 6, f"{key} 用境外端点（{host}）—— 性能取向取舍，非缺陷",
                "境外端点测出的延迟含国际段，更贴近真实访问体感；"
                "境内端点则更省一次本地解析。两者都是合理选择，按你的取向定。")


# ⭐ 国内公共 204 / 连通性测试端点的域名后缀 —— 这些域名的归属是公开事实。
# ⚠️ 判据只认后缀，**不要**用 `endswith('.com.cn')` 这种一刀切：
#    `connect.rom.miui.com` 是小米的域名，`.miui.com` / `.xiaomi.com` 都是国内的，
#    但它们不以 `.cn` 结尾。第一版就是在这里把 miui.com 误判成境外域。
DOMESTIC_TEST_SUFFIXES = (
    ".cn",
    ".miui.com", ".xiaomi.com", ".mifans.com",
    ".qq.com", ".tencent.com", ".weixin.qq.com",
    ".baidu.com", ".bdstatic.com",
    ".alibaba.com", ".aliyun.com", ".alicdn.com", ".taobao.com", ".tmall.com",
    ".huawei.com", ".hicloud.com",
    ".jd.com", ".360.cn", ".so.com",
    ".netease.com", ".163.com",
    ".bilibili.com", ".zhihu.com",
)


def is_domestic_name(host):
    h = host.lower()
    return h.endswith(DOMESTIC_TEST_SUFFIXES)


def check_7_groups(sections):
    """7 · 策略组引用的节点 / 组是否存在于 [Proxy] / [Proxy Group]。

    ⚠️ **允许前向引用**（本组可以引用在它**之后**才定义的组）。
       依据：官方文档「包含本地或其他策略组的策略」一节的示例本身就是前向引用 ——
       `PROXY = select, include-other-group="A,B"` 写在 `A` / `B` 定义之前。
       ⇒ 所以必须先把**全部**组名收集齐，再逐组校验；不能边扫边判。
       本配置还刻意把组序对齐到 Egern v3（总入口 → 应用组 → 订阅槽位 → 地区组 → 兜底），
       这必然产生前向引用（`Proxy` 引用它后面的地区组）。
    """
    proxy_entries = sections.get("proxy", [])
    defined = set()
    for lineno, raw in proxy_entries:
        s = strip_comment(raw)
        if not s or "=" not in s:
            continue
        defined.add(s.split("=", 1)[0].strip())
    lower = {d.lower(): d for d in defined}

    # 第一遍：收集全部组名 + 保留每条定义，供第二遍校验
    group_entries = sections.get("proxy group", [])
    group_names = []
    parsed = []
    for lineno, raw in group_entries:
        s = strip_comment(raw)
        if not s or "=" not in s:
            continue
        name = s.split("=", 1)[0].strip()
        group_names.append(name)
        parsed.append((lineno, name, split_csv(s.split("=", 1)[1])))

    known_groups = set(group_names)

    # 第二遍：校验（此时 known_groups 已含全部组名 ⇒ 前向引用合法）
    for lineno, name, members in parsed:
        if not members:
            add(HIGH, 7, f"策略组 `{name}` 没有任何成员", "第 %d 行" % lineno)
            continue
        gtype = members[0].lower()
        if gtype not in ("select", "smart", "fallback", "url-test", "load-balance",
                         "round-robin", "ssid", "subnet"):
            add(MEDIUM, 7, f"策略组 `{name}` 的类型 `{members[0]}` 不是已知类型",
                "第 %d 行；成员会被全部当成节点名解析" % lineno)
        for m in members[1:]:
            if "=" in m:  # icon-url= / no-alert= / hidden= 这类参数
                continue
            if m.lower() in BUILTIN_POLICIES:
                continue
            if m in defined or m in known_groups:
                continue
            if m.lower() in lower:
                continue
            add(HIGH, 7, f"策略组 `{name}` 引用了不存在的成员 `{m}`",
                "第 %d 行；Surge 会因无法解析成员而拒绝加载整份配置" % lineno)
    if defined:
        add(OK, 7, f"[Proxy] 定义 {len(defined)} 个节点，"
                   f"[Proxy Group] 定义 {len(group_names)} 个组，成员引用全部可解析")
    return defined, group_names


def parse_rules(sections):
    """[[Rule] 段] -> [(lineno, [字段...])]，跳过注释与空行。"""
    out = []
    for lineno, raw in sections.get("rule", []):
        s = strip_comment(raw)
        if not s:
            continue
        out.append((lineno, split_csv(s)))
    return out


# ⚠️ `policy_index` 与 `_RULE_TYPES_*` / 端点判据 / INI 解析都在 `_surge_common.py`，
#    从那里 import。**不要在本文件里再写一份** —— 「同一判据两份拷贝、改一处漏另一处」
#    正是 Egern 项目踩过的坑（两个脚本对同一份配置给出相反结论）。


def check_8_rule_policies(sections, defined, group_names):
    """8 · 规则引用的策略是否可解析。"""
    rules = parse_rules(sections)
    known = {n.lower() for n in (list(defined) + list(group_names))} | BUILTIN_POLICIES
    bad = []
    unknown_type = []
    for lineno, parts in rules:
        t = parts[0].strip().upper()
        pi = policy_index(parts)
        if pi is None:
            unknown_type.append((lineno, " → ".join(parts), t))
            continue
        if len(parts) <= pi:
            unknown_type.append((lineno, " → ".join(parts), t))
            continue
        pol = parts[pi].strip()
        if pol.lower() not in known:
            bad.append((lineno, pol, " → ".join(parts)))
    for lineno, line, t in unknown_type:
        add(MEDIUM, 8, f"第 {lineno} 行的规则类型 `{t}` 未识别或字段不足",
            f"{line}（无法确定策略字段位置，已跳过策略校验）")
    if bad:
        for lineno, pol, line in bad:
            add(HIGH, 8, f"规则引用了未定义的策略 `{pol}`",
                f"第 {lineno} 行：{line}；Surge 会因策略无法解析而拒绝加载整份配置")
    else:
        add(OK, 8, f"{len(rules)} 条规则的策略全部可解析")


def check_9_rule_order(sections):
    """9 · 规则顺序：白名单 → 拦截 → 域名类直连 → IP 类规则 → 兜底。"""
    rules = parse_rules(sections)
    if not rules:
        add(HIGH, 9, "[Rule] 段为空或缺失")
        return
    idx_first_domain = None
    idx_first_ip = None
    idx_final = None
    reject_lines = []
    for i, (lineno, parts) in enumerate(rules):
        t = parts[0].strip().upper()
        if idx_first_domain is None and t in (
                "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD", "RULE-SET"):
            idx_first_domain = i
        if idx_first_ip is None and t in ("IP-CIDR", "IP-CIDR6", "GEOIP", "IP-ASN"):
            idx_first_ip = i
        if idx_final is None and t == "FINAL":
            idx_final = i
        if len(parts) >= 2 and parts[1].strip().lower().startswith("reject"):
            reject_lines.append(i)

    if idx_final is None:
        add(HIGH, 9, "[Rule] 段没有 FINAL 兜底规则")
    elif idx_final != len(rules) - 1:
        add(MEDIUM, 9, f"FINAL 不在最后一条（是第 {idx_final + 1} / {len(rules)} 条）",
            "FINAL 之后的规则永远不会被求值")

    if idx_first_ip is not None and idx_first_domain is not None and idx_first_ip < idx_first_domain:
        add(HIGH, 9, "IP 类规则排在域名类规则之前",
            f"第 {rules[idx_first_ip][0]} 行是第一条 IP 规则，"
            f"而第一条域名规则在第 {rules[idx_first_domain][0]} 行")
    else:
        add(OK, 9, "域名类规则全部排在 IP 类规则之前")

    if reject_lines:
        first_reject = reject_lines[0]
        # 真正的判据：拦截是否排在"会命中大量国内域名的 DIRECT 规则"之前。
        # 这里只能做顺序性提示，命中与否取决于规则集内容（交给 audit_routing_coverage.py）。
        add(OK if first_reject <= (idx_first_ip if idx_first_ip is not None else 1 << 30)
            else MEDIUM, 9,
            f"广告拦截在第 {rules[first_reject][0]} 行，第一条 IP 类规则在第 "
            f"{rules[idx_first_ip][0] if idx_first_ip is not None else '—'} 行")


def check_10_ad_rule_policy(sections):
    """10 · 广告拦截必须是字面量 REJECT 族策略（pre-matching 的硬要求）。"""
    rules = parse_rules(sections)
    ad_hits = []
    for lineno, parts in rules:
        t = parts[0].strip().upper()
        if t != "RULE-SET":
            continue
        opts = [p.strip().lower() for p in parts[3:]]
        if "pre-matching" not in opts:
            continue
        pi = policy_index(parts)
        pol = parts[pi].strip() if pi is not None and len(parts) > pi else ""
        ad_hits.append((lineno, parts[1] if len(parts) > 1 else "?", pol, opts))

    if not ad_hits:
        add(LOW, 10, "没有使用 pre-matching 的规则",
            "pre-matching 的 REJECT 在 DNS / TCP-SYN 阶段生效，"
            "是广告密集配置最大的一笔 CPU 与耗电优化")
        return
    for lineno, target, pol, opts in ad_hits:
        if pol.lower().startswith("reject"):
            add(OK, 10, f"第 {lineno} 行 pre-matching 的策略是字面量 `{pol}`")
        else:
            add(HIGH, 10, f"第 {lineno} 行 pre-matching 的策略是 `{pol}`，不是字面量 REJECT 族",
                "pre-matching 要求策略本身一定是 REJECT 族；"
                "写成策略组会因『组在运行时可能解析成 DIRECT』而被 Surge 拒绝加载")
        if "extended-matching" not in opts:
            add(LOW, 10, f"第 {lineno} 行的 pre-matching 规则没有 extended-matching",
                "缺少它时，App 直连 IP 的场景下域名规则会失效（TLS SNI / HTTP Host 兜底）")


def check_11_real_ip(sections, cfg):
    """11 · always-real-ip 的主机名是否在兜底之前被域名规则接住。"""
    raw = cfg.get("always-real-ip")
    if not raw:
        return
    patterns = [p.strip() for p in split_csv(raw[1]) if p.strip()]
    if not patterns:
        return
    rules = parse_rules(sections)
    covered = []          # 兜底之前所有域名类规则的匹配表达式
    covered_kw = []       # DOMAIN-KEYWORD 的被匹配子串（子串匹配，判据不同）
    for lineno, parts in rules:
        t = parts[0].strip().upper()
        if t == "FINAL":
            break
        if t in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-WILDCARD") and len(parts) > 1:
            covered.append(parts[1].strip().lower())
        elif t == "DOMAIN-KEYWORD" and len(parts) > 1:
            covered_kw.append(parts[1].strip().lower())
        elif t == "RULE-SET":
            # 远程规则集的内容不在本文件里 —— 无法静态判定，按"接不住"算，
            # 但单独归组、只给 LOW（真实答案是"要看规则集内容"，交给
            # audit_routing_coverage.py 用真实域名走一遍）。
            covered.append("__ruleset__")

    def hit(p):
        """always-real-ip 的写法是 Surge 通配，逐级回退后缀来判是否被覆盖。"""
        pl = p.strip().lower()
        if pl.startswith("*."):
            # *.x.y  ->  x.y / y  （子域匹配；裸域是否命中取决于 Surge 语义，从严处理）
            pl = pl[2:]
        parts_ = pl.split(".")
        for i in range(len(parts_)):
            cand = ".".join(parts_[i:])
            if cand in covered:
                return True
            for kw in covered_kw:
                if kw in cand:
                    return True
        return False

    has_ruleset = "__ruleset__" in covered
    misses = [p for p in patterns if not hit(p)]
    # 本地/局域网类主机名本来就该由 [Host] + LAN 规则处理，不计入
    local_like = [p for p in misses if p.lstrip("*.").split(".")[-1] in
                  ("lan", "local", "localdomain", "arpa", "home")]
    real_miss = [p for p in misses if p not in local_like]

    if real_miss:
        level = LOW if has_ruleset else MEDIUM
        add(level, 11,
            f"{len(real_miss)} 个 always-real-ip 主机名在兜底之前没有被**本文件的**域名规则接住",
            f"{', '.join(real_miss)}。" +
            ("本文件中的 RULE-SET 是远程规则集，其内容无法静态判定 —— "
             "它们仍可能被接住，需用 audit_routing_coverage.py 拿真实域名复核。"
             if has_ruleset else "它们会被迫走一次本地解析；"
             "若最终落到依赖代理的兜底，启动期会回退明文引导。"))
    else:
        add(OK, 11, f"{len(patterns)} 个 always-real-ip 主机名都已被前置域名规则接住"
                    f"（{len(local_like)} 个本地类主机名归 [Host] / LAN 规则处理）")


def check_12_no_resolve(sections):
    """12 · IP 类规则是否都带 no-resolve。"""
    rules = parse_rules(sections)
    ip_rules = [(l, p) for l, p in rules if p[0].strip().upper() in ("IP-CIDR", "IP-CIDR6", "GEOIP", "IP-ASN")]
    if not ip_rules:
        add(OK, 12, "没有 IP 类规则（不存在缺 no-resolve 的风险）")
        return
    bad = [(l, p) for l, p in ip_rules
           if not any(x.strip().lower() == "no-resolve" for x in p[2:])]
    if bad:
        for lineno, parts in bad:
            # ⚠️ 判级是 MEDIUM 不是 HIGH：走代理策略时解析本就在代理服务器进行
            #    （官方 KB），缺 no-resolve 只是**多触发一次冗余本地解析**，
            #    不是泄露补丁缺失。真正要防的是它同时带来的连带风险（见 check_13/14）。
            add(MEDIUM, 12, f"第 {lineno} 行的 IP 类规则缺少 no-resolve",
                " → ".join(parts) + "；匹配时会额外触发一次本地解析。"
                "注意：这不是泄露补丁 —— 走代理时解析在代理服务器进行；"
                "但**补上它必须同时确认有域名类国内直连集**，否则国内域名会走代理")
    else:
        add(OK, 12, f"{len(ip_rules)} 条 IP 类规则全部带 no-resolve")
    # FINAL 的 dns-failed
    for lineno, parts in rules:
        if parts[0].strip().upper() == "FINAL":
            if any("dns-failed" in x.lower() for x in parts[2:]):
                add(OK, 12, "FINAL 带 dns-failed（DNS 失败时走代理远端解析而非直接失败）")
            else:
                add(LOW, 12, "FINAL 没有 dns-failed",
                    "规则求值因 DNS 失败中断时，请求会直接失败")


# ============================================================================
# 主流程
# ============================================================================

def run(path, strict=False, quiet=False):
    _waivers.clear()
    # findings 与 _waivers 同属模块级状态：不清空则同一进程内第二次 run() 会把上一轮的
    # 发现累计进来（实测：对同一份 profile 连跑两次，len(findings) 16 → 32）。
    # 一次性 CLI 看不出，但任何复用 / 单测都会中招，且结论会静默偏大。
    findings.clear()
    load_waivers(path)
    sections, _ = parse_conf(path)
    cfg = kv_dict(sections.get("general", []))

    if not sections:
        print("❌ 没有解析到任何 [Section] —— 文件格式可能不对", file=sys.stderr)
        return 2

    check_1_endpoints(sections, cfg)
    check_2_bootstrap(cfg)
    check_3_hijack(cfg)
    check_4_follow_mode(cfg)
    check_5_system_dns(cfg)
    check_6_latency_urls(cfg)
    defined, group_names = check_7_groups(sections)
    check_8_rule_policies(sections, defined, group_names)
    check_9_rule_order(sections)
    check_10_ad_rule_policy(sections)
    check_11_real_ip(sections, cfg)
    check_12_no_resolve(sections)

    counts = {k: 0 for k in _RANK}
    waived = 0
    for lv, _, _, _ in findings:
        if lv.startswith("WAIVED:"):
            waived += 1
        else:
            counts[lv] = counts.get(lv, 0) + 1

    if not quiet:
        icons = {HIGH: "🔴", MEDIUM: "🟠", LOW: "🟡", OK: "✅"}
        for lv in [HIGH, MEDIUM, LOW, OK]:
            group = [f for f in findings if f[0] == lv]
            if not group:
                continue
            print(f"\n{icons[lv]} {lv} · {len(group)} 条")
            for _, cid, msg, detail in group:
                print(f"   [{cid:>2}] {msg}")
                if detail:
                    print(f"        ↳ {detail}")
        gw = [f for f in findings if f[0].startswith("WAIVED:")]
        if gw:
            print(f"\n⚪ 已豁免 · {len(gw)} 条（不改判定，但照样列出来）")
            for _, cid, msg, detail in gw:
                print(f"   [{cid:>2}] {msg}")
                if detail:
                    print(f"        ↳ {detail}")

    print(f"\n{'─' * 62}")
    print(f"result: {counts[HIGH]} high, {counts[MEDIUM]} medium, "
          f"{counts[LOW]} low, {counts[OK]} ok"
          + (f", {waived} waived" if waived else ""))

    fail = counts[HIGH] > 0 or (strict and counts[MEDIUM] > 0)
    if fail:
        print("❌ 未通过" + ("（--strict：medium 也算失败）" if strict and counts[HIGH] == 0 else ""))
        return 1
    print("✅ 通过")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Surge profile 防 DNS 泄露审计器")
    ap.add_argument("profile", help="Surge .conf 文件路径")
    ap.add_argument("--strict", action="store_true", help="medium 也视为失败")
    ap.add_argument("--quiet", action="store_true", help="只打印计数")
    a = ap.parse_args()
    if not os.path.isfile(a.profile):
        print(f"❌ 找不到文件：{a.profile}", file=sys.stderr)
        return 2
    return run(a.profile, a.strict, a.quiet)


if __name__ == "__main__":
    sys.exit(main())
