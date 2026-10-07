# 三内核差异对照

> 本仓库把 Surge、Egern 与 clash-mihomo 三套模板放到一处。**分组意图和规则骨架可以共用，配置语法与执行阶段不能照抄。**
> 这一页是给“想把一侧的改动移植到另外两侧”的人看的：哪些能直接照搬、哪些照搬就是错的。
>
> 本页结论按当前文件逐条核对：`surge/profiles/routing.conf`、`egern/profiles/routing.yaml`、
> `clash/profiles/routing.yaml` 与 `clash/override/my_clash.js`。计数只算启用项，不算注释：
> Surge **23 组 / 26 条规则**，Egern **23 组 / 26 条规则**，mihomo 静态分流版
> **25 组 / 27 条规则 / 25 份 rule-provider**；mihomo 覆写脚本实际生成
> **<!-- auto:group-count -->23<!-- /auto:group-count --> 组 / <!-- auto:rule-count -->26<!-- /auto:rule-count --> 条规则 / 25 份 rule-provider**。

## 1 · 语法与机制映射

| 语义 | Surge | Egern | clash-mihomo | 移植时注意 |
|:-----|:------|:------|:-------------|:-----------|
| 配置载体 | `.conf`，INI 分段 | `.yaml` | 静态 `.yaml`；另有 `.js` 覆写脚本 | mihomo 的脚本是第二种交付形态，不是可粘进 YAML 的配置片段 |
| 组结构 | 23 组 | 23 组，名称与顺序和 Surge 逐位相同 | 静态 25 组；覆写脚本 22 组 | 三侧共有 22 个业务/地区组；Surge/Egern 多 `Airport`，mihomo 静态多三个倍率子组 |
| 策略组类型 | `select` / `smart` | `select` / `smart` / `external` | `select` / `fallback` / `url-test`；内核还支持 `load-balance` | mihomo 没有 `smart`，不能只换类型名 |
| 订阅源 | `Airport = select, policy-path=…`，`hidden=true` | `Airport` 为 `external`，`urls` + `interval` + `hidden` | 静态 `routing.yaml` **已声明** `proxy-providers.Airport`（2026-10-07 起）；覆写脚本保留输入订阅的 `proxies` / `proxy-providers` | `policy-path`、`external.urls`、`proxy-providers/use/include-all*` 不是同一种对象，不能互抄 |
| 组展开 / 节点入组 | `include-other-group="X"`；显式成员不受 `policy-regex-filter` 影响 | `policies: [X]` + `flatten: true`；地区组再用 `filter` | 没有 `flatten`；用 `use`、`include-all`、`include-all-proxies` 或把组名写进 `proxies` | `flatten: true` 是 Egern 特有；mihomo 的 `include-all-proxies` 只收内联节点，`include-all` 才连 provider 一起收 |
| 组内筛选 | `policy-regex-filter` | `filter` | `filter` + `exclude-filter` | 三侧当前地区正则并不相同；只能移植“按地区筛”的意图，不能假定逐字等价 |
| 倍率 / 权重 | `policy-priority="正则:0.15"`，Smart 与 6 个地区组都有 | `priorities: {正则: 0.15}`，Smart 与 6 个地区组都有 | **无权重键**；只能用 `fallback` + `filter` / 节点排序模拟 | 0.15 在 Surge/Egern 是软权重；mihomo 的分档回落不是同一算法 |
| 规则顺序 | 26 条，first-match-wins | 26 条，与 Surge 逐位同义 | 27 条，保留“白名单 → 广告 → 系统/内网 → AI/应用 → 国内 → IP → 兜底”的骨架，但不是逐位同构 | mihomo 多 `geoip-google` / `geoip-telegram`，少独立 `Claude.list`，且 Telegram 位置不同，见 §3 |
| 远程规则集 | URL 直接写在 `RULE-SET,<URL>,<策略>` | URL 写在 `rule_set.match` | 先在 `rule-providers` 声明名字、`format`、`behavior`、`path`、`interval`，规则再按名字引用 | 把 `.list` URL 直接塞进 mihomo 的 `RULE-SET` 名字位是错的 |
| 规则集格式 | Surge `.list` / `.txt`，另有内置 `LAN` / `SYSTEM` | 可直接消费 Surge `.list` / `.txt` | 当前 25 份中：20 份 `.mrs`（16 个 `domain` + 4 个 `ipcidr`），5 份 `yaml` + `classical` | mihomo 的 `format` 与 `behavior` 必须和文件内容成对 |
| 刷新间隔 | `update-interval=604800` | `update_interval: 604800` | `interval: 86400` | 当前就是一周对一天；不要为了“数值统一”抹掉各侧既有节奏 |
| 本地 / 引导 DNS | `dns-server` 4 个 IP | `dns.bootstrap` 2 个 IP；`dns.upstreams` 4 个加密端点 | `default-nameserver` 2 个 IP；另分 direct / proxy-server / nameserver / fallback | 键名相似不代表调用阶段相同 |
| 加密与分流 DNS | `encrypted-dns-server` 3 个端点 | `upstreams.Domestic-DNS` + `forward` + `proxy_nameservers` | `direct-nameserver`、`proxy-server-nameserver`、`nameserver`、`fallback`、`nameserver-policy` | Egern 的 `proxy_nameservers` 会绕过 `forward`；mihomo 在 `respect-rules: true` 下需要 `proxy-server-nameserver` |
| 接管明文 53 | `hijack-dns` 枚举 6 个地址 | `hijack_dns: ['*']` | 仅静态 profile 的 `tun.dns-hijack: [any:53]`；当前只接管 UDP:53 | 覆写脚本不应写 `tun`；客户端自己管理 TUN |
| IPv6 | `ipv6 = false` + `ipv6-vif = disable` | `ipv6: false` | 顶层 `ipv6: false` + `dns.ipv6: false` | 目标可照搬为“关闭 IPv6”，键不能照搬；mihomo 少关一处都不完整 |
| 广告拦截 | 两条规则指向字面量 `REJECT`，并带 `pre-matching,extended-matching` | 规则层指向 `AD`；DNS 层 `dns.forward.value: reject` | 规则层指向 `AD`；DNS 层同时要求 `nameserver-policy: rcode://success` 与 `fake-ip-filter` | 三侧都在 DNS 前后设防，但触发链完全不同 |
| `no-resolve` | 规则行尾；当前用于 `LAN`、6 条含 IP 的应用集与 `GEOIP,CN` | `no_resolve: true` 只写在 `geoip`；写在 `rule_set` 上不生效 | 规则行尾；当前 4 个 `geoip-*` provider 引用都带 | 可移植的是“IP 规则不要为了匹配而先解析域名”的原则，不是字段落点 |
| 默认出口 | `FINAL,Proxy,dns-failed` | `default.policy: Proxy` | `MATCH,Proxy` | 只有 Surge 有 `dns-failed` 参数 |

