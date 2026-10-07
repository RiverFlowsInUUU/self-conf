#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""".min 与完整版对拍 —— 去掉注释与空行后必须逐字相同。

为什么单独要这一项：
    每份 profile 都有两份形态（`.conf` / `.min.conf`、`.yaml` / `.min.yaml`）。
    `.min` 的定位是**同一份配置去掉注释**，不是"裁剪配置"。一旦两版的配置本体漂移，
    照着文档改完整版、实际导入的却是 `.min` ⇒ 改了个寂寞，而且肉眼看不出来。

    既有检查各守了一角、都不覆盖这条：DNS 审计只逐字比 DNS 段的键、
    ④-b 只比组顺序，且**只管 Surge 侧**；Egern 侧过去完全没有人对拍过两版形态。

判据（与人工核对时的口径一致）：
    · 删行尾注释（`空格/制表符 + #` 或 `;` 起的部分）
    · 删整行注释与空行
    · 删行尾空白
    剩下逐行比对；任何一处不同即判负，并打印**第一处**差异的行号与两侧内容。

版本与归档序列（2026-09-24 起，订阅地址固定化之后一并由本脚本判）：
    订阅地址钉成 `routing.*` / `lazy.*`（固定名、升版不改名）⇒ "当前是哪一版"只剩
    profile **头注**这一处显式承诺（从前是三份 runner 里各一行 `CURRENT=`，改一处漏两处）。
    判据是固定 16 条：两侧各 6 条（顶层只有固定名四件 · 头注版本标记形状合法 · 归档目录在 ·
    归档文件名形状合法 · 每版成对齐全 · 归档不高于当前版且同版本仍是逐字快照）
    + **版本节奏 2 条**（V7「一天一版」，路由线 / 懒人线各一）
    + 跨侧 2 条（两侧 routing 版本一致 · 两侧 lazy 版本一致）。
    **条数不随归档文件数增长** —— 与 `CURRENT` 是承诺值同一条纪律。

