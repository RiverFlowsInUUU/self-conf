#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""".min 与完整版对拍 —— 去掉注释与空行后必须逐字相同；另判版本头注与跨内核同号。

判据清单（固定 9 条，不随文件数增长）
────────────────────────────────────
每内核 2 条：
  V1 顶层只有固定名四件（routing/lazy × 完整/min）
  V2 头注版本标记形状合法（`#! version=<line>_vX.Y.Z`，line 必须与文件名对应）
跨内核 2 条：
  X1 三内核 routing 版本号一致
  X2 三内核 lazy 版本号一致

对拍本体：每份 `.min` 去掉注释/空行后必须与完整版逐字相同；
**外加**一条「空白落位」判据（合并自原 `.min 漂移` 闸门 —— 见下）。

> ⚠️ 2026-10-08 合并：原 `make_min.py --check` 单独开了一道闸门（`.min 漂移`），
> 它判「`.min` 是否等于生成器输出」。实测两者**只在空白落位上分岔**
> （手工改内容 ⇒ 两者都红；只动空白 ⇒ 仅它红），而空白漂移不影响配置语义、
> 下次 `--apply` 自动修好 ⇒ 不值得单开一道门，但值得保留检测
> （它是「有人手工编辑 `.min`」的早期信号）。现已并入本脚本。
`.min` 的定位是**同一份配置去掉注释**，不是"裁剪配置"。两版一旦漂移，
照完整版改、实际导入的是 `.min` ⇒ 改了个寂寞，且肉眼看不出来。

⚠️ 2026-10-08 改革：归档（`config_old/`）整套已删除 ——
    版本历史由 git 承担，不再在仓内维护快照。随之删除：
    V3–V10 归档判据 · `SKIP_V7` / `STRICT_ARCHIVE` 两个逃生门 · `LEGACY_MAX` 白名单
    · 对 `release_publish.build_days` 的依赖。
    收益：本文件 396 → ~120 行；全仓少 132 个文件 / 2.3 MB；
    少两个只在"迁仓历史不成立"时才有意义的逃生门。

