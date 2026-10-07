# -*- coding: utf-8 -*-
"""Egern 审计脚本的共享工具 —— 消灭「同一判据两份拷贝」。

背景（2026-09-20，二次核查报告 P1）：
  `check_egern_dns.py` 与 `audit_dns_forward.py` 各自实现了一份「端点主机名解析 +
  是否为 IP 字面量 + 国内知名解析器白名单」的逻辑，靠注释互相提醒同步。
  结果：判据本体同步了，**喂给判据的 helper 没同步** ——
  `audit_dns_forward.ep_ip('https://[2400:3200::1]/dns-query')` 返回被截断的 `'[2400:3200:'`，
  而 `check_egern_dns.hostpart()` 正确返回 `'2400:3200::1'`。
  ⇒ 同一份配置，两个脚本给出**相反结论**。

  结论：**靠注释提醒同步两份拷贝是不可靠的。** 本模块把这些共用逻辑收编到一处，
  两个脚本都从这里 import，从结构上消灭拷贝。

后续修正（2026-09-20，三次核查报告 P2）：
  「收编」这一次动作本身引入了新回归 —— `hostpart()` 剥 scheme 从「通用剥离」
  退化成「大小写敏感白名单」，于是 `HTTPS://223.5.5.5/dns-query` 被解析出主机名
  `HTTPS`，端点从 IP 字面量误判成待解析域名，同一份配置读数从 0 high 翻成 9 high。
  已改回大小写不敏感的通用正则，并由 `tests/scheme_case.yaml` 守卫生效。

用法：
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _egern_common import DOMESTIC_RESOLVER_IPS, ep_ip, ip_literal, hostpart
    from _egern_common import fetch_cached          # 远程规则集取件（缓存 + 7 天窗口）
"""

import hashlib
import io
import os
import re
import sys
import tempfile
import time
import urllib.request

# ⭐ 国内知名公共 DNS 解析器 IP —— 「兜底组直连可达」的第二判据。
# 在 profile 文本内无法证明任意 IP 是否可直连，但这些 IP 的归属与服务商是公开事实，
# 且在国内任何链路上都直连可达 —— 与「在 rules 里判给 DIRECT」等价，且不需要
# 配置里额外写装饰性规则。
# ⚠️ 只收「国内」解析器：境外解析器（8.8.8.8 等）必须经代理才可达，一个全由境外 IP
# 组成的组即便端点全是 IP 字面量也**不能**判为直连可达（f5 的真实踩坑）。
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

_IP4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

# ⭐ 通用 scheme 前缀：`scheme://`，**大小写不敏感**，不枚举具体 scheme。
# ⚠️ 不要改成白名单（`("https://", "tls://", ...)`）：那会让 scheme 的拼法参与
#    审计结论。三次核查报告 P2 的回归正是如此 —— 端点写 `HTTPS://223.5.5.5/dns-query`
#    时，白名单失配，`HTTPS` 被当成主机名，端点从「IP 字面量」误判成「待解析域名」，
#    同一份配置的读数从 0 high 翻成 9 high。scheme 拼法不是本工具要审的对象。
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")


def hostpart(ep):
    """从端点字符串里取出主机部分（去 scheme、去 path/query、去 :port）。

    正确处理这些形态（scheme 拼法任意、大小写任意）：
      - `https://223.5.5.5/dns-query`      -> `223.5.5.5`
      - `HTTPS://223.5.5.5/dns-query`      -> `223.5.5.5`
      - `dot://223.6.6.6`                  -> `223.6.6.6`
      - `https://[2400:3200::1]/dns-query` -> `2400:3200::1`   ← IPv6（方括号）
      - `[2400:3200::1]:443`               -> `2400:3200::1`
      - `tls://223.5.5.5:853`              -> `223.5.5.5`
      - `dns.google` / `2001:db8::1`       -> 原样
    """
    s = str(ep).strip()
    m = _SCHEME_RE.match(s)
    if m:
        s = s[m.end():]
    s = s.split("/")[0]                        # 去 path
    s = s.split("?")[0].split("#")[0]          # 去 query / fragment
    if s.startswith("["):                      # IPv6 带方括号
        end = s.find("]")
        return s[1:end] if end != -1 else s.lstrip("[")
    if s.count(":") == 1:                      # host:port（IPv4 或域名）
        return s.split(":")[0]
    return s                                   # 裸 IPv4 / 裸 IPv6 / 域名


def ip_literal(ep):
    """端点是不是 IP 字面量（不需要任何解析）。"""
    host = hostpart(ep)
    if _IP4_RE.match(host):
        return True
    return ":" in host                         # IPv6 字面量


