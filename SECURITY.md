# 🔐 安全策略

本仓是一个**公开的配置模板仓**：两份代理内核（Surge / Egern）的防 DNS 泄露模板，
加一套给 AI 用的技能包与离线回归闸门。所有节点地址、凭据、订阅 token 一律是占位假值，
由仓内判据把关：提交前在本地跑 `python skill/tests/check_secrets.py`（占位符 / 凭据扫描），push 后 CI 会再扫一遍。

## 请不要做的事

- **不要把真实配置提进来**：真实节点地址、认证凭据、订阅链接里的 token，
  一旦推上公开仓库就**不可回收**（git 历史撤回需要改写历史）。
  如果你在本地副本里放了真实值又准备提交 —— 先停下来，把它们换回占位假值。
- **不要在 issue 里贴含真实凭据的报错输出**。报错截图 / 日志里常见订阅 token
  与内网地址，先打码再贴。

## 报告漏洞

如果发现以下任一类问题，请走 GitHub 的**私密安全通告**
（仓库页 Security → Report a vulnerability），不要公开发 issue：

- 仓内任何文件带着**非占位**的真实地址 / 凭据 / token；
- `skill/tests/` 的闸门判据存在**看着全绿而其实失效**的路径
  （即 `skill/tests/` 下的判据脚本本身）；
- 链接的第三方规则集来源被替换为不可控的镜像。

一般性功能问题、文档笔误、配置建议走普通 issue 即可，不必占安全通告通道。

## 范围说明

本仓不提供运行中的服务，也没有依赖包管理清单。
「漏洞」在本仓的语境里主要是**泄露**与**判据失效**两类，上面两条通道按此划分。

## 判据清单（本仓的纪律全部落成机器判据，不靠文档自觉）

与姊妹仓一致的做法 —— 它的 `check_surge_dns.py` 里就有一整条判
「加密 DNS 端点必须 IP 字面量」，同一条纪律在那里也是判据而非文档里的一句话。

mihomo 侧（`skill/tests/clash/check_structure.py`）现守 8 项：

| 项 | 守什么 |
|:--|:--|
| ① | 无悬空引用（组成员必须存在） |
| ② | 规则指向的 provider 与策略组必须存在 |
| ③ | DNS 广告拦截双条件 + 广告项排在 `cn` 之前 |
| ④ | `tun` 四键齐全（**仅静态 profile**；覆写脚本不该有 tun） |
| ⑤ | `geoip-*` 规则必须带 `no-resolve` |
| ⑥ | `nameserver` 必须写 IP 字面量，不能写主机名 |
| ⑦ | **零 dat 依赖**：不得用 `geox-url` / `geo-auto-update` / `geo-update-interval`，<br>不得写 `GEOSITE,` / `GEOIP,` 原生规则，<br>`nameserver-policy` 键不得用 `geosite:` |
| ⑧ | IPv6 两处显式关闭（顶层 + `dns.ipv6`） |

⚠️ 第 ⑦ 项**不排斥 `.mrs`**：`geoip-private` / `geoip-cn` 等是 MetaCubeX 的
独立远程集文件（`format: mrs`），与 `GeoSite.dat` / `GeoIP.dat` 数据库无关，
是本仓想要的形式。判据只拦 dat，不拦 mrs —— 已实测不会误伤。
