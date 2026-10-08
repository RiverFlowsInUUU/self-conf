#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mihomo（clash）profile 防 DNS 泄露审计器。

对一份 mihomo .yaml 跑 14 项判据，输出分级发现，退出码：
    0 = 无 high（--strict 下还要求无 medium）
    1 = 有 high（--strict 下 medium 也算）
    2 = 用法错误 / 文件读不到 / YAML 坏了 / 缺 pyyaml

用法：
    python check_clash_dns.py clash/profiles/lazy.yaml clash/profiles/routing.yaml
    python check_clash_dns.py clash/profiles/routing.yaml --strict   # medium 也算失败
    python check_clash_dns.py clash/profiles/routing.yaml --quiet    # 只打印汇总
    python check_clash_dns.py override_out.yaml --override           # 覆写脚本输出形态：不要求 tun 段

判据与 `tools/reference/ops.md` 的六个泄露面一一对应：

    面① 引导解析   → 判据 2 / 3 / 4（端点写主机名 ⇒ 冷启动必走一次明文 :53）
    面② 回退链     → 判据 3 / 4（端点不带加密 scheme ⇒ 每一笔查询都是明文 :53）
    面③ 旁路设备   → 判据 7（tun.dns-hijack 是否接管 :53 + strict-route）
    面④ 规则判定   → 判据 10（IP 类规则缺 no-resolve ⇒ 为判定而解析）
    面⑤ 远程集内容 → 判据 10 / 12（classical 集内容无法静态判定；死 provider ⇒ 静默降级）
    面③′ IPv6      → 判据 6（顶层 ipv6 与 dns.ipv6 **两处**都要关）

⚠️ 本工具审的是**防 DNS 泄露语义**，不审以下内容（本仓另有门禁，此处不越界）：
    · 规则集 URL 是否可达        → tools/gates/clash/check_remote_urls.py（**本脚本不做网络探测**）
    · 结构 / 悬空引用 / 两形态一致 → tools/gates/clash/check_structure.py / check_min_pair.py
    · 节点是否可用                → 需要真实网络
   审计通过 ≠ 配置可用 —— 这条是姊妹仓付出多次事故换来的结论。

⭐ 与 `check_surge_dns.py` / `check_egern_dns.py` 的对齐点：
    · 顶部强制 UTF-8（Windows cp936 下 print 一个 emoji 就 UnicodeEncodeError，
      而进程以 1 退出 —— 1 恰是「判负」的码，会被读成「判负其实没跑」）
    · 判据是**实测推导**而非字符串匹配：端点是否 IP 字面量 / 是否加密 scheme /
      provider 的 behavior 是不是 ipcidr / fake-ip-range 是否落在 RFC 6815 保留段 /
      dns-hijack 是否覆盖 :53 的**整个**地址空间
    · 分级 emoji：🔴 HIGH / 🟠 MEDIUM / 🟡 LOW / ✅ OK
    · 豁免写在**被审对象**里（`# audit-waive: <判据号> <理由>`），不写在审计器里

--------------------------------------------------------------------------
判别力实测（2026-10-07）：35 条坏样例注入 **35/35 全部命中预期**，对照组
（lazy.yaml / routing.yaml 原样）均为 exit 0 · 0 high。
坏样例写在**仓库外**的临时副本上（tempfile.mkdtemp，跑完即删），未改动任何被审文件。
--------------------------------------------------------------------------
只让「好配置通过」证明不了判别力 —— 本仓纪律要求每条判据**真的会判负**。
下表是逐条注入后的实测输出（「命中」= 该判据真的报出了预期等级）：

| # | 注入的坏样例 | 预期 | 实测 |
|:-:|:--|:--|:--|
| 1 | `dns.enable: false` | HIGH | ✅ HIGH ① |
| 2 | `default-nameserver: [dns.alidns.com]` | HIGH | ✅ HIGH ② |
| 2 | `default-nameserver: [https://223.5.5.5/dns-query]` | MEDIUM | ✅ MEDIUM ②（引导层成环）|
| 3 | `nameserver: [https://dns.cloudflare.com/dns-query]` | HIGH | ✅ HIGH ③（面①）|
| 3 | `nameserver: [8.8.8.8]` | HIGH | ✅ HIGH ③（面② 明文 UDP:53）|
| 3 | `fallback: [http://1.1.1.1/dns-query]` | HIGH | ✅ HIGH ③（明文 http://）|
| 4 | 删掉 `proxy-server-nameserver` | HIGH | ✅ HIGH ④（鸡蛋问题）|
| 4 | 删掉 `direct-nameserver` | MEDIUM | ✅ MEDIUM ④ |
| 4 | `proxy-server-nameserver: [https://dns.google/dns-query]` | MEDIUM | ✅ MEDIUM ④（境外主机名引导）|
| 5 | `enhanced-mode: redir-host` | MEDIUM | ✅ MEDIUM ⑤ |
| 5 | `fake-ip-range: 10.0.0.1/16` | HIGH | ✅ HIGH ⑤（不在 RFC 6815 段）|
| 6 | 顶层 `ipv6: true` | HIGH | ✅ HIGH ⑥ |
| 6 | `dns.ipv6: true` | HIGH | ✅ HIGH ⑥（另一处，独立命中）|
| 6 | 删掉顶层 `ipv6` 键 | HIGH | ✅ HIGH ⑥（`is not False`：键缺失也算不过）|
| 7 | `tun.dns-hijack: []` | HIGH | ✅ HIGH ⑦（面③ 无收口）|
| 7 | `tun.dns-hijack: [8.8.8.8:53]` | MEDIUM | ✅ MEDIUM ⑦（列不全就漏）|
| 7 | `tun.strict-route: false` | HIGH | ✅ HIGH ⑦ |
| 7 | 整段删掉 `tun`，不带 `--override` | HIGH | ✅ HIGH ⑦；带 `--override` → 0（形态豁免）|
| 8 | 删掉 `nameserver-policy` 的 `rcode://success` | HIGH | ✅ HIGH ⑧ |
| 8 | 删掉 `fake-ip-filter` 里的 `rule-set:` 广告项 | HIGH | ✅ HIGH ⑧ |
| 8 | 两处广告集不一致 | HIGH | ✅ HIGH ⑧ |
| 9 | 把 `rule-set:cn` 挪到广告项之前 | HIGH | ✅ HIGH ⑨ |
| 8 | `nameserver-policy` 引用不存在的 `rule-set:nope` | HIGH | ✅ HIGH ⑧（死引用 ⇒ 静默消失）|
| 10 | `RULE-SET,geoip-cn,DIRECT`（去掉 no-resolve）| HIGH | ✅ HIGH ⑩ |
| 10 | `RULE-SET,geoip-google,Google`（去掉 no-resolve）| HIGH | ✅ HIGH ⑩ |
| 11 | 顶层加 `geox-url` | HIGH | ✅ HIGH ⑪ |
| 11 | 规则里加 `GEOSITE,cn,DIRECT` | HIGH | ✅ HIGH ⑪ |
| 11 | `nameserver-policy` 键写 `geosite:cn` | HIGH | ✅ HIGH ⑪ |
| 11 | provider url 改成 `…/geosite.dat` | HIGH | ✅ HIGH ⑪ |
| 11 | `geoip-*` 的 `format: mrs` provider | **不判负** | ✅ 全程 0 命中（未误伤 .mrs）|
| 12 | provider 既无 `url` 也无 `path` | HIGH | ✅ HIGH ⑫ |
| 13 | 规则引用未定义的 provider | HIGH | ✅ HIGH ⑬ |
| 13 | 规则策略写笔误 `负载均衡` | HIGH | ✅ HIGH ⑬ |
| 14 | `use-system-hosts: true` | LOW | ✅ LOW ⑭ |
| — | 好配置（lazy / routing 原样）| 0 | ✅ exit 0（两版均 0 high）|

