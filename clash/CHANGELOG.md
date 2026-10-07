# 更新日志

本文件按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范编写。

---

## 2026-10-06

### 变更

- ⚡ **`Smart` 收敛为单组** —— 原 `MAX`（倍率筛选）/ `Fallback`（逐级回退）/ `Smart`
  （全池 url-test）三组合一，改为一个 `fallback`，成员由脚本按节点名里的倍率
  升序排列（`0.01` → `0.1` → `0.5` → 正常）。倍率判据沿用姊妹仓的
  `(?<!\d.)0\.\d*[1-9]`，`0.1倍` / `0.1倍率` / `0.1x` / `0.5` 均可识别，
  `香港 01`、`1.5GB` 不误伤。同时取消 `hidden`，显示在 `Proxy` 之后。
- 🏷 **`Anthropic` 组更名 `Claude`**（对齐姊妹仓命名），`RULE-SET,anthropic` 指向同步更新。
- 🗑 **删除 `Select` 分流组** 与 **`Final` 兜底组**（`MATCH` 改为直指 `Proxy`）。
- 🖼 **图标同步姊妹仓** —— 更新 4 个过时图标（`Twitter` / `YouTubeMusic` /
  `claude-color` / `openai`），新增 `Twitter-old.png`。

### 修复

- 🍎 **`Apple Update` 首选改为 `DIRECT`** 并移除 `PASS` —— 此前顺序为
  `REJECT, PASS, DIRECT`（等于默认拒绝，系统更新下不动），现为 `DIRECT, REJECT`。
- 🎵 **`YouTube Music` 首选改为 `United States`** —— 与姊妹仓及 `Spotify` 同口径。

---

## 2026-10-07

### 新增

- 🔐 **SECURITY.md —— 安全策略** —— 声明本仓为公开模板仓，所有节点地址 /
  凭据 / 订阅 token 一律占位假值；说明「请勿提交真实配置」与漏洞报告通道
  （私密安全通告而非公开 issue）。
- 🕵 **`check_secrets.py` 门禁** —— SECURITY.md 承诺的技术支撑：扫描凭据字段
  的非占位值、订阅 token、白名单外主机与 IP、私钥头。
  判据经判别力验证：干净→绿，注入真实密码→红，还原→绿。
  （初版靠「高熵」判定会漏掉含 `@` 的密码，已改为「非占位即报警 + 值含数字」。）

### 变更

- 📝 **README 重写，对齐姊妹仓结构** —— 图标头部 + 徽章、两版 × 两形态
  （静态 / 脚本）下载表、井然有序组对比表、分流顺序、隐私至上、文件结构。
  修正：分流顺序表此前把 Apple 与内网的先后写反、且漏了 Telegram。
- ⚙️ **CI 增补 Secrets scan** —— 现共 10 步。

### 新增

- 🧠 **Smart 三档倍率分流（仅模板）** —— `Smart` 由全池 `url-test` 改为 `fallback`，
  依次回落到三个隐藏的 `url-test` 子组：`Low Mult.`（<1 倍率）· `Auto`（正常倍率）·
  `High Mult.`（>1 倍率）。子组靠 `filter` 在运行时筛节点，**不依赖生成期可见节点名** ——
  这正是 provider 订阅下脚本倍率排序做不到、而模板能做的原因。
  - 倍率判据（消歧靠「倍率单位」）：低倍率 `0.xxx`；高倍率数值 ≥1 且必须紧跟
    `倍` / `倍率` / `x` / `X` / `*`；其余视为无倍率标记。于是「巴西 09 2倍」归 High，
    而序号「09」「香港 01」不误伤。18 例回归测试全通过。
- 📦 **本仓自托管规则集**（`rules/` 目录，`format: yaml`）——
  - `emby.yaml`（4 条自用枚举域名 → Emby）
  - `apple_system.yaml`（18 条 Apple 系统域 → DIRECT，Surge 内置 `SYSTEM` 快照）
  - `AI_Domains.yaml`（272 条 AI 伴生域 → AI，与姊妹仓 `rules/AI.list` 同源）
  - 自托管而非跨项目引用姊妹仓，理由与该仓注释一致：避免跨仓依赖。
