#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三内核 `#! version=` 头注规范检查。

守的规矩（见 tools/reference/ops.md）：
  V1 头注格式 `#! version=<产品线>_v<X.Y.Z>`（产品线 ∈ routing / lazy）
  V2 Surge 与 Egern 同一产品线**必须同号**（跨内核对拍的前提）
  V3 `.min` 版必须带与完整版**同一行**头注（对拍要求逐字节一致）
  V4 六个产品线（三内核 × routing/lazy）的完整版与 .min 都有头注

mihomo 是独立版本线，不参与 V2（不与 Surge/Egern 同号），但必须满足 V1 / V3 / V4。

⚠️ 2026-10-08 起（第三轮审查第 3 条）：三内核现役版本**统一为 v1.0.0**，
   这条不再适用 —— mihomo 的号必须与 Surge / Egern 一致。
   此前把 mihomo 头注改成 v9.9.9 后，本脚本、check_min_pair、
   clash/check_min_pair、build_profiles --check **全部 exit 0**（因为
   build_profiles 直接继承盘上头注）⇒ 「统一 v1.0.0」这个说法无人看守。
   现新增 V5 断言守它。

退出码：0 = 全部合规 · 1 = 有违规 · 2 = 环境/文件缺失（未验证，不是通过）
用法：python tools/gates/clash/check_version_header.py [仓库根]
"""

import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    ROOT = sys.argv[1]

VER_RE = re.compile(r"^#! version=(routing|lazy)_v(\d+)\.(\d+)(?:\.(\d+))?$")

# (内核, 产品线, 完整版相对路径, .min 相对路径)
FILES = [
    ("surge", "routing", "surge/profiles/routing.conf", "surge/profiles/routing.min.conf"),
    ("surge", "lazy", "surge/profiles/lazy.conf", "surge/profiles/lazy.min.conf"),
    ("egern", "routing", "egern/profiles/routing.yaml", "egern/profiles/routing.min.yaml"),
    ("egern", "lazy", "egern/profiles/lazy.yaml", "egern/profiles/lazy.min.yaml"),
    ("mihomo", "routing", "clash/profiles/routing.yaml", "clash/profiles/routing.min.yaml"),
    ("mihomo", "lazy", "clash/profiles/lazy.yaml", "clash/profiles/lazy.min.yaml"),
]


def head_line(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.readline().rstrip(chr(10))


def main():
    print("版本头注检查（三内核）")
    print("-" * 78)

    bad = 0
    missing = 0
    vers = {}          # (内核, 产品线) -> 完整版版本串

    for kern, fam, full_rel, min_rel in FILES:
        fp = os.path.join(ROOT, full_rel)
        mp = os.path.join(ROOT, min_rel)
        hl = head_line(fp)
        if hl is None:
            print("  ?? 缺文件: %s" % full_rel)
            missing += 1
            continue
        m = VER_RE.match(hl)
        if not m:
            print("  NG %s 头注不合规: %r" % (full_rel, hl[:60]))
            bad += 1
            continue
        if m.group(1) != fam:
            print("  NG %s 产品线不符（应为 %s）: %s" % (full_rel, fam, hl))
            bad += 1
            continue
        vers[(kern, fam)] = hl
        # V3 .min 必须同头注
        hm = head_line(mp)
        if hm is None:
            print("  ?? 缺 .min: %s" % min_rel)
            missing += 1
            continue
        if hm != hl:
            print("  NG %s 与完整版头注不一致" % min_rel)
            print("       完整版: %s" % hl)
            print("       .min  : %s" % hm)
            bad += 1
            continue
        print("  OK %-14s %s" % (kern + " " + fam, hl))

    # V2 Surge / Egern 同产品线必须同号（mihomo 独立版本线，不参与）
    for fam in ("routing", "lazy"):
        s = vers.get(("surge", fam))
        e = vers.get(("egern", fam))
        if s and e and s != e:
            print("  NG %s：Surge %s / Egern %s 不同号（跨内核对拍前提）" % (fam, s, e))
            bad += 1

    print("-" * 78)
    if missing:
        print("有 %d 个文件缺失 ⇒ 未验证，不是通过" % missing)
        return 2
    if bad:
        print("版本头注违规 %d 处" % bad)
        return 1
    print("合规 —— 三内核版本头注格式一致，Surge / Egern 同号，`.min` 与完整版一致")
    # ── V5：三内核版本统一（2026-10-08 起）
    #    Surge / Egern / mihomo 现役必须同号。此前无人守 ⇒ 改 mihomo 头注无人发现。
    # ⚠️ 2026-10-08 改革：原有一个 `UNIFIED_VERSION` 环境变量可覆盖这里的期望值
    #    —— 那是一个**多余的放行类后门**：三内核同号已由 check_min_pair 的 X1/X2
    #    硬性守住，无需一个可改期望值的开关。已删除，期望值写死为“三内核必须同号”。
    #    判据改为：读六个文件的头注，**彼此相等**即过（不再对着一个硬编码号比）。
    seen = {}
    for kern, path, key in (
        ("surge", "surge/profiles/routing.conf", "routing"),
        ("surge", "surge/profiles/lazy.conf", "lazy"),
        ("egern", "egern/profiles/routing.yaml", "routing"),
        ("egern", "egern/profiles/lazy.yaml", "lazy"),
        ("mihomo", "clash/profiles/routing.yaml", "routing"),
        ("mihomo", "clash/profiles/lazy.yaml", "lazy"),
    ):
        fp = os.path.join(ROOT, path.replace("/", os.sep))
        if not os.path.isfile(fp):
            continue
        with open(fp, encoding="utf-8") as fh:
            first = fh.readline().strip()
        m = re.match(r"^#!\s*version=\s*\S+?_v(.+?)\s*$", first)
        seen[(kern, key)] = ("v" + m.group(1)) if m else None

    unified_bad = []
    for fam in ("routing", "lazy"):
        vals = {kern: seen.get((kern, fam)) for kern in ("surge", "egern", "mihomo")}
        uniq = set(vals.values())
        if len(uniq) != 1 or None in uniq:
            unified_bad.append("%s：%s" % (fam, " / ".join(
                "%s=%s" % (k, v) for k, v in vals.items())))
    if unified_bad:
        print("  NG V5 三内核版本未统一：")
        for b in unified_bad:
            print("       %s" % b)
        return 1
    print("  OK V5 三内核版本统一（routing=%s · lazy=%s）"
          % (seen.get(("surge", "routing")), seen.get(("surge", "lazy"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
