#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把共享真源 `.list` 转成 mihomo 用的 `.yaml` 规则集。

为什么需要（合并项目的核心收益）：
    整合前，`Self-Configuration` 与 `Clash` 两仓各存一份相同内容的规则集，
    一份 `.list`（Surge / Egern 原生）、一份 `.yaml`（mihomo payload）。
    内容逐条相同（emby 4 / apple_system 18 / AI 272），只是格式不同 ——
    **双份维护，改一处忘一处就漂移**。

    合并后：`.list` 是唯一真源，本脚本生成 `.yaml`。单一真源，不可能漂移。

用法：
    python skill/scripts/clash/build_rules.py            # 生成
    python skill/scripts/clash/build_rules.py --check    # 只检查是否最新（CI 用）

退出码：0 = 成功 / 已是最新 · 1 = 生成物过期或缺失
"""

import os
import sys
import hashlib

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# (真源 .list, 产出 .yaml, 说明)
TARGETS = [
    ("emby.list", "emby.yaml", "Emby 自用枚举域名 → Emby 组"),
    ("apple_system.list", "apple_system.yaml", "Apple 系统域 → DIRECT"),
    ("AI.list", "AI_Domains.yaml", "AI 伴生域 → AI 组"),
]

HEADER = '''# %s
# ⚠️ 本文件由 build_rules.py **自动生成**，请勿手工编辑。
#    真源是同目录的 `%s`（共享于三内核），改内容请改真源后重跑：
#      python skill/scripts/clash/build_rules.py
#
# %s
#
# 条数：%d
# 格式：mihomo rule-provider（format: yaml / behavior: classical）
#
# ⚠️ 纯域名集、零 IP 条目 ⇒ 引用方**不写**规则级 no-resolve。
#########################################
'''


def read_rules(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def render(name, src_name, desc, rules):
    body = "payload:\n"
    for r in rules:
        body += "  - '%s'\n" % r.replace("'", "''")
    return HEADER % (name, src_name, desc, len(rules)) + "\n" + body


def main():
    check = "--check" in sys.argv
    src_dir = os.path.join(ROOT, "rules")
    stale = []

    for src, dst, desc in TARGETS:
        sp = os.path.join(src_dir, src)
        dp = os.path.join(src_dir, dst)
        if not os.path.exists(sp):
            print("  NG 真源缺失: rules/%s" % src)
            stale.append(src)
            continue
        rules = read_rules(sp)
        want = render(dst, src, desc, rules)
        have = open(dp, encoding="utf-8").read() if os.path.exists(dp) else None

        if have == want:
            print("  OK rules/%s ← %s (%d 条，已是最新)" % (dst, src, len(rules)))
        elif check:
            print("  NG rules/%s 已过期（真源 %s 有更新）" % (dst, src))
            stale.append(dst)
        else:
            open(dp, "w", encoding="utf-8", newline="\n").write(want)
            print("  ++ rules/%s ← %s (%d 条，已重新生成)" % (dst, src, len(rules)))

    if stale:
        print("\n有 %d 项需要处理" % len(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
