# -*- coding: utf-8 -*-
"""Release 发布器：一个更新日 = 一个 GitHub Release（tag = vYYYY-MM-DD）

时间线模型（2026-09-29 定稿，取代旧的"一个分工版本 = 一个 Release"）：
    Releases 列表按创建时间排序且 created_at 不可回写 —— 只有"一天一张"合并发版，
    列表时间线才可能与真实演进一致。两张产品线同日更新合并进同一张 Release，
    正文分「懒人版 / 分流版」小节逐版本列要点，资产 = 当日各产品线最终版本的
    固定名文件（三内核 × 两产品线 × 完整版/.min = 最多 12 件）。

用法（仓库根目录）:
    python skill/scripts/release_publish.py                     # 计划模式：只列清单与说明样例，一个字不发
    python skill/scripts/release_publish.py --apply             # 按计划发布全部缺失的 Release（需 --token 或环境变量 GITHUB_TOKEN）

规矩（详见 skill/reference/shared/ops.md §6.9，断言在 skill/tests/check_releases.py）:
    - tag = vYYYY-MM-DD（现役版取**版本号首现日** number_birth；归档版取快照 blob 诞生日）；
      资产文件名一律不带版本号（固定名）；
    - Release 标题 = emoji + 日期 + 当日主题（DAY_THEMES 表）；
    - 正文按产品线分小节：每版本一行 **vX.Y(.Z)** 头 + 公众向要点（PUBLIC_NOTES 表）；
    - **说明是面向公众的产品更新日志**（参考 Apple 更新说明的正式产品语言），
      禁止文言腔与内部过程语言；内核维度写全称「Surge」/「Egern」（允许并列作
      「Surge / Egern 内核」，共享「内核」后缀），但同一句内不得把「内核」写两遍、
      不得加「两者的」这类同义回指；
    - **关键实体必须点名**：写明具体分组 / 文件 / 功能名，不用模糊概括
      （「低倍率精选分组」这类写法曾把「哪个组并进哪个组」这条关键信息省掉）；
    - **忌赘述**：同一句不重复同一名词；一件事只写一条，不为凑条数拆条；
    - 单边内核日如实注明（如 Egern 内核当日无内容），不硬凑；
    - 发新版本前必须先补 DAY_THEMES 一行 + PUBLIC_NOTES 对应条目 —— 动线⑦的一部分。
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, urllib.request

# Windows 中文环境的控制台与管道默认 GBK(cp936)：emoji 一 print 就 UnicodeEncodeError、
# 进程以退出码 1 结束 —— 与"期望判负"的用例撞码会假绿。统一钉成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ⚠️ 2026-10-08 修正：默认仓库原为姊妹仓 Self-Configuration，
#    在 self-conf 里跑会把下载链接指向旧仓（发布出去的按钮全是死链）。
REPO = os.environ.get('GITHUB_REPO', 'RiverFlowsInUUU/self-conf')
API = f'https://api.github.com/repos/{REPO}'
UPLOAD = f'https://uploads.github.com/repos/{REPO}/releases'
FAMS = ('lazy', 'routing')
RAW = f'https://raw.githubusercontent.com/{REPO}/main'
DL = f'https://github.com/{REPO}/releases/download'
# 下载按钮 = shields.io 在线徽章（for-the-badge 风格）：颜色编码内核，文字编码分工
FAM_CN = {'lazy': '懒人版', 'routing': '分流版'}
# ⚠️ 2026-10-08 修正：本仓是**三内核**（Surge · Egern · mihomo），
#    这里原只有 surge / egern ⇒ ASSET_NAMES 派生不出 clash-* 四种资产名，
#    首次发布时 R2 判据把 4 个 clash 资产全判「不在固定名集合」。
KERN_LABEL = {'surge': 'Surge', 'egern': 'Egern', 'clash': 'mihomo'}
KERN_COLOR = {'surge': '0A84FF', 'egern': '10B981', 'clash': '8250DF'}
# 内核顺序（Surge → Egern → mihomo）。⚠️ 全脚本只认这一个元组，
# 不要再散写 KERNS —— 2026-10-08 彻查时全仓有 11 处硬编码两内核，
# 加 mihomo 后每处都得改，漏一处就是「资产少一个内核」这类静默缺失。
KERNS = ('surge', 'egern', 'clash')
KERN_EXT = {'surge': '.conf', 'egern': '.yaml', 'clash': '.yaml'}


def kern_ext(kern):
    """内核 → 配置扩展名（单一真源，替代 `'.conf' if kern == 'surge' else '.yaml'`）。"""
    return KERN_EXT[kern]

def badge_url(kern, fam):
    return (f"https://img.shields.io/badge/{KERN_LABEL[kern]}-{FAM_CN[fam]}_下载-"
            f"{KERN_COLOR[kern]}?style=for-the-badge")

# 每个更新日的主题（Release 标题 = 分类 emoji + 日期 + 主题；tag = v<日期>）。
# 禁止「维护性更新」这类通用兜底标题复用；文风 = 面向用户的正式产品语言
# （参考 Apple 更新说明）：专业、克制、通俗，不用文言腔。
# 发新版本前必须先在此补一行 —— 动线⑦的一部分。
DAY_THEMES = {
    '2026-09-24': ('🚀', '首次发布与分流版重构'),
    '2026-09-25': ('🔬', '注释修正与解析策略优化'),
    '2026-09-26': ('📶', 'Wi-Fi 自动暂停与占位节点'),
    '2026-09-27': ('📚', '文档修正与规则快照整合'),
    '2026-09-28': ('🔄', 'AI 规则集换源与自托管整合'),
    '2026-09-29': ('🛡️', '监听端口收敛与 IPv6 对齐关闭'),
    '2026-10-01': ('💰', '低倍率节点优先与分组精简'),
    '2026-10-04': ('🧹', '微信分组精简、Apple 规则集换源与直连白名单更名'),
    '2026-10-05': ('🧭', '分组精简与配置注释现况化'),
    '2026-10-06': ('🍎', 'Apple 更新分组、系统域落点调整与 Select 显性选择组'),
    '2026-10-07': ('🧹', '占位节点全面移除：只填订阅即可导入'),
    # 2026-10-08：整合仓首次发布 —— 三内核（Surge · Egern · mihomo）版本线统一 v1.0.0
    '2026-10-08': ('🎉', '首次发布：三内核版本线统一 v1.0.0'),
}

# ⚠️ 归组口径（2026-10-05 起）："注释/文案改动不升号" —— 它与"一天一版"合起来的结果是，
#    某天只改了懒人版**注释**（无功能/无配置键变动）时，懒人版**不升号、不入归档**，
#    而分流版若有实质改动则正常升号；那张 Release 的**懒人版小节会并列"现役旧版本号"**
#    与"分流版新版本号"，并在正文里说明懒人版仅注释更新。这是刻意的，不是漏写。
#    断言：check_min_pair V7（一天一版）只看**升过号的**版本，注释改动不会凭空造出新版本。

# 归组例外：个别版本的「版本号诞生日期」与「内容诞生日期」不同日，按内容事件归组。
# 依据（0929 实证）：c593895（2026-09-26 19:29）一个提交同时给懒人版（v1.3）与分流版
# （当时头注 v3.4）加入 [SSID Setting]；49392da（09-27）补归档升版只改 routing 头注
# v3.4→v3.5，正文与 .min 零改动。Wi-Fi 自动暂停是两条产品线同日的同一功能，
# 劈到两张 Release 会让 9-27 那张看起来「只有分流版有此功能」。
# 不用「剥头注再比对内容」做通用规则：那会把仅同步版本号的版本（surge v1.7/v3.7）
# 也回溯到旧日期 —— 只对确证的个案做显式例外。
DATE_OVERRIDES = {('routing', 'v3.5'): '2026-09-26'}

# 公众向更新摘要（Release 页是产品对外的更新日志，不搬运内部 commit subject）。
# 键：(family, version)，值 = 要点列表（1~4 条，逐版本如实总结，禁止模板句复用）。
# 内容依据 = config_old 相邻版本快照的逐行 diff（行为改动 + 有意义的注释修正）。
# 文风 = 面向用户的正式产品语言（参考 Apple 更新说明）：完整句子、专业、克制、通俗；
# 不用文言腔（口径修正/收编/压到最小/上线），不搬内部过程语言。
# 发新版本前必须先在此补一组 —— 动线⑦的一部分。
PUBLIC_NOTES = {
    # ── 2026-10-08 首次发布（三内核版本线统一 v1.0.0）
    #    本仓为整合仓：Surge · Egern 的 config_old/ 保留原仓历史版本（沿革），
    #    现役与 mihomo 一并从 v1.0.0 重新计数。
    ('lazy', 'v1.0.0'): [
        '首次发布（三内核版本线统一 v1.0.0）。内置订阅槽位与占位节点，导入后填入订阅即可使用。',
        '懒人版：一个总出口，只做防泄露 + 广告拦截 + AI 分流，省心优先。',
        'DNS 全链路加密解析；IPv6 显式关闭。',
        '三内核同源：Surge（.conf）、Egern（.yaml）、mihomo（.yaml）结构对齐。',
    ],
    ('routing', 'v1.0.0'): [
        '首次发布（三内核版本线统一 v1.0.0）。按应用 + 按地区细分，每个应用可单独指定走哪个地区。',
        '分流版：23 组 / 26 条规则（Surge · Egern）；mihomo 静态 25 组 / 27 条，'
        '覆写脚本输出 22 组 / 27 条。',
        '广告拦截前移；代理域名不给真答案；解析器全加密。',
        'mihomo 另有覆写脚本（my_clash.js / my_clash_lazy.js），'
        '不用下载配置 —— 挂在自己的订阅上即可改造成同样结构。',
    ],
    ('lazy', 'v1.0'): [
        '首次发布。内置订阅槽位与占位节点，导入后填入订阅即可使用。',
        '内置完整分流规则：广告拦截、AI 服务分流、系统与国内域名直连。',
        'DNS 全链路加密解析。',
    ],
    ('lazy', 'v1.1'): [
        '更新了配置内的注释说明：国内直连规则集的条数不再标注固定数字，因为上游每周更新，固定数字很快会过期。分流行为无变化。',
    ],
    ('lazy', 'v1.2'): [
        '新增订阅槽位：填入机场订阅链接后，节点会自动加入主出口与 AI 分组。',
        '精简了示例节点，保留两条占位节点（主出口与 AI 各一条）。',
        '仅填订阅或仅填节点均可正常使用。',
    ],
    ('lazy', 'v1.3'): [
        '新增 Wi-Fi 自动暂停（SSID Setting）：连接到可信网络时自动停用代理，离开后自动恢复。此功能仅 Surge 内核支持，Egern 内核无对应配置项。',
    ],
    ('lazy', 'v1.4'): [
        '修正了配置内的文档引用路径。分流行为无变化。',
    ],
    ('lazy', 'v1.5'): [
        '文档引用路径已迁移至仓库的新目录结构。分流行为无变化。',
    ],
    ('lazy', 'v1.6'): [
        '广告拦截组移除了多余的 DIRECT 备选项，保持默认拦截、可手动放行。',
        'Apple 系统服务规则集改为使用本仓库自托管的快照，两个内核使用同一来源。',
    ],
    ('lazy', 'v1.7'): [
        '国内域名规则集更名为 CN-Domains，在客户端日志中更易识别。分流行为无变化。此改动仅涉及 Egern 内核，Surge 内核仅同步版本号。',
    ],
    ('lazy', 'v1.8'): [
        'AI 服务规则集更换为持续维护的上游，新增覆盖 Gemini、Sora、Grok 等服务。原上游已停止更新。',
    ],
    ('lazy', 'v1.9'): [
        '新增自托管 AI 域名整合集（合并 10 个来源）：googleapis.com 等伴生域名整体纳入 AI 分流，ChatGPT 认证与遥测相关域名不再遗漏。',
        'AI 分组由自动测速改为手动选择：AI 服务对出口 IP 频繁变化较为敏感，固定节点使用更稳定。',
    ],
    ('lazy', 'v2.0'): [
        ('关闭局域网代理共享端口', [
            'Surge：`allow-wifi-access = false`、`allow-hotspot-access = false`',
            '影响：局域网共享出口由专用网关承担；本机不再开放监听端口，暴露面收窄。',
        ]),
        ('关闭 IPv6', [
            'Surge：`ipv6 = false`、`ipv6-vif = disable`',
            'Egern：`ipv6: false`',
            '影响：不再返回 AAAA 记录，双栈站点自动回落 IPv4；两版行为对齐。',
        ]),
    ],
    ('routing', 'v1'): [
        '分流版首次发布：按应用分组（ChatGPT、Gemini、Claude、YouTube、Telegram 等），并支持地区智能选组。',
        '此版本仅提供 Egern 侧文件。',
    ],
    ('routing', 'v2'): [
        '重构 DNS 配置：移除冗余的域名映射与重复的兜底规则，上游端点精简为两个机构的 DoH / DoT 组合，明文解析通路仅保留一条。',
        '防泄露能力经审计脚本逐项验证，配置更简短、更易读。',
    ],
    ('routing', 'v2.1'): [
        '移除仅使用默认值的配置项（IPv6 开关、路由兼容选项等）。行为无变化，文件更简洁。',
    ],
    ('routing', 'v2.2'): [
        '机场订阅槽位由 4 个精简至 2 个。',
        'MAX 分组改为低倍率节点智能筛选：先按倍率过滤，再自动选择最优节点。',
    ],
    ('routing', 'v2.3'): [
        '修正 MAX 低倍率筛选：此前的规则会误收部分高倍率节点、同时遗漏低倍率节点，现改为收录所有低于 1 倍率的节点，并经 18 个真实节点样例验证。',
        '修复 ChatGPT、Gemini 分组为空时导入后断流的问题，已补充默认出口。',
        'Smart 分组补齐节点展开，自动选择改为节点级测速。',
    ],
    ('routing', 'v2.4'): [
        '为全部 21 条规则集补充每日自动更新：此前仅在首次下载后不再更新，导致新收录的域名无法命中。',
    ],
    ('routing', 'v3'): [
        '规则段与 Surge 分流版逐行对齐：新增内网直连规则，移除与主规则集重复的 .cn 兜底。',
        'DNS 转发扩展为四层：白名单、两条广告清单在解析阶段直接拒答，再到兜底，广告在 DNS 层即被拦截。',
        '机场订阅入口合并为单一隐藏槽位，并为各应用分组补充默认取向（Claude 至台湾、Spotify 与 YouTube Music 至美区、Microsoft 直连等）。',
    ],
    ('routing', 'v3.1'): [
        '规则集更新周期由每天调整为每周，与 Surge 侧保持一致，减少不必要的重复下载。',
    ],
    ('routing', 'v3.2'): [
        '逐条实测并优化各规则集的 no-resolve 设置：纯域名规则集不再写入解析开关；包含 IP 条目的规则集则必须写入，以避免额外的本地解析。',
        '新增自托管 Apple 系统服务快照集，补齐 Egern 缺失的内置系统规则。',
        '文件启用首行版本号标注。',
    ],
    ('routing', 'v3.3'): [
        '新增两条占位节点：仅填节点时主出口与 AI 分组同样可用，仅填订阅也可正常运行。',
        'Spotify 与 YouTube Music 的默认出口设为美区。',
        'AI 分组默认使用独立占位节点，不与主出口共用。',
    ],
    ('routing', 'v3.4'): [
        '修正了订阅占位符数量的说明。此为文档性修正，配置行为无变化。',
    ],
    ('routing', 'v3.5'): [
        '新增 Wi-Fi 自动暂停（SSID Setting）：连接到可信网络时自动停用代理，离开后自动恢复。此功能仅 Surge 内核支持，Egern 内核无对应配置项。',
    ],
    ('routing', 'v3.6'): [
        '配置内的文档引用路径已迁移至仓库的新目录结构。分流行为无变化。此改动仅涉及 Egern 内核，Surge 内核仅同步版本号。',
    ],
    ('routing', 'v3.7'): [
        '国内域名规则集更名为 CN-Domains，在客户端日志中更易识别。分流行为无变化。此改动仅涉及 Egern 内核，Surge 内核仅同步版本号。',
    ],
    ('routing', 'v3.8'): [
        'AI 服务规则集更换为持续维护的上游。原 ACL4SSR 源已停止更新，且缺少 Gemini 相关域名。',
    ],
    ('routing', 'v3.9'): [
        '新增自托管 AI 域名整合集（266 条，合并 10 个来源）：googleapis.com、googleusercontent.com 等伴生域名整体纳入，GMS 网关与 ChatGPT 认证、遥测相关域名不再遗漏。',
        '上游换源集继续滚动维护新增的 AI 域名，本集合负责结构稳定的伴生域与宽后缀，两者分工互补。',
    ],
    ('routing', 'v4.0'): [
        ('关闭局域网代理共享端口', [
            'Surge：`allow-wifi-access = false`、`allow-hotspot-access = false`',
            '影响：局域网共享出口由专用网关承担；本机不再开放监听端口，暴露面收窄。',
        ]),
        ('关闭 IPv6', [
            'Surge：`ipv6 = false`、`ipv6-vif = disable`',
            'Egern：`ipv6: false`',
            '影响：不再返回 AAAA 记录，双栈站点自动回落 IPv4；两版行为对齐。',
        ]),
    ],
    ('lazy', 'v2.0.1'): [
        '修正了配置注释中的过期版本号与规则条数描述，当前版本信息统一只保留在文件头注。分流行为无变化。',
    ],
    ('routing', 'v4.0.1'): [
        '修正了配置注释中的过期版本号与规则条数描述，当前版本信息统一只保留在文件头注。分流行为无变化。',
        '移除了订阅槽位中重复的占位地址。分流行为无变化。',
    ],
    ('routing', 'v4.0.2'): [
        '原 MAX 分组并入 Smart 分组：低倍率节点由「只走低倍率」改为「优先低倍率」，其不可用或明显更慢时自动切换到其他节点；分组数量由 26 个减少至 25 个。',
        'Surge / Egern 内核同步支持该优先策略，取值、匹配规则一致。',
    ],
    ('routing', 'v4.0.3'): [
        '移除微信分组与微信规则集：微信在国内的流量改由国内域名清单与 IP 归属判定接管，结果仍为直连；规则集里少量指向境外的腾讯云 IP 段改由代理访问。分组数量由 25 个减少至 24 个。',
        'Apple 规则集更换为「在中国大陆可直连」的域名清单（165 条）。原清单包含大量面向境外的 Apple 域名，强制直连反而更慢。',
        'App Store、软件更新、定位、推送，以及中国大陆账号的 iCloud 仍为直连；开发者站点、国际版 iCloud 端点与第三方 CloudKit 服务改由代理访问。',
        '防误杀直连白名单规则集随上游更名：`surge-white-guard.list` → `surge-direct.list`，订阅地址同步更新；同时新增一条放行域名，白名单由 43 条增至 44 条。这份清单排在两条广告清单之前，作用是放行会被广告规则误杀的域名（命中即直连）；地址变更本身不影响分流行为。',
        '配置注释不再标注规则集的固定条数：上游规则集每周更新，固定数字很快会过期，改由脚本现抓。分流行为无变化。',
    ],
    ('lazy', 'v2.0.2'): [
        '修正了配置内关于 Apple 规则集的一处说明。分流行为无变化。此改动仅涉及 Surge 内核，Egern 内核仅同步版本号。',
        '防误杀直连白名单规则集随上游更名：`surge-white-guard.list` → `surge-direct.list`，订阅地址同步更新；同时新增一条放行域名，白名单由 43 条增至 44 条。这份清单排在两条广告清单之前，作用是放行会被广告规则误杀的域名（命中即直连）；地址变更本身不影响分流行为。',
        '配置注释不再标注规则集的固定条数：上游规则集每周更新，固定数字很快会过期，改由脚本现抓。分流行为无变化。',
        '配置注释改为只描述当前状态，不再保留历代版本的沿革说明。配置更短、更好读，分流与防 DNS 泄露行为均无变化（注释更新不升版本号）。',
    ],
    ('lazy', 'v2.0.3'): [
        '系统域名（Apple 激活、推送、定位与配对主机）提升为最高优先级规则，排在所有规则之前（原在广告拦截之后）。本次调整不改变拦截结果：系统域清单与两条广告清单没有重叠域名。',
    ],
    ('routing', 'v4.0.4'): [
        '分组精简：移除韩国、GitHub 与 Final 三个分组，分流版分组数量由 24 个减少至 21 个，另新增 Emby 分组，现为 22 个。韩国节点并入「其他地区」分组仍可正常选用；GitHub 的规则集保留，流量改走主出口；兜底流量改由规则直接指向主出口。分流结果与防 DNS 泄露能力均无变化。',
        '分组顺序与名称整理：地区分组按「香港 / 台湾 / 日本 / 新加坡 / 美国 / 其他地区」排列，应用分组按「YouTube / Emby / Google / Telegram / YouTube Music / Spotify / Twitter / Microsoft」排列（新增 Emby 分组，用于 Emby 影视服务域名，规则集自托管于本仓）；原「USA」更名为「United States」，原「YouTubeMusic」更名为「YouTube Music」。分组与规则的排列顺序保持一致（YouTube Music 的规则因规则集包含关系需排在 YouTube 之前）。均为顺序与命名调整，不改变分流结果。',
        'ChatGPT 与 Gemini 分组的默认出口改为美区，与 Spotify、YouTube Music 的取向保持一致（此前跟随智能选优）。',
        '配置注释改为只描述当前状态，不再保留历代版本的沿革说明。配置更短、更好读，分流与防 DNS 泄露行为均无变化。',
        '订阅刷新间隔与延迟测试端点补齐：Egern 侧的订阅槽位此前未显式设置刷新周期，现固定为一周（与 Surge 侧一致）；两个内核的延迟测试端点也统一为同一组地址。均为可预期性改进，不改变分流结果。',
    ],
    ('lazy', 'v2.0.4'): [
        '系统域名规则（Apple 激活、推送、定位与配对主机）不再排在所有规则之前，改为排在广告拦截之后、内网规则之前。分流结果与防 DNS 泄露能力均无变化。',
    ],
    ('lazy', 'v2.0.5'): [
        '移除 `Node-A` / `Node-B` 两条占位节点：四份配置的节点自此**全部来自订阅**，导入时只需填 `Airport` 的订阅 URL，不再需要手工补本机节点。',
    ],
    ('routing', 'v4.0.5'): [
        '新增「Apple Update」分组（现位于「Microsoft」之后、「AD」之前），用于系统更新（OTA）流量：默认直连，可在面板上随时切换为拒绝以阻止自动下载。',
        '系统域名规则（Apple 激活、推送、定位与配对主机）不再排在所有规则之前，改为排在系统更新规则之后、内网规则之前。分流结果与防 DNS 泄露能力均无变化。',
        '新增「Select」分组，与「Smart」同为订阅全节点池，但不带任何权重、也不自动选优：面板上可逐个看到全部节点并直接手动指定。它位于「Smart」之后，两者并列为「Proxy」的成员；懒人版无此分组。',
        '分组数量由 22 个增加至 24 个、规则数量由 25 条增加至 26 条。',
        '移除 `[Proxy]` 里两条占位节点（`Node-A` / `Node-B`）：分流版的 `[Proxy]` 自此为空，节点全部来自订阅 —— 只填一个订阅 URL 就能导入，不再需要手工补节点。懒人版保持原样。',
    ],
}

def git(*a):
    return subprocess.check_output(['git', *a], text=True).strip()

def repo_root():
    return git('rev-parse', '--show-toplevel')

def parse_ver(name):
    m = re.search(r'_(v\d+(?:\.\d+){0,2})\.', name)
    return m.group(1) if m else None

def vkey(ver):
    return tuple(int(x) for x in ver[1:].split('.'))

def active_versions(root):
    """现役版本：从头注 #! version= 读，两内核应同号。"""
    out = {}
    for fam in FAMS:
        vers = set()
        for kern, ext in (('surge', '.conf'), ('egern', '.yaml')):
            p = os.path.join(root, kern, 'profiles', f'{fam}{ext}')
            with open(p, encoding='utf-8') as fh:
                m = re.search(r'^#!\s+version=(\S+)', fh.read(400), re.M)
            vers.add(m.group(1).split('_', 1)[-1])
        assert len(vers) == 1, f'{fam} 两内核头注版本不一致: {vers}'
        out[fam] = vers.pop()
    return out

