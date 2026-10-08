#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""换设备可移植性检查：只读仓库自身的 tracked 文件，不需要任何其他仓库在场。

为什么要有这一项：本仓的使用方式承诺的是「任何一台机器 clone → 直接改 → 推上去，
双端一致」。会悄悄破坏这件事的只有两类东西——**同一份 commit 在不同机器上落盘成不同字节**，
以及**换个机器就打不开/打错名字的路径**。两类都能在纯静态下判死，所以固化成检查。

规则清单（每条 = 1 个断言，**共 20 条、不随文件数增长**）：
    E1 .gitattributes 在场，且把 `*` 钉成 `text=auto eol=lf`   —— 系统级 autocrlf=true 会被它覆盖
    E2 工作树文本文件零 CRLF                                   —— 磁盘字节 == 提交字节 == raw 字节的前提
    E2b 工作树文本文件零孤立 CR（老 Mac 行尾，同样破坏按 `\n` 写的正则）
    （前置）被跟踪文件全部存在于工作树 —— 缺任何一个即退回退出码 2，不静默跳过
    E3 工作树文本文件零 BOM                                   —— BOM 会让 shebang 与 YAML 头解析当场失效
    N1 所有路径为 Unicode NFC                                 —— macOS 会以 NFD 落盘，同一名字变两个文件
    N2 无 Windows/macOS 非法字符 `\\ / : * ? " < > |`
    N3 无 Windows 保留设备名（CON / PRN / AUX / NUL / COMn / LPTn）
    N4 路径段无首尾空格                                        —— Windows 静默剥掉，两边就对不上
    N4b 路径段无尾点                                           —— 同上，且 git 里留着它 checkout 会失败
    N5 大小写折叠后无冲突                                      —— Windows 的 core.ignorecase=true 会让后者覆盖前者
    N6 机器消费的路径纯 ASCII（skill/ · profiles/ · scripts/ · tests/ · icons/ · 根文件）
       人读的详解正文（docs/）允许中文，且必须过 N1
    L1 相对路径 ≤ 120 字符                                    —— Windows MAX_PATH 260，给 clone 目录留余量
    H1 无单机残留被跟踪（__pycache__ · *.pyc · .DS_Store · Thumbs.db · desktop.ini · *.bak …）
    H2 零字节跟踪文件                                          —— 通常是上一次写入中断的壳
    H3 无符号链接                                              —— 在 Windows 上 checkout 出来就是普通文本文件
    H3b 无 submodule                                           —— 换机器后 clone 下来是空目录，检查跟着失效
    H4 .gitignore 对上述单机残留与 OS 垃圾文件有兜底
    S1 每个 .sh 的首行是 `#!/` shebang                            —— 换机器后行首多了空格/BOM 就跑不起来了
    M1 以 `---` 开头的 .md 其 frontmatter 用第二条 `---` 闭合      —— 未闭合会让整份头部解析崩
    E4 脚本 print 非 GBK 字符者必有输出编码保护                    —— Windows cp936 管道路径下会崩成退出码 1（假绿）