mihomo 各键的逐键行为与边界，继续看 [`profile-anatomy.md`](../clash/profile-anatomy.md)；
静态 profile 的 DNS / TUN 加固理由见 [`hardening-template.md`](../clash/hardening-template.md)。

## 2 · 分组：22 个共同语义，三种实现

Surge 与 Egern 各 23 组，名称与顺序逐位相同：

```text
<!-- auto:group-list -->
Proxy · Smart · ChatGPT · Gemini · Claude · AI · YouTube · Emby · Google
Telegram · YouTube Music · Spotify · Twitter · Airport · Microsoft · Apple Update
AD · Hong Kong · Taiwan · Japan · Singapore · United States · Other Regions
<!-- /auto:group-list -->
```

mihomo 静态分流版没有 `Airport` 组，但有三个额外隐藏倍率组，所以是 25 组：

```text
Proxy · Smart · Low Mult. · Auto · High Mult. · ChatGPT · Gemini · Claude · AI
YouTube · Emby · Google · Telegram · YouTube Music · Spotify · Twitter · Microsoft
Apple Update · AD · Hong Kong · Taiwan · Japan · Singapore · United States · Other Regions
```

三侧真正共有的是除 `Airport` 外的 **22 个组名**。应用组的主要成员顺序也已对齐：
例如 `ChatGPT` 都是“美 → 台 → 日 → 新”，`Claude` 都是“台 → 日 → 新 → 美”，
`Microsoft` 都是 `DIRECT → Proxy`，`Apple Update` 都是 `DIRECT → REJECT`。
这类**产品取向**可以三侧同步改；组类型、节点展开方式和筛选键必须各写各的。

