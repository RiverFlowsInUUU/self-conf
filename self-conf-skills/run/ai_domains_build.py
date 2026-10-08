# -*- coding: utf-8 -*-
"""AI_Domains 整合生成器：多源 AI 规则集合并 → rules/AI.list（Surge ruleset 格式）

用法（仓库根目录）:
    python self-conf-skills/run/ai_domains_build.py
可选参数:
    --src-dir  源规则集目录（默认: self-conf-skills/run/ai_sources/，内含 10 份上游抓取快照）
    --out      输出路径（默认: rules/AI.list）

上游来源与维护状态见生成文件的头部档案。纪律: 零 IP 条目（防 DNS 泄露面）；
googleapis.com 宽后缀已收窄（YouTube 误伤实测）；-pa 动态命名空间用 DOMAIN-KEYWORD 一条封死；
冗余归并: DOMAIN 被「同值或父域」DOMAIN-SUFFIX 覆盖者一律删（后缀匹配集严格更宽，删之不改落点）；
KEYWORD 与 SUFFIX 同值时删 KEYWORD。
"""
import re, os, sys, argparse
from collections import defaultdict

# 共用模块定位：先 self-conf-skills/lib/，再本目录（重组后 _*_common 统一在 lib/）
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _cand in (_os.path.join(_d, '..', '..', 'lib'),
              _os.path.join(_d, '..', 'lib'), _d):
    _cand = _os.path.normpath(_cand)
    if _os.path.isfile(_os.path.join(_cand, '_surge_common.py')) or \
       _os.path.isfile(_os.path.join(_cand, '_egern_common.py')) or \
       _os.path.isfile(_os.path.join(_cand, '_clash_common.py')):
        _sys.path.insert(0, _cand)
        break


# Windows 中文环境的控制台与管道默认 GBK(cp936)：本脚本输出大量中文状态，与 UTF-8 终端
# （现代终端 / Git Bash，即本仓主流环境）不匹配时会显示成乱码。统一钉成 UTF-8，
# 与仓内其余输出型脚本（tests/ 的 4 行模板、scripts 下的 _egern_common/_surge_common）同口径。
# ⚠️ 取舍：传统 cp936 cmd 下中文会反过来显示成乱码 —— 与全仓「统一 UTF-8」的选择一致。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# (文件名, 来源标签)
SOURCES = [
    ('repcz-ai.list',   'Repcz/Tool (Surge)'),
    ('my-ai.list',      'ddgksf2013.top 订阅快照 (墨鱼 · Clash payload)'),
    ('acl4ssr-ai.list', 'ACL4SSR (Clash classical)'),
    ('bm7-OpenAI.list',     'blackmatrix7 OpenAI'),
    ('bm7-Gemini.list',     'blackmatrix7 Gemini'),
    ('bm7-Claude.list',     'blackmatrix7 Claude'),
    ('bm7-Copilot.list',    'blackmatrix7 Copilot'),
    ('bm7-BardAI.list',     'blackmatrix7 BardAI'),
    ('meta-ai.list',    'MetaCubeX geosite category-ai-!cn'),
    ('dler-ai.list',    'dler-io/Rules AI Suite (Surge)'),
]
# 用户拍板：googleusercontent.com 宽后缀保留（静态 CDN，无账号判定语义）；
# googleapis.com 宽后缀 2026-09-28 二次修正改窄 —— 它是全 Google API 域（youtubei.googleapis.com
# 是 YouTube App 的核心 API），整域收编会误拉 YouTube/GMS 其他服务进 AI 组（用户实测 IP 乱跳）。
WIDE_REQUIRED = ['googleusercontent.com']
# 精确补入：GMS 主网关 + 账号 OAuth 基础设施（oauth2 令牌端点为全 Google 共享·低频，随 Gemini 走 AI 出口）
EXTRA_EXACT = [('DOMAIN', 'play.googleapis.com'),
               ('DOMAIN', 'oauthaccountmanager.googleapis.com'),
               ('DOMAIN', 'oauth2.googleapis.com')]
