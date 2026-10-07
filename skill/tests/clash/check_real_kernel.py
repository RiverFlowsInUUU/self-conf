#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真机验证：用**真实的 mihomo 内核**加载配置，确认它能被接受。

为什么单独要这一项：
    前面所有门禁都是「我们自己的判据」，判的是我们**认为**正确的东西。
    门禁全绿 ≠ 真实内核能加载 —— 语法错、键名错、provider 形态错，
    只有真内核才判得出来。本仓此前**从未用真机验证过**（这是成熟度上
    最后一块缺口）。

    2026-10-07 实测：mihomo Meta alpha-9f053c4 加载四份配置全部
    `test is successful`（分流版 / 懒人版 / .min 版 / 脚本输出形态）。

做法：
    找 mihomo 二进制（`-b` 指定，或 PATH/常见位置找），跑 `mihomo -t -f <profile>`。
    找不到二进制 ⇒ 退出码 2（**未验证**，不是通过）—— 不能假绿。

用法：
    python skill/tests/clash/check_real_kernel.py                     # 自动找二进制
    python skill/tests/clash/check_real_kernel.py -b /path/to/mihomo  # 指定
    python skill/tests/clash/check_real_kernel.py -b <bin> <profile>… # 指定配置

退出码：0 = 全部被真核接受 · 1 = 有配置被拒 · 2 = 无二进制/参数问题（未验证）
"""

import os
import sys
import subprocess
import argparse
import shutil

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件在 skill/tests/clash/ 下 ⇒ 仓库根是往上 4 级
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if os.path.isdir(os.path.join(ROOT, "clash", "profiles")):
    CLASH = os.path.join(ROOT, "clash")     # 整合仓布局
else:
    CLASH = ROOT                            # 单仓布局

DEFAULT_PROFILES = [
    "profiles/routing.yaml",
    "profiles/routing.min.yaml",
    "profiles/lazy.yaml",
    "profiles/lazy.min.yaml",
]

# 常见的二进制名
CANDIDATES = ("mihomo", "mihomo.exe", "clash", "clash.exe",
              "mihomo-windows-amd64-compatible.exe")


def find_binary(explicit=None):
    if explicit:
        if os.path.exists(explicit):
            return explicit
        return None
    for c in CANDIDATES:
        p = shutil.which(c)
        if p:
            return p
    # 常见安装位置
    extra = [
        os.path.join(os.path.dirname(sys.executable), "mihomo.exe"),
        os.path.join(os.path.expanduser("~"), "scoop", "shims", "mihomo.exe"),
    ]
    for p in extra:
        if os.path.exists(p):
            return p
    return None


def run(binary, profile):
    """跑 mihomo -t -f；返回 (ok, 输出摘要)"""
    cmd = [binary, "-t", "-f", profile]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        return (False, "超时（180s）")
    except Exception as e:
        return (False, "执行异常: %s" % type(e).__name__)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "test is successful" in out
    # 抽取关键行
    tail = [l for l in out.strip().split("\n") if l.strip()][-1:] or [""]
    return (ok, tail[0][:160])


def main():
    ap = argparse.ArgumentParser(description="用真实 mihomo 内核校验配置能否加载")
    ap.add_argument("-b", "--binary", help="mihomo 二进制路径（不传则自动找）")
    ap.add_argument("profiles", nargs="*", help="要验的配置（默认验四份）")
    args = ap.parse_args()

    print("真机验证（真实 mihomo 内核加载测试）")
    print("-" * 78)

    binary = find_binary(args.binary)
    if not binary:
        print("  未找到 mihomo 二进制 ⇒ 未验证，不是通过")
        print("  修法：-b 指定路径，或把 mihomo 放进 PATH")
        print("-" * 78)
        return 2
    print("  内核: %s" % binary)

    profiles = args.profiles or [os.path.join(CLASH, p) for p in DEFAULT_PROFILES]
    bad = 0
    for p in profiles:
        if not os.path.exists(p):
            print("  NG 文件不存在: %s" % p)
            bad += 1
            continue
        ok, note = run(binary, p)
        name = os.path.basename(p)
        if ok:
            print("  OK %s —— 真核接受" % name)
        else:
            bad += 1
            print("  NG %s —— 真核拒绝" % name)
            print("       %s" % note)

    print("-" * 78)
    if bad:
        print("%d 份未被真核接受" % bad)
        return 1
    print("全部被真核接受 —— 配置可行性已验证")
    return 0


if __name__ == "__main__":
    sys.exit(main())
