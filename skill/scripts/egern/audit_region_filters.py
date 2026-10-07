#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计地区组 filter 的「两份拷贝」是否同步 —— 守住 Other Regions 的负向断言。

为什么必须有这个脚本
--------------------
模板里 5 个地区组（Hong Kong / Taiwan / Japan / Singapore / United States）各自写自己的
`filter` 正则，而 `Other Regions` 用一条**负向断言**（`^ (?! .* (?: 关键词 ) ) .+ $`）
把它们的全部关键词**又抄了一遍**。这是负向断言的固有要求（"排除以上全部"必须逐字列出），
Egern 也不支持 `filter` 引用别的 filter，所以**无法靠 YAML 变量消除这份拷贝**。

但拷贝的代价是真实的：**任何地区组新增/修改关键词而忘了同步 Other Regions**，
该关键词就不再被负向断言排除 ⇒ 属于那个地区的节点会**同时**出现在
它自己的地区组和 `Other Regions` 里，两个组不再互斥。

本项目在 `_egern_common.py` 里刚写过结论：**靠注释提醒同步两份拷贝是不可靠的**
（那次是 `hostpart()` 的回归，同一份配置两个脚本给出相反结论）。
所以这里用脚本守，而不是再写一句"记得同步"。

判据（为什么是「逐字包含」而不是「按 | 拆开比对」）
--------------------------------------------------
早期版本按 `|` 拆分两边再比集合 —— 这是错的：地区 filter 里存在**分组内的选择分支**，
例如香港的 `(?:深|沪|京|广)港` 会被拆成 `(?:深` / `沪` / `京` / `广)港` 四片。
两边拆法一致时结论"碰巧"仍对，但拆分本身已经破坏了语义，稍有格式差异就会误报。

现在改为：把**地区组 filter 去掉 `(?i)` 后的整串**，拿去负向断言里做**子串包含**判断。
负向断言是多行缩进写的，先去掉全部实际空白再比（注意 `\\s` 这类**正则转义**不受影响，
因为它们是反斜杠 + 字母，不是真空白）。

怎么识别"地区组"
----------------
`filter` 里含中文或国旗 emoji 的，才算地区组（`CJK_OR_FLAG`）。
这样能自动跳过"有 filter 但与地区无关"的组 —— 例如 v4.0.1 及更早的 `MAX` 组
（数值过滤器 `(?<![\\d.])0\\.\\d*[1-9]`）。
⚠️ v4.0.2 起"低倍率优先"改写进 `priorities` 字段（不再是 `filter`），本判据不会误收它；
这条跳过规则作为防御保留，遇到新的非地区 filter 时仍会把它排除在比对之外。
**跳过的组会全部打印出来**，不静默 —— 万一某个地区组写成纯 ASCII（如 `(?i)HK|TW`），
你会看到它出现在"跳过"列表里而不是被悄悄忽略。

用法
----
    python audit_region_filters.py profile.yaml
    python audit_region_filters.py profile.yaml --verbose     # 打印逐组比对串

