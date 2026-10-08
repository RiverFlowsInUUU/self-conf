#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键收尾闸门 —— 动线⑤ 的闸门命令合并成 1 条，并行跑、出汇总表。

为什么存在：
    AGENTS.md 动线原来列一堆独立命令，AI 逐条调用 = 多次工具调用、多段输出
    折进上下文，且任何一次漏跑/跑错参数都算事故。本脚本与 `.github/workflows/ci.yml`
    的步骤**同源**（改 CI 步骤时必须同步这里，反之亦然），并行执行后只输出一张
    「闸门 | 结果 | 耗时」汇总表，红的才展开输出尾部 —— 正常情况一段话看完全部结论。

用法：
    python self-conf-skills/gates/verify_all.py            # 全量并行，全绿退出码 0
    python self-conf-skills/gates/verify_all.py -v         # 无论红绿都打印每个闸门的输出尾部
    python self-conf-skills/gates/verify_all.py --index    # 只读列出闸门清单（不跑、不判负），供引用时现抓

设计约定：
    · 与 CI 同源是铁律 —— 本地绿但 CI 红属于竞态/环境差，不允许有"第三套判据"。
      ⚠️ **已知挂账**：闸门清单靠人工双写（ci.yml ↔ 本文件），机器对账未做（对账脚本
      自身也是维护面）。**推翻挂账的触发条件**：一旦出现「一侧增删闸门、另一侧未同步」
      且事后确认是人工漏同步造成的本地/CI 结论分歧，就必须补上清单对账断言。
    · 退出码语义（全仓统一，见 reference/pitfalls.md §8.2）：
      0 = 判据全过 ｜ 1 = 有判负 ｜ 2 = 前置环境不达标（**计入失败，先修环境再看判据**）
      ｜ 3 = SKIP（未能验证 → 不计入失败但必须明示）。
      3 的准入 = 「没读到远端真值」。**任何脚本不得因故障/未知错误返回 3**（故障走 2、
      断言不过走 1）——本脚本对 3 是全闸门通用判定，滥用 3 会被静默吞成假绿。
      SKIP 独立占用 3：2 已被全仓铁律占用为「环境不达标」，复用会让环境故障被吞成
      SKIP → 假绿（0930 二轮外部审查）。
    · check_releases 需 GITHUB_TOKEN：由 `verify_all._token()` 提供（读 GITHUB_TOKEN 环境变量）；本仓 Release 为公开仓，无 token 时 check_releases 走**匿名**公共读。都没有、或 API
      离线/限流/上游 5xx/非 JSON 时返回 3，本脚本以 ⚠️ 明示「未验证」并不计入失败
      （0929 一轮审查：原实现按输出文本嗅探、且被跳过仍 exit 1，提示与实际矛盾，
      现按退出码判定）。
      ⚠️ 本地与 CI 对 3 的口径**有意不同**：本地允许 SKIP（可能真离线 → exit 0 + ⚠️），
      CI 侧 3 视为失败（CI 带 token，读不到远端即 CI 环境异常）——这是**严格化**，不是
      "第三套判据"；CI 侧偶发 3（共享 runner IP 被 GitHub 限流）→ 重跑即可。
    · make_min 漂移检查 = `make_min.py --check`（0929 起）：--check 直接比对磁盘 .min 与
      生成器输出，有差异即非 0。旧写法「计划模式 + git diff」两半恒空/恒 0，是永远绿的
      空操作（2026-09-29 外部审查实锤后废除，原『git 无漂移』闸门随之合并）。
    · CI 另有一道**运行时编码闸门**（`.github/workflows/ci.yml` 的 `Encoding gate (cp936)`）：
      以 `PYTHONIOENCODING=cp936` 跑一遍本脚本，在 Linux 上等价复现 Windows(ACP=936) 的
      管道路径 —— 脚本 print 非 GBK 字符却无编码保护时当场崩、当场红。
      它与 `check_portability.py` 的 E4 **互补、不可互相替代**：
        - 本闸门测**运行时真相**、零假阳性，但只覆盖 `build_gates()` 跑到的脚本，
          且只覆盖**执行到的**分支（只在失败分支打印 emoji 的脚本仍测不到）；
        - E4 是静态近似，全覆盖（含 CI 不跑的审计脚本），但会漏报也会假阳性。
      两者叠加才封住「脚本忘加保护 → 崩成退出码 1 → 被读成判负」这条假语义路径。
      前提是 `run_one` 对 PYTHONIOENCODING 用 `setdefault`（显式继承，见该处注释）。
