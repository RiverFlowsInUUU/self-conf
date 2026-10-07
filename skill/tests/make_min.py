#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`.min` 生成器：把完整版的内容改动搬进精简版，注释与空白按固定规则重排。

    python skill/tests/make_min.py                    # 只看差异，一个字都不写
    python skill/tests/make_min.py --check           # 闸门：只查不写，有差异 exit 1
    python skill/tests/make_min.py --apply            # 写盘（写完立刻自查）
    python skill/tests/make_min.py --family lazy      # 只处理某一族的四份（默认 all）
    python skill/tests/make_min.py --selftest         # 自带回归，改这个脚本后要跑它

为什么要它：`.min` 是**订阅端真正下载的那两份**，但仓里一直只有对拍器（`check_min_pair.py`）
没有生成器 —— 改了完整版的配置本体，精简版要人手工同步，全靠 all.sh 第 3 项事后抓。
本脚本把"同步"这一步收进命令，规则只有一条来源：判据在 `check_min_pair.py`，
本脚本 import 它的 `normalize` / `TRAIL` / `WHOLE`，**不复制第二份规则**（改一处漏两处是这仓的老病）。

两侧的规则（2026-09-24 实测钉下来的）：
    Egern  精简版 == 完整版去注释去空行去行尾空白，逐字节可复现 ⇒ 纯函数，直接生成。
    Surge  精简版里**留着几条注释**：一条 `# audit-waive:`（审计豁免，必须留在下载文件里，
           否则第 2 项的 `--strict` 会把它当未豁免判负）+ `[Proxy Group]` 前那两行"怎么加节点"。
           所以规则是：正文从完整版重算，**注释行从现有精简版继承**，每条注释钉在它后面
           第一条正文行（锚点）上；锚点在正文里消失了 ⇒ 不猜位置，**报出来要人定**。
           空白钉成规范形态：连续空行压成一行、首尾不留空行、头部注释后留一行空行。

⚠️ 第一次跑会看到 Surge 两份报「仅空白差异」：现存 `.min` 是手工维护的，空行落点和规则不完全一致。
   `--apply` 一次之后就是纯函数了 —— 这类改动只动空白，正文逐字不变（对拍器按 normalize 判，
   前后都绿），但订阅下载到的**字节**确实变了，所以升版本号并在提交信息里写明。

它**不**做：不改完整版本身；
   不判 `.min` 内容对不对（那是 `check_min_pair.py` + 各侧回归的活，本脚本只负责"搬得动"）。
   ⚠️ 唯一要预先说清的连带：若某族当前版已有**同号快照**（现在只有 lazy 的
   `lazy_v1.0.*` 种子），写盘就会让对拍器 V6 判负 —— 那是设计好的"内容改了没升版"告警，
   本脚本只在计划里点名提醒，处置办法是升版（改头注 `#! version=`），不是代它改历史。

⚠️ 换行：所有生成结果按 LF 写（仓根 `.gitattributes` 已把检出钉成 `eol=lf`）；
   读入时先归一化 CRLF，判据不受设备影响。
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 仓库根：本文件在 <根>/skill/tests/ ⇒ 上溯两级。判据从同目录的对拍器 import，不复制规则。
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from check_min_pair import TRAIL, WHOLE, normalize, head_version, OLD_DIR   # noqa: E402  判据唯一来源

NL = chr(10)
CRLF = chr(13) + NL
WAIVE_OK = "# audit-waive"            # 必须留在下载文件里的指令行（对拍器按整行注释忽略它）

# 家族 ⇒ 四份形态（完整版在前，精简版在后）
PAIRS = {
    "routing": [("surge/profiles/routing.conf", "surge/profiles/routing.min.conf"),
                ("egern/profiles/routing.yaml", "egern/profiles/routing.min.yaml")],
    "lazy": [("surge/profiles/lazy.conf", "surge/profiles/lazy.min.conf"),
             ("egern/profiles/lazy.yaml", "egern/profiles/lazy.min.yaml")],
}


def read(p):
    return io.open(p, encoding="utf-8", newline="").read().replace(CRLF, NL)


