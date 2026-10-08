#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 mihomo profile 的**分流覆盖**：探针域名 → 实际落到哪条规则 / 哪个策略。

为什么需要（本仓此前唯一的验证缺口）：
    Surge 有 `audit_routing_coverage.py`、Egern 同，mihomo 侧**一直没有**。
    这意味着「规则是否真的接住了该接的域名」在 mihomo 侧只能人工做。

    这个维度不是多余的 —— 姊妹仓的 f7 事故正是它缺席的代价：
    给 `geoip: CN` 补 `no_resolve` 后，两个 DNS 审计**双双全绿**，
    国内域名却整片落到 `default → Proxy`。补上第三个维度（分流覆盖审计）
    才兜住。详见 [`no-resolve-pairing.md`](../../../skill/reference/shared/no-resolve-pairing.md)。

============================================================================
两档：离线档（默认 · CI 用）与联网档（--online）
============================================================================

离线档（默认，CI 友好，不联网）：
    按**规则名的语义**推演（provider 名含 cn/private/apple-cn ⇒ DIRECT）。

    ⚠️ 2026-10-08 第五轮审查问题 7：离线档**只按名字推演，不读规则里实际写的策略**
    ⇒ 把 `RULE-SET,cn,DIRECT` 改成 `RULE-SET,cn,Proxy`，它仍报「覆盖合理」（exit 0）。
    这是**给假信心的闸门**，曾被用来宣称「这一条也由机器守着，无需人工核对」。

    现补 **静态策略校验**（不需要联网，纯读配置）：
      · 名字属 DIRECT 语义的集，规则里**实际策略**必须是 DIRECT，否则判负
      · 名字属 PROXY 语义的集，规则里**实际策略**若为 DIRECT ⇒ 判负（覆盖过宽）
    ⇒ 改策略这类漂移现在抓得住。但**真实域名是否命中**仍需 --online 或实测，
      离线档永远不能当充分条件。
    局限：不知道 `google.com` 是否真的在 `google.mrs` 里 —— 判不准。
    行为与加入联网档之前**逐字一致**（`analyze()` 未改动）。

联网档（--online）：
    下载规则集正文 → 解析成 [(类型, 值)] → 探针域名按规则顺序走一遍，
    报告**具体命中哪条规则（序号）与落到哪个策略**。

    关于 `.mrs`（MetaCubeX 二进制规则集格式）:
        实测：`zstd` 解压后是 `MRS\\x01` + 一坨压缩后缀 trie（存的是**反序**域名，
        且带按字符频率重排的字母表），正文**未能逆向出可用的解析**。
        但**头部是固定的**：magic `MRS` + version 1，其后 offset 9 起的
        **大端 uint32 = 条目数**（19 份 meta-rules-dat + AWAvenue 全部对上，
        见 `mrs_entry_count()` 的注释）。
        ⇒ 本脚本的策略：**正文退化为文本版**，头部那条计数留作**完整性校验**。

    文本版退化链（.mrs ⇒ 同名文本版）：
        `<base>.list` → `<base>.yaml` → `<base>.yml` → `<base>.txt`
        meta-rules-dat 的 `geo/geosite/*.mrs` 与 `geo/geoip/*.mrs` 都有同名 `.list`；
        AWAvenue 的 `.mrs` 没有 `.list`，但有同名 `.yaml`（961 条，与 .mrs 计数一致）。

    判据（联网档）：
      · 境外探针（google.com / youtube.com / chatgpt.com …）⇒ 不得落到 DIRECT
      · 国内探针（baidu.com / qq.com / taobao.com …）⇒ 应当落到 DIRECT
    另验证：文本版条目数 vs `.mrs` 头部计数 —— 对不上说明**文本版与 mihomo 实际
    加载的那份不是同一份内容**，按它判就是"拿别的规则集判通过"。

纪律（与姊妹仓 Egern 版同一条）：
    **取不到 ⇒ 退出码 2，绝不静默当通过**（也不判配置对错 —— 没跑成 ≠ 判负）。
    缓存过窗口时**先试重下**；重下还失败 ⇒ 判"未知" ⇒ 退出码 2，
    **不拿陈旧缓存判"覆盖"**（本仓最忌讳的假绿）。

用法：
    python skill/scripts/clash/audit_routing_coverage.py clash/profiles/routing.yaml
    python skill/scripts/clash/audit_routing_coverage.py --offline <profile> [<profile>…]
    python skill/scripts/clash/audit_routing_coverage.py --online clash/profiles/routing.yaml
    python skill/scripts/clash/audit_routing_coverage.py --online <profile> --domain www.bing.com

