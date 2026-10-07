#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""".min 与完整版对拍 —— 去掉注释与空行后，配置本体必须逐字相同。

为什么单独要这一项：
    每份 profile 都有两份形态（`.yaml` / `.min.yaml`）。`.min` 的定位是
    **同一份配置去掉注释**，不是"裁剪配置"。一旦两版的配置本体漂移，
    照着文档改完整版、实际导入的却是 `.min` ⇒ 改了个寂寞，而且肉眼看不出来。

    本仓踩过：`routing.yaml` 由脚本重新生成后，若忘了同步重生成 `.min`，
    两份就会不一致，而静态文件不会报错。

判据（与人工核对时的口径一致）：
    · 用 YAML 解析两侧成 Python 对象后**直接比对象** —— 这样注释、键顺序、
      缩进、引号风格都不影响判定，只看配置本体
    · 任何一处不同即判负

退出码：0 = 全部成对相同 · 1 = 有不一致 · 2 = 目录/解析问题
用法：python skill/tests/check_min_pair.py [仓库根]
"""

import os
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
except ImportError:
    print("需要 pyyaml：pip install pyyaml")
    sys.exit(2)

def _default_root():
    # 本文件在 skill/tests/clash/ 下 → 仓库根是往上 4 级
    r = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    if os.path.isdir(os.path.join(r, "clash", "profiles")):
        return os.path.join(r, "clash")
    return r

ROOT = sys.argv[1] if len(sys.argv) > 1 else _default_root()

PAIRS = [
    ("profiles/lazy.yaml", "profiles/lazy.min.yaml"),
    ("profiles/routing.yaml", "profiles/routing.min.yaml"),
]


def diff(a, b, path=""):
    """递归比对两个对象，返回差异描述列表。"""
    out = []
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append("%s 类型不同: %s vs %s" % (path, type(a).__name__, type(b).__name__))
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append("%s.%s 仅 min 有" % (path, k))
            elif k not in b:
                out.append("%s.%s 仅完整版有" % (path, k))
            else:
                out.extend(diff(a[k], b[k], "%s.%s" % (path, k)))
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s 长度不同: %d vs %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff(x, y, "%s[%d]" % (path, i)))
    else:
        if a != b:
            out.append("%s 值不同: %r vs %r" % (path, a, b))
    return out


def main():
    print("min / 完整版对拍")
    print("-" * 78)
    bad = 0
    for full, mini in PAIRS:
        pf, pm = os.path.join(ROOT, full), os.path.join(ROOT, mini)
        if not os.path.exists(pf):
            print("  NG %s 不存在" % full)
            bad += 1
            continue
        if not os.path.exists(pm):
            print("  NG %s 不存在" % mini)
            bad += 1
            continue
        try:
            a = yaml.safe_load(open(pf, encoding="utf-8"))
            b = yaml.safe_load(open(pm, encoding="utf-8"))
        except Exception as e:
            print("  NG %s 解析失败: %s" % (full, e))
            bad += 1
            continue
        d = diff(a, b)
        if d:
            bad += 1
            print("  NG %s vs %s —— %d 处差异" % (full, mini, len(d)))
            for line in d[:10]:
                print("       ", line)
            if len(d) > 10:
                print("        ... 另 %d 处" % (len(d) - 10))
        else:
            print("  OK %s" % full)
    print("-" * 78)
    if bad:
        print("不一致 %d 对" % bad)
        return 1
    print("全部成对一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
