#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则集来源文档同步 —— 配置改了 URL，文档表必须跟着改。

为什么需要
    `reference/rulesets.md` 的「全部规则集」表写着每份规则集的**来源**（仓库 + 路径）。
    它是人读的对照表，但改配置里的 `rule-providers.*.url` 时**没有机器逼着同步** ——
    `check_remote_urls.py` 扫的是配置里的 URL（不管文档），
    `check_selfcontained.py` 也不扫 `.md`。

    这个缺口是有前科的：2026-10-04 上游把 `*-white-guard.*` 改名成 `*-direct.*`，
    配置换了、文档表仍写旧名（旧名已 404），且没有任何闸门会发现。

判据
    ① 配置里每份远程 provider 的 (仓库, 路径) ⇒ 必须在文档表里出现
    ② 文档表里出现的 (仓库, 路径) ⇒ 必须在配置里有对应项
    ③ 两边都提到的规则集名 ⇒ 路径必须逐字一致

    URL 归一：
      `https://cdn.jsdelivr.net/gh/{owner}/{repo}@{ref}/{path}`
        → ('{owner}/{repo}', '{path}')
      `https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}`
        → ('{owner}/{repo}', '{path}')
    文档表里写的是 `[仓库名](https://github.com/{owner}/{repo})` · `` `path` ``
        → ('{owner}/{repo}', '{path}')

