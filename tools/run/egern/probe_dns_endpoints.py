#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐个实测 Egern profile 里声明的每个加密 DNS 端点，确认它真的能用。

为什么需要它（本轮真实教训）：
  「把端点写成 IP 字面量」是为了消灭 bootstrap 的用途①（官方：bootstrap 会用来
  解析 upstreams 中加密 DNS 服务器的主机名）。但**写成 IP 之后证书不一定覆盖该 IP**，
  写错形式就白占一个端点，而且是**静默失效** —— 配置校验不会报错。
  实测反例：https://9.9.9.9/dns-query 直接 `HTTP Version Not Supported`
  （Quad9 在 9.9.9.9 上只提供 HTTP/3，不响应 RFC8484 的 HTTP/1.1 线格式），
  但 tls://9.9.9.9 正常（证书 CN=dns.quad9.net）。

用法：
  python probe_dns_endpoints.py profile.yaml          # 从 profile 里抽出所有 dns 端点
  python probe_dns_endpoints.py 8.8.8.8 1.1.1.1      # 或直接给端点/主机
  python probe_dns_endpoints.py tls://9.9.9.9

覆盖协议：udp:// / 裸 IP（传统 UDP:53）、tls://（DoT 853）、https://（DoH，RFC8484 线格式）。
不做 JSON API 判断（见 SKILL 坑 1）。
"""
import base64
import socket
import ssl
import struct
import sys
import os

# 共用模块定位：`_*_common` 统一在 tools/lib/（重组后不再与本脚本同目录）
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _cand in (_os.path.normpath(_os.path.join(_d, "..", "..", "lib")),
              _os.path.normpath(_os.path.join(_d, "..", "lib")), _d):
    if any(_os.path.isfile(_os.path.join(_cand, _m)) for _m in
           ("_surge_common.py", "_egern_common.py", "_clash_common.py")):
        _sys.path.insert(0, _cand)
        break

from _egern_common import force_utf8_stdout, hostpart as _common_hostpart  # noqa: E402
import urllib.request



TIMEOUT = 12
QNAME = "example.com"

# ⚠️ 2026-10-08 第十五轮：联网探测**必须有重试**，否则 CI 绿不绿看运气。
#
# 背景（真实事件）：本 step 在 push 事件下 `continue-on-error` 为 false，
# 而 2026-10-08 一次 push（commit 25079c9）它就红了 —— 报
# `https://120.53.53.53/dns-query` 两次都 `_ssl.c:993: The handshake operation timed out`。
# 但同一台服务器的 `tls://1.12.12.12`（853）**同一次运行里正常**，
# 且历史两次 run 里该 DoH 端点**都是 HTTP 200** ⇒ 偶发不可达，不是真失效。
# 本机复现：直连该 IP:443 的 TLS 连测 4 次**全成功（0.08s）**，
# 但脚本里同一端点**第一次失败、第二次成功** ⇒ 典型冷连接/偶发丢包。
#
# 姊妹门禁 `check_remote_urls.py` 早就加了重试（`for method in ("HEAD","GET")`），
# 两者设计不一致 —— 而"抖动会假红"正是本 step 当初不进闸门的理由，
# 却在 CI 里以最严的方式判红，自相矛盾。此处对齐。
RETRIES = 3          # 总尝试次数（首次 + 2 次重试）
RETRY_BACKOFF = 1.5  # 秒，每次重试前等待（递减退避）


# ---------------------------------------------------------------- DNS 报文
def build_query(name=QNAME, qtype=1, rd=True):
    flags = 0x0100 if rd else 0x0000
    head = struct.pack(">HHHHHH", 0x1234, flags, 1, 0, 0, 0)
    body = b"".join(bytes([len(p)]) + p.encode() for p in name.split("."))
    return head + body + b"\x00" + struct.pack(">HH", qtype, 1)


def parse_answers(buf):
    """返回 [(type, 值)]；只解 A / AAAA / CNAME。"""
    out, i = [], 12
    if len(buf) < 12:
        return out
    qd, an = struct.unpack(">HH", buf[4:8])
    for _ in range(qd):
        while buf[i]:
            i += buf[i] + 1
        i += 5
    for _ in range(an):
        if buf[i] & 0xC0 == 0xC0:
            i += 2
        else:
            while buf[i]:
                i += buf[i] + 1
            i += 1
        rtype, _cls, _ttl, dl = struct.unpack(">HHIH", buf[i:i + 10])
        i += 10
        data = buf[i:i + dl]
        i += dl
        if rtype == 1 and dl == 4:
            out.append(("A", socket.inet_ntoa(data)))
        elif rtype == 28 and dl == 16:
            out.append(("AAAA", socket.inet_ntop(socket.AF_INET6, data)))
        elif rtype == 5:
            # CNAME：可能是压缩指针，简单跳过
            out.append(("CNAME", "<见应答>"))
    return out


# ---------------------------------------------------------------- 各协议
def hostport(s):
    """'tls://8.8.8.8:853' -> ('tls', '8.8.8.8', 853)   （proto, host, port）

    ⚠️ 主机部分**复用** `_egern_common.hostpart()`（方括号 IPv6 / 裸 IPv6 / `:port` / 任意
    scheme 都对），端口另判 —— 早先本文件自己写了一份 `rsplit(":", 1)` 的拆分，**裸 IPv6
    会被拆坏**：`2400:3200::1` → host=`2400:3200:`、port=`1`（2026-09-25 实测修掉）。
    另：旧 docstring 把返回顺序写成了 `(host, port, proto)`，与实际相反，一并改正。
    """
    proto = s.split("://", 1)[0].lower() if "://" in s else "udp"
    rest = (s.split("://", 1)[1] if "://" in s else s).split("/")[0]
    port = {"udp": 53, "tls": 853, "https": 443}.get(proto, 53)
    tail = rest.rsplit("]", 1)[-1] if rest.startswith("[") else rest
    if tail.startswith(":") and tail[1:].isdigit():
        port = int(tail[1:])
    return proto, _common_hostpart(rest), port


# ⚠️ 自检（import 即跑，fail-loud）：端口 / 主机的拆分必须对这几类形态成立。
#    早先自己写的那份把裸 IPv6 `2400:3200::1` 拆成 host=`2400:3200:` / port=`1` —— 这个
#    自检就是为它立的；放在模块级是为了**不可能静默失效**（
#    判不到运行期行为；本文件又是闸外脚本）。
for _case, _want in (("tls://8.8.8.8:853", ("tls", "8.8.8.8", 853)),
                     ("2400:3200::1", ("udp", "2400:3200::1", 53)),
                     ("[2400:3200::1]:853", ("udp", "2400:3200::1", 853)),
                     ("https://223.5.5.5/dns-query", ("https", "223.5.5.5", 443)),
                     ("8.8.8.8", ("udp", "8.8.8.8", 53))):
    if hostport(_case) != _want:
        raise SystemExit("❌ 自检：hostport(%r) = %r，期望 %r"
                         % (_case, hostport(_case), _want))


def try_udp(host, port):
    # ⚠️ 早先固定 `AF_INET` ⇒ IPv6 端点必然失败（对着一份正确的配置报 FAIL）。
    #    用 getaddrinfo 按端点自己选族，顺便把 socket 关掉（原先没关）。
    af, socktype, proto_, _canon, sa = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)[0]
    s = socket.socket(af, socktype, proto_)
    s.settimeout(TIMEOUT)
    try:
        s.sendto(build_query(), sa)
        # 跳过发往本机的 ICMP 导致的假连接（UDP 无连接，直接看是否有回包）
        data, _ = s.recvfrom(4096)
    finally:
        s.close()
    return parse_answers(data)


def try_dot(host, port, server_hostname=None):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=TIMEOUT) as raw:
        with ctx.wrap_socket(raw, server_hostname=server_hostname or host) as ts:
            m = build_query()
            ts.sendall(struct.pack(">H", len(m)) + m)
            ln = struct.unpack(">H", ts.recv(2))[0]
            buf = b""
            while len(buf) < ln:
                buf += ts.recv(ln - len(buf))
            cn = dict(x[0] for x in ts.getpeercert().get("subject", ())).get("commonName", "?")
            return parse_answers(buf), cn


def try_doh(host, port, path="/dns-query", server_hostname=None):
    """RFC 8484 线格式：GET ?dns=<base64url> + accept: application/dns-message"""
    enc = base64.urlsafe_b64encode(build_query()).rstrip(b"=").decode()
    url = f"https://{host}:{port}{path}?dns={enc}"
    req = urllib.request.Request(url, headers={"accept": "application/dns-message"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, parse_answers(r.read())


# ---------------------------------------------------------------- 入口
def endpoints_from_profile(path):
    try:
        import yaml
    except ImportError:
        sys.exit("需要 pyyaml 才能读 profile；或直接把端点作为参数传入")
    doc = yaml.safe_load(open(path, encoding="utf-8")) or {}
    dns = doc.get("dns") or {}
    out = []
    for grp, servers in (dns.get("upstreams") or {}).items():
        for s in servers or []:
            out.append((f"upstream {grp}", str(s)))
    for s in dns.get("proxy_nameservers") or []:
        out.append(("proxy_nameservers", str(s)))
    for r in dns.get("forward") or []:
        for b in r.values():
            v = str((b or {}).get("value") or "")
            if "://" in v and v not in [x[1] for x in out]:
                out.append(("forward 内联端点", v))
    for s in dns.get("bootstrap") or []:
        out.append(("bootstrap（明文 UDP）", str(s)))
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    items = []
    for a in args:
        if a.endswith((".yaml", ".yml")):
            items += endpoints_from_profile(a)
        else:
            items.append(("CLI", a))

    print("%-22s %-38s %-10s %s" % ("来源", "端点", "结果", "应答 / 说明"))
    print("-" * 112)
    bad = 0
    for where, s in items:
        proto, host, port = hostport(s)
        # ⚠️ 重试：偶发握手超时不应判成"端点失效"（见文件头 RETRIES 的说明）。
        #    只对**异常**重试；拿到应答（哪怕内容意外）不重试 —— 那是真判据问题。
        last_err = None
        for attempt in range(RETRIES):
            try:
                if proto == "https":
                    st, ans = try_doh(host, port)
                    res = f"HTTP {st}"
                    detail = ans or "（无 A 记录）"
                elif proto == "tls":
                    ans, cn = try_dot(host, port)
                    res = "OK"
                    detail = f"cert CN={cn}  {ans}"
                else:
                    ans = try_udp(host, port)
                    res = "OK"
                    detail = f"{ans}  ⚠️ 明文 UDP:53"
                if attempt:
                    detail += "  （第 %d 次尝试成功）" % (attempt + 1)
                print("%-22s %-38s %-10s %s" % (where, s, res, detail))
                last_err = None
                break
            except Exception as e:                              # noqa: BLE001
                last_err = e
                if attempt < RETRIES - 1:
                    import time
                    time.sleep(RETRY_BACKOFF * (RETRIES - 1 - attempt))
        if last_err is not None:
            bad += 1
            m = str(getattr(last_err, "reason", last_err)).replace("\n", " ")[:56]
            print("%-22s %-38s %-10s %s"
                  % (where, s, "FAIL", "%s（已重试 %d 次）" % (m, RETRIES)))
    print()
    print(f"失效端点：{bad} / {len(items)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
