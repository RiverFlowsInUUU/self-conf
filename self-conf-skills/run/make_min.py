#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`.min` 生成器：把完整版的内容改动搬进精简版，注释与空白按固定规则重排。

    python self-conf-skills/run/make_min.py                    # 只看差异，一个字都不写
    python self-conf-skills/run/make_min.py --check           # 闸门：只查不写，有差异 exit 1
    python self-conf-skills/run/make_min.py --apply            # 写盘（写完立刻自查）
    python self-conf-skills/run/make_min.py --family lazy      # 只处理某一族的四份（默认 all）
    python self-conf-skills/run/make_min.py --selftest         # 自带回归，改这个脚本后要跑它

为什么要它：`.min` 是**订阅端真正下载的那两份**，但仓里一直只有对拍器（`check_min_pair.py`）
没有生成器 —— 改了完整版的配置本体，精简版要人手工同步，全靠 all.sh 第 3 项事后抓。
本脚本把"同步"这一步收进命令，规则只有一条来源：判据在 `check_min_pair.py`，
本脚本 import 它的 `normalize` / `TRAIL` / `WHOLE`，**不复制第二份规则**（改一处漏两处是这仓的老病）。

三侧的规则（2026-09-24 钉 Egern/Surge，2026-10-09 补 clash）：
    clash  精简版 == 完整版**剔掉整行注释**（行尾注释、行尾空白一并去），
           **保留其余每一行原样**（含内部空行与缩进）⇒ 也是纯函数。
           依据（三条，都实测过，缺一不可）：
           ① `build_profiles.py` 正是这么产出 `.min.yaml` 的（`yaml.dump` 同一份
              `final`，YAML dumper 不写注释）——所以「删注释」是与上游生成器
              同构的规则，不是我们发明的；
           ② clash 侧**没有**任何必须留在下载文件里的语义注释：`check_min_pair.py`
              比的是 YAML 对象，注释根本不进比对（gates.md §5.1 明写「别把 Surge
              侧的注意事项搬过来」）；clash 的审计口径也不认 `# audit-waive:`。
           ③ 实测：对仓内四份 clash 文件跑「剔注释」得到的结果与现存
              `*.min.yaml` 正文**逐字节相同** ⇒ 规则被现状背书，不是推测。
           ⚠️ 与 Egern 的差别**只在空行的处理口径**：Egern 压掉全部空行（`normalize`），
              clash 只压**首尾**空行、正文里的空行原样保留。
              实测：现役 clash 完整版里唯一的内部空行在注释块尾部（lazy 第 15 行），
              它在 `.min` 里也不存在（上游是 `_ver + yaml.dump()`，头注紧挨正文）
              ⇒ 两条规则在**现役文件上输出相同**，但规则本身不同、不可互换：
              一旦完整版正文里出现段落空行，clash 必须保留（YAML 里那是排版意图）、
              Egern 必须删掉。S7 用人工样本把这条分岔钉住。
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

# ── 仓库定位与判据复用 ─────────────────────────────────────────
# 本文件在 `self-conf-skills/run/`，对拍器在 `self-conf-skills/gates/` —— 相距一个目录，
# 但**不靠相对层数**定位（那在重组时会断，见 self-conf-skills/lib/paths.py）。
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, "..", "lib"))
sys.path.insert(0, os.path.join(_d, "..", "gates"))
from paths import repo_root  # noqa: E402  靠标志物上溯，不依赖目录层数

REPO_ROOT = repo_root()

from check_min_pair import TRAIL, WHOLE, normalize, head_version   # noqa: E402  判据唯一来源

NL = chr(10)
CRLF = chr(13) + NL
WAIVE_OK = "# audit-waive"            # 必须留在下载文件里的指令行（对拍器按整行注释忽略它）