- 🤖 **ChatGPT / Gemini 策略组与规则**（对齐姊妹仓）——
  - 两组均为 `美国 → 台湾 → 日本 → 新加坡`；
  - 规则 `RULE-SET,openai,ChatGPT` / `RULE-SET,google-gemini,Gemini` 全部走 MRS。

### 变更

- 🧬 **分流版改为由脚本生成** —— `profiles/routing.yaml` 由 `override/my_clash.js`
  直接生成，与脚本覆写后的订阅逐位一致；同步重生成 `.min.yaml`。
  删除自用版 `my_clash.yaml` / `my_clash.min.yaml`，三版并列收敛为两版。
- 🔁 **节点来源改为 provider** —— 订阅由 `Airport` provider 拉取，各策略组用
  `include-all` 引入，去掉 Node-A / Node-B 占位节点。
- 🗂 **规则集命名与次序对齐姊妹仓** —— `jinx-white-guard` → `Jinx-CN`、
  `jinx-ads-delta` → `Jinx-Ads`；广告段次序改为 白名单 → `Jinx-Ads` → `AWAvenue-Ads`；
  `Emby` 移至 `YouTube` 之后、`Google` 之前。
- 📝 **自建集后缀统一** —— `.list`（Surge / Egern 惯例）→ `.txt` → 最终定为 `.yaml`
  （与本仓 Jinx 两份一致），内容相应改为 `payload` 结构。
- 🎨 **AI 组图标** —— 一度改用 `openai.png`，现改回 `grok.png`（与姊妹仓同款）。

### 修复

- 🔒 **显式关闭 IPv6** —— 顶层 `ipv6: false` + `dns.ipv6: false`。
  此前 `dns.ipv6` 为 `true` 时会返回 AAAA 记录，而本机真实 IPv6 未被 TUN 完整接管，
  双栈站点优先走 IPv6 ⇒ 出口 IP 与节点不符（表现为站点测到美国 IPv6）。
  关闭后双栈站点自动回落 IPv4，与姊妹仓处理一致。
- 🧩 **AD 组移除 `PASS`** —— 改为 `REJECT` / `DIRECT` 二选一，与姊妹仓同口径。
  `PASS` 语义为「绕过代理直连」，与拦截二选一口径不符，易误操作。
- 🌍 **Proxy 补 `Other Regions` 子节点** —— 收尾接住 5 个主流地区之外的落单节点。
- 🔎 **补齐 AI 伴生域覆盖** —— 原引用 MetaCubeX `category-ai-chat-!cn`（188 条），
  实测漏掉姊妹仓 `AI.list` 中的 93 条（两边重叠仅 178 条）。漏的主要是各家上游清单
  都不收的认证 / 遥测 / 风控基础设施域（`auth0`、`statsig`、`arkoselabs`、
  `apis.google.com`、`apple-relay` 等），伴生请求漏出 AI 组易触发风控。
- ↩️ **YTM 维持内联** —— 曾改为引用 blackmatrix7 远程集，实测该 Clash 版同样只有
  `music.youtube.com` 一条，无覆盖增益且多一次远程拉取，已换回内联写法。

### 删除

- 🗑 `Select` 分流组；`Final` 兜底组（由 `MATCH` 直指 `Proxy`）；
  `MAX` / `Fallback` 组（由 Smart 三档取代）；自用版 `my_clash` 两份配置。

---

## 2026-10-04

### 新增

- 🧬 **进阶版配置落地** —— `profiles/my_clash.yaml`（带注释）/ `profiles/my_clash.min.yaml`（纯配置），
  由自用路由器（OpenWrt + mihomo）实测配置整理而成：剥离全部私有节点后保留分流骨架，
  **23 个策略组**（含 `Smart` / `Select` 全池择优与手动选择、`MAX` 倍率筛选、5 组地区与 12 个应用组）、
  **20 份规则集**、**26 条规则**，只留 1 个订阅槽位 `Airport`（换 `url` 即用，无内联节点）。
  与懒人版 / 分流版并列为第三类，定位是「进阶 · 自用」。

### 变更