# 兼容旧调用名（audit_dns_forward.py 历史上用的是 ep_ip）
ep_ip = hostpart


# ============================================================================
# 远程规则集取件（缓存 + 新鲜度窗口）—— 三份手抄收编到这一处
# ============================================================================
# 背景（2026-09-24 实测）：`audit_routing_coverage.py` / `audit_ruleset_noresolve.py` /
# `profile_ruleset.py` 各自抄了一份 fetch，**同一个缓存目录名**（`egern-ruleset-cache`）
# 互吃对方落的文件，却两套口径混读：前两份判 7 天窗口，`profile_ruleset.py` 只判
# "文件在不在" ⇒ 同一份陈旧缓存在一个脚本里会出声报"按陈旧那份判"，在另一个脚本里
# 被当成"缓存命中"直接拿去判条目数。这正是本模块开头那条结论的同一个形状：
# **靠注释提醒同步两份拷贝是不可靠的。** 窗口判据从此只有一份。
CACHE_DIR_NAME = "egern-ruleset-cache"
CACHE_MAX_AGE = 7 * 86400          # 秒；与 surge 侧 audit_ruleset_content.py 同一条口径
CACHE_DIR = os.path.join(tempfile.gettempdir(), CACHE_DIR_NAME)


def _slurp(path):
    """读文件正文。**统一走 `with`** —— 缓存目录会被反复读，Windows 上未关的句柄
    会短暂占着文件（2026-09-25 起本模块的读都收口到这里）。"""
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def cache_key(url):
    """URL → 缓存文件名：`<末段消毒名（截 60）>__<全 URL 的 sha1 前 12 位>`。

    ⚠️ 早先**只取 URL 末段**（`split("/")[-1]`）⇒ 不同仓库的同名文件会**互相覆盖**。
    实测（2026-09-25）：当前 profile 引用的 64 条 URL 里 `dns-query` 同名 5 条、
    `generate_204` 同名 4 条（这两类不进缓存，所以还没出事）；但规则集本身已引用
    6 个上游 owner，一旦出现同名规则集，审计就会**拿别的仓库的内容判通过**。
    前半给人读、后半保证唯一。Surge 侧 `audit_ruleset_content.py` 用**同一形状** ——
    两侧缓存目录本就不同（`surge-ruleset-cache` / `egern-ruleset-cache`），所以这不是
    "跨内核共用一份实现"，只是口径一致（并存两套才是隐患）。
    """
    tail = re.sub(r"[^A-Za-z0-9._-]", "_", url.rstrip("/").split("/")[-1])[:60] or "ruleset"
    return "%s__%s" % (tail, hashlib.sha1(url.encode("utf-8")).hexdigest()[:12])


def cache_path_for(url, cache_dir=None):
    """URL → 缓存文件路径。键的算法见 `cache_key()`。"""
    return os.path.join(cache_dir or CACHE_DIR, cache_key(url))


def fetch_cached(url, offline=False, user_agent="egern-audit/1.0", timeout=60, cache_dir=None):
    """取规则集正文，带缓存新鲜度窗口。**只取不印** —— 出声留给调用方，三处措辞不同。

    → `(body, path, source, detail)`
      · `fresh`  本次下载并落盘                 · `cache`  窗口内直接用缓存
      · `stale`  过了窗口后退回的那份（**调用方必须出声**：离线不重下，或重下失败）
      · `miss`   离线且没有缓存 ⇒ `body` 为 None  · `error`  取不到也没有旧份 ⇒ `body` 为 None
    `detail` 是给人看的短句（异常文本 / "离线不重下"），要不要用、怎么拼由调用方定。

    ⚠️ 三条实现约束，都是这份合并前逐字抄着的：文件**存在且非空**才算命中（0 字节的
       半成品不能当"缓存里有"）；过窗口时**先试重下**，失败才退回旧那份；写盘固定 LF。
    """
    cache_dir = cache_dir or CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    path = cache_path_for(url, cache_dir)
    stale = False
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if time.time() - os.path.getmtime(path) <= CACHE_MAX_AGE:
            return _slurp(path), path, "cache", ""
        stale = True
    if offline:
        if stale:
            return _slurp(path), path, "stale", "离线不重下"
        return None, path, "miss", ""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception as exc:                                      # noqa: BLE001
        if stale:
            return _slurp(path), path, "stale", "重下失败：%s" % exc
        return None, path, "error", str(exc)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    return body, path, "fresh", ""



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

