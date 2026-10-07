#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 Egern profile 引用的**远程规则集**里是否存在「会强制 DNS 解析」的 IP 类条目。

为什么必须有这个脚本
--------------------
官方 rules 文档原文：
    no_resolve (bool), 可选 —— 仅适用于 IP 类规则（geoip、ip_cidr、ip_cidr6、asn）。
    **设为 true 时仅匹配已解析的 IP 地址，不会触发 DNS 解析。**
⇒ 反过来说：**不带 no_resolve 的 IP 类条目会触发 DNS 解析。**

这个缺陷藏在**别人仓库里的规则集文件**中，profile 自己写得多干净都看不出来。实测踩坑：
blackmatrix7 的 `Surge/Apple/Apple_All.list` 有 13 条 IP-CIDR（139.178.128.0/18 等 Apple CDN 段）
没带 no-resolve。该规则排 `default` 之前、policy=DIRECT（未禁用），于是
**每个没被前面规则命中的域名，经过它都会被强制本地解析一次** ——
表现为 Egern DNS 日志里「规则判定 default → Final → Proxy，但 upstream 显示 bootstrap」，
在运营商蜂窝上就是明文 :53，泄露给运营商。

blackmatrix7 的命名约定（可直接换用等价文件）
--------------------------------------------
    XXX.list             标准版（IP 条目**不一定**带 no-resolve）
    XXX_No_Resolve.list  所有 IP 条目都带 no-resolve（推荐；对 IP 形式连接判定无影响）
    XXX_Resolve.list     所有 IP 条目**都不**带 no-resolve（会强制解析，勿用于大范围规则）
    XXX_Domain.list      纯域名、零 IP 条目（最干净，但会失去 IP 形式连接的路由）
⚠️ 换用前务必跑本脚本核对：`XXX` 与 `XXX_No_Resolve` 在**去掉 ,no-resolve 后必须逐条相同**，
   否则覆盖范围变了。Apple 实测：1616 条完全一致，只是那 13 条补上了后缀。

用法
----
    python audit_ruleset_noresolve.py profile.yaml [profile2.yaml ...]
    python audit_ruleset_noresolve.py --url https://.../Apple_All.list     # 单文件模式
    python audit_ruleset_noresolve.py profile.yaml --offline                # 只用缓存