"""

import glob
import os
import re
import subprocess
import ast
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# 仓库定位：靠标志物上溯，不依赖目录层数（见 self-conf-skills/lib/paths.py）
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../lib'))
from paths import repo_root as _repo_root  # noqa: E402


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = _repo_root()
# 三内核现役 profile —— **单一真源**：闸门清单与文件枚举都从这里取。
KERNS = ('surge', 'egern', 'clash')
PROFILE_EXT = {'surge': '.conf', 'egern': '.yaml', 'clash': '.yaml'}


def _profiles(kern):
    """该内核的**完整版**现役文件（lazy / routing）。

    ⚠️ 含 `.min`：`check_min_pair` 已保证两者去注释后逐字相同，
    审计 `.min` 是**重复劳动**（同一内容审两遍）。故审计只喂完整版。
    """
    ext = PROFILE_EXT[kern]
    return ['%s/profiles/%s%s' % (kern, fam, ext)
            for fam in ('lazy', 'routing')
            if os.path.isfile(os.path.join(ROOT, '%s/profiles/%s%s' % (kern, fam, ext)))]


ALL_PROFILES = {k: _profiles(k) for k in KERNS}      # list，不是空格串（argv 要分开传）


def _routing(kern):
    ext = PROFILE_EXT[kern]
    return '%s/profiles/routing%s' % (kern, ext)


ROUTING = {k: _routing(k) for k in KERNS}
PY = sys.executable or 'python'


def _gh_exe():
    """找 gh 可执行文件 —— **不能只靠 PATH**（第十一轮问题 1）。

    实测本机：`shutil.which('gh')` 返回 None，`subprocess.run(['gh', 'auth', 'token'])`
    抛 FileNotFoundError(WinError 2)，而 Git-Bash 里 `gh` 却能跑 ⇒ Git-Bash 的 PATH
    与 Python 进程拿到的 PATH **不是同一套**。所以除了 PATH，还得显式找常见安装位置。
    """
    cands = [shutil.which('gh'), shutil.which('gh.exe')]
    for env in ('LOCALAPPDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)'):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, 'Programs', 'GitHub CLI', 'bin', 'gh.exe'))
            cands.append(os.path.join(base, 'GitHub CLI', 'bin', 'gh.exe'))
    for c in ('/usr/bin/gh', '/usr/local/bin/gh', '/opt/homebrew/bin/gh',
              os.path.expanduser('~/.local/bin/gh')):
        cands.append(c)
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _token():
    """check_releases 用：环境变量 → `gh auth token` → None（匿名）。

    ⚠️ 第十一轮问题 1：此前只有 `subprocess.run(['gh', ...])`，异常被 `except Exception: pass`
       吞掉 ⇒ **本机实际永远返回 None**，而 docstring 却写着"自动回退 gh auth token"
       ⇒ 文档在为**不存在的回落**背书。现改为先用 `_gh_exe()` 定位 gh；仍找不到才 None。
    """
    if os.environ.get('GITHUB_TOKEN'):
        return os.environ['GITHUB_TOKEN']
    gh = _gh_exe()
    if not gh:
        return None
    try:
        r = subprocess.run([gh, 'auth', 'token'],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        # ⚠️ 第十二轮问题 1：`except Exception: pass` 把【gh 返回非零 / 超时 /
        #    token 过期】全吞了，一句告警都没有 ⇒ 调用方只知道"没拿到 token"，
        #    不知道是"没装 gh"还是"装了但失败" —— 与第十一轮那条
        #    "文档给不存在的回落背书"是同一类隐蔽性。现在分情况都吭声。
        print('   ⚠️ `gh auth token` 未取到 token（rc=%s）—— Release 断言退回匿名读；'
              '若需要更高配额请设 GITHUB_TOKEN' % r.returncode)
    except Exception as e:
        print('   ⚠️ 调 `gh auth token` 失败（%s: %s）—— Release 断言退回匿名读'
              % (type(e).__name__, str(e)[:60]))
    return None


# ─────────────────────────────────────────────────────────────────────
# 环境变量登记（逃生门 / 输入类 / 动态读取）
#
# ⚠️ 2026-10-08 改革：这份登记**从文档搬进了代码**。
#    旧做法把三张登记表放在 `reference/ops.md` 的 §4.2.1/§4.2.2/§4.2.3，
#    再写解析器去读它 —— 结果是：文档与代码必须同步，于是又长出「登记漂移」
#    这个需要专门门禁去守的元问题。而登记本质就是**代码的元数据**，
#    放进代码里 ⇒ 物理上不可能漂移，解析器与章节定位代码全部删除。
#
# 判据：AST 抓到的全部名字 − INPUT（输入类）= 放行类候选；
#       候选必须 ∈ ESCAPES，否则启动即报错（防悄悄加后门）。
# ─────────────────────────────────────────────────────────────────────

# 放行类：能动判据宽严的开关。每项写明「默认是否安全」。
ESCAPES = {
    # 已全部移除：SKIP_V7 / STRICT_ARCHIVE（归档机制已删）、UNIFIED_VERSION
    # （三内核同号已由 check_min_pair 的 X 判据硬性守住，无需覆盖开关）。
}

# 输入类：只提供运行所需信息，缺了只是「环境没准备好」，不是「标准被放低」。
INPUT = {
    'GITHUB_TOKEN', 'GITHUB_REPO', 'GITHUB_ACTIONS', 'CI',
}

# 静态判不出名字的动态读取（如 os.environ.get(var)）⇒ 必须登记，登记 = 人工看过。
DYNAMIC_READS = {
    # 只读路径类变量（LOCALAPPDATA / PROGRAMFILES / …）用于定位 gh.exe，
    # 与判据宽严无关。
    'gates/verify_all.py',
}


def _assert_escapes_registered():
    """放行类逃生门必须在 ESCAPES 里登记 —— 防悄悄加后门。

    fail-closed：AST 抓到但既不在 ESCAPES 也不在 INPUT ⇒ 报错，不放行。
    反向：登记了但代码不再读 ⇒ 提醒（不报错，避免删代码被卡）。
    """
    found, dynamic_reads = _collect_env_reads()
    alive = set()
    for v in found.values():
        alive.update(v)

    missing = sorted(x for x in (alive - INPUT) if x not in ESCAPES)
    if missing:
        where = {}
        for f, vs in found.items():
            for x in missing:
                if x in vs:
                    where.setdefault(x, []).append(f)
        raise SystemExit(
            '❌ 这些环境变量被代码读取却没登记：\n'
            + '\n'.join('     %s  ← %s' % (x, '、'.join(where.get(x, ['?'])))
                        for x in missing)
            + '\n   —— 放行类（能改判据宽严）⇒ 加进本文件 ESCAPES 并写明默认安全性；'
              '输入类（只是环境信息）⇒ 加进 INPUT。不放行。')

    unlisted = []
    for rel in sorted(dynamic_reads):
        norm = rel.replace('\\', '/')
        if norm not in DYNAMIC_READS and ('self-conf-skills/' + norm) not in DYNAMIC_READS:
            unlisted.append(norm)
    if unlisted:
        raise SystemExit(
            '❌ 这些文件用**动态名字**读环境变量（如 `os.environ.get(var)`），'
            '静态判不出具体名字 ⇒ 无法确认是否夹带后门：\n'
            + '\n'.join('     %s' % x for x in unlisted)
            + '\n   —— 确认无放行类后门后，加进本文件 DYNAMIC_READS；否则改成字面量。不放行。')

    stale = sorted(x for x in ESCAPES if x not in alive)
    if stale:
        print('   ℹ️ ESCAPES 登记了但代码不再读取：%s（可选清理）' % '、'.join(stale))


def _scan_env_reads_in(tree, pat):
    """对**单棵** AST 做「污点传播 + 取值点」判定。返回 (名字集合, 是否有动态读取)。

    ⚠️ 这是第十五轮重写的核心。上一版（第十三/十四轮）的失败根因是
    **判据挂在语法位置上**（`base.attr == 'environ' and base.value.id in os_names`）
    ⇒ 只认「直接成员访问」这一种写法，把对象搬到一个新名字上就整类失明。

    本版改为**按名字 + 污点判定**：
      ① 建家族：os 模块名 / environ 家族名 / getenv 家族名 / environ 取值函数家族名；
         `from os import *` ⇒ 三个家族名全部入场。
      ② 迭代传播（fixpoint）：`x = <污名>` / `x = <污名>.environ` / `x = <污名>.getenv` /
         `x = getattr(<污名>, 'environ'|'getenv')` / `x = globals()['os']` /
         `x = getattr(<environ污名>, 'get')` —— 把污点搬到新名字上。
      ③ 只看两件事：**基名是否污点** + **是不是取值动作**。于是
         `E.get("X")`（E = os.environ）与 `os.environ.get("X")` 一视同仁。

    ⚠️ 刻意区分「整体搬走」与「取值」（第十四轮回滚的教训）：
      · `dict(os.environ)` / `os.environ.copy()` / `env=os.environ`
        ⇒ **只取快照，没取任何键** ⇒ 不算读取，**不标 dynamic**
        （上一版把它判成动态 ⇒ 10 个文件假红 ⇒ 门禁判负 ⇒ 整轮回滚）
      · `.get/.pop/.setdefault/[]/getenv(...)` 才计。
    这条边界写在 release-rules.md §4.2.3。
    """
    os_mod = {'os'}
    environ_fam = set()
    getenv_fam = set()
    envgetter_fam = set()      # getattr(os.environ, 'get') 这类「取值函数被取出」
    star_import = False
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Import):
            for al in nd.names:
                if al.name == 'os':
                    os_mod.add(al.asname or 'os')
        elif isinstance(nd, ast.ImportFrom) and nd.module == 'os':
            for al in nd.names:
                nm = al.asname or al.name
                if al.name == 'environ':
                    environ_fam.add(nm)
                elif al.name == 'getenv':
                    getenv_fam.add(nm)
                elif al.name == '*':
                    star_import = True
    if star_import:
        environ_fam.add('environ')
        getenv_fam.add('getenv')

    def _resolve(node, depth=0):
        """把一个表达式解析成污点类别：
        'os' / 'environ' / 'getenv' / 'envgetter' / None。
        """
        if depth > 8:
            return None
        if isinstance(node, ast.Name):
            if node.id in os_mod:
                return 'os'
            if node.id in environ_fam:
                return 'environ'
            if node.id in getenv_fam:
                return 'getenv'
            if node.id in envgetter_fam:
                return 'envgetter'
            return None
        if isinstance(node, ast.Attribute):
            base = _resolve(node.value, depth + 1)
            if base == 'os' and node.attr == 'environ':
                return 'environ'
            if base == 'os' and node.attr == 'getenv':
                return 'getenv'
            return None
        if isinstance(node, ast.Subscript):
            sl = node.slice
            # globals()['os'] —— 把模块从 globals 字典里捞出来
            if isinstance(node.value, ast.Call) \
                    and isinstance(node.value.func, ast.Name) \
                    and node.value.func.id == 'globals':
                if isinstance(sl, ast.Constant) and sl.value == 'os':
                    return 'os'
                return None
            base = _resolve(node.value, depth + 1)
            if base == 'os' and isinstance(sl, ast.Constant):
                if sl.value == 'environ':
                    return 'environ'
                if sl.value == 'getenv':
                    return 'getenv'
            return None
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == 'getattr' and len(node.args) >= 2:
                base = _resolve(node.args[0], depth + 1)
                a1 = node.args[1]
                key = a1.value if isinstance(a1, ast.Constant) else None
                if key == 'environ':
                    return 'environ'
                if key == 'getenv':
                    return 'getenv'
                # getattr(os.environ, 'get') ⇒ 取值函数被取出
                if base == 'environ' and key in ('get', 'pop', 'setdefault'):
                    return 'envgetter'
                return None
            return None
        return None

    def _names_in(target):
        """赋值目标里的名字（支持 a = b = ... 与元组解包）。"""
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            out = []
            for e in target.elts:
                out.extend(_names_in(e))
            return out
        return []

    fam_of = {'os': os_mod, 'environ': environ_fam,
              'getenv': getenv_fam, 'envgetter': envgetter_fam}

    # ── 污点传播到不动点 ──
    for _ in range(12):
        added = False
        for nd in ast.walk(tree):
            tgts, val = None, None
            if isinstance(nd, ast.Assign):
                tgts, val = nd.targets, nd.value
            elif isinstance(nd, ast.AnnAssign) and nd.value is not None:
                tgts, val = [nd.target], nd.value
            if not tgts or val is None:
                continue
            kind = _resolve(val)
            if not kind:
                continue
            grp = fam_of[kind]
            for t in tgts:
                for nm in _names_in(t):
                    if nm not in grp:
                        grp.add(nm)
                        added = True
        if not added:
            break

    VALUE_METHODS = ('get', 'pop', 'setdefault')

    def _lit_str(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and pat.match(node.value):
            return node.value
        return None

    got, dyn = set(), False
    for nd in ast.walk(tree):
        # ── ① 取值类方法调用 ──
        if isinstance(nd, ast.Call):
            f = nd.func
            is_value_read = False
            if isinstance(f, ast.Attribute) and f.attr in VALUE_METHODS:
                if _resolve(f.value) == 'environ':
                    is_value_read = True
            r = _resolve(f)
            if r in ('getenv', 'envgetter'):
                is_value_read = True
            if is_value_read:
                v = _lit_str(nd.args[0]) if nd.args else None
                if v:
                    got.add(v)
                else:
                    dyn = True        # 名字不是字面量 ⇒ 静态判不出
        # ── ② 下标取值：<environ 家族>["N"] ──
        if isinstance(nd, ast.Subscript) and _resolve(nd.value) == 'environ':
            v = _lit_str(nd.slice)
            if v:
                got.add(v)
            else:
                dyn = True
    return got, dyn


def _collect_env_reads():
    """抓 `self-conf-skills/**/*.py` 读取的环境变量名 —— 返回 ({相对路径: [名字]}, {相对路径: True})。

    ⚠️ 演进（每一轮都是被指出打脸后才补的，记下来防止再退化）：
      · 第十二轮：只认 `b.value.id == 'os'` ⇒ `import os as _os` 写的 SKIP_V7 **整个消失**
      · 第十二轮补：`import os as _os` 别名
      · 第十三轮：仍漏 **整类**常见写法（逐个实测全部溜过去）：
          `os.getenv("X")` / `from os import environ` 后 `environ.get("X")` /
          `from os import getenv` 后 `getenv("X")` / `from os import environ as e` 后 `e.get("X")` /
          `getattr(os.environ, "get")("X")` / 二次别名 `_oo = _o` /
          **名字存在变量里** `_KEY="X"; os.environ.get(_KEY)`
      · 第十四轮：作者重写后**引入 DYNAMIC 兜底过宽**（`dict(os.environ)` 也被判动态）
          ⇒ 10 个文件假红、门禁判负 ⇒ **权衡后回滚，7 种写法继续溜过，只记账未修**。
          那 7 种（已逐个注错复现，全部 rc=0 溜过）：
          `E = os.environ; E.get("X")` / `environ = os.environ; environ.get("X")` /
          `g = os.getenv; g("X")` / `getattr(os,'environ')["X"]` /
          `getattr(os,'getenv')("X")` / `globals()['os'].environ.get("X")` /
          `from os import *` 后 `environ.get("X")`

    第十五轮（本版）：判据从「按语法位置」改为「**按名字 + 污点传播**」，
    上面 7 种与第十三轮那批**一并用同一套判据覆盖**（见 `_scan_env_reads_in`），
    并且**显式区分「整体搬走」与「取值」**，避免第十四轮那种过宽假红。
    回归测试见 `_ENV_SCAN_FIXTURES` / `_selftest_env_scan()` —— 注错用例已固化进代码，
    不再是"改完手测一遍"。

    **剩下的动态形态（名字不是字面量）静态本质上判不出** ⇒ 不假装能抓，
    改为 **fail-closed**：单独收集到 `dynamic`，由 `_assert_escapes_registered()`
    要求其所在文件显式登记豁免（否则报错），把"看不见"变成"看得见的待办"。
    """
    skill = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..'))
    pat = re.compile(r'^[A-Z_][A-Z0-9_]*$')
    names = {}
    dynamic = {}
    for dp, dirs, files in os.walk(skill):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in sorted(files):
            if not fn.endswith('.py'):
                continue
            fp = os.path.join(dp, fn)
            try:
                tree = ast.parse(open(fp, encoding='utf-8').read())
            except Exception:
                continue
            rel = os.path.relpath(fp, skill)
            got, dyn = _scan_env_reads_in(tree, pat)
            if got:
                names[rel] = sorted(got)
            if dyn:
                dynamic[rel] = True
    return names, dynamic


# ─────────────────────────────────────────────────────────────────────
# 注错回归（第十五轮新增）：把「曾经溜过的写法」固化成用例。
#
# 为什么必须有：第十三、十四两轮都是「改完手测一遍」——手测不留痕，下一轮重写
# 时同样的洞会再开一次（第十四轮就是这么回滚的：改对了 7 种，却因过宽假红被整体
# 回滚，那 7 种于是继续溜）。用例进仓后，**判据失效会当场红**，不再靠人的记忆。
#
# 每条用例 = (说明, 源码片段, 期望抓到的名字集合, 期望是否判为动态)。
# 空集合 + 动态 False ⇒ 该写法**本就不该被算作读取**（防过宽，第十四轮的坑）。
# ─────────────────────────────────────────────────────────────────────
_ENV_SCAN_FIXTURES = (
    # ── 第十三轮那批（曾整类失明）──
    ('裸成员访问', 'import os\nX = os.environ.get("A_1")', {'A_1'}, False),
    ('import os as 别名', 'import os as _os\nX = _os.environ.get("A_2")', {'A_2'}, False),
    ('os.getenv', 'import os\nX = os.getenv("A_3")', {'A_3'}, False),
    ('from os import environ', 'from os import environ\nX = environ.get("A_4")', {'A_4'}, False),
    ('from os import environ as', 'from os import environ as e\nX = e.get("A_5")', {'A_5'}, False),
    ('from os import getenv', 'from os import getenv\nX = getenv("A_6")', {'A_6'}, False),
    ('getattr 取 environ 的 get',
     'import os\nX = getattr(os.environ, "get")("A_7")', {'A_7'}, False),
    ('二次别名', 'import os as _o\n_oo = _o\nX = _oo.environ.get("A_8")', {'A_8'}, False),
    ('名字存在变量里',
     'import os\n_K = "A_9"\nX = os.environ.get(_K)', set(), True),
    ('下标取值', 'import os\nX = os.environ["A_10"]', {'A_10'}, False),
    # ── 第十四轮记账未修的 7 种（本轮目标）──
    ('environ 整体搬到新名', 'import os\nE = os.environ\nX = E.get("B_1")', {'B_1'}, False),
    ('environ 赋给同名变量', 'import os\nenviron = os.environ\nX = environ.get("B_2")', {'B_2'}, False),
    ('getenv 搬到新名', 'import os\ng = os.getenv\nX = g("B_3")', {'B_3'}, False),
    ('getattr 取 os 的 environ 再下标',
     'import os\nX = getattr(os, "environ")["B_4"]', {'B_4'}, False),
    ('getattr 取 os 的 getenv',
     'import os\nX = getattr(os, "getenv")("B_5")', {'B_5'}, False),
    ('globals 里捞 os',
     'import os\nX = globals()["os"].environ.get("B_6")', {'B_6'}, False),
    ('from os import *', 'from os import *\nX = environ.get("B_7")', {'B_7'}, False),
    ('from os import * 用 getenv', 'from os import *\nX = getenv("B_8")', {'B_8'}, False),
    # ── 防过宽（第十四轮假红的根因，必须**不**判动态）──
    ('dict(os.environ) 只取快照', 'import os\nX = dict(os.environ)', set(), False),
    ('environ.copy() 只取快照', 'import os\nX = os.environ.copy()', set(), False),
    ('整体传引用', 'import os\nX = os.environ', set(), False),
    ('os.environ 出现在比较里', 'import os\nX = (os.environ is not None)', set(), False),
    ('无关的 .get 调用', 'import os\nX = {}.get("C_1")', set(), False),
    ('同名但非 os 的 environ', 'environ = {}\nX = environ.get("C_2")', set(), False),
)


def _selftest_env_scan():
    """注错回归：判据失效即报错（fail-closed）。

    ⚠️ 这是**自检**，不是闸门 —— 但它必须跑在真正入口（`main()`），否则等于摆设。
    历史上「写了没接进去」在本仓发生过多次，故此处与 `_assert_*` 并列。
    """
    pat = re.compile(r'^[A-Z_][A-Z0-9_]*$')
    bad = []
    for label, code, want_got, want_dyn in _ENV_SCAN_FIXTURES:
        got, dyn = _scan_env_reads_in(ast.parse(code), pat)
        if got != want_got or dyn != want_dyn:
            bad.append('     %s：期望 names=%s dyn=%s，实得 names=%s dyn=%s'
                       % (label, sorted(want_got) or '{}', want_dyn,
                          sorted(got) or '{}', dyn))
    if bad:
        raise SystemExit(
            '❌ 环境变量 AST 判据自检失败 —— 有写法会溜过或误报（共 %d 条）：\n%s\n'
            '   —— 这层判据是「反查每一个环境变量名」的凭据，失真即等于后门敞开。不放行。'
            % (len(bad), '\n'.join(bad)))




def _assert_escapes_registered_OLD_REMOVED():
    """（已删除，见上方新实现）"""


def build_gates():
    """闸门清单 —— **声明式**，不手抄。

    设计（2026-10-08 重写）：旧实现是 127 行手写清单，把「三内核 × 判据类型」的
    笛卡尔积手工展开 —— 同一判据按文件各开一道（Surge DNS lazy / Surge DNS routing
    就是这么来的），大量重复劳动，加一个内核要复制十来行。
    现在改成两张声明表 + KERNS 遍历生成，**加内核只改 KERNS**。

    返回 [(名称, argv, 额外环境), ...]，与 ci.yml 的 Gates step 同源。
    """
    PRE = ['--strict'] if False else []
    G, R = [], []                      # G=闸门累加器, R=三内核审计脚本的路径规则

    def add(name, argv, env=None):
        G.append((name, argv, env or {}))

    # ── ① 全局闸门（不按内核分）────────────────────────────────────
    # AI 入口完整性：保证「换任何 AI 都能维护本仓」（AGENTS.md + 各工具指针）
    add('AI 入口完整性', [PY, 'self-conf-skills/gates/check_ai_entry.py'])
    # Agent Skill 规范合规（agentskills.io 开放标准，30+ 工具可加载）
    add('Skill 规范合规', [PY, 'self-conf-skills/gates/check_skill_spec.py'])
    # 写死数字的新鲜度：文档里的「N 个图标」「N 道判据」必须与真源一致
    # （实测漂过三次；靠人记不管用，必须机器守）
    add('文档数字新鲜度', [PY, 'self-conf-skills/gates/check_doc_numbers.py'])
    # DNS 段跨配置一致性（防泄露标准不因分流粒度而变）
    # —— 文档长期声称有、实际不存在；2026-10-08 用「全新 AI 实测」发现后补上
    add('DNS 段跨配置一致', [PY, 'self-conf-skills/gates/check_dns_parity.py'])
    # §节号引用的跨话题歧义（合并文档造成的系统性债；实测两轮都撞到）
    add('§引用无歧义', [PY, 'self-conf-skills/gates/check_section_refs.py'])
    # 已删机制的残留引用（改革删东西后，文档引用要一起清）
    add('无已删引用', [PY, 'self-conf-skills/gates/check_dead_refs.py'])
    add('secrets 扫描', [PY, 'self-conf-skills/gates/check_secrets.py'])
    add('未定义名扫描', [PY, 'self-conf-skills/gates/check_undefined_names.py'])
    add('portability', [PY, 'self-conf-skills/gates/check_portability.py'])
    add('自洽性', [PY, 'self-conf-skills/gates/check_selfcontained.py'])
    add('markdown 链接', [PY, 'self-conf-skills/gates/check_links.py', '.'])
    add('README 徽章', [PY, 'self-conf-skills/gates/check_badges.py'])
    add('min-pair 一致', [PY, 'self-conf-skills/gates/check_min_pair.py'])
    add('版本头注', [PY, 'self-conf-skills/gates/clash/check_version_header.py'])
    add('make_min 自检', [PY, 'self-conf-skills/run/make_min.py', '--selftest'])
    # ⚠️ 原「.min 漂移」闸门（make_min --check）已并入 check_min_pair ——
    #    两者只在「空白落位」上分岔，而那不影响配置语义；但保留检测（见该脚本）。
    add('Release 断言', [PY, 'self-conf-skills/gates/check_releases.py'],
        {'GITHUB_TOKEN': _token() or ''})

    # ── ② 三内核审计（每内核按现役文件各一道；脚本支持多文件）────────
    # 每项 = (闸门名, 脚本相对路径模板, 参数模板)
    #   {k}=内核  {files}=该内核全部现役 profile
    # ⚠️ 每个内核**未必都有**每一项 —— 缺的必须**显式登记理由**，不许静默跳过。
    #    用 None 表示「该内核设计上就没有这一项」。
    AUDITS = [
        # ⚠️ DNS 审计器在 gates/（它们是判据，不是工具）—— 见「目录重组」的说明
        ('DNS 审计',        'self-conf-skills/gates/{k}/{dns}',           ['{files}'], None),
        ('分流覆盖',        'self-conf-skills/run/{k}/audit_routing_coverage.py', ['{files}'], None),
        ('地区组判别力',    'self-conf-skills/run/{k}/audit_region_filters.py',   ['{routing}'], None),
        # clash 无独立脚本：刷新周期写在 rule-providers 的 interval 字段，
        # 由 check_structure.py / check_ruleset_doc_sync.py 间接覆盖。
        ('规则集刷新周期',  'self-conf-skills/run/{k}/audit_ruleset_refresh.py',  ['--strict', '{routing}'],
         {'clash': '该内核的刷新周期写在 rule-providers 的 `interval` 字段，'
                   '由 clash 结构与规则集来源判据覆盖，无需独立脚本'}),
    ]
    DNS_SCRIPT = {'surge': 'check_surge_dns.py', 'egern': 'check_egern_dns.py',
                  'clash': 'check_clash_dns.py'}
    for kern in KERNS:
        files = ALL_PROFILES[kern]          # list：每个文件是独立的 argv 元素
        routing = ROUTING[kern]
        for label, tpl, args, absent in AUDITS:
            if absent and kern in absent:
                continue          # 显式登记「该内核设计上无此项」
            path = tpl.format(k=kern, dns=DNS_SCRIPT[kern])
            # ⚠️ 2026-10-08 修：原为 `if not isfile: continue` —— **静默跳过**。
            #    目录重组时 DNS 审计器的路径模板没更新（run/ → gates/），
            #    于是三道 DNS 审计**静默消失**，而汇总表看不出少了什么。
            #    缺失必须报错，不能静默（判据列表本身就是被验证的对象）。
            if not os.path.isfile(os.path.join(ROOT, path)):
                raise SystemExit(
                    '❌ 闸门「%s·%s」的脚本不存在：%s' % (label, kern, path)
                    + chr(10)
                    + '   —— 目录重组后路径模板没更新？**不许静默跳过**'
                      '（少一道闸门必须显式报出）')
            a = []
            for x in args:
                if x == '{files}':
                    a.extend(files)          # 展开成多个 argv 元素
                else:
                    a.append(x.format(files=files, routing=routing))
            add('%s·%s' % (label, kern), [PY, path, *a])

    # ── ③ 三内核各有专属判据（不对称的部分，显式列出）──────────────
    add('规则集内容·surge', [PY, 'self-conf-skills/run/surge/audit_ruleset_content.py',
                             ROUTING['surge']])
    add('规则集内容·clash', [PY, 'self-conf-skills/run/clash/audit_ruleset_content.py',
                             ROUTING['clash']])
    add('DNS 转发泄露·egern', [PY, 'self-conf-skills/run/egern/audit_dns_forward.py',
                               ROUTING['egern']])
    add('no-resolve 配对·egern', [PY, 'self-conf-skills/run/egern/audit_ruleset_noresolve.py',
                                  ROUTING['egern']])
    add('clash 结构', [PY, 'self-conf-skills/gates/clash/check_structure.py'])
    add('clash 脚本/静态对拍', [PY, 'self-conf-skills/gates/clash/check_script_sync.py'])
    add('脚本对拍 diff 自检', [PY, 'self-conf-skills/gates/clash/check_script_sync.py', '--self-test'])
    add('clash 头注数字新鲜度', [PY, 'self-conf-skills/gates/clash/check_header_numbers.py'])
    add('clash 规则集生成物', [PY, 'self-conf-skills/run/clash/build_rules.py', '--check'])
    add('clash 静态 profile 新鲜度', [PY, 'self-conf-skills/run/clash/build_profiles.py', '--check'])
    add('profile 结构', [PY, 'self-conf-skills/gates/check_structure.py'])
    add('smart 权重口径', [PY, 'self-conf-skills/gates/check_priority_weight.py'])
    add('规则集来源文档同步', [PY, 'self-conf-skills/gates/clash/check_ruleset_doc_sync.py'])

    # ── ④ 自托管清单的裸 IP 检测 ────────────────────────────────
    # 原为每份 .list 各开一道（3 道），但脚本本就支持多文件 ⇒ 合并成一道。
    # 新增自托管清单时**不必改这里**（扫 rules/*.list）。
    lists = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, 'rules', '*.list')))
    add('自托管清单·裸IP检测',
        [PY, 'self-conf-skills/run/egern/profile_ruleset.py', '--offline']
        + ['rules/' + x for x in lists])

    return G


def run_one(name, argv, extra_env):
    t0 = time.perf_counter()
    env = dict(os.environ)
    env.update({k: v for k, v in extra_env.items() if v})
    if 'GITHUB_TOKEN' in extra_env and not extra_env['GITHUB_TOKEN']:
        env.pop('GITHUB_TOKEN', None)
    # 运行时编码兜底：子进程默认以 UTF-8 输出，兜住 E4 静态判不到的情形（函数返回值 /
    # 运行时数据 / 多层 wrapper 等盲区）。已自带 reconfigure 或 import 编码垫片的脚本会覆盖
    # 本变量，行为不变。
    # ⚠️ 与 E4 **互补而非替代**：E4 是静态门禁、只读源码，不受这里影响 —— 因此注入不会
    #    掩盖 E4 能抓的问题。（早前「注入会掩盖」的判断已由 2026-10-02 实测推翻。）
    # ⚠️ 必须 setdefault，**不可**写成硬赋值 `env[...] = 'utf-8'`：CI 的「Encoding gate (cp936)」
    #    正是靠 `PYTHONIOENCODING=cp936` 从父进程传下来、再经这里**原样继承**给子进程，
    #    才能复现 Windows(ACP=936) 的管道路径。硬赋值会把继承来的 cp936 抹成 utf-8 ⇒
    #    那道闸门永远绿（空操作）。2026-10-02 实测：父进程设 cp936 时子进程仍报
    #    `CHILD-ENC: utf-8`、emoji 照常输出 —— 闸门形同虚设。
    #    「显式指定优先、缺省才兜底」也是这条兜底本该有的语义。
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=env, timeout=600)
        return {'name': name, 'argv': argv, 'code': r.returncode,
                'dt': time.perf_counter() - t0,
                'out': (r.stdout or '') + (r.stderr or '')}
    except Exception as e:                                   # noqa: BLE001
        return {'name': name, 'argv': argv, 'code': -1,
                'dt': time.perf_counter() - t0, 'out': f'{type(e).__name__}: {e}'}


def print_index():
    """--index：只读列出闸门清单（现抓 build_gates()），**不判负、不跑闸门、退出码 0**。

    存在理由：闸门清单不应被手抄成第二份。要引用清单时**用本命令现抓**。
    输出仅供**人读 + 文档引用**。
    """
    _assert_escapes_registered()
    gates = build_gates()
    print(f'闸门清单：{len(gates)} 道（现抓自 build_gates()，勿手抄成死表）\n')
    for i, (name, argv, env) in enumerate(gates, 1):
        need = '  [需 GITHUB_TOKEN]' if 'GITHUB_TOKEN' in env else ''
        print(f'{i:>2}. {name}{need}')
        print(f'      {" ".join(argv[1:])}')
    sys.exit(0)


def main():
    _selftest_env_scan()             # AST 判据注错回归
    _assert_escapes_registered()     # 环境变量登记（逃生门防后门）
    if '--index' in sys.argv:
        print_index()
    verbose = '-v' in sys.argv
    gates = build_gates()
    print(f'并行跑 {len(gates)} 道闸门（与 ci.yml 同源）…\n')
    with ThreadPoolExecutor(max_workers=min(len(gates), 8)) as ex:
        results = list(ex.map(lambda g: run_one(*g), gates))

    width = max(len(r['name']) for r in results)
    print(f"{'闸门':<{width}}  结果  耗时")
    print('-' * (width + 16))
    for r in results:
        mark = {0: '✅', 3: '⚠️', 2: '🔧'}.get(r['code'], '❌')
        print(f"{r['name']:<{width}}  {mark}   {r['dt']:.1f}s")
    print()

    # 退出码语义（全仓统一，troubleshoot-faq.md §8.2）：
    #   0 = 判据全过；1 = 有判负；2 = 前置环境不达标（计入失败）；3 = SKIP（未验证）
    failed = [r for r in results if r['code'] not in (0, 3)]
    env_fail = [r for r in results if r['code'] == 2]
    skipped = [r for r in results if r['code'] == 3]
    if not failed and not verbose:
        print('全部通过 —— 详细输出用 -v 查看。' if not skipped
              else '闸门全过（有 SKIP 项，见下）。')
    if failed or skipped or verbose:
        for r in results:
            if verbose or r['code'] != 0:
                tail = '\n'.join(r['out'].splitlines()[-30:]) or '(无输出)'
                print(f"──── {r['name']} (exit {r['code']}) {'─' * 30}")
                print(tail)
                print()
    if env_fail:
        print('🔧 以下闸门前置环境不达标（退出码 2）—— 先修环境，别读判据：'
              + '、'.join(r['name'] for r in env_fail))
    if skipped:
        print('⚠️ 以下闸门被跳过（未验证 ≠ 绿）：'
              + '、'.join(r['name'] for r in skipped))

    # ⚠️ 2026-10-08 第六轮审查问题 1：
    #    本文件 docstring 写着「CI 侧 3 视为失败」，但代码里**从来没有任何 CI 分支**，
    #    实际是 `sys.exit(1 if failed else 0)` ⇒ SKIP(3) 永远不算失败。
    #    后果：GITHUB_TOKEN 缺失/过期时 `Release 断言` 返回 3，而 verify_all 仍 exit 0
    #    ⇒ **Release 纪律在 CI 里被静默关掉，构建照样绿**。
    #    这正是本仓自己在防的「共享环境变量掩盖真实失败」。现按 docstring 的意图补上。
    # CI 里 SKIP(3) 视为失败 —— 读不到远端通常是 token 缺失或环境异常，不能静默放行。
    # （本仓已无「登记豁免」类的常态 SKIP：归档机制删除后 SKIP_V7 一并移除。）
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"
    if in_ci and skipped:
        print('🔴 CI 环境：以下未验证（exit 3）视为失败 —— '
              '读不到远端通常是 token 缺失或环境异常，不能静默放行：'
              + '、'.join(r['name'] for r in skipped))
        sys.exit(1)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
