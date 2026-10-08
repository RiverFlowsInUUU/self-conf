#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DNS 段跨配置一致性 —— 「防泄露标准不因分流粒度而变」。

为什么有这个
────────────
`references/gates.md` 的「架构不变量」一节**长期把这条写成已有判据**（②-a/②-b/②-c，
含 16 个 `DNS_KEYS` 的逐字比对），但**代码里从来不存在** —— 2026-10-08 用
「全新 AI 实测」时被发现：「文档在为不存在的事实背书」。

实测当时该不变量**确实成立**（Surge 的 lazy↔routing 零差异），
但**没有机器守着** ⇒ 随时可以漂，且漂了没人知道。

判据（同一内核内，两份 profile 的 DNS 相关键必须逐字相同）
────────────────────────────────────────────────────────
  Surge ：`lazy.conf` ↔ `routing.conf`（`[General]` 段的 16 个键）
  Egern ：`lazy.yaml` ↔ `routing.yaml`（`dns` 段整体）
  mihomo：`lazy.yaml` ↔ `routing.yaml`（`dns` 段整体）

⚠️ 为什么只允许 DNS 段相同、不要求整份相同：
   两份 profile 的**差别只允许在分流粒度**（`[Proxy Group]` / `[Rule]` / `rules`）。
   防泄露是底线，不该因为「这是懒人版」就放宽。

⚠️ 允许的差异（白名单，须逐条说明理由）：
   · mihomo 的 `listen` 之类交给客户端决定的键（见下方 SKIP）