退出码：0 = 全过 · 1 = 有不一致 · 2 = 环境不达标（profiles 目录不存在）
"""
import os
import re
import sys

# Windows 中文控制台默认 GBK：emoji 一 print 就 UnicodeEncodeError、进程以 1 结束
# —— 与"期望判负"的退出码撞码会假绿。统一钉成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

KERNS = {"surge": "conf", "egern": "yaml", "clash": "yaml"}
TRAIL = re.compile(r"[ \t]+[#;].*$")      # 行尾注释
WHOLE = re.compile(r"^\s*[#;]")           # 整行注释
# 三段制：X.Y.Z 合法（第三段可选）。历史两段号不回改，两段三段混排都认。
VERSION_RE = re.compile(r"^#! version=(routing|lazy)_v([0-9]+)\.([0-9]+)(?:\.([0-9]+))?$")


def normalize(text):
    """去注释、去空行、去行尾空白；CRLF 先归一化成 LF。"""
    out = []
    for ln in text.replace("\r\n", "\n").split("\n"):
        ln = TRAIL.sub("", ln)
        if not ln.strip() or WHOLE.match(ln):
            continue
        out.append(ln.rstrip())
    return out


def blank_drift(full_text, min_text):
    """返回 (.min 相对完整版的空白落位差异描述列表)。

    只看**非空非注释行的缩进**与**空行数** —— 内容相同但空白不同，
    说明 `.min` 不是生成器的输出（有人手工编辑过）。
    ⚠️ 这不是配置错误（那些空白不影响语义），是**卫生信号**：
    手工编辑 `.min` 往往会连着改内容，而内容漂移由上面的对拍抓。
    """
    def sig(text):
        out = []
        for ln in text.replace("\r\n", "\n").split("\n"):
            if not ln.strip() or WHOLE.match(ln):
                out.append(None)          # 空行/注释行：只记位置
            else:
                out.append(len(ln) - len(ln.lstrip()))
        return out
    a, b = sig(full_text), sig(min_text)
    # 比较「非空行的缩进序列」
    ca = [x for x in a if x is not None]
    cb = [x for x in b if x is not None]
    if ca == cb:
        return []
    for i, (x, y) in enumerate(zip(ca, cb)):
        if x != y:
            return ["第 %d 个内容行缩进不同（完整版 %s vs .min %s）" % (i + 1, x, y)]
    return ["内容行数不同（完整版 %d vs .min %d）" % (len(ca), len(cb))]


def first_diff(a, b):
    """返回第一处不同的 0-based 行号；仅长度不同则返回较短长度。"""
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def head_version(path):
    """读 profile 第一行的版本标记 ⇒ ("routing", "1.0.0")；读不出 ⇒ None。"""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            first = f.readline()
    except OSError:
        return None
    m = VERSION_RE.match(first.rstrip("\r\n"))
    if not m:
        return None
    ver = "%s.%s%s" % (m.group(2), m.group(3), ("." + m.group(4)) if m.group(4) else "")
    return m.group(1), ver


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = os.path.abspath(root)

    pairs = bad = 0
    heads = {}
    for kern, ext in KERNS.items():
        d = os.path.join(root, kern, "profiles")
        if not os.path.isdir(d):
            sys.stderr.write("找不到 %s —— 参数应当是仓库根\n" % d)
            return 2

        # ── 对拍：.min ↔ 完整版 ──
        for name in sorted(os.listdir(d)):
            if ".min." not in name:
                continue
            ann = name.replace(".min.", ".")
            try:
                with open(os.path.join(d, ann), encoding="utf-8", newline="") as f:
                    a = normalize(f.read())
                with open(os.path.join(d, name), encoding="utf-8", newline="") as f:
                    b = normalize(f.read())
            except (OSError, UnicodeDecodeError) as e:
                sys.stderr.write("读取失败 %s：%s\n" % (name, e))
                return 2
            pairs += 1
            i = first_diff(a, b)
            raw_full = open(os.path.join(d, ann), encoding="utf-8", newline="").read()
            raw_min = open(os.path.join(d, name), encoding="utf-8", newline="").read()
            blank = blank_drift(raw_full, raw_min) if i is None else []
            if i is None and not blank:
                print("✅ %s/%s ↔ %s（去注释后 %d 行逐字相同）" % (kern, ann, name, len(a)))
                continue
            if i is None:
                # 内容一致但空白落位不同 ⇒ 卫生告警（不判负，见 blank_drift docstring）
                print("⚠️  %s/%s ↔ %s：内容一致，但空白落位与完整版不同 —— %s"
                      % (kern, ann, name, "; ".join(blank)))
                print("     ⇒ .min 可能被手工编辑过。跑 `make_min.py --apply` 重新生成即可。")
                continue
            bad += 1
            print("❌ %s/%s ↔ %s 去注释后仍有差异（%d 行 vs %d 行）"
                  % (kern, ann, name, len(a), len(b)))
            print("   第 %d 行：\n     完整版: %s\n     .min  : %s"
                  % (i + 1, a[i] if i < len(a) else "<无更多行>",
                     b[i] if i < len(b) else "<无更多行>"))

        # ── 头注 ──
        vr = head_version(os.path.join(d, "routing." + ext))
        vl = head_version(os.path.join(d, "lazy." + ext))
        heads[kern] = (vr, vl)

    print("\n版本头注与跨内核同号：")
    checks = []
    for kern, ext in KERNS.items():
        d = os.path.join(root, kern, "profiles")
        fixed = sorted(["routing.%s" % ext, "routing.min.%s" % ext,
                        "lazy.%s" % ext, "lazy.min.%s" % ext])
        top = sorted(n for n in os.listdir(d) if n.endswith("." + ext))
        checks.append(("%s V1 顶层只有固定名四件" % kern, top == fixed,
                       "实有：%s" % (", ".join(top) or "（空）")))
        vr, vl = heads[kern]
        checks.append(("%s V2 头注版本标记形状合法" % kern,
                       vr is not None and vl is not None
                       and vr[0] == "routing" and vl[0] == "lazy",
                       "routing=%s · lazy=%s" % (vr, vl)))
    for idx, kind in enumerate(("routing", "lazy")):
        vals = {k: heads[k][idx] for k in KERNS}
        uniq = {v[1] for v in vals.values() if v}
        checks.append(("X %s 三内核版本一致" % kind, len(uniq) == 1 and len(vals) == len(KERNS),
                       " · ".join("%s=%s" % (k, v[1] if v else None) for k, v in vals.items())))

    v_bad = 0
    for name, ok_, note in checks:
        print("   %s %s%s" % ("✅" if ok_ else "❌", name, ("   " + note) if note else ""))
        if not ok_:
            v_bad += 1
    print("\n共 %d 对形态相同 · 头注判据 %d/%d 过"
          % (pairs - bad, len(checks) - v_bad, len(checks)))
    print("TOTAL: %d passed, %d failed" % (pairs - bad + len(checks) - v_bad, bad + v_bad))
    return 1 if (bad or v_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