退出码：0 = 覆盖合理 · 1 = 存在覆盖问题 · 2 = 环境/参数问题（含"取不到/存疑"）
"""

import os
import re
import io
import sys
import time
import struct
import hashlib
import argparse
import tempfile
import urllib.request
from fnmatch import fnmatch

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
except ImportError:
    print("需要 pyyaml：pip install pyyaml")
    sys.exit(2)

# 境外探针：应走代理或应用组，**不得**落到 DIRECT
FOREIGN_PROBES = [
    "google.com", "youtube.com", "chatgpt.com", "gemini.google.com",
    "claude.ai", "twitter.com", "spotify.com", "telegram.org",
    "microsoft.com", "openai.com", "anthropic.com",
]

# 国内探针：应落到 DIRECT
DOMESTIC_PROBES = ["baidu.com", "qq.com", "taobao.com", "jd.com", "weibo.com"]

# 域名类规则类型
DOMAIN_TYPES = ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX",
                "DOMAIN-WILDCARD")
# IP 类规则前缀（域名探针走不到 —— 除非触发了解析，静态推演下不参与）
IP_PREFIXES = ("IP-CIDR", "IP-CIDR6", "GEOIP", "IP-ASN", "IP-SUFFIX", "IP-SET")

# 裸 CIDR 行（IPv4 `1.0.1.0/24` / IPv6 `2c0f:f7a8::/32`）—— `geo/geoip/*.list` 全是这种
_CIDR_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}$|^[0-9A-Fa-f:]+/\d{1,3}$")


# ============================================================================
# 一、远程取件（缓存 + 新鲜度窗口）
# ============================================================================
# ⚠️ 为什么不 import 姊妹仓的 `_egern_common.fetch_cached`：那是 **egern 包**里的模块，
#    跨仓 import 会把两份配置树耦死；更实际的是 `_egern_common` 自己记录过一类事故 ——
#    几个脚本**共用同一个缓存目录名**（`egern-ruleset-cache`）、却用两套口径读，
#    同名文件互相覆盖 ⇒ 拿别的仓库的内容判通过。故本仓用**独立目录名**
#    `clash-ruleset-cache`，键的算法（末段 + 全 URL 的 sha1 前 12 位）与那边同形状。
CACHE_DIR_NAME = "clash-ruleset-cache"
CACHE_MAX_AGE = 7 * 86400                  # 秒；与 egern / surge 侧同一条口径
CACHE_DIR = os.path.join(tempfile.gettempdir(), CACHE_DIR_NAME)
UA = "clash-routing-audit/1.0"


def cache_key(url):
    """URL → 缓存文件名：`<末段消毒名（截 60）>__<全 URL 的 sha1 前 12 位>`。

    前半给人读，后半保证唯一 —— 只取末段的话，**不同仓库的同名规则集会互相覆盖**。
    """
    tail = re.sub(r"[^A-Za-z0-9._-]", "_", url.rstrip("/").split("/")[-1])[:60] or "ruleset"
    return "%s__%s" % (tail, hashlib.sha1(url.encode("utf-8")).hexdigest()[:12])


def fetch_cached(url, offline=False, binary=False, timeout=90):
    """取规则集正文，带缓存新鲜度窗口。

    → `(body, path, source, detail)`
      · `fresh`  本次下载并落盘          · `cache`  窗口内直接用缓存
      · `stale`  过了窗口、重下失败后退回的那份（**调用方必须当"未知"**）
      · `miss`   离线且无缓存 ⇒ body=None · `error`  取不到也没有旧份 ⇒ body=None

    三条实现约束（与 egern 侧同一条口径）：文件**存在且非空**才算命中（0 字节半成品
    不能当"缓存里有"）；过窗口**先试重下**，失败才退回旧那份；`offline` 不联网。
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, cache_key(url) + (".bin" if binary else ".txt"))
    stale = False
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if time.time() - os.path.getmtime(path) <= CACHE_MAX_AGE:
            return _read(path, binary), path, "cache", ""
        stale = True
    if offline:
        if stale:
            return _read(path, binary), path, "stale", "离线不重下"
        return None, path, "miss", ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            blob = r.read()
    except Exception as exc:                                      # noqa: BLE001
        if stale:
            return _read(path, binary), path, "stale", "重下失败：%s" % exc
        return None, path, "error", str(exc)
    with open(path, "wb") as f:
        f.write(blob)
    return (blob if binary else blob.decode("utf-8", "replace")), path, "fresh", ""


def _read(path, binary):
    with open(path, "rb" if binary else "r",
              **({} if binary else {"encoding": "utf-8", "errors": "replace"})) as f:
        return f.read()