退出码：0 = 没有 enabled 且缺 no-resolve 的规则集；1 = 有。
"""
import argparse
import io
import os
import sys
# 输出编码垫片：见 _egern_common.force_utf8_stdout —— GBK 控制台下 emoji 会崩成退出码 1
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _egern_common import CACHE_MAX_AGE, fetch_cached, force_utf8_stdout  # noqa: E402

try:
    import yaml
except ImportError:
    print("需要 PyYAML：<venv>/Scripts/python -m pip install pyyaml", file=sys.stderr)
    sys.exit(2)

# 新鲜度窗口与取件本体都在 `_egern_common.fetch_cached`（2026-09-24 三份手抄收编到那一处）；
# 这里只把它的 `error` 翻成本脚本行内一直在用的 `FAIL <原因>` 标签。


def fetch(url, offline=False):
    """取规则集正文。返回 `(text, path, source)`，source ∈ `fresh`（本次下载）·
    `cache`（窗口内命中）· `stale`（过了窗口退回旧那份，调用方要出声）· `miss` · `FAIL <原因>`。
    """
    body, path, source, detail = fetch_cached(url, offline,
                                              user_agent="egern-dns-audit/1.0", timeout=60)
    return body, path, ("FAIL " + detail) if source == "error" else source


def parse(body):
    """返回 (总条目, IP类条目列表, 缺 no-resolve 的 IP 条目列表, 类型分布)。"""
    lines = [l.strip() for l in body.split("\n") if l.strip() and not l.strip().startswith(("#", "//"))]
    entries = []
    for l in lines:
        if l.startswith("- "):          # Clash YAML payload 行
            l = l[2:].strip()
        if "," not in l and l.startswith("."):   # Egern/QuantumultX 裸域名写法
            l = "DOMAIN-SUFFIX," + l
        entries.append(l)
    ip = [l for l in entries if l.split(",")[0].strip().upper() in
          ("IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP", "IP-CIDR6".upper())]
    missing = [l for l in ip if "no-resolve" not in l.lower()]
    dist = {}
    for l in entries:
        dist[l.split(",")[0].strip()] = dist.get(l.split(",")[0].strip(), 0) + 1
    return entries, ip, missing, dist


def collect(doc):
    """从 profile 里收集所有远程规则集引用：(段落, 规则类型, url, policy, disabled, rule_no_resolve)"""
    out = []
    for section, lst in (("rules", doc.get("rules") or []),
                         ("dns.forward", (doc.get("dns") or {}).get("forward") or [])):
        for r in lst:
            if not isinstance(r, dict):
                continue
            for t, b in r.items():
                if not isinstance(b, dict):
                    continue
                m = str(b.get("match") or "")
                if m.startswith("http"):
                    out.append((section, t, m, b.get("policy") or b.get("value"),
                                bool(b.get("disabled")), b.get("no_resolve")))
    return out


def main():
    ap = argparse.ArgumentParser(description="审计 Egern 规则集里缺 no-resolve 的 IP 条目")
    ap.add_argument("profiles", nargs="*", help="Egern profile yaml")
    ap.add_argument("--url", help="直接审计单个规则集 URL")
    ap.add_argument("--offline", action="store_true", help="只用本地缓存")
    a = ap.parse_args()
    if not a.profiles and not a.url:
        ap.print_help()
        return 2

    jobs = []
    if a.url:
        jobs.append(("(url)", "ruleset", a.url, "-", False, None))
    for p in a.profiles:
        doc = yaml.safe_load(io.open(p, encoding="utf-8"))
        jobs += collect(doc)

    if not jobs:
        print("没有找到任何远程规则集引用。")
        return 0

    print(f"共 {len(jobs)} 个远程规则集引用\n")
    print(f"{'规则集':34s} {'条目':>7s} {'IP类':>6s} {'缺no-resolve':>13s}  {'状态':6s} 归属")
    print("-" * 96)
    highs, goods = [], []
    hows = []
    for section, t, url, policy, disabled, nr in jobs:
        body, path, how = fetch(url, a.offline)
        name = url.rstrip("/").split("/")[-1]
        if body is None:
            print(f"{name:34s} {'-':>7s} {'-':>6s} {'-':>13s}  {'取失败':6s} {how}")
            continue
        hows.append(how)
        entries, ip, missing, dist = parse(body)
        status = "禁用" if disabled else "启用"
        flag = ""
        if missing:
            flag = f"  <<<< {len(missing)} 条 IP 规则未带 no-resolve，会强制 DNS 解析"
            if not disabled:
                highs.append((name, policy, len(missing)))
        else:
            goods.append(name)
        print(f"{name:34s} {len(entries):>7d} {len(ip):>6d} {len(missing):>13d}  {status:6s} {policy}{flag}")
        if how == "stale":
            # 两种"退回陈旧那份"的成因不一样，话要说对：离线档根本没尝试重下。
            why = "，--offline 不重下" if a.offline else "且重下失败"
            print(f"{'':34s} ⚠️ 缓存已过 {CACHE_MAX_AGE // 86400} 天窗口{why} ⇒ 以上按陈旧那份判")
        if missing and not disabled:
            print(f"{'':34s} 样例: " + " | ".join(missing[:3]))
        if section == "dns.forward":
            print(f"{'':34s} (以上来自 dns.forward，是 DNS 转发而非路由)")

    print("\n" + "=" * 96)
    print("缓存读数：%d 个规则集 —— 新下载 %d · 窗口内直用 %d · 过期退回 %d（窗口 %d 天；"
          "过期退回**只报不判**，要按最新规则集下就联网重跑）"
          % (len(hows), hows.count("fresh"), hows.count("cache"), hows.count("stale"),
             CACHE_MAX_AGE // 86400))
    if highs:
        print(f"HIGH —— 以下规则集被启用，且含 {sum(h[2] for h in highs)} 条未带 no-resolve 的 IP 条目：")
        for n, p, c in highs:
            print(f"  * {n}  (policy={p}, 缺 {c} 条)")
        print("\n后果：每一条走到该规则的域名都会被强制本地解析一次；该解析若落在 bootstrap")
        print("      （明文 UDP:53），在运营商蜂窝上就直接泄露给运营商。")
        print("\n修法（按推荐顺序）：")
        print("  1) 换用同源等价文件：blackmatrix7 提供 XXX_No_Resolve.list。")
        print("     ⚠️ 必须核对：去掉 ,no-resolve 后两份文件逐条相同（否则覆盖范围变了）。")
        print("  2) 若上游没有 No_Resolve 变体：自建一份把 IP 条目补上 ,no-resolve 的镜像。")
        print("  3) 下策：整条规则 disabled，或用纯域名变体 XXX_Domain.list。")
        return 1
    print("OK —— 所有被启用的规则集，其 IP 类条目都带 no-resolve（不会为匹配域名而触发解析）。")
    if goods:
        print(f"（共 {len(goods)} 个规则集核对通过）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