### 2.1 Smart 与倍率不是同一个实现

- **Surge**：`smart` 直接展开 `Airport`，用 `policy-priority` 给低倍率节点乘 0.15。
- **Egern**：`smart` + `policies: [Airport]` + `flatten: true`，用 `priorities` 表达同一个 0.15 权重。
- **mihomo**：没有权重机制。静态文件声明 `Low Mult.` / `Auto` / `High Mult.` 三个
  `url-test` 组，以 `filter` 分档，再由 `fallback` 按档回落；覆写脚本则在执行时用
  `sortedByRate()` 排可见的内联节点，`Smart` 仍是 `fallback`。

⚠️ **按真实配置核对出的当前状态**：`clash/profiles/routing.yaml` 虽然声明了三个隐藏分档组，
但 `Smart.proxies` 当前实际是单独的 `DIRECT`，并未引用这三个组；同一文件也没有
`proxy-providers`，末尾却是空的 `proxies: []`。这与文件头“替换
`proxy-providers.Airport.url`”的说明不一致。这里不替配置找理由：移植时应按“当前静态版没有可用订阅源、
三档没有接到 Smart”处理。**【2026-10-07 更新】此段已过时：静态 `routing.yaml` 现已声明
`proxy-providers.Airport`，且 Smart 三档已接入。移植时按“有可用订阅源”处理。**
它从传入订阅保留节点与 provider。

### 2.2 地区组不能只复制正则

Surge/Egern 的 5 个命名地区组使用同一套长关键词表，并在 `Other Regions` 里维护对应负向集合；
mihomo 当前使用另一套较短正则。更关键的是节点入口不同：

- Surge：`include-other-group="Airport"`；
- Egern：`policies: [Airport]` + `flatten: true`；
- mihomo 静态：地区组是 `include-all: true`（2026-10-07 起；此前为 `include-all-proxies`）；
- mihomo 覆写：检测到输入有 provider 时用 `include-all`，否则用 `include-all-proxies`。

因此，“新增一个地区关键词”可以三侧同步做；“复制一整行地区组”一定不行。

## 3 · 规则：共同骨架，不是假装 27 条逐位相同

Surge 与 Egern 的 26 条规则逐位同义；mihomo 有 27 条。当前分流版的真实顺序如下：

| 语义 | Surge | Egern | clash-mihomo |
|:-----|:------|:------|:-------------|
| 广告白名单 | ① `surge-direct.list` → `DIRECT` | ① 同源 `.list` → `DIRECT` | ① `Jinx-CN`（yaml/classical）→ `DIRECT` |
| 两条广告 | ②③ `.list` → 字面量 `REJECT` + pre-matching | ②③ `.list` → `AD` | ②③ `Jinx-Ads` / `AWAvenue-Ads` → `AD` |
| Apple 更新 | ④ `SystemOTA.list` → `Apple Update` | ④ 同左 | ④ `apple-update.mrs` → `Apple Update` |
| 系统域 | ⑤ 内置 `SYSTEM` → `DIRECT` | ⑤ `apple_system.list` → `DIRECT` | ⑤ `apple-system.yaml` → `DIRECT` |
| 内网 | ⑥ 内置 `LAN`；⑦ `private.txt` | ⑥ `Lan.list`；⑦ `private.txt` | ⑥ `geoip-private.mrs`；⑦ `private.mrs` |
| AI 专属 | ⑧ OpenAI；⑨ Gemini；⑩ Anthropic；⑪ Claude | ⑧–⑪ 同左 | ⑧ openai；⑨ google-gemini；⑩ anthropic；**无独立 Claude 集** |
| AI 兜底 | ⑫ Repcz `AI.list`；⑬ 本仓 `AI.list` | ⑫⑬ 同左 | ⑪ `category-ai-chat-!cn.mrs`；⑫ 本仓 `AI_Domains.yaml` |
| YouTube Music | ⑭ 远程 `YouTubeMusic.list` | ⑭ 同左 | ⑬ 内联 `DOMAIN-SUFFIX,music.youtube.com` |
| GitHub / YouTube / Emby / Google | ⑮–⑱ | ⑮–⑱ | ⑭–⑰ |
| Telegram / Spotify / Twitter / Microsoft | ⑲–㉒，Telegram 在前 | ⑲–㉒，同左 | ⑱ Spotify；⑲ Twitter；⑳ Microsoft；Telegram 下移到㉒ |
| Apple | ㉓ `apple.txt` | ㉓ 同左 | ㉑ `apple-cn.mrs` |
| 应用 IP 补充 | 已合在部分 Surge `.list` 中 | 由清单与 Egern 能力处理 | ㉓ `geoip-google`；㉔ `geoip-telegram`，均带 `no-resolve` |
| 国内与兜底 | ㉔ `direct.txt`；㉕ `GEOIP,CN`；㉖ `FINAL` | ㉔ `direct.txt`；㉕ `geoip`；㉖ `default` | ㉕ `cn.mrs`；㉖ `geoip-cn.mrs`；㉗ `MATCH` |