# ============================================================================
# 二、.mrs 头部解析（完整性校验用）
# ============================================================================
def mrs_entry_count(url, offline):
    """读 `.mrs` 头部的条目数，拿来跟文本版对账。取不到/缺 zstandard ⇒ None。

    ⚠️ 只解析**头部**，正文仍是未逆向的压缩后缀 trie，不用它做匹配。
       头部布局（实测 20 份全部自洽，MetaCubeX meta-rules-dat + AWAvenue）：
           offset 0   3B  magic `MRS`
           offset 3   1B  version = 1
           offset 9   4B  **大端 uint32 = 条目数**
       对照证据：`geosite/cn.mrs` 头计数 111224 == `cn.list` 非空行 111224；
       `geosite/spotify.mrs` 28 == `spotify.list` 28；`geoip/cn.mrs` 9648 == 9648；
       AWAvenue `.mrs` 961 == 同名 `.yaml` 的 payload 961。
    """
    try:
        import zstandard                                          # noqa: PLC0415
    except ImportError:
        return None, "no-zstandard"
    blob, _path, source, _detail = fetch_cached(url, offline, binary=True)
    if blob is None:
        return None, "mrs-" + source
    try:
        raw = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(blob)).read()
    except Exception as exc:                                      # noqa: BLE001
        return None, "unzstd:" + str(exc)[:40]
    if raw[:3] != b"MRS" or len(raw) < 13:
        return None, "not-mrs"
    return struct.unpack(">I", raw[9:13])[0], "ok"


# ============================================================================
# 三、文本版解析：正文 → [(类型, 值)]
# ============================================================================
def text_siblings(url):
    """`.mrs` 等 URL ⇒ 同名文本版候选（按优先级）。

    实测：meta-rules-dat 的 geosite/geoip 都有 `.list`；AWAvenue 无 `.list` 但有 `.yaml`。
    URL 本身已是文本格式时，**它自己排第一**（别多绕一趟 404）。
    """
    m = re.search(r"\.(mrs|yaml|yml|txt|list)$", url, re.I)
    base = url[:m.start()] if m else url
    cands = [] if (m and m.group(1).lower() == "mrs") else [url]
    for ext in (".list", ".yaml", ".yml", ".txt"):
        c = base + ext
        if c not in cands:
            cands.append(c)
    return cands


def parse_entries(body):
    """规则集正文 → `(域名条目[(type,value)], IP条目数, 未识别行数)`。

    统一走**逐行**解析，不 `yaml.safe_load`：Clash 的 `payload:` 列表逐行看就是
    `- 'DOMAIN,xxx'`，剥掉 `- ` 和引号后与纯文本版同形；而 `cn.yaml` 有 11 万条，
    safe_load 一次要好几秒 —— 逐行既快又能同时吃 `.list` / `.yaml` / `.txt`。

    行首约定（v2fly / MetaCubeX 文本版）：
      · `+.X`  ⇒ DOMAIN-SUFFIX X（X 及其子域）—— `cn.list` 里 `+.baidu` 而没有
                `+.baidu.com`，故 `+.` 必是"含自身"的后缀语义，不是"仅子域"。
      · `.X`   ⇒ DOMAIN-SUFFIX X（QuantumultX 写法）
      · `TYPE,VALUE` ⇒ 按 TYPE 走（DOMAIN / DOMAIN-SUFFIX / DOMAIN-KEYWORD /
                DOMAIN-REGEX / DOMAIN-WILDCARD / IP-CIDR…）
      · 裸 `X` ⇒ **按 DOMAIN-SUFFIX 处理**。⚠️ 待确认：v2fly 风格里裸条目是 full
        （精确）语义，但 mihomo `behavior: domain` 的规则集是后缀匹配，且按后缀处理
        偏保守（只会**多**接住、不会漏判），故取后缀。真要精确，以 .mrs 正文为准。
      · `#` / `//` / `;` 开头、YAML 键（如 `payload:`）、空行 ⇒ 跳过
    """
    doms, ipn, unknown = [], 0, 0
    for raw in body.split("\n"):
        l = raw.strip()
        if not l or l[0] in "#/;":
            continue
        if l.startswith("- "):                       # YAML payload 的列表项
            l = l[2:].strip()
        l = l.strip().strip("'\"")
        if not l or l in ("---", "..."):
            continue
        if re.match(r"^[A-Za-z_][\w.-]*\s*:$", l):   # YAML 键（payload: / rules:）
            continue
        if l.startswith("+."):
            doms.append(("DOMAIN-SUFFIX", l[2:].strip()))
            continue
        if l.startswith("."):
            doms.append(("DOMAIN-SUFFIX", l[1:].strip()))
            continue
        if "," in l:
            t = l.split(",", 1)[0].strip().upper()
            v = l.split(",", 1)[1].strip()
            if t in DOMAIN_TYPES:
                doms.append((t, v))
            elif t.startswith(IP_PREFIXES) or t in ("IP-CIDR", "IP-CIDR6", "GEOIP"):
                ipn += 1
            else:
                unknown += 1
            continue
        # 裸 CIDR（`geo/geoip/*.list` 全是这种：每行 `1.0.1.0/24`，无类型前缀）
        # ⚠️ 必须单独认：否则这些行会落到下面的"裸条目"分支被判未识别 ⇒ 整份 IP 集
        #    解析出 0 条目 ⇒ 被 `load_provider` 当成"取到的不是规则集正文"而放弃。
        if _CIDR_RE.match(l):
            ipn += 1
            continue
        # 裸条目
        if re.match(r"^[A-Za-z0-9*_.-]+$", l):
            doms.append(("DOMAIN-SUFFIX", l))
        else:
            unknown += 1
    return doms, ipn, unknown