def squeeze(lines):
    """连续空行压成一行 + 去掉首尾空行（规范空白形态）。"""
    out = []
    for l in lines:
        if not l.strip():
            if out and out[-1].strip():
                out.append("")
        else:
            out.append(l)
    while out and not out[-1].strip():
        out.pop()
    return out


def body_of(full_text):
    """完整版的正文：去整行注释、去行尾注释、去行尾空白，再压空白。"""
    rows = []
    for l in full_text.split(NL):
        l = TRAIL.sub("", l)
        if WHOLE.match(l):
            continue
        rows.append(l.rstrip())
    return squeeze(rows)


def keeps_of(min_text):
    """现有精简版里的整行注释 ⇒ [(注释, 锚点)]；锚点 = 其后第一条正文行，末段之后为 None。"""
    ls = min_text.split(NL)
    out = []
    for i, l in enumerate(ls):
        if not WHOLE.match(l):
            continue
        anchor = next((x.strip() for x in ls[i + 1:] if x.strip() and not WHOLE.match(x)), None)
        out.append((l.rstrip(), anchor))
    return out


def make_min(full_text, min_text, side):
    """⇒ (生成的精简版全文, 没能落位的注释列表)。Egern 侧没有注释可留，是纯函数。"""
    if side == "egern":
        return NL.join(normalize(full_text)) + NL, []
    body = body_of(full_text)
    by_anchor = {}
    for comment, anchor in keeps_of(min_text):
        by_anchor.setdefault(anchor, []).append(comment)
    out = []
    if body:
        head = by_anchor.pop(body[0], [])
        if head:
            out.extend(head)
            out.append("")
    for i, line in enumerate(body):
        out.append(line)
        nxt = body[i + 1].strip() if i + 1 < len(body) else None
        if nxt and nxt in by_anchor:
            out.extend(by_anchor.pop(nxt))
    lost = [c for cs in by_anchor.values() for c in cs]
    return NL.join(out) + NL, lost


def classify(cur, gen):
    """差异分类：'same' · 'blank'（只有空行位置不同，正文逐字相同）· 'body'（正文有增删改）。"""
    if cur == gen:
        return "same", 0, 0
    a = [x for x in cur.split(NL) if x.strip()]
    b = [x for x in gen.split(NL) if x.strip()]
    if a == b:
        n = sum(1 for x, y in zip(cur.split(NL), gen.split(NL)) if x != y)
        return "blank", n, abs(len(cur.split(NL)) - len(gen.split(NL)))
    import difflib
    d = [x for x in difflib.unified_diff(a, b, lineterm="", n=0)
         if x.startswith(("+", "-")) and not x.startswith(("+++", "---"))]
    return "body", sum(1 for x in d if x.startswith("-")), sum(1 for x in d if x.startswith("+"))


def targets(fam):
    fams = list(PAIRS) if fam == "all" else [fam]
    out = []
    for f in fams:
        for full, mn in PAIRS[f]:
            out.append((f, full, mn))
    return out


def run_once(root, fam):
    """⇒ [(家族, 完整路径, 精简路径, 分类, 现文本, 生成文本, 丢位注释)]；生成即自查一次 normalize。"""
    rows = []
    for f, full, mn in targets(fam):
        fp, mp = os.path.join(root, *full.split("/")), os.path.join(root, *mn.split("/"))
        if not (os.path.isfile(fp) and os.path.isfile(mp)):
            raise SystemExit("❌ 缺文件：" + (full if not os.path.isfile(fp) else mn)
                             + "（固定名是永久订阅地址，不能被改名或挪走）")
        ft, mt = read(fp), read(mp)
        side = full.split("/")[0]
        gen, lost = make_min(ft, mt, side)
        # 自查：生成的精简版与完整版去注释后必须逐字相同 —— 与 all.sh 第 3 项同一条判据，
        # 先在内存里过一遍，别写坏了才发现。
        if normalize(gen) != normalize(ft):
            raise SystemExit("❌ " + mn + "：生成结果与完整版 normalize 后仍不同 —— 规则漏了情形，别写盘")
        rows.append((f, fp, mp, classify(mt, gen)[0], mt, gen, lost, snap_path(fp, mp)))
    return rows