三侧都必须保留的**顺序命题**是：白名单先于广告、专属 AI 先于通用 AI、应用规则先于国内兜底、
域名规则先于 IP 规则、最终兜底最后。不能从“顺序命题一致”推导出“规则数量和 URL 必须一致”。

三处尤其不是疏漏：

1. Surge 有内置 `LAN` / `SYSTEM`；Egern 与 mihomo 分别用远程清单或自托管快照补位。
2. Surge/Egern 用 Surge `.list` 体系；mihomo 优先用 MetaCubeX `.mrs`，只把 5 份清单留作 YAML。
3. mihomo 把 Google / Telegram 的 IP 兜底拆成独立 `ipcidr` provider，因此比另外两侧多出规则位。

完整规则集来源可与 [`rulesets.md`](rulesets.md) 交叉看；但该页仍以 Surge/Egern 为主，
mihomo 的实际值应以本页和 [`profile-anatomy.md`](../clash/profile-anatomy.md) 为准。

## 4 · 移植边界：什么能照搬，什么照搬就是错

### 4.1 可以三侧同步的，是“意图”

以下改动适合一次设计、三侧落地：

1. **业务组名、默认取向和成员顺序**：例如把某服务默认出口从 `Smart` 改成 `United States`，
   三侧都应改；但仍分别写 INI、Egern YAML、mihomo YAML/JS。
2. **规则排序约束**：新增专属规则时放在通用规则之前；新增国内兜底不能越过应用规则；
   IP 规则放在域名规则之后。
3. **共享图标与三份自托管规则真源**：改 `icons/` 的同一路径可供三侧引用；改
   `rules/*.list` 后生成 mihomo YAML，见 §8。
4. **安全目标**：关闭 IPv6、接管明文 DNS、加密上游、广告在解析阶段拒答、IP 规则不触发额外解析。
   这些目标一致，但每个目标都有三种落点。
5. **共同业务规则的策略去向**：如 GitHub → `Proxy`、Apple 更新 → `Apple Update`、系统域 → `DIRECT`。
   规则集来源可以不同，最终策略应同步复核。

### 4.2 下列写法照搬就是错

