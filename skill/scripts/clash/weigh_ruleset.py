#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""称一个 mihomo 规则集的"重量"：条目构成 / 可删冗余 / 加载与匹配耗时 /（可选）与小表的覆盖对比。

为什么需要（对标缺口）：
    egern 侧有 `weigh_ruleset.py`，clash 侧此前没有 —— 而 clash 有 25 份 provider，
    其中 `cn` 是 11 万条级的大表。

    用途：回答「这张表值不值得用」。尤其是大表（10 万条级）与小表（几百条级）
    在体积上差 100 倍时，必须用**覆盖率**而不是文件大小来决策 ——
    这正是本仓决定「`category-ai-chat-!cn`（181 条）不够，还要自托管
    `AI_Domains`（272 条）」的依据（两者交集 177、差集 94 条伴生域）。

用法：
    python skill/scripts/clash/weigh_ruleset.py rules/AI.list
    python skill/scripts/clash/weigh_ruleset.py big.list --sub small.list
    python skill/scripts/clash/weigh_ruleset.py rules/AI.list --probe www.jd.com --probe api.deepseek.com

内存口径（重要）：
    下面的 RSS 是 **Python dict** 的数字，约为原生实现（Go）的 2 倍。
    原生实测：每个域名条目 ≈ 130–175 B（mihomo v1.19 / Go：111,332 域名 + 12,472 IP
    = +22.6 MB 稳态 RSS）。估任何表的内存用 `条目数 × 0.15 KB`。
"""

import argparse
import collections
import gc
import os
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DOMAIN_TYPES = ("DOMAIN-SUFFIX", "DOMAIN", "DOMAIN-KEYWORD", "DOMAIN-REGEX",
                "DOMAIN-WILDCARD")


def rss_mb():
    try:
        import psutil  # type: ignore
        return psutil.Process().memory_info().rss / 1048576
    except Exception:
        return 0.0


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().split("\n")


def parse(lines):
    """→ (域名条目[(type,value)], IP条目数, 未识别行数)"""
    doms, ipn, unknown = [], 0, 0
    for raw in lines:
        l = raw.strip()
        if not l or l[0] in "#/;":
            continue
        if l.endswith(":") or l in ("payload",):
            continue
        if l.startswith("- "):
            l = l[2:].strip().strip("'\"")
        elif l.startswith("-"):
            l = l[1:].strip().strip("'\"")
        if not l:
            continue
        if "," in l:
            t, _, v = l.partition(",")
            t, v = t.strip().upper(), v.strip()
            if t.startswith("IP-CIDR"):
                ipn += 1
            elif t in DOMAIN_TYPES:
                doms.append((t, v))
            else:
                unknown += 1
            continue
        # 裸条目：v2fly 的 `+.X` / `.X` 是后缀语义，裸 X 亦按后缀处理（偏保守）
        if l.startswith("+.") or l.startswith("."):
            doms.append(("DOMAIN-SUFFIX", l.lstrip("+.")))
        else:
            doms.append(("DOMAIN-SUFFIX", l))
    return doms, ipn, unknown


def load_table(path):
    doms, ipn, unknown = parse(read_lines(path))
    exact = {v for t, v in doms if t == "DOMAIN"}
    suffix = [v for t, v in doms if t == "DOMAIN-SUFFIX"]
    others = [(t, v) for t, v in doms if t not in ("DOMAIN", "DOMAIN-SUFFIX")]
    return {"exact": exact, "suffix": suffix, "others": others,
            "ip": ipn, "unknown": unknown, "n": len(doms)}


def hit(host, table):
    if host in table["exact"]:
        return "DOMAIN"
    for s in table["suffix"]:
        if host == s or host.endswith("." + s):
            return "DOMAIN-SUFFIX"
    for t, v in table["others"]:
        if t == "DOMAIN-KEYWORD" and v in host:
            return t
    return None


def main():
    ap = argparse.ArgumentParser(description="称一个 mihomo 规则集的重量")
    ap.add_argument("ruleset", help="规则集文件（.list / .yaml / .txt）")
    ap.add_argument("--sub", help="小表：与大表做覆盖对比")
    ap.add_argument("--probe", action="append", default=[],
                    help="探针域名，可重复（看是否被命中、耗时）")
    args = ap.parse_args()

    p = args.ruleset
    if not os.path.exists(p):
        print("文件不存在: %s" % p)
        return 2

    print("规则集重量：%s" % os.path.basename(p))
    print("-" * 78)

    t0 = time.time()
    table = load_table(p)
    load_s = time.time() - t0

    doms_n = table["n"]
    size_kb = os.path.getsize(p) / 1024
    print("  文件体积      %.1f KB" % size_kb)
    print("  条目          %d 条（域名 %d / IP %d / 未识别 %d）"
          % (doms_n, doms_n, table["ip"], table["unknown"]))
    print("  构成          exact %d · suffix %d · 其它 %d"
          % (len(table["exact"]), len(table["suffix"]), len(table["others"])))
    print("  加载耗时      %.3f s" % load_s)
    print("  估算内存      ≈ %.1f MB（原生口径：条目 × 0.15 KB）" % (doms_n * 0.15 / 1024))

    # 冗余：被更长后缀覆盖的短后缀
    suf = sorted(set(table["suffix"]), key=len)
    redundant = []
    for i, a in enumerate(suf):
        for b in suf[i + 1:]:
            if b.endswith("." + a) or b == a:
                redundant.append(a)
                break
    if redundant:
        print("  可删冗余      %d 条（被更长后缀覆盖）" % len(redundant))
        for r in redundant[:8]:
            print("       %s" % r)
        if len(redundant) > 8:
            print("       ... 另 %d 条" % (len(redundant) - 8))
    else:
        print("  可删冗余      0 条")

    if args.probe:
        print("  探针：")
        gc.collect()
        for h in args.probe:
            t1 = time.time()
            r = hit(h, table)
            dt = (time.time() - t1) * 1000
            print("       %-32s %-16s %.2f ms" % (h, r or "未命中", dt))

    if args.sub:
        if not os.path.exists(args.sub):
            print("  小表不存在: %s" % args.sub)
            return 2
        sub = load_table(args.sub)
        inter = 0
        for t, v in [(("DOMAIN", x)) for x in sub["exact"]] + \
                    [(("DOMAIN-SUFFIX", x)) for x in sub["suffix"]]:
            if hit(v, table):
                inter += 1
        total = len(sub["exact"]) + len(sub["suffix"])
        pct = (inter / total * 100) if total else 0
        print("  与小表对比    %s：%d/%d 条被大表覆盖（%.1f%%）"
              % (os.path.basename(args.sub), inter, total, pct))
        print("  ⇒ 未被覆盖的 %d 条，就是「大表不够用」的证据" % (total - inter))

    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
