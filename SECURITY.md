# 🔐 安全策略

本仓是公开的三内核配置模板仓：`surge/`、`egern/` 与 `clash/`（mihomo，另含
`clash/override/` 覆写脚本）并列维护，共用 `icons/` 的 40 个图标 PNG + 1 个 SVG与 `rules/` 资产。
`rules/*.list` 是共享规则的唯一真源；派生格式不得反向成为维护入口。

安全纪律对 **Surge / Egern / mihomo** 同等生效：模板只能携带假节点、假凭据与假订阅
信息，所有待替换值统一写成 `REPLACE_WITH_YOUR_*`；订阅域名 `sub.example.com` 也是占位，
不是可用服务。

## 请不要做的事

- **不要提交真实配置。** Surge / Egern / mihomo 的节点地址、用户名、密码、UUID、密钥、
  SNI、订阅 token 等必须是假值；准备提交前先恢复为 `REPLACE_WITH_YOUR_*` 或文档保留地址。
- **不要把真实值推上公开仓库。** 删除最新版本并不能删除旧 commit；彻底清理需要改写 Git
  历史并强制推送，仍无法收回已被拉取的 clone、fork、缓存或日志。因此一旦泄露，应先撤销、
  轮换凭据和订阅 token，再处理历史，不能把“删文件”当作回收。
- **不要破坏仓库自洽性。** Surge / Egern / mihomo 自有的图标、共享规则与派生资产必须引用
  本仓，不得借用其他仓库中同名的在线资源；[`check_selfcontained.py`](skill/tests/check_selfcontained.py)
  会对此判负。明确列出的第三方规则上游不属于本仓自有资产，按下节单独管理。
- **不要在公开 issue、评论、日志或截图中留下敏感信息。** 订阅 token、节点凭据、真实节点地址、
  内网地址、设备名与可识别请求参数都应先打码；无法确认是否敏感时，按敏感信息处理。

## 报告漏洞

发现下列问题时，请使用 GitHub 的**私密安全通告**（仓库页 Security → Report a
vulnerability），不要公开发 issue：

- Surge / Egern / mihomo 任一配置、脚本、文档或历史中出现真实地址、凭据或订阅 token；
- [`check_secrets.py`](skill/tests/check_secrets.py)、
  [`check_selfcontained.py`](skill/tests/check_selfcontained.py) 或任一内核判据存在“结果全绿但实际未检查”
  的路径；
- 第三方规则集 URL 被替换为不可控镜像、内容疑似被投毒，或规则更新导致泄露防线失效。

一般性功能问题、文档笔误与不含敏感信息的配置建议可走普通 issue。报告中仍须使用假值，
必要样本请最小化并打码。

## 第三方规则集与供应链

三内核都会在运行时读取远程规则，维护活跃或社区使用广泛不等于内容天然可信：

| 内核 | 当前主要格式与上游 | 主要风险 |
|:--|:--|:--|
| Surge | blackmatrix7、Jinx、TG-Twilight、Loyalsoldier、Repcz 的 `.list` / `.txt` | 滚动分支可无预警改变匹配范围、顺序或 IP 条目；文本可审阅，但仍须核对来源、格式与策略归属。 |
| Egern | blackmatrix7、Jinx、TG-Twilight、Loyalsoldier、Repcz 的 Surge 兼容 `.list` / `.txt` | 同一上游在 Egern 的加载与 DNS 语义可能不同；可下载不等于规则有效，也不等于不会触发额外解析。 |
| mihomo | 主要使用 MetaCubeX 的 `.mrs`，并使用 Jinx 与 TG-Twilight 的 mihomo 规则集 | `.mrs` 是预编译格式，肉眼审阅能力弱于文本；发布账号、分发 CDN、格式或内容变化都可能静默改变分流与 DNS 行为。 |

新增或替换上游时，必须使用上游项目的规范地址，复核维护状态、许可证、发布链路与规则语义；
不得仅因 URL 可访问就认定可信。共享自有规则仍以 `rules/*.list` 为唯一真源，不能用远程副本
绕过本仓审查。

## 判据清单

文档不是安全边界。以下判据分别覆盖 Surge / Egern / mihomo，并由跨内核门禁收口。

### 跨内核

| 判据 | 守什么 |
|:--|:--|
| [`skill/tests/check_secrets.py`](skill/tests/check_secrets.py) | 扫描 Surge / Egern / mihomo 的配置，阻止非文档地址、真实凭据、非 `REPLACE_WITH_YOUR_*` 值与订阅 token 进入公开仓库。 |
| [`skill/tests/check_selfcontained.py`](skill/tests/check_selfcontained.py) | 扫描三内核配置与脚本中的在线引用，阻止本仓自有图标、规则和派生资产回指其他仓库。 |

### Surge