| 想移植的改动 | 错误照搬 | 实际后果 | 正确做法 |
|:-------------|:---------|:---------|:---------|
| Surge 解析阶段广告拦截 | 把 `pre-matching,extended-matching` 原样搬到 Egern / mihomo，或只把规则改成 `AD` | 两侧没有同名参数；mihomo 在 fake-IP 路径下甚至可能先返回假 IP，DNS 拒答根本走不到 | Egern 写 `dns.forward.value: reject`；mihomo 同时写 `nameserver-policy: rcode://success` 与同集 `fake-ip-filter`，规则层再指 `AD` |
| Egern 节点展开 | 把 `flatten: true` 搬到 mihomo | mihomo 无对应键；不会得到“展开 provider 节点”的效果 | 静态配置按来源选 `use` / `include-all` / `include-all-proxies`；覆写脚本先判断输入有没有 provider |
| 倍率偏好 | 把 Surge `policy-priority` 或 Egern `priorities` 政名后塞给 mihomo | mihomo 不支持节点权重；未知键不能产生 0.15 软偏好 | 用 `url-test` + `filter` 分档，再由 `fallback` 按档回落；脚本只能对执行时可见节点排序。当前静态接线异常见 §2.1 |
| mihomo TUN | 把静态 profile 的 `tun` 段写进 `my_clash.js` | 覆写脚本会越过客户端的 TUN 管理，可能与 Mihomo Party / Clash Verge 设置冲突 | `tun` 只属于 `profiles/*.yaml`；`override/*.js` 不生成它 |
| 规则集引用 | 把 Surge 的 `RULE-SET,https://…list,...` 原样搬进 mihomo | mihomo 的规则位需要 provider **名字**，不是下载 URL；同时缺 `format/behavior/path` | 先声明 `rule-providers`，再 `RULE-SET,<name>,<policy>` |
| `no-resolve` | 把 Surge 的规则尾参数改成 Egern `rule_set.no_resolve: true` | Egern 对 `rule_set` 不执行该字段，防解析形同虚设 | Egern 只在 `geoip/ip_cidr/ip_cidr6/asn` 用 `no_resolve`，远程集靠条目级语义；mihomo 的 `ipcidr` provider 引用可带行尾 `no-resolve` |
| IPv6 关闭 | 只复制一个 `ipv6: false` 到 mihomo | 只关顶层或只关 DNS 都不完整，AAAA 或真实 IPv6 通路仍可能存在 | mihomo 同时关顶层与 `dns.ipv6`；Surge 关 `ipv6` + `ipv6-vif`；Egern 关顶层 `ipv6` |
| 订阅入口 | 把 Surge `Airport` 当组名写进 mihomo `proxies` | `Airport` 在 mihomo 设计里应是 provider 名；未声明时就是悬空引用 | 静态声明 `proxy-providers.Airport` 并用 `use/include-all`；脚本沿用传入订阅。段**已存在**（2026-10-07） |
| DNS 路由 | 把 Egern `proxy_nameservers` 当成 mihomo `proxy-server-nameserver` 的纯改名 | Egern 的键会跳过 `forward`；mihomo 的键负责节点域名解析，并与 `respect-rules` 有约束，执行链不同 | 按“引导 / 直连 / 节点 / 主解析 / 回退”五个角色逐项重配 |
| 默认规则 | 把 `FINAL,Proxy,dns-failed` 改个大小写放进另外两侧 | Egern / mihomo 不认 Surge 的 `dns-failed` 语义 | Egern 用 `default.policy`；mihomo 用 `MATCH` |
| 规则禁用 | 把 Egern 的 `disabled: true` 搬到 Surge | Surge `RULE-SET` 没有该字段；整行仍可能无法加载 | 为保持位数一致，本仓两侧都把不用的 `Proxy.list` 注释掉；mihomo 则删除对应 rules 项与无用 provider |

> 最重要的判断法：先问“这个改动发生在**解析阶段、规则阶段、节点展开阶段还是客户端运行层**”，
> 再找目标内核的对应机制。只按相似键名替换，通常就是错的。

`no-resolve` 的三侧落点另见 [`no-resolve-pairing.md`](no-resolve-pairing.md)。

## 5 · 懒人版：同为 11 条规则，不代表可以复制文件

当前实配计数：

| | Surge `lazy.conf` | Egern `lazy.yaml` | mihomo `lazy.yaml` / `my_clash_lazy.js` |
|:--|:------------------|:------------------|:-----------------------------------------|
| 分组 | 4：`Airport` / `Proxy` / `AI` / `AD` | 4：同左 | 3：`Proxy` / `AI` / `AD`；没有 `Airport` 组 |
| 规则 | 11 | 11 | 11 |
| 规则集载体 | URL 内联 `.list` | `rule_set.match` 指向 `.list` | 10 份 rule-provider；规则另有最终 `MATCH` |
| 广告解析阶段 | `pre-matching REJECT` | `dns.forward.value: reject` | `nameserver-policy` + `fake-ip-filter` |
| 系统 / 内网 | 内置 `SYSTEM` + `LAN` + `private.txt` | `apple_system.list` + `Lan.list` + `private.txt` | `apple-system.yaml` + `geoip-private.mrs` + `private.mrs` |
| 默认出口 | `FINAL,Proxy,dns-failed` | `default.policy: Proxy` | `MATCH,Proxy` |
| TUN | 由 Surge 自身配置模型处理 | 由 Egern 自身配置模型处理 | 静态 YAML 有 `tun`；覆写脚本没有，也不应有 |