# 关键词兜底：-pa.googleapis.com 是 Google 助手后端的动态命名空间
# （signaler/growth/notifications/robinfrontend/geller/cloudcode/aisandbox… 永远会冒新的），
# 一条 KEYWORD 兜住现有与未来的全部 xxx-pa 后端；子串高度特异，youtubei 等非 -pa 域不受影响
EXTRA_KEYWORD = [('-pa.googleapis.com')]
# 人工过审剔除：过宽云/CDN/支付后缀（误伤面巨大）+ Envato 素材市场误收 + googleapis.com 宽后缀
BLACKLIST = {'amazonaws.com', 'cloudflare.com', 'wp.com', 'imgix.net', 'sentry.io', 'stripe.com',
             'envato.com', 'envato-static.com', 'envatousercontent.com', 'themeforest.net',
             'googleapis.com'}
# 点名剔除的**特定主机**（与上面的"宽后缀名"不同：这里父域本身没问题，仅该主机不该进 AI 组）。
# 判据是**逐个主机**而非整域 —— 故上面的 BLACKLIST 不要改成"后缀匹配"：那样会误杀
# challenges.cloudflare.com（AI 服务人机验证，上游已收且该收）/ openaicom.imgix.net（OpenAI 专属）等
# 父域在黑名单、子域却该收的条目。
# ① 通用基础设施的个别主机：支付(stripe) / 遥测(sentry) / 对象存储(s3) / 图片 CDN(imgix) / 邮件投递(sendgrid)
# ② 撞本仓 GitHub / 微软分流规则的共享域 —— AI 组排在其前，收了会静默改写这些域的出口
#    （GitHub 规则 2026-10-05 起直指 `Proxy`、不再单设组；黑名单仍保留，因为 AI 组排在它之前）
BLACKLIST_EXACT = {
    'js.stripe.com', 'o207216.ingest.sentry.io', 'workos.imgix.net', 'ct.sendgrid.net',
    'anysphere-binaries.s3.us-east-1.amazonaws.com',
    'login.live.com', 'login.microsoftonline.com',
    'copilot-reports.github.com', 'origin-tracker.githubusercontent.com',
}

