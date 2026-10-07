#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README badge 承诺数字 ↔ profiles 实抓对拍 —— 组数与规则数必须一致。

为什么单独要这一项：
    README 顶部的 `Groups 26|26` 与 `Rules 24|24` 是**承诺数字**：它向读者断言
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
    "Groups": re.compile(r"badge/Groups-(\d+)%20%7C%20(\d+)"),
    "Rules": re.compile(r"badge/Rules-(\d+)%20%7C%20(\d+)"),
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

    try:
        surge = (surge_section_count(surge_p, "[Proxy Group]"),
                 surge_section_count(surge_p, "[Rule]"))
        d = yaml.safe_load(open(egern_p, encoding="utf-8")) or {}
        egern = (len(d.get("policy_groups") or []),
                 len(d.get("rules") or []))
    except Exception as e:
        sys.stderr.write("profiles 解析失败：%s\n" % e)
        return 2

    bad = 0
    rows = [
        ("Groups", badges["Groups"], surge[0], egern[0]),
        ("Rules", badges["Rules"], surge[1], egern[1]),
    ]
    for kind, (bs, be), vs, ve in rows:
        ok = bs == vs and be == ve
        print("%s %s badge %d|%d  ↔  surge %d · egern %d"
              % ("✅" if ok else "❌", kind, bs, be, vs, ve))
        if not ok:
            print("   改 README badge，或确认实抓口径（surge 段计数 / egern 数组长度）")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