三侧懒人版的**语义骨架**已经对齐为：广告白名单 → 广告 ×2 → 系统 → 内网 ×2 → AI ×2 → 国内域名 → 国内 IP → 兜底。
仍然只能按语义移植，不能复制规则行。mihomo 静态懒人版也存在“头注要求替换
`proxy-providers.Airport.url`”的对照 —— 该段**现已存在**，不再是待确认项。

## 6 · 版本保留策略

- 三侧 `profiles/` 顶层都保留固定名四件：`routing` / `lazy`，各有带注释版与 `.min` 版；订阅地址不随版本改名。
- Surge / Egern 的现役文件以 `#! version=` 标当前版本，并把历史成对放进 `profiles/config_old/`。
- mihomo 静态 profile 由 `skill/scripts/clash/build_profiles.py` 生成，**现已带 `#! version=` 头注**（2026-10-07 补），
  并按版本存进 `clash/profiles/config_old/`；另有两个覆写脚本。
  **不要把 Surge/Egern 的头注版本与归档约定机械搬到 mihomo。**
- `.min` 的含义始终是“同一配置去注释”，不是精简功能；改完必须对拍。

## 7 · 脚本与测试

| 目的 | Surge | Egern | clash-mihomo |
|:-----|:------|:------|:-------------|
| DNS 判据 | `check_surge_dns.py` | `check_egern_dns.py` + `audit_dns_forward.py` | `skill/tests/clash/check_structure.py` 检查 DNS、IPv6、广告双条件与静态 TUN |
| 地区组 | `audit_region_filters.py` | `audit_region_filters.py` | 当前无同名专用脚本；结构与脚本同步由 clash 门禁检查 |
| 路由覆盖 | `audit_routing_coverage.py` | `audit_routing_coverage.py` | `check_structure.py` 检查引用与排序，`check_script_sync.py` 对拍静态版 / 覆写版 |
| 规则集内容 | `audit_ruleset_content.py` | `audit_ruleset_noresolve.py` | `check_remote_urls.py`；共享 YAML 由 `build_rules.py --check` 对拍真源 |
| `.min` 对拍 | 共享 `skill/tests/check_min_pair.py` | 同左 | `skill/tests/clash/check_min_pair.py` |
| 总入口 | `python skill/tests/verify_all.py` | 同左 | 同一总入口会继续执行 mihomo 专属门禁 |
| 链接门禁 | `python skill/tests/check_links.py` | 同左 | 同左 |

三侧测试不能合成一个“万能解析器”：相同目标背后的语法、默认值和失败方式不同。
维护入口与命令总表见 [`SKILL.md`](../../SKILL.md)。

## 8 · 合并后真正共享的东西

### 8.1 `icons/`

根目录当前有 **38 个图标文件（37 PNG + 1 SVG）**。三侧配置都引用同一个
`https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/…` 基址；覆写脚本也只定义这一份 `ICON`。

因此换图标时可以直接三侧共用同一路径。需要同步复核的是：组名是否仍指向正确文件、目标客户端是否支持该文件格式，
而不是再复制三份图片。

### 8.2 `rules/`：`.list` 是真源，`.yaml` 是生成物

当前共享清单为三对文件：

| 唯一真源 | 条目数 | mihomo 生成物 | 三侧用途 |
|:---------|------:|:---------------|:---------|
| `rules/AI.list` | 272 | `rules/AI_Domains.yaml` | Surge/Egern 直接引用 `.list`；mihomo 引用 yaml/classical |
| `rules/apple_system.list` | 18 | `rules/apple_system.yaml` | Egern 补 Surge 内置 `SYSTEM`；mihomo 用 yaml；Surge 直接用内置集 |
| `rules/emby.list` | 4 | `rules/emby.yaml` | Surge/Egern 直接引用 `.list`；mihomo 引用 yaml/classical |

生成链只有一条：

```bash
# 只改 rules/*.list，然后生成 mihomo payload
python skill/scripts/clash/build_rules.py

# CI / 本地核对生成物是否过期
python skill/scripts/clash/build_rules.py --check
```

