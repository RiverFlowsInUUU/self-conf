#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown 相对链接与锚点 + 现役层命令行全路径检查 —— 内部链接与可照抄命令都要真的能到。

本脚本有两条判据：① 相对链接与锚点（原始面，下面第一段）；② 现役层文档里
「可照抄命令行中的完整路径」是否存在 —— **2026-09-26 经用户授权扩面**（标记 `q11-user-approved`）。

为什么要单独一个脚本：
    改了标题之后，**引用它的所有链接都会静默失效** —— GitHub 不会报错，
    读者点了 404。这类问题肉眼扫不出来（尤其锚点里含中文、emoji、全角标点）。

⭐ 锚点算法：自实现（不依赖 node），但**逐条与 github-slugger 对拍过**。
    规则 ≈ 删掉标点 / 符号 / 控制字符，其余保留，空格转 `-`。
    三个最容易写错的点（曾经全踩过，2026-09-22 修正）：

      · `_`(U+005F) **保留** —— 它不在 github-slugger 的删除字符类里。
        `## 4. `policy_groups` 段`  ->  `#4-policy_groups-段`
        （错写成 `4-policygroups-段` 就点不动）
      · FE0F 变体选择符 **保留**（它是 Mn 组合符，不是符号），emoji 本体删掉。
        `## 🛡️ Clash 配置模板`  ->  `#️-clash-配置模板`
        （`#` 后紧跟一个**看不见**的 U+FE0F，别手打）
      · 同名标题从第 2 次出现起加后缀：`#新增` / `#新增-1` / `#新增-2`

    ⚠️ 适用范围：本实现按「中日韩汉字 + 拉丁字母数字 + `_`/`-`/空格 + FE0F」白名单。
       若标题引入新字符类别（希腊 / 西里尔字母、上标数字、`Ⓐ` 这类带圈字母…
       github-slugger 对这些的处理与直觉不同），**必须逐条核对**。核对办法全程在仓内、
       不依赖 node：
         ① 把该标题加进本文件的 `SELFTEST` 列表，跑 `python check_links.py --selftest`，
            看本实现的输出；
         ② 把同一条标题贴进 GitHub 任意 Markdown 预览（或 issue 编辑框），从渲染后的标题
            上取锚点；
         ③ 两者不一致 ⇒ 改 `gh_slug()` 的白名单，并把该标题回填进 `SELFTEST`。
       ⚠️ 早先这里写的是一条 `node _tools/dump_slugs.mjs` + `compare_slug.py` 的对拍流程 ——
       那两个文件**从来不在本仓**（合并前的外挂脚本），照做会直接卡住。2026-09-25 换成上面
       的仓内办法：**头注里不留跑不通的指引**。

判据 ② · 现役层「可照抄命令行」里的完整路径（q11-user-approved · 2026-09-26）：
    q7 曾判出 4 条「命令照抄跑不通」——它们全是写在反引号 / 代码围栏里的完整路径，
    而原始判据只认 `](...)` 这一种 markdown 链接语法，**抓不到**这一类漂移。扩面收口到最小：
    只判「命令行（行内含 python / python3 / bash / sh / PYTHONIOENCODING=utf-8 触发词）里
    以 `.py` / `.sh` 结尾、且含 `/` 的完整路径 token」，按**仓根**解析、与 `git ls-files`
    跟踪件对拍（无 git 环境退回文件系统 walk）。三类东西一律**不判**：
      · 沿革层整篇排除：`CHANGELOG.md`、`*文件版本沿革*`、`日志旧版原文`、`_archive`、
        `DetailsReadme` —— 它们记录的是当时的历史事实，不该被今天的树形倒着改；
      · 变量拼接形：`bash $S/go.sh`（`$` 不是路径字符，正则会从 `S` 起截出残片 ——
        靠「token 前一位必须是空白/引号/` 等起始位」挡掉，见 _CMD_OK_BEFORE）；
      · 占位符：含 `<` `>` `*` `$` `{` `}`、`/path/to`、`YYYY` 的，以及**裸文件名**
        （`run.sh` 无 `/` ⇒ 不是完整路径，多半在 cd 之后跑，判它等于误报）。
    与判据 ① 相反，这条**在代码围栏内照判** —— 可照抄命令恰恰大多写在围栏里。
    正/反例 fixture 随 `--selftest` 常驻：措辞润色（路径不动）必绿、
    命令行路径的目标脚本消失必红且点名。

退出码：0 = 全部可解析；1 = 有失效链接或取不到的命令行路径；2 = 环境问题。
"""

import os
import re
import subprocess
import sys

# Windows 中文环境（控制台 / 管道重定向）默认 GBK(cp936)：emoji 一 print 就
# UnicodeEncodeError、进程以退出码 1 结束 —— 而回归里"期望判负"的 fixture 期望的
# 恰恰是 1 ⇒ 会假绿。统一钉成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 保留集：ASCII 小写字母、数字、下划线、汉字、假名、谚文、变体选择符 / 键帽组合符
# （`_` 与 `\ufe0f` 是 2026-09-22 的对拍结论：github-slugger 保留它们）
_KEEP = re.compile(r"[a-z0-9_\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af"
                   r"\ufe0e\ufe0f\u20e3]")
# 只列**本仓有实质理由**跳的目录；其余点开头的目录（各家编辑器 / AI 工具的本地工作区，
# 名字随工具版本变）由下面 `collect()` 的「点开头的目录一律不 walk」统一兜 ——
# 早先这里写死过一个第三方工具的工作目录名，那属于"每来一个工具改一次判据"。
_SKIP_DIRS = {".git", "icons", "node_modules", "__pycache__"}
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_FENCE = re.compile(r"^\s*(```+|~~~+)")

