#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一屏现状 —— 开工摸底：一次工具调用拿到「现役版本 + Release + CI」。

为什么存在：
    「现在是什么状态」在仓里没有单一落点：版本号写在 6 个现役文件头注里、
    最新 Release / CI 结论要调 GitHub。AI 每个任务开工都要花几次工具调用摸底
    —— 本脚本一次输出全部。它是**只读实时计算**，不维护任何状态文件。

用法：
    python skill/scripts/repo_state.py          # 人读表格
    python skill/scripts/repo_state.py --json   # 机读 JSON
"""
import json
import os
import re
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACTIVE = {
    ("surge", "lazy"): "surge/profiles/lazy.conf",
    ("surge", "routing"): "surge/profiles/routing.conf",
    ("egern", "lazy"): "egern/profiles/lazy.yaml",
    ("egern", "routing"): "egern/profiles/routing.yaml",
    ("clash", "lazy"): "clash/profiles/lazy.yaml",
    ("clash", "routing"): "clash/profiles/routing.yaml",
}
VER_RE = re.compile(r"#!\s*version=(\S+)")


def _git(*args):
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else None


def _gh(*args):
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def collect():
    state = {"active_versions": {}, "release": None, "ci": None}

    for (kern, fam), rel in ACTIVE.items():
        p = os.path.join(ROOT, rel)
        m = VER_RE.match(open(p, encoding="utf-8").readline()) if os.path.exists(p) else None
        state["active_versions"]["%s-%s" % (kern, fam)] = \
            m.group(1).split("_", 1)[-1] if m else None

    remote = _git("remote", "get-url", "origin") or ""
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
    if m:
        rel = _gh("api", "repos/%s/releases/latest" % m.group(1),
                  "--jq", "{tag: .tag_name, name: .name, published: .published_at}")
        state["release"] = json.loads(rel) if rel else None

    ci = _gh("run", "list", "--limit", "1", "--json", "status,conclusion,displayTitle",
             "--jq", ".[0]")
    state["ci"] = json.loads(ci) if ci else None
    return state


def render(state):
    a = state["active_versions"]
    print("══ 现役版本（三内核 × 两产品线，各自必须同号）══")
    for fam in ("lazy", "routing"):
        row = "  ".join("%-7s %s" % (k, a.get("%s-%s" % (k, fam)) or "-")
                        for k in ("surge", "egern", "clash"))
        print("  %-8s %s" % (fam, row))
    r = state["release"]
    print("══ 发布层 ══")
    if r:
        print("  最新 Release：%s　%s　(%s)" % (r["tag"], r["name"], r["published"][:10]))
    else:
        print("  最新 Release：未知（gh 不可用或未发布）")
    c = state["ci"]
    if c:
        print("  CI：%s / %s　%s" % (c.get("status"), c.get("conclusion") or "-",
                                     c.get("displayTitle", "")[:44]))
    print("══ 提示 ══")
    print("  跑 python skill/tests/verify_all.py 验证（与 CI 同源）；本脚本只报现状。")


def main():
    state = collect()
    if "--json" in sys.argv:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        render(state)


if __name__ == "__main__":
    main()
