#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 Surge profile 里**远程规则集**的刷新参数（`update-interval`）。

为什么单独有这一个脚本
----------------------
「规则集到底多久刷新一次」此前**不在任何审计的覆盖范围内** —— 全仓脚本一个都没看过这个键。
于是出现过这样一轮：文档把判据写成「不显式写 `update-interval`，规则集就会停在首次下载的版本」，
而 profile 里有 5 条远程规则集确实没写 ⇒ 被报成"高危疏漏"。

⭐ **那个因果是错的。** Surge 手册对 `RULE-SET` 的 `update-interval` 写得很明确：
    Re-download interval for the external resource. **Default: 86400 (24 hours).
    A negative value disables auto-updating.**
⇒ **漏写不会停止刷新**，只是让周期不可见（并且与 Egern 侧不同构 ——
   Egern 才是真正**未文档化缺省值**的那一侧，那里必须显式写）。

所以本脚本的判据分三档，各按各的事实定级：

    HIGH    显式写了**负值或 0** —— 这是主动关掉自动更新（Surge 手册：负值即禁用）。
            真的会造成"规则集停在旧版"的只有这一种写法。
    约定    与**本仓约定值**（默认 604800 = 一周）不一致：缺字段、或写的是别的秒数。
            默认只报不改退出码 —— 历史版本按当时的口径交付，不算错。
            加 `--strict` 后这一档也算失败，用于守当前推荐版与懒人版。
    OK      全部等于约定值。

用法
----
    python audit_ruleset_refresh.py surge/profiles/routing.conf
    python audit_ruleset_refresh.py surge/profiles/routing.conf --strict
    python audit_ruleset_refresh.py Profile.conf --expect 86400    # 换约定值

退出码：0 = 无 HIGH（且 --strict 下无约定偏离）；1 = 有；2 = 用法 / 文件读不到。
"""
import argparse
import os
import re
import sys
# 输出编码垫片：见 _surge_common.force_utf8_stdout —— GBK 控制台下 emoji 会崩成退出码 1
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _surge_common import force_utf8_stdout  # noqa: E402

# RULE-SET / DOMAIN-SET 的远程条目；[Proxy Group] 的 policy-path 用别的键，不在此列。
REMOTE = re.compile(r"^(?:RULE-SET|DOMAIN-SET),\s*(https?://[^,\s]+)")
INTERVAL = re.compile(r"""['"]?\bupdate-interval=(-?\d+)\b['"]?""")


def audit(path, expect):
    """返回 (total, high, dev, ok_tags)。"""
    high, dev, good = [], [], []
    total = 0
    for lineno, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.strip()
        if not REMOTE.match(line):
            continue
        total += 1
        m = INTERVAL.search(line)
        tag = f"第 {lineno} 行 {line[:60]}…"
        if not m:
            dev.append(f"{tag} —— 未写 update-interval"
                       f"（Surge 缺省 86400 仍会刷新，只是周期在文件里不可见、与 Egern 侧不同构）")
            continue
        v = int(m.group(1))
        if v <= 0:
            high.append(f"{tag} —— update-interval={v} 是**非正值**，"
                        f"按手册即关闭自动更新 ⇒ 规则集会停在已下载的版本")
        elif v != expect:
            dev.append(f"{tag} —— update-interval={v}，与本仓约定 {expect} 不同")
        else:
            good.append(tag)
    return total, high, dev, good


def main():
    ap = argparse.ArgumentParser(description="Surge 远程规则集刷新参数审计器")
    ap.add_argument("profile", nargs="+", help="Surge .conf 文件路径（可多个）")
    ap.add_argument("--expect", type=int, default=604800,
                    help="本仓约定的刷新秒数（默认 604800 = 一周）")
    ap.add_argument("--strict", action="store_true",
                    help="把「与约定值不一致 / 未写」也算失败（当前推荐版与懒人版用这条）")
    ap.add_argument("--quiet", action="store_true", help="只打印计数")
    a = ap.parse_args()

    rc = 0
    for path in a.profile:
        if not os.path.isfile(path):
            print(f"❌ 找不到文件：{path}", file=sys.stderr)
            rc = max(rc, 2)
            continue
        try:
            total, high, dev, good = audit(path, a.expect)
        except Exception as e:                                  # noqa: BLE001
            print(f"❌ 解析失败：{path}: {e}", file=sys.stderr)
            rc = max(rc, 2)
            continue
        if not a.quiet:
            print(f"\n📄 {path} —— 远程规则集 {total} 条")
            for m in high:
                print(f"   🔴 HIGH  {m}")
            for m in dev:
                print(f"   🟡 约定   {m}")
            if not high and not dev:
                print(f"   ✅ {len(good)} 条全部显式带 update-interval={a.expect}"
                      f"（{'一周' if a.expect == 604800 else str(a.expect) + ' 秒'}）")
        this = 0
        if high:
            this = 1
        elif dev and a.strict:
            this = 1
        rc = max(rc, this)
        if a.quiet:
            print(f"{os.path.basename(path)}: {total} 条 · {len(high)} high · {len(dev)} 偏离约定")
    if rc == 0:
        print("\n✅ 通过" + ("（--strict）" if a.strict else ""))
    return rc


if __name__ == "__main__":
    sys.exit(main())
