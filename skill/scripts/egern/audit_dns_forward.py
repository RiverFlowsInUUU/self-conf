# -*- coding: utf-8 -*-
"""清单 18：dns.forward 审计 —— 「换订阅会不会让防泄露失效？」

回答三个问题：
  ① forward 里**除 `reject` 之外**的去向是不是**单值（= 兜底组）**？若是，则规则顺序与域名清单都不影响结果
   （`reject` 是终止动作、命中即拒答，不产生解析，与兜底判定无关）
     ⇒ 新增/更换任何域名（含换订阅后的节点域名）行为不变，本节无需维护。
  ② forward 里有没有把**节点域名写死**（订阅耦合度）？换订阅后这些规则会变死代码。
  ③ 兜底组是否「直连可达 + 端点全为 IP 字面量 + 不需要 bootstrap」？这决定
     未命中任何规则时会不会掉进明文 UDP:53。

判据来源（官方 dns 文档逐字）：
  - 「规则按声明顺序求值，第一条命中的决定上游」
  - 「配置了 proxy_nameservers 后，代理 DNS 会跳过 Forward 阶段，直接走该列表」
  - 「Forward 未命中时，默认 DNS 回退到 Bootstrap」

用法：
  python audit_dns_forward.py profile.yaml
  python audit_dns_forward.py profile.yaml --domain new-node.example.com --domain hk1.foo.net
  python audit_dns_forward.py profile.yaml --drill          # 内置「换订阅演练」合成域名

退出码：0 = 通过；1 = 存在会让新域名掉进 bootstrap 的风险。
"""

import argparse
import fnmatch
import io
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("需要 pyyaml：<venv>/Scripts/pip.exe install pyyaml")

# ⭐ 共享工具：DOMESTIC_RESOLVER_IPS / hostpart / ip_literal 等收编在 _egern_common.py，
#    与 check_egern_dns.py 共用同一份实现 —— 不再有「两份拷贝靠注释同步」的隐患。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _egern_common import DOMESTIC_RESOLVER_IPS, ip_literal, hostpart  # noqa: E402

ep_ip = hostpart  # 本脚本历史调用名


# 「换订阅演练」用的合成域名：模拟以后换机场/换中转会出现的节点域名形态。
# 它们**故意不在**任何规则集里，用来验证「未命中的域名会落到哪里」。
DRILL_DOMAINS = [
    "new-node.example-airport.com",
    "hk1.somecdn.net",
    "us3.fastnode.io",
    "jp02.another-relay.xyz",
    "edge.cdn-provider.top",
    "node-a.sub-new.example",
]


def dom_suffix(h, m):
    """domain_suffix 按 '.' 边界对齐（官方：match: cn 命中 cn 与 example.cn，不命中 examplecn）。"""
    h, m = h.lower(), str(m).lower().lstrip("+.")
    return h == m or h.endswith("." + m)


def rule_matches(typ, match, host):
    """返回 True/False/None —— None 表示需要下载远程规则集才能判定。"""
    h = host.lower()
    m = str(match)
    if typ == "domain":
        return h == m.lower()
    if typ == "domain_suffix":
        return dom_suffix(h, m)
    if typ == "domain_keyword":
        return m.lower() in h
    if typ == "domain_wildcard":
        return fnmatch.fnmatch(h, m.lower())
    if typ == "domain_regex":
        try:
            return re.search(m, h) is not None
        except re.error:
            return False
    if typ in ("proxy_rule_set", "rule_set"):
        return None
    if typ in ("ssid", "bssid", "cellular"):
        return None  # 依网络状态，与域名无关
    return None