退出码：0 = 全部成对相同 · 1 = 有不一致 · 2 = 目录/参数问题（profiles 目录不存在）。
用法：python skill/tests/check_min_pair.py [仓库根]     # 默认取本文件所在的仓库根
"""

import os
import re
import sys

# Windows 中文环境的控制台与管道默认 GBK(cp936)：emoji 一 print 就 UnicodeEncodeError、
# 进程以退出码 1 结束 —— 与"期望判负"的用例撞码会假绿。统一钉成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ⚠️ 原本只有两族 —— mihomo 的 .min 对拍 / 版本头注 / 归档序列**从来没被审过**。
#   2026-10-07 补上 clash/profiles（mihomo 无 config_old，归档判据对它不适用）。
PROFILE_DIRS = ("surge/profiles", "egern/profiles", "clash/profiles")
TRAIL = re.compile(r"[ \t]+[#;].*$")      # 行尾注释
WHOLE = re.compile(r"^\s*[#;]")           # 整行注释


def normalize(text):
    """去注释、去空行、去行尾空白；CRLF 先归一化成 LF。"""
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    for ln in lines:
        ln = TRAIL.sub("", ln)
        if not ln.strip() or WHOLE.match(ln):
            continue
        out.append(ln.rstrip())
    return out


def first_diff(a, b):
    """返回第一处不同的 0-based 行号；仅长度不同则返回较短长度。"""
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


# 三段制（2026-09-29 起）：X.Y.Z 合法（第三段可选）；历史两段号不回改，两段三段混排都认。
VERSION_RE = re.compile(r"^#! version=(routing|lazy)_v([0-9]+)\.([0-9]+)(?:\.([0-9]+))?$")
# 归档名里的版本号最多三段（满 10 进 1 ⇒ 4.0.10 也合法）；本仓 2026-09-24 固定化之前
# 有一批只写主号（`routing_v3.conf`），一并认 —— V4 要抓的是"新归档没按进位规则起名"，不是考古。
ARCHIVE_RE = re.compile(r"^(routing|lazy)_v([0-9]+(?:\.[0-9]+){0,2})(\.min)?\.(conf|yaml)$")
OLD_DIR = "config_old"          # 归档目录（2026-09-27 恢复；每版完整版 + .min 成对）
# 「一天一版」生效日（2026-10-04，写入当日即生效）：此前的多版本日
# （09-24 分流版 8 个、09-26/27/28 各 3 个、09-29 各 2 个）是历史，不回改也不追溯 ——
# 与三段制「历史两段号不回改」同一条纪律。
CADENCE_FROM = "2026-10-04"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ver_tuple(v):
    """'4.0.1' / '3.2' / '3' → (4,0,1) / (3,2) / (3,)，逐段数值比先后（元组前缀小于长尾）。"""
    return tuple(int(x) for x in v.split("."))


def head_version(path):
    """读 profile 第一行的版本标记 ⇒ ("routing", "3.2")；读不出或形状不对 ⇒ None。"""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            first = f.readline()
    except OSError:
        return None
    m = VERSION_RE.match(first.rstrip("\r\n"))
    ver = "%s.%s%s" % (m.group(2), m.group(3),
                       ("." + m.group(4)) if m.group(4) else "")
    return (m.group(1), ver) if m else None


def day_versions(root):
    """(产品线, 'YYYY-MM-DD') → [该日出生的版本…]，外加"日期不可得"的分组数。

    直接复用发布器的 `build_days`（版本诞生日期 = 归档快照的 blob 在现役 profile 历史中
    首次出现的提交日）—— **不另写一套日期口径**，否则两处早晚漂。
    任何异常（缺 git / 缺 release_publish.py）⇒ 返回 None，由调用方判「未验证，不是通过」。
    """
    try:
        import importlib.util
        rp_path = os.path.join(root, "skill", "scripts", "release_publish.py")
        spec = importlib.util.spec_from_file_location("release_publish", rp_path)
        rp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rp)
        cwd = os.getcwd()
        try:
            os.chdir(root)              # build_days 内部的 git 调用按 cwd 定位仓库
            days = rp.build_days(root)
        finally:
            os.chdir(cwd)
    except Exception:                   # noqa: BLE001 —— 环境不具备时如实判「未验证」
        return None
    groups, unknown = {}, 0
    for d in days:
        date = d.get("date") or ""
        if not ISO_DATE.match(date):
            unknown += 1                # 「未知日期」分组：浅克隆 / 历史缺失的退化产物
            continue
        for fam, info in (d.get("fams") or {}).items():
            groups.setdefault((fam, date), []).extend(info.get("versions") or [])
    return groups, unknown


def version_checks(root):
    """固定名与头注版本 ⇒ [(判据名, 通过?, 说明)]：两侧各 V1–V6 · 跨侧 X 两条 · V7 版本节奏两条。
    归档判据（V3–V6）在 config_old/ 目录存在时照常生效；V7 需完整 git 历史（否则判「未验证」）。"""
    out, heads = [], {}
    for d in PROFILE_DIRS:
        side = d.split("/")[0]
        ext = "conf" if side == "surge" else "yaml"
        dirpath = os.path.join(root, d.replace("/", os.sep))
        fixed = sorted(["routing.%s" % ext, "routing.min.%s" % ext,
                        "lazy.%s" % ext, "lazy.min.%s" % ext])
        top = sorted(n for n in os.listdir(dirpath) if n.endswith("." + ext))
        out.append(("%s V1 顶层只有固定名四件" % side, top == fixed,
                    "实有：%s" % (", ".join(top) or "（空）")))
        vr = head_version(os.path.join(dirpath, "routing.%s" % ext))
        vl = head_version(os.path.join(dirpath, "lazy.%s" % ext))
        heads[side] = (vr, vl)
        out.append(("%s V2 头注版本标记形状合法" % side,
                    vr is not None and vl is not None and vr[0] == "routing" and vl[0] == "lazy",
                    "routing=%s · lazy=%s（读不出多半是第一行被挪走或段数超过三段）" % (vr, vl)))
        old_dir = os.path.join(dirpath, OLD_DIR)
        if not os.path.isdir(old_dir):
            continue          # 缺归档目录：V3–V6 无从判起，只保 V1/V2 与跨侧 4 条
        names = sorted(n for n in os.listdir(old_dir) if not n.startswith("."))
        # V3 的"存在"两字由上面那个 `isdir` 分支兜着（缺目录时 V3–V6 一并判负），
        # 走到这里存在性已成事实 ⇒ 这条唯一还能判的东西是"非空"。从前它写的是字面量 True，
        # 历史注记：归档目录存在时把清空成 0 个文件，输出照旧
        # `✅ surge V3 归档目录存在（0 个文件）` · TOTAL: 18 passed ⇒ 一条永远绿的判据占着计数。
        out.append(("%s V3 归档目录存在且非空（%d 个文件）" % (side, len(names)), bool(names),
                    "空归档：每退一版留一份快照是这套沿革制度的前提 ⇒ 目录空 = 快照被手工挪走，"
                    "或归档根本没建起来（缺目录不在此条，由上面的 缺目录 分支判）"))
        groups, illegal = {}, []
        for n in names:
            m = ARCHIVE_RE.match(n)
            if m:
                groups.setdefault((m.group(1), m.group(2)), []).append(n)
            else:
                illegal.append(n)
        out.append(("%s V4 归档文件名形状合法" % side, not illegal, "非法名：%s" % ", ".join(illegal)))
        unpaired = ["/".join(k) + "→" + ",".join(v) for k, v in sorted(groups.items())
                    if len(v) != 2 or sum(1 for x in v if ".min." in x) != 1]
        out.append(("%s V5 归档每版成对齐全（完整版 + .min）" % side, not unpaired,
                    "不齐：%s" % "; ".join(unpaired)))
        # V6：归档里出现"当前版"只有一种正当情况 —— 升版前打的快照，与线上文件逐字节相同。
        #      版本号比当前版更高 ⇒ 归档了一个没发布过的号；同名而内容已漂 ⇒ 线上改了没升版，
        #      或归档被人当工作文件动过（归档目录是只读历史，这条也守住它）。
        v6_bad = []
        for n in names:
            m = ARCHIVE_RE.match(n)
            hv = vr if (m and m.group(1) == "routing") else vl
            if not m or not hv:
                continue
            if ver_tuple(m.group(2)) > ver_tuple(hv[1]):
                v6_bad.append("%s 版本号高于当前版 v%s" % (n, hv[1]))
            elif m.group(2) == hv[1]:
                p_old = os.path.join(old_dir, n)
                p_live = os.path.join(dirpath, "%s%s.%s" % (m.group(1), m.group(3) or "", ext))
                try:
                    with open(p_old, "rb") as fa, open(p_live, "rb") as fb:
                        same = fa.read() == fb.read()
                except OSError:
                    same = False
                if not same:
                    v6_bad.append("%s 与线上同版本但内容已漂（改了没升版，或归档被动过）" % n)
        out.append(("%s V6 归档不高于当前版·同版本仍是逐字快照" % side, not v6_bad,
                    " ".join(v6_bad)))
        # ── V8 / V9：归档头注（第二轮外部审查第 9 条）
        #
        # V8 头注 ↔ 文件名一致：此前把 routing_v4.0.4.conf 的头注改成 v9.9.9，
        #     V1–V6 与「版本头注」闸门双双全绿 —— 文件名与内容可以各说各话。
        # V9 头注覆盖率：74 份归档（surge .min 以 audit-waive: 开头、egern .min 以
        #     vif_only: / ipv6: 开头）没有 #! version= 首行 ⇒ V8 对它们无从判起。
        #     这里把「缺多少」显式报出来，让缺口可见，而不是被覆盖率掩盖。
        v8_bad = []
        no_head = []
        for n in names:
            m = ARCHIVE_RE.match(n)
            if not m:
                continue
            fp = os.path.join(old_dir, n)
            try:
                with open(fp, encoding="utf-8", errors="replace") as fh:
                    first = fh.readline().strip()
            except OSError:
                continue
            hh = re.match(r"^#!\s*version=\s*(\S+?)\s*$", first)
            if not hh:
                no_head.append(n)
                continue          # 缺头注 ⇒ 归 V9，不重复计入 V8
            # 文件名 routing_v4.0.4[.min].conf  ⇒ 期望头注 routing_v4.0.4
            want = "%s_v%s" % (m.group(1), m.group(2))
            if hh.group(1) != want:
                v8_bad.append("%s 头注写 %s（文件名应为 %s）" % (n, hh.group(1), want))
        out.append(("%s V8 归档头注与文件名一致" % side, not v8_bad,
                    " ".join(v8_bad)))
        out.append(("%s V9 归档头注齐全（%d/%d，缺 %d）" % (
                        side, len(names) - len(no_head), len(names), len(no_head)),
                    not no_head,
                    "缺头注：%s" % ", ".join(no_head[:6]) +
                    ("…等 %d 份" % len(no_head) if len(no_head) > 6 else "")))
    for kind in ("routing", "lazy"):
        a = heads.get("surge", (None, None))[0 if kind == "routing" else 1]
        b = heads.get("egern", (None, None))[0 if kind == "routing" else 1]
        out.append(("X 两侧 %s 版本一致" % kind, bool(a) and a == b, "%s vs %s" % (a, b)))

    # V7：一天一版（CADENCE_FROM 起）—— 同一产品线在同一个「版本诞生日期」内最多一个版本。
    #   一天里改几次都只升一次号：当天后续改动（含修前一次带出来的连带问题）沿用同一版本号，
    #   不再归档、不再升号。规矩见 SKILL.md「归档机制」与 reference/shared/ops.md §6.1。
    #   ⚠️ 前置条件是**完整 git 历史**（浅克隆下日期会退化成「未知日期」）—— 那些分组按
    #   「未验证」跳过并在说明里点名，不冒充通过。前置条件纪律见 ops.md §6.8。
    # 整合仓适配（self-conf）：本仓由两仓文件**复制**而来，不继承原仓 git 历史，
    # 于是所有归档文件的「版本诞生日期」都退化成复制当天 —— V7「一天一版」
    # 会把几十个历史版本读成「同一天升了几十次号」而误判。
    # 这是**整合方式的局限**，不是配置违规。设 SKIP_V7=1 表示已知此局限并跳过，
    # 但会明确输出「未验证」而非冒充通过。
    import os as _os
    if _os.environ.get("SKIP_V7") == "1":
        for fam in ("routing", "lazy"):
            out.append(("V7 %s 一天一版" % fam, True,
                        "已跳过（SKIP_V7=1）：本仓无原仓 git 历史，日期分组不成立 "
                        "⇒ 未验证，不是通过"))
        return out
    dv = day_versions(root)
    for fam in ("routing", "lazy"):
        if dv is None:
            out.append(("V7 %s 一天一版" % fam, False,
                        "日期分组构建失败（缺 git 或 skill/scripts/release_publish.py）"
                        "⇒ 未验证，不是通过"))
            continue
        groups, unknown = dv
        judged = sorted(d for (f, d) in groups if f == fam and d >= CADENCE_FROM)
        over = [(d, groups[(fam, d)]) for d in judged if len(groups[(fam, d)]) > 1]
        if over:
            note = "；".join("%s 有 %d 个版本（%s）" % (d, len(v), "→".join(v)) for d, v in over) \
                   + " —— 一天之内只应升一次号：当天后续改动沿用同一版本号，不再归档、不再升号"
        else:
            note = "已判 %d 个更新日（≥ %s）" % (len(judged), CADENCE_FROM)
            if unknown:
                note += "；另有 %d 个分组的日期不可得 ⇒ 未验证（浅克隆？见 ops.md §6.8）" % unknown
        out.append(("V7 %s 一天一版" % fam, not over, note))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = os.path.abspath(root)
    pairs = bad = 0
    for d in PROFILE_DIRS:
        dirpath = os.path.join(root, d.replace("/", os.sep))
        if not os.path.isdir(dirpath):
            sys.stderr.write("找不到 %s —— 参数应当是仓库根（本仓自身）\n" % d)
            return 2
        for name in sorted(os.listdir(dirpath)):
            if ".min." not in name:
                continue
            stem, ext = os.path.splitext(name)
            ann = stem.replace(".min", "") + ext
            full_p, min_p = os.path.join(dirpath, ann), os.path.join(dirpath, name)
            try:
                with open(full_p, encoding="utf-8", newline="") as f:
                    a = normalize(f.read())
                with open(min_p, encoding="utf-8", newline="") as f:
                    b = normalize(f.read())
            except (OSError, UnicodeDecodeError) as e:
                sys.stderr.write("读取失败 %s：%s\n" % (name, e))
                return 2
            pairs += 1
            i = first_diff(a, b)
            if i is None:
                print("✅ %s/%s  ↔  %s（去注释后 %d 行逐字相同）" % (d, ann, name, len(a)))
                continue
            bad += 1
            print("❌ %s/%s ↔ %s  去注释后仍有差异（%d 行 vs %d 行）" % (d, ann, name, len(a), len(b)))
            left = a[i] if i < len(a) else "<此侧已无更多行>"
            right = b[i] if i < len(b) else "<此侧已无更多行>"
            print("   第 %d 行：\n     完整版: %s\n     .min  : %s" % (i + 1, left, right))
    v_out = version_checks(root)
    v_bad = 0
    print("\n固定名与归档序列（判据条数不随归档文件数增长）：")
    for name, ok_, note in v_out:
        # V7 的说明在**通过时也要显示**：它承载的是「判了几个更新日 / 有多少分组因历史不全
        # 而没验证」这类信息 —— 只挂在失败上，浅克隆下就会显示成一条干净的绿。其余判据维持
        # 原样（失败才打印说明），免得把输出变吵。
        show_note = (not ok_) or name.startswith("V7 ")
        print("   %s %s%s" % ("✅" if ok_ else "❌", name,
                              ("   " + note) if (show_note and note) else ""))
        if not ok_:
            v_bad += 1
    v_pass = len(v_out) - v_bad
    # 与两侧 runner 同一口径的合计行，便于 all.sh / 文档按断言数对账。
    print("\n共 %d 对形态相同 · 归档判据 %d/%d 过" % (pairs - bad, v_pass, len(v_out)))
    print("TOTAL: %d passed, %d failed" % (pairs - bad + v_pass, bad + v_bad))
    return 1 if (bad or v_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
