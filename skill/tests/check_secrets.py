#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""占位符 / 凭据纪律扫描（自原 skill/tests/surge/architecture.sh ① 提炼，2026-09-27 精简）。

本仓的 profiles 是**脱敏模板**：节点地址必须是 RFC 5737 文档段 / example.com，
凭据必须是 REPLACE_WITH_*，订阅 URL 的 token/key/sub 参数值必须含 REPLACE_WITH。
真实值一旦推上公开仓库就不可回收 —— 这是本仓最严重的一类泄露。

扫描面 = 全仓 walk 到的 `*.conf` / `*.yaml` / `*.yml`（跳过 `.` 开头目录与
node_modules / __pycache__；故意不用 git ls-files —— 未提交的本地工作副本
正是这道纪律要拦的东西）。注释行不判（说明性文字不是泄露），
但"禁止的敏感串"与订阅 token 两类连注释一起判（藏在注释里同样是残留）。

用法：`python skill/tests/check_secrets.py`（仓库根默认取本文件位置往上两级）
退出码：0 全过 · 1 有判负 · 2 前置不达标（扫不到当前版 profile）
"""
import os
import re
import sys

# 仓库定位：靠标志物上溯，不依赖目录层数（见 tools/lib/paths.py）
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../lib'))
from paths import repo_root as _repo_root  # noqa: E402


try:
    for _s in (sys.stdout, sys.stderr):
        _s.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = _repo_root()
# RFC 5737 文档段 + mihomo 的 fake-ip 保留段（198.18.0.0/15，RFC 6815）。
# 后者是整合 mihomo 内核后新增的：fake-ip-range 默认 198.18.0.1/16，
# 对 Surge / Egern 而言是陌生段，不加入就会被误判成真实 IP。
DOC_NETS = ("192.0.2.", "198.51.100.", "203.0.113.", "198.18.")
ALLOWED_DOMAINS = (
    "example.com", "example.net", "example.org",
    "sub.example.com", "cdn-relay.example.com",
    "connect.rom.miui.com", "www.gstatic.com",
    "raw.githubusercontent.com", "cdn.jsdelivr.net",
    "github.com", "api.github.com", "objects.githubusercontent.com",
    "www.google.com", "g.cn", "google.cn",
    "apple.com", "Surge", "Jinx", "ACL4SSR", "Loyalsoldier", "adysec",
    "blackmatrix7", "nintendo.net", "playstation.net", "xboxlive.com",
    "pool.ntp.org", "market.xiaomi.com", "home.arpa",
)
FORBIDDEN_SUBSTRINGS = [
    # 旧仓教训黑名单：只收来历可考的真实泄露串（2026-09-29 外部审查时清理过一次，
    # 移除了无法确证来历的 cloudflare-cdn.com —— 禁串条目必须条条有据，否则是哑弹）
    "tange365.com",
    "wangxinyu",
]
TOKEN_RE = re.compile(r"(?:token|key|sub)\s*=\s*([A-Za-z0-9_\-]{6,})", re.I)
_IPV4 = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
KNOWN_IPS = {
    "223.5.5.5", "119.29.29.29", "1.1.1.1", "8.8.8.8", "8.8.4.4",
    "1.0.0.1", "9.9.9.9", "208.67.222.222", "114.114.114.114",
    "223.6.6.6", "1.12.12.12", "120.53.53.53",
    "0.0.0.0", "127.0.0.1",
}
YAML_CRED_KEYS = ("password", "username", "uuid", "secret", "obfs-password", "credential")
YAML_CRED_RE = re.compile(r"^\s*(?:-\s+)?(%s)\s*:\s*(.+)$" % "|".join(YAML_CRED_KEYS), re.M)
YAML_SNI_RE = re.compile(r"^\s*(?:-\s+)?(sni|servername)\s*:\s*(.+)$", re.M)
PLACEHOLDER_VALS = ("REPLACE_WITH_",)


def strip_c(s, yaml_=False):
    """去掉整行注释与行尾注释。YAML 只认 `#`；行首空白必须保留（YAML 层级）。"""
    if s.lstrip().startswith("#") or (not yaml_ and s.lstrip().startswith(";")):
        return ""
    marks = "#" if yaml_ else "#;"
    for i in range(1, len(s)):
        if s[i] in marks and s[i - 1] in " \t":
            return s[:i].rstrip()
    return s.rstrip()


def scan_targets(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")
                  and d not in ("node_modules", "__pycache__")]
        for fn in sorted(fns):
            if not fn.endswith((".conf", ".yaml", ".yml")):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            tier = ("FIXTURE" if rel.startswith("skill/tests/") else "LIVE")
            out.append((tier, rel, p))
    return sorted(out)


def main():
    fails = []
    scan = scan_targets(ROOT)
    live = [x for x in scan if x[0] == "LIVE"]
    if not live:
        print("❌ 全仓 walk 不到任何当前版 profile —— 目录被挪走了，这**不是**\"没有敏感串\"")
        return 2

    for tier, f, path in scan:
        yaml_ = f.endswith((".yaml", ".yml"))
        tag = "%s %s" % (tier, f)
        try:
            raw_text = open(path, encoding="utf-8").read()
        except UnicodeDecodeError:
            fails.append(f"{tag}: 非 UTF-8 ⇒ 占位符纪律读不了（按未审处理）")
            continue
        text = "\n".join(strip_c(l, yaml_) for l in raw_text.splitlines())

        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in raw_text:
                fails.append(f"{tag}: 出现禁止的敏感串 `{bad}`")

        for ip in set(_IPV4.findall(text)):
            if ip.startswith(DOC_NETS) or ip in KNOWN_IPS:
                continue
            fails.append(f"{tag}: 出现非占位 IPv4 `{ip}`（必须用文档段 192.0.2.x / 198.51.100.x / 203.0.113.x，或 mihomo fake-ip 段 198.18.x）")

        if yaml_:
            for m in YAML_CRED_RE.finditer(text):
                val = m.group(2).strip().strip("\"'")
                if not val or val.startswith(PLACEHOLDER_VALS):
                    continue
                fails.append(f"{tag}: 凭据字段 `{m.group(1)}` 的值不是占位符（`{val[:24]}…`）")
            for m in YAML_SNI_RE.finditer(text):
                val = m.group(2).strip().strip("\"'")
                if not val or val.startswith(PLACEHOLDER_VALS) or val.endswith("example.com"):
                    continue
                fails.append(f"{tag}: sni 的值不是占位符（`{val}`）")
        else:
            for m in re.finditer(r"(password|username|auth)\s*=\s*\"?([^,\"\n]+)", text):
                val = m.group(2).strip()
                if val.startswith("REPLACE_WITH_"):
                    continue
                fails.append(f"{tag}: 凭据字段 `{m.group(1)}` 的值不是占位符（`{val[:24]}…`）")
            for m in re.finditer(r"sni\s*=\s*([^,\n]+)", text):
                val = m.group(1).strip()
                if val.startswith("REPLACE_WITH_") or val.startswith(DOC_NETS) \
                        or val.endswith("example.com"):
                    continue
                fails.append(f"{tag}: sni 的值不是占位符（`{val}`）")

        for m in TOKEN_RE.finditer(raw_text):
            val = m.group(1)
            if "REPLACE_WITH" in val.upper():
                continue
            fails.append(f"{tag}: 订阅 URL 里出现疑似真实 token（`{val[:8]}…`）—— 必须写成 REPLACE_WITH_YOUR_TOKEN")

        if yaml_:
            in_proxies = False
            for i, line in enumerate(text.splitlines(), 1):
                if line.startswith("proxies:"):
                    in_proxies = True
                    rest = line.split(":", 1)[1].strip()
                    if rest not in ("", "[]"):
                        fails.append(f"{tag}:{i}: `proxies:` 内联了非空值 —— 模板不得携带节点")
                    continue
                if in_proxies and line and not line[0].isspace() and not line.startswith("-") \
                        and ":" in line:
                    in_proxies = False
                if not in_proxies:
                    continue
                m = re.search(r"\b(?:server|host)\s*[:=]\s*[\"']?([^\"'\s,]+)", line)
                if not m:
                    continue
                srv = m.group(1)
                if _IPV4.match(srv):
                    if not (srv.startswith(DOC_NETS) or srv in KNOWN_IPS):
                        fails.append(f"{tag}:{i}: 节点 `server` 是非占位 IPv4 `{srv}`")
                    continue
                if srv.startswith("["):
                    continue
                if not any(a in srv for a in ALLOWED_DOMAINS):
                    fails.append(f"{tag}:{i}: 节点主机名 `{srv}` 不在允许清单内")
        else:
            in_proxy = False
            for i, line in enumerate(text.splitlines(), 1):
                s = line.strip()
                if s.startswith("[Proxy]"):
                    in_proxy = True
                    continue
                if s.startswith("[") and in_proxy:
                    in_proxy = False
                if not in_proxy or not s or "=" not in s:
                    continue
                rhs = s.split("=", 1)[1]
                p = [x.strip() for x in rhs.split(",")]
                if len(p) < 2:
                    continue
                server = p[1]
                if _IPV4.match(server) or server.startswith("["):
                    continue
                if not any(a in server for a in ALLOWED_DOMAINS):
                    fails.append(f"{tag}:{i}: [Proxy] 里的节点主机名 `{server}` 不在允许清单内")

    if fails:
        print("❌ 占位符 / 凭据纪律判负 %d 处：" % len(fails))
        for f_ in fails:
            print("   · " + f_)
        return 1
    print("✅ 占位符 / 凭据纪律：%d 个 conf/yaml 全过（当前版 %d · 夹具 %d）"
          % (len(scan), len(live), len(scan) - len(live)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
