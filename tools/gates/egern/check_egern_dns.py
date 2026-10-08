"""DNS-leak audit for an Egern profile (f3).

f3 相对 f2 新增/修正的检查项，来自一次"审计通过但用户实测泄露"的复盘：
  * ⭐ 兜底组可达性：判据从「端点写 IP + 有显式路由」收紧为「端点写 IP + 至少一个判给
    DIRECT」。理由：官方只写了「未命中 Forward -> 回退 Bootstrap」，「命中组的端点全失败」
    是未定义行为；且兜底组经代理会引入「先有代理才能解析」的隐式依赖，启动阶段（规则集 /
    geoip·asn DB 下载、策略组首轮测速）代理未就绪时，解析会掉进 bootstrap 明文。
  * ⭐ 兜底指向**国内**组不再是 HIGH，而是 OK + 一条 LOW 说明。前提是它直连可达；按官方
    语义走代理的域名由节点远程解析、不经过 dns 段，所以"本地解析用国内解析器"影响面仅限
    DIRECT 域名。f2 那条"兜底指国内 = 既泄露又与 CDN 冲突"的判断是错的（它把"泄露"和
    "答案可能被污染"混为一谈，而真正致命的是**明文**）。

f2 相对 f1 的检查项（保留）：
  * proxy 的读取修对了 —— rule 的 policy 是嵌在类型字典里的（{domain: {match, policy}}），
    f1 里用 r.get("policy") 读会永远拿到 None，等于没查。
  * DNS 端点路由覆盖：no_resolve 之后 geoip 不再匹配域名，域名形式的加密 DNS 端点会
    一路落到 default 策略上。必须存在显式规则把国内端点钉到 DIRECT、境外端点钉到 Proxy。
  * 规则引用的策略必须能解析到已定义的策略组/代理/内建策略（抓出 `负载均衡` 这类笔误）。
  * rule_set.match 不是 URL 也不是文件路径的（如 `match: AI`）无法加载，属死规则。

Usage:
    python check_egern_dns.py profile.yaml [profile2.yaml ...]

Exit 0 = 无 HIGH 项，1 = 至少一条 HIGH。
"""
import os
import re
import sys

import yaml

# 输出含 emoji（🟡🟠🔴）：非 UTF-8 控制台（Windows 默认代码页）会 UnicodeEncodeError，
# 与其余收尾脚本统一强制 UTF-8（0929 外部审查指出本脚本缺此保护）。
try:
    for _s in (sys.stdout, sys.stderr):
        _s.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ⭐ 共享工具：DOMESTIC_RESOLVER_IPS / hostpart 等收编在 _egern_common.py，
#    与 audit_dns_forward.py 共用同一份实现 —— 不再有「两份拷贝靠注释同步」的隐患。
#    （二次核查报告 P1：判据本体同步了、helper 没同步，两脚本会对同一配置给出相反结论。）
# 共用模块定位：`_*_common` 统一在 tools/lib/（重组后不再与本脚本同目录）
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _cand in (_os.path.normpath(_os.path.join(_d, "..", "..", "lib")),
              _os.path.normpath(_os.path.join(_d, "..", "lib")), _d):
    if any(_os.path.isfile(_os.path.join(_cand, _m)) for _m in
           ("_surge_common.py", "_egern_common.py", "_clash_common.py")):
        _sys.path.insert(0, _cand)
        break

from _egern_common import (  # noqa: E402


    DOMESTIC_RESOLVER_IPS, hostpart as _common_hostpart,
)

IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
RULE_TYPES = (
    "domain", "domain_suffix", "domain_keyword", "domain_wildcard", "domain_regex",
    "geoip", "ip_cidr", "ip_cidr6", "asn", "rule_set", "url_regex", "user_agent",
    "dest_port", "protocol", "ssid", "bssid", "cellular", "and", "or", "not", "default",
)
IP_RULE_TYPES = ("geoip", "ip_cidr", "ip_cidr6", "asn")
BUILTIN = {"DIRECT", "REJECT", "PROXY"}
# 只用真正稳定的国内后缀，别把 .xyz/.top 这类通用后缀当成"国内"
DOMESTIC_SUFFIX = (".cn", ".com.cn", ".net.cn", ".org.cn", ".gov.cn")