def snap_path(fp, mp):
    """这份 `.min` 的**同版本归档快照**路径 ⇒ str | None（存在才给路径）。

    用途只有一个：写盘前提醒。归档是只读历史，本脚本不碰它 —— 而 V6 把"与线上同号的归档"
    定义成线上文件的逐字节快照，所以改了 `.min` 又存在同号快照时，对拍器必然判负。
    那条判负是**设计好的告警**（内容改了却没升版），不是要脚本代它改历史。
    """
    hv = head_version(fp)
    if not hv:
        return None
    fam, ver = hv
    p = os.path.join(os.path.dirname(mp), OLD_DIR,
                     "%s_v%s.min.%s" % (fam, ver, mp.rsplit(".", 1)[1]))
    return p if os.path.isfile(p) else None


def selftest(root):
    """自带回归：规则的可复现性 + 两条防线。改过本脚本就跑它。"""
    ok = True

    def chk(name, cond, extra=""):
        nonlocal ok
        ok = ok and cond
        print(("   ✅ " if cond else "   ❌ ") + name + ("  " + extra if extra else ""))

    rows = run_once(root, "all")
    chk("S1 四份都能生成且 normalize 自查通过", len(rows) == 4)
    chk("S2 Egern 两份是纯函数（与仓内现状逐字节相同）",
        all(c == "same" for f, a, b, c, m, g, l, s in rows if b.endswith(".yaml")))
    chk("S3 Surge 两份的差异不含正文（只有空白/注释落位）",
        all(c in ("same", "blank") for f, a, b, c, m, g, l, s in rows if b.endswith(".conf")))
    chk("S4 豁免指令留在下载文件里（对拍器不认它，审计认）",
        all((WAIVE_OK in g) == (WAIVE_OK in m) for f, a, b, c, m, g, l, s in rows
            if b.endswith(".conf")))
    # S5：锚点消失 ⇒ 必须报出来，不能把注释随便插进正文（拿真档删掉 [Proxy Group] 那一行做反向实测）
    rp = os.path.join(root, "surge", "profiles", "routing.conf")
    mp0 = os.path.join(root, "surge", "profiles", "routing.min.conf")
    ft = [l for l in read(rp).split(NL) if l != "[Proxy Group]"]
    _, lost = make_min(NL.join(ft), read(mp0), "surge")
    chk("S5 锚点被删时不猜位置，改为上报", len(lost) == 2,
        "报出 %d 条（钉在 [Proxy Group] 上的那两条「怎么加节点」）" % len(lost))
    # S6：空白钉死之后再拿生成结果当"现有精简版"重跑一遍 ⇒ 必须逐字节幂等
    idem = all(make_min(read(fp), gen, "egern" if mp.endswith(".yaml") else "surge")[0] == gen
               for f, fp, mp, c, mt, gen, l, s in rows)
    chk("S6 生成一次后再钉一次 ⇒ 逐字节幂等", idem)
    # S7：同号归档快照 ⇒ 只点名、绝不写盘（归档只读；V6 的判负留给升版处置，不由生成器代改历史）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "profiles")
        od = os.path.join(d, OLD_DIR)
        os.makedirs(od)
        full, mn = os.path.join(d, "lazy.conf"), os.path.join(d, "lazy.min.conf")
        io.open(full, "w", encoding="utf-8", newline="").write("#! version=lazy_v9.9" + NL + "X" + NL)
        none_case = snap_path(full, mn)
        p99, p98 = os.path.join(od, "lazy_v9.9.min.conf"), os.path.join(od, "lazy_v9.8.min.conf")
        for p in (p99, p98):
            io.open(p, "wb").write(b"OLD" + NL.encode())
        got = snap_path(full, mn)
        kept = all(io.open(p, "rb").read() == b"OLD" + NL.encode() for p in (p99, p98))
        chk("S7 同号快照只点名不写盘（无⇒None · 有⇒该版路径，不认低版本）",
            none_case is None and got == p99 and kept,
            "无快照→%s · 有快照→%s · 归档字节未动→%s" % (none_case, os.path.basename(got or ""), kept))
    print(("ALL GREEN" if ok else "有判负") + " · 自带回归 7 条")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="`.min` 生成器（默认只出差异，--apply 才写盘）")
    ap.add_argument("--family", choices=("routing", "lazy", "all"), default="all")
    ap.add_argument("--root", default=REPO_ROOT,
                    help="仓库根（默认取本文件位置往上两级 ⇒ 任何克隆、任何 cwd 都能跑）")
    ap.add_argument("--apply", action="store_true", help="写盘")
    ap.add_argument("--check", action="store_true",
                    help="闸门模式：只查不写，.min 与生成器输出有任何差异即 exit 1（CI / verify_all 用）")
    ap.add_argument("--selftest", action="store_true", help="跑自带回归（不写盘）")
    a = ap.parse_args()

    if a.selftest:
        return selftest(a.root)
    if a.check and a.apply:
        raise SystemExit("--check 与 --apply 互斥：check 只查不写")
    rows = run_once(a.root, a.family)
    rel = lambda p: os.path.relpath(p, a.root).replace(os.sep, "/")
    kinds = {"same": "已同步", "blank": "仅空白差异", "body": "含正文差异"}
    if a.check:
        # 0929 修复：旧 CI 是「计划模式(恒 exit 0) + git diff(不写盘恒空)」——永远绿的空操作。
        # --check 直接比对磁盘 .min 与生成器输出：blank 也算漂移（闸门意图就是字节级一致），
        # 注释锚点丢失（lost）一并判负（连 --apply 都会拒写的情形）。
        drifted = [(rel(mp), c, len(lost)) for f, fp, mp, c, mt, gen, lost, snap in rows
                   if c != "same" or lost]
        if drifted:
            for mp, c, n in drifted:
                print("❌ " + mp + "：" + ("注释锚点丢失 %d 条" % n if n else kinds[c]))
            print("闸门判定：.min 与生成器输出不一致 —— 跑 make_min.py --apply 同步后一并提交")
            return 1
        print("✅ 四份 .min 与生成器输出逐字一致（--check）")
        return 0
    if not a.apply:
        print("（计划模式：一个字都不写。加 --apply 才落盘）" + NL)
    for f, fp, mp, c, mt, gen, lost, snap in rows:
        n_cur, n_gen = len(mt.split(NL)), len(gen.split(NL))
        print("%-34s %s（%d → %d 行）· %s" % (
            rel(mp), kinds[c], n_cur, n_gen,
            "正文未动" if c != "body" else "⚠️ 精简版与完整版的正文已漂移，这次会把精简版拉回完整版"))
        for l in lost:
            print("      ⚠️ 这条注释的锚点没了，生成器没地方放它，要人决定去处：" + l.strip()[:68])
        if snap and (mt != gen):
            print("      ⚠️ " + rel(mp) + " 在归档里有同号快照 " + rel(snap)
                  + "，本脚本不碰它 ⇒ 对拍器 V6 会判负（'改了没升版'）。"
                    "处置：升版（改四份 profile 头注 `#! version=`），别手改归档。")
    if not a.apply:
        print(NL + "确认后加 --apply")
        return 0
    # 全批次先验一遍再写：第一条能写、第二条没能落位 ⇒ 别留下半批已改的文件
    bad = [(mp, n) for f, fp, mp, c, mt, gen, lost, s in rows if lost]
    if bad:
        for mp, n in bad:
            print("❌ " + rel(mp) + "：有 %d 条注释没能落位" % n)
        print("整批一个字节未写 —— 先按上面的提示定规则（归档同样没动）")
        return 1
    for f, fp, mp, c, mt, gen, lost, snap in rows:
        if mt == gen:
            print("未动 " + rel(mp) + "（已是规则的输出）")
            continue
        # `with` 收口（A-8）：写完必须确定性关闭，不依赖引用计数。
        with io.open(mp, "w", encoding="utf-8", newline="") as f:
            f.write(gen)
        print("已写 " + rel(mp))
    print(NL + "验收：python skill/tests/check_min_pair.py（拿完整版逐字对拍这几份）")
    return 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    sys.exit(main())
