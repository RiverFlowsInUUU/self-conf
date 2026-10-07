#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 Egern profile 里**远程规则集**的刷新参数（`update_interval`）。

与 Surge 侧的 `audit_ruleset_refresh.py` 是同一件事的**两份内核实现**，
判据相同、**依据并不相同** —— 这正是本脚本存在的意义：

    · Surge 手册写明 `update-interval` **缺省即 86400（24 小时）**，负值才关闭自动更新
      ⇒ 漏写只是"周期不可见"。
    · Egern 官方 `rules` 页只在 `rule_set` 的**示例**里出现过 `update_interval: 86400`，
      「规则集字段」一节只写了 `no_resolve` ⇒ **缺省行为未文档化**。
      不写就是"会不会刷新、多久刷新，都无从断言"。

所以本仓两侧都显式钉成 **604800（一周）**，判据分三档：

    HIGH    非正值（0 / 负数）—— 关闭或未知，属实质风险。
    约定    缺 `update_interval`、或值 ≠ 约定值。
            ⚠️ 缺字段在 Egern 侧比在 Surge 侧**严重**（那边缺省会正常按天刷新，这里未知），
               但历史版本（`lazy` / `routing_v1` ~ `routing_v2.3`）确实按当时的口径交付，
               故默认仍归入"约定"档、不改退出码；当前推荐版与懒人版用 `--strict` 守住。
    OK      全部等于约定值。

用法
----
    python audit_ruleset_refresh.py egern/profiles/routing.yaml
    python audit_ruleset_refresh.py egern/profiles/routing.yaml egern/profiles/lazy.yaml --strict

退出码：0 = 无 HIGH（且 --strict 下无约定偏离）；1 = 有；2 = 用法 / 文件读不到 / 解析失败。
"""
import argparse
import os
import sys
# 输出编码垫片：见 _egern_common.force_utf8_stdout —— GBK 控制台下 emoji 会崩成退出码 1
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _egern_common import force_utf8_stdout  # noqa: E402

import yaml

EXPECT_DEFAULT = 604800


def rule_type(r):
    """Egern 的一条 rule 是 {类型: {字段…}}；也兼容扁平写法。"""
    if not isinstance(r, dict):
        return None, {}
    if len(r) == 1:
        k = next(iter(r))
        v = r[k]
        if isinstance(v, dict):
            return k, v
    return r.get("type") or "rule_set", r


def audit(path, expect):
    doc = yaml.safe_load(open(path, encoding="utf-8")) or {}
    rules = [r for r in (doc.get("rules") or []) if isinstance(r, dict)]
    total, high, dev, good = 0, [], [], []
    for idx, r in enumerate(rules, 1):
        t, b = rule_type(r)
        if t != "rule_set":
            continue
        match = str(b.get("match") or "")
        if not match.startswith(("http://", "https://")):
            continue                      # 本地文件路径型规则集，不涉及下载刷新
        total += 1
        name = b.get("name") or match.split("/")[-1]
        tag = f"第 {idx} 条 rule_set `{name}`"
        if "update_interval" not in b:
            dev.append(f"{tag} —— 未写 update_interval。Egern 官方未文档化该字段的缺省值，"
                       f"不写 = 刷新行为不可断言（这是本仓坚持显式钉死的原因）")
            continue
        v = b.get("update_interval")
        try:
            v = int(v)
        except (TypeError, ValueError):
            high.append(f"{tag} —— update_interval={v!r} 不是整数秒")
            continue
        if v <= 0:
            high.append(f"{tag} —— update_interval={v} 为非正值。Egern 未文档化负值语义，"
                        f"最保守的解释即「不再自动更新」⇒ 规则集会停在已下载的版本")
        elif v != expect:
            dev.append(f"{tag} —— update_interval={v}，与本仓约定 {expect} 不同")
        else:
            good.append(tag)
    return total, high, dev, good


def main():
    ap = argparse.ArgumentParser(description="Egern 远程规则集刷新参数审计器")
    ap.add_argument("profile", nargs="+", help="Egern .yaml 文件路径（可多个）")
    ap.add_argument("--expect", type=int, default=EXPECT_DEFAULT,
                    help="本仓约定的刷新秒数（默认 604800 = 一周）")
    ap.add_argument("--strict", action="store_true", help="把「约定」档也算失败")
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
            print(f"\n📄 {path} —— 远程 rule_set {total} 条")
            for m in high:
                print(f"   🔴 HIGH  {m}")
            for m in dev:
                print(f"   🟡 约定   {m}")
            if not high and not dev:
                print(f"   ✅ {len(good)} 条全部显式带 update_interval={a.expect}（一周）")
        this = 1 if (high or (dev and a.strict)) else 0
        rc = max(rc, this)
        if a.quiet:
            print(f"{os.path.basename(path)}: {total} 条 · {len(high)} high · {len(dev)} 偏离约定")
    if rc == 0:
        print("\n✅ 通过" + ("（--strict）" if a.strict else ""))
    return rc


if __name__ == "__main__":
    sys.exit(main())
