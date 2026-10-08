# -*- coding: utf-8 -*-
"""
称一个域名规则集的"重量"：条目构成 / 可删冗余 / 标签深度 / 加载与匹配耗时 /（可选）与小表的覆盖对比。

用途：回答「这张表值不值得用」——尤其是当大表（10 万条级）和小表（几百条级）在体积上差 100 倍时，
必须用「覆盖率」而不是「文件大小」来决策。

用法：
    python weigh_ruleset.py ChinaMax_All_No_Resolve.list
    python weigh_ruleset.py big.list --sub small.list --probe www.jd.com --probe api.deepseek.com

内存口径说明（重要）：
    下面的 RSS 是 **Python dict 实现**的数字，约为原生实现（Go/Swift/C）的 2 倍。
    原生实现的实测经验值：**每个域名条目 ≈ 130–175 B**（mihomo v1.19 / Go 实测：
    111,332 域名 + 12,472 IP = +22.6 MB 稳态 RSS）。估任何表的内存就用 `条目数 × 0.15 KB`。
    ⇒ 想要原生口径的准确数字，必须真的起一个内核去量（见本 skill 报告里的 mihomo 基准方法）。
"""
import argparse
import collections
import gc
import io
import os
import random
import sys
import time
# 共用模块定位：`_*_common` 统一在 self-conf-skills/lib/（重组后不再与本脚本同目录）
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _cand in (_os.path.normpath(_os.path.join(_d, "..", "..", "lib")),
              _os.path.normpath(_os.path.join(_d, "..", "lib")), _d):
    if any(_os.path.isfile(_os.path.join(_cand, _m)) for _m in
           ("_surge_common.py", "_egern_common.py", "_clash_common.py")):
        _sys.path.insert(0, _cand)
        break

from _egern_common import force_utf8_stdout  # noqa: E402



DOMAIN_TYPES = ("DOMAIN-SUFFIX", "DOMAIN", "DOMAIN-KEYWORD")
IP_TYPES = ("IP-CIDR", "IP-CIDR6", "IP-ASN")


def rss_mb():
    try:
        import psutil
        gc.collect()
        return psutil.Process().memory_info().rss / 1048576
    except Exception:
        return None


def read_lines(path):
    return io.open(path, encoding="utf-8", errors="replace").read().split("\n")


def parse(lines):
    cnt = collections.Counter()
    byt = collections.Counter()
    domains = []
    nbytes = sum(len(l.encode("utf-8")) + 1 for l in lines)
    for l in lines:
        s = l.strip()
        if not s or s[0] == "#":
            continue
        k = s.split(",", 1)[0].strip()
        cnt[k] += 1
        byt[k] += len(l.encode("utf-8")) + 1
        if k in DOMAIN_TYPES:
            domains.append(s.split(",")[1].strip().lower())
    return cnt, byt, domains, nbytes


def load_table(path):
    suf, exact, kw = set(), set(), []
    for l in read_lines(path):
        s = l.strip()
        if not s or s[0] == "#":
            continue
        k, _, rest = s.partition(",")
        k = k.strip()
        v = rest.split(",")[0].strip().lower()
        if k == "DOMAIN-SUFFIX":
            suf.add(v.lstrip("+."))
        elif k == "DOMAIN":
            exact.add(v)
        elif k == "DOMAIN-KEYWORD":
            kw.append(v.lstrip("+."))
    return suf, exact, kw


def hit(host, table):
    suf, exact, kw = table
    host = host.lower()
    if host in exact:
        return True
    labs = host.split(".")
    for i in range(len(labs)):
        if ".".join(labs[i:]) in suf:
            return True
    return any(k in host for k in kw)


def build_trie(domains):
    root, nodes = {}, 0
    for d in domains:
        node = root
        for lab in reversed(d.split(".")):
            nxt = node.get(lab)
            if nxt is None:
                nxt = {}
                node[lab] = nxt
                nodes += 1
            node = nxt
        node["\x00"] = True
    return root, nodes