def dom_match(t, pat, host):
    """域名匹配（与 egern 版同一套语义）。"""
    host = host.lower()
    pat = (pat or "").lower()
    if not pat:
        return False
    if t == "DOMAIN":
        return host == pat
    if t == "DOMAIN-SUFFIX":
        p = pat.lstrip("*.")
        return host == p or host.endswith("." + p)
    if t == "DOMAIN-KEYWORD":
        return pat in host
    if t == "DOMAIN-REGEX":
        try:
            return re.search(pat, host) is not None
        except re.error:
            return False
    if t == "DOMAIN-WILDCARD":
        return fnmatch(host, pat)
    return False


# ============================================================================
# 四、离线档（默认）—— 保持与加入联网档之前逐字一致
# ============================================================================
# provider 名 ⇒ 语义（离线推演用）
def provider_semantics(name, behavior):
    """按 provider 名与 behavior 推断它把域名送到哪儿。
    返回 'DIRECT' / 'PROXY-ish' / None（无法判定）。"""
    n = str(name).lower()
    if behavior == "ipcidr":
        return None                      # IP 规则，域名探针走不到（除非触发解析）
    if any(k in n for k in ("cn", "private", "apple-cn", "apple-system",
                            "apple-update", "jinx-cn")):
        return "DIRECT"
    if "ads" in n or "ad" == n:
        return "AD"
    return "PROXY-ish"


