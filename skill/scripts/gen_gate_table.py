#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 checker.md §11 的闸门总览表 —— 从 verify_all --index 现抓，不手抄。

为什么需要
    2026-10-08 第四轮审查 P5：那张表表头写着「由 --index 现抓生成，请勿手抄」，
    但**没有任何东西在生成它**（sync_docs 不 target checker.md）、
    **也没有任何东西在守着它**（对账判据只比脚本名，不读这张表）。
    它对得上只是因为那次手改对了 —— 会静默漂移，正是想根治的「死表」问题。

判据
    生成后与盘上内容比对；不一致则以退出码 1 报「文档过期，跑 --apply 重写」。
    ⇒ 这样它既**能生成**又**有判据守**，`check_gate_manifest.py` 会接它。

用法
    python skill/scripts/gen_gate_table.py            # --check：只比对，过期则 exit 1
    python skill/scripts/gen_gate_table.py --apply    # 重写 checker.md §11 表格
"""

import io
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CHECKER = os.path.join(ROOT, "skill", "reference", "clash", "checker.md")

START = "## 11 · "
END = "### 11.1 汇总表怎么读"


def index_entries():
    """现抓 verify_all --index → [(编号, 名字, 命令)]"""
    r = subprocess.run([sys.executable, "skill/tests/verify_all.py", "--index"],
                       cwd=ROOT, capture_output=True, timeout=600)
    txt = r.stdout.decode("utf-8", errors="replace")
    out = []
    cur = None
    for line in txt.split("\n"):
        m = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if m:
            cur = [int(m.group(1)), m.group(2).strip(), ""]
            out.append(cur)
        elif cur is not None and line.startswith("      ") and line.strip():
            cur[2] = line.strip()
    return [tuple(x) for x in out]


def _dup_groups(ents):
    """近重复闸门组 —— 同一脚本 + **至少审一个相同的注册文件**（profile 或 .list）。

    ⚠️ 第十轮问题 5：注释原写"profile 文件"，代码实际匹配任何
       `.conf/.yaml/.yml/.list`（含 `rules/*.list`）⇒ 注释与代码不符。
       现注释改为"注册文件"以如实描述；判据本身不变（按文件交集）。

    判据收窄的原因（一次做对，别来回）：
      · 只按脚本名 ⇒ 11 组（地区组判别力 ×3 也被算进去，但那是三个内核各查各的，
        属合理分工，不是重复劳动）
      · 加上"审同一份文件" ⇒ 只剩真正审重复内容的那几对
    例：#9「分流覆盖·mihomo」审 routing.yaml；#41「clash 分流覆盖」审 routing+lazy
        ⇒ 有交集（routing.yaml）⇒ 算近重复。#4/#5/#6 各审自己内核的 profile ⇒ 不算。
    ⚠️ 同时取代了字面量 `#9 与 #41`（插入占位闸门后编号会漂移，--check 抓不到）。
    """
    by_script = {}
    for num, name, cmd in ents:
        m = re.search(r"([A-Za-z0-9_]+[.]py)", cmd or "")
        if not m:
            continue
        files = frozenset(re.findall(r"[A-Za-z0-9_./-]+[.](?:conf|yaml|yml|list)", cmd or ""))
        by_script.setdefault(m.group(1), []).append((num, name, files))
    out = {}
    for script, items in by_script.items():
        if len(items) < 2:
            continue
        # 与**其它任一项**有文件交集 ⇒ 算近重复。
        # ⚠️ 不能用"跟已入组的比"的增量算法：第一个入组的若是 #7（Surge），
        #    后面 clash 的 #9/#41 与它无交集就都进不来 ⇒ 实测恒返回 0 组。
        #    （这是第九轮来回改了三次才定位的错，记在此）
        # ⚠️ 第十轮问题 4：若**同一道闸门被列两次**（同脚本同文件、编号也相同），
        #    会被当成"刻意保留的双档覆盖"，措辞不符（字面重复不叫刻意保留）。
        #    ⇒ 先按 (编号, 名字) 去重，再看文件交集。
        uniq = []
        seen = set()
        for it in items:
            key = (it[0], it[1])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)
        grp = [it for it in uniq
               if any(it[2] & other[2] for other in uniq if other is not it)]
        if len(grp) > 1:
            out[script] = grp
    return out


def _where_of(name):
    """「位置」列：CI 独立 step / 手动 —— 由该脚本是否**真正被调用**决定（不猜）。

    ⚠️ 第十轮问题 6：位置列曾被写死成 "—"。
    ⚠️ 第十一轮问题 5：改成 `name in ci` 后仍是**裸子串** —— ci.yml 的注释或 echo
       里只要提到这个名字，该列就会从"手动"翻成"CI 独立 step"。
       现改为：只看**非注释行**、且要求脚本名前面是空白/斜杠/引号（`.../xxx.py`），
       即真正的调用形态。另：`verify_all.py` 单独说明它是总入口本身。
    """
    try:
        ci = open(os.path.join(ROOT, ".github", "workflows", "ci.yml"),
                  encoding="utf-8").read()
    except Exception:
        return "—"
    if name == "verify_all.py":
        return "CI 独立 step（总入口本身）"
    base = re.escape(name[:-3] if name.endswith(".py") else name)
    pat = re.compile(r"[\s/\\'\"]" + base + r"\.py\b")
    for line in ci.splitlines():
        if line.strip().startswith("#"):
            continue                      # 注释行不算
        if pat.search(" " + line):
            return "CI 独立 step"
    return "手动（不在任何闸门）"



def _not_in_gates_rows():
    """「不进闸门」表行 —— 真源是 check_gate_manifest.KNOWN_SEPARATE。

    第九轮问题 1：此前这张表在模板里硬编码，且谎称"以 KNOWN_SEPARATE 为真源"
    （check_gate_manifest 从不读 §11）⇒ 声明是假的，两边已不一致。
    """
    sys.path.insert(0, os.path.join(ROOT, "skill", "tests"))
    try:
        import check_gate_manifest as m
    except Exception:
        return []
    out = []
    for name in sorted(m.KNOWN_SEPARATE):
        why = m.KNOWN_SEPARATE[name]
        if not isinstance(why, str):
            why = str(why)
        out.append((name, why))
    return out


def build_block():
    ents = index_entries()
    if not ents:
        return None, 0
    rows = "\n".join("| %d | %s | `%s` |" % (n, name, cmd or "—") for n, name, cmd in ents)

    # 近重复：从 entries 现算（第九轮问题 2：不再用字面量 #9/#41）
    dups = _dup_groups(ents)
    _dup_n = len(dups)
    if _dup_n:
        _dup_desc = "；".join(
            "%s（%s）" % (" 与 ".join("#%d" % it[0] for it in items),
                          "|".join(it[1] for it in items))
            for _sc, items in sorted(dups.items(),
                                     key=lambda kv: min(it[0] for it in kv[1])))
    else:
        _dup_desc = "无"

    # 「不进闸门」表：真源是 check_gate_manifest.KNOWN_SEPARATE（第九轮问题 1）
    _sep = _not_in_gates_rows()
    _sep_rows = chr(10).join(
        "| `%s` | %s | %s |" % (nm, _where_of(nm), why) for nm, why in _sep)
    if not _sep_rows:
        _sep_rows = "| （读不到 KNOWN_SEPARATE） | — | — |"
    block = (
        "## 11 · %d 道总览表\n\n"
        "> ⚠️ **关于道数（含近重复，对外说数量时心里有数）**：\n"
        "> %d 道里有 %d 组近重复 —— %s。**刻意保留**：双档覆盖能让分流版与\n"
        "> 懒人版都查到；合并会让其中一档漏检。故这个数**含重复劳动**，不是 %d 种独立检查。\n"
        ">\n"
        "> ✅ **本表由 `python skill/scripts/gen_gate_table.py --apply` 生成**，\n"
        "> 真源是 `verify_all.py --index`，**不要手抄**。\n"
        "> 漂移由同一脚本的 `--check` 判负（已接闸门），不再靠人记得更新。\n"
        ">\n"
        "> 历史：此表曾长期是手抄死表 —— 表头自称「现抓、勿手抄」，实际编号与\n"
        "> `--index` 全对不上（Release 写 27 实为 18、地区组 28–30 实为 2–4），\n"
        "> 还把 `check_selfcontained` 同时列为「第 21 道」和「不进闸门」。（第三轮审查第 6 条）\n\n"
        "| # | 闸门 | 命令 |\n"
        "|:--|:-----|:-----|\n"
        "%s\n\n"
        "另有**不进闸门**的 %d 项 —— 下表由 `check_gate_manifest.KNOWN_SEPARATE` **直接生成**，\n"
        "> 与它不会分叉（第九轮问题 1：此前硬编码且谎称对账，两边曾不一致）：\n\n"
        "| 项 | 位置 | 为什么不进 |\n"
        "|:---|:-----|:-----------|\n"
        "%s\n"
        "⚠️ `min-pair 一致` 一道含 V7「一天至多一版」两条断言；本仓以 `SKIP_V7=1` 豁免\n"
        "⇒ 该两条记为 **未验证**（⚠️）而非通过，本道以 exit 3 结束，上层显示 ⚠️。\n"
        "详见 `release-rules.md` §4.1。\n\n"
        % (len(ents), len(ents), _dup_n, _dup_desc, len(ents), rows, len(_sep), _sep_rows)
    )
    return block, len(ents)


def main():
    apply_ = "--apply" in sys.argv
    block, cnt = build_block()
    if not block:
        print("  NG 抓不到闸门清单（verify_all --index 失败）")
        return 1

    s = open(CHECKER, encoding="utf-8").read()
    i = s.find(START)
    j = s.find(END)
    if i < 0 or j < 0 or j < i:
        print("  NG checker.md 里定位不到 §11 区块")
        return 1

    current = s[i:j]
    if current.strip() == block.strip():
        print("  一致 —— §11 总览表与 --index 现抓一致（%d 道）" % cnt)
        return 0
    if not apply_:
        print("  NG §11 总览表已过期（真源 %d 道）⇒ 跑 "
              "`python skill/scripts/gen_gate_table.py --apply`" % cnt)
        return 1

    open(CHECKER, "w", encoding="utf-8", newline="\n").write(s[:i] + block + s[j:])
    print("  已重写 §11 总览表（%d 道）" % cnt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