def archive_file(root, kern, fam, ver):
    ext = kern_ext(kern)
    return os.path.join(root, kern, 'profiles', 'config_old', f'{fam}_{ver}{ext}')

def archive_min(root, kern, fam, ver):
    ext = kern_ext(kern)
    return os.path.join(root, kern, 'profiles', 'config_old', f'{fam}_{ver}.min{ext}')

def _blob_birth(root, kern, fam, path):
    """path（仓库内相对路径）所指 blob 首次进入该 profile 历史的提交日期。

    历史重写查不到诞生提交时，兜底取该文件被加入 repo 的日期；再查不到返回 None。
    ⚠️ 本函数仍是**归档版**（`config_old/` 快照）的正式口径 —— 快照是冻住的内容，
       其 blob 首现日就是那版内容的诞生日，与是否升号无关。
       它也是现役版在“号查不到”时的兜底。"""
    rel = path.replace(os.sep, '/')
    prof = f'{kern}/profiles/{fam}{".conf" if kern == "surge" else ".yaml"}'
    # ⚠️ 文件不存在就别查 —— 否则下面 `--diff-filter=A` 会对一个不存在的路径返回
    #    最近一次提交的日期（假值），把「本内核没有这一版」误报成一个日期。
    #    2026-10-05 实测：`routing v1`/`v2` 只有 egern 侧有归档，surge 侧因此拿到
    #    当天日期，把 v1/v2 成片算进 10-05，V7 报「一天 9 个版本」。
    if not os.path.exists(os.path.join(root, rel)):
        return None
    try:
        sha = git('rev-parse', f'HEAD:{rel}')
        log = git('log', '--reverse', '--format=%as', '--find-object=' + sha, '--', prof)
        lines = [l for l in log.splitlines() if l.strip()]
        if lines:
            return lines[0]
    except subprocess.CalledProcessError:
        pass
    try:
        log = git('log', '--diff-filter=A', '--format=%as', '--', rel)
        lines = [l for l in log.splitlines() if l.strip()]
        return lines[-1] if lines else None
    except subprocess.CalledProcessError:
        return None