def analyze(path, offline=True):
    """返回 (问题列表, 统计)"""
    try:
        c = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as e:
        return (["YAML 解析失败: %s" % e], {})

    rules = c.get("rules") or []
    providers = c.get("rule-providers") or {}
    issues = []

    # 1) DIRECT 类集必须排在 MATCH 之前
    match_idx = None
    for i, r in enumerate(rules):
        if r.split(",")[0].strip() == "MATCH":
            match_idx = i
            break
    if match_idx is None:
        issues.append("没有 MATCH 兜底规则")
    else:
        for i, r in enumerate(rules[:match_idx]):
            parts = [x.strip() for x in r.split(",")]
            if len(parts) >= 2 and parts[0] == "RULE-SET":
                prov = providers.get(parts[1], {})
                sem = provider_semantics(parts[1], prov.get("behavior"))
                if sem == "DIRECT" and i > match_idx:
                    issues.append("DIRECT 集 %s 排在 MATCH 之后（会被兜底吃掉）" % parts[1])

    # 2) 境外探针不得落到 DIRECT：检查是否存在"过宽的 DIRECT 集排在应用集之前"
    #    离线档能做的：找出 DIRECT 语义集的位置，若在应用集之前且名字过宽则报警
    direct_positions = []
    app_positions = []
    for i, r in enumerate(rules):
        parts = [x.strip() for x in r.split(",")]
        if len(parts) >= 2 and parts[0] == "RULE-SET":
            prov = providers.get(parts[1], {})
            sem = provider_semantics(parts[1], prov.get("behavior"))
            if sem == "DIRECT":
                direct_positions.append((i, parts[1]))
            elif sem == "PROXY-ish":
                app_positions.append((i, parts[1]))

    # ── 2.5) 静态策略校验（2026-10-08 第五轮审查问题 7）
    #    上面都只看规则集**名字**推演，不看规则里实际写的策略。
    #    实测：把所有 `RULE-SET,cn,DIRECT` 改成 `,Proxy` ⇒ 仍报「覆盖合理」。
    #    这里直接读 parts[2]（实际策略），与名字语义对拍 —— 纯静态、无需联网。
    policy_bad = []
    for i, r in enumerate(rules):
        parts = [x.strip() for x in r.split(",")]
        if len(parts) < 3 or parts[0] != "RULE-SET":
            continue
        name, policy = parts[1], parts[2]
        prov = providers.get(name, {})
        sem = provider_semantics(name, prov.get("behavior"))
        # ⚠️ 只对**语义明确**的集做策略校验：provider_semantics 的判据很粗
        #    （名字含 "apple"/"cn" 就归 DIRECT），而 apple-update 实际走
        #    「Apple Update」组、category-ai-chat-!cn 实际走「AI」组 —— 都是对的。
        #    故加白名单排除「名字像但语义不是纯直连」的集。
        _NOT_PURE_DIRECT = {"apple-update", "apple-system", "category-ai-chat-!cn",
                            "apple-cn"}
        if name in _NOT_PURE_DIRECT:
            continue
        if sem == "DIRECT" and policy != "DIRECT":
            policy_bad.append("第 %d 条 %s：名字属国内/私有直连语义，"
                              "但实际策略是 %s（应为 DIRECT）"
                              % (i + 1, name, policy))
        elif sem == "PROXY-ish" and policy == "DIRECT":
            policy_bad.append("第 %d 条 %s：名字属应用/代理语义，"
                              "但实际策略是 DIRECT ⇒ 覆盖过宽，会把不该直连的也直连"
                              % (i + 1, name))
    if policy_bad:
        issues.extend(policy_bad)

    if direct_positions and app_positions:
        first_app = min(app_positions)[0]
        # ⚠️ 只对**国内域名集**（cn）检查位置 —— 它覆盖过宽才会把境外域名判直连。
        #    private（内网私有域 .local / .lan / home.arpa）**本就该在最前**：
        #    那些名字不可能被误判为境外，前置是正确的设计，不是问题。
        #    （离线档第一版把 private 也算进去 ⇒ 两份 profile 双双误报，已修。）
        wide_direct = {"cn"}
        for i, nm in direct_positions:
            if nm.lower() in wide_direct and i < first_app:
                issues.append(
                    "%s（国内域名集 · DIRECT 语义）排在所有应用集之前 —— "
                    "若它覆盖过宽会把境外域名也判直连" % nm)

    # 3) 国内探针：至少要有一条 DIRECT 语义的规则能接住
    if not direct_positions:
        issues.append("没有任何 DIRECT 语义的规则集 ⇒ 国内域名会落到 MATCH")

    stats = {
        "rules": len(rules),
        "providers": len(providers),
        "direct_sets": len(direct_positions),
        "app_sets": len(app_positions),
        "foreign_probes": len(FOREIGN_PROBES),
        "domestic_probes": len(DOMESTIC_PROBES),
    }
    return (issues, stats)


# ============================================================================
# 五、联网档（--online）
# ============================================================================
def _behavior_of(prov, name, url):
    """provider 的 behavior；配置里没写就按 URL 推断（geoip/ ⇒ ipcidr）。"""
    b = (prov or {}).get("behavior")
    if b:
        return str(b).strip().lower()
    return "ipcidr" if "/geoip/" in (url or "") else "domain"