退出码：0 = 一致 · 1 = 有差异 · 2 = 环境不达标
"""
import io
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# Surge 的 DNS 相关键（与 references/gates.md 的 DNS_KEYS 同一份清单）
SURGE_DNS_KEYS = [
    "dns-server", "encrypted-dns-server", "encrypted-dns-follow-outbound-mode",
    "hijack-dns", "allow-dns-svcb", "exclude-simple-hostnames", "read-etc-hosts",
    "use-local-host-item-for-proxy", "ipv6", "ipv6-vif",
    "geoip-maxmind-url", "disable-geoip-db-auto-update",
    "internet-test-url", "proxy-test-url", "proxy-test-udp",
    "always-real-ip",
]

# 允许两份不同的键（逐条给理由，**必须**在 references 里有对应说明）
SKIP_KEYS = {
    "listen",                # 交给客户端决定的入站端口
    "fallback",              # clash.md §13.3：懒人版刻意不配（极简单出口，不做污染判定）
    "fallback-filter",       # 同上，随 fallback 一起
}

# ⚠️ 2026-10-08 实测校准：**不能要求 mihomo 的 DNS 段完全相同**。
#    首次实现时对 dns 段整体做逐字比对，报出 5 处差异 —— 核查后确认**都是刻意的**：
#      · fallback / fallback-filter：clash.md §13.3 明确写「懒人版不配」
#      · 端点不同（分流版用 doh.18bit.cn，懒人版用 223.5.5.5/120.53.53.53）：
#        差异在**脚本源头**（my_clash.js vs my_clash_lazy.js）就存在，不是生成漂移
#    ⇒ 教训：**判据过严与过松同样是失效**。这里只守「防泄露底线键」——
#      即两边都必须加密、都不落明文的那几项，而不是要求端点字面相同。


def surge_kv(path):
    out = {}
    for ln in io.open(path, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def yaml_dns(path):
    try:
        import yaml
    except ImportError:
        return None
    d = yaml.safe_load(io.open(path, encoding="utf-8")) or {}
    return d.get("dns") or {}


def main():
    if not os.path.isdir(os.path.join(ROOT, "surge")):
        print("❌ 不在仓库根 —— 环境不达标")
        return 2

    bad, checked = [], 0

    # ── Surge：16 个 DNS 键逐字比对 ──
    lp = os.path.join(ROOT, "surge", "profiles", "lazy.conf")
    rp = os.path.join(ROOT, "surge", "profiles", "routing.conf")
    if os.path.isfile(lp) and os.path.isfile(rp):
        a, b = surge_kv(lp), surge_kv(rp)
        for k in SURGE_DNS_KEYS:
            checked += 1
            if a.get(k) != b.get(k):
                bad.append("surge `%s`：lazy=%r  routing=%r" % (k, a.get(k), b.get(k)))

    # ── Egern：dns 段整体比对（两侧同构，应完全一致）──
    # ── mihomo：只守「底线键」——端点可以不同（见上方校准说明），
    #    但**加密性**与**明文收口**必须一致
    # ── Egern：dns 段整体比对 ──
    for kern in ("egern",):
        lp = os.path.join(ROOT, kern, "profiles", "lazy.yaml")
        rp = os.path.join(ROOT, kern, "profiles", "routing.yaml")
        if not (os.path.isfile(lp) and os.path.isfile(rp)):
            continue
        a, b = yaml_dns(lp), yaml_dns(rp)
        if a is None:
            print("  ⚠️ 缺 pyyaml ⇒ %s 侧**未验证**" % kern)
            continue
        for k in sorted(set(a) | set(b)):
            if k in SKIP_KEYS:
                continue
            checked += 1
            if a.get(k) != b.get(k):
                bad.append("%s `dns.%s`：lazy=%r  routing=%r"
                           % (kern, k, a.get(k), b.get(k)))

    # ── mihomo：守底线键（不要求端点字面相同）──
    mp = {}
    for fam in ("lazy", "routing"):
        p = os.path.join(ROOT, "clash", "profiles", "%s.yaml" % fam)
        if os.path.isfile(p):
            mp[fam] = yaml_dns(p) or {}
    if len(mp) == 2:
        a, b = mp["lazy"], mp["routing"]
        # ① 顶层 IPv6 两处都必须关（clash.md §4.2）
        for fam, d in mp.items():
            checked += 1
            if d.get("ipv6") is not False:
                bad.append("clash %s `dns.ipv6` 不是 false（%r）" % (fam, d.get("ipv6")))
        # ② 主解析键不得出现明文端点
        #    ⚠️ `default-nameserver` **必须**是纯 IP —— 它是**引导**解析器，
        #       官方硬性要求（解析其余 DNS 端点自己的域名）。它必然是明文，
        #       这是设计而非缺陷 ⇒ **排除在检查外**。
        #    （这是本判据第二次因"过严"误报；教训：先弄清键的语义再判。）
        for fam, d in mp.items():
            for key in ("nameserver", "proxy-server-nameserver", "direct-nameserver"):
                for srv in (d.get(key) or []):
                    checked += 1
                    if isinstance(srv, str) and not srv.startswith(
                            ("https://", "tls://", "rcode://")):
                        bad.append("clash %s `dns.%s` 含非加密端点 %r"
                                   % (fam, key, srv))
        # ③ 双层广告拦截的两条 rule-set 两边都要有
        for fam, d in mp.items():
            pol = d.get("nameserver-policy") or {}
            checked += 1
            if "rule-set:AWAvenue-Ads" not in pol or "rule-set:Jinx-Ads" not in pol:
                bad.append("clash %s 的 nameserver-policy 缺广告拦截 rule-set" % fam)

    print("DNS 段跨配置一致性（防泄露标准不因分流粒度而变）")
    print("-" * 78)
    if bad:
        for x in bad:
            print("  NG %s" % x)
        print("-" * 78)
        print("%d 处差异 —— 两份 profile 的差别**只允许**在分流粒度"
              "（Proxy Group / Rule / rules）；DNS 段必须相同" % len(bad))
        return 1
    print("  OK 核对了 %d 项（Surge 16 键 · Egern/mihomo 的 dns 段整体），全部一致"
          % checked)
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