def number_birth(root, kern, fam, ver):
    """该版本号（`#! version=<fam>_v<ver>`）**首次加进该 profile** 的日期 —— 只用于**现役版**。

    为什么现役版需要它（2026-10-05 改口径）
    ──────────────────────────────────────
    本仓政策是“**注释/文案改动不升号**”（见 SKILL.md「归档机制」）。若某天只给懒人版
    改了注释、版本号不动，那么“现役文件 blob 的诞生日”会跟着挪到那天 ⇒ 懒人版会被
    拉进当天那张 Release（而它本属于旧版本），版本号与发布日期从此错位。
    “版本号首现日”不受无号改动影响：号没变，日期就不变。

    为什么要锚定正则、不能用 `-S`
    ──────────────────────────────
    `-S` 是**子串**匹配：`#! version=routing_v1` 会把 `routing_v1.0` / `v1.1` … 全部命中
    （2026-10-05 实测：历史版本被成片错分到最新一天）。改写 `-G "^#! version=<号>$"`
    （basic regex，`^$` 锚定整行）后逐版本正确。
    ⚠️ `-G` 同时匹配“增加”与“删除”：升号那天旧号那一行被改掉也算一次命中。
       因此取 `--reverse` 后的**第一条** = 首次出现（即加入那一次），不能取最后一条。
    ⚠️ 兜底：早期版本（v1 / v2 / v3.0–v3.4）根本没有 `#! version=` 头注 ⇒ 查不到，
       退回 blob 口径。现役版全部有头注，故不影响；归档版走 `version_date`，本就不经这里。"""
    ext = kern_ext(kern)
    prof = f'{kern}/profiles/{fam}{ext}'
    # ⚠️ 入参 `ver` 可能带 `v` 前缀（`parse_ver`/`active_versions` 返回的就是 `v2.0.3`），
    #    而头注里是 `#! version=lazy_v2.0.3`（只有一个 v）⇒ 必须先剥掉前缀再拼，
    #    否则 pattern 变成 `lazy_vv2.0.3`，永远匹配不到（2026-10-05 实测踩到）。
    ver_bare = ver[1:] if ver.startswith('v') else ver
    try:
        log = git('log', '--reverse', '--format=%as', '-G',
                  f'^#! version={fam}_v{ver_bare}$', '--', prof)
        lines = [l for l in log.splitlines() if l.strip()]
        if lines:
            return lines[0]
    except subprocess.CalledProcessError:
        pass
    # ⚠️ 这里**不设 blob 兜底**：兜底是调用方的事 —— 现役版兜底到现役文件、归档版
    #    兜底到归档快照。早先在这里统一兜底到「现役文件」，害得归档版查到的是**现役
    #    文件**的最近改动日期（= 今天），把 v1/v2 成片算进 10-05（2026-10-05 实测）。
    return None

