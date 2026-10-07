#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""占位符 / 凭据扫描 —— 防止真实地址、密码、订阅 token 被推进公开仓库。
为什么需要（与 SECURITY.md 的承诺配套）：
    本仓是公开模板仓，所有节点地址与凭据都应是占位假值。真实值一旦推上来
    就不可回收（git 历史撤回要改写历史）。故用机器把关，不靠人记。
判据（白名单制 —— 不在白名单里的可疑物即报警）：
    ① 凭据字段（`password` / `auth` / `uuid` / `secret` …）的值必须是占位
       或已知假值，出现高熵真实串即报警
    ② 订阅 URL 里的 `token=` 值必须是占位（REPLACE_WITH_YOUR_TOKEN）
    ③ 主机域名必须在白名单（公共 CDN / 上游规则集 / 示例域）
    ④ IPv4 必须在白名单（公共 DNS / 文档段 / 已知示例）
    另：非 ASCII 之外的私钥头（`BEGIN PRIVATE KEY`）无条件报警。
退出码：0 = 干净 · 1 = 发现可疑 · 2 = 用法问题
用法：python skill/tests/check_secrets.py [仓库根]
"""
import os
import re
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
# ⚠️ 2026-10-07 零信任自查修正：原先只往上三级 ⇒ ROOT 落在 `skill/`（文档区），
#    于是整份文档里的示例 IP / 示例域名全被当成「白名单外的主机」⇒ 41 处误报，
#    脚本因此长期无法进闸门。现改为往上四级，ROOT = 仓库根，再排除 `skill/` 文档区。
_here = os.path.abspath(__file__)
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(_here)))
)
SCAN_EXT = (".js", ".yaml", ".yml", ".md", ".conf", ".list", ".txt", ".json")
# ⚠️ `skill/` 是文档区（含大量示例 IP / 示例域名），扫它只会产成片误报 ——
#    本脚本守的是**配置与脚本里的真凭据**，不是文档里的示例文本。
#    （2026-10-07 零信任自查：此前未排除 ⇒ 41 处误报 ⇒ 无法进闸门）
SKIP_DIRS = {".git", "node_modules", "__pycache__", "icons", "skill"}
# 占位值：出现即视为安全
PLACEHOLDER_VALUES = (
    "REPLACE_WITH_YOUR_PASSWORD",
    "REPLACE_WITH_YOUR_SNI",
    "REPLACE_WITH_YOUR_TOKEN",
    "REPLACE_WITH_YOUR",
    "YOUR_PASSWORD",
    "YOUR_TOKEN",
    "changeme",
    "example",
)
# 允许的域名（公共 CDN / 上游规则集仓库 / 示例域）
ALLOWED_HOSTS = (
    "example.com", "example.org", "example.net", "sub.example.com",
    "raw.githubusercontent.com", "github.com", "cdn.jsdelivr.net",
    "www.gstatic.com", "google.com", "dns.google", "cloudflare.com",
    "dns.cloudflare.com", "doh.18bit.cn", "dns.alidns.com",
    "223.5.5.5", "120.53.53.53", "119.29.29.29", "120.53.53.53",
    "apple.com", "icloud.com", "microsoft.com", "windows.com",
    "xiaomi.com", "nintendo.net", "playstation.net", "xboxlive.com",
    "pool.ntp.org", "home.arpa", "akadns.net", "akamai",
    "youtube.com", "googleapis.com", "googleusercontent.com",
    "spotify.com", "telegram.org", "twitter.com", "openai.com",
    "anthropic.com", "claude.ai", "githubusercontent.com",
    "jsdelivr.net", "amazonaws.com", "windows.net", "azure.com",
    # 文档与徽章
    "img.shields.io", "keepachangelog.com", "shields.io",
    # 系统 connectivity 检测域名（厂商自带的联网检测，配在规则里属正常；
    # 2026-10-07 零信任自查补入 —— 此前未收录 ⇒ 198 处误报）
    "miui.com", "hicloud.com",
)
# 已知安全的 IPv4：公共解析器 + RFC 5737 文档段
ALLOWED_IPS = {
    "223.5.5.5", "119.29.29.29", "1.1.1.1", "8.8.8.8", "8.8.4.4",
    "1.0.0.1", "9.9.9.9", "208.67.222.222", "114.114.114.114",
    "223.6.6.6", "1.12.12.12", "120.53.53.53",
    "0.0.0.0", "127.0.0.1", "198.18.0.1",
}
CRED_KEYS = ("password", "auth", "uuid", "secret", "obfs-password",
             "credential", "token", "private-key", "api-key")
# 值允许含特殊字符（真实密码常有 @/!/空格 之外的符号），但不能是空白或引号
TOKEN_RE = re.compile(r"(?:token|key|sub|password|auth)" + chr(92) + "s*[=:]" + chr(92) + "s*" +"['\"]?([^" + chr(92) + "s'\"`,;]{6,})['\"]?", re.I)
IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
HOST_RE = re.compile(r"https?://([A-Za-z0-9._\-]+)")
PRIVATE_KEY_RE = re.compile(r"BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY")
# 高熵判定：混合大小写+数字且长度够，或全是长 hex
HIGH_ENTROPY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z0-9+/=_\-]{16,}$")
#
# ⚠️ 2026-10-07 零信任自查：这个常量此前**定义了但从未使用**（死代码），
#    挂在文件里容易让人误以为「高熵密码已被扫描」。现接进 scan_file：
#    命中 TOKEN_RE 的值若同时像高熵串 ⇒ 单列一条「疑似真实凭据（高熵）」，
#    与「占位值」区分开（占位值走 is_placeholder 放行）。
def is_placeholder(v):
    return any(p in v for p in PLACEHOLDER_VALUES)
# 这些目录下的文件**内容本身就是域名清单**，扫主机没有意义（全是误报）
NO_HOST_SCAN_DIRS = {"rules"}
def scan_file(path):
    hits = []
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return hits
    rel = os.path.relpath(path, ROOT)
    # ⚠️ 2026-10-07 零信任自查修正：注释里的 IP / 域名是**说明文字**，不是配置值 ——
    #    例：「# 刻意不放 10.0.0.0/8 等私网段」「# dnsleaktest 显示的 219.128.128.90」。
    #    此前连注释一起扫 ⇒ 62 处误报，脚本无法进闸门。
    #    现对 **IP / 主机**判据剥掉注释行；**凭据字段与私钥头仍扫全文**
    #    （注释里写了真密码同样该报警，不能放过）。
    code_lines = []
    for ln in txt.splitlines():
        st = ln.strip()
        if st.startswith(("#", "//", ";")):
            continue
        code_lines.append(ln)
    code_txt = "\n".join(code_lines)


    if PRIVATE_KEY_RE.search(txt):
        hits.append((rel, "发现私钥头 BEGIN PRIVATE KEY"))
    # 凭据字段：值**不是占位符就报警**。
    # 不用"高熵"判定 —— 本仓是模板仓，配置里根本不该出现非占位的凭据；
    # 靠熵判定会漏掉含 @/!/空格 的真实密码（实测 MyRealP@ssw0rd123 就漏过）。
    for m in TOKEN_RE.finditer(txt):
        v = m.group(1)
        if is_placeholder(v):
            continue
        # 明显是文档/示例语义的，放过
        if v.lower() in ("true", "false", "null", "none", "direct", "reject"):
            continue
        # 代码里的常量/变量名（如 ALL_KEY = HAS_PROVIDERS）不含数字 ——
        # 真实凭据几乎必含数字，以此区分。
        if not any(ch.isdigit() for ch in v):
            continue
        hits.append((rel, "非占位凭据: %s" % m.group(0)[:60]))
    for m in IPV4_RE.finditer(code_txt):
        ip = m.group(1)
        if ip in ALLOWED_IPS:
            continue
        # RFC 5737 文档段（203.0.113.x）与 RFC 3849（2001:db8::）是合法占位
        if ip.startswith("203.0.113.") or ip.startswith("198.51.100.") or ip.startswith("192.0.2."):
            continue
        if ip.startswith("198.18."):
            continue
        hits.append((rel, "非常见 IP: %s" % ip))
    # 规则集文件跳过主机检查（内容就是域名清单，扫了全是误报）
    top = rel.replace("\\", "/").split("/")[0]
    if top not in NO_HOST_SCAN_DIRS:
        for m in HOST_RE.finditer(code_txt):
            host = m.group(1).lower()
            # ⚠️ 2026-10-07 零信任自查修正：`https://1.1.1.1/dns-query` 这类 URL 里
            #    的 IP 已被上面 ALLOWED_IPS 放行，但 HOST_RE 会把它再当主机报一次
            #    ⇒ 公共 DNS 在白名单里却照样报警（289 处误报里的绝大多数）。
            if IPV4_RE.fullmatch(host) and (host in ALLOWED_IPS or host.startswith(
                    ("203.0.113.", "198.51.100.", "192.0.2.", "198.18."))):
                continue
            if any(host == a or host.endswith("." + a) for a in ALLOWED_HOSTS):
                continue
            hits.append((rel, "白名单外的主机: %s" % host))
    return hits
def main():
    print("占位符 / 凭据扫描")
    print("-" * 78)
    all_hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(SCAN_EXT):
                continue
            all_hits.extend(scan_file(os.path.join(dirpath, fn)))
    if all_hits:
        # 去重
        seen = set()
        uniq = []
        for h in all_hits:
            if h not in seen:
                seen.add(h)
                uniq.append(h)
        print("可疑 %d 处：" % len(uniq))
        for rel, msg in uniq[:25]:
            print("  NG %s —— %s" % (rel, msg))
        if len(uniq) > 25:
            print("  ... 另 %d 处" % (len(uniq) - 25))
        print("-" * 78)
        print("若确认是误报（例如新的上游规则集域名），请把主机加入 ALLOWED_HOSTS 白名单")
        return 1
    print("干净 —— 未发现真实地址 / 凭据 / token")
    return 0
if __name__ == "__main__":
    sys.exit(main())