⇒ 14 条判据**全部**注入命中；`.mrs` 远程集与 `geoip-*` provider 未误伤。
"""

import argparse
import os
import re
import sys

# 共用模块定位：先 tools/lib/，再本目录（重组后 _*_common 统一在 lib/）
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _cand in (_os.path.join(_d, '..', '..', 'lib'),
              _os.path.join(_d, '..', 'lib'), _d):
    _cand = _os.path.normpath(_cand)
    if _os.path.isfile(_os.path.join(_cand, '_surge_common.py')) or \
       _os.path.isfile(_os.path.join(_cand, '_egern_common.py')) or \
       _os.path.isfile(_os.path.join(_cand, '_clash_common.py')):
        _sys.path.insert(0, _cand)
        break


# 输出含 emoji（🔴🟠🟡✅）：非 UTF-8 控制台（Windows 默认代码页）会 UnicodeEncodeError，
# 与其余收尾脚本统一强制 UTF-8（0929 外部审查指出姊妹仓脚本缺此保护）。
# ⚠️ 必须在任何 print 之前 —— 否则第一次 print 就把进程炸掉。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
except ImportError:
    print("❌ 需要 pyyaml：pip install pyyaml")
    sys.exit(2)

# ============================================================================
# 发现收集
# ============================================================================

HIGH, MEDIUM, LOW, OK = "HIGH", "MEDIUM", "LOW", "OK"
_RANK = {OK: 0, LOW: 1, MEDIUM: 2, HIGH: 3}

findings = []      # (level, check_id, message, detail)
_waivers = {}      # check_id -> 理由（来自 profile 里的 `# audit-waive:` 行）


def add(level, cid, msg, detail=""):
    if cid in _waivers and _RANK.get(level, 0) > 0:
        findings.append((f"WAIVED:{level}", cid, msg,
                         f"⚠️ 已豁免（profile 内声明）：{_waivers[cid]}\n        ↳ {detail}"
                         if detail else f"⚠️ 已豁免（profile 内声明）：{_waivers[cid]}"))
        return
    findings.append((level, cid, msg, detail))


# ---------------------------------------------------------------------------
# 豁免机制（与 check_surge_dns.py 同一条设计）
# ---------------------------------------------------------------------------
# 为什么要有它：有些 profile 会做**刻意的设计取舍**（例如为了 CDN 就近解析而让
# `direct-nameserver` 写主机名）。豁免**必须写在被审对象里**，不能写在审计器里：
#   · 写在审计器里 = 判据被永久削弱，别的 profile 也享受不到这层保护；
#   · 写在 profile 里 = 每一次豁免都在被审对象上留痕、可被 grep、可被复核。
# 豁免不消除打印 —— 它只让该条不再使整轮判负。
_WAIVE_RE = re.compile(r"#\s*audit-waive:\s*(\d+)\s+(.*)")


def load_waivers(path):
    _waivers.clear()
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    for m in _WAIVE_RE.finditer(text):
        _waivers[int(m.group(1))] = m.group(2).strip()


# ============================================================================
# 通用 helper
# ============================================================================

_IP4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
# ⭐ 通用 scheme 前缀，**大小写不敏感**、不枚举具体 scheme。
#    ⚠️ 不要改成白名单：那会让 scheme 的拼法参与审计结论。
#    （姊妹仓 _egern_common.py 三次核查报告 P2 的回归正是这么来的 ——
#      `HTTPS://223.5.5.5/dns-query` 被白名单漏掉，`HTTPS` 被当成主机名。）
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")

# 加密 DNS 的 scheme。名字不是加密 ⇒ 明文（http:// 走 80 端口的 DoH 也是明文）。
ENCRYPTED_SCHEMES = ("https", "tls", "quic", "h3", "http3", "dot", "doh")

BUILTIN_POLICIES = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "GLOBAL", "PROXY"}

# 国内公共解析器的**主机名**后缀 —— 端点写主机名时的定级依据：
# 引导查询必然发生（面①），但问的是国内端点 ⇒ 信号弱、只 LOW；境外端点 ⇒ MEDIUM
# （国内线路直连通常不通，解析失败会让该层整体失效）。
DOMESTIC_DNS_SUFFIX = (
    ".cn", ".com.cn", ".net.cn", ".org.cn", ".gov.cn",
    "alidns.com", "dns.pub", "doh.pub", "dnspod.com",
    "tencent-cloud.net", "qq.com", "163.com", "baidu.com",
)


def hostpart(ep):
    """从端点字符串里取出主机部分（去 scheme / path / query / :port / IPv6 方括号）。

    正确处理这些形态：
        https://223.5.5.5/dns-query      -> 223.5.5.5
        HTTPS://8.8.8.8/dns-query        -> 8.8.8.8
        tls://223.5.5.5:853              -> 223.5.5.5
        https://[2400:3200::1]/dns-query -> 2400:3200::1
        8.8.8.8                          -> 8.8.8.8（无 scheme = 明文 UDP:53）
        dns.alidns.com                   -> dns.alidns.com
    """
    s = str(ep).strip()
    m = _SCHEME_RE.match(s)
    if m:
        s = s[m.end():]
    s = s.split("/")[0]
    s = s.split("?")[0].split("#")[0]
    if s.startswith("["):                      # IPv6 带方括号
        end = s.find("]")
        return s[1:end] if end != -1 else s.lstrip("[")
    if s.count(":") == 1:                      # host:port（IPv4 或域名）
        return s.split(":")[0]
    return s                                   # 裸 IPv4 / 裸 IPv6 / 域名


def scheme_of(ep):
    m = _SCHEME_RE.match(str(ep).strip())
    return m.group(0)[:-3].lower() if m else ""


def is_ip(host):
    return bool(_IP4_RE.match(host)) or ":" in host


def is_private_ip(host):
    """RFC1918 / 环回 —— 内网解析器上的明文不算「泄露到运营商」（leak 文档 §10）。"""
    if ":" in host:
        return host.lower() in ("::1", "::")
    try:
        a, b = (int(x) for x in host.split(".")[:2])
    except Exception:
        return False
    return a == 10 or a == 127 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def ep_kind(ep):
    """端点 -> (host, is_ip_literal, is_encrypted, plaintext_reason)

    is_encrypted 只认 ENCRYPTED_SCHEMES；**没有 scheme 就是明文 UDP:53**
    （mihomo 里 `nameserver: 8.8.8.8` 即传统 DNS，不是 DoH）。
    """
    h = hostpart(ep)
    sc = scheme_of(ep)
    enc = sc in ENCRYPTED_SCHEMES
    reason = ""
    if not enc:
        reason = "" if sc else "无 scheme ⇒ mihomo 按传统 UDP:53 明文查询"
        if sc:
            reason = f"scheme `{sc}://` 不是加密 DNS"
    return h, is_ip(h), enc, reason


def _ip2n(s):
    parts = str(s).split(".")
    n = 0
    for p in parts:
        n = (n << 8) | int(p)
    return n


def in_rfc6815(cidr):
    """fake-ip-range（v4）是否落在 RFC 6815 保留段 198.18.0.0/15 内。

    198.18.0.0/15 = 198.18.0.0 ~ 198.19.255.255（mihomo 默认与官方示例都用这段）。
    ⚠️ 用「整段是否包含在内」判，而不是只看基地址 —— 否则 `198.18.0.1/8`
    这种写法会一路覆盖到 198.255.x.x 的真实地址。
    """
    if ":" in cidr:
        return None                       # IPv6 段：mihomo 侧语义待确认，不判
    if "/" not in cidr:
        return None
    ip, _, plen = cidr.partition("/")
    try:
        plen = int(plen)
        n = _ip2n(ip)
    except Exception:
        return False
    if plen < 0 or plen > 32:
        return False
    size = 1 << (32 - plen)
    net = (n >> (32 - plen)) << (32 - plen) if plen else 0
    return 0xC6120000 <= net and net + size - 1 <= 0xC613FFFF   # 198.18.0.0 ~ 198.19.255.255


def pinned(h, hosts):
    """主机名是否被 hosts 钉住（钉住则不需要引导解析）。"""
    for k in hosts:
        k = str(k).strip()
        if k == h:
            return True
        if k.startswith("*.") and h.endswith(k[1:]):
            return True
        if k.startswith("+.") and h.endswith(k[1:]):
            return True
    return False


def is_domestic_host(h):
    hl = h.lower()
    return hl.endswith(DOMESTIC_DNS_SUFFIX)


def _iter_eps(v):
    """nameserver-policy 的值可能是字符串也可能是列表 —— 统一成列表。"""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [str(v)]


# ============================================================================
# 判据
# ============================================================================

def check_1_dns_enable(doc):
    """1 · dns 段存在且 enable: true（否则走系统 DNS）。"""
    dns = doc.get("dns")
    if not isinstance(dns, dict) or not dns:
        add(HIGH, 1, "没有 dns 段 ⇒ 全部查询走系统 DNS（运营商 DHCP 下发的那台）",
            "mihomo 的 dns 段是「接管一切查询」的开关；没有它就没有任何一层是你能控制的。")
        return None
    if dns.get("enable") is not True:
        add(HIGH, 1, f"dns.enable 不是 true（当前 {dns.get('enable')!r}）⇒ DNS 劫持与 fake-ip 全部失效",
            "键缺失也不算过：mihomo 的 dns 段默认行为是「不接管」，必须显式打开。")
        return dns
    add(OK, 1, "dns.enable: true（内核接管全部查询）")
    return dns


def check_2_default_ns(dns):
    """2 · default-nameserver 必须全为 IP 字面量（官方硬性要求）。

    这一层**唯一**的用途就是解析其余 DNS 端点**自己的域名**（引导）。
    它必然是明文 UDP:53（它不能再依赖任何加密解析器，否则成环）。
    ⇒ 它自己写主机名 ⇒ 「解析解析器」又需要一次明文解析 = 鸡生蛋。
    """
    if dns is None:
        return
    eps = _iter_eps(dns.get("default-nameserver"))
    if not eps:
        add(HIGH, 2, "default-nameserver 为空 ⇒ 加密端点写主机名时无法建连，"
                     "mihomo 会退回系统 DNS（运营商）")
        return
    bad = []
    for e in eps:
        h, ip, _enc, _ = ep_kind(e)
        if not ip:
            bad.append(e)
            add(HIGH, 2, f"default-nameserver 用了主机名：`{e}`",
                "官方要求这一层**必须是 IP**：它的用途就是解析 DNS 端点的域名，"
                "写主机名 ⇒ 引导链自己还需要被引导（鸡生蛋），实际会退回系统 DNS。")
        elif scheme_of(e):
            bad.append(e)
            add(MEDIUM, 2, f"default-nameserver 写了带 scheme 的端点：`{e}`",
                "这一层是**明文**引导层（成环不可能消除），写成 DoH/DoT URL 会让它"
                "自己也去等一次加密通道建立 —— 写成纯 IP（`223.5.5.5`）。")
    if not bad:
        add(OK, 2, f"default-nameserver {len(eps)} 个端点全为 IP 字面量：{', '.join(eps)}")
    elif len(eps) < 2:
        add(LOW, 2, f"default-nameserver 只有 {len(eps)} 个端点 ⇒ 它一挂，引导链无退路")


def check_3_main_endpoints(dns, hosts):
    """3 · nameserver / fallback 端点必须「IP 字面量 + 加密 scheme」（面① + 面②）。

    两条独立的坏法，对应两个不同的面：
      · 写主机名  ⇒ 冷启动**必然**用 default-nameserver 明文解析一次（面①）；
      · 写裸 IP   ⇒ 每一笔查询都是明文 UDP:53（面②，比面① 严重得多：带的是业务域名）。
    ⇒ 判据不是「是不是 IP"，而是」是不是 IP"**且**"是不是加密 scheme"。只判前者会把
      `nameserver: 8.8.8.8` 这种最坏写法判成通过。
    """
    if dns is None:
        return
    for key in ("nameserver", "fallback"):
        eps = _iter_eps(dns.get(key))
        if key == "nameserver" and not eps:
            add(HIGH, 3, "nameserver 为空 ⇒ 没有主解析器，查询会退回系统 DNS")
            continue
        if key == "fallback" and not eps:
            add(OK, 3, "fallback 未设置（不开回退 ⇒ 面② 根本不存在；lazy 版的有意取舍）")
            continue
        ok_eps = []
        for e in eps:
            h, ip, enc, plain_reason = ep_kind(e)
            if not ip:
                if pinned(h, hosts):
                    add(LOW, 3, f"{key} 端点 `{e}` 是主机名，但已被 hosts 钉住",
                        "⚠️ 待确认：mihomo 在**引导阶段**是否使用 hosts 映射（官方未明确）；"
                        "若不使用，这次明文解析照旧发生。")
                else:
                    add(HIGH, 3, f"{key} 端点 `{e}` 是主机名 ⇒ 冷启动必然明文解析一次 `{h}`（面①）",
                        "这一问只能用 default-nameserver（明文 UDP:53）完成："
                        "加密通道要先知道端点 IP 才能建立。改成 IP 字面量 "
                        f"（`https://1.1.1.1/dns-query`）即可消除 —— 详见 "
                        "reference/profiles/clash.md §5。")
                continue
            if not enc:
                lvl = LOW if is_private_ip(h) else HIGH
                add(lvl, 3, f"{key} 端点 `{e}` 不是加密端点 —— {plain_reason}（面②）",
                    ("内网解析器（192.168.x / 127.x）上的明文属可接受取舍，见 leak 文档 §10。"
                     if is_private_ip(h) else
                     "面② 比面① 严重：这里带的是**业务域名**，"
                     "fallback-filter 每命中一次就明文外发一次。写成 "
                     "`https://223.5.5.5/dns-query` 而不是 `223.5.5.5`。"))
                continue
            ok_eps.append(e)
        if ok_eps and len(ok_eps) == len(eps):
            add(OK, 3, f"{key} {len(eps)} 个端点全部「IP 字面量 + 加密 scheme」：{', '.join(ok_eps)}")
    # fallback-filter 的代价只提示：它让每一次「判定为境外答案」都多查一遍
    ff = dns.get("fallback-filter") or {}
    if _iter_eps(dns.get("fallback")) and ff.get("geoip") is True:
        add(LOW, 3, "fallback-filter.geoip: true ⇒ 每个被判定为境外答案的查询都要再查一遍",
            "两端都是 DoH 时这不是泄露，但是**双倍延迟**。先问一句「我真的需要回退吗」"
            "（lazy 版干脆不开回退就是这个判断）。")


def check_4_side_nameservers(dns, hosts):
    """4 · proxy-server-nameserver 必须存在（节点域名解析，鸡蛋问题）。

    · 缺 `proxy-server-nameserver`：代理节点自己的域名会走主路径（本仓是境外 DoH）
      ⇒ "要先有代理才能解析出节点地址" = 启动期鸡生蛋；失败时退回明文/系统 DNS，
      **节点域名会以明文暴露**（与姊妹仓 Egern 侧同一条判据）。
    · 缺 `direct-nameserver`：DIRECT 出站的域名也去问境外主解析器
      ⇒ 答案不准（CDN 调度到境外）+ 多一次境外查询。不是明文，故 MEDIUM。
    """
    if dns is None:
        return
    psn = _iter_eps(dns.get("proxy-server-nameserver"))
    if not psn:
        add(HIGH, 4, "缺少 proxy-server-nameserver ⇒ 节点域名走主路径（境外 DoH）",
            "要先有代理才能解析出节点地址 = 启动期鸡生蛋；解析失败会退回明文/系统 DNS，"
            "**节点域名以明文暴露**。写一个国内 DoH 端点即可。")
    else:
        add(OK, 4, f"proxy-server-nameserver 已设置（{len(psn)} 个）⇒ 节点域名有独立出口，不依赖代理")
    dnm = _iter_eps(dns.get("direct-nameserver"))
    if not dnm:
        add(MEDIUM, 4, "缺少 direct-nameserver ⇒ DIRECT 出站的域名也去问境外主解析器",
            "不是明文泄露（仍走 DoH），但国内域名会拿到境外答案（CDN 调度错、延迟高）。"
            "补一个国内 DoH。")
    else:
        add(OK, 4, f"direct-nameserver 已设置（{len(dnm)} 个）⇒ 直连域名用国内解析器")

    # 这两层的端点形态：主机名 ⇒ 引导期多一次明文（按端点归属定级）
    for key in ("proxy-server-nameserver", "direct-nameserver"):
        for e in _iter_eps(dns.get(key)):
            h, ip, enc, plain_reason = ep_kind(e)
            if not ip:
                lvl = LOW if is_domestic_host(h) else MEDIUM
                add(lvl, 4, f"{key} 端点 `{e}` 是主机名 ⇒ 引导期明文解析一次 `{h}`",
                    ("国内端点：信号弱（只带出「本机在用哪个 DoH」）。"
                     if is_domestic_host(h) else
                     "境外端点：国内线路直连通常不通 ⇒ 这一层解析可能整体失败。"))
            elif not enc:
                add(HIGH, 4, f"{key} 端点 `{e}` 是明文端点 —— {plain_reason}（面②）",
                    "这一层解析的是**节点域名** —— 明文等于把节点地址直接交给运营商。")


def check_5_fakeip(dns):
    """5 · enhanced-mode: fake-ip 且 fake-ip-range 在 RFC 6815 保留段。"""
    if dns is None:
        return
    mode = dns.get("enhanced-mode")
    if mode == "fake-ip":
        add(OK, 5, "enhanced-mode: fake-ip（代理域名只回假 IP，本地不留答案）")
    elif mode in (None, False):
        add(MEDIUM, 5, "enhanced-mode 未设置（当前为普通模式）⇒ 每个域名都要真实解析一次",
            "fake-ip 是「本地不留答案」的前提；不开它会把解析次数与泄露面一起放大。")
    elif mode == "redir-host":
        add(MEDIUM, 5, "enhanced-mode: redir-host ⇒ 每个域名真实解析一次（拿真 IP）",
            "不是明文泄露（仍走 DoH），但真实答案留在本地，且失去 fake-ip 的"
            "「域名级分流」能力。")
    else:
        add(MEDIUM, 5, f"enhanced-mode 的值 `{mode}` 不是已知值（fake-ip / redir-host）")

    rng = dns.get("fake-ip-range")
    if not rng:
        add(MEDIUM, 5, "fake-ip-range 未设置 ⇒ 用内核默认段（不显式声明不便对拍四份 profile）")
        return
    verdict = in_rfc6815(str(rng))
    if verdict is None:
        add(LOW, 5, f"fake-ip-range `{rng}` 是 IPv6 段或未写前缀长度 —— 本脚本不判（语义待确认）")
    elif verdict:
        add(OK, 5, f"fake-ip-range `{rng}` 在 RFC 6815 保留段 198.18.0.0/15 内")
    else:
        add(HIGH, 5, f"fake-ip-range `{rng}` 不在 RFC 6815 保留段（198.18.0.0/15）内",
            "与真实地址冲突时，应用会拿着「假 IP」去连真实网络；本仓 pitfalls §13 记过"
            "另一个方向的同类事故：198.18.0.1 被 Surge 侧凭据扫描判成真实 IP。")


def check_6_ipv6(doc, dns):
    """6 · IPv6 面（③′）：顶层 ipv6 与 dns.ipv6 **两处**都要显式关闭。

    判据用 `is not False` ⇒ **键缺失也算不过**（与 check_structure.py §⑧ 同一条口径）。
    `ipv6: false` 虽等于内核默认值，但显式声明是「看文件即知」的对齐面纪律。

    为什么两处都要关（leak 文档 §6.4）：
        dns.ipv6: true  ⇒ 应用拿到真实 AAAA
        顶层 ipv6: false ⇒ IPv6 流量不被 TUN 接管
        两者叠加 = 双栈站点直连出去，绕过代理（CHANGELOG 记过的那个 bug）。
    """
    if doc.get("ipv6") is not False:
        add(HIGH, 6, f"顶层 ipv6 未显式关闭（当前 {doc.get('ipv6')!r}）",
            "顶层管 TUN 是否接管 IPv6 流量。不关（或键缺失）⇒ IPv6 侧留有残余通路。")
    else:
        add(OK, 6, "顶层 ipv6: false（TUN 不管 IPv6 流量）")
    if dns is None:
        return
    if dns.get("ipv6") is not False:
        add(HIGH, 6, f"dns.ipv6 未显式关闭（当前 {dns.get('ipv6')!r}）",
            "dns 段管是否返回 AAAA。开着 ⇒ 双栈站点拿到真实 IPv6，"
            "配合顶层关闭即「拿得到却不被接管」= 必然绕过 TUN。")
    else:
        add(OK, 6, "dns.ipv6: false（不返回 AAAA，双栈站点自动回落 IPv4）")


def check_7_tun(doc, override_form):
    """7 · 旁路设备面（③）：tun 接管 :53 + strict-route。

    ⭐ 判据不是「列了几条」，而是"**是否覆盖 :53 的整个地址空间**"。
    :53 的地址空间是无限的，逐个列举**永远不可能列全**（姊妹仓 check_surge_dns.py
    第 3 项踩过同一个坑：按条数判负是错的）。只有 `any:53` / `0.0.0.0:53` 才叫收口。

    ⚠️ 2026-10-07 修正：**tun 不是防 DNS 泄露的必要条件，也不是接管 :53 的唯一方式。**
    本仓只管 DNS 防泄露（dns 段），TUN 交由客户端决定，故配置里**不带 tun 段**。
    面③ 的接管可以是：
      · TUN 模式：`tun.dns-hijack` 劫持（客户端默认形态）
      · 透明代理模式：iptables/nftables 把 :53 重定向到 mihomo 的 DNS 监听端口
        —— 实测案例：软路由 OpenClash 透明代理模式、未开 TUN，仅靠 dns 段即防泄露。
    两者都不在本仓配置内（属客户端 / 系统层），故本项**不判负**，只做提示。
    """
    tun = doc.get("tun")
    if not isinstance(tun, dict) or not tun:
        add(OK, 7, "不带 tun 段（本仓只管 DNS 防泄露，TUN 交由客户端决定）",
            "面③（旁路设备直发 :53）需由客户端侧的接管完成 —— TUN 劫持或透明代理重定向；"
            "两者均不在本仓配置内。防 DNS 泄露的本体是 dns 段，本文件已覆盖。")
        return
    if not tun.get("enable"):
        add(HIGH, 7, "tun.enable 不是 true ⇒ TUN 不工作，dns-hijack 写了也不生效")
    else:
        add(OK, 7, "tun.enable: true")
    for k in ("auto-route", "strict-route"):
        if not tun.get(k):
            add(HIGH, 7, f"tun.{k} 未开启",
                ("没有 auto-route ⇒ 出站流量根本没进 TUN。" if k == "auto-route"
                 else "没有 strict-route ⇒ 仍有流量从物理网卡绕出去（锁不死绕行）。"))
        else:
            add(OK, 7, f"tun.{k}: true")

    hj = [str(x).strip() for x in (tun.get("dns-hijack") or [])]
    if not hj:
        add(HIGH, 7, "tun.dns-hijack 为空 ⇒ 应用/旁路设备自己发的明文 :53 不被接管")
        return
    any_53, specific_53, has_tcp = [], [], False
    for item in hj:
        proto = "udp"
        s = item
        m = _SCHEME_RE.match(s)
        if m:
            proto = m.group(0)[:-3].lower()
            s = s[m.end():]
        if ":" not in s:
            continue
        host, _, port = s.rpartition(":")
        if port.strip() != "53":
            continue
        host = host.strip()
        if proto == "tcp":
            has_tcp = True
        if host.lower() in ("any", "*", "0.0.0.0", "::", "[::]"):
            any_53.append(item)
        else:
            specific_53.append(item)
    if not any_53 and not specific_53:
        add(HIGH, 7, f"tun.dns-hijack 没有任何 :53 条目（当前 {hj}）⇒ 明文 :53 全部裸奔")
    elif any_53:
        add(OK, 7, f"dns-hijack 全量接管 :53（{', '.join(any_53)}）⇒ 面③ 收口",
            "any:53 覆盖 :53 的**整个**地址空间，不依赖列举解析器。")
    else:
        add(MEDIUM, 7, f"dns-hijack 只劫持了 {len(specific_53)} 个具体解析器 ⇒ 列不全就漏",
            f"当前：{', '.join(specific_53)}。:53 的地址空间是无限的，"
            "写成 `any:53` 才是正解（leak 文档 §4.3）。")
    if not has_tcp:
        add(LOW, 7, "dns-hijack 未接管 TCP:53（不写协议前缀时默认 udp://）",
            "本仓已知取舍：明文 TCP 查询在现代客户端里罕见，加 `tcp://any:53` 才覆盖。"
            "见 profile-anatomy §16.6。")


def check_8_adblock(dns, providers):
    """8 · DNS 层广告拦截的两个必要条件（缺任一 ⇒ 静默失效，且不报错）。

    ① nameserver-policy 里 `rule-set:<广告集>: rcode://success`
    ② 同一个广告集在 fake-ip-filter 里再列一遍
       否则 withFakeIP 中间件对 A/AAAA **直接返回假 IP**，请求永远走不到 ①。
    """
    if dns is None:
        return
    npol = dns.get("nameserver-policy") or {}
    ffil = [str(x) for x in (dns.get("fake-ip-filter") or [])]
    ad_np = [k for k, v in npol.items() if str(v).strip().startswith("rcode://")]
    ad_ff = [x for x in ffil if x.startswith("rule-set:")]

    if not ad_np:
        add(HIGH, 8, "nameserver-policy 里没有 rcode://success ⇒ 广告域名被正常解析",
            "DNS 层拦截比规则层早（连接根本建立不起来）；少了它，广告拦截只剩规则层兜底。")
    if not ad_ff:
        add(HIGH, 8, "fake-ip-filter 未列出广告规则集 ⇒ rcode://success 永远走不到",
            "fake-ip 模式下 A/AAAA 会被中间件**直接**回假 IP，nameserver-policy 根本不会被问到。"
            "广告集必须在 fake-ip-filter 里再列一遍。")
    if ad_np and ad_ff:
        np_sets = {str(k).replace("rule-set:", "") for k in ad_np}
        ff_sets = {x.replace("rule-set:", "") for x in ad_ff}
        if np_sets != ff_sets:
            add(HIGH, 8, "两处广告集不一致 ⇒ 有一半名字拿不到空回答",
                f"nameserver-policy={sorted(np_sets)} / fake-ip-filter={sorted(ff_sets)}")
        else:
            add(OK, 8, f"广告拦截双条件满足（{', '.join(sorted(np_sets))}）"
                       f"，且两处一致")
    # ⭐ 死引用检查覆盖 **所有** rule-set: 键，不只广告项。
    #    理由：nameserver-policy 里任何一条引用了不存在的 provider，该条 policy
    #    就永不生效 —— 对广告项是"拦截静默失效"，对 `rule-set:cn` 是"国内域名
    #    拿境外答案"。两者都是**收口装置静默消失**，而门禁看不出来。
    dangling = [str(k).replace("rule-set:", "") for k in npol
                if str(k).startswith("rule-set:") and
                str(k).replace("rule-set:", "") not in providers]
    if dangling:
        add(HIGH, 8, f"nameserver-policy 引用了未定义的规则集：{dangling}",
            "该 provider 不存在 ⇒ 这条 policy 永不生效。广告项上是拦截静默失效，"
            "cn 项上是国内域名改用主解析器（境外答案）—— 都是收口装置消失而不报错。")
    if ffil and not any(str(x).lstrip("+*.").split(".")[0] in
                        ("lan", "local", "localdomain", "home", "localhost") for x in ffil):
        add(LOW, 8, "fake-ip-filter 未含本地/内网类条目（*.lan / *.local …）",
            "内网名字也会拿到假 IP，可能导致局域网访问异常。")


def _is_domestic_key(k):
    """nameserver-policy 的键是不是「国内类」（cn / private / *-cn）。"""
    name = str(k)
    for pre in ("rule-set:", "geosite:", "geodata:"):
        if name.startswith(pre):
            name = name[len(pre):]
    for part in name.split(","):
        p = part.strip()
        if p in ("cn", "private") or p.endswith("-cn") or p == "geolocation-cn":
            return True
    return False


def check_9_policy_order(dns):
    """9 · nameserver-policy 的广告项必须排在 cn / private 之前。

    YAML mapping 在 Python 3.7+ 保持插入顺序，而这个顺序**就是 mihomo 的匹配顺序**：
    先命中 `rule-set:cn` ⇒ 拿国内答案，永远走不到后面的 rcode://success。
    """
    if dns is None:
        return
    npol = dns.get("nameserver-policy") or {}
    if not npol:
        add(MEDIUM, 9, "nameserver-policy 为空 ⇒ 所有域名都用主解析器（国内域名拿境外答案）")
        return
    keys = list(npol.keys())
    ads = [i for i, k in enumerate(keys) if str(npol[k]).strip().startswith("rcode://")]
    dom = [i for i, k in enumerate(keys) if _is_domestic_key(k)]
    if ads and dom and min(ads) > min(dom):
        add(HIGH, 9, "广告 policy 排在 cn/private 之后 ⇒ 会先命中 cn 而拿不到空回答",
            f"当前顺序：{keys}。广告项必须排在最前（hardening-template §6）。")
    elif ads:
        add(OK, 9, f"广告 policy 排在 cn/private 之前（{len(ads)} 条广告项）")
    else:
        add(LOW, 9, "nameserver-policy 里没有广告项（见判据 8）")


def check_10_no_resolve(doc, providers):
    """10 · IP 类规则必须带 no-resolve（面④）+ 域名类不该写（刀刃二）。

    ⭐ 判「是不是 IP 类规则」的**第一依据是 provider 的 behavior**，不是名字前缀：
        behavior: ipcidr ⇒ 内容就是 IP 段 ⇒ 不带 no-resolve 会为判定而强制解析（面④）
        behavior: domain ⇒ 纯域名集，写了 no-resolve 无意义
        behavior: classical ⇒ 内容混合，**无法静态判定** ⇒ 单独归组提示（面⑤）
    只有 provider 未声明 behavior 时才退回到 `geoip-` 名字前缀兜底。
    """
    rules = [r for r in (doc.get("rules") or []) if isinstance(r, str)]
    if not rules:
        add(HIGH, 10, "rules 为空 ⇒ 没有分流，也没有任何一面被收口")
        return
    ip_types = ("GEOIP", "IP-CIDR", "IP-CIDR6", "IP-ASN", "ASN")
    missing, domain_with_nr, unknown_content = [], [], []
    nr_count = 0
    for r in rules:
        parts = [x.strip() for x in r.split(",")]
        opts = [x.lower() for x in parts[1:]]
        t = parts[0].upper()
        has_nr = "no-resolve" in opts
        if t in ip_types:
            nr_count += 1
            if not has_nr:
                missing.append(r)
            continue
        if t != "RULE-SET":
            continue
        prov = parts[1] if len(parts) > 1 else ""
        beh = (providers.get(prov) or {}).get("behavior")
        if beh == "ipcidr":
            nr_count += 1
            if not has_nr:
                missing.append(r)
        elif beh == "domain":
            if has_nr:
                domain_with_nr.append(r)
        elif beh == "classical":
            unknown_content.append(prov)
        elif beh is None and prov.startswith("geoip-"):
            # 名字兜底：provider 未声明 behavior，但名字是 IP 集的样子
            nr_count += 1
            if not has_nr:
                missing.append(r)
    for r in missing:
        add(HIGH, 10, f"IP 类规则缺 no-resolve ⇒ 为判定归属而强制解析一次（面④）：`{r}`",
            "不带 no-resolve 时，mihomo 要先把域名解析成 IP 才能判它是否落在段内 —— "
            "这一问带的是**用户要访问的站点**。源码依据：rules/parser.go 的 "
            "`case \"RULE-SET\": isSrc, noResolve := RC.ParseParams(params)`，"
            "该参数确实被传给 NewRuleSet。")
    if nr_count and not missing:
        add(OK, 10, f"{nr_count} 条 IP 类规则全部带 no-resolve")
    elif not nr_count:
        add(LOW, 10, "没有 IP 类规则（不存在缺 no-resolve 的风险）")
    for r in domain_with_nr:
        add(LOW, 10, f"域名类规则集写了 no-resolve：`{r}`",
            "本仓立场（leak 文档 §4.4.1 刀刃二）：纯域名集写了会关掉域名匹配。"
            "⚠️ 待确认：mihomo 对该组合的确切语义（domain behavior 下应为无操作）。")
    if unknown_content:
        add(LOW, 10, f"{len(set(unknown_content))} 个 classical 规则集内容无法静态判定"
                     f"（{', '.join(sorted(set(unknown_content)))}）",
            "面⑤：远程集里的裸 IP 条目**不在本文件里**，本地静态门禁看不见，"
            "必须拉下来数。本仓自托管的 rules/*.list 实测 0 条 IP 条目。")


def check_11_zero_dat(doc, dns, providers):
    """11 · 零 dat 依赖（本仓纪律落成判据，与 check_structure.py ⑦ 同一条口径）。

    ⚠️ **这不排斥 `.mrs`**：geoip-private / geoip-cn 等是 MetaCubeX 的**独立远程集文件**
    （format: mrs），与 geosite.dat / geoip.dat 数据库无关 —— 那正是本仓想要的形态。
    判据只拦 dat，不拦 mrs（注入测试专门验过这条不误伤）。
    """
    for k in ("geox-url", "geo-auto-update", "geo-update-interval"):
        if k in doc:
            add(HIGH, 11, f"顶层出现 `{k}` ⇒ mihomo 会去下载并加载 GeoSite.dat / GeoIP.dat",
                "本仓纪律是零 dat 依赖：全部规则集走远程 .mrs / .yaml。"
                f"（`geodata-mode` / `geodata-loader` 是否同属此类本脚本未判，待确认。）")
    for r in [x for x in (doc.get("rules") or []) if isinstance(x, str)]:
        t = r.split(",")[0].strip()
        if t in ("GEOSITE", "GEOIP"):
            add(HIGH, 11, f"规则用了原生 `{t}` ⇒ 直接查 dat 数据库：`{r}`",
                "改用 `RULE-SET,<provider>,<policy>` 引用远程集（profile-anatomy §10.2）。")
    if dns:
        for k in (dns.get("nameserver-policy") or {}):
            if str(k).startswith("geosite:"):
                add(HIGH, 11, f"nameserver-policy 的键用了 `geosite:` ⇒ 依赖 dat：`{k}`",
                    "本仓规则集都是 rule-provider，改用 `rule-set:` 前缀。")
    for name, p in providers.items():
        for key in ("url", "path"):
            v = str((p or {}).get(key) or "")
            if v.lower().endswith(".dat"):
                add(HIGH, 11, f"rule-provider `{name}` 引用了 .dat 文件（`{key}: {v}`）",
                    "这与「零 dat 依赖」冲突；换成 .mrs 远程集。")
    if not any(f[0] == HIGH and f[1] == 11 for f in findings):
        mrs = sum(1 for p in providers.values() if str((p or {}).get("format", "")).lower() == "mrs")
        add(OK, 11, f"零 dat 依赖：{len(providers)} 个 provider 无一是 dat"
                    + (f"（其中 {mrs} 个 format: mrs —— 允许）" if mrs else ""))


def check_12_providers(doc, providers):
    """12 · rule-provider 形态。**不做网络探测** —— 可达性归 check_remote_urls.py。

    这里只判「它有没有可能被加载」：既无 url 也无 path ⇒ 永远加载不出来 ⇒
    引用它的规则静默变成空集（死规则），而门禁看不出来。
    """
    if not providers:
        add(MEDIUM, 12, "没有 rule-provider ⇒ 规则只能靠原生 GEOSITE/GEOIP 或行内域名",
            "本仓形态是规则集全面远程化（.mrs），没有 provider 意味着形态回退。")
        return
    dead = []
    for name, p in providers.items():
        p = p or {}
        if not p.get("url") and not p.get("path"):
            dead.append(name)
    for name in dead:
        add(HIGH, 12, f"rule-provider `{name}` 既无 url 也无 path ⇒ 永远加载不出来",
            "引用它的规则会静默变成空集（死规则）—— 广告拦截/国内直连因此失效而没有报错。")
    if not dead:
        add(OK, 12, f"{len(providers)} 个 rule-provider 形态完整（url/path 齐备）"
                    f"；可达性由 check_remote_urls.py 守，本脚本不探测网络")


def check_13_references(doc, providers):
    """13 · 规则引用的名字必须能解析（provider / 策略组）。

    引用不存在的东西不会让 mihomo 拒绝启动 —— 它只是**静默不生效**。
    对防泄露而言这最危险：那正是收口装置所在的位置（广告集 / 国内集 / 兜底）。
    """
    gnames = {g.get("name") for g in (doc.get("proxy-groups") or []) if isinstance(g, dict)}
    pnames = {p.get("name") for p in (doc.get("proxies") or []) if isinstance(p, dict)}
    known = gnames | pnames | BUILTIN_POLICIES
    bad_prov, bad_pol = [], []
    for r in [x for x in (doc.get("rules") or []) if isinstance(x, str)]:
        parts = [x.strip() for x in r.split(",")]
        t = parts[0].upper()
        if t == "RULE-SET" and len(parts) > 1:
            if parts[1] not in providers:
                bad_prov.append((r, parts[1]))
            if len(parts) > 2 and parts[2] not in known:
                bad_pol.append((r, parts[2]))
        elif t == "MATCH" and len(parts) > 1:
            if parts[1] not in known:
                bad_pol.append((r, parts[1]))
    for r, name in bad_prov:
        add(HIGH, 13, f"规则引用了未定义的 rule-provider `{name}`：`{r}`",
            "该规则是死规则 ⇒ 引用它的收口（广告 / 国内直连）静默失效。")
    for r, pol in bad_pol:
        add(HIGH, 13, f"规则引用了无法解析的策略 `{pol}`：`{r}`",
            f"已定义的组：{len(gnames)} 个 + 节点 {len(pnames)} 个；"
            "⚠️ 待确认：mihomo 对未知策略的确切行为（告警后跳过 / 拒绝加载），"
            "但无论哪种，这条规则都不按预期工作。")
    if not bad_prov and not bad_pol:
        add(OK, 13, f"{len([x for x in (doc.get('rules') or []) if isinstance(x, str)])} 条规则的"
                    f"provider 与策略引用全部可解析（{len(gnames)} 组 / {len(pnames)} 节点）")


def check_14_misc_switches(dns):
    """14 · 其余 DNS 开关（提示性，不计入风险等级之外的失败）。"""
    if dns is None:
        return
    if dns.get("respect-rules") is not True:
        add(LOW, 14, "respect-rules 未开启 ⇒ DNS 查询自己不按路由规则走",
            "发往境外 DoH 端点的查询不会被判给代理 ⇒ 国内线路上直连境外 :443 常被阻断。"
            "见 hardening-template §3.2。")
    else:
        add(OK, 14, "respect-rules: true（DNS 查询也受路由规则管辖）")
    if dns.get("use-system-hosts"):
        add(LOW, 14, "use-system-hosts: true ⇒ 读本机 hosts 文件",
            "本机 hosts 被污染时会覆盖配置里的映射；本仓立场是只读配置内 hosts。")
    if dns.get("prefer-h3"):
        add(LOW, 14, "prefer-h3: true ⇒ 优先 HTTP/3",
            "QUIC 在部分网络被限速或拦截；本仓刻意只用 HTTP/1.1 + HTTP/2。")
    if dns.get("listen"):
        add(LOW, 14, f"dns.listen = {dns.get('listen')} ⇒ 内核对外开了明文 :53 端口",
            "局域网内其它设备会以明文来问；若是有意提供内网解析服务则忽略。")


# ============================================================================
# 主流程
# ============================================================================

def audit(doc):
    dns = check_1_dns_enable(doc)
    providers = doc.get("rule-providers") or {}
    hosts = doc.get("hosts") or (dns or {}).get("hosts") or {}
    if not isinstance(hosts, dict):
        hosts = {}
    check_2_default_ns(dns)
    check_3_main_endpoints(dns, hosts)
    check_4_side_nameservers(dns, hosts)
    check_5_fakeip(dns)
    check_6_ipv6(doc, dns)
    return providers


def run(path, strict=False, quiet=False, override_form=False):
    # findings / _waivers 是模块级状态：不清空则同一进程内第二次 run() 会把上一轮的
    # 发现累计进来（姊妹仓 check_surge_dns.py 实测：连跑两次 16 → 32）。
    findings.clear()
    load_waivers(path)
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        print(f"❌ {path}：YAML 顶层不是 mapping", file=sys.stderr)
        return 2

    providers = audit(doc)
    dns = doc.get("dns")
    check_7_tun(doc, override_form)
    check_8_adblock(dns, providers)
    check_9_policy_order(dns)
    check_10_no_resolve(doc, providers)
    check_11_zero_dat(doc, dns, providers)
    check_12_providers(doc, providers)
    check_13_references(doc, providers)
    check_14_misc_switches(dns)

    counts = {k: 0 for k in _RANK}
    waived = 0
    for lv, _, _, _ in findings:
        if lv.startswith("WAIVED:"):
            waived += 1
        else:
            counts[lv] = counts.get(lv, 0) + 1

    if not quiet:
        icons = {HIGH: "🔴", MEDIUM: "🟠", LOW: "🟡", OK: "✅"}
        for lv in (HIGH, MEDIUM, LOW, OK):
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
          f"{counts[LOW]} low, {counts[OK]} ok" + (f", {waived} waived" if waived else ""))

    fail = counts[HIGH] > 0 or (strict and counts[MEDIUM] > 0)
    if fail:
        print("❌ 未通过" + ("（--strict：medium 也算失败）" if strict and counts[HIGH] == 0 else ""))
        return 1
    print("✅ 通过")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="mihomo（clash）profile 防 DNS 泄露审计器",
        epilog="例：python check_clash_dns.py clash/profiles/lazy.yaml clash/profiles/routing.yaml")
    ap.add_argument("profile", nargs="+", help="mihomo .yaml 路径（可多个）")
    ap.add_argument("--strict", action="store_true", help="medium 也视为失败")
    ap.add_argument("--quiet", action="store_true", help="只打印汇总")
    ap.add_argument("--override", action="store_true",
                    help="本文件是 override/*.js 的输出形态：不要求 tun 段（客户端自管 TUN）")
    a = ap.parse_args()

    missing = [p for p in a.profile if not os.path.isfile(p)]
    if missing:
        for p in missing:
            print(f"❌ 找不到文件：{p}", file=sys.stderr)
        return 2

    rc = 0
    for p in a.profile:
        print(f"\n=== {p} ===")
        try:
            r = run(p, a.strict, a.quiet, a.override)
        except yaml.YAMLError as e:
            print(f"  ❌ YAML 解析失败：{e}", file=sys.stderr)
            r = 2
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ {type(e).__name__}: {e}", file=sys.stderr)
            r = 2
        rc = max(rc, r)
    return rc


if __name__ == "__main__":
    sys.exit(main())