# ⚠️ 为什么用 `-G` 而不是 `-S`（防御性选择，不是当前 bug 修复）：
#    `-G` 锚定整行；`-S` 是**子串**匹配 —— 若未来出现互为前缀的现役号（如 v4.1 与 v4.1.0
#    共存过一段时间），`-S` 会把新号的首现日错记成旧号的首现日。当前两个产品线的现役号
#    之间不存在这种关系（_v1 配 _v1.0 那类只存在于**归档**，而归档走 `version_date`、不经这里），
#    所以今天两者结果相同（2026-10-05 实测全量对拍 0 处不符）。取 -G 是为了不对未来埋雷。
#    ⚠️ 这个选择**无专用闸门**（2026-10-05 实测：把 -G 换回 -S，`check_releases` 仍 140 passed
#      —— 因为当前现役号互不为前缀、两者结果同值）。按本仓纪律「靠注释提醒不可靠」的处置方式，
#      已把它登记为仓级**已论定裁定**（含重议条件），而不是只留一句“靠注释”：
#      `skill/reference/shared/boundaries.md` §2「不建日期口径专用闸门」。

def version_date(root, kern, fam, ver):
    """版本诞生日期：先取「版本号首现日」，查不到才退回「快照/文件 blob 诞生日」。

    ⚠️ 2026-10-05 修正（实测事故）：原先归档版**只用** blob 口径，对「补归档」失灵 ——
       懒人版 v2.0.2 生于 10-04，但当天没归档（当天懒人版没升号），归档动作发生在
       10-05 ⇒ 快照 blob 诞生日 = 10-05，于是 v2.0.2 被算进 10-05 组，与 v2.0.3
       撞成「一天两个版本」，V7 误判负。号首现日对此免疫：号是 10-04 出现的。
    ⚠️ 兜底仍必要：早期版本（v1 / v2 / v3.0–v3.4）没有 `#! version=` 头注，
       只能退回 blob 口径。"""
    ext = kern_ext(kern)
    d = number_birth(root, kern, fam, ver)
    if d:
        return d
    arch = os.path.join(kern, 'profiles', 'config_old', f'{fam}_{ver}{ext}')
    return _blob_birth(root, kern, fam, arch)