# ── 判据 ② 的构件（q11-user-approved · 2026-09-26 · 口径与 q10 收口扫描同源：现役层可照抄
#    命令行的完整路径 token 对拍跟踪树 · 上线首日 132 token / 0 取不到 ⇒ 必须绿）──
# 沿革层：整篇不进判据 ②（判据 ① 的口径保持原样，一个文件都不许多排除）。
_CMD_HIST = re.compile(r"CHANGELOG\.md$|文件版本沿革|日志旧版原文|_archive|DetailsReadme")
# 触发词：这一行得是「能照着敲」的命令上下文，纯提文件名的散文不算。
_CMD_LINE = re.compile(r"(?:python3?|bash|sh|PYTHONIOENCODING=utf-8)\s")
# 路径 token：起点限定 `. / 字母`，体部允许 `-` `_` `/` 点、汉字与 ASCII 词字符，尾 `.py` / `.sh`。
_CMD_PATH = re.compile(r"([./A-Za-z][\w\-/.\u4e00-\u9fff]*)\.(?:py|sh)\b")
# 占位符 / 变量拼接的残片特征（对 token 本体查）。
_CMD_PLACE = re.compile(r"[<>*$]|\{/|\}|\bpath/to\b|YYYY")
# token 前一位必须是「起始位」，否则它只是更长表达式（`$VAR/…`、`docs/<名>/…` 这类
# 被正则从腰身截断的残片）。真实命令里路径前面只可能是：行首、空白、
# 引号 / 反引号（内联代码）、`=`（`--flag=skill/x.py` 形）—— 收紧到这五个，
# `>` `|` `&` `(` 一律不算起始位（fixture 实测：`<名>/tool.py` 正是从 `>` 后被截出的假路径）。
_CMD_OK_BEFORE = set(" \t\"'`=")


def gh_slug(heading):
    """按 GitHub（github-slugger）规则把标题文本转成锚点 —— 不含去重后缀。"""
    s = heading.strip().lower()
    s = s.replace("`", "")          # 行内代码反引号在锚点里不存在
    out = []
    for ch in s:
        if ch == " " or ch == "-":
            out.append(ch)
        elif _KEEP.match(ch):
            out.append(ch)
        # 其余（emoji / 全角标点 / `.` / `/` / `[` `]` …）全部丢弃
    return "".join(out).replace(" ", "-")


def anchors_of(path):
    """收集文件里所有可用锚点 —— 含同名标题的 `-1` / `-2` 去重后缀。"""
    occ = {}          # slug -> 已出现次数
    out = set()
    for line in open(path, encoding="utf-8"):
        m = _HEADING.match(line.rstrip())
        if not m:
            continue
        result = gh_slug(m.group(2))
        original = result
        while result in occ:
            occ[original] += 1
            result = f"{original}-{occ[original]}"
        occ[result] = 0
        out.add(result)
    return out


def collect(dirpath):
    files = []
    for root, dirs, names in os.walk(dirpath):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for n in names:
            if n.endswith((".md", ".markdown")):
                files.append(os.path.join(root, n))
    return sorted(files)


def tracked_files(root):
    """仓根基准的「可被克隆读者拿到」文件集（斜杠归一）。

    首选 `git ls-files -z` —— 判「可照抄」就必须以跟踪树为准：盘上存在但没提交的文件，
    对克隆下来的人而言等于不存在。非 git 环境（临时 fixture 目录、打包归档）退回
    文件系统 walk：宽一档，但断链/断路径照样抓得住。
    """
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"],
                             capture_output=True).stdout.decode("utf-8", "replace")
        names = {p.strip('"') for p in out.split("\0") if p}
        if names:
            return names
    except OSError:
        pass
    names = set()
    for r, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for f in fs:
            names.add(os.path.relpath(os.path.join(r, f), root).replace(os.sep, "/"))
    return names