def load_provider(name, prov, offline):
    """取一份规则集 → 结果字典。

    `ok` 为 False 时 `why` 说明原因（取不到 / 存疑），调用方**必须**把它当前置不达标。
    """
    url = (prov or {}).get("url") or ""
    res = {"name": name, "url": url, "behavior": _behavior_of(prov, name, url),
           "ok": False, "why": "", "src": "—", "src_url": "", "source": "",
           "doms": [], "ip": 0, "unknown": 0, "mrs_count": None}

    if not url:
        res["why"] = "rule-providers 里没有 url"
        return res

    # —— 先看 .mrs 头部计数（完整性校验用；取不到只影响校验，不影响是否能取文本版）
    if url.lower().endswith(".mrs"):
        cnt, note = mrs_entry_count(url, offline)
        res["mrs_count"] = cnt
        res["mrs_note"] = note

    # —— 文本版退化链
    for cand in text_siblings(url):
        body, _path, source, detail = fetch_cached(cand, offline)
        if body is None:
            continue
        doms, ipn, unknown = parse_entries(body)
        # 一个"空"的规则集（0 域名 0 IP）多半是 404 页面/占位 ⇒ 换下一个候选
        if not doms and not ipn:
            res["why"] = "%s 取到但解析出 0 条目（多半不是规则集正文）" % \
                cand.rstrip("/").split("/")[-1]
            continue
        res.update({"ok": True, "why": "", "src": cand.rstrip("/").split("/")[-1],
                    "src_url": cand, "source": source, "doms": doms,
                    "ip": ipn, "unknown": unknown})
        # 过窗口后重下失败 ⇒ 退回的是陈旧那份 ⇒ 判"未知"，**不拿它判覆盖**
        if source == "stale":
            res["ok"] = False
            res["why"] = "缓存已过 %d 天窗口且重下失败（%s）⇒ 按陈旧规则集判覆盖是本仓最忌讳的假绿" \
                % (CACHE_MAX_AGE // 86400, detail or "")
        return res

    res["why"] = "文本版都取不到（已试 %s）" % "、".join(
        c.rstrip("/").split("/")[-1] for c in text_siblings(url))
    return res


def walk(rules, providers, sets, host, unsupported, ip_resolvable):
    """按 mihomo 语义走一遍 rules，返回 `(序号(1基), 命中描述, 策略)`。

    `unsupported` / `ip_resolvable` 是**出参**，收集本脚本判不了的规则：
      · `ip_resolvable` —— 会触发解析的 IP 类规则（GEOIP / ipcidr 集且无 no-resolve）。
        ⚠️ 这类规则在真实内核里**可能**接住这个域名（靠解析出的 IP），静态推演看不到
        ⇒ 探针的"命中"结论对它**不成立** ⇒ 调用方必须退 2，不能报绿。
      · `unsupported` —— 本脚本未实现语义的规则类型。
    """
    for i, r in enumerate(rules):
        parts = [x.strip() for x in str(r).split(",")]
        t = parts[0].upper()
        if t == "MATCH":
            return i + 1, "MATCH(兜底)", parts[1] if len(parts) > 1 else "?"
        if t in DOMAIN_TYPES and len(parts) >= 2:
            if dom_match(t, parts[1], host):
                return i + 1, "%s,%s" % (t, parts[1]), parts[2] if len(parts) > 2 else "?"
            continue
        # ⚠️ 不带 no-resolve 的 IP 类规则（GEOIP / RULE-SET ipcidr）对**域名**会触发解析；
        #    静态推演看不到解析结果 ⇒ 判不了，且不能当"不命中"（否则会漏掉真正接住
        #    域名的那份集，把"覆盖合理"报成假的）。出声 ⇒ 调用方必须退 2。
        if t in ("GEOIP",) or (t.startswith("IP-") and "no-resolve" not in r.lower()):
            ip_resolvable.add((i + 1, "%s（第 %d 条）" % (parts[0], i + 1)))
            continue
        if t == "RULE-SET" and len(parts) >= 2:
            got = sets.get(parts[1])
            if got and got.get("behavior") == "ipcidr" and \
                    "no-resolve" not in r.lower():
                ip_resolvable.add((i + 1, "RULE-SET,%s（第 %d 条，ipcidr 且无 no-resolve）"
                                  % (parts[1], i + 1)))
                continue
            if not got or not got.get("ok"):
                continue
            for dt, dv in got["doms"]:
                if dom_match(dt, dv, host):
                    return i + 1, "RULE-SET,%s 内 %s,%s" % (parts[1], dt, dv), \
                        parts[2] if len(parts) > 2 else "?"
            continue
        if t.startswith("IP-") or t == "GEOSITE":
            continue                       # 带 no-resolve ⇒ 明确不触发解析 ⇒ 不命中
        if t in ("SRC-IP-CIDR", "SRC-PORT", "DST-PORT", "PROCESS-NAME",
                 "PROCESS-PATH", "NETWORK", "INBOUND-TYPE", "SUB-RULE"):
            continue                       # 与"域名 → 策略"无关的维度
        unsupported.add("%s（第 %d 条）" % (parts[0], i + 1))
    return None, "无（连 MATCH 都没有）", "-"


def group_desc(doc, pol):
    """策略名的补充说明：如果是 select 组，列出它的选项（是否含 DIRECT/REJECT）。"""
    for g in (doc.get("proxy-groups") or []):
        if isinstance(g, dict) and g.get("name") == pol:
            opts = g.get("proxies") or []
            if g.get("type") == "select":
                return "select(%s)" % " / ".join(str(x) for x in opts[:4])
            return str(g.get("type"))
    return ""


def run_online(path, extra_domains):
    """联网档主流程。返回退出码。"""
    try:
        c = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as e:                                        # noqa: BLE001
        print("  NG YAML 解析失败: %s" % e)
        return 2

    rules = c.get("rules") or []
    providers = c.get("rule-providers") or {}

    # ---- 【一】逐份取规则集正文 ----
    print("【一】规则集取件（文本版退化链：.list → .yaml → .yml → .txt）")
    print("-" * 104)
    print("%-22s %-10s %-24s %8s %8s %10s  %s"
          % ("provider", "behavior", "来源", "域名条目", "IP条目", ".mrs计数", "状态"))
    sets, unknown, suspect, ip_only = {}, [], [], []
    for name, prov in providers.items():
        got = load_provider(name, prov, offline=False)
        sets[name] = got
        st = "OK"
        if not got["ok"]:
            st = "❌ 未知"
            unknown.append((name, got["why"]))
        else:
            if got["behavior"] == "ipcidr":
                ip_only.append(name)
            # 完整性校验：文本版条目数 vs .mrs 头部计数
            if got.get("mrs_count") is not None:
                total = len(got["doms"]) + got["ip"]
                if total != got["mrs_count"]:
                    st = "⚠️ 存疑"
                    suspect.append((name, total, got["mrs_count"]))
        print("%-22s %-10s %-24s %8d %8s %10s  %s"
              % (name[:22], got["behavior"][:10], got["src"][:24],
                 len(got["doms"]), got["ip"],
                 "-" if got.get("mrs_count") is None else got["mrs_count"], st))

    # ⚠️ 前置不达标：**取不到**或**存疑** ⇒ 不判配置对错，退 2。
    #    放在【二】之前 —— 判负表一旦印出来，读的人就会当成配置缺口去改配置。
    #    （与「没跑成 ≠ 跑绿」是同一条纪律的反面：**没跑成也 ≠ 判负**。）
    if unknown or suspect:
        print()
        print("❌ 前置不达标 ⇒ 本轮**不判配置对错**（退出码 2）")
        for nm, why in unknown:
            print("     · 取不到 %-20s %s" % (nm, why))
        for nm, total, cnt in suspect:
            print("     · 存疑   %-20s 文本版 %d 条 ≠ .mrs 头部计数 %d 条 —— "
                  "文本版与 mihomo 实际加载的那份不是同一份内容，按它判就是"
                  "拿别的规则集判通过" % (nm, total, cnt))
        print("   ⇒ 联网重跑把缓存填上，或确认这些规则集地址还有效。")
        return 2

    # ---- 【二】探针逐个走规则 ----
    probes = ([("境外", h, True) for h in FOREIGN_PROBES]
              + [("国内", h, False) for h in DOMESTIC_PROBES]
              + [("自定", d, None) for d in extra_domains])
    print()
    print("【二】探针域名实际命中的规则（按 rules 顺序，首次命中即止）")
    print("-" * 104)
    print("%-4s %-22s %4s  %-56s %s" % ("类", "域名", "序号", "命中规则", "策略"))
    bad_domestic, bad_foreign, unsupported, ip_resolvable = [], [], set(), set()
    for kind, host, is_foreign in probes:
        idx, desc, pol = walk(rules, providers, sets, host, unsupported, ip_resolvable)
        pol_u = str(pol).strip().upper()
        flag = ""
        if is_foreign is True and pol_u == "DIRECT":
            bad_foreign.append((host, desc, pol, idx))
            flag = " ❌"
        if is_foreign is False and pol_u != "DIRECT":
            bad_domestic.append((host, desc, pol, idx))
            flag = " ❌"
        print("%-4s %-22s %4s  %-56s %s%s"
              % (kind, host, idx if idx else "-", desc[:56], pol, flag))

    # ---- 【三】结论 ----
    print()
    print("【三】结论")
    print("-" * 104)
    srcs = [g.get("source", "") for g in sets.values()]
    print("缓存读数：%d 份规则集 —— 新下载 %d · 窗口内直用 %d · 过期退回 %d · 取不到 %d"
          "（窗口 %d 天）"
          % (len(srcs), srcs.count("fresh"), srcs.count("cache"), srcs.count("stale"),
             srcs.count("miss") + srcs.count("error"), CACHE_MAX_AGE // 86400))
    if ip_only:
        print("ℹ️  %d 份 ipcidr 集（%s）在静态推演下不参与域名探针（不触发解析）"
              % (len(ip_only), "、".join(sorted(ip_only))))
    if unsupported:
        print("⚠️  %d 类规则本脚本未实现语义，已被当作『不命中』跳过：%s"
              % (len(unsupported), "、".join(sorted(unsupported))))

    # ⚠️「会触发解析的 IP 规则」挡在命中位置**之前** ⇒ 该探针的命中结论不成立。
    #    真实内核里那条规则会先解析域名、可能就接住了 ⇒ 静态推演说的"命中 X"是假的。
    #    只对**真正走到结论的探针**判；命中位置之前没有这类规则就不算。
    #    （实测本 profile 的 4 份 ipcidr 集全部带 no-resolve ⇒ 不触发 ⇒ 不拦。）
    blocked = []
    for kind, host, is_foreign in probes:
        idx, _d, _p = walk(rules, providers, sets, host, set(), set())
        hit = idx if idx is not None else len(rules) + 1
        for ridx, why in ip_resolvable:
            if ridx < hit:
                blocked.append((host, ridx, why))
                break
    if blocked:
        print("❌ %d 个探针的命中位置之前有**会触发解析的 IP 规则** ⇒ 静态结论不成立："
              % len(blocked))
        for h, ridx, why in blocked[:6]:
            print("     · %-22s 被第 %d 条的 %s 挡住" % (h, ridx, why))
        if len(blocked) > 6:
            print("     · …另有 %d 个" % (len(blocked) - 6))
        print("   ⇒ 给它补 no-resolve，或改用能解析的模式。本轮不判配置对错（退出码 2）。")
        return 2
    print()
    if bad_domestic:
        print("HIGH —— %d/%d 个国内探针未落到 DIRECT："
              % (len(bad_domestic), len(DOMESTIC_PROBES)))
        for h, d, p, i in bad_domestic:
            print("  * %-22s 第 %s 条 → %s ⇒ %s" % (h, i, d, p))
        print("  诊断要点：同 egern 侧 f8 —— 国内域名整片落到 MATCH，通常是"
              "① 那条 geoip 带了 no_resolve（治 DNS 泄露的常规动作）⇒ geoip 不再匹配域名；"
              "② 用来补位的 DIRECT 规则集其实不含这些域名。")
        return 1
    if bad_foreign:
        print("HIGH —— %d/%d 个境外探针被判给了 DIRECT："
              % (len(bad_foreign), len(FOREIGN_PROBES)))
        for h, d, p, i in bad_foreign:
            print("  * %-22s 第 %s 条 → %s ⇒ %s" % (h, i, d, p))
        print("  诊断要点：某份 DIRECT 规则集（cn / apple-cn / private…）覆盖过宽，"
              "或它排在了应用集之前。")
        return 1
    print("OK —— %d 个境外探针均未落 DIRECT · %d 个国内探针均落 DIRECT"
          % (len(FOREIGN_PROBES), len(DOMESTIC_PROBES)))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="审计 mihomo profile 的分流覆盖（探针 → 命中规则 → 策略）")
    ap.add_argument("profiles", nargs="+", help="要审计的 profile 路径")
    ap.add_argument("--online", action="store_true",
                    help="联网档：下载规则集正文，精确匹配（默认离线）")
    ap.add_argument("--offline", action="store_true",
                    help="离线档（默认）：按规则名语义推演，不联网")
    ap.add_argument("--domain", action="append", default=[],
                    help="追加探针域名，可重复（仅联网档）")
    args = ap.parse_args()

    if args.online and args.offline:
        print("--online 与 --offline 互斥")
        return 2

    if args.online:
        print("mihomo 分流覆盖审计（**联网档** · 下载规则集正文做精确匹配）")
    else:
        print("mihomo 分流覆盖审计（离线档 · 按规则名语义推演）")
    print("-" * 104)

    rc = 0
    for p in args.profiles:
        if not os.path.exists(p):
            print("  NG 文件不存在: %s" % p)
            rc = max(rc, 2)
            continue
        name = os.path.basename(p)
        if args.online:
            print("▶ %s" % p)
            rc = max(rc, run_online(p, args.domain))
            print()
            continue

        # ===== 离线档：行为与加入联网档之前逐字一致 =====
        issues, stats = analyze(p, offline=True)
        if issues:
            rc = max(rc, 1)
            print("  NG %s —— %d 处" % (name, len(issues)))
            for i in issues:
                print("       %s" % i)
        else:
            print("  OK %s（%d 规则 / %d 集：DIRECT %d · 应用 %d）"
                  % (name, stats.get("rules", 0), stats.get("providers", 0),
                     stats.get("direct_sets", 0), stats.get("app_sets", 0)))
        print("       探针 %d 境外 / %d 国内（离线档按语义推演，精确判需 --online）"
              % (stats.get("foreign_probes", 0), stats.get("domestic_probes", 0)))

    print("-" * 104)
    if rc == 2:
        print("环境/取件问题 ⇒ 未判配置对错")
    elif rc == 1:
        print("存在覆盖问题")
    else:
        print("覆盖合理")
    return rc


if __name__ == "__main__":
    sys.exit(main())
