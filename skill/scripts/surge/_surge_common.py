# -*- coding: utf-8 -*-
"""Surge 审计脚本的共享工具 —— 消灭「同一判据两份拷贝」。

背景：Egern 项目里 `check_egern_dns.py` 与 `audit_dns_forward.py` 各自实现了
一份「端点主机名解析 + 是否为 IP 字面量」的逻辑，靠注释互相提醒同步。
结果判据本体同步了、**喂给判据的 helper 没同步**，同一份配置两个脚本给出相反结论
（IPv6 端点被截断成 `'[2400:3200:'`）。

⇒ 教训：**靠注释提醒同步两份拷贝是不可靠的。** 本模块把共用逻辑收编到一处，
所有 Surge 审计脚本都从这里 import，从结构上消灭拷贝。

用法：
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _surge_common import parse_conf, ip_literal, hostpart, DOMESTIC_RESOLVER_IPS
"""

import re
import sys

# ============================================================================
# INI 段解析
# ============================================================================

# 段头：[General] / [Proxy] …（允许行尾注释）
_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[#;].*)?$")


def parse_conf(path_or_text, is_text=False):
    """把 Surge .conf 切成 {段名小写: [ (行号, 原始行), ... ]}。

    返回 (sections, lines)：
      - sections: {"general": [(lineno, raw_line), ...], ...}
      - lines:    全文行列表（供需要看顺序的场景，例如 [Rule] 段）

    ⚠️ 只做**语法切分**，不做语义校验：注释、空行、"键 = 值" 的解析交给各脚本。
       键名大小写、`= ` 两侧空格这些 Surge 都容忍的写法，不应参与审计结论。
    """
    text = path_or_text if is_text else open(path_or_text, encoding="utf-8", errors="replace").read()
    sections = {}
    cur = None
    lines = text.splitlines()
    for i, raw in enumerate(lines, 1):
        m = _SECTION_RE.match(raw)
        if m:
            cur = m.group(1).strip().lower()
            sections.setdefault(cur, [])
            continue
        if cur is not None:
            sections[cur].append((i, raw))
    return sections, lines


def kv_lines(entries):
    """从段的行列表里取出 "键 = 值"（跳过注释与空行），返回 [(lineno, key, value)]。

    用于 [General] / [Host] 这类键值段；[Proxy] / [Proxy Group] / [Rule] 是
    逗号分隔的另一种语法，不要用这个函数。
    """
    out = []
    for lineno, raw in entries:
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith(";"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        out.append((lineno, k.strip(), v.strip()))
    return out


def kv_dict(entries):
    """同 kv_lines，但折叠成 {key_lower: (lineno, value)}。同名键保留**第一个**。"""
    d = {}
    for lineno, k, v in kv_lines(entries):
        d.setdefault(k.lower(), (lineno, v))
    return d


def strip_comment(raw):
    """去掉整行注释与行尾注释，返回纯内容（保留原始缩进无关）。"""
    s = raw.strip()
    if s.startswith("#") or s.startswith(";"):
        return ""
    # 行尾注释：只在 ` #` / ` ;` 且不在引号内时切掉
    in_q = None
    for i, ch in enumerate(s):
        if in_q:
            if ch == in_q:
                in_q = None
        elif ch in "\"'":
            in_q = ch
        elif ch in "#;" and i > 0 and s[i - 1] in " \t":
            return s[:i].strip()
    return s.strip()


def split_csv(value):
    """按逗号切分一行，**尊重双引号**（Surge 允许 `"a, b"` 这种带逗号的项）。

    `select, Smart, Select, icon-url=...` -> ['select', 'Smart', 'Select', 'icon-url=...']
    """
    out, buf, in_q = [], [], None
    for ch in value:
        if in_q:
            if ch == in_q:
                in_q = None
            else:
                buf.append(ch)
        elif ch in "\"'":
            in_q = ch
        elif ch == ",":
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf).strip())
    return [x for x in out if x != ""]


# ============================================================================
# 端点 / IP 判据
# ============================================================================