# 家族 ⇒ 六份形态（完整版在前，精简版在后）
# ⚠️ clash 两族是 2026-10-09 补的，补之前 `clash/profiles/*.min.yaml` **靠手工同步**
#    + `check_min_pair.py` 对拍兜底 —— 那是 gates.md §16.4 登记的第 2 条已知缺口
#    （触发条件写的就是「出现第一次手工同步漏改」）。缺口现在消掉，那条登记也该删。
# ⚠️ 顺序有意义：同一族内完整版必须排在它的 `.min` 前面（下面按对读取）。
PAIRS = {
    "routing": [("surge/profiles/routing.conf", "surge/profiles/routing.min.conf"),
                ("egern/profiles/routing.yaml", "egern/profiles/routing.min.yaml"),
                ("clash/profiles/routing.yaml", "clash/profiles/routing.min.yaml")],
    "lazy": [("surge/profiles/lazy.conf", "surge/profiles/lazy.min.conf"),
             ("egern/profiles/lazy.yaml", "egern/profiles/lazy.min.yaml"),
             ("clash/profiles/lazy.yaml", "clash/profiles/lazy.min.yaml")],
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
    """⇒ (生成的精简版全文, 没能落位的注释列表)。Egern / clash 侧没有注释可留，是纯函数。"""
    if side == "egern":
        return NL.join(normalize(full_text)) + NL, []
    if side == "clash":
        # clash：剔注释，正文**原样保留**（唯一与 Egern 分岔之处，见文件头「三侧的规则」）。
        # 首尾空行要压掉：完整版首行是 `#! version=` 头注（被 WHOLE 当注释剔掉），
        # 而它后面就是注释块尾部那行空行 —— 不压就会出现「头注 + 空行 + 正文」，
        # 与上游 `build_profiles.py` 写的 `.min.yaml`（`_ver` 紧挨 `yaml.dump(...)`）不符。
        rows = []
        for l in full_text.split(NL):
            l = TRAIL.sub("", l)
            if WHOLE.match(l):
                continue
            rows.append(l.rstrip())
        while rows and not rows[0].strip():
            rows.pop(0)
        while rows and not rows[-1].strip():
            rows.pop()
        return NL.join(rows) + NL, []
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
        # `.min` 首行是 `#! version=` 头注（元数据，不是正文）。比对正文时剥掉，
        # 否则加了版本头反而被判「含正文差异」。
        _mtl = mt.split(NL)
        if _mtl and _mtl[0].startswith("#! version="):
            mt = NL.join(_mtl[1:])
        side = full.split("/")[0]
        gen, lost = make_min(ft, mt, side)
        # 自查：生成的精简版与完整版去注释后必须逐字相同 —— 与 all.sh 第 3 项同一条判据，
        # 先在内存里过一遍，别写坏了才发现。
        if normalize(gen) != normalize(ft):
            raise SystemExit("❌ " + mn + "：生成结果与完整版 normalize 后仍不同 —— 规则漏了情形，别写盘")
        rows.append((f, fp, mp, classify(mt, gen)[0], mt, gen, lost))
    return rows


def selftest(root):
    """自带回归：规则的可复现性 + 两条防线。改过本脚本就跑它。"""
    ok = True

    def chk(name, cond, extra=""):
        nonlocal ok
        ok = ok and cond
        print(("   ✅ " if cond else "   ❌ ") + name + ("  " + extra if extra else ""))

    rows = run_once(root, "all")
    # ⚠️ 判内核一律用**路径首段**（`surge/` · `egern/` · `clash/`），
    #    **不要**用扩展名 —— clash 与 Egern 都是 `.yaml`，按扩展名筛会把 clash
    #    混进 Egern 的判据里（S2「逐字节相同」恰好都想成立，但 S6 的 side 会传错）。
    def kern_of(p):
        return p.split(os.sep)[-3] if os.sep in p else p

    chk("S1 六份都能生成且 normalize 自查通过", len(rows) == 6)
    chk("S2 Egern 两份是纯函数（与仓内现状逐字节相同）",
        all(c == "same" for f, a, b, c, m, g, l in rows if kern_of(a) == "egern"))
    chk("S2b clash 两份也是纯函数（剔注释不改空行，与仓内现状逐字节相同）",
        all(c == "same" for f, a, b, c, m, g, l in rows if kern_of(a) == "clash"))
    chk("S3 Surge 两份的差异不含正文（只有空白/注释落位）",
        all(c in ("same", "blank") for f, a, b, c, m, g, l in rows if b.endswith(".conf")))
    chk("S4 豁免指令留在下载文件里（对拍器不认它，审计认）",
        all((WAIVE_OK in g) == (WAIVE_OK in m) for f, a, b, c, m, g, l in rows
            if b.endswith(".conf")))
    # S5：锚点消失 ⇒ 必须报出来，不能把注释随便插进正文（拿真档删掉 [Proxy Group] 那一行做反向实测）
    rp = os.path.join(root, "surge", "profiles", "routing.conf")
    mp0 = os.path.join(root, "surge", "profiles", "routing.min.conf")
    ft = [l for l in read(rp).split(NL) if l != "[Proxy Group]"]
    _, lost = make_min(NL.join(ft), read(mp0), "surge")
    chk("S5 锚点被删时不猜位置，改为上报", len(lost) == 2,
        "报出 %d 条（钉在 [Proxy Group] 上的那两条「怎么加节点」）" % len(lost))
    # S6：空白钉死之后再拿生成结果当"现有精简版"重跑一遍 ⇒ 必须逐字节幂等
    # ⚠️ side 取路径首段，与 run_once 同源 —— 用扩展名判会把 clash 当成 egern（都 .yaml），
    #    而 clash 恰恰**不许**压空行，传错 side 这条幂等判据就名存实亡。
    idem = all(make_min(read(fp), gen, kern_of(fp))[0] == gen
               for f, fp, mp, c, mt, gen, l in rows)
    chk("S6 生成一次后再钉一次 ⇒ 逐字节幂等", idem)
    # S7：clash 与 Egern 规则必须真的分岔 —— 若哪天有人把 clash 也塞进 normalize，
    #    这条会红。这不是重复 S6：S6 只证明「幂等」，把三种规则全换成同一个同样幂等。
    cfp = os.path.join(root, "clash", "profiles", "lazy.yaml")
    cft = read(cfp)
    c_keep, _ = make_min(cft, "", "clash")
    c_flat = NL.join(normalize(cft)) + NL
    # 实测事实（2026-10-09 拿仓内 clash 四份实测）：clash **完整版**里唯一的内部空行是
    # 注释块之后那一行（lazy 第 15 行），而它属于注释块的尾巴 —— 上游 `_ver + yaml.dump()`
    # 写的 `.min` 里没有它 ⇒ 两条规则在**现役文件**上输出相同，S7 不能拿它分岔。
    # 所以判别力改为：**人工构造**一份含内部空行的样本，两条规则必须给出不同结果。
    # 这才是「clash 不压空行」这条规则的真判据 —— 现役文件恰好不触发它。
    probe = NL.join(["# 注释", "", "a: 1", "", "b: 2"]) + NL
    p_clash = make_min(probe, "", "clash")[0]
    p_egern = make_min(probe, "", "egern")[0]
    chk("S7 clash 与 Egern 规则真的分岔：内部空行 clash 留存、Egern 压掉",
        p_clash != p_egern
        and p_clash == NL.join(["a: 1", "", "b: 2"]) + NL
        and p_egern == NL.join(["a: 1", "b: 2"]) + NL,
        "clash=%r · Egern=%r" % (p_clash, p_egern))
    # S8：clash 侧**不许**出现 lost —— 它没有需要继承的语义注释（gates.md §5.1：
    # 「别把 Surge 侧的注意事项搬过来」）。若哪天 clash 规则误走了 Surge 分支，
    # 这里会红（Surge 分支会去读 .min 的注释并可能报 lost）。
    chk("S8 clash 走纯函数分支，不继承注释、不报 lost",
        all(l == [] for f, a, b, c, m, g, l in rows if kern_of(a) == "clash"))
    print(("ALL GREEN" if ok else "有判负") + " · 自带回归 8 条")
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
        drifted = [(rel(mp), c, len(lost)) for f, fp, mp, c, mt, gen, lost in rows
                   if c != "same" or lost]
        if drifted:
            for mp, c, n in drifted:
                print("❌ " + mp + "：" + ("注释锚点丢失 %d 条" % n if n else kinds[c]))
            print("闸门判定：.min 与生成器输出不一致 —— 跑 make_min.py --apply 同步后一并提交")
            return 1
        print("✅ 六份 .min 与生成器输出逐字一致（--check）")
        return 0
    if not a.apply:
        print("（计划模式：一个字都不写。加 --apply 才落盘）" + NL)
    for f, fp, mp, c, mt, gen, lost in rows:
        n_cur, n_gen = len(mt.split(NL)), len(gen.split(NL))
        print("%-34s %s（%d → %d 行）· %s" % (
            rel(mp), kinds[c], n_cur, n_gen,
            "正文未动" if c != "body" else "⚠️ 精简版与完整版的正文已漂移，这次会把精简版拉回完整版"))
        for l in lost:
            print("      ⚠️ 这条注释的锚点没了，生成器没地方放它，要人决定去处：" + l.strip()[:68])
    if not a.apply:
        print(NL + "确认后加 --apply")
        return 0
    # 全批次先验一遍再写：第一条能写、第二条没能落位 ⇒ 别留下半批已改的文件
    bad = [(mp, n) for f, fp, mp, c, mt, gen, lost in rows if lost]
    if bad:
        for mp, n in bad:
            print("❌ " + rel(mp) + "：有 %d 条注释没能落位" % n)
        print("整批一个字节未写 —— 先按上面的提示定规则")
        return 1
    for f, fp, mp, c, mt, gen, lost in rows:
        if mt == gen:
            print("未动 " + rel(mp) + "（已是规则的输出）")
            continue
        # 保留 `#! version=` 头注：`.min` 必须带与完整版**同一行**头注
        # （check_version_header 的 V3 判据）。生成器只产出正文，头注在此补回。
        _hv = ""
        if os.path.isfile(fp):
            with io.open(fp, encoding="utf-8") as _fh:
                _first = _fh.readline()
            if _first.startswith("#! version="):
                _hv = _first.rstrip(chr(10)) + NL
        # `with` 收口（A-8）：写完必须确定性关闭，不依赖引用计数。
        with io.open(mp, "w", encoding="utf-8", newline="") as f:
            f.write(_hv + gen)
        print("已写 " + rel(mp))
    print(NL + "验收：python self-conf-skills/gates/check_min_pair.py（拿完整版逐字对拍这几份）")
    return 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    sys.exit(main())