退出码：0 = 全部同步；1 = 有地区关键词没被负向断言覆盖；2 = 用法/解析错误。
"""
import argparse
import io
import os
import re
import sys
# 输出编码垫片：见 _egern_common.force_utf8_stdout —— GBK 控制台下 emoji 会崩成退出码 1
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _egern_common import force_utf8_stdout  # noqa: E402

try:
    import yaml
except ImportError:
    print("需要 PyYAML：<venv>/Scripts/python -m pip install pyyaml", file=sys.stderr)
    sys.exit(2)

# 负向断言的识别标志：filter 里出现 `(?!`
NEG_MARKER = "(?!"

# 内联 flag 前缀，如 `(?i)` / `(?xi)`
FLAG_RE = re.compile(r"^\(\?[a-z]+\)")

# 负向断言的包裹结构：`(?xi) ^ (?! .* (?: … ) ) .+ $`
NEG_BODY_RE = re.compile(r"\(\?:([\s\S]*)\)\s*\)\s*\.\+\s*\$$")

# 地区组的识别：含中文或国旗 emoji（数值过滤器两者都没有 ⇒ 一并跳过）
CJK_OR_FLAG = re.compile(r"[\u4e00-\u9fff]|[\U0001F1E6-\U0001F1FF]")


def norm(text):
    """去掉全部**实际空白**（换行 / 缩进 / 空格），便于逐字比对。

    只删真空白字符 —— `\\s`（反斜杠 + s）是正则转义，不受影响。
    """
    return re.sub(r"\s+", "", text)


def strip_flag(text):
    """剥掉开头的内联 flag，如 `(?i)` / `(?xi)`。"""
    return FLAG_RE.sub("", text.strip()).strip()


def region_groups(groups):
    """挑出「正向地区组」与「被跳过的数值过滤器」。"""
    out, skipped = [], []
    for name, body in groups.items():
        f = body.get("filter")
        if not f:
            continue
        if NEG_MARKER in f:
            continue  # 负向断言组，单独处理
        if not CJK_OR_FLAG.search(f):
            skipped.append((name, f))
            continue
        out.append((name, f))
    return out, skipped


def negative_group(groups):
    for name, body in groups.items():
        f = body.get("filter")
        if f and NEG_MARKER in f:
            return name, f
    return None, None


def main():
    ap = argparse.ArgumentParser(description="校验地区组关键词与 Other Regions 负向断言是否同步")
    ap.add_argument("profile", help="profile YAML 路径")
    ap.add_argument("--verbose", action="store_true", help="打印逐组比对串")
    args = ap.parse_args()

    try:
        doc = yaml.safe_load(io.open(args.profile, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"❌ 无法解析 {args.profile}：{e}", file=sys.stderr)
        return 2

    groups = {}
    for item in doc.get("policy_groups") or []:
        (_, body), = item.items()
        groups[body["name"]] = body

    pos, skipped = region_groups(groups)
    if not pos:
        print("✅ 本 profile 没有「正向地区组 + 负向断言」结构，无需校验。")
        return 0

    neg_name, neg_filter = negative_group(groups)
    if not neg_name:
        print(f"❌ 发现 {len(pos)} 个正向地区组，但找不到带负向断言（`(?!`）的组。")
        print("   若这是有意设计（例如删掉了 Other Regions），请忽略；否则说明结构变了。")
        return 2

    m = NEG_BODY_RE.search(neg_filter)
    if not m:
        print(f"❌ 无法解析 {neg_name} 的负向断言结构（期望 `(?xi) ^ (?! .* (?: … ) ) .+ $`）。")
        print("   本脚本宁可报错也不静默通过 —— 解析失败意味着校验没做。")
        return 2

    neg_norm = norm(m.group(1))

    print("=" * 78)
    print(f"地区组关键词 → 负向断言（{neg_name}）同步校验")
    print(f"profile: {args.profile}")
    print("=" * 78)

    missing_total = []
    for name, f in pos:
        body = norm(strip_flag(f))
        ok = body in neg_norm
        if not ok:
            missing_total.append(name)
        print(f"  {'✅' if ok else '❌'} {name:<14} {'整串已在负向断言里' if ok else '整串未出现在负向断言里'}")
        if args.verbose:
            print(f"        比对串：{body}")

    if skipped:
        print()
        print(f"  ⏭  跳过 {len(skipped)} 个非地区 filter（不含中文 / 国旗，按设计不校验）：")
        for name, f in skipped:
            print(f"        {name}: {f}")

    region_norm = norm("|".join(strip_flag(f) for _, f in pos))
    extra = sorted({p for p in neg_norm.split("|") if p and p not in region_norm})
    if extra:
        print()
        print(f"  ℹ️  {neg_name} 独有的排除词 {len(extra)} 个（用于排除订阅里的「信息行」，属预期）：")
        for a in extra:
            print(f"        {a}")

    print()
    print("=" * 78)
    if missing_total:
        print(f"❌ {len(missing_total)} 个地区组的关键词没被负向断言完整覆盖：{'、'.join(missing_total)}")
        print(f"   ⇒ 这些地区的节点会**同时**落进自己的地区组和 {neg_name}，两组不再互斥。")
        print(f"   修法：把该组 filter（去掉 `(?i)` 后）的整串补进 `{neg_name}` 的负向断言。")
        print("=" * 78)
        return 1
    print(f"✅ 全部同步：{len(pos)} 个地区组的关键词都已逐字出现在负向断言里。")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