退出码：0 全绿 · 1 有判负 · 2 前置环境不达标（不在 git 仓库里 / 拿不到 tracked 清单）
"""

import ast
import os
import re
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))          # <仓根>/skill/tests
ROOT = os.path.dirname(os.path.dirname(HERE))               # → skill → 仓根

ILLEGAL = set('\\:*?"<>|')
WIN_RESERVED = {"CON", "PRN", "AUX", "NUL"}
WIN_RESERVED |= {"COM%d" % i for i in range(1, 10)}
WIN_RESERVED |= {"LPT%d" % i for i in range(1, 10)}
# ⚠️ 自检：清单里不许留下**未格式化**的模板串。
#    2026-09-25 实测：上面那行原本写成 `{"LPT%d" for i in ...}`（漏了 `% i`），
#    于是加进去的是字面量 `LPT%d` 而不是 `LPT1`…`LPT9` —— N3 声称覆盖 LPTn，实际一个都不判。
#    这类"集合内容写错"靠自带回归判，
#    所以在源头立一条 fail-loud 自检：带 `%` 的名字一定是漏了格式化。
if any("%" in n for n in WIN_RESERVED):
    raise SystemExit("❌ 前置：WIN_RESERVED 里有未格式化的模板串 %s ⇒ 检查集合推导式是不是漏了 `%% i`"
                     % sorted(n for n in WIN_RESERVED if "%" in n))
TEXT_EXT = (".md", ".py", ".sh", ".conf", ".yaml", ".yml", ".txt", ".list",
            ".json", ".js", ".html", ".gitignore", ".gitattributes")
BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".icns", ".mmdb", ".pcap",
              ".p12", ".pfx", ".pem", ".key", ".crt")
# 这些前缀下的路径必须纯 ASCII：脚本、配置、图标、测试、fixture 都是被程序消费的
MACHINE_PREFIXES = ("skill/", "icons/", "surge/profiles/", "egern/profiles/",
                    "surge/scripts/", "egern/scripts/", "surge/tests/", "egern/tests/")
# ⚠️ 分三类判，**不要退回 `any(g in p)` 子串匹配** —— 那会把正常名字判负：
#    2026-09-25 实测 `docs/a~b.md` 命中 `"~"`（H1 直接判负），`a.log.md` 之类只差一个字符
#    就命中 `".log"`。方向是**误报**，比漏报更烦人（会逼人给正常文件改名）。
GARBAGE_DIRS = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
GARBAGE_NAMES = (".DS_Store", "Thumbs.db", "desktop.ini")
GARBAGE_SUFFIX = (".pyc", ".pyo", ".orig", ".bak", ".tmp", ".log", ".swp", "~")


def is_garbage(p):
    """路径是不是单机残留：**目录段整段相等** / **文件名整名相等** / **文件名后缀相等**。"""
    parts = p.split("/")
    if any(seg in GARBAGE_DIRS for seg in parts[:-1]):
        return True
    name = parts[-1]
    return name in GARBAGE_NAMES or name.endswith(GARBAGE_SUFFIX)


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        return None
    return [f.decode("utf-8", "replace") for f in out.stdout.split(b"\0") if f]


def is_text(path):
    """E2/E2b/E3 的判定域：哪些跟踪文件该是 LF 文本。

    无扩展名的跟踪文件（`LICENSE` / `NOTICE` / `README` 之类）**同样是文本** ——
    早先只按扩展名白名单判，`LICENSE` 落在白名单外，成了字节层的一个盲区。
    将来若真要放一个无扩展名的二进制，必须在 `.gitattributes` 里显式标 `binary`，
    并同时加进 BINARY_EXT，别靠"没有扩展名所以不算文本"蒙过去。
    """
    if path.endswith(BINARY_EXT):
        return False
    name = os.path.basename(path)
    return "." not in name or name.startswith(".") or path.endswith(TEXT_EXT)


def read(path):
    with open(os.path.join(ROOT, path), "rb") as fh:
        return fh.read()


def gbk_encodable(ch):
    """这个字符能不能编进 GBK(cp936) —— 不能的（emoji / ⇒ / ↔ …）在 cp936 管道下会炸。"""
    try:
        ch.encode("gbk")
        return True
    except Exception:                                          # noqa: BLE001
        return False


def _is_sys_stdout(node):
    """AST 节点是不是 `sys.stdout` 这条属性链。"""
    return (isinstance(node, ast.Attribute) and node.attr == "stdout"
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def _scoped_reconfigure_calls(tree):
    """收集所有 `.reconfigure()` 调用点 → [(调用节点, 所在函数名 或 None)]，None = 模块级。"""
    hits = []
    stack = []

    class V(ast.NodeVisitor):
        def _fn(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()
        visit_FunctionDef = _fn
        visit_AsyncFunctionDef = _fn

        def visit_Call(self, node):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "reconfigure":
                hits.append((node, stack[-1] if stack else None))
            self.generic_visit(node)

    V().visit(tree)
    return hits


def _loop_stdout_vars(tree):
    """`for X in (… sys.stdout …)` 绑定的循环变量 → {(所在函数名 或 None, 变量名)}。"""
    found = set()
    stack = []

    class V(ast.NodeVisitor):
        def _fn(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()
        visit_FunctionDef = _fn
        visit_AsyncFunctionDef = _fn

        def visit_For(self, node):
            if isinstance(node.target, ast.Name) and any(
                    _is_sys_stdout(sub) for sub in ast.walk(node.iter)):
                found.add((stack[-1] if stack else None, node.target.id))
            self.generic_visit(node)

    V().visit(tree)
    return found


def _module_level_called(tree):
    """模块级（不在任何函数体内）被调用的函数名集合。"""
    called = set()
    stack = []

    class V(ast.NodeVisitor):
        def _fn(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()
        visit_FunctionDef = _fn
        visit_AsyncFunctionDef = _fn

        def visit_Call(self, node):
            if not stack and isinstance(node.func, ast.Name):
                called.add(node.func.id)
            self.generic_visit(node)

    V().visit(tree)
    return called


def protects_stdout(tree):
    """AST 判定脚本是否**真的把 sys.stdout 钉住了**。两条要求须同时满足：

        A. 有 `.reconfigure()` 调用，受体是 `sys.stdout`，或「**同作用域**内由
           `for X in (sys.stdout, …)` 绑定的循环变量」
           —— 刻意**不认**只护 stderr：stdout 没被保护，print 照样崩；
        B. 该调用点**在模块级**，或它在函数体内、但**那个函数在模块级被调用过**。

    ⚠️ B 是 2026-10-02 第三轮对抗补上的：先前只看「调用点存不存在」，于是
    `def setup(): sys.stdout.reconfigure(...)` 这种**定义了却从未调用**的写法会被误判成
    「已有保护」—— 性质与 E4 自己批判的「子串判断」相同，都是**乐观地认保护**。
    （本仓既有惯例恰是「def + 模块级调用」，照抄 `_egern_common.py` 而忘写调用即中招。）

    ⚠️ 不要退回 `"reconfigure" not in src` 这类**子串判断**：第二轮对抗实测，光在**注释**里
    写一句 `# 需要 reconfigure 保护` 就会被误判成「已有保护」。假保护比漏报更坏。

    ⚠️ **已知边界（与上面方向相反：宁严勿宽）**：B 只追**一层**调用关系。保护若被**包了两层
    以上**（`boot()` → `force_utf8_stdout()` → `reconfigure`），内层函数名不在「模块级被调用」
    集合里 ⇒ 会被**误判为无保护**。2026-10-02 实测该写法：真实运行 `rc=0` 不崩，E4 却判负。
    这是刻意的保守 —— 宁可误报也不放过。修法：把保护直接写在模块级，或让**中间层**在模块级
    被调用（本仓 `_egern_common.force_utf8_stdout()` 属后者，故不受影响）。
    """
    module_calls = _module_level_called(tree)
    loop_vars = _loop_stdout_vars(tree)
    for node, fn in _scoped_reconfigure_calls(tree):
        target = node.func.value
        if _is_sys_stdout(target):
            covers = True
        elif isinstance(target, ast.Name):
            covers = (fn, target.id) in loop_vars
        else:
            covers = False
        if covers and (fn is None or fn in module_calls):
            return True
    return False


def imports_common(tree):
    """AST 判定**真 import** 了公共编码垫片模块。

    ⚠️ 不要退回 `"_egern_common" in src` 这类子串判断：2026-10-02 实测
    `egern/audit_region_filters.py` 的 docstring 里提了一句 `_egern_common.py`，
    子串判断会把它误当「已 import」—— 而它真 import 只有 argparse/io/re/sys，没有任何保护。
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name in ("_egern_common", "_surge_common") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("_egern_common", "_surge_common"):
                return True
    return False


