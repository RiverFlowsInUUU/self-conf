#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clash 仓门禁脚本的共用工具。

提供两件在 Windows / Git Bash 环境下反复踩坑的事：

① find_node() —— 定位 node 可执行文件
   Windows 上 Python 的 subprocess 不继承 Git Bash 扩展出来的 PATH，
   直接 subprocess.run(["node", ...]) 会 WinError 2。故显式探测。

② run_js_file() —— 执行 override/*.js 的 main() 并取回结果对象
   输出可能很大且含非 GBK 字符（emoji / 中文），走管道会被 cp936 编码炸掉
   （UnicodeDecodeError）。故让 node 把 JSON 写到临时文件，Python 再读。

③ utf8_stdout() —— 把 stdout/stderr 钉成 UTF-8
   中文 Windows 控制台默认 cp936，print 一个 ✅ 就 UnicodeEncodeError、
   进程以退出码 1 结束 —— 而 1 恰是"判负"的码，会被读成"判负其实没跑"。
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess


def utf8_stdout():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_NODE = None


def find_node():
    """定位 node，找不到抛 RuntimeError。"""
    global _NODE
    if _NODE:
        return _NODE
    exe = shutil.which("node")
    if exe:
        _NODE = exe
        return _NODE
    cands = [
        "C:/Program Files/nodejs/node.exe",
        "C:/Program Files (x86)/nodejs/node.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            _NODE = c
            return _NODE
    raise RuntimeError("找不到 node：请确认已安装 Node.js 并加入 PATH")


def run_main(path, config=None):
    """执行 override/*.js 的 main(config)，返回生成的配置对象。

    config 缺省为空订阅：{proxies: [], proxy-groups: [], rules: [], dns: {}}
    """
    node = find_node()
    cfg_js = json.dumps(config or {"proxies": [], "proxy-groups": [],
                                   "rules": [], "dns": {}}, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        js = (
            "const fs=require('fs');"
            "eval(fs.readFileSync(%s,'utf8'));"
            "const out=main(%s);"
            "require('fs').writeFileSync(%s, JSON.stringify(out), 'utf8');"
        ) % (json.dumps(os.path.abspath(path)),
             cfg_js,
             json.dumps(tmp))
        r = subprocess.run([node, "-e", js], capture_output=True,
                           timeout=90, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "node 执行失败")[:300])
        return json.load(open(tmp, encoding="utf-8"))
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