def cmd_path_misses(path, tracked):
    """判据 ②：单个 markdown 里「现役层可照抄命令行」的完整路径，取不到者列表。

    ⇒ ([(lineno, token)], n)：命中列表 与 判定范围内的完整路径 token 总数
    （报数与判负同源，不另跑一遍计数循环）。围栏内照判（命令大多写在那儿）；
    沿革层由调用方整篇排除。
    """
    bad = []
    n = 0
    text = open(path, encoding="utf-8").read()
    for lineno, line in enumerate(text.split("\n"), 1):
        if not _CMD_LINE.search(line):
            continue
        for m in _CMD_PATH.finditer(line):
            tok = m.group(0)
            prev = line[m.start() - 1] if m.start() else " "
            if prev not in _CMD_OK_BEFORE:       # 变量拼接 / 表达式残片掐出来的腰身
                continue
            if _CMD_PLACE.search(tok):          # 占位符不宣称存在
                continue
            rel = tok[2:] if tok.startswith("./") else tok
            if "/" not in rel:                  # 裸文件名不是「完整路径」
                continue
            n += 1
            if rel not in tracked:
                bad.append((lineno, tok))
    return bad, n


SELFTEST = [
    ("🛡️ Clash 配置模板", "️-clash-配置模板"),
    ("4. `policy_groups` 段", "4-policy_groups-段"),
    ("1.3 `policy_groups` —— 四种类型、组间引用、图标",
     "13-policy_groups--四种类型组间引用图标"),
    ("## 2 · 防泄露原理：从机制到推导", "2--防泄露原理从机制到推导"),
    ("📁 文件结构", "-文件结构"),
    ("abc_def", "abc_def"),
]