def hostpart(server):
    """'https://8.8.8.8/dns-query' -> '8.8.8.8'; '[2400:3200::1]' -> '2400:3200::1'.

    实现已收编到 _egern_common.hostpart（正确处理 IPv6 方括号、:port、任意 scheme）。
    这里保留本名以便调用点不变。
    """
    return _common_hostpart(server)


def is_ip(h):
    return bool(IPV4.match(h)) or ":" in h


def pinned(h, hosts):
    if h in hosts:
        return True
    for k in hosts:
        if str(k).startswith("*.") and h.endswith(str(k)[1:]):
            return True
    return False


def rule_type(r):
    """规则的类型名（第一个 key）。"""
    for k in r:
        if k in RULE_TYPES:
            return k
    return None


def rbody(r):
    t = rule_type(r)
    return t, (r.get(t) if isinstance(r.get(t), dict) else None)


def is_disabled(r):
    t, b = rbody(r)
    return bool((b or {}).get("disabled")) if b is not None else False


# 能被判定为"捕获一切域名"的写法。官方 DNS 文档里 domain_wildcard 与 domain_regex
# 都能表达兜底；domain_regex 是 PCRE2 find 式（命中任意子串即算），故 '.'/'.*' 都覆盖全部域名。
CATCHALL_WILDCARD = {"*", "**"}
CATCHALL_REGEX = {".", ".*", ".+", "^.*", "^.+"}


def is_catchall(r):
    t, b = rbody(r)
    if b is None:
        return False
    m = str(b.get("match") or "").strip()
    if t == "domain_wildcard":
        return m in CATCHALL_WILDCARD
    if t == "domain_regex":
        return m in CATCHALL_REGEX
    return False


