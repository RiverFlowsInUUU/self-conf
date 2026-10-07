#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""闸门清单对账 —— CI 与 verify_all 跑的是不是同一套判据。

为什么需要
    `checker.md` §12.2 曾把「闸门清单靠人工双写（ci.yml ↔ verify_all.py）」
    记为**已知挂账**，靠人记得核对。本脚本把它变成机器判据：
    从 `ci.yml` 里现抓所有被直接调用的判据脚本，与 `verify_all.build_gates()`
    的清单比对，两边不一致即判负。

判据
    ① ci.yml 里 `python …/tests/…py` 形式的调用 ⇒ 必须在 verify_all 清单里
       （唯一豁免：`check_remote_urls.py` —— 慢，CI 独立 step，已登记在册）
    ② verify_all 列出的每一道 ⇒ 脚本文件必须真实存在（防死条目）
    ③ 未进任何闸门、也未登记在 §6.8.1 的判据脚本 ⇒ 报「既没跑也没记录」

退出码：0 = 一致 · 1 = 不一致
"""

import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CI = os.path.join(ROOT, ".github", "workflows", "ci.yml")

# 有意不在 verify_all 里的：CI 独立 step（慢 / 需真机），已在 ops.md §6.8.1 登记
KNOWN_SEPARATE = {"check_remote_urls.py": "CI 独立 step（慢，需联网探测数十个 URL）",
                  "check_real_kernel.py": "需真内核 + 真网络，仅本地人工跑（ops.md §6.8.1）",
                  "check_releases.py": ("本仓尚未发布过 Release ⇒ 暂不适用；"
                                        "首次发布后启用（release-rules.md §4 已在册）"),
                  "verify_all.py": "它自己就是总入口，不是被调的判据"}


def ci_invoked():
    """ci.yml 里被直接 `python <path>` 调用的判据脚本名集合。"""
    if not os.path.isfile(CI):
        return None
    names = set()
    for m in re.finditer(r"python\s+([A-Za-z0-9_/\.\-]+\.py)", open(CI, encoding="utf-8").read()):
        names.add(os.path.basename(m.group(1)))
    return names


def gate_scripts():
    """verify_all.build_gates() 里出现的判据脚本名集合（现抓，不手抄）。"""
    sys.path.insert(0, os.path.join(ROOT, "skill", "tests"))
    try:
        import verify_all
    except Exception as e:
        print("  NG 无法导入 verify_all：%s" % e)
        return None
    names = set()
    try:
        gates = verify_all.build_gates()
    except Exception as e:
        print("  NG build_gates() 失败：%s" % e)
        return None
    for _name, cmd, _env in gates:
        for tok in cmd:
            if tok.endswith(".py"):
                names.add(os.path.basename(tok))
    return names


def all_test_scripts():
    """判据目录 = skill/tests/**（含 clash 子目录）。

    ⚠️ 刻意**不扫 skill/scripts/**：那是审计 / 探测 / 生成工具区（人用的分析脚本，
    如 probe_doh.py、weigh_ruleset.py），不是判据。它们进不进闸门由人决定，
    不该被当成「漏跑的判据」批量报警 —— 2026-10-07 自查时试过全扫，假报 18 处。
    scripts/ 里的脚本若**确实被闸门引用**，由判据 ②（文件必须存在）兜底。
    """
    out = []
    root_d = os.path.join(ROOT, "skill", "tests")
    for dirpath, dirnames, filenames in os.walk(root_d):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "fixtures")]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            if fn in ("verify_all.py", "__init__.py") or fn.startswith("_"):
                continue
            out.append(os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/"))
    return out


def main():
    print("闸门清单对账（ci.yml ↔ verify_all）")
    print("-" * 78)
    ci = ci_invoked()
    ga = gate_scripts()
    if ci is None or ga is None:
        return 1

    bad = []

    # ① ci.yml 调用的，必须在 verify_all 里（豁免已登记的）
    for n in sorted(ci):
        if n in ga:
            continue
        if n in KNOWN_SEPARATE:
            print("  ⏭  %s —— 已登记为独立项：%s" % (n, KNOWN_SEPARATE[n]))
            continue
        bad.append("ci.yml 调用 %s，但它不在 verify_all 清单里" % n)

    # ② verify_all 列出的，文件必须存在
    for n in sorted(ga):
        found = False
        for base in ("tests", "scripts"):
            for dirpath, _d, filenames in os.walk(os.path.join(ROOT, "skill", base)):
                if n in filenames:
                    found = True
                    break
            if found:
                break
        if not found:
            bad.append("verify_all 列了 %s，但 skill/ 下找不到该文件" % n)

    # ③ 既没进闸门、也没登记的判据脚本
    for p in all_test_scripts():
        b = os.path.basename(p)
        if b in ga or b in ci:
            continue
        if b in KNOWN_SEPARATE:
            continue
        # 被别的判据 import 的模块（如 _clash_common）不算
        if b.startswith("_"):
            continue
        bad.append("%s 既不在 verify_all 也不在 ci.yml，且未登记 —— 它永远不会跑" % p)

    if bad:
        for b in bad:
            print("  NG %s" % b)
        print("-" * 78)
        print("不一致 %d 处" % len(bad))
        return 1
    print("  一致 —— ci.yml 与 verify_all 跑的是同一套判据（豁免项已逐条点名）")
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