# ⭐ 国内知名公共 DNS 解析器 IP —— 「兜底组直连可达」的第二判据。
# 在 profile 文本内无法证明任意 IP 是否可直连，但这些 IP 的归属与服务商是公开事实，
# 且在国内任何链路上都直连可达 —— 与「在 rules 里判给 DIRECT」等价，
# 且不需要在配置里写装饰性规则。
# ⚠️ 只收「国内」解析器：境外解析器（8.8.8.8 等）必须经代理才可达，
#    一个全由境外 IP 组成的兜底即便端点全是 IP 字面量也**不能**判为直连可达。
DOMESTIC_RESOLVER_IPS = {
    # 阿里 AliDNS
    "223.5.5.5", "223.6.6.6", "2400:3200::1", "2400:3200:baba::1",
    # 腾讯 DNSPod
    "119.29.29.29", "119.28.28.28", "2402:4e00::",
    # DNSPod 备用 / 其他国内公共解析器
    "182.254.116.116", "1.12.12.12", "120.53.53.53", "120.53.53.54",
    # 114DNS
    "114.114.114.114", "114.114.115.115",
    # 百度
    "180.76.76.76",
    # 360
    "101.226.4.6", "218.30.118.6", "123.125.81.6", "140.205.1.1",
    # 中国电信 / 联通 / 移动 常见递归（非必须，仅作识别）
    "1.2.4.8", "210.2.4.8",
}

# ⭐ 境外知名解析器 —— 只用于**提示**（"国内线路上通常不可达"），不参与判负。
FOREIGN_RESOLVER_IPS = {
    "1.1.1.1", "1.0.0.1", "1.1.1.2", "1.0.0.2",
    "8.8.8.8", "8.8.4.4", "2001:4860:4860::8888",
    "9.9.9.9", "149.112.112.112",
    "208.67.222.222", "208.67.220.220",
    "185.228.168.9", "76.76.2.0",
}

_IP4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

# ⭐ 通用 scheme 前缀：`scheme://`，**大小写不敏感**，不枚举具体 scheme。
# ⚠️ 不要改成白名单：那会让 scheme 的拼法参与审计结论
#    （Egern 项目踩过：端点写 `HTTPS://…` 时白名单失配，主机名被误判成 `HTTPS`，
#     读数从 0 high 翻成 9 high）。scheme 拼法不是本工具要审的对象。
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")


def hostpart(ep):
    """从端点字符串里取出主机部分（去 scheme、去 path/query、去 :port）。

    正确处理这些形态（scheme 拼法任意、大小写任意）：
      - `https://1.1.1.1/dns-query`          -> `1.1.1.1`
      - `HTTPS://223.5.5.5/dns-query`        -> `223.5.5.5`
      - `https://[2400:3200::1]/dns-query`   -> `2400:3200::1`   ← IPv6（方括号）
      - `[2400:3200::1]:443`                 -> `2400:3200::1`
      - `223.5.5.5:53`                       -> `223.5.5.5`
      - `dns.google` / `2001:db8::1`         -> 原样
    """
    s = str(ep).strip()
    m = _SCHEME_RE.match(s)
    if m:
        s = s[m.end():]
    s = s.split("/")[0]
    s = s.split("?")[0].split("#")[0]
    if s.startswith("["):
        end = s.find("]")
        return s[1:end] if end != -1 else s.lstrip("[")
    if s.count(":") == 1:
        return s.split(":")[0]
    return s


def ip_literal(ep):
    """端点是不是 IP 字面量（不需要任何解析）。"""
    host = hostpart(ep)
    if _IP4_RE.match(host):
        return True
    return ":" in host


def is_domestic_resolver(ep):
    """端点主机是不是已知的国内公共解析器 IP（含 IPv6 字面量）。"""
    return hostpart(ep) in DOMESTIC_RESOLVER_IPS


def is_foreign_resolver(ep):
    """端点主机是不是已知的境外解析器 IP。"""
    return hostpart(ep) in FOREIGN_RESOLVER_IPS