def is_catchall(typ, match):
    """能不能当兜底：匹配任意域名的规则。"""
    m = str(match)
    if typ == "domain_wildcard":
        return m.strip() == "*" or (m.startswith("*") and m.count("*") == 1 and m.endswith("*") and len(m) == 1)
    if typ == "domain_regex":
        return m.strip() == "." or m.strip() in (".*", "^.*$", ".+")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--domain", action="append", default=[],
                    help="额外要演练的域名（可重复）")
    ap.add_argument("--drill", action="store_true",
                    help="加入内置的『换订阅演练』合成域名")
    a = ap.parse_args()

    doc = yaml.safe_load(io.open(a.profile, encoding="utf-8").read())
    dns = doc.get("dns") or {}
    fwd = dns.get("forward") or []
    ups = dns.get("upstreams") or {}
    pns = dns.get("proxy_nameservers") or []
    boot = dns.get("bootstrap") or []
    rules = doc.get("rules") or []
    proxies = doc.get("proxies") or []

    print("=" * 100)
    print("Egern forward 规则审计 ——「换订阅会不会让防泄露失效？」")
    print(f"profile: {a.profile}")
    print("=" * 100)

    # ---------- 展开 forward ----------
    flat = []          # (序, 类型, match, value, enabled)
    for r in fwd:
        for typ, body in r.items():
            if not isinstance(body, dict):
                continue
            flat.append((typ, body.get("match"),
                         str(body.get("value")),
                         not bool(body.get("disabled", False))))

    print()
    print(f"【一】forward 规则表（声明顺序，共 {len(flat)} 条）")
    print("-" * 100)
    # 找最后一条兜底的位置
    last_catch = max([i for i, (t, m, v, e) in enumerate(flat) if is_catchall(t, m)] or [-1])
    catch_value = flat[last_catch][2] if last_catch >= 0 else None

    print(f"{'#':>3}  {'类型':16s} {'匹配':40s} {'value':16s} 说明")
    redundant = []
    for i, (t, m, v, e) in enumerate(flat, 1):
        note = ""
        if is_catchall(t, m):
            note = "★兜底（匹配任意域名）"
        elif e and last_catch >= i - 1 and v == catch_value:
            note = "冗余：其结果与兜底相同（可删）"
            redundant.append(i)
        if not e:
            note = (note + " [已禁用]").strip()
        print(f"{i:>3}  {t:16s} {str(m)[:40]:40s} {v:16s} {note}")

    if last_catch < 0:
        print()
        print("  ⚠️ 没有找到兜底规则 ⇒ 未命中的域名会回退 Bootstrap（明文 UDP:53）。")
    elif redundant:
        print()
        print(f"  ⇒ 第 {redundant} 条是**结构性冗余**（它们先命中，结果却与兜底完全相同）。")

    # ---------- 单值性 ----------
    values = sorted({v for (_, _, v, e) in flat if e})
    print()
    print("【二】value 单值性（决定『换域名还要不要改配置』）")
    print("-" * 100)
    print(f"  启用的规则里出现的 value 集合: {values}")
    # ⚠️ 判据（2026-09-23 扩展）：`reject` 是**终止动作**（官方：「refuse the query and
    #    return an empty response」）—— 命中即拒答、根本不产生解析，因此它与兜底组**不冲突**，
    #    可以并存。真正要保证的性质是：**所有非 reject 规则的去向都等于兜底组**，
    #    这样新域名（含换订阅后的节点域名）落进兜底组的行为与其它域名一致。
    non_reject = sorted({v for v in values if v != 'reject'})
    n_reject = len([1 for (_, _, v, e) in flat if e and v == 'reject'])
    if n_reject:
        print(f"  其中 `reject` 规则 {n_reject} 条 —— 终止动作（拒答，不产生解析）⇒ 与兜底判定无关。")
    single = set(non_reject) <= ({catch_value} if catch_value is not None else set())
    if single:
        print("  ✅ 非 reject 规则去向唯一且等于兜底组：无论命中哪一条、无论声明顺序，结果都是同一上游")
        print("     ⇒ **域名清单与规则顺序都不影响结果** ⇒ 新增任何域名（含换订阅后的节点域名）行为不变。")
    else:
        print("  ⚠️ 多值：结果取决于域名命中哪条规则 ⇒ 新域名会落到兜底组，需确认兜底组是否安全。")
        print(f"     非 reject 值集合 = {non_reject}；兜底组的 value = {catch_value}")

    # ---------- 订阅耦合度 ----------
    node_domains = []
    for p in proxies:
        for typ, body in p.items():
            if isinstance(body, dict):
                s = str(body.get("server", ""))
                if s and not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", s):
                    node_domains.append(s)
    node_domains = sorted(set(node_domains))
    matches_txt = [(str(m), i) for i, (_, m, _, _) in enumerate(flat, 1)]
    coupled = []
    for nd in node_domains:
        for m, idx in matches_txt:
            if nd == m or nd.endswith("." + m.lstrip("+.")):
                coupled.append((nd, idx, m))
    print()
    print("【三】订阅耦合度：forward 里有没有把节点域名写死")
    print("-" * 100)
    print(f"  proxies 段里的节点 server（域名形式）: {len(node_domains)} 个")
    for nd in node_domains:
        print(f"     - {nd}")
    print(f"  forward 的 match 里出现这些域名的规则: {len(coupled)} 条")
    for nd, idx, m in coupled:
        print(f"     #{idx} match={m}  ← 命中节点 {nd}")
    if not coupled:
        print("  ✅ 零耦合：换订阅、换机场、换节点域名，本节都不需要改一个字。")
    else:
        print("  ℹ️ 存在耦合，但因为【二】是单值，这些规则删掉也不改变行为（它们只是文档）。")

    # ---------- 演练 ----------
    # ⚠️ fails 必须在 if probes: 之外初始化 —— 否则不带 --drill / --domain 时
    #    （probes 为空）不会进入该分支，下面结论段的 `not fails` 会抛 UnboundLocalError。
    fails = []
    probes = list(a.domain) + (DRILL_DOMAINS if a.drill else [])
    if probes:
        print()
        print(f"【四】域名演练（{len(probes)} 个：你给的 + 合成『未来订阅』域名）")
        print("-" * 100)
        print(f"{'域名':36s} {'命中规则':34s} {'value':16s} 结论")
        for h in probes:
            hit_i, hit_t, hit_v = None, "(未命中任何规则)", catch_value
            for i, (t, m, v, e) in enumerate(flat, 1):
                if not e:
                    continue
                r = rule_matches(t, m, h)
                if r is True:
                    hit_i, hit_t, hit_v = i, f"#{i} {t}", v
                    break
                if r is None and hit_i is None:
                    # 远程规则集/网络状态类规则：值相同则不影响结论，先记为候选
                    hit_i, hit_t, hit_v = i, f"#{i} {t}(需下载)", v
            verdict = "✅ 一致" if hit_v == catch_value else f"⚠️ 与兜底({catch_value})不同"
            if hit_v != catch_value:
                fails.append((h, hit_t, hit_v))
            print(f"{h:36s} {hit_t[:34]:34s} {str(hit_v):16s} {verdict}")

    # ---------- 兜底组可用性 ----------
    print()
    print("【五】兜底组可用性（决定未命中的域名会不会掉进 bootstrap）")
    print("-" * 100)
    eps = []
    if catch_value in ups:
        eps = list(ups[catch_value])
    else:
        eps = [catch_value]  # 隐式上游：value 直接就是一个 DNS 地址
    bad_ep = [e for e in eps if not ip_literal(e)]
    print(f"  兜底组 {catch_value} 的端点: {len(eps)} 个")
    for e in eps:
        print(f"     {'✅' if ip_literal(e) else '⚠️'} {e}")
    if bad_ep:
        print(f"  ⚠️ 有 {len(bad_ep)} 个主机名端点 ⇒ 官方会用 bootstrap（明文 UDP:53）解析它：{bad_ep}")
    else:
        print("  ✅ 全部是 IP 字面量 ⇒ 兜底组自身不需要 bootstrap 解析。")

    direct_ips = set()
    for r in rules:
        for typ, body in r.items():
            if not isinstance(body, dict) or body.get("disabled"):
                continue
            if typ in ("ip_cidr", "ip_cidr6") and str(body.get("policy")).upper() == "DIRECT":
                direct_ips.add(str(body.get("match")).split("/")[0])
    routed_direct = sorted({ep_ip(e) for e in eps} & direct_ips)
    print(f"  rules 中判给 DIRECT 的端点: {routed_direct if routed_direct else '（无）'}")
    # ⭐ f3.1：第二判据 —— 端点本身是国内知名解析器 IP 时，国内链路直连可达，
    # 无需在 rules 里写装饰性 DIRECT 规则（与 check_egern_dns.py 的 group_reach 判据 B 一致）。
    known_domestic = sorted({ep_ip(e) for e in eps} & DOMESTIC_RESOLVER_IPS)
    reachable = bool(routed_direct or known_domestic)
    if routed_direct:
        print("  ✅ 该组不依赖代理也永远活着（启动阶段代理未就绪时也能解析）。")
    elif known_domestic:
        print(f"  ✅ 端点 {known_domestic} 是国内知名解析器 IP ⇒ 国内链路直连可达，"
              f"无需 rules 里的 DIRECT 路由；该组同样不依赖代理。")
    else:
        print("  ⚠️ 该组端点既不在 rules 里判给 DIRECT、也不是已知的国内解析器 "
              "⇒ 无法证明它不经代理即可到达。")

    print()
    print("  proxy_nameservers:", "已配置" if pns else "未配置（代理 DNS 会共用 forward 并回退 bootstrap）")
    pns_bad = [e for e in pns if not ip_literal(e)]
    if pns:
        print(f"     {'✅ 全部 IP 字面量' if not pns_bad else '⚠️ 含主机名端点: ' + str(pns_bad)}")
        print("     官方：配置后代理 DNS **跳过 Forward**，直接走该列表 ⇒ 节点域名根本不会查 forward。")
    print(f"  bootstrap: {boot}")
    if any(str(b).strip() == "system" for b in boot):
        print("     ⚠️ 含 system ⇒ 主动把运营商 DNS 接进回退链。")
    elif boot:
        print("     ✅ 不含 system。")
    else:
        print("     ⚠️ 未配置 ⇒ 官方：自动使用系统 DNS 服务器（= 运营商下发的）。")

    # ---------- 结论 ----------
    print()
    print("=" * 100)
    ok = single and catch_value is not None and not bad_ep and reachable and pns and not pns_bad \
        and not any(str(b).strip() == "system" for b in boot) and not fails
    if ok:
        print("结论：✅ 通过")
        print("  任意域名（含以后换订阅新增的节点域名）在 forward 里都会得到同一个结果 "
              f"({catch_value})，")
        why = "在 rules 中被判 DIRECT" if routed_direct else f"是国内知名解析器（{known_domestic}）"
        print(f"  而该组端点为 IP 字面量、{why}、不依赖代理 ⇒ 不会掉进明文 bootstrap。")
        print("  ⇒ 换订阅/换机场**不需要修改 dns 段**。")
    else:
        print("结论：⚠️ 有需要确认的项")
        reasons = []
        if not single:
            reasons.append("forward 的非 reject 去向不止一个（或与兜底组不同）⇒ 新域名会落到兜底组，需人工确认")
        if catch_value is None:
            reasons.append("没有兜底规则 ⇒ 未命中的域名回退 Bootstrap（明文 UDP:53）")
        if bad_ep:
            reasons.append(f"兜底组含主机名端点 {bad_ep} ⇒ 触发 bootstrap 明文解析")
        if not reachable:
            reasons.append("兜底组端点既无 rules 里的 DIRECT 路由、也不是已知国内解析器 ⇒ 可能依赖代理")
        if not pns:
            reasons.append("未配置 proxy_nameservers ⇒ 代理 DNS 会共用 forward 并回退 bootstrap")
        if fails:
            reasons.append(f"{len(fails)} 个演练域名的结果与兜底不同")
        for r in reasons:
            print(f"  - {r}")
    print("=" * 100)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
