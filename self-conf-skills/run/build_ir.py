#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_ir.py — 三内核路由意图的统一中间表示（IR）· 给 AI 读的规范化视图。

⚠️ 本脚本**只读**三内核配置，绝不改它们（AGENTS.md：三内核「对齐」是刻意的，别去修）。
它把 surge/egern/clash 三份不同格式的规则与策略组抽成一套**规范、可机读**的意图模型，
落成 self-conf-skills/references/intent.json —— 让任何 AI 一眼看懂「我的流量到底怎么分流」，
不必再逐个啃三种格式。

它**不判负任何内核间差异**：Surge 用 smart / mihomo 用 url-test、份数不同、规则名不同
—— 这些都是刻意的，IR 只如实呈现并标注，不做「对齐」判断。

用法：
    python build_ir.py           # 重新生成 references/intent.json（改完配置后跑）
    python build_ir.py --check   # 只校验 intent.json 是否为最新（不写）——闸门用
退出码：0 = 最新/已写 · 1 = 过期（--check 且与重算不一致）· 2 = 环境/解析失败。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except Exception as e:  # pragma: no cover
    sys.stderr.write("缺少 pyyaml：%s\n" % e)
    raise SystemExit(2)

try:  # E4 可移植性：中文 Windows 控制台 GBK 会让 print 崩成退出码 1（恰是判负码）
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCHEMA = "self-conf.intent/v1"
PRODUCTS = ("routing", "lazy")
KERNELS = ("surge", "egern", "clash")

# 自托管规则集：Surge/Egern 用 raw URL，mihomo 用 provider 名 —— 名字对不上。
# 这张表把同一份「本仓规则集」在三内核里的 source 归一到同一个 key，供跨内核弱关联。
# 值必须等于该集在 mihomo 侧经通用归一后的形态（小写 + 去扩展 + 下划线转连字符）。
_SELF_HOSTED = {
    "rules/ai.list": "ai-domains",      # rules/AI.list（由 ai_sources 生成） <-> mihomo provider AI_Domains
    "rules/emby.list": "emby",
    "rules/apple_system.list": "apple-system",
}