- 🛑 **广告拦截前移到 DNS 层（进阶版）** —— 双层机制，任一单用均无效：
  - `dns.nameserver-policy` 对 `rule-set:AWAvenue-Ads` / `rule-set:jinx-ads-delta`
    返回 `rcode://success`（空回答），广告域名**在解析阶段就断掉**，连接不再建立；
  - 同一批集合**必须同时出现在 `dns.fake-ip-filter`** —— 否则 `withFakeIP` 中间件对
    A / AAAA 查询直接返回假 IP（`dns/middleware.go` 中 `withFakeIP` 先于 `withResolver`
    返回），请求永远到不了 `nameserver-policy`。此坑有社区先例：
    [Discussion #668](https://github.com/MetaCubeX/mihomo/discussions/668)；
  - 顺序约束：广告 policy 必须写在 `rule-set:private,cn` **之前**，否则先命中 `cn`；
  - 规则层 `RULE-SET,xxx,AD`（`AD` 组默认 `REJECT`）**保留为兜底** ——
    DNS 拦截覆盖不到 IP 直连、DoH / DoT 与客户端缓存命中；
  - 实测（本地内核 v1.19.32，手工构造 DNS 查询）：`ad.doubleclick.net` / `ad.qq.com` /
    `ucc.umeng.com` / `abtest-ch.snssdk.com` 均返回 `rcode=0` 且 **answer=0**；
    对照 `www.baidu.com` / `www.google.com` 正常返回 `198.18.0.x`。
- 🧩 **规则集全面转为 MRS（进阶版）** —— 17 条 `GEOSITE,xxx` / `GEOIP,xxx` 改为
  `RULE-SET,xxx`，新增 13 份 geosite `.mrs` + 4 份 geoip `.mrs` 的 provider 定义（源为
  `cdn.jsdelivr.net`，国内可直连）。⇒ `rules` 不再引用 `GEOSITE` / `GEOIP`，`GeoSite.dat`
  与 `GeoIP.dat` 不再是运行时必需。
  - 选型依据（实测而非推测）：13 个分类逐一与 Loyalsoldier `geosite.dat` 反解比对，
    条目数最大差异为 `cn` 的 340/111361（0.3%），其余多数为 0 或 ±2；
  - `jinx-ads-delta` 虽声明 `behavior: classical`，实测内容为 3740 条 `DOMAIN-SUFFIX` +
    149 条 `DOMAIN-REGEX`、**0 条 IP 规则**，故在 DNS 阶段可 100% 生效
    （内核会打印 `only matching it contain domain rule` 警告，属预期行为）。
- 📝 **`README.md` 改为三版并列** —— 标题「两全其美」→「三全其美，各取所需」，
  下载区并列懒人版 / 分流版 / 自用版三条链接；「井然有序」组对比表由两列扩为三列；
  增补「自用版」小节（双层拦截机制、全 MRS 取舍、两条必要约束）与分流顺序差异说明；
  顶部 badge 与「文件结构」表同步更新为三类配置。

### 新增

- 🔗 **JS 覆写脚本 `override/my_clash.js`** —— 对**任意订阅**做整体覆写，使其结构等同于
  `profiles/my_clash.yaml`（23 组 / 20 规则集 / 26 规则 / 双层广告拦截）。
  与静态模板的唯一机制差异：
  - 静态模板用 `use: [Airport]` 引入订阅；脚本改用 **`include-all-proxies: true`**，
    让订阅自身的 `proxies` **直接成为各组成员**，因此无需额外的订阅槽位；
  - 订阅若同时带 `proxy-providers`，脚本自动切换为 `include-all`（= proxies + providers），
    避免 provider 内节点成为孤儿；
  - 入站端口（`port` / `mixed-port`）不覆盖，交由客户端决定；`proxies` 保留。
  - 附 [`override/README.md`](override/README.md) 说明用法与实测读数。

### 变更

- ✂️ **移除 `gfw` 规则集** —— 实测确认冗余，可从规则链中删除：
  - **数据层**：`gfw`（4374 条）与 `cn`（111224 条）**零重叠** —— 完全同名 0 条，
    后缀覆盖 0 条（逐个域名回溯父级后缀比对）；
  - **行为层**：内核实机对同一 gfw 域名（`kepard.com`）分别测试两份配置 ——
    含 `gfw` 命中 `RuleSet/gfw → Proxy`，不含则落到 `Match → Final`；
    而 `Final` 组默认出口即 `Proxy`，**最终归属相同**；
  - 删除 `gfw` 同时**减少一份远程规则集的下载与匹配开销**。
  - 影响：规则 26 → 25 条，规则集 20 → 19 份（12 geosite + 4 geoip + 3 自定义）。

- 🔧 **脚本与静态模板同步优化（4 项）** —— 均先核对官方文档 / 内核源码再改：
  - 🧹 **新增 `exclude-filter` 排除「信息节点」** —— 机场订阅普遍附带
    「剩余流量 / 套餐到期 / 官网」等不可用节点，原先只靠 `filter` 排除「直连」，
    这些信息节点会进入 `Smart` / `Select` 的 `url-test` 池、污染择优结果。
    现补 `exclude-filter: 剩余|流量|到期|过期|官网|订阅|重置|续费|Traffic|Expire|GB`
    （官方文档：`exclude-filter` 作用于「引入代理集合」与「引入所有出站代理」；
    内核 `groupbase.go` 的 `GetProxies()` 中作用于最终合并后的成员列表）。
    实测：3 个信息节点全部被排除。
  - 🗑️ **规则集改为整体重建** —— 脚本原先对订阅自带的 `rule-providers` 做「合并」，
    会残留无用 provider。现改为 `config["rule-providers"] = {}` 后只写入本脚本的 20 份。
  - 🔇 **DNS 不再硬编码 `listen`** —— 原写死 `0.0.0.0:7874`，可能与客户端自身 DNS 端口
    冲突（官方默认值为空，即不监听）。现两处均不设该字段，交由客户端决定。
  - 🎨 **脚本图标 URL 提取为 `ICON` 常量** —— 23 处完整 URL 收敛为
    `const ICON = ".../Clash/main/icons/"`，纯可读性改动。
- 🔄 **顺带统一脚本与静态模板的 3 处 `filter` 差异** —— `Smart` / `Select` 的
  `filter` 补上 `DIRECT`（订阅里可能存在名为 `DIRECT` 的节点）；`HongKong` 的
  负向排除去掉 `深`（避免误伤「深港」类中转节点命名）。

### 修复

- 🖼️ **脚本中 `Anthropic` / `AI` 两个组的图标 404** —— 两处 URL 与静态模板不一致，
  实测均返回 404（面板上表现为破图）：
  - `Anthropic`：`appleanthropic.png` → `claude-color.png`
  - `AI`：`new-ChatGPT-icon-black-background-png-2600x2600.png` → `new-ChatGPT-icon-white-png-medium-size.png`

  同时逐组比对脚本与静态模板的 23 个图标，并 HEAD 实测全部 URL —— 23/23 可访问。
  ⚠️ 教训（与 2026-10-02 那次同因）：外部图标 URL 必须逐个实测，
  **404 在面板上表现为破图，内核语法校验发现不了**。
- 🖼️ **图标收归本仓库 `icons/`** —— 原先自用版从 Qure / edigitalagency / AIsouler 等**外部源**
  直链图标（3 个来源、4 处外链），与懒人版 / 分流版「统一引用姊妹仓」的约定不一致，且外部源
  随时可能失效。现改为：从姊妹仓 [Self-Configuration](https://github.com/RiverFlowsInUUU/Self-Configuration/tree/main/icons)
  同步 30 个图标到本仓 `icons/`，并补齐 3 个自用版独有的（`Emby` / `Apple` / `AppleUpdate`），
  共 33 个；`profiles/my_clash.yaml` 与 `override/my_clash.js` 的 23 处图标全部改指本仓库。
  - 顺带压缩 `AppleUpdate.png`（1254² 165 KB → 256² 29 KB）；
  - 实测脚本与静态模板 23/23 图标一致，且 URL 与本地文件逐一对上。

- 📝 **`README.md` 自用版小节增补脚本入口** —— 改为「两种用法」并列：① 静态配置
  （`profiles/my_clash.min.yaml`）② 覆写脚本（`override/my_clash.js`），
  并加一行说明二者节点来源差异（`use: [Airport]` vs `include-all-proxies`）。

### 说明

- ⚠️ `global-client-fingerprint` 已在 mihomo v1.19+ 移除（本地 `-t` 报
  `configuration is removed`），进阶版**未包含**该键，指纹请在代理条目上直接写
  `client-fingerprint`。
- ⚠️ 进阶版沿用 OpenClash 侧「源配置」的结构习惯（含 `geox-url` 段），
  独立运行时该段可整段删除。

---

## 2026-10-02

### 新增

- 🧭 **分流版配置落地** —— `profiles/routing.yaml`（带注释）/ `profiles/routing.min.yaml`（纯配置）：
  - 🧩 **24 个策略组**：`Proxy`（总入口）· `Smart`（全节点池 url-test 自动择优）·
    12 个应用组（ChatGPT / Gemini / Claude / AI / Spotify / YouTubeMusic / YouTube /
    GitHub / Google / Microsoft / Telegram / Twitter）· `WeChat` · `AD` ·
    7 个地区组（Hong Kong / USA / Japan / Taiwan / Singapore / Korea / Other Regions）· `Final`；
  - 📋 **22 条规则**，自上而下：白名单 → 广告拦截 ×2 → 内网 ×2 → AI 厂商 ×3 → AI 兜底 →
    媒体 ×3 → 开发 ×3 → 社交 ×2 → Apple 全量直连 → 微信 → 国内 → 兜底；
  - 🧬 **结构对照 Self-Configuration 仓库 routing_v4.0.2**：组分工、占位节点（Node-A → Proxy、
    Node-B → AI 末位备选）、地区组关键词、应用组默认取向逐项对齐，仅 ChatGPT / Gemini / AI
    三组默认出口刻意偏离（理由见「变更」首条）；其余差异只在 mihomo 能力边界
    （见下方「变更」）。

### 变更

- 🎯 **三个应用组的默认出口调整** —— 与蓝本对齐后仅这三处刻意偏离，其余逐组一致：
  - `ChatGPT` / `Gemini` 首项改为 `USA` —— 两家都对美区 IP 友好（蓝本原取 `Proxy` 首项 `Smart`）；
  - `AI` 首项改为 `Smart` —— 蓝本原取占位节点 `Node-B`，而它是 RFC 5737 文档段、**实际不通**，
    拿它当默认出口等于默认断网，故降为末位备选；
  - 懒人版 `lazy.yaml` 的 `AI` 组同因同改：首项由 `Node-B` 改为 `Proxy`（懒人版的自动择优组，
    等价于分流版的 `Smart`，懒人版无地区组故不以地区组打头）。
- 🌐 **懒人版规则选型升级为 GEOSITE 优先** —— `lazy.yaml` 重写，规则集由 3 份远程 + 6 条原生
  升级为「GEOSITE 优先 → MRS → 传统规则集」三级选型（与分流版同口径）：
  - 白名单 / 广告清单维持远程（Jinx 自托管 + AWAvenue 的 .mrs）；
  - AI 分流由 `GEOSITE,category-ai-chat-!cn` 承接，伴生域/宽后缀整合集收敛进数据库；
  - 规则数 9 → 11 条（补 Apple 系统服务直连 + AI 分流拆两条）。
- 🪶 **懒人版 Proxy 组改为 url-test 自动择优** —— 对齐蓝图的 smart 组语义：
  主出口按延迟自动选优，无需手动管；AI 组仍是 select 类型，默认出口指向 `Proxy`（自动择优）。
- ✈️ **占位节点协议由 vless 改为 hysteria2** —— 与 Self-Configuration 双内核的占位节点同协议
  （`password` ≙ Egern 的 `auth` ≙ Surge 的 `password`），占位节点数 1 → 2
  （Node-A 归 Proxy、Node-B 归 AI）。
- 🖼️ **策略组图标统一引用姊妹仓的 `icons/`** —— 27 处（分流 24 + 懒人 3）从
  Qure / lobe-icons 的外链改为 [Self-Configuration · icons](https://github.com/RiverFlowsInUUU/Self-Configuration/tree/main/icons)
  （29 个图标，与两仓组名一一对应）。换的三个原因：
  ① 原先外链里 `UnitedStates.png` / `WorldMap.png` 两个文件名在 Qure 目录**不存在**（实测 404，
  面板上显示破图），正确名是 `United_States.png` / `World_Map.png`；
  ② lobe-icons 没有 `grok` / `gemini-color` / `claude-color` 这类，隔壁仓现成；
  ③ 两仓图标同源，风格统一，且省掉一份外部依赖。
  ⚠️ 教训：外部图标 URL 必须逐个 HEAD 实测 —— **404 在面板上表现为破图，语法校验发现不了**。
- 📌 **`proxies` / `proxy-providers` 提到配置文件最顶部** —— 两份配置统一为
  `proxies → proxy-providers → proxy-groups → rule-providers → rules → dns → tun`：
  导入前必改的两处（占位节点、订阅地址）开箱就在第一屏，不用翻到文件末尾。
- 🧩 **12 个应用组的成员改为「分流组名」** —— ChatGPT / Gemini / Claude / AI / Spotify /
  YouTubeMusic / YouTube / GitHub / Google / Microsoft / Telegram / Twitter 去掉
  `use: [Airport]`，成员直接写 `Smart` + 7 个地区组 + `Node-A`；各组再前置自己的默认取向
  （Claude 前置 `Taiwan`、Spotify / YouTubeMusic 前置 `USA`、Google 前置 `Gemini`、
  Microsoft 前置 `DIRECT`、AI 前置 `Node-B`）。
  对齐基准是蓝本 `flatten: true` **求值后的结果**，不是 flatten 这个行为本身：蓝本面板上
  应用组的成员就是 `Proxy` 的成员表，逐组核对一致。节点只留在 `Smart` 与 7 个地区组内部。
  实测印证（测试订阅挂 3 个节点）：`YouTube.all = ["Smart","Hong Kong","USA","Singapore",
  "Taiwan","Japan","Korea","Other Regions","Node-A"]`（与 `Proxy.all` 同表），
  而 `Smart.all = ["T-Node-1","T-Node-2","T-Node-3"]`。
  ⚠️ 上一版按「摊平订阅节点」理解，把节点全塞进 12 个应用组，与蓝本对不上；
  同期还把 `include-all-proxies` 插在 `proxies:` 与列表项之间，写成非法 YAML
  （`proxies:` 空值 + 悬空的 `- Proxy`），`routing.yaml` 无法加载。本次一并改正。
- ⚠️ **两条 mihomo 能力缺口，已写进 `routing.yaml` 策略组段首**（分流版 + 懒人版同）：
  ① **没有 `smart` 组类型** —— 内核只有 `select` / `url-test` / `fallback` / `load-balance`
  四种（源码 `adapter/outboundgroup/` 下无 smart 实现），故暂用 `url-test` 近似；
  `Smart` 是沿用蓝本的**组名**，不是内核类型。
  ② **没有节点权重机制** —— `url-test` 的专属字段只有 `tolerance`（切换容差，非权重），
  `load-balance.strategy` 也只选分发算法、不带权重。蓝本那套低倍率优先
  （Surge `policy-priority` / Egern `priorities`，软加权 0.15）在 mihomo 侧无从表达，
  暂不引入 —— 唯一近似是把低倍率节点用 `filter` **硬筛**出来，那是硬过滤、行为不同。
- 🌐 **规则集换到 GeoSite.dat 原生类别，全部移除 blackmatrix7** —— Gemini / Claude /
  YouTubeMusic / WeChat 四类原先挂在 blackmatrix7 的 classical YAML 上，而该仓应用类目的
  最后更新停在 **2025-06-17**（`Surge/Anthropic` 更是 2024-02-02），已明显滞后。
  逐条解析 `geosite.dat`（1552 个类别）后改为：
  - `google-gemini`（46 条）→ `Gemini` 组；
  - `anthropic`（8 条）→ `Claude` 组；
  - YouTube Music：`geosite.dat` 确无独立类别，改用一条内联 `DOMAIN-SUFFIX,music.youtube.com`
    （它是 `youtube.com` 的子域，必须排在 `GEOSITE,youtube` 之前才不被抢走）；
  - WeChat：同样**没有独立类别**，先退到 `tencent`（683 条），随后换成远程 `.mrs`（见下条）。
  ⇒ 分流版远程规则集 **7 份 → 3 份**（`jinx-white-guard` / `jinx-ads` / `AWAvenue-Ads`）。
  ⚠️ 教训：`geosite.dat` 的类别名是**全大写**（`GOOGLE-GEMINI` / `ANTHROPIC` / `TENCENT`），
  用小写比对会把已有类别误判成「不存在」—— 这正是上一版绕道第三方的根因。
- 💬 **`WeChat` 组改用微信专属 `.mrs`（`Lanlan-WeChat`），不再用 `GEOSITE,tencent`** ——
  `MetaCubeX/meta-rules-dat` 的 `geo/geosite` 目录共 1904 个类别，逐个核过：
  `wechat` / `weixin` / `wx*` **一个都没有**；最接近的 `tencent`（682 条）是靠 `+.qq.com`
  泛化兜住微信的，微信专属域名在里头只有 10 条 —— 走它等于把 QQ / 腾讯云 / 腾讯视频
  一并拖进 `WeChat` 组。现改用 30 条纯微信域名的 `.mrs`：
  - **源**：[Lanlan13-14/Rules](https://github.com/Lanlan13-14/Rules) · `rules/Domain/WeChat.mrs`。
    横向比过 `Keviin560/Shunt_Rules`、`7ac9d42/Rules`（两家内容同源）、`ACL4SSR/ACL4SSR`
    （只有 `.list`、不提供 `.mrs`）；选 `Lanlan13-14` 是因为它被第三方配置模板引用最广；
  - **规则**：`- GEOSITE,tencent,WeChat` → `- RULE-SET,Lanlan-WeChat,WeChat`，位置不变
    （仍排在 `GEOSITE,cn` 之前，微信域名同属 `cn` 类，靠前才能先被摘出来）；
  - **实测**：`type: http` + `format: mrs` 加载后 `ruleCount = 30`、`behavior = Domain`、
    `vehicle = HTTP`；远程规则集 3 份 → **4 份**。
  ⚠️ 教训：找社区规则集别手工试三家就下「全社区没有」的结论 ——
  `gh search code "WeChat.mrs"` 一行扫出全部候选，抽样必然漏。

### 已知取舍

- ⚠️ **mihomo 无低倍率优先加权** —— Surge 的 `policy-priority` / Egern 的 `priorities` 能按节点名
  里的倍率标记给低倍率节点软加权，mihomo 的 url-test 没有对应机制。本配置选择「纯延迟择优」，
  想要低倍率优先可给对应组补 `filter` 硬筛（代价：硬过滤非软偏好，低倍率节点延迟再高也不让位）。
- ⚠️ **`WeChat` 组的语义是「腾讯」** —— `geosite.dat` 无独立 `wechat` 类，退用 `tencent`（683 条），
  因此腾讯全家桶（QQ / 腾讯视频 / 腾讯云）都会落进 `WeChat` 组。出口同为直连，扩宽无害；
  但它不再只是「微信」。

---

## 2026-09-22

### 新增

- 🎉 **仓库初始化** —— `README.md` + `LICENSE`（MIT）。定位 Clash 配置模板，交付懒人版与分流版两份配置。
- 🪶 **懒人版配置落地** —— `profiles/lazy.yaml`（带注释）/ `profiles/lazy.min.yaml`（纯配置）：
  - 🧩 **3 个策略组**：`Proxy`（主出口）· `AI`（AI 流量独立出口）· `AD`（手动开关，`REJECT` / `PASS` / `DIRECT`）；
  - 📋 **9 条规则**，自上而下：白名单 → 广告拦截 ×2 → 内网 → AI → 国内 → 兜底；
  - ✈️ `proxies` 一条 vless + reality 节点占位；`proxy-providers.Airport` 订阅槽位（含健康检查），两个策略组均以 `use: [Airport]` 引入；
  - 🔧 `.min.yaml` 由 `build_clash_lazy.py` 从带注释版剥离生成，两份解析后数据完全一致（脚本断言守着）。
- 🗓️ **更新日志** —— 本文件，自建仓起记账。
- 📘 **技术文档立项** —— 新建 `DetailsReadme/DetailsReadme.md`：防泄露三条出口的逐条推导、`dns` 段 15 键逐键说明、五个解析器键的分工、`tun` 段与 `dns-hijack` 语义、明文泄露面实测读数、已知取舍。

### 变更

- 🌐 **DNS 段改为加密解析** —— 解析器此前写 `system`（即交给操作系统 / ISP 的明文递归），现全部换成加密端点：

| 键 | 解析器 | 用途 |
|:--|:--|:--|
| 🧭 `nameserver` | `dns.cloudflare.com` · `dns.google` | 主解析器 |
| 🎯 `nameserver-policy` | `geosite:private,cn` → 国内 DoH | 按域名换解析器 |
| ✈️ `proxy-server-nameserver` | 国内 DoH | 代理节点域名 |
| 🚪 `direct-nameserver` | 国内 DoH | `DIRECT` 出站的域名 |
| 🥾 `default-nameserver` | `223.5.5.5` · `119.29.29.29` | 仅引导 DoH 端点自身的域名 |

  同时补齐 `ipv6: false` · `listen` · `prefer-h3: false` · `respect-rules: true` · `use-hosts` · `use-system-hosts: false` · `fake-ip-range` · 15 条 `fake-ip-filter`。

  - ✅ **明文泄露面实测**（本地 mihomo 内核 + 本机 DNS sink，2026-09-22）：把唯一走明文 UDP 的
    `default-nameserver` 顶到本机 sink 上跑真实解析，**明文 `UDP:53` 只出现在
    `dns.google` / `dns.cloudflare.com` 两个 DoH 端点域名上**（解析端点自身所需的引导），
    业务域名与节点域名全部走 `443` 加密端点。
  - ✅ 四个 DoH 端点按 DNS-over-HTTPS 协议实发查询，均回 `200` + `application/dns-message`。

- 📝 **README 门面化** —— 首页「防泄露原理」整节改为 **DNS 防泄漏能力清单**。README 是产品门面，只讲「得到什么」：明文 `:53` 本地接管不出网 / 本地不做真实解析 / 节点域名独立通道 / 解析器全为加密端点 / 锁死 TUN / 实测零业务域名；不讲机制推导，也不出现内核实现键。
- ✂️ **README 瘦身** —— 首页只讲「是什么」：`dns` 逐键、解析器分工、`respect-rules` 连带要求、实测推导全部下沉 `DetailsReadme`，首页只留结论与指路。
- 🔗 **README「文件结构」改为可点击跳转** —— 原先是 fenced code block 里的目录树，而 GitHub **不解析代码块内的 markdown**，那些路径一个都点不动、只能靠手翻。改为表格（图标 / 路径 / 说明），路径列写成相对链接，点一下直达对应目录或文件。未创建的目录（`icons/`、`docs/`、`skill/`）**不装链接** —— 装了就是 404，改用行内代码并在表下给一句图例。三仓同步同一版式。
- 🧭 **首页下沉规则集信息，新开专题承接** —— 首页原有两处规则集层面的内容：「📋 规则顺序」（表里是 `jinx-white-guard` · `jinx-ads` · `AWAvenue-Ads` · `GEOIP,cn` 这类规则集名与规则类型）与「📚 规则来源」整节（来源仓库清单）。规则集属**实现侧**，读者只关心「能实现怎样的分流」，于是：
  - 📋 「规则顺序」改为 **「分流顺序」** —— 列「匹配什么 → 去向」（白名单域名 / 广告域名 / 内网 / AI 服务 / 国内 / 其余全部），首页不再出现任何规则集文件名；
  - 📚 「规则来源」整节撤下首页；
  - 🆕 新开 [`docs/01-规则集与来源.md`](docs/01-规则集与来源.md) —— 3 份规则集的格式 / 行为 / 去向 / 来源、6 条原生规则、刷新与落盘机制（`path` 先落盘再解析、`interval: 86400`、`.mrs` 格式取舍）、逐条匹配顺序、五条排序约束、素材与许可；
  - 🔗 首页只在「文件结构」与「更多文档」里各留一个入口；
  - ✅ 首页外链随之收敛为**徽章 + 本仓地址**，第三方来源链接全部随之下沉（新增断言守着）。
- 🚧 **顶部「部分发布」口径更新** —— `docs/` 已有首篇专题，不再列为「准备中」。

### 修复

- ✂️ **README 去掉三处跨仓比对 / 跨仓导流** —— 开头「与 Surge · Egern 同构」整句、分流版「组序与 Egern 对齐」、末尾导流两个姊妹仓的「更多文档」整节。
- ✏️ **`fake-ip-filter` 注释写准通配语义** —— 实测（`+.example.com` 命中 `example.com` 本域；`*.lan` 不命中 `a.b.lan`）后改为「`+.` 含本域与任意层子域；`*` / `*.` 只匹配一层」，此前只笼统写「含子域」。