`build_rules.py` 会去掉空行与注释，把每条 Surge 规则原样包进 mihomo 的 `payload:`；
当前对拍结果为 4 / 18 / 272 条全部一致。**不要手工编辑 `rules/*.yaml`。**

这里的“共享”不等于三内核直接读取同一种文件：Surge/Egern 消费 `.list`，mihomo 消费生成的 `.yaml`；
共享的是同一份内容真源。mihomo 其余 **20 份 `.mrs` + 5 份 YAML** 仍由自己的 `rule-providers` 管理。

## 9 · 已知单侧独有、不可移植项

| 只在哪侧 | 项 | 为什么不能移植 |
|:---------|:---|:---------------|
| Surge | `[SSID Setting]` 的 `suspend=true` | 是整机网络级暂停；Egern 的 `ssid` 条件规则和 mihomo 路由规则都只是选路，不等于暂停 |
| Surge | `pre-matching` / `extended-matching` | 是 Surge 的提前求值阶段；另外两侧只能用各自 DNS 拒答链实现目标 |
| Surge | 内置 `LAN` / `SYSTEM` | Egern/mihomo 没有同一内置集合，只能用远程集或本仓快照补位 |
| Surge | `FINAL,...,dns-failed` | `dns-failed` 没有另外两侧的同名参数 |
| Surge | `[Host]` 与 `[URL Rewrite]` 当前两条 302 | 本仓另外两份分流配置没有对应段；若真要移植，应按客户端能力另设计，不能塞进 rules |
| Egern | `flatten: true` | 是 Egern 的嵌套组展开键 |
| Egern | `dns.forward` 与 `proxy_nameservers` 绕行关系 | 是 Egern 自己的 DNS 执行链；mihomo 的 `nameserver-policy` 不是字段改名 |
| Egern | `vif_only`、`real_ip_domains`、`block_ips` | 都是 Egern 顶层 / DNS 模型的专有落点 |
| mihomo 静态 profile | `tun`、`dns-hijack`、`strict-route` | 静态导入需要自己收口；覆写脚本也不应继承这段 |
| mihomo | `rule-providers.format/behavior/path` 与 `.mrs` | Surge/Egern 的 URL 内联规则没有这层声明 |
| mihomo | `fake-ip-range`、`nameserver-policy`、`fake-ip-filter` 双条件 | 广告空回答必须绕开 fake-IP 快速返回；另外两侧没有同一中间件链 |
| mihomo | `.js` 覆写交付形态 | 脚本整体替换 groups/providers/rules/dns，同时保留输入节点；Surge/Egern 没有对应物 |
| mihomo 静态分流版 | `Low Mult.` / `Auto` / `High Mult.` 三个隐藏组 | 是为了模拟没有原生权重的限制；不能反向移植去替代 Surge/Egern 的权重键 |

还要保留三项**有意不统一**的差异：

1. **DNS 端点写法**：Surge 的 3 个加密端点中有 2 个主机名；Egern 的 4 个 upstream 全为 IP 字面量；
   mihomo 的主 `nameserver` / `fallback` 用 IP 字面量，但 direct / proxy-server 端点仍是主机名。
   不能拿任一侧的“全 IP”或“保留主机名”当三侧通用硬指标。
2. **刷新周期**：Surge/Egern 规则集当前统一 604800 秒；mihomo provider 是 86400 秒。
3. **静态与覆写职责**：mihomo 静态 YAML 自带 TUN，覆写 JS 交给客户端；这不是漏项。

最后，`my_clash.js` 头注写“22 组 / 25 份规则集 / 27 条规则”，与脚本实际执行结果一致
**22 / 25 / 27**；静态 `routing.yaml` 的头注数字 **25 / 25 / 27** 与实际一致，但订阅入口与 Smart 接线存在
§2.1 所述不一致。这些都应在后续修配置或生成器时处理，**不能在移植文档里替真实配置补写不存在的行为**。

---

相关：[`rulesets.md`](rulesets.md) · [`no-resolve-pairing.md`](no-resolve-pairing.md) ·
[`profile-anatomy.md`](../clash/profile-anatomy.md) · [`hardening-template.md`](../clash/hardening-template.md) ·
[`SKILL.md`](../../SKILL.md)