def _strip_ext(name):
    for ext in (".list", ".txt", ".yaml", ".yml", ".mrs"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def norm_source(source, kernel):
    """把不同内核的规则集 source 归一成可弱关联的 key（小写、去扩展名、下划线转连字符、URL 取 basename）。"""
    if not source:
        return None
    s = str(source).strip().strip('"')
    if s.startswith("http"):
        low = s.lower()
        for path_key, norm in _SELF_HOSTED.items():
            if low.endswith(path_key):
                return norm
        base = s.rstrip("/").split("/")[-1]
    else:
        base = s
    return _strip_ext(base.lower()).replace("_", "-")


# ---------------------------------------------------------------- surge

def _is_key_value(tok):
    return "=" in tok and not tok.startswith("=")


def _parse_surge_group(line):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("["):
        return None
    if "=" not in line:
        return None
    name, _, rest = line.partition("=")
    parts = [p.strip() for p in rest.split(",")]
    gtype = parts[0] if parts else ""
    members = []
    for p in parts[1:]:
        if _is_key_value(p):
            break
        members.append(p)
    return {"name": name.strip(), "type": gtype, "members": members, "raw": line}


def _load_surge_groups(path):
    groups, section = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            continue
        if section != "[Proxy Group]":
            continue
        g = _parse_surge_group(raw)
        if g:
            groups.append(g)
    return groups


def _load_surge_rules(path):
    rules, section = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            continue
        if section != "[Rule]" or not s or s.startswith("#"):
            continue
        fields = [f.strip().strip('"') for f in s.split(",")]
        kind = fields[0]
        if kind == "FINAL":
            target, source = fields[1], None
            options = fields[2:]
        else:
            source, target = fields[1], fields[2]
            options = fields[3:]
        rules.append({"kind": kind, "source": source, "target": target,
                      "source_norm": norm_source(source, "surge"), "options": options})
    return rules


# ---------------------------------------------------------------- clash

def _load_clash_groups(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups = []
    for g in data.get("proxy-groups") or []:
        groups.append({"name": g.get("name"), "type": g.get("type"),
                       "members": list(g.get("proxies") or []), "raw": None})
    return groups


def _load_clash_rules(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = []
    for item in data.get("rules") or []:
        fields = [f.strip() for f in str(item).split(",")]
        kind = fields[0]
        if kind == "MATCH":
            target, source = fields[1], None
            options = fields[2:]
        else:
            source, target = fields[1], fields[2]
            options = fields[3:]
        rules.append({"kind": kind, "source": source, "target": target,
                      "source_norm": norm_source(source, "clash"), "options": options})
    return rules


# ---------------------------------------------------------------- egern

def _load_egern_groups(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups = []
    for item in data.get("policy_groups") or []:
        if not isinstance(item, dict) or len(item) != 1:
            continue
        gtype, body = next(iter(item.items()))
        if not isinstance(body, dict):
            continue
        groups.append({"name": body.get("name"), "type": gtype,
                       "members": list(body.get("policies") or []), "raw": None})
    return groups


def _load_egern_rules(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = []
    for item in data.get("rules") or []:
        if not isinstance(item, dict) or len(item) != 1:
            continue
        kind, body = next(iter(item.items()))
        if not isinstance(body, dict):
            body = {}
        source = body.get("match") if kind in ("rule_set", "geoip") else None
        target = body.get("policy") or body.get("value")
        options = [k for k in ("no_resolve", "disabled") if body.get(k)]
        rules.append({"kind": kind, "source": source, "target": target,
                      "source_norm": norm_source(source, "egern"), "options": options})
    return rules


def _kernel_paths(root, product):
    return {
        "surge": root / "surge" / "profiles" / ("%s.conf" % product),
        "egern": root / "egern" / "profiles" / ("%s.yaml" % product),
        "clash": root / "clash" / "profiles" / ("%s.yaml" % product),
    }


def _cross(rules_by_kernel):
    sources = {}
    for kernel, rules in rules_by_kernel.items():
        for r in rules:
            key = r.get("source_norm")
            if not key or r["kind"] in ("FINAL", "MATCH"):
                continue
            sources.setdefault(key, {})[kernel] = r["target"]
    notes = []
    for key, per in sources.items():
        present = sorted(per.keys())
        if len(present) < len(KERNELS):
            notes.append({"source": key, "present_in": present, "kind": "partial",
                          "detail": "仅出现在 %s —— 多为内核机制差异（如 mihomo 拆分/内置），AGENTS.md 明示刻意不对齐" % present})
        if len(set(per.values())) > 1:
            notes.append({"source": key, "targets": dict(per), "kind": "target_mismatch",
                          "detail": "同一规则集在不同内核挂到不同策略组 —— 多为刻意，改前先读 rulesets.md"})
    return {"sources": sources, "notes": notes}


def build(root):
    out = {"schema": SCHEMA, "generated_by": "self-conf-skills/run/build_ir.py",
           "products": {}}
    for product in PRODUCTS:
        paths = _kernel_paths(root, product)
        # ⚠️ 必须 as_posix()，不能 str()：str(Path) 用**平台分隔符** —— Windows 得
        # `clash\profiles\x.yaml`、Linux 得 `clash/profiles/x.yaml`。而本闸门的判据是
        # 「重算结果与落盘 intent.json **逐字相等**」⇒ 在 Windows 生成、Linux 校验时
        # 必然不等 ⇒ CI 假红「intent.json 已过期」（本仓真实踩过：两次 push 连续判负）。
        # 统一成正斜杠后，两侧任何平台算出的 IR 都相同。
        entry = {"paths": {k: v.relative_to(root).as_posix() for k, v in paths.items()},
                 "kernels": {}, "cross": {}}
        rules_by_kernel = {}
        for kernel in KERNELS:
            p = paths[kernel]
            if not p.exists():
                entry["kernels"][kernel] = {"error": "缺失 %s" % p.name}
                continue
            if kernel == "surge":
                groups, rules = _load_surge_groups(p), _load_surge_rules(p)
            elif kernel == "clash":
                groups, rules = _load_clash_groups(p), _load_clash_rules(p)
            else:
                groups, rules = _load_egern_groups(p), _load_egern_rules(p)
            entry["kernels"][kernel] = {
                "groups": [{"name": g["name"], "type": g["type"], "members": g["members"]} for g in groups],
                "rules": rules,
            }
            rules_by_kernel[kernel] = rules
        entry["cross"] = _cross(rules_by_kernel)
        out["products"][product] = entry
    return out


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1)


def main(argv):
    root = Path(__file__).resolve().parents[2]
    # __file__ = <root>/self-conf-skills/run/build_ir.py -> parents[0]=run, [1]=self-conf-skills, [2]=<root>
    target = root / "self-conf-skills" / "references" / "intent.json"
    try:
        ir = build(root)
    except Exception as e:
        sys.stderr.write("IR 解析失败：%s\n" % e)
        return 2
    text = _canonical(ir)
    if "--check" in argv:
        if not target.exists():
            sys.stderr.write("intent.json 缺失（先跑 build_ir.py 生成）\n")
            return 1
        current = _canonical(json.loads(target.read_text(encoding="utf-8")))
        if current != text:
            sys.stderr.write("intent.json 已过期 —— 配置改了但没重跑 build_ir.py\n")
            return 1
        print("intent.json ✓ 最新")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    # 用 LF 写（.gitattributes 钉 eol=lf；Windows 默认 CRLF 会被 portability 判据 E2 打回）
    with target.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text + "\n")
    print("已写入 %s" % target.relative_to(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
