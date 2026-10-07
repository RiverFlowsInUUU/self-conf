import io,sys,yaml
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
p='skill/tests/clash/check_header_numbers.py'
s=open(p,encoding='utf-8').read()

# 1) 增加"静态真值"：静态 profile 含脚本没有的 Smart 三档子组，
#    故组数以静态文件自身为准（这是已知差异，不是过期）
old = '''def real_sizes(script_path):'''
new = '''def static_sizes(path):
    """静态 profile 的真实规模。

    ⚠️ 静态版比脚本输出多 3 个组（Low Mult. / Auto / High Mult.，
    是 Smart 的三档子组，模板专属）。这是**已知差异**不是过期，
    故静态文件用自身实际值做真值，不用脚本输出的组数。
    """
    try:
        c = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception:
        return None
    return {
        "groups": len(c.get("proxy-groups") or []),
        "providers": len(c.get("rule-providers") or {}),
        "rules": len(c.get("rules") or []),
    }


def real_sizes(script_path):'''
assert s.count(old)==1
s=s.replace(old,new)
s=s.replace('import os\nimport re\nimport sys','import os\nimport re\nimport sys\n\ntry:\n    import yaml\nexcept ImportError:\n    yaml = None')

# 2) 按行判断产品线（README 里 lazy 与 routing 两行并存，按文件名判断会误判）
old2 = '''        # 判断这份文件属于哪条产品线（决定用哪套真值）
        is_lazy = "lazy" in rel
        key = "my_clash_lazy.js" if is_lazy else "my_clash.js"
        truth = real.get(key)
        if not truth:
            continue

        for i, line in enumerate(txt.split("\n"), 1):'''
new2 = '''        # 静态 profile 用自身实际值做真值（含 Smart 三档，与脚本输出不同）
        if rel.startswith("profiles/"):
            truth = static_sizes(p)
            if not truth:
                continue
            default_key = "my_clash_lazy.js" if "lazy" in rel else "my_clash.js"
            for i, line in enumerate(txt.split("\n"), 1):'''
assert s.count(old2)==1, '块1未匹配'
s=s.replace(old2,new2)

# 上面替换后结构乱了，改为重写扫描循环
i0=s.find('        # 静态 profile 用自身实际值做真值')
i1=s.find('    if bad:')
new_block = '''        # 真值选择：
        #   · profiles/* → 用静态文件自身实际值（含 Smart 三档，已知差异）
        #   · override/* → 用脚本输出真值；且**按行**判断说的是哪个脚本
        #     （README 里 lazy 与 routing 两行并存，按文件名判断会误判）
        static_truth = None
        if rel.startswith("profiles/"):
            static_truth = static_sizes(p)
            if not static_truth:
                continue

        for i, line in enumerate(txt.split("\n"), 1):
            stripped = line.strip()
            if not (stripped.startswith(("#", "//", ";", "|")) or stripped.startswith("*")):
                continue
            # 按行判断产品线
            is_lazy = "lazy" in line.lower()
            key = "my_clash_lazy.js" if is_lazy else "my_clash.js"
            if static_truth is not None:
                truth = static_truth
            else:
                truth = real.get(key)
                if not truth:
                    continue
            for pat, kind in CONTEXT:
                for m in re.finditer(pat, line):
                    n = int(m.group(1))
                    want = truth[kind]
                    if n != want:
                        bad.append((rel, i, kind, n, want, stripped[:70]))

'''
s = s[:i0] + new_block + s[i1:]
open(p,'w',encoding='utf-8',newline='\n').write(s)
print('判据已修')