def endpoint_kind(ep):
    """给一个 DNS 端点 / dns-server 条目分类。

    返回 (kind, host)：
      kind ∈ {"domestic-ip", "foreign-ip", "other-ip", "hostname"}
      - `223.5.5.5`                          -> domestic-ip
      - `1.1.1.1`                            -> foreign-ip
      - `203.0.113.7`                        -> other-ip（IP 字面量，归属未知）
      - `https://dns.google/dns-query`       -> hostname  ← 会触发明文引导解析
      - `system`                             -> hostname  ← 最坏情况，等价于交运营商
    """
    h = hostpart(ep)
    if h.lower() == "system":
        return "hostname", h
    if _IP4_RE.match(h) or ":" in h:
        if h in DOMESTIC_RESOLVER_IPS:
            return "domestic-ip", h
        if h in FOREIGN_RESOLVER_IPS:
            return "foreign-ip", h
        return "other-ip", h
    return "hostname", h


# ============================================================================
# [Rule] 规则解析 —— 策略字段位置
# ============================================================================

# 规则的**匹配类型** —— 决定策略字段在第几个位置。
# ⚠️ 这是本类审计器最容易写错的地方（第一版就栽在这里）：
#    带匹配值的规则（DOMAIN-SUFFIX,x.com,POLICY / GEOIP,CN,DIRECT）策略恒在 index 2；
#    只有不带匹配值的 FINAL 是 `FINAL,POLICY`，策略在 index 1。
#    RULE-SET 的 index 1 恒为「规则集标识」（URL / 内置集合名），不是策略 ⇒ 也在 index 2。
#
#    第一版把 `GEOIP` 归进"无匹配值"一组、策略取 index 1，于是把 `CN` 当成了策略名，
#    报出「规则引用了未定义的策略 `CN`」这个**假 HIGH**。
#    ⇒ 判据写错方向比漏报更危险：它会让使用者去改一条本来正确的规则。
_RULE_TYPES_WITH_VALUE = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "DOMAIN-SET", "URL-REGEX", "USER-AGENT", "PROCESS-NAME",
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "SRC-IP", "DEST-PORT", "SRC-PORT", "PROTOCOL",
    "GEOIP", "IP-GEOIP", "ASN",
}
_RULE_TYPES_NO_VALUE = {"FINAL"}


def policy_index(parts):
    """返回策略字段的下标；无法判定时返回 None。

    按「这个类型有没有匹配值」分两类，**不是**按「策略在第几个逗号后」：
      - 有匹配值：`DOMAIN-SUFFIX,x.com,POLICY` / `GEOIP,CN,DIRECT` / `RULE-SET,SET,POLICY`
        → 策略恒为 index 2
      - 无匹配值：`FINAL,POLICY` → 策略为 index 1
    """
    if len(parts) < 2:
        return None
    t = parts[0].strip().upper()
    if t in _RULE_TYPES_NO_VALUE:
        return 1                                          # ← 业务值：策略字段下标，非退出码
    if t in _RULE_TYPES_WITH_VALUE or t == "RULE-SET":
        return 2 if len(parts) > 2 else None              # ← 业务值：策略字段下标，非退出码
    return None


# ============================================================================
# 输出编码垫片（import 即生效）
# ============================================================================
def force_utf8_stdout():
    """把 stdout / stderr 钉成 UTF-8。

    Windows 中文环境的控制台编码与管道重定向默认是 **GBK(cp936)** —— 脚本里一个
    emoji 一 print 就抛 `UnicodeEncodeError`，进程以**退出码 1** 结束。
    ⚠️ 这比"打印不出来"严重得多：回归测试里 `bad_*` fixture 期望的**恰恰也是 1**
       ⇒ 解释器坏了会被计成「判负通过」，整轮看着绿、其实一条判据都没执行。
    Git Bash 与现代终端都是 UTF-8，所以统一按 UTF-8 输出；
    真正的 cp936 控制台下最坏是图形字符显示成 `?`，不影响判据与退出码。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:                                      # noqa: BLE001
            pass


force_utf8_stdout()   # import 本模块即生效，调用方不需要再写一行

