#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README badge 承诺数字 ↔ profiles 实抓对拍 —— 组数与规则数必须一致。

为什么单独要这一项：
    README 顶部的 `Groups 23|23|25` 与 `Rules 26|26|27` 是**承诺数字**：它向读者断言
    "两侧分流版的组数相同、规则条数相同"。其余承诺都有闸门兜底（min 对拍、头注
    版本、归档序列、DNS 审计），唯独这两个数字过去靠人肉维护 —— 配置增删了组或
    规则而忘改 badge，页面就静默地说谎，而且没有任何检查会红。

判据（与人工核对时的口径一致）：
    · Surge：`routing.conf` 的 `[Proxy Group]` / `[Rule]` 段内非注释、非空行数
    · Egern：`routing.yaml` 的 `policy_groups` / `rules` 数组长度（PyYAML 解析）
    · badge：正则抽 `badge/Groups-<s>%20%7C%20<e>` 与 `badge/Rules-<s>%20%7C%20<e>`
    四个数两两对拍（surge↔badge、egern↔badge），任何一侧对不上即判负。

退出码：0 = 全部一致 · 1 = 有不一致 · 2 = 文件缺失或解析失败。
用法：python skill/tests/check_badges.py [仓库根]     # 默认取本文件所在的仓库根
"""

import os
import re
import sys

# Windows 中文环境的控制台与管道默认 GBK(cp936)：emoji 一 print 就 UnicodeEncodeError、
# 进程以退出码 1 结束 —— 与"期望判负"的用例撞码会假绿。统一钉成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import yaml  # CI 已装（ci.yml: pip install pyyaml）

BADGE_RE = {
    "Groups": re.compile(r"badge/Groups-(\d+)%20%7C%20(\d+)(?:%20%7C%20(\d+))?"),
    "Rules": re.compile(r"badge/Rules-(\d+)%20%7C%20(\d+)(?:%20%7C%20(\d+))?"),
}


def surge_section_count(path, section):
    """[section] 段内非注释、非空行数；遇到下一个段标题即停计。"""
    sec, n = None, 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("["):
                sec = s
                continue
            if sec != section or not s or s.startswith("#"):
                continue
            n += 1
    return n


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = os.path.abspath(root)
    readme = os.path.join(root, "README.md")
    surge_p = os.path.join(root, "surge", "profiles", "routing.conf")
    egern_p = os.path.join(root, "egern", "profiles", "routing.yaml")
    for p in (readme, surge_p, egern_p):
        if not os.path.isfile(p):
            sys.stderr.write("找不到 %s —— 参数应当是仓库根（本仓自身）\n" % p)
            return 2

    try:
        text = open(readme, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write("读取失败 README.md：%s\n" % e)
        return 2

    badges = {}
    for kind, rx in BADGE_RE.items():
        m = rx.search(text)
        if not m:
            print("❌ README 未找到 %s badge（正则 %s）" % (kind, rx.pattern))
            return 1
        badges[kind] = tuple(int(x) for x in m.groups())

    # 三个内核的实际规模（顺序：Surge · Egern · mihomo）
    # ⚠️ 本脚本原只比对 surge / egern 两个 —— mihomo 那两个数**从未被校验**，
    #    而文件头声称「组数与规则数必须一致」。2026-10-07 补上 mihomo。
    clash_p = os.path.join(root, "clash", "profiles", "routing.yaml")
    try:
        surge = (surge_section_count(surge_p, "[Proxy Group]"),
                 surge_section_count(surge_p, "[Rule]"))
        d = yaml.safe_load(open(egern_p, encoding="utf-8")) or {}
        egern = (len(d.get("policy_groups") or []),
                 len(d.get("rules") or []))
        clash = None
        if os.path.isfile(clash_p):
            dc = yaml.safe_load(open(clash_p, encoding="utf-8")) or {}
            clash = (len(dc.get("proxy-groups") or []),
                     len(dc.get("rules") or []))
    except Exception as e:
        # ⚠️ 2026-10-08 第十五轮：此处原写 `+ NL`，而本文件**从未定义过 `NL`**
        #    ⇒ 一旦真的走到这个分支（profiles 解析失败），先炸 `NameError` 而不是
        #    返回 2。后果比"崩溃"更糟：
        #      · 本意是 2（前置环境不达标 —— 先修环境，别读判据）
        #      · 实际退出码变成 1（**判负**）
        #    ⇒ 环境坏了被读成"判据判负"，正是本仓全仓在防的那件事。
        #    与 `check_script_sync.py` 的 `diff` 未定义是**同一类** bug（只在异常/判负
        #    路径上才炸，现役恒好时永远潜伏）。
        #    现由 `skill/tests/check_undefined_names.py` 常驻守着（已接进 verify_all）。
        sys.stderr.write("profiles 解析失败" + chr(58) + " " + str(e) + chr(10))
        return 2

    kernels = [("surge", surge), ("egern", egern)]
    if clash:
        kernels.append(("mihomo", clash))
    bad = 0
    for kind in ("Groups", "Rules"):
        idx = 0 if kind == "Groups" else 1
        want = badges[kind]
        got = tuple(v[idx] for _n, v in kernels)
        ok = want == got
        line = (("OK " if ok else "NG ") + kind + " badge "
                + "|".join(str(x) for x in want)
                + "  " + chr(8596) + "  "
                + " - ".join(str(n) + " " + str(v[idx]) for n, v in kernels))
        print(line)
        if not ok:
            bad += 1

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