def selftest():
    bad = 0
    for head, want in SELFTEST:
        got = gh_slug(head.lstrip("# "))
        flag = "✅" if got == want else "❌"
        if got != want:
            bad += 1
        print(f"  {flag} {head!r}\n     得到 {got!r}  期望 {want!r}")
    # 去重后缀
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("## 新增\n\ntext\n\n## 新增\n\n## 新增\n")
        tmp = f.name
    got = anchors_of(tmp)
    os.unlink(tmp)
    want = {"新增", "新增-1", "新增-2"}
    ok = got == want
    print(f"  {'✅' if ok else '❌'} 同名标题去重 -> {sorted(got)}")
    if not ok:
        bad += 1
    # ⚠️ 负例：坏链接必须被判出来。早先 selftest 只覆盖了**锚点算法**那半边，
    #    "能不能判出坏链接"这半边一直没有反例（2026-09-25 补）。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        def _w(name, text):
            with open(os.path.join(td, name), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        _w("b.md", "# 你好\n")
        _w("a.md", "[好](b.md#你好)\n[坏](b.md#nope)\n[丢](missing.md)\n")
        p = subprocess.run([sys.executable, os.path.abspath(__file__), td],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        ok2 = p.returncode == 1 and "nope" in out and "missing.md" in out
        print(f"  {'✅' if ok2 else '❌'} 坏链接负例 -> rc={p.returncode}"
              f"（期望 1 且点名 nope / missing.md）")
        if not ok2:
            bad += 1
    # ⚠️ 判据 ② 的正/反例（2026-09-26 用户授权扩面时约定的「改前先交付」件）：
    #    反例 = 命令行里的路径漂移**必须判负**（q7 那 4 条正是这一类）；
    #    正例 = 只润色行文、路径一字不动**必须保持绿**（误报会逼人删判据，比漏报更伤）；
    #    同批钉住三类不该判的：变量拼接形 / 占位符 / 裸文件名，以及沿革层整篇排除。
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "skill", "scripts"))
        with open(os.path.join(td, "skill", "scripts", "go.sh"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("#!/usr/bin/env bash\n")
        # 沿革层 fixture：名字必须命中 _CMD_HIST，里面写坏路径也不判
        with open(os.path.join(td, "CHANGELOG.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("# 更新日志\n\n历史条目照抄：bash skill/scripts/gone-in-history.sh\n")

        def _run(doc_text):
            with open(os.path.join(td, "docs.md"), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(doc_text)
            q = subprocess.run([sys.executable, os.path.abspath(__file__), td],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            return q.returncode, (q.stdout or "") + (q.stderr or "")

        _body = ("```bash\nPYTHONIOENCODING=utf-8 python3 ./skill/scripts/go.sh\n```\n"
                 "变量不判：bash $S/go.sh ｜ 占位不判：bash docs/<名>/tool.py · "
                 "bash /path/to/x.py ｜ 裸名不判：cd skill/scripts && bash go.sh\n")
        rc_pos, out_pos = _run("# T\n\n先跑 `bash skill/scripts/go.sh` 验收。\n" + _body)
        # 同一棵树、同一批路径，只换措辞（正例之二：润色不红）
        rc_pos2, out_pos2 = _run("# T\n\n下面这条可直接照抄，跑完即绿：`bash skill/scripts/go.sh`。\n"
                                 + _body.replace("验收", "复验"))
        okp = rc_pos == 0 and rc_pos2 == 0
        print(f"  {'✅' if okp else '❌'} 措辞润色正例 -> rc={rc_pos}/{rc_pos2}"
              f"（期望 0/0；变量/占位/裸名/沿革不误判）")
        if not okp:
            bad += 1
        os.remove(os.path.join(td, "skill", "scripts", "go.sh"))
        rc_neg, out_neg = _run("# T\n\n照抄 `bash skill/scripts/go.sh` 即红（fixture：目标已删）。\n"
                               + _body)
        okn = (rc_neg == 1 and "skill/scripts/go.sh" in out_neg
               and "gone-in-history" not in out_neg
               and "tool.py" not in out_neg and "/path/to/x.py" not in out_neg)
        print(f"  {'✅' if okn else '❌'} 路径漂移负例 -> rc={rc_neg}"
              f"（期望 1 且只点名 skill/scripts/go.sh，不牵连沿革/变量/占位/裸名）")
        if not okn:
            bad += 1
    print("─" * 62)
    print("✅ 自检通过" if not bad else f"❌ 自检失败 {bad} 项")
    return 0 if not bad else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()

    root = sys.argv[1] if len(sys.argv) > 1 else "."
    if not os.path.isdir(root):
        print(f"❌ 找不到目录：{root}", file=sys.stderr)
        return 2

    mds = collect(root)
    if not mds:
        print("⚠️  没有找到任何 markdown 文件", file=sys.stderr)
        return 2

    anchors = {os.path.relpath(p, root).replace(os.sep, "/"): anchors_of(p)
               for p in mds}
    tracked = tracked_files(root)

    bad = []
    checked = 0
    for p in mds:
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        base = os.path.dirname(p)
        fence = None
        for lineno, line in enumerate(open(p, encoding="utf-8"), 1):
            # 跳过 fenced code block 里的行 —— 那里的 `](...)` 往往是示例
            f = _FENCE.match(line)
            if fence:
                if f and line.strip().startswith(fence):
                    fence = None
                continue
            if f:
                fence = f.group(1)
                continue
            for tgt in _LINK.findall(line):
                if tgt.startswith(("http://", "https://", "mailto:", "tel:")):
                    continue
                checked += 1
                path, _, frag = tgt.partition("#")
                if not path:
                    if frag and frag not in anchors.get(rel, set()):
                        bad.append((rel, lineno, "页内锚点不存在", tgt))
                    continue
                tgt_fs = os.path.normpath(os.path.join(base, path))
                tgt_rel = os.path.relpath(tgt_fs, root).replace(os.sep, "/")
                if os.path.isdir(tgt_fs):
                    continue
                if not os.path.exists(tgt_fs):
                    bad.append((rel, lineno, "目标文件不存在", tgt))
                    continue
                if frag and tgt_rel in anchors and frag not in anchors[tgt_rel]:
                    bad.append((rel, lineno, "目标锚点不存在", tgt))

    # ── 判据 ② · 现役层可照抄命令行的完整路径（q11-user-approved · 见头注）──
    n_cmd = 0
    for p in mds:
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        if _CMD_HIST.search(rel):               # 沿革层整篇不进判据 ②
            continue
        misses, n = cmd_path_misses(p, tracked)
        n_cmd += n
        for lineno, tok in misses:
            bad.append((rel, lineno, "命令行路径取不到（不在跟踪树）", tok))

    print(f"扫描 {len(mds)} 个 markdown 文件，检查 {checked} 条相对链接"
          f" · 现役层命令行完整路径 {n_cmd} 处（沿革/变量/占位不判）")
    print("─" * 62)
    if bad:
        for rel, lineno, why, tgt in bad:
            print(f"   ❌ {rel}:{lineno}  [{why}]  {tgt}")
        print("─" * 62)
        print(f"result: {len(bad)} 条失效")
        return 1
    print("   ✅ 全部相对链接与锚点均可解析 · 现役层命令行完整路径全部可照抄")
    print("─" * 62)
    print("✅ 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