def build_days(root):
    """按版本诞生日期分组：一天 = 一个候选 Release。

    ⚠️ 日期口径（2026-10-05 起，与「注释不升号」政策配套）：
       现役版 = `number_birth`（版本号首现日）；归档版 = `version_date`（快照 blob 诞生日）。
       理由与判据见 `number_birth` 的 docstring。

    返回按日期升序的 day 列表：
        {date, tag, emoji, theme, is_current,
         fams: {fam: {'versions': [v1, v2...],   # 当日该产品线全部版本（升序）
                      'entries':  [版本 dict...],
                      'assets':   {kern: {full, min}},  # 当日最终版本的固定名资产
                      }}}"""
    act = active_versions(root)
    versions = []
    for fam in FAMS:
        vers = set()
        for kern in KERNS:
            d = os.path.join(root, kern, 'profiles', 'config_old')
            for f in os.listdir(d):
                if parse_ver(f) and f.startswith(fam + '_v'):
                    vers.add(parse_ver(f))
        vers.add(act[fam])
        for ver in sorted(vers, key=vkey):
            is_cur = ver == act[fam]
            kerns = {}
            for kern in KERNS:
                ext = kern_ext(kern)
                full = os.path.join(root, kern, 'profiles', f'{fam}{ext}') if is_cur \
                    else archive_file(root, kern, fam, ver)
                if not os.path.exists(full):
                    kerns[kern] = None
                    continue
                mn = full[:full.rindex(ext)] + f'.min{ext}'
                # 现役版 / 归档版统一走 version_date —— 它先取「版本号首现日」，
                # 查不到才退回 blob 口径（见其 docstring 的 2026-10-05 修正说明）。
                date = version_date(root, kern, fam, ver)
                kerns[kern] = {'full': os.path.relpath(full, root),
                               'min': os.path.relpath(mn, root), 'date': date}
            dates = sorted({i['date'] for i in kerns.values() if i and i['date']})
            versions.append({'family': fam, 'version': ver, 'is_current': is_cur,
                             'kerns': kerns,
                             'date': DATE_OVERRIDES.get((fam, ver)) or (dates[0] if dates else None)})
    grouped = {}
    for v in versions:
        grouped.setdefault(v['date'] or '未知日期', []).append(v)
    days = []
    for date in sorted(grouped):
        vs = grouped[date]
        fams = {}
        for fam in FAMS:
            fv = sorted((v for v in vs if v['family'] == fam), key=lambda v: vkey(v['version']))
            if not fv:
                continue
            latest = fv[-1]
            fams[fam] = {'versions': [v['version'] for v in fv], 'entries': fv,
                         'assets': {k: latest['kerns'][k] for k in KERNS
                                    if latest['kerns'].get(k)}}
        emoji, theme = DAY_THEMES.get(date, ('📦', '配置更新'))
        days.append({'date': date, 'tag': f'v{date}', 'emoji': emoji, 'theme': theme,
                     'is_current': any(v['is_current'] for v in vs), 'fams': fams})
    return days