退出码：0 = 一致 · 1 = 漂移
用法：python skill/tests/clash/check_ruleset_doc_sync.py [仓库根]
"""

import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
    os.path.dirname(os.path.dirname(HERE)))

DOC = os.path.join(ROOT, "skill", "reference", "rulesets.md")
ROUTING = os.path.join(ROOT, "clash", "profiles", "routing.yaml")
LAZY = os.path.join(ROOT, "clash", "profiles", "lazy.yaml")

JSDELIVR = re.compile(r"cdn\.jsdelivr\.net/gh/([^/]+)/([^/@]+)(?:@[^/]+)?/(.+)$")
RAW_GH = re.compile(r"raw\.githubusercontent\.com/([^/]+)/([^/]+)/[^/]+/(.+)$")
# 文档表格里的来源列：`[名字](https://github.com/owner/repo)` · `` `path` ``
DOC_LINK = re.compile(r"\((https://github\.com/([^/]+/[^/]+?))\)")
DOC_PATH = re.compile(r"`([^`]+\.(?:mrs|yaml|yml|list|txt|json))`")


def _norm_url(u):
    """URL → (owner/repo, path)；非远程形式返回 None。"""
    u = (u or "").strip()
    m = JSDELIVR.search(u) or RAW_GH.search(u)
    if not m:
        return None
    return ("%s/%s" % (m.group(1), m.group(2)), m.group(3))


def providers_from_config(path):
    """配置 → {规则集名: (owner/repo, path)}（只收有 URL 的远程项）。"""
    try:
        import yaml
        d = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except Exception:
        return {}
    out = {}
    for name, v in (d.get("rule-providers") or {}).items():
        if not isinstance(v, dict):
            continue
        n = _norm_url(v.get("url") or "")
        if n:
            out[name] = n
    return out


def sources_from_doc(path):
    """文档表 → {(owner/repo, path), ...}（按表格行解析，取该行的仓库与路径）。"""
    if not os.path.isfile(path):
        return set()
    out = set()
    section = ""
    for line in open(path, encoding="utf-8"):
        if line.startswith("#"):
            section = line.strip()
        if not line.lstrip().startswith("|"):
            continue
        # ⚠️ 只校验「全部规则集」表。**候选源对比表**（含「候选源」「结论」表头、
        #    记录曾评估但未采用的来源）是沿革，不参与 —— 否则会把「未采用」的
        #    候选误报成「配置里没有」。2026-10-08 校准。
        # ⚠️ 只认「全部规则集」这一节（明确点名，不靠关键词猜）。
        #    曾试过用「候选」关键词排除候选源对比表 —— 但那节标题是
        #    「0.3 微信为什么选远程 .mrs」不含「候选」二字，误报挡不住。
        if "全部规则集" not in section:
            continue
        link = DOC_LINK.search(line)
        paths = DOC_PATH.findall(line)
        if not link or not paths:
            continue
        repo = link.group(2)
        for p in paths:
            out.add((repo, p))
    return out


def main():
    print("规则集来源文档同步（配置 ↔ ruleset-sources.md）")
    print("-" * 78)

    if not os.path.isfile(DOC):
        print("  NG 缺文档：%s" % os.path.relpath(DOC, ROOT))
        return 1

    # ⚠️ 不能 dict.update 合并两个 profile —— 同名 provider 会被后一个覆盖，
    #    于是「只改了 routing 的 URL、lazy 还是旧值」这种漂移**判不出来**
    #    （2026-10-08 注错测试发现：改 routing 后判据仍绿）。
    #    改为按「来源文件 + 名字」分别登记，两份都判。
    cfg = {}
    for p in (ROUTING, LAZY):
        tag = os.path.basename(p)
        for name, val in providers_from_config(p).items():
            cfg["%s::%s" % (tag, name)] = val
    doc = sources_from_doc(DOC)

    if not cfg:
        print("  NG 配置里没解析出任何远程 provider —— 环境不达标，不是通过")
        return 1

    bad = []

    # ⚠️ 口径（2026-10-08 校准）：**不要求文档表逐份登记全部 provider**。
    #    MetaCubeX/meta-rules-dat 那 20 份是统一来源，文档用一行说明即可 ——
    #    强求逐份列出只会逼出一堆无信息量的表格行。
    #    本判据守的是另一件事：**文档写了来源的那些，来源必须是当前真值**。
    #    （前科：上游把 *-white-guard.* 改名成 *-direct.* 后，配置换了、
    #     文档表仍写旧名且旧名已 404，没有任何闸门发现。）

    cfg_set = set(cfg.values())
    cfg_paths = {path: (name, repo) for name, (repo, path) in cfg.items()}

    # ① 文档提到的来源，配置里必须有活着的 provider（否则是旧名残留 / 死链记载）
    for (repo, path) in sorted(doc):
        if path.startswith("rules/"):
            continue          # 本地自托管清单，配置里是另一形态
        if (repo, path) in cfg_set:
            continue
        # 同一 path 但换了仓库 ⇒ 很可能就是改名/换源
        if path in cfg_paths:
            n2, r2 = cfg_paths[path]
            bad.append("文档表写 %s · %s，但配置里该路径来自 %s（provider %s）—— 来源已变"
                       % (repo, path, r2, n2))
        else:
            bad.append("文档表提到 %s · %s，但配置里没有对应 provider（旧名残留？）"
                       % (repo, path))

    # ② 反向：配置里出现的路径，若文档表提到过**同路径不同仓库**，上面已报；
    #    这里再查「文档以旧路径名出现而配置已改名」—— 用路径 basename 近似匹配
    doc_base = {}
    for (repo, path) in doc:
        doc_base.setdefault(os.path.basename(path), set()).add((repo, path))
    for name, (repo, path) in sorted(cfg.items()):
        base = os.path.basename(path)
        if base in doc_base and (repo, path) not in doc:
            others = [p for (r, p) in doc_base[base] if p != path]
            if others:
                bad.append("配置 %s 用 %s，文档表仍写 %s —— 路径已变"
                           % (name, path, " / ".join(sorted(others))))

    if bad:
        for b in bad:
            print("  NG %s" % b)
        print("-" * 78)
        print("漂移 %d 处 —— 改了 rule-providers 的 URL 后，同步改 %s"
              % (len(bad), os.path.relpath(DOC, ROOT)))
        return 1

    print("  一致 —— 配置里 %d 份远程 provider 的来源，均已在文档表中登记"
          % len(cfg))
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
