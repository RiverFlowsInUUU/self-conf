#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写死数字的新鲜度 —— 「文档里写的数字」必须与真源一致。

为什么有这个
────────────
本仓纪律是「组数/条数一律现抓」，但**纪律靠人记 = 会漂**。实测已漂过三次：
  · SECURITY.md 写「40 个图标」，实际 41（2026-10-08 发现）
  · SKILL.md 写「33 道判据」，实际 34（同一天发现，而且是在刚为"门禁数副本"
    加过判据之后又犯 —— 说明**靠改文档挡不住，必须机器守**）
  · 历史上还有 48/47/46/43/35 道的一串漂移

判据：扫描**人类面向的入口文件**（README / SECURITY / AGENTS / SKILL），
对**能现算的量**逐个核对：
  · 「N 个图标」      ⇔ `ls icons | wc -l`
  · 「N 道判据/闸门/门禁」 ⇔ `verify_all.py --index` 的道数
若不等 ⇒ 判负，并直接给出正确值（省得人去数）。

⚠️ 只查**指出具体数量的**表述；「全套闸门」「图标若干」这类**不写数字**的说法一律放行
—— 那正是本仓推荐的做法（避免副本）。

退出码：0 = 一致或无可核对项 · 1 = 有漂移 · 2 = 环境不达标
"""
import io
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# 面向人类的入口文件（AI 也要读，但它们常被手改，最容易漂）
SCAN = ["README.md", "SECURITY.md", "AGENTS.md",
        "self-conf-skills/SKILL.md", "clash/AGENTS.md"]

# 能现算的量：(正则, 现算函数, 量的名字)
ICON_N = re.compile(r"(\d+)\s*个\s*图标")
GATE_N = re.compile(r"(\d+)\s*道\s*(?:判据|闸门|门禁)")


def real_icons():
    d = os.path.join(ROOT, "icons")
    return len([f for f in os.listdir(d) if not f.startswith(".")]) if os.path.isdir(d) else None


def real_gates():
    p = os.path.join(ROOT, "self-conf-skills", "gates", "verify_all.py")
    try:
        r = subprocess.run([sys.executable, p, "--index"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           cwd=ROOT, timeout=60)
    except Exception:
        return None
    m = re.search(r"(\d+)\s*道", r.stdout)
    return int(m.group(1)) if m else None


def main():
    if not os.path.isdir(os.path.join(ROOT, "icons")):
        print("❌ 不在仓库根 —— 环境不达标")
        return 2

    icons, gates = real_icons(), real_gates()
    bad, checked = [], 0

    for rel in SCAN:
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        txt = io.open(p, encoding="utf-8").read()
        for i, ln in enumerate(txt.splitlines(), 1):
            m = ICON_N.search(ln)
            if m and icons is not None:
                checked += 1
                if int(m.group(1)) != icons:
                    bad.append("%s:%d 写「%s 个图标」，实际 **%d**"
                               % (rel, i, m.group(1), icons))
            m = GATE_N.search(ln)
            if m and gates is not None:
                checked += 1
                if int(m.group(1)) != gates:
                    bad.append("%s:%d 写「%s 道」，实际 **%d**"
                               % (rel, i, m.group(1), gates))

    print("写死数字的新鲜度（现算：图标 %s · 判据 %s 道）" % (icons, gates))
    print("-" * 78)
    if bad:
        for b in bad:
            print("  NG %s" % b)
        print("-" * 78)
        print("%d 处漂移 —— 本仓纪律是「数字一律现抓」，写死就会漂。"
              "改法：删掉数字（写「全套闸门」「图标若干」），或改成现抓命令" % len(bad))
        return 1
    print("  OK 核对了 %d 处数字，全部与真源一致" % checked)
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