def asset_name(kern, path):
    """固定名 = 内核前缀 + 产品线（如 surge-lazy.conf）：Assets 面板自解释，
    不必依赖「.conf=Surge / .yaml=Egern」的圈内约定。"""
    return kern + '-' + re.sub(r'_(v\d+(?:\.\d+){0,2})', '', os.path.basename(path))

# 资产固定名全集 —— check_releases 的 R2 白名单从这派生，单一真源防两份手抄漂移。
ASSET_NAMES = {f'{kern}-{fam}{ext}' for kern in KERN_LABEL for fam in FAM_CN
               for ext in ('.conf', '.min.conf', '.yaml', '.min.yaml')}

def _day_items(day):
    """[(fam, [(version, note), ...]), ...]，按 FAMS 顺序，缺侧产品线不在结果里。"""
    out = []
    for fam in FAMS:
        if fam not in day['fams']:
            continue
        items = []
        for e in day['fams'][fam]['entries']:
            notes = PUBLIC_NOTES.get((fam, e['version']), [])
            if isinstance(notes, str):
                notes = [notes]
            items += [(e['version'], n) for n in notes]
        out.append((fam, items))
    return out


def _vers_range(vers):
    # ⚠️ 2026-10-08 修正：本仓由两仓**复制**整合而来，不继承原仓 git 历史，
    #    build_days() 算不出版本诞生日期 ⇒ fam_vers[fam] 可能是空列表 ⇒ 这里
    #    原先直接 vers[0] 抛 IndexError（整个脚本 traceback 崩掉，看不出真实原因）。
    #    现在退化成占位并让上层给出可读说明 —— 崩溃比错误结论更糟，
    #    但**静默编造一个版本号**更糟，所以用显式占位 + 提示。
    if not vers:
        return '(版本信息缺失：git 历史不完整)'
    return vers[0] + (f' → {vers[-1]}' if len(vers) > 1 else '')


def _item_key(note):
    """条目归一化键：结构化条目 (标题, 行列表) 与散文条目分别取键，用于两产品线去重。"""
    if isinstance(note, tuple):
        return ('s', note[0], tuple(note[1]))
    return ('p', note)