def audit(path):
    doc = yaml.safe_load(open(path, encoding="utf-8")) or {}
    high, low, ok = [], [], []

    dns = doc.get("dns") or {}
    upstreams = dns.get("upstreams") or {}
    hosts = dns.get("hosts") or {}
    proxy_ns = dns.get("proxy_nameservers") or []
    bootstrap = dns.get("bootstrap") or []
    forward = dns.get("forward") or []
    rules = [r for r in (doc.get("rules") or []) if isinstance(r, dict)]
    enabled = [r for r in rules if not is_disabled(r)]

    # ---- 0. 策略引用必须能解析 --------------------------------------------
    groups = set()
    for g in doc.get("policy_groups") or []:
        for v in g.values():
            if isinstance(v, dict) and v.get("name"):
                groups.add(v["name"])
    proxies = set()
    node_hosts = set()
    for p in doc.get("proxies") or []:
        for v in p.values():
            if isinstance(v, dict) and v.get("name"):
                proxies.add(v["name"])
            if isinstance(v, dict) and v.get("server"):
                srv = str(v["server"]).strip()
                if not is_ip(hostpart(srv)) and "." in hostpart(srv):
                    node_hosts.add(hostpart(srv))
    known = groups | proxies | BUILTIN
    for r in enabled:
        t, b = rbody(r)
        pol = (b or {}).get("policy")
        if pol and pol not in known:
            high.append(f"rule {t} references unknown policy '{pol}' - it can never be used")
    ok.append(f"policies resolve: {len(groups)} groups + {len(proxies)} proxies")

    # ---- 1. 加密 DNS 端点的主机名会被 bootstrap 明文解析 -------------------
    unresolved = []

    def judge(where, s):
        h = hostpart(s)
        if is_ip(h):
            ok.append(f"{where}: {s} 是 IP 字面量，不需要 bootstrap")
        elif pinned(h, hosts):
            ok.append(f"{where}: {s} 主机名已被 dns.hosts 钉住")
        else:
            unresolved.append(h)
            if h.endswith(DOMESTIC_SUFFIX):
                low.append(f"{where}: '{s}' 是域名且未钉 IP -> bootstrap 明文解析一次 '{h}'（国内域名，信号弱）")
            else:
                high.append(
                    f"{where}: '{s}' 是境外域名且未钉 IP -> bootstrap 会用明文 UDP:53 解析 '{h}'，"
                    f"ISP 可直接看到「本机在用该 DoH」。改用 IP 字面量或写进 dns.hosts['{h}']。"
                )

    for grp, servers in upstreams.items():
        for s in servers or []:
            judge(f"upstream {grp}", s)
    for s in proxy_ns:
        judge("proxy_nameserver", s)

    # ---- 2. proxy_nameservers 的语义与影响 --------------------------------
    # 官方：一旦设置，代理 DNS 查询强制走该列表并"完全绕过 forward 规则"，且强制直连。
    # 原配置若没有它，回退到"跟随 forward"才是符合预期的默认行为 —— 所以这里要判断的是
    # "不设置它，代理侧（尤其是节点域名）会不会掉回 bootstrap 明文"。
    def fwd_covers_name(h):
        """forward 里是否有非兜底规则能明确接住这个名字（兜底不算：它指向境外组，
        而代理侧连接是强制直连的，境外 DoH 在国内直连基本不通）。"""
        for r in forward:
            if is_catchall(r):
                continue
            t, b = rbody(r)
            if b is None:
                continue
            m = str(b.get("match") or "")
            if t == "domain" and m == h:
                return True
            if t == "domain_suffix" and (h == m or h.endswith("." + m)):
                return True
        return False

    if proxy_ns:
        ok.append(f"proxy_nameservers 已设置（{len(proxy_ns)} 个）")
        low.append(
            "设置了 proxy_nameservers -> 代理 DNS 的查询全部走该列表、绕过 forward 且强制直连。"
            "确认这是有意为之：它会成为代理侧解析的唯一出口。"
        )
    else:
        uncovered = sorted(h for h in node_hosts if not fwd_covers_name(h))
        if uncovered:
            low.append(
                f"proxy_nameservers 未设置，且这些节点域名没有显式 forward 规则：{uncovered}。"
                f"代理 DNS 强制直连，问不到境外解析器时会回退 bootstrap 明文（国内解析器）——"
                f"节点域名会明文暴露。为它们补 domain_suffix -> 国内加密组，或把节点改写成 IP。"
            )
        else:
            ok.append(
                "proxy_nameservers 未设置，但全部节点域名已被 forward 显式覆盖"
                "（或节点本就是 IP 形式）-> 代理 DNS 不会回退 bootstrap"
            )
    # ---- 2b. 明文回退面：bootstrap 是本文件唯一无法加密的出口 --------------
    # 官方原文：「Bootstrap …… 仅支持传统 UDP 协议（端口 53），且不遵循代理规则——流量直连」，
    # 且「未配置或解析失败时，自动使用系统 DNS 服务器」（system = Wi-Fi/蜂窝网络下发的 DNS）。
    # ⇒ 在运营商蜂窝上，明文 :53 要么被运营商透明重定向到它自己的解析器，要么直接失败后
    #   掉到系统 DNS —— 两条路的归属都是运营商。这正是「leak test 显示 china telecom」的机制。
    if any(str(x).strip().lower() == "system" for x in bootstrap):
        high.append(
            "dns.bootstrap 里含 'system' -> 把运营商下发的解析器直接接进了回退链"
            "（Wi-Fi 下是路由器、蜂窝下是运营商）。改成国内公共 DNS 的 IP 字面量。"
        )
    if not bootstrap:
        high.append("dns.bootstrap 为空 -> 回退到系统 DNS（运营商下发的那台）")
    elif len(bootstrap) < 2:
        low.append(
            f"bootstrap 只有 {len(bootstrap)} 个端点 -> 它一旦失败，官方规定会自动改用"
            f"「系统 DNS」（= 运营商）。建议列 2 个以上国内公共 DNS 的 IP 字面量。"
        )
    elif unresolved:
        low.append(f"bootstrap 仍需明文解析：{sorted(set(unresolved))}")
    else:
        ok.append(
            f"bootstrap {len(bootstrap)} 个端点、且无待解析项（加密端点全是 IP 或已钉 hosts），"
            f"正常运行不会触发"
        )

    # ---- 兜底组可达性：一个 upstreams 组是不是「不依赖代理也活得下来」--------
    # f3 新增。起因：f5 把 backstop 挂在「端点全为 IP、且都在 rules 里判给 Proxy」的境外组上，
    # 审计判了 OK，用户实测却看到 `upstream: bootstrap`。复盘发现两个漏洞：
    #   ① 官方只写了「未命中 Forward -> 回退 Bootstrap」，「命中组的端点全失败」是未定义行为，
    #      一旦它同样回退 bootstrap，兜底挂在必须经代理的组上就是一条明文通道；
    #   ② 兜底组经代理 => 隐式要求「先有代理才能解析」。启动阶段（规则集与 geoip/asn DB 下载、
    #      策略组首轮测速）代理尚未就绪，此时任何本地解析都会掉进 bootstrap 明文。
    # 所以判据从「端点写 IP + 有显式路由」收紧为「端点写 IP + 至少一个判给 DIRECT」。
    def endpoint_route(ip):
        for r in enabled:
            t, b = rbody(r)
            if t in ("ip_cidr", "ip_cidr6") and b is not None:
                m = str(b.get("match") or "")
                if m in (f"{ip}/32", f"{ip}/128"):
                    return b.get("policy")
        return None

    def group_reach(grp):
        """(可达性, 原因码, 说明)

        True  = 不依赖代理也活得下来。判据（二者满足其一即可）：
                 A. 至少一个端点 IP 在 rules 里判给 DIRECT（显式路由证据）；
                 B. 端点全为 IP 字面量，且**至少一个是国内知名解析器 IP**
                    （DOMESTIC_RESOLVER_IPS —— 其国内直连可达性是公开事实）。
        False = 需要 bootstrap 明文（'hostname'）或必须经代理才可达（'proxy_only'）
        None  = 组不存在或为空（'missing'）

        ⭐ 判据 B 是 f3.1 新增。起因：f10 把 DNS 端点路由规则整段删掉后（依据是
        「端点全是 IP 字面量 ⇒ 不需要在 rules 里钉路由」，历史依据见 f10 迭代记录），
        只有判据 A 会让这类配置**永远**判负 —— 判据与设计意图互相排斥。
        但也不能退回「端点全为 IP 即判可达」：那会放行一个**全由境外 IP 组成**的组
        （f5 的真实踩坑：兜底挂在必须经代理的境外组上，审计 OK、实测泄露）。
        所以用「国内知名解析器 IP」这个在 profile 文本内可验证、且语义等价于
        「直连可达」的证据，替代 ip_cidr 装饰性规则。
        """
        servers = upstreams.get(grp) or []
        if not servers:
            return None, "missing", f"组 {grp} 不存在或为空"
        hn = sorted({hostpart(s) for s in servers if not is_ip(hostpart(s))})
        if hn:
            return False, "hostname", f"含主机名端点 {hn} -> 需 bootstrap 明文解析"
        pols = {hostpart(s): endpoint_route(hostpart(s)) for s in servers}
        direct = sorted(ip for ip, p in pols.items() if str(p or "").upper() == "DIRECT")
        if direct:
            return True, "ok", f"{len(pols)} 个端点全为 IP，其中 {direct} 判给 DIRECT"
        known = sorted(ip for ip in pols if ip in DOMESTIC_RESOLVER_IPS)
        if known:
            return True, "ok_domestic_resolver", (
                f"{len(pols)} 个端点全为 IP，其中 {known} 是国内知名解析器"
                f"（国内链路直连可达，无需 rules 里的 DIRECT 路由）"
            )
        return False, "proxy_only", (
            f"端点全为 IP，但无一在 rules 里判给 DIRECT，也都不是已知的国内解析器"
            f"（当前 {pols}）-> 无法证明它不经代理即可到达"
        )

    # ---- 3. forward 必须有"捕获一切"的兜底，且兜底组必须直连可达 ----------
    if not forward:
        high.append("dns.forward 为空 -> 默认 DNS 全部回退 bootstrap（明文国内解析器）")
    else:
        catches = [r for r in forward if is_catchall(r)]
        if not catches:
            high.append(
                "forward 里没有捕获一切的兜底规则 -> 未匹配的域名会回退 bootstrap 明文解析"
                "（电信蜂窝上就是运营商归属）。补一条 domain_wildcard:'*'（或 domain_regex:'.'）。"
            )
        else:
            vals = [str((rbody(r)[1] or {}).get("value")) for r in catches]
            for val in sorted(set(vals)):  # 两条兜底常指向同一个组，去重免得重复报警
                lv = val.lower()
                if lv == "system":
                    high.append(
                        "forward 兜底 = system -> 未命中规则的域名直接交给系统 DNS，蜂窝下就是运营商"
                    )
                    continue
                if lv in ("bootstrap", "bootstrap_dns"):
                    low.append("forward 兜底 = bootstrap -> 明文 UDP:53，蜂窝上会被运营商接管")
                    continue
                reach, reason, detail = group_reach(val)
                if reach:
                    ok.append(f"forward 兜底 {val} 直连可达（{detail}）-> 不依赖代理，不会回退 bootstrap")
                    if "domestic" in lv:
                        low.append(
                            f"forward 兜底指向国内组（{val}）-> 需要本地解析的境外域名会拿到国内答案"
                            f"（可能被污染）。按官方语义走代理的域名由节点远程解析、不经过 dns 段，"
                            f"实际影响面仅限 DIRECT 域名；确认这是有意为之。"
                        )
                elif reason == "proxy_only":
                    high.append(
                        f"forward 兜底组 {val} 依赖代理（{detail}）-> 官方只写了「未命中 Forward 回退 "
                        f"Bootstrap」，「命中组全失败」会怎样没写；且启动阶段（规则集 / geoip·asn DB "
                        f"下载、策略组首轮测速）代理未就绪，那时这次解析会掉进 bootstrap 明文。"
                        f"把兜底改为一个「直连可达」的组（如国内加密组）。"
                    )
                else:
                    high.append(
                        f"forward 兜底组 {val} 不安全（{detail}）-> 解析失败会回退 bootstrap 明文，"
                        f"蜂窝上就是运营商归属"
                    )
        # 靠前规则（不含兜底本身）指向境外组 —— 只提示，不算错
        early = []
        for r in forward:
            if is_catchall(r):
                continue
            v = str((rbody(r)[1] or {}).get("value"))
            if "foreign" in v.lower():
                early.append(v)
        if early:
            low.append(
                f"forward 里出现了指向境外组的靠前规则（{sorted(set(early))}）-> 这些域名会被固定"
                f"走境外上游；确认是有意为之"
            )

    # ---- 3b. forward 的 value 里不能出现明文出口 --------------------------
    # 官方：value 除了组名，还接受特殊值 `bootstrap`（明文 UDP:53）与 `system`（系统 DNS）。
    # `system` 在蜂窝下 = 运营商 -> 等同于主动泄露，必判 HIGH。
    # `bootstrap` 官方示例确实用它接国内域名（`domain_suffix: cn -> bootstrap`），所以只提示；
    # 但对「防泄露到运营商」这个目标而言，它仍是一条明文路径，能换成国内加密组就换。
    sys_rules, boot_rules = [], []
    for r in forward:
        t, b = rbody(r)
        v = str((b or {}).get("value", "")).strip().lower()
        if v == "system":
            sys_rules.append(f"{t}:{b.get('match')}")
        elif v in ("bootstrap", "bootstrap_dns"):
            boot_rules.append(f"{t}:{b.get('match')}")
    if sys_rules:
        high.append(
            f"forward 的 value 出现 'system'（{sys_rules}）-> 这些域名直接由系统 DNS 解析，"
            f"蜂窝下就是运营商解析器。改成国内加密组名。"
        )
    if boot_rules:
        low.append(
            f"forward 的 value 出现 'bootstrap'（{boot_rules}）-> 走明文 UDP:53。"
            f"国内域名这样写是官方示例做法、可接受；但若目标是「不出现任何运营商归属」，"
            f"请换成国内加密组名。"
        )

    # ---- 4. IP 类规则必须带 no_resolve ------------------------------------
    for r in enabled:
        t, b = rbody(r)
        if t in IP_RULE_TYPES and b is not None:
            if not b.get("no_resolve"):
                low.append(
                    f"rule {t}:{b.get('match')} 没有 no_resolve -> 会为匹配该规则触发一次本地 DNS 解析"
                )
    if not any(rbody(r)[0] == "geoip" and (rbody(r)[1] or {}).get("no_resolve") for r in enabled):
        low.append("没有带 no_resolve 的 geoip 规则 -> 每个域名都要先本地解析一次才能判归属")
    else:
        ok.append("geoip 带 no_resolve")

    # ---- 5. DNS 端点必须有显式路由（no_resolve 之后的域名侧缺口）----------
    def routes_of(h):
        """返回能覆盖该端点的显式规则描述。

        ⚠️ 早先有个 `want` 形参，调用处传了「期望策略」、函数体里**从没用过**
        （策略判断在调用处另算了一遍）—— 2026-09-25 去掉死参数，避免读者以为它会按
        「期望策略」筛选。
        """
        hits = []
        for r in enabled:
            t, b = rbody(r)
            if b is None:
                continue
            m = str(b.get("match", "")).lower()
            if t in ("domain", "domain_suffix", "domain_keyword", "domain_wildcard") and not is_ip(h):
                if h == m or h.endswith(m.lstrip("*.")):
                    hits.append(f"{t}:{m}->{b.get('policy')}")
            elif t in ("ip_cidr", "ip_cidr6") and is_ip(h):
                if str(m).split("/")[0] == h:
                    hits.append(f"{t}:{m}->{b.get('policy')}")
        return hits

    has_ruleset = any(rule_type(r) == "rule_set" for r in enabled)
    for grp, servers in upstreams.items():
        foreign = "foreign" in grp.lower()
        for s in servers or []:
            h = hostpart(s)
            want = "Proxy" if foreign else "DIRECT"
            hits = routes_of(h)
            if hits:
                ok.append(f"端点 {h} 有显式路由 {hits[0]}（期望 {want}）")
            elif not foreign and is_ip(h) and h in DOMESTIC_RESOLVER_IPS:
                # ⭐ f3.1：端点本身是国内知名解析器 IP —— 它不经代理即可直达，
                # 不需要在 rules 里再钉一条装饰性 DIRECT 规则（与 group_reach 判据 B 一致）。
                ok.append(
                    f"端点 {h} 是国内知名解析器 IP，国内链路直连可达，无需显式 DIRECT 路由"
                )
            else:
                # 是否靠 default 兜住？那对国内端点就是错的
                dr = [r for r in enabled if rule_type(r) == "default"]
                dpol = (rbody(dr[0])[1] or {}).get("policy") if dr else None
                if not foreign and dpol not in (None, "DIRECT") and has_ruleset:
                    # 不能直接判 HIGH：某个 rule_set（例如 ChinaMax.list）里可能带
                    # DOMAIN-SUFFIX,cn 兜住它。但这条依赖无法在本脚本里展开验证，
                    # 一旦该集合加载失败，国内端点就会被绕到境外出口。
                    low.append(
                        f"国内 DNS 端点 {h} 没有显式 DIRECT 规则，目前只能依赖某个 rule_set 内的 "
                        f"DOMAIN-SUFFIX 兜底；若该集合加载失败就会落到 default->{dpol} —— "
                        f"国内 DNS 查询被绕到境外出口。建议补一条显式 domain_suffix 规则。"
                    )
                elif not foreign and dpol not in (None, "DIRECT"):
                    high.append(
                        f"国内 DNS 端点 {h} 没有任何 DIRECT 兜底，会落到 default->{dpol}，"
                        f"国内 DNS 查询被绕到境外出口（或直接失败）"
                    )
                elif foreign and dpol in (None, "DIRECT"):
                    high.append(f"境外 DNS 端点 {h} 会落到 default->{dpol} 直连 -> 被运营商阻断/劫持")
                else:
                    low.append(f"端点 {h} 无显式路由，依赖 default->{dpol}")

    for s in proxy_ns:
        h = hostpart(s)
        if not is_ip(h) and not pinned(h, hosts) and not any(
                rbody(r)[0] in ("domain", "domain_suffix") and h.endswith(str((rbody(r)[1] or {}).get("match", "")).lstrip("*."))
                for r in enabled):
            low.append(f"proxy_nameserver {h} 无显式路由（代理 DNS 强制直连，通常无需规则）")

    # ---- 6. 反污染 / fake-IP 相关 ----------------------------------------
    if not dns.get("block_ips"):
        low.append("dns.block_ips 未设置 -> 0.0.0.0 这类空路由式污染应答会被照单收下")
    else:
        ok.append(f"block_ips = {dns['block_ips']}")
    if not doc.get("hijack_dns"):
        high.append("hijack_dns 为空 -> 应用自己发出的明文 :53 查询不被接管")
    else:
        ok.append(f"hijack_dns = {doc['hijack_dns']}")
    if not doc.get("real_ip_domains"):
        low.append(
            "real_ip_domains 为空 -> 走不到隧道的流量（APNs / 内网）也会拿到 Fake IP，"
            "可能导致推送或内网访问异常"
        )
    else:
        ok.append(f"real_ip_domains = {doc['real_ip_domains']}")
    if doc.get("ipv6"):
        high.append("ipv6 已开启 -> AAAA 查询可能绕过 IPv4 钉定")
    else:
        ok.append("ipv6 关闭")

    # ---- 7. 死规则（rule_set.match 既不是 URL 也不是路径）-----------------
    for r in enabled:
        t, b = rbody(r)
        if t == "rule_set" and b is not None:
            m = str(b.get("match", ""))
            if not (m.startswith("http://") or m.startswith("https://") or m.endswith(".yaml") or m.endswith(".list") or "/" in m):
                low.append(f"rule_set match='{m}' 既不是 URL 也不是文件路径 -> 该规则无法加载，等同死规则")

    # ---- 8. profile 自身运行所必需的解析（延迟测试 / 策略组图标）----------
    # 这一类的名字不是"用户要访问的网站"，但 Egern 每次节点测速都要解析一遍，
    # 与用户访问什么无关，所以它的泄露是"持续型"而不是"偶发型"。
    # 实测这些名字普遍不在 ChinaDomain.list 里（cp.cloudflare.com / hicloud.com 均 0 命中），
    # 于是落到 forward 兜底 = 境外组。境外组（8.8.8.8 / 1.1.1.1 DoH）只有在「经代理」时才通；
    # 而代理侧解析（代理 DNS）是强制直连的 -> 直连问 8.8.8.8:443 在电信线路上必然失败
    # -> 回退 bootstrap 明文 -> bootstrap 也不通时按官方文档「自动使用系统 DNS」
    # -> 系统 DNS = Wi-Fi 下发的运营商解析器。这就是"漏到中国电信/联通"的完整链条。
    def _glob(pat, s):
        return re.fullmatch(pat.replace(".", r"\.").replace("*", ".*").replace("?", "."), s) is not None

    def fwd_value(host):
        """第一条覆盖该主机名的 forward 规则 -> (value, 是否落在兜底上)。"""
        for r in forward:
            t, b = rbody(r)
            if b is None or b.get("disabled"):
                continue
            m = str(b.get("match") or "").lower()
            hit = False
            if t == "domain":
                hit = m == host
            elif t == "domain_suffix":
                hit = host == m or host.endswith("." + m)
            elif t == "domain_keyword":
                hit = m in host
            elif t == "domain_wildcard":
                hit = _glob(m, host)
            elif t == "domain_regex":
                try:
                    hit = re.search(str(b.get("match")), host) is not None
                except re.error:
                    hit = False
            if hit:
                return str(b.get("value")), is_catchall(r)
        return None, False

    def group_ready(grp):
        """兜底组是否「不依赖代理也活得下来」——判据统一见 group_reach。"""
        reach, _reason, detail = group_reach(grp)
        return bool(reach), detail

    selfneed = []
    for key in ("proxy_latency_test_url", "direct_latency_test_url"):
        h = hostpart(doc.get(key) or "")
        if h and not is_ip(h):
            selfneed.append((key, h, True))
    for g in doc.get("policy_groups") or []:
        for v in g.values():
            if isinstance(v, dict) and isinstance(v.get("icon"), str):
                h = hostpart(v["icon"])
                if h and not is_ip(h):
                    selfneed.append(("policy_groups[].icon", h, False))

    seen = set()
    for key, h, critical in selfneed:
        if h in seen or pinned(h, hosts):
            continue
        seen.add(h)
        val, is_def = fwd_value(h)
        if val is not None and not is_def:
            ok.append(f"自身必需解析 {key} 的 {h} -> {val}（不经兜底）")
            continue
        ready, detail = group_ready(val)
        if ready:
            ok.append(
                f"自身必需解析 {key} 的 {h} 落到兜底组 {val}，而该组直连可达（{detail}）"
                f"-> 不依赖代理、不会回退明文"
            )
            continue
        msg = (
            f"自身必需解析 {key} 的域名 '{h}' 没有靠前的 forward 规则接住"
            f"（落到兜底 -> {val}；该组不可直连：{detail}）-> 解析失败会回退 bootstrap 明文、"
            f"再落到系统 DNS（运营商）。请补一条 domain/domain_suffix -> 国内加密组，"
            f"或把兜底换成直连可达的组。"
        )
        (high if critical else low).append(f"[自身解析] {msg}")

    return high, low, ok


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rc = 0
    for path in sys.argv[1:]:
        try:
            high, low, ok = audit(path)
        except Exception as e:  # noqa: BLE001
            print(f"=== {path} ===\n  ERROR {type(e).__name__}: {e}\n")
            rc = 1
            continue
        print(f"=== {path} ===")
        for m in ok:
            print(f"  OK   {m}")
        for m in low:
            print(f"  LOW  {m}")
        for m in high:
            print(f"  HIGH {m}")
        print(f"\n  summary: {len(high)} high, {len(low)} low, {len(ok)} ok\n")
        if high:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