def lookup(root, d):
    node = root
    for lab in reversed(d.split(".")):
        node = node.get(lab)
        if node is None:
            return False
        if node.get("\x00"):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ruleset")
    ap.add_argument("--sub", help="对照的小规则集（看它覆盖大表的多少）")
    ap.add_argument("--probe", action="append", default=[], help="额外探针域名，可重复")
    a = ap.parse_args()

    path = a.ruleset
    lines = read_lines(path)
    cnt, byt, domains, nbytes = parse(lines)
    print(f"### {os.path.basename(path)}")
    print(f"    文件 {os.path.getsize(path):,} B / {len(lines):,} 行；有效条目 {sum(cnt.values()):,}")
    print(f"\n{'类型':18s}{'条数':>10s}{'字节':>12s}{'占比':>8s}")
    for t, c in cnt.most_common():
        print(f"{t:18s}{c:>10,d}{byt[t]:>12,d}{byt[t]/nbytes*100:>7.1f}%")
    ip = sum(cnt[t] for t in IP_TYPES)
    print(f"\n域名类 {len(domains):,} 条 / IP 类 {ip:,} 条")

    # ---- 冗余 ----
    uniq = sorted(set(domains))
    S = set(uniq)
    red = []
    for d in uniq:
        labs = d.split(".")
        for i in range(1, len(labs)):
            if ".".join(labs[i:]) in S:
                red.append(d)
                break
    print(f"去重后 {len(uniq):,} 条；被更短父后缀覆盖（可删）{len(red):,} 条"
          f"（{len(red)/max(len(uniq),1)*100:.3f}%）")

    # ---- 深度分布 ----
    depth = collections.Counter(d.count(".") for d in uniq)
    print(f"标签深度分布（0=顶级）: {dict(sorted(depth.items()))}")

    # ---- 加载与匹配 ----
    t0 = time.perf_counter()
    # 这一次读取只为了量「读盘耗时」，结果本身不参与后续计算 —— 因此不绑定变量。
    io.open(path, encoding="utf-8", errors="replace").read()
    t_read = time.perf_counter() - t0
    base = rss_mb()
    t0 = time.perf_counter()
    root, nodes = build_trie(uniq)
    t_build = time.perf_counter() - t0
    after = rss_mb()
    print(f"\n【加载】读 {t_read*1000:.0f} ms + 建索引 {t_build*1000:.0f} ms；trie 节点 {nodes:,}")
    if base is not None and after is not None:
        print(f"【内存·Python 口径】+{after-base:.1f} MB ⇒ 约 {(after-base)*1048576/max(len(uniq),1):.0f} B/条"
              f"（原生实现约再除以 2，即 ~130–175 B/条）")

    random.seed(7)
    probes = uniq[:5000]
    q = []
    for d in probes:
        q += [d, f"x9.{d}", f"a.b.{d}"]
    t0 = time.perf_counter()
    for x in q:
        lookup(root, x)
    dt = (time.perf_counter() - t0) / len(q) * 1e6
    print(f"【匹配】{len(q):,} 次查询 ⇒ {dt:.2f} µs/次（与表规模基本无关，O(标签数)）")

    # ---- 与对照小表的覆盖对比 ----
    if a.sub:
        small = load_table(a.sub)
        print(f"\n【覆盖对比】--sub {os.path.basename(a.sub)}："
              f"后缀 {len(small[0]):,} / 精确 {len(small[1]):,} / 关键词 {len(small[2])}，"
              f"{os.path.getsize(a.sub):,} B")
        missed_suf = small[0] - S
        print(f"  小表里有、大表里没有的后缀: {len(missed_suf):,} 条")
        sample = random.sample(uniq, min(5000, len(uniq)))
        cov = sum(1 for d in sample if hit(d, small))
        print(f"  从大表抽 {len(sample):,} 条，小表覆盖 {cov:,} 条（{cov/len(sample)*100:.1f}%）")
    probes = list(a.probe)
    if probes:
        big_table = (S, set(), [])
        print(f"\n【探针】{len(probes)} 个域名：")
        for d in probes:
            row = f"  {d:32s} 本表 {'✓' if hit(d, big_table) else '✗'}"
            if a.sub:
                row += f"   对照 {'✓' if hit(d, load_table(a.sub)) else '✗'}"
            print(row)


if __name__ == "__main__":
    main()