OK_TYPES = {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'URL-REGEX'}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_sources'))
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_path = a.out or os.path.join(repo_root, 'rules', 'AI.list')

    dropped = defaultdict(list)   # 源 -> [(type, value, 原因)]
    rules = {}                    # (type, value) -> set(来源)

    def add(t, v, src):
        t, v = t.strip().upper(), v.strip().rstrip('.')
        if t not in OK_TYPES:
            dropped[src].append((t, v, '类型不支持')); return
        if not v or ' ' in v:
            dropped[src].append((t, v, '空值/含空格')); return
        if v.endswith('.cn') or v == 'cn':          # 防国内域混入
            dropped[src].append((t, v, '国内域剔除')); return
        if v in BLACKLIST:                          # 过宽云/CDN/支付后缀人工剔除
            dropped[src].append((t, v, '过宽后缀人工剔除')); return
        if v in BLACKLIST_EXACT:                    # 点名剔除的特定主机（见其定义处）
            dropped[src].append((t, v, '特定主机点名剔除')); return
        rules.setdefault((t, v), set()).add(src)

    for fname, src in SOURCES:
        path = os.path.join(a.src_dir, fname)
        if not os.path.exists(path):
            print(f'[跳过] 源缺失: {fname}')
            continue
        for raw in open(path, encoding='utf-8', errors='replace'):
            line = raw.strip()
            if not line or line.startswith(('#', '//', ';')):
                continue
            if line == 'payload:':
                continue
            line = re.sub(r'^-\s*', '', line).strip()   # payload/geosite 列表前缀
            if not line: continue
            if line.startswith('+.'):                   # geosite 展开的 suffix 标记
                add('DOMAIN-SUFFIX', line[2:], src); continue
            if line.startswith('full:'):  add('DOMAIN', line[5:], src); continue
            if line.startswith('domain:'): add('DOMAIN-SUFFIX', line[7:], src); continue
            if line.startswith('keyword:'): add('DOMAIN-KEYWORD', line[8:], src); continue
            if line.startswith('regexp:'):
                dropped[src].append((line, '', 'geosite regexp 无 Surge 对应')); continue
            if '@' in line and ' ' in line:             # geosite 属性行
                line = line.split('@')[0].strip()
                if not line: continue
            parts = line.split(',')
            if len(parts) == 1:                         # geosite 裸域名 → SUFFIX
                add('DOMAIN-SUFFIX', parts[0], src); continue
            t = parts[0].strip().upper()
            if t in ('IP-CIDR', 'IP-CIDR6', 'IP-ASN'):  # 零 IP 纪律
                dropped[src].append((t, parts[1] if len(parts) > 1 else '', 'IP 条目丢弃(AI 集零 IP 纪律)')); continue
            if len(parts) >= 2:
                add(t, parts[1], src)                   # 只取 type+value，多余参数(策略等)不进集
            else:
                dropped[src].append((line, '', '无法解析'))

    # 用户拍板宽后缀强制收录
    for w in WIDE_REQUIRED:
        if ('DOMAIN-SUFFIX', w) not in rules:
            rules[('DOMAIN-SUFFIX', w)] = {'用户拍板收录'}
            print('[补入宽后缀]', w)
    # 用户拍板精确补入（GMS 主网关 + 账号 OAuth 基础设施）
    for t, v in EXTRA_EXACT:
        if (t, v) not in rules:
            rules[(t, v)] = {'用户拍板精确补入'}
            print('[补入精确]', t, v)
    # 用户拍板关键词兜底（-pa 动态命名空间一条封死）
    for kw in EXTRA_KEYWORD:
        if ('DOMAIN-KEYWORD', kw) not in rules:
            rules[('DOMAIN-KEYWORD', kw)] = {'用户拍板关键词兜底'}
            print('[补入关键词]', kw)

    # 归并：KEYWORD 与 SUFFIX 同值 → 删 KEYWORD（后缀更精确宽）
    for (t, v) in list(rules):
        if t == 'DOMAIN-KEYWORD' and ('DOMAIN-SUFFIX', v) in rules:
            del rules[('DOMAIN-KEYWORD', v)]
            print('[归并] KEYWORD→SUFFIX 覆盖:', v)

    # 归并：DOMAIN 被「同值或父域」DOMAIN-SUFFIX 覆盖 → 删 DOMAIN
    # SUFFIX,x 的匹配集 = {x} ∪ {*.x}，严格包含 DOMAIN,x 的 {x}，也包含 DOMAIN,y.x 的 {y.x}
    # ⇒ 上述两种情形删之均不改变任何请求落点，纯去冗余，非行为变更。
    # 注：只收「同值 / 域名层级父子」两类覆盖。KEYWORD 的子串式巧合覆盖（如 cdn.openaimerge.com
    # 被 KEYWORD,openai 兜住）语义不同且随该 KEYWORD 存废而失效，属另一类，不在此处归并。
    suffixes = {v for (t, v) in rules if t == 'DOMAIN-SUFFIX'}
    for (t, v) in list(rules):
        if t == 'DOMAIN' and (v in suffixes or any(v.endswith('.' + s) for s in suffixes)):
            del rules[('DOMAIN', v)]
            print('[归并] DOMAIN→SUFFIX 覆盖:', v)

    # 排序：按服务商分组
    def bucket(t, v):
        lv = v.lower()
        if t == 'DOMAIN-SUFFIX' and lv in ('googleusercontent.com',): return '00 宽后缀(伴生域收编)'
        if 'google' in lv or 'gstatic' in lv or 'ggpht' in lv or lv.endswith('.goog') or lv == 'goog' or 'deepmind' in lv or lv in ('android.com','chrome.com'): return '01 Google/Gemini 系'
        if 'openai' in lv or 'chatgpt' in lv or 'oai' in lv or lv in ('ai.com','chat.com','sora.com'): return '02 OpenAI/ChatGPT 系'
        if 'claude' in lv or 'anthropic' in lv: return '03 Claude/Anthropic 系'
        if 'grok' in lv or lv == 'x.ai' or 'xai' in lv: return '04 Grok/xAI 系'
        if 'copilot' in lv or 'microsoft' in lv or 'bing' in lv or 'github' in lv or 'jetbrains' in lv or 'azureedge' in lv or 'githubnext' in lv or 'msn.com' in lv or 'appcenter' in lv or 'officeapps' in lv or 'blob.core.windows' in lv: return '05 Copilot/微软系'
        if 'meta.ai' in lv: return '06 Meta 系'
        if any(k in lv for k in ('perplexity','pplx-','poe.com','openrouter','groq','mistral','huggingface','together','deepseek','clipdrop','openart','jasper','dify.ai','cursor','notebooklm','anythingllm','arena.ai','cerebras','chutes.ai','cici','clawhub','codeium','coderabbit','clau.de','usefathom','chatbox')): return '07 其他 AI 服务'
        if any(k in lv for k in ('statsig','datadoghq','auth0','arkoselabs','intercom','launchdarkly','featuregates','identrust','segment.io','cloudflareinsights','challenges.cloudflare','gateway.ai.cloudflare')): return '08 基础设施/认证/遥测(伴生)'
        return '09 其他未归类'

    groups = defaultdict(list)
    for (t, v), srcs in rules.items():
        groups[bucket(t, v)].append((t, v, srcs))

    total = sum(len(v) for v in groups.values())
    out_lines = [
        '# NAME: AI_Domains (AI 全量整合集 · Surge ruleset)',
        '# 生成: 2026-10-01（dler-io 源 + 归并器补全：同值 + 父域）· 本仓自托管静态整合快照',
        '# 生成脚本: self-conf-skills/run/ai_domains_build.py（源目录: self-conf-skills/run/ai_sources/）',
        f'# 合计: {total} 条规则 —— 本行为条数唯一真源（自动统计，勿手抄到别处）',
        '#',
        '# ============ 上游来源详细信息 ============',
        '#',
        '# 1. Repcz/Tool (Surge) —— 主参考集，滚动维护',
        '#    https://github.com/Repcz/Tool  (X 分支 · Surge/Rules/AI.list)',
        '#    2026-09-28 仍在提交。贡献：Gemini 专属后端(-pa 系精确枚举) + 主流 AI 域。',
        '#    另以独立订阅在本仓四 profile 中并排引用(滚动承接新 AI 域)。',
        '#',
        '# 2. ddgksf2013.top (墨鱼) —— 滚动更新，本集伴生域基线',
        '#    https://ddgksf2013.top/filter/Ai.yaml  (Ai.yaml, Clash payload 形态)',
        '#    旧 gist 地址已停更并于 2026-09-30 迁至该域名（旧地址最后实质提交 2025-11-26）。',
        '#    贡献：ChatGPT / Meta AI 网页伴生的第三方基础设施域',
        '#    (auth0/statsig/datadoghq/arkoselabs/intercom/launchdarkly 等认证/遥测/风控域)。',
        '#',
        '# 3. ACL4SSR/ACL4SSR —— AI.list 长期停更，本仓已弃用其作 AI 源',
        '#    https://github.com/ACL4SSR/ACL4SSR  (曾钉 commit 75f01010)',
        '#    贡献：早期基线(main 与锁版同内容，无增量)。',
        '#',
        '# 4. blackmatrix7/ios_rule_script —— 每日更新，本集取 5 个分集',
        '#    https://github.com/blackmatrix7/ios_rule_script  (master · rule/Surge/{OpenAI,Gemini,Claude,Copilot,BardAI})',
        '#    贡献：各家专属域名细分(其 IP 条目已按零 IP 纪律丢弃)。分流版另有其 4 条专属集独立在役。',
        '#',
        '# 5. MetaCubeX/meta-rules-dat —— 每日构建，本集最大覆盖源',
        '#    https://github.com/MetaCubeX/meta-rules-dat  (meta 分支 · geo/geosite/category-ai-!cn.list)',
        '#    v2fly domain-list-community 的 category-ai-!cn 展开版。贡献：Gemini 后端全清单',
        '#    (antigravity/notebooklm/cloudcode/aicode 等) + 新兴 AI 服务全家(cohere/deepseek 等)。',
        '#    youtubei 等 YouTube 域天然不在该分类(已实测验证)。',
        '#',
        '# 6. 用户自有镜像 (RiverFlowsInUUU/Rule) —— 与第 2 条同源的快照 + notebooklm 补遗',
        '#    https://github.com/RiverFlowsInUUU/Rule  (main · AI, Clash payload 形态)',
        '#',
        '# 7. dler-io/Rules —— 滚动维护，高质量补漏源',
        '#    https://github.com/dler-io/Rules  (main · Surge 3/Provider/AI Suite.list)',
        '#    贡献：Google 新 AI 产品(Opal/Jules/antigravity/notebooklm.cloud) + AI 编程工具',
        '#    (zed/augment/chorus/udify) + JetBrains/Apple Intelligence + Grok 登录域。',
        '#    ⚠️ 该集设计前提是「置于微软/Apple/通用代理规则之前」，故意收录共享登录/token 域',
        '#    (js.stripe.com / login.live.com 等)以保证账号风控一致 —— 与本仓取舍不同，故用',
        '#    BLACKLIST_EXACT 点名剔除其中会撞本仓 GitHub/微软分流规则、或属通用基础设施的 9 个主机。',
        '#',
        '# ============ 整合纪律 ============',
        '# · 零 IP 条目：所有 IP-CIDR/IP-ASN 一律丢弃(纯域名集不触发解析，无 DNS 泄露面)',
        '# · googleapis.com 宽后缀已收窄：它是全 Google API 域(含 youtubei=YouTube 信令)，',
        '#   整域收编会误拉 YouTube/GMS 其他服务；改为 Gemini 专属后端精确枚举 + play 网关 1 条',
        '# · 域名形态：DOMAIN / DOMAIN-SUFFIX / DOMAIN-KEYWORD / URL-REGEX（零 IP）',
        '# · 冗余归并：DOMAIN 被「同值或父域」DOMAIN-SUFFIX 覆盖者删之（后缀的匹配集严格包含 DOMAIN，',
        '#   删之不改任何落点，纯去冗余）；KEYWORD 与 SUFFIX 同值时删 KEYWORD。三项均由生成器自动执行，',
        '#   新源带来的同类冗余一并消解',
        '#',
        '# ============ 分工与拍板记录 ============',
        '# 分工: 本集管「Gemini 专属后端 + 伴生域 + 基础设施域」(静态)；新 AI 域由 Repcz AI.list(滚动)承接，两者同指 AI 组',
        '# 拍板: googleapis.com 宽后缀改窄(YouTube 误伤实测)；play.googleapis.com 精确收编(GMS 主网关随 Gemini)；',
        '#       googleusercontent.com 宽后缀保留(静态 CDN 无账号语义)；AI 组 select 钉死出口(风控一致性)',
        '# 三修: 2026-09-28 实测漏网收编 —— oauth2 / oauthaccountmanager(账号 OAuth 基础设施·低频) 精确补入；',
        '#       DOMAIN-KEYWORD,-pa.googleapis.com 一条封死 -pa 动态命名空间(signaler/growth/notifications 等未来新后端全兜)',
        '# 四修: 2026-09-30 墨鱼源换址(gist → ddgksf2013.top)刷新快照，净增 11 条(Cursor/Meta AI/HuggingFace 系)；',
        '#       facebook.com / fbcdn.net / connect.facebook.net 三条宽域按用户拍板原样收录(Meta AI 账号与 CDN 依赖)',
        '# 五修: 2026-10-01 新增第 10 源 dler-io/Rules(AI Suite)；其独有 33 条中 9 条由 BLACKLIST_EXACT 点名剔除，',
        '#       净增 24 条(Google 新 AI / AI 编程工具 / JetBrains / Apple Intelligence / Grok 登录)',
        '# 六修: 2026-10-01 归并器补 DOMAIN 同类项 —— 此前仅做 KEYWORD→SUFFIX 归并，故 DOMAIN,x 与同值',
        '#       DOMAIN-SUFFIX,x 并存(共 32 处，其中 26 处旧集即有、6 处由 dler 源带入)。补归并后列表',
        '#       318 → 286 条；匹配行为零变化(SUFFIX 覆盖 DOMAIN)，属生成器级修复，往后同类冗余自动消解',
        '# 七修: 2026-10-01 归并扩到「父域覆盖」—— 原只认同值，故 y.x 型 DOMAIN 与父域 DOMAIN-SUFFIX,x',
        '#       并存(14 处，如 waa-pa.clients6.google.com <- clients6.google.com)。补后列表 286 → 272 条；',
        '#       匹配行为仍零变化(SUFFIX,x 本就含全部 *.x)。KEYWORD 的子串式巧合覆盖(1 处 cdn.openaimerge.com',
        '#       被 KEYWORD,openai 兜住)语义不同，本次不动',
        '#',
    ]
    for b in sorted(groups):
        out_lines.append(f'# ==== {b} ====')
        for t, v, srcs in sorted(groups[b], key=lambda x: (x[0], x[1])):
            out_lines.append(f'{t},{v}')
        out_lines.append('')
    open(out_path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out_lines) + '\n')
    print(f'\n输出 {out_path}: {total} 条规则')
    if dropped:
        print('\n=== 丢弃明细 ===')
        for src, items in dropped.items():
            for t, v, why in items:
                print(f'  [{src}] {t},{v} <- {why}')

if __name__ == '__main__':
    main()
