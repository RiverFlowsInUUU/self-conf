#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自洽性检查 —— 整合仓不得引用原仓的在线资源。

为什么单独要这一项（整合最容易犯的错）：
    把两个仓的文件复制进一个新仓，文件是进来了，但**里面的 URL 还指着原仓**。
    表面上整合成功、门禁全绿，实际上新仓不自洽 —— 把原仓删了，
    图标全挂、规则集全空，而配置还能"正常加载"（远程集拉不到只是静默变空）。

    本仓踩过：整合后共 2511 处 URL 仍指向 Self-Configuration / Clash，
    其中图标 2311 处、规则集 200 处。

判据：
    · 扫描配置与脚本里的 http(s) URL
    · 出现原仓仓库名（Self-Configuration / Clash）即判负
    · 注释里的说明性文字（提及来源）不在扫描范围 —— 那是记录，不是引用
    · 上游第三方（MetaCubeX / blackmatrix7 / Jinx / TG-Twilight）放行

退出码：0 = 自洽 · 1 = 存在外部依赖
用法：python skill/tests/check_selfcontained.py [仓库根]
"""

import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

# 原仓仓库名 —— 出现即判负（整合仓必须自洽）
FORBIDDEN_REPOS = ("Self-Configuration", "RiverFlowsInUUU/Clash")

# 排除：说明性文字（注释里提及来源不算引用）
COMMENT_PREFIX = ("#", "//", ";")

EXTS = (".yaml", ".conf", ".js", ".list", ".txt", ".json", ".yml")
SKIP_DIRS = {".git", "__pycache__", "icons", "config_old"}

URL_RE = re.compile(r"https?://[^\s\"'`,)\]]+")


def scan(path):
    hits = []
    try:
        lines = open(path, encoding="utf-8").read().split("\n")
    except Exception:
        return hits
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # 跳过纯注释行
        if stripped.startswith(COMMENT_PREFIX):
            continue
        for m in URL_RE.finditer(line):
            u = m.group(0).rstrip(".,;")
            for repo in FORBIDDEN_REPOS:
                if repo in u:
                    hits.append((i, u))
                    break
    return hits


def main():
    print("自洽性检查 —— 整合仓不得引用原仓在线资源")
    print("-" * 78)
    bad = []
    for dp, dn, fs in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fs:
            if not f.endswith(EXTS):
                continue
            p = os.path.join(dp, f)
            for ln, u in scan(p):
                bad.append((os.path.relpath(p, ROOT), ln, u))

    if bad:
        print("外部依赖 %d 处（应改为指向本仓）：" % len(bad))
        for rel, ln, u in bad[:20]:
            print("  NG %s:%d" % (rel, ln))
            print("       %s" % u[:100])
        if len(bad) > 20:
            print("  ... 另 %d 处" % (len(bad) - 20))
        print("-" * 78)
        print("修法：把 URL 里的仓库名换成 self-conf，"
              "并确认对应文件已在本仓（icons/ 或 rules/）")
        return 1
    print("自洽 —— 配置与脚本均引用本仓资源")
    return 0


if __name__ == "__main__":
    sys.exit(main())