def print_emojis(tree):
    """print 会输出的非 GBK 字符集合。

    除直接写在 `print(...)` 里的字面量，还跟**变量中转链**（迭代到不动点）：

        M = "✅" ; print(M)                     # 一层
        A = "✅" ; B = A + " x" ; print(B)       # 多层 + 拼接（第三轮对抗补上）

    **覆盖范围**：`X = …` 的赋值，其**值里出现**非 GBK 字面量、或**已污染的名字**即算污染；
    **含字面量容器** —— 元组 / 列表 / 字典都会被 ast.walk 遍历到，
    `D = {"ok": "✅"}; print(D["ok"])` 照样命中（实测）。

    **静态盲区（已知、不打算覆盖）**：**函数返回值**（`def f(): return "✅"; print(f())`，实测漏）、
    运行时才拿到的数据（读文件 / 网络）、以及运行时**动态构建**的容器 —— 要抓这些得真跑脚本，
    代价（参数各异 + 可能有副作用）远大于收益。E4 守的是「**新写的脚本忘加保护**」这一类，
    不是「穷尽一切可能输出 emoji 的路径」。
    """
    assigns = []                       # [(变量名, 赋值右侧)]
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    assigns.append((tgt.id, node.value))
    tainted = {}                       # 变量名 → 该变量持有的非 GBK 字符
    for _ in range(len(assigns) + 1):  # 迭代到收敛（最长传播链不会超过赋值条数）
        changed = False
        for name, value in assigns:
            chars = {c for sub in ast.walk(value)
                     if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                     for c in sub.value if not gbk_encodable(c)}
            chars |= {c for sub in ast.walk(value)
                      if isinstance(sub, ast.Name) for c in tainted.get(sub.id, ())}
            if chars - tainted.get(name, set()):
                tainted.setdefault(name, set()).update(chars)
                changed = True
        if not changed:
            break
    out = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "print"):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out |= {c for c in sub.value if not gbk_encodable(c)}
                elif isinstance(sub, ast.Name) and sub.id in tainted:
                    out |= tainted[sub.id]
    return out