[`skill/scripts/surge/check_surge_dns.py`](skill/scripts/surge/check_surge_dns.py) 对 Surge profile
执行 12 项防 DNS 泄露与结构检查：

1. 加密 DNS 端点使用 IP 字面量，避免主机名引导解析；
2. `dns-server` 显式设置、不混入系统 DNS，并保留足够的国内引导端点；
3. `hijack-dns` 接管应用硬编码的解析器；
4. `encrypted-dns-follow-outbound-mode` 不形成解析与代理依赖环；
5. `always-real-ip` 与 `[Host]` 不引入隐式系统 DNS；
6. 延迟测试 URL 的域名归属可解释；
7. 策略组成员无悬空节点或组引用；
8. 规则策略可解析；
9. 白名单、广告拦截、域名直连、IP 规则与兜底顺序正确；
10. 广告规则使用满足 `pre-matching` 要求的字面量 REJECT 族策略；
11. `always-real-ip` 主机在兜底前有域名规则承接；
12. IP 类规则带 `no-resolve`，不为规则判定额外触发解析。

### Egern

[`skill/scripts/egern/check_egern_dns.py`](skill/scripts/egern/check_egern_dns.py) 守 Egern profile
的 DNS 链与规则可达性：策略引用必须存在；加密端点不得依赖未受控的 bootstrap 解析；
`proxy_nameservers`、`bootstrap` 与 `forward` 的回退关系明确；`forward` 必须有捕获全部域名且
直连可达的加密兜底，不能混入明文出口；IP 类规则使用 `no_resolve`；DNS 端点有正确路由；
`hijack_dns`、IPv6、反污染与 real-IP/fake-IP 设置不留旁路；无死规则；profile 自身的测速、
图标等必要域名也能在不回退明文的前提下解析。

### mihomo

mihomo 同时覆盖 `clash/profiles/` 静态配置与 `clash/override/` 覆写脚本；两种形态分开判，
不能把客户端负责的 TUN 设置强塞进覆写脚本，也不能让静态 profile 缺少 TUN（流量接管与 :53 劫持）。

[`skill/tests/clash/check_structure.py`](skill/tests/clash/check_structure.py) 守 8 项结构红线：

| 项 | 守什么 |
|:--|:--|
| ① | 策略组成员无悬空引用。 |
| ② | 规则引用的 provider 与策略组都存在。 |
| ③ | DNS 广告拦截同时满足 `nameserver-policy` 与 `fake-ip-filter` 两个条件，且广告项排在 `cn` / `private` 前。 |
| ④ | 静态 profile **禁止** `tun` 段（4c4bc56 起反转）；配置内不出现 `tun`，脚本也不写。 |
| ⑤ | `geoip-*` 规则带 `no-resolve`。 |
| ⑥ | `nameserver` 使用 IP 字面量，避免冷启动引导泄露。 |
| ⑦ | 零 dat 依赖：禁用 `geox-url`、自动更新键、原生 `GEOSITE` / `GEOIP` 规则及 `geosite:` policy 键；独立 `.mrs` 不在禁用范围。 |
| ⑧ | 顶层 `ipv6` 与 `dns.ipv6` 两处均显式关闭。 |

[`skill/scripts/clash/check_clash_dns.py`](skill/scripts/clash/check_clash_dns.py) 再执行 14 项
DNS 防泄露审计：

1. DNS 已启用；
2. `default-nameserver` 全为 IP 字面量；
3. `nameserver` / `fallback` 同时满足 IP 字面量与加密协议；
4. 节点域名和直连域名使用职责明确的侧路 nameserver；
5. 使用 `fake-ip`，且地址段落在 RFC 6815 保留范围；
6. 两处 IPv6 开关关闭；
7. 静态 profile 的 TUN 接管 53 端口并启用 `strict-route`，覆写输出按覆写形态审计；
8. 广告规则在 policy 与 fake-IP filter 两处同时存在且引用有效；
9. 广告 policy 排在 `cn` / `private` 前；
10. IP 类规则带 `no-resolve`，域名类规则不滥用该选项；
11. 零 dat 依赖，且不把 `.mrs` 误判为 dat；
12. rule-provider 至少有可加载的 `url` 或 `path`，形态完整；
13. provider 与策略引用均可解析，防止静默失效；
14. `respect-rules`、`use-system-hosts` 等其余 DNS 开关给出风险提示。

## 范围说明

本仓只提供 Surge / Egern / mihomo 配置模板、共享资产、覆写脚本与离线判据，不提供运行中的
网络服务，也不保存用户的真实节点或订阅。这里的“漏洞”主要分为两类：**敏感信息泄露**，
以及**判据失效导致泄露防线或供应链约束未被执行**。前者立即轮换真实值，后者修复判据并
回查受影响版本；两类均按上文使用私密安全通告处理。