def build_notes(day):
    """Release 说明（面向公众的产品更新日志，正式产品语言）。

    层级（2026-09-29 二次定稿，与用户模板一致）：
    # 懒人版 vX / 分流版 vY 更新日志     ← H1 永远置顶（多版本日用范围）
    > 引言一句（两版变更一致时点明；单边内核日在括注里说明）
    ## 共同变更 → ### N. 标题 + 结构行（PUBLIC_NOTES 结构化条目）；散文条目维持要点列表
    ## 懒人版变更 / ## 分流版变更（各自条目，缺侧不写节）
    ## 适用版本 → 各产品线版本
    下载按钮区。**没有元信息小字行。**
    行距：GitHub 剥掉正文 CSS，无法真设 line-height；用列表项间空一行（松散列表）近似。"""
    fams_items = _day_items(day)
    fam_vers = {fam: list(dict.fromkeys(v for v, _ in items)) for fam, items in fams_items}
    # 去重：条目归一化键完全一致、且当日两产品线都有的条目 → 共同变更
    by_key, first = {}, {}
    for fam, items in fams_items:
        for v, n in items:
            k = _item_key(n)
            by_key.setdefault(k, []).append((fam, v))
            first.setdefault(k, (v, n))
    common = [k for k, pairs in by_key.items()
              if len(fams_items) > 1 and len({f for f, _ in pairs}) == len(fams_items)]
    common_keys = set(common)

    def multi_prefix(pairs):
        return ' · '.join(f'{FAM_CN[f]} {v}' for f, v in
                          sorted(set(pairs), key=lambda p: FAMS.index(p[0])))

    def render_entry(idx, ver, note, multi, pairs=None):
        """一条变更：结构化条目 → ### N. 标题 + 行列表；散文条目 → 要点（多版本日加前缀）。"""
        if isinstance(note, tuple):
            title = note[0]
            if multi and pairs:
                title = f'{title}（{multi_prefix(pairs)}）'
            out = [f'### {idx}. {title}', '']
            for ln in note[1]:
                out += [f'- {ln}', '']
            return out, idx + 1
        if multi and pairs:
            return [f'- **{multi_prefix(pairs)}**：{note}', ''], idx
        if multi:
            return [f'- **{ver}** {note}', ''], idx
        return [f'- {note}', ''], idx

    lines = []
    # H1：更新日志标题置顶，永远是正文最大的字
    lines.append('# ' + ' / '.join(f'{FAM_CN[fam]} {_vers_range(fam_vers[fam])}'
                                   for fam, _ in fams_items) + ' 更新日志')
    lines.append('')
    # 引言
    all_common = (len(fams_items) == 2 and bool(common) and
                  all(_item_key(n) in common_keys for _, items in fams_items for _, n in items))
    if all_common:
        core = '本次两版同步，变更一致。'
    elif len(fams_items) == 2 and common:
        core = '本次两版同步更新，共同变更如下，各侧独立变更分列其后。'
    elif len(fams_items) == 2:
        core = '本次懒人版与分流版各有变更，分列如下。'
    else:
        core = f'本次更新仅涉及{FAM_CN[fams_items[0][0]]}。'
    extras = []                                        # 单边内核日在引言括注（缺席产品线不提，核心句已说清）
    for fam in FAMS:
        if fam not in day['fams']:
            continue
        assets = day['fams'][fam].get('assets', {})
        missing = [k for k in KERNS if k not in assets]
        if len(missing) == 1:
            have = [k for k in KERNS if k in assets]
            extras.append(f'{FAM_CN[fam]}当日仅 {KERN_LABEL[have[0]]} 内核有内容变化')
        elif len(missing) == 2:
            extras.append(f'{FAM_CN[fam]}当日无内容变化')
    lines.append('> ' + core + (f'（{"；".join(extras)}）' if extras else ''))
    lines.append('')

    multi = any(len(vs) > 1 for vs in fam_vers.values())
    # 共同变更
    if common:
        lines += ['## 共同变更', '']
        idx = 1
        for k in common:
            ver, note = first[k]
            chunk, idx = render_entry(idx, ver, note, multi, by_key[k])
            lines += chunk

    # 各产品线变更（仅剩各自条目）
    for fam, items in fams_items:
        own = [(v, n) for v, n in items if _item_key(n) not in common_keys]
        if not own:
            continue
        lines += [f'## {FAM_CN[fam]}变更', '']
        idx = 1
        for v, n in own:
            chunk, idx = render_entry(idx, v, n, len(fam_vers[fam]) > 1)
            lines += chunk

    # 适用版本
    lines += ['## 适用版本', '']
    for fam, _ in fams_items:
        lines += [f'- {FAM_CN[fam]} {_vers_range(fam_vers[fam])}', '']

    # 下载按钮
    buttons = []
    for fam in FAMS:
        for kern in KERNS:
            info = day['fams'].get(fam, {}).get('assets', {}).get(kern)
            if not info:
                continue
            name = asset_name(kern, info['full'])
            buttons.append(f'[![Download {KERN_LABEL[kern]} {fam}]({badge_url(kern, fam)})]({DL}/{day["tag"]}/{name})')
    if buttons:
        lines += [' '.join(buttons), '']
    return '\n'.join(lines)


def release_title(day):
    """Release 标题：emoji + 日期 + 当日主题（tag 芯片在旁显示 vYYYY-MM-DD）。"""
    return f"{day['emoji']} {day['date']} · {day['theme']}"

def api_req(url, token, method='GET', data=None, ctype='application/json', raw=None):
    body = raw if raw is not None else (json.dumps(data, ensure_ascii=False).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'self-conf-release')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    if body is not None:
        req.add_header('Content-Type', ctype)
    return urllib.request.urlopen(req)

def existing_releases(token):
    out, page = [], 1
    while True:
        with api_req(f'{API}/releases?per_page=100&page={page}', token) as r:
            batch = json.load(r)
        out += batch
        if len(batch) < 100:
            return out
        page += 1

def _asset_stale(asset, path):
    """Release 上已有同名资产、但内容与本地文件不一致（如归组调整后同一固定名换了版本内容）。

    优先用 API 返回的 digest（sha256）在本地比对，零下载；digest 缺失才退回
    大小 + 下载全量比对；下载失败视为不陈旧，宁可跳过不误删。"""
    with open(path, 'rb') as fh:
        local = fh.read()
    digest = asset.get('digest') or ''
    if digest.startswith('sha256:'):
        return digest != 'sha256:' + hashlib.sha256(local).hexdigest()
    if asset.get('size') != len(local):
        return True
    try:
        req = urllib.request.Request(asset['browser_download_url'],
                                     headers={'User-Agent': 'self-conf-release'})
        return urllib.request.urlopen(req).read() != local
    except Exception:                                  # noqa: BLE001
        return False

