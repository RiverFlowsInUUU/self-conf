#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""未定义名扫描 —— 抓「只在异常/判负路径上才炸」的潜伏 bug。

## 为什么单独有这道门（而不是装 pyflakes）

本仓已两次栽在**同一类** bug 上，且两次都潜伏很久：

| 位置 | 症状 | 潜伏原因 |
|:-----|:-----|:---------|
| `clash/check_script_sync.py` | 引用未定义的 `diff` | 现役配置恒一致 ⇒ `if` 恒假 ⇒ `diff` **从未被调用**；一旦真漂移就 `NameError` |
| `check_badges.py` | 引用未定义的 `NL` | 只在 `except`（profiles 解析失败）分支上；现役文件永远能解析 ⇒ 永不执行 |

两次的共同点：**只在"出错"路径上才炸**。而"出错路径"恰恰是门禁最有价值的时刻 ——
那时它给不出诊断，反而把**本意是 2（环境不达标）**变成**1（判负）**，
即"环境坏了被读成判据判负"，正是本仓全仓在防的事。

## 为什么不用 pyflakes

1. **外部依赖**：CI 只 `pip install pyyaml`。为一道门引入新依赖，要么改 CI（改动面大），
   要么在没装时 SKIP —— 而 SKIP 就是"未验证"，等于这道门在 CI 上默认不存在。
2. **噪声比**：pyflakes 对本仓报 29 条，其中**只有 1 条**是真 bug（`NL`），
   其余是 unused import / f-string 无占位符 / 变量赋值未用。**1/29 的信噪比**下，
   真 bug 会被淹没；而"全部修干净"意味着动 20 个文件的无关行（风险 > 收益）。
3. **本仓要的是判据，不是风格检查**：只扫 `F821 undefined name` 这一类，
   零依赖、零噪声、零豁免清单。

⇒ 结论：**只实现 F821 那一类**（约 60 行），判据窄但**零假红**，可以进 CI 常驻。

## 判据

对 `self-conf-skills/**/*.py` 逐个文件做**文件级**名字解析（不区分作用域，宁松勿紧 ——
松只可能漏报，紧会假红，而假红会让这道门被撤掉，见 §4.2.3.1 的教训）：

- 收集所有**绑定**：import / def / class / 赋值 / for 目标 / with as / except as /
  形参 / global / nonlocal / 推导式目标
- 所有 **Load 上下文**的 `Name` 若既不在绑定集、也不在内建、也不是已知魔术名 ⇒ 报出
- 文件里出现 `from X import *` ⇒ **该文件整体跳过**（静态无法判定，不假装能抓）

⚠️ 不判作用域顺序（先使用后定义不报）：那属于 pyflakes 的 `F821` 之外，
本仓没有这类写法，加了只会引入假红。

退出码：0 通过 / 1 发现未定义名 / 2 环境不具备（解析失败）。
"""
import ast
import builtins
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SCAN_DIR = os.path.join(ROOT, 'self-conf-skills')

# 解释器/框架注入的名字，不算未定义
MAGIC = {
    '__file__', '__name__', '__doc__', '__package__', '__spec__',
    '__loader__', '__builtins__', '__debug__', 'self', 'cls',
}

# ⚠️ 已知豁免：出现 `from X import *` 的文件静态判不出，整体跳过（不假装能抓）。
#    本仓当前**没有**这种文件；若有，必须在此登记理由（登记 = 人工看过）。
STAR_IMPORT_EXEMPT = {}


def _bound_names(tree):
    """收集文件里所有被绑定的名字（文件级，不区分作用域）。"""
    out = set()
    for nd in ast.walk(tree):
        if isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(nd.name)
            if hasattr(nd, 'args'):
                out.update(_arg_names(nd.args))
        elif isinstance(nd, ast.Lambda):
            out.update(_arg_names(nd.args))
        elif isinstance(nd, ast.Import):
            for al in nd.names:
                out.add((al.asname or al.name).split('.')[0])
        elif isinstance(nd, ast.ImportFrom):
            for al in nd.names:
                if al.name != '*':
                    out.add(al.asname or al.name)
        elif isinstance(nd, ast.Name) and isinstance(nd.ctx, (ast.Store, ast.Del)):
            out.add(nd.id)
        elif isinstance(nd, ast.ExceptHandler) and nd.name:
            out.add(nd.name)
        elif isinstance(nd, (ast.Global, ast.Nonlocal)):
            out.update(nd.names)
    return out


def _arg_names(args):
    out = set()
    for a in list(getattr(args, 'posonlyargs', [])) + list(args.args) \
            + list(args.kwonlyargs):
        out.add(a.arg)
    if args.vararg:
        out.add(args.vararg.arg)
    if args.kwarg:
        out.add(args.kwarg.arg)
    return out


def scan_file(fp):
    """返回 (未定义名列表[(名字, 行号)], 是否含 star-import)。"""
    src = open(fp, encoding='utf-8').read()
    tree = ast.parse(src)
    star = any(isinstance(n, ast.ImportFrom)
               and any(a.name == '*' for a in n.names) for n in ast.walk(tree))
    known = _bound_names(tree) | set(dir(builtins)) | MAGIC
    undef = []
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Name) and isinstance(nd.ctx, ast.Load) \
                and nd.id not in known:
            undef.append((nd.id, nd.lineno))
    undef.sort(key=lambda x: x[1])
    return undef, star


def main():
    if not os.path.isdir(SCAN_DIR):
        print('❌ 找不到 %s —— 未定义名扫描**未验证**' % SCAN_DIR)
        return 2

    bad, skipped, errs, nfiles = [], [], [], 0
    for dp, dirs, files in os.walk(SCAN_DIR):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in sorted(files):
            if not fn.endswith('.py'):
                continue
            nfiles += 1
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, ROOT).replace('\\', '/')
            try:
                undef, star = scan_file(fp)
            except SyntaxError as e:
                errs.append('%s 语法错误: %s' % (rel, e))
                continue
            except Exception as e:                              # noqa: BLE001
                errs.append('%s 解析失败: %s' % (rel, e))
                continue
            if star:
                if rel not in STAR_IMPORT_EXEMPT:
                    skipped.append(rel)
                continue
            if undef:
                bad.append((rel, undef))

    print('未定义名扫描（F821 类）—— 扫了 %d 个文件' % nfiles)
    print('-' * 78)
    if errs:
        for e in errs:
            print('  🔧 %s' % e)
        print('-' * 78)
        print('环境不达标（解析失败）—— 先修环境，别读判据')
        return 2
    if skipped:
        for r in skipped:
            print('  ⚠️ %s 含 `from ... import *`，静态判不出 ⇒ **未验证**' % r)
    if bad:
        for rel, undef in bad:
            print('  NG %s' % rel)
            for nm, ln in undef:
                print('       L%-5d %s' % (ln, nm))
        print('-' * 78)
        print('发现 %d 个文件引用了未定义的名字 —— 这类 bug 只在异常/判负路径上才炸，'
              '届时给不出诊断，还会把「环境不达标(2)」变成「判负(1)」。'
              % len(bad))
        return 1
    print('  OK 无未定义名')
    print('-' * 78)
    if skipped:
        print('通过，但有 %d 个文件**未验证**（见上）' % len(skipped))
        return 3
    print('全部通过')
    return 0


if __name__ == '__main__':
    # 中文 Windows 下 stdout 是 gbk：print ❌ 会 UnicodeEncodeError 且以 1 结束，
    # 而 1 恰是判负码 ⇒ 崩溃被误读成判负。每个独立脚本都得自己护住。
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    sys.exit(main())
