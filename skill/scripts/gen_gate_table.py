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


def build_block():
    ents = index_entries()
    if not ents:
        return None, 0
    rows = "\n".join("| %d | %s | `%s` |" % (n, name, cmd or "—") for n, name, cmd in ents)
    block = (
        "## 11 · %d 道总览表\n\n"
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
        "另有**不进闸门**的两项（由「闸门清单对账」登记并逐条点名理由）：\n\n"
        "| 项 | 位置 | 为什么不进 |\n"
        "|:---|:-----|:-----------|\n"
        "| `clash/check_remote_urls.py` | CI 独立 step | 慢（需联网探测数十个 URL），不适合与快门并行 |\n"
        "| `egern/probe_dns_endpoints.py` | CI 独立 step | 需联网实测加密 DNS 端点，网络抖动会假红 |\n\n"
        "⚠️ `min-pair 一致` 一道含 V7「一天至多一版」两条断言；本仓以 `SKIP_V7=1` 豁免\n"
        "⇒ 该两条记为 **未验证**（⚠️）而非通过，本道以 exit 3 结束，上层显示 ⚠️。\n"
        "详见 `release-rules.md` §4.1。\n\n"
        % (len(ents), rows)
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