def apply(days, token):
    ex = {r['tag_name']: r for r in existing_releases(token)}
    created, updated, skipped, failed = [], [], [], []
    # 现行日取**最新**那天，与 check_releases 的 R5 同一口径。
    # ⚠️ 单产品线更新日会有两个现行日（未动的那条产品线，其现役版本仍停在旧日期分组）；
    #    用 next 会取到最早那天 ⇒ latest_ok 恒为 False，白白多打一次 PATCH。
    current_tag = max((d['tag'] for d in days if d['is_current']), default=None)
    # Latest 已指向现行日就不再 PATCH：逐个 PATCH 会让指针抖动，
    # 与 CI 的 Releases 检查步构成竞态（0929 实测红过一次）
    # 注：这里**刻意不套四态退出码协议**（check_releases 的 Skip/3 体系）—— 本函数是
    # mutating 发布器，读不到 Latest 只影响「要不要多 PATCH 一次」，走保守分支即
    # latest_ok=False（reconcile 幂等，多跑一次无害），不能把「读不到」升级成中断发版。
    req = urllib.request.Request(f'{API}/releases/latest',
                                 headers={'User-Agent': 'self-conf-release'})
    try:
        latest_ok = json.load(urllib.request.urlopen(req)).get('tag_name') == current_tag
    except Exception:                                  # 404 = 仓库还没有任何 Latest
        latest_ok = False
    for day in days:                                   # 日期升序创建 → 列表时间线自然正确
        tag = day['tag']
        try:
            if tag in ex:
                rel = ex[tag]
            else:
                with api_req(API + '/releases', token, 'POST',
                             {'tag_name': tag, 'target_commitish': 'main', 'name': release_title(day),
                              'body': build_notes(day),
                              'make_latest': 'true' if day['is_current'] else 'false'}) as r:
                    rel = json.load(r)
                created.append(tag)
                time.sleep(2)                          # 拉开 created_at，保证列表排序稳定
            # 幂等 reconcile：已存在的 Release 标题/说明与当前模板不一致就回写
            new_body = build_notes(day)
            new_name = release_title(day)
            patch = {}
            if (rel.get('body') or '') != new_body:
                patch['body'] = new_body
            if (rel.get('name') or '') != new_name:
                patch['name'] = new_name
            if patch:
                api_req(f"{API}/releases/{rel['id']}", token, 'PATCH', patch)
                updated.append(tag)
            # 资产 reconcile 以期望清单为准：缺的补传、同名不同内容的删传、
            # 清单外的（如改名前的旧名资产）删除 —— 防改名/换版后残留
            have = {a['name']: a for a in rel.get('assets', [])}
            expected = {}
            for fam in FAMS:
                for kern, info in day['fams'].get(fam, {}).get('assets', {}).items():
                    for key in ('full', 'min'):
                        expected[asset_name(kern, info[key])] = os.path.join(repo_root(), info[key])
            deleted = set()
            for a in rel.get('assets', []):
                if a['name'] not in expected or _asset_stale(a, expected[a['name']]):
                    api_req(f"{API}/releases/assets/{a['id']}", token, 'DELETE')
                    deleted.add(a['name'])
            for name, path in expected.items():
                if name in have and name not in deleted:
                    continue
                with open(path, 'rb') as fh:
                    raw = fh.read()
                api_req(f"{UPLOAD}/{rel['id']}/assets?name={name}", token, 'POST',
                        raw=raw, ctype='application/octet-stream')
            # Latest 只钉现行日（= 最新那个现行日）；未指向时补钉一次
            if tag == current_tag and not latest_ok:
                api_req(f"{API}/releases/{rel['id']}", token, 'PATCH', {'make_latest': 'true'})
            if tag not in created:
                skipped.append(tag)
        except Exception as exc:                       # noqa: BLE001 —— 逐条报告，不中断后续
            failed.append((tag, str(exc)[:120]))
    print(f'\n创建 {len(created)}：{", ".join(created) or "—"}')
    print(f'回写 {len(updated)}：{", ".join(updated) or "—"}')
    print(f'已存在跳过 {len(skipped)}：{", ".join(skipped) or "—"}')
    print(f'失败 {len(failed)}：{failed or "—"}')
    return 0 if not failed else 1

def show_plan(days):
    for d in days:
        fam_bits = []
        for fam in FAMS:
            if fam not in d['fams']:
                continue
            info = d['fams'][fam]
            kerns = '/'.join(k for k in KERNS if k in info['assets']) or '无资产'
            fam_bits.append(f"{FAM_CN[fam]} {'→'.join(info['versions'])}[{kerns}]")
        mark = '现行' if d['is_current'] else '历史'
        print(f"{d['tag']:14s} {mark}  {'  '.join(fam_bits)}")
    print(f'\n共 {len(days)} 张 Release（按版本诞生日期归并）')
    # 样例取**最新**现行日 —— 计划模式要显示的是"现行版长什么样"。
    # ⚠️ 用 next(升序) 会命中最早那个现行日：单产品线更新日有两个现行日
    # （未动的产品线其现役版本仍停在旧日期分组），打出来的是旧日正文（2026-10-01 实测踩过）。
    sample = max((d for d in days if d['is_current']), key=lambda d: d['tag'], default=days[-1])
    print(f'\n──── 说明样例（{sample["tag"]}）────')
    print(build_notes(sample))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真发（默认只出计划）')
    ap.add_argument('--token', default=os.environ.get('GITHUB_TOKEN'), help='GitHub token（--apply 必需）')
    args = ap.parse_args()
    days = build_days(repo_root())
    if not args.apply:
        show_plan(days)
        print('\n（计划模式：一个 Release 都不发。加 --apply 才发布，需 --token 或 GITHUB_TOKEN）')
        return 0
    if not args.token:
        print('❌ --apply 需要 --token 或环境变量 GITHUB_TOKEN'); return 2
    return apply(days, args.token)

if __name__ == '__main__':
    sys.exit(main())