def _e4_verdict(src):
    """E4 对单份源码的判定：True = 判负（有非 GBK 输出、却没有覆盖 stdout 的保护）。"""
    tree = ast.parse(src)
    return bool(print_emojis(tree)) and not (protects_stdout(tree) or imports_common(tree))


# ⚠️ 自检（与上面 WIN_RESERVED 那条自检同款思路）：E4 的判定逻辑本身必须先能抓漏。
#    2026-10-02 两轮对抗测试各暴露一批漏报 —— 第二轮：emoji 藏在变量里、reconfigure 只护
#    stderr / 只写在注释里；第三轮：多层变量中转、保护写在**从未调用**的函数里 ——
#    每修一轮就往这里加样例，防将来把判定改回去。
#    （`bad` 样例是「必须判负」，`ok` 样例是「必须放行」。）
for _src, _expect_bad in (
    ('M = "\u2705"\nprint(M)\n', True),                                    # 变量中转的 emoji（二轮）
    ('a = "\u2705"\nb = a\nprint(b)\n', True),                              # 多层中转（三轮）
    ('import sys\nsys.stderr.reconfigure(encoding="utf-8")\nprint("\u2705")\n', True),   # 只护 stderr（二轮）
    ('# 需要 reconfigure 保护\nprint("\u2705")\n', True),                    # 只写注释（二轮）
    ('import sys\n\n\ndef setup():\n    sys.stdout.reconfigure(encoding="utf-8")\n'
     '\n\nprint("\u2705")\n', True),                                         # 保护在从未调用的函数里（三轮）
    ('import sys\nsys.stdout.reconfigure(encoding="utf-8")\nprint("\u2705")\n', False),  # 直点 stdout
    ('import sys\nfor _s in (sys.stdout, sys.stderr):\n'
     '    _s.reconfigure(encoding="utf-8", errors="replace")\nprint("\u2705")\n', False),  # 双流循环
    ('import sys\n\n\ndef setup():\n    sys.stdout.reconfigure(encoding="utf-8")\n'
     '\n\nsetup()\nprint("\u2705")\n', False),                                # 函数内保护 + 模块级调用
    ('import sys\nfrom _egern_common import force_utf8_stdout\nprint("\u2705")\n', False),  # 公共垫片
):
    if _e4_verdict(_src) != _expect_bad:
        raise SystemExit(
            "❌ 前置：E4 判定逻辑自检失败（期望判负=%s，实得 %s）\n   样例：%r"
            % (_expect_bad, _e4_verdict(_src), _src))


