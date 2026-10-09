#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""routing_evolution.py — 分流意图的 git 演变分析 · 给 AI 读的机读时间线。

纯读 git，绝不改任何文件。它回答一个 AI 接手时最该知道的问题：
「这套分流逻辑是怎么一步步变成现在这样的？」—— 哪些规则集在哪个 commit
被加进来 / 删掉 / 悄悄改了去向（如某域从 PROXY 挪到 DIRECT），规则总量怎么涨的。

解析复用 build_ir.py 的同一套加载器（**单一真源**，不重复解析逻辑 —— 本仓已为
「审计脚本重复」付过 2773 行的债，见 pitfalls.md）。产出是机读 JSON，**不是闸门**
（它依赖 git 历史长度，会随每次提交变化，故不落盘、不判负）——按需跑。

用法：
    python routing_evolution.py                 # JSON 打到 stdout
    python routing_evolution.py --out e.json    # 写文件
    python routing_evolution.py --product lazy  # 分析懒人版（默认 routing）
    python routing_evolution.py --limit 20      # 只看最近 20 个动过分流的 commit
退出码：0 = 成功 · 2 = 环境/解析失败。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:  # E4 可移植性：中文 Windows 控制台 GBK 会让 print 崩成退出码 1
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 复用 build_ir 的解析器（单一真源）
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ir  # noqa: E402

SCHEMA = "self-conf.evolution/v1"


def _git(root, *args):
    r = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("git %s 失败：%s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def _file_at(root, commit, relpath):
    """取某 commit 下某文件内容；不存在返回 None。"""
    r = subprocess.run(["git", "show", "%s:%s" % (commit, relpath)], cwd=str(root),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return None
    return r.stdout


def _load_kernel_rules(kernel, text):
    """把某 commit 下某内核配置的**文本**解析成规则列表（复用 build_ir 的加载器）。"""
    if text is None:
        return None
    with tempfile.NamedTemporaryFile("w", suffix="." + ("conf" if kernel == "surge" else "yaml"),
                                     delete=False, encoding="utf-8") as fh:
        fh.write(text)
        tmp = Path(fh.name)
    try:
        if kernel == "surge":
            return build_ir._load_surge_rules(tmp)
        if kernel == "clash":
            return build_ir._load_clash_rules(tmp)
        return build_ir._load_egern_rules(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def _rel(root, p):
    """仓库相对路径，统一正斜杠（git 在 Windows 上也要 forward-slash 路径）。"""
    return str(p.relative_to(root)).replace("\\", "/")


def _snapshot(root, commit, product):
    """某 commit 下三内核 routing 意图快照：{kernel: [rule,...] or None}。"""
    paths = build_ir._kernel_paths(root, product)
    snap = {}
    for kernel, p in paths.items():
        text = _file_at(root, commit, _rel(root, p))
        snap[kernel] = _load_kernel_rules(kernel, text)
    return snap


def _index_by_key(rules):
    """source_norm -> target（同 key 取最后一次，规则集在一份配置里唯一）。"""
    idx = {}
    for r in rules or []:
        key = r.get("source_norm") or ("__%s__" % r["kind"])
        idx[key] = r.get("target")
    return idx


def _delta(prev_rules, cur_rules):
    prev_i = _index_by_key(prev_rules)
    cur_i = _index_by_key(cur_rules)
    added = sorted(k for k in cur_i if k not in prev_i)
    removed = sorted(k for k in prev_i if k not in cur_i)
    retargeted = sorted(({"source": k, "from": prev_i[k], "to": cur_i[k]}
                         for k in cur_i if k in prev_i and prev_i[k] != cur_i[k]
                         and not k.startswith("__")), key=lambda d: d["source"])
    return {"added": added, "removed": removed, "retargeted": retargeted,
            "rule_count": len(cur_rules or [])}


def build(root, product="routing", limit=0):
    # 取所有动过任一 routing 配置的 commit（正序：旧 -> 新）
    relpaths = [_rel(root, p) for p in build_ir._kernel_paths(root, product).values()]
    hashes = [h for h in _git(root, "log", "--pretty=%H", "--reverse", "--", *relpaths).split() if h]
    if limit and len(hashes) > limit:
        hashes = hashes[-limit:]

    commits = []
    timeline = []
    prev_snap = None
    # 追踪「每个 source 的去向随时间怎么变」—— 回答「谁悄悄从 PROXY 挪到 DIRECT」
    target_evolution = {}
    for h in hashes:
        meta = _git(root, "show", "-s", "--pretty=%H%x00%ad%x00%s", "--date=short", h).strip("\n")
        _hh, date, subject = meta.split("\x00", 2)
        snap = _snapshot(root, h, product)
        delta = {}
        for kernel in build_ir.KERNELS:
            cur = snap.get(kernel)
            if cur is None:
                continue
            prev = prev_snap.get(kernel) if prev_snap else None
            if prev is None:
                # 首次出现：整份算 added baseline，不做逐条 diff
                delta[kernel] = {"baseline_rules": len(cur), "added": [], "removed": [],
                                 "retargeted": [], "rule_count": len(cur)}
            else:
                delta[kernel] = _delta(prev, cur)
            # 记录去向演变
            for r in cur:
                key = r.get("source_norm")
                if not key:
                    continue
                ev = target_evolution.setdefault(kernel, {}).setdefault(key, [])
                if not ev or ev[-1]["to"] != r.get("target"):
                    ev.append({"commit": h[:7], "date": date, "to": r.get("target")})
        timeline.append({"commit": h[:7], "date": date,
                         "rule_count": {k: len(snap[k]) for k in build_ir.KERNELS if snap.get(k) is not None}})
        commits.append({"commit": h[:7], "date": date, "subject": subject, "delta": delta})
        prev_snap = snap

    # 只保留「真的变过去向」的 source（演变序列长度 > 1）
    moved = {k: {src: seq for src, seq in m.items() if len(seq) > 1}
             for k, m in target_evolution.items()}
    moved = {k: v for k, v in moved.items() if v}

    return {"schema": SCHEMA, "product": product,
            "generated_by": "self-conf-skills/run/routing_evolution.py",
            "commits_analyzed": len(commits),
            "moved_targets": moved,        # 哪些规则集的去向随历史变过（含 from/to 链）
            "timeline": timeline,          # 每个 commit 的三内核规则总量
            "commits": commits}            # 每个 commit 的逐内核增/删/改判 diff


def main(argv):
    root = Path(__file__).resolve().parents[2]
    product = "routing"
    limit = 0
    out = None
    i = 0
    while i < len(argv):
        if argv[i] == "--product" and i + 1 < len(argv):
            product = argv[i + 1]; i += 2
        elif argv[i] == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1]); i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out = argv[i + 1]; i += 2
        else:
            i += 1
    try:
        evo = build(root, product=product, limit=limit)
    except Exception as e:
        sys.stderr.write("演变分析失败：%s\n" % e)
        return 2
    text = json.dumps(evo, ensure_ascii=False, sort_keys=False, indent=1)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        print("已写入 %s（%d 个 commit）" % (out, evo["commits_analyzed"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
