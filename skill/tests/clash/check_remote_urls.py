#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""远程资源可达性检查 —— 所有被引用的远程规则集 URL 必须活着。

为什么单独要这一项（本仓的切肤之痛）：
    Jinx 上游把 `*-white-guard.*` 改名为 `*-direct.*`，本仓脚本里那条
    `mihomo-white-guard.yaml` 就此 404。分流版改配置时碰巧发现并修了，
    **懒人版一直挂着死链没人察觉** —— 因为本仓没有 CI，没人定期去问
    「这个 URL 还活着吗」。

    死链的后果不是报错，是**静默降级**：rule-provider 拉不到就变成空集，
    该走 AD 的广告全进了兜底出口，配置看着跑得挺好，其实拦截没了。

判据：
    · 从 override/*.js 与 profiles/*.yaml 里抽出所有 http(s) 远程资源 URL
    · 逐个 HEAD（失败则退化为 GET Range）探测
    · 非 2xx / 3xx 即判负，并打印 URL 与出处

豁免：
    · 占位地址（`sub.example.com`、`REPLACE_WITH_YOUR_TOKEN`）跳过 ——
      那是给用户替换的订阅槽位，本来就不该可达
    · 本仓 raw 地址在文件刚推送、CDN 未同步时可能短暂 404，
      用 `--skip-self` 跳过（CI 里对本仓地址用重试而非跳过）

退出码：0 = 全部可达 · 1 = 存在死链 · 2 = 用法/环境问题
用法：python skill/tests/check_remote_urls.py [--skip-self] [--timeout N]
"""

import os
import re
import sys
import subprocess

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def _default_root():
    """仓库根；整合仓里 clash 配置位于 clash/ 子目录，自动识别。"""
    r = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    if os.path.isdir(os.path.join(r, "clash", "profiles")):
        return os.path.join(r, "clash")
    return r

ROOT = _default_root()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "clash")))
try:
    from _clash_common import run_main
except Exception:
    run_main = None

# 占位/示例地址：本来就该不可达，不参与探测
PLACEHOLDER_PAT = re.compile(
    r"(example\.com|example\.org|REPLACE_WITH|YOUR_TOKEN|localhost|127\.0\.0\.1)",
    re.I,
)

URL_PAT = re.compile(r"https?://[^\s\"'`,)\]]+")

SELF_PREFIX = "https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/"

# 基址常量：脚本里用 `BASE + "xxx.mrs"` 拼接，基址本身不是可探测的资源
BASE_URLS = (
    "https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/main/icons/",
    "https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/main/",
    "https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo",
)

# DoH 端点：是解析器不是静态资源，HEAD 往往不通，且不属于"规则集"范畴
DOH_PAT = re.compile(r"/dns-query$", re.I)

# 健康检查探针：连通性探测用，不是规则集资源
HC_URLS = ("https://www.gstatic.com/generate_204",)

# 只有这些后缀才是"静态规则集资源"，其它一概不探测 —— 避免误判
RESOURCE_SUFFIX = (".mrs", ".yaml", ".yml", ".list", ".txt", ".json")


def collect_urls():
    """(url, 出处) 列表，去重保序。"""
    seen = {}
    targets = []
    for d in ("override", "profiles"):
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if not fn.endswith((".js", ".yaml", ".yml")):
                continue
            p = os.path.join(base, fn)
            try:
                txt = open(p, encoding="utf-8").read()
            except Exception:
                continue
            for m in URL_PAT.finditer(txt):
                url = m.group(0).rstrip(".,;")
                if PLACEHOLDER_PAT.search(url):
                    continue
                if any(url.startswith(b) for b in BASE_URLS):
                    continue
                if DOH_PAT.search(url) or url in HC_URLS:
                    continue
                if not url.lower().endswith(RESOURCE_SUFFIX):
                    continue
                if url not in seen:
                    seen[url] = "%s/%s" % (d, fn)
                    targets.append((url, seen[url]))
    return targets


def collect_from_scripts():
    """执行 override/*.js 的 main()，取真实生成的 rule-providers URL 与图标。

    脚本里 MRS 是 `JS + "/geosite/" + c + ".mrs"` 拼接出来的，纯文本扫描
    抓不到完整 URL —— 必须真的跑一遍脚本才能拿到最终地址。
    """
    if run_main is None:
        print("  ! 无法导入 _clash_common，跳过脚本运行期收集")
        return []
    urls = []
    for fn in sorted(os.listdir(os.path.join(ROOT, "override"))):
        if not fn.endswith(".js"):
            continue
        p = os.path.join(ROOT, "override", fn)
        try:
            out = run_main(p)
        except Exception as e:
            print("  ! %s 跳过: %s" % (fn, str(e)[:100]))
            continue
        for u in (out.get("rule-providers") or {}).values():
            if u.get("url"):
                urls.append((u["url"], "override/%s (运行期)" % fn))
        for g in out.get("proxy-groups") or []:
            if g.get("icon"):
                urls.append((g["icon"], "override/%s (图标)" % fn))
    return urls


def probe(url, timeout):
    """返回 (ok, 状态说明)。HEAD 不通则退化为 GET（部分 CDN 不支持 HEAD）。"""
    for method in ("HEAD", "GET"):
        cmd = ["curl", "-sS", "-L", "--max-time", str(timeout),
               "-o", os.devnull, "-w", "%{http_code}", "-X", method, url]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            code = (r.stdout or "").strip()[-3:]
            if code.isdigit():
                c = int(code)
                if 200 <= c < 400:
                    return True, str(c)
                last = "%s=%s" % (method, c)
            else:
                last = "%s 无响应" % method
        except subprocess.TimeoutExpired:
            last = "%s 超时" % method
        except Exception as e:
            last = "%s 异常 %s" % (method, type(e).__name__)
    return False, last


def main():
    args = [a for a in sys.argv[1:]]
    skip_self = "--skip-self" in args
    timeout = 15
    if "--timeout" in args:
        try:
            timeout = int(args[args.index("--timeout") + 1])
        except Exception:
            pass

    targets = collect_urls() + collect_from_scripts()
    # 去重保序
    _seen = set()
    _t = []
    for u, src in targets:
        if u not in _seen:
            _seen.add(u)
            _t.append((u, src))
    targets = _t
    if not targets:
        print("未收集到任何远程 URL —— 检查收集规则")
        return 2

    print("远程资源可达性检查 —— 共 %d 个 URL" % len(targets))
    print("-" * 78)
    dead = []
    for url, src in targets:
        if skip_self and url.startswith(SELF_PREFIX):
            print("  ~ 跳过(本仓) %s" % url[:70])
            continue
        ok, note = probe(url, timeout)
        print("  %s %-62s %s" % ("OK" if ok else "NG", url[:62], note if not ok else ""))
        if not ok:
            dead.append((url, src, note))

    print("-" * 78)
    if dead:
        print("死链 %d 个：" % len(dead))
        for url, src, note in dead:
            print("  NG(%s) %s" % (note, url))
            print("        出处: %s" % src)
        return 1
    print("全部可达")
    return 0


if __name__ == "__main__":
    sys.exit(main())