def main():
    files = tracked_files()
    if files is None:
        print("❌ 前置不达标：这里不是 git 仓库，拿不到 tracked 清单")
        print("   仓库根按本文件定位：%s" % ROOT)
        return 2
    # ⚠️ 前置：被跟踪文件必须都在工作树里。
    #    少任何一个（`git rm` 未提交 / 改到一半 / 误删）时，下面的 read() 会抛
    #    FileNotFoundError ⇒ traceback + **退出码 1 + 没有 TOTAL 行**：既让后面 18 条判据
    #    一条都不跑，又把"没跑成"伪装成"判负"（本仓最忌的那种假绿的反面）。
    #    2026-09-25 实测：`rm icons/grok.png` 就是这个表现。
    #    ⇒ 归到退出码 2（前置/环境不达标），与"不是 git 仓库"同一档。
    missing = [p for p in files if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        print("❌ 前置不达标：%d 个被跟踪文件在工作树里不存在" % len(missing))
        for p in missing[:6]:
            print("     · %s" % p)
        if len(missing) > 6:
            print("     · …另有 %d 个" % (len(missing) - 6))
        print("   ⇒ 先 `git status` 看清是删除还是改名；本项不判内容，退回退出码 2"
              "（没跑成 ≠ 跑绿）")
        return 2
    print("仓库根：%s" % ROOT)
    print("tracked 文件：%d 个" % len(files))

    checks = []          # (编号, 说明, [违规样例])

    # ── E1 .gitattributes ────────────────────────────────────────────
    if ".gitattributes" not in files:
        checks.append(("E1", ".gitattributes 在场", ["缺文件"]))
    else:
        txt = read(".gitattributes").decode("utf-8", "replace")
        ok = re.search(r"^\*\s+text=auto\s+eol=lf\s*$", txt, re.M)
        checks.append(("E1", ".gitattributes 把 * 钉成 text=auto eol=lf",
                       [] if ok else ["没有 `* text=auto eol=lf` 这一行"]))

    # ── E2 / E3 / H2 / S1 字节层 ─────────────────────────────────────
    crlf, lone_cr, bom, empty, no_shebang = [], [], [], [], []
    for p in files:
        b = read(p)
        if not b and not p.endswith(BINARY_EXT):
            empty.append(p)
        if p.endswith(BINARY_EXT) or not is_text(p):
            continue
        if b.startswith(b"\xef\xbb\xbf"):
            bom.append(p)
        if b"\r\n" in b:
            crlf.append(p)
        elif b"\r" in b:
            lone_cr.append(p)
        if p.endswith(".sh"):
            if not b.startswith(b"#!/"):
                no_shebang.append(p)
    checks.append(("E2", "工作树文本文件无 CRLF", crlf))
    checks.append(("E2b", "工作树文本文件无孤立 CR", lone_cr))
    checks.append(("E3", "工作树文本文件无 BOM", bom))
    checks.append(("H2", "无零字节跟踪文件", empty))
    checks.append(("S1", "每个 .sh 以 #!/ 开头", no_shebang))

    # ── 命名层 ───────────────────────────────────────────────────────
    non_nfc = [p for p in files if unicodedata.normalize("NFC", p) != p]
    illegal = [p for p in files if set(p) & ILLEGAL]
    reserved, spaced, tail_dot = [], [], []
    ascii_bad, too_long = [], []
    for p in files:
        for seg in p.split("/"):
            if seg.split(".")[0].upper() in WIN_RESERVED:
                reserved.append(p)
            if seg != seg.strip():
                spaced.append(p)
            if seg.endswith("."):
                tail_dot.append(p)
        if any(ord(c) > 127 for c in p) and p.startswith(MACHINE_PREFIXES):
            ascii_bad.append(p)
        if len(p) > 120:
            too_long.append(p)
    folded = {}
    for p in files:
        folded.setdefault(p.lower(), []).append(p)
    collide = [v for v in folded.values() if len(v) > 1]

    checks.append(("N1", "所有路径为 NFC", non_nfc))
    checks.append(("N2", "无 Windows/macOS 非法字符", illegal))
    checks.append(("N3", "无 Windows 保留设备名", reserved))
    checks.append(("N4", "路径段无首尾空格", spaced))
    checks.append(("N4b", "路径段无尾点", tail_dot))
    checks.append(("N5", "大小写折叠无冲突", [" + ".join(v) for v in collide]))
    checks.append(("N6", "机器消费的路径纯 ASCII（docs 正文允许中文）", ascii_bad))
    checks.append(("L1", "相对路径 ≤ 120 字符", too_long))

    # ── 残留与外链结构 ───────────────────────────────────────────────
    garbage = [p for p in files if is_garbage(p)]
    checks.append(("H1", "无单机残留被跟踪", garbage))
    links = [p for p in files
             if os.path.islink(os.path.join(ROOT, p))]
    checks.append(("H3", "无符号链接", links))
    checks.append(("H3b", "无 submodule", [] if ".gitmodules" not in files else [".gitmodules"]))
    gi = read(".gitignore").decode("utf-8", "replace") if ".gitignore" in files else ""
    # 期望的是 `.gitignore` 里的**字面条目**；`*.py[cod]` 一条覆盖 .pyc/.pyo/.pyd 三种后缀
    missing = [g for g in ("__pycache__/", "*.py[cod]", ".DS_Store", "Thumbs.db",
                           "desktop.ini", "*.bak", "*.tmp", "*.log") if g not in gi]
    checks.append(("H4", ".gitignore 兜底覆盖单机残留与 OS 垃圾", missing))

    # ── M1 markdown frontmatter 完好性 ──────────────────────────────
    #    2026-09-27 实测：批量删 hr 的脚本把 SKILL.md 的 frontmatter 闭合线
    #    （其后正好是 H1 标题）当成"标题前的 hr"删掉 ⇒ YAML 未闭合，全文件
    #    解析崩。凡以 `---` 开头的 .md，头部必须有第二条 `---` 闭合。
    fm_bad = []
    for p in files:
        if not p.endswith(".md"):
            continue
        b = read(p)
        if not b.startswith(b"---\n"):
            continue
        head = b[:4096].split(b"\n")
        if not any(l.strip() == b"---" for l in head[1:]):
            fm_bad.append(p)
    checks.append(("M1", "markdown frontmatter 以闭合的 --- 收尾", fm_bad))

    # ── E4 脚本输出编码保护 ──────────────────────────────────────────
    #    2026-10-02 外部审查暴露：Windows 原生 shell（ACP=936）下，子进程 stdout 走管道时
    #    Python 用 cp936 编码 —— 脚本 print 一个非 GBK 字符（✅/❌/⚠️/⇒…）就
    #    UnicodeEncodeError、进程以退出码 1 结束。而 1 恰是本仓「判负」的码
    #    ⇒ 崩溃被读成「判负通过」，整轮看着绿、其实一条判据都没跑（假绿）。
    #    保护二选一：① 本文件把 **sys.stdout** 钉成 UTF-8（stdout 必须覆盖，只护 stderr 不算）；
    #                ② import _egern_common / _surge_common —— 二者在**模块级**调用
    #                   force_utf8_stdout()，import 即生效，调用方无需再写一行。
    #    判据一律走 AST（protects_stdout / imports_common / print_emojis），**绝不用子串判断** ——
    #    见各函数自身的注释，以及文件顶部那段 E4 自检回归。
    enc_bad = []
    for p in files:
        if not p.endswith(".py"):
            continue
        src = read(p).decode("utf-8", "replace")
        try:
            tree = ast.parse(src)
        except SyntaxError as e:                               # 语法坏 → 显式报出，不静默跳过
            enc_bad.append("%s（AST 解析失败：%s）" % (p, e))
            continue
        out = print_emojis(tree)
        if out and not (protects_stdout(tree) or imports_common(tree)):
            enc_bad.append("%s（print 输出 %s，且无编码保护）" % (p, " ".join(sorted(out))))
    checks.append(("E4", "脚本 print 非 GBK 字符时必有编码保护", enc_bad))

    bad = 0
    for cid, desc, viol in checks:
        if viol:
            bad += 1
            print("   ❌ %s %s · %d 处：" % (cid, desc, len(viol)))
            for v in viol[:6]:
                print("        · %s" % v)
        else:
            print("   ✅ %s %s" % (cid, desc))
    total = len(checks)
    print("TOTAL: %d passed, %d failed" % (total - bad, bad))
    if bad:
        print("   修法：换设备一致性靠 `.gitattributes` 与命名纪律，不靠任何人改本机 git 配置。")
        print("   详见 skill/reference/pitfalls.md 的「换设备 / 双端一致」一节。")
    return 1 if bad else 0


if __name__ == "__main__":
    # Windows GBK 终端里 print 中文/emoji 会 UnicodeEncodeError ⇒ 退出码 1，
    # 看着像判负、其实一条都没判。与 make_min.py 同款兜底。
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    sys.exit(main())
