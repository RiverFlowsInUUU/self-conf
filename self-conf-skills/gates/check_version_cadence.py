#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「一天一版」节奏判据 —— 同一自然日内同一产品线只应升一次号。

为什么要有这一项（2026-10-10 补）
─────────────────────────────────
`ops.md` §2 规定「一天一版：一天内改几次都只升一次号，当天后续改动沿用同号」。
改革删掉归档快照后，原本守它的 V7 断言一并删除 ⇒ 此后**没有任何机器在守它**
（`ops.md` §6.1 与 `gates.md` §16.4 第 4 条都如实登记了这一点，措辞是
「靠纪律」「没有机器守它」）。

⇒ 风险形态：同一天把 `lazy_v1.0.1` 改成 `v1.0.2`、再改成 `v1.0.3`，
   没有任何东西会叫 —— 而这会让用户看到「一天内出现三个版本」，
   且 Release 的一天一版模型（tag = `vYYYY-MM-DD`）也无法表达它们。

判据
────
扫 `git log` 的头注版本号变更（`#! version=<fam>_v<X.Y.Z>`），按
**（产品线, 提交日期）** 分组，要求：同一组内**不同的版本号至多一个**。

⚠️ 刻意**不判**「同一天必须升号」—— 只改注释/文档的日子**不该**升号
   （§2 的表格明说），要求每天都必须升号会逼人乱升。
   本判据只管「一天内不许升多次」这个上界。

⚠️ 只看**现役 12 个头注文件**的版本行，不看别的含 `vX.Y.Z` 的文本 ——
   否则会把文档里的示例数字、历史叙述也算成升号（误报）。

退出码：0 = 全过（或不适用）· 1 = 同一天升了多次号 · 2 = 环境不达标（不是 git 仓库）
"""
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_d = os.path.dirname(os.path.abspath(__file__))
for _c in (os.path.join(_d, "..", "lib"), _d):
    _c = os.path.normpath(_c)
    if os.path.isfile(os.path.join(_c, "paths.py")):
        sys.path.insert(0, _c)
        break
from paths import repo_root  # noqa: E402

VER_RE = re.compile(r"^#! version=(routing|lazy)_v(\d+)\.(\d+)\.(\d+)\s*$")

# 现役 12 个头注文件（三内核 × 两产品线 × 完整版/.min）
HEADER_FILES = [
    "surge/profiles/routing.conf", "surge/profiles/routing.min.conf",
    "surge/profiles/lazy.conf", "surge/profiles/lazy.min.conf",
    "egern/profiles/routing.yaml", "egern/profiles/routing.min.yaml",
    "egern/profiles/lazy.yaml", "egern/profiles/lazy.min.yaml",
    "clash/profiles/routing.yaml", "clash/profiles/routing.min.yaml",
    "clash/profiles/lazy.yaml", "clash/profiles/lazy.min.yaml",
]


def git(root, *a):
    return subprocess.check_output(["git", *a], cwd=root, encoding="utf-8",
                                   errors="replace", stderr=subprocess.DEVNULL)


def main():
    root = repo_root()
    try:
        git(root, "rev-parse", "--git-dir")
    except Exception:
        print("❌ 前置不达标：不是 git 仓库")
        return 2

    # 每条提交：日期 + 它对头注文件里版本行的改动（新增的版本值）
    # ⚠️ 用 `-z` 之外最稳的做法：**逐条提交单独查**，避免解析 diff 正文里的
    #    `@@` 与 `+` 行混入（第一版一次性解析 `git log --unified=0` 的输出，
    #    被 hunk 头 `@@ -1 +1 @@` 干扰 ⇒ `split("|")` 解包失败，实测崩过）。
    try:
        shas = git(root, "log", "--format=%h|%as", "--", *HEADER_FILES).splitlines()
    except subprocess.CalledProcessError as e:
        print("❌ 前置不达标：git log 失败 %s" % e)
        return 2

    day_versions = {}          # (fam, date) -> {version: [shas]}
    for entry in shas:
        if "|" not in entry:
            continue
        sha, date = entry.split("|", 1)
        try:
            diff = git(root, "show", "--unified=0", "--format=", sha, "--",
                       *HEADER_FILES)
        except subprocess.CalledProcessError:
            continue
        for ln in diff.splitlines():
            if ln.startswith("+") and not ln.startswith("+++"):
                m = VER_RE.match(ln[1:].strip())
                if m:
                    fam = m.group(1)
                    ver = "%s.%s.%s" % (m.group(2), m.group(3), m.group(4))
                    day_versions.setdefault((fam, date), {}).setdefault(
                        ver, []).append(sha)

    ok, bad = [], []
    for (fam, date), vers in sorted(day_versions.items()):
        if len(vers) > 1:
            detail = " · ".join("%s(%s)" % (v, ",".join(s[:7] for s in shas))
                                for v, shas in sorted(vers.items()))
            bad.append("%s %s：同一天升了 %d 个号 —— %s"
                       % (date, fam, len(vers), detail))
        else:
            v = list(vers)[0]
            ok.append("%s %s：v%s（单次）" % (date, fam, v))

    for m in ok:
        print("  ✅ %s" % m)
    for m in bad:
        print("  ❌ %s" % m)
    print("\nTOTAL: %d passed, %d failed" % (len(ok), len(bad)))
    if bad:
        print("   规矩见 self-conf-skills/references/ops.md §2："
              "一天一版，当天后续改动**沿用同号**（不重复升号）。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
