#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库路径定位 —— **全仓唯一实现**。

⚠️ 为什么不用 `dirname(dirname(__file__))` 上溯
────────────────────────────────────────────
那种写法依赖「本文件在第几层」。2026-10-08 重组目录
（`tools/run/` → `tools/run/` 等）时，全仓 48 处一次性失效，
且失效方式很隐蔽：**算错目录 ⇒ 报「找不到文件」**，
很容易被读成「配置有问题」而不是「定位坏了」。

改为**按标志物逐级上溯**：往上找同时含 `AGENTS.md` 与
`surge/profiles/routing.conf` 的目录 —— 那就是仓库根。
目录怎么移动都不会断。
"""
import os

# 仓库根的标志物（**两个都要有**，防误命中同名的子目录）
_MARKERS = (("AGENTS.md",), ("surge", "profiles", "routing.conf"))
_MAX_UP = 8


def repo_root(start=None):
    """仓库根绝对路径。找不到时抛 RuntimeError（**不猜**，宁可报错）。"""
    here = os.path.abspath(start or os.path.dirname(__file__))
    cur = here if os.path.isdir(here) else os.path.dirname(here)
    for _ in range(_MAX_UP):
        if all(os.path.exists(os.path.join(cur, *m)) for m in _MARKERS):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    raise RuntimeError(
        "找不到仓库根（向上找 %d 级都没有同时含 AGENTS.md 与 "
        "surge/profiles/routing.conf 的目录）。起点：%s" % (_MAX_UP, here))


def pkg_root(start=None):
    """本工具包根（即 `lib/` 的上一级，重组前的 `skill/`）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(start or __file__)))
