# 加固模板（完整 YAML）

> 本文是 [`SKILL.md`](../../SKILL.md) 的引用文件。 **何时读**：要产出一份加固后的 `dns` 段 + `rules` 时。

模板里的行内注释就是**逐行理由**，别删。规则顺序不能反：
先把解析路径收口（`proxy_nameservers` 显式写 + `forward` 只留兜底），再去调 `upstreams` 里的解析器。

---

```yaml
dns:
  bootstrap:                      # 只能明文 UDP:53 —— 本文件唯一无法加密、无法走代理的出口。
  - 223.5.5.5                     # 列 2 个以上国内公共 DNS：官方「解析失败时自动使用系统 DNS」，
  - 223.6.6.6                     # 而 system 在蜂窝下就是运营商。多列几个只为压低这一最坏分支。
  - 119.29.29.29                  # ⚠️ 绝不写 system —— 那是主动把运营商解析器接进回退链。
  upstreams:
    Domestic-DNS:                 # 国内域名 → 国内加密 DNS。★ 全部写 IP 字面量：
    - https://223.5.5.5/dns-query  #   端点上每写一个主机名，官方就会用明文 bootstrap 解析它一次
    - https://223.6.6.6/dns-query  #   （bootstrap 用途①）。写 IP 则一次都不产生，且零依赖。
    - https://1.12.12.12/dns-query #   下面 6 个已实测通过（含证书覆盖 IP），两家机构 × 两种协议。
    - https://120.53.53.53/dns-query
    - tls://223.5.5.5
    - tls://1.12.12.12
    Foreign-DNS:                  # ★ 一律 IP 字面量，杜绝 bootstrap 解析
    - https://8.8.8.8/dns-query    # 需在 rules 里把这些 IP 显式判给 Proxy，链路才是
    - https://8.8.4.4/dns-query    # 「设备 → 代理 → 8.8.8.8」，从国内蜂窝也能建起来。
    - https://1.1.1.1/dns-query    # 多列端点：官方「组内并发竞速、最快者胜」，
    - https://1.0.0.1/dns-query    # 触发回退的唯一条件是「本组全失败」，端点越多越不可能。
    - tls://8.8.8.8
    - tls://9.9.9.9                # ⚠️ Quad9 只能走 DoT：其 9.9.9.9 的 DoH 实测
                                  #    返回 HTTP Version Not Supported（只提供 HTTP/3）
                                  #    写 https://9.9.9.9/dns-query 会静默失效。
    # ⚠️⚠️ 本组**不要**用作 forward 的兜底 —— 它必须经代理才可达，把兜底挂在它身上等于
    #      「先有代理，才敢解析」，代理未就绪时那次解析会掉进 bootstrap 明文（见坑 13）。
  forward:                        # ★★ f10 起只留兜底 —— **不要在这里写任何具体域名**（坑 18）
  - domain_regex:                 # ★★ 双保险之一：官方 PCRE2 find 式，'.' 必然命中任何域名
      match: '.'
      value: Domestic-DNS         # ★★ 兜底指向「直连可达」的国内加密组 —— 不是境外组。
  - domain_wildcard:              #    境外组必须经代理，代理没就绪时兜底就会掉进 bootstrap
      match: '*'                  #    明文（见坑 13）。按官方语义走代理的域名由节点远程解析，
      value: Domestic-DNS         #    本地 dns 段只服务 DIRECT 域名，所以国内组没有副作用。
  # ★ 为什么不需要 `.cn` / 国内域名表 / 节点域名 / 延迟测试域名 / 图标域名这些规则：
  #   ① 它们的 value 与兜底**完全相同** ⇒ 单值集合里"命中顺序"不产生任何影响，删掉也不变（清单 18）。
  #      官方那句"第一条命中的决定上游"只在 value 有差异时才有意义。
  #   ② 节点域名的解析走**代理 DNS**，配了 proxy_nameservers 后官方明确"**跳过 Forward**"
  #      ⇒ 写在 forward 里的节点域名规则是**死代码**（f7 之前它有用，f7 之后退役）。
  #   ③ 延迟测试域名与图标域名同理：f4 加它们是因为当时兜底是境外组（不安全）；
  #      f6 把兜底换成国内组之后，它们就已被兜底覆盖。
  #   ⚠️ 千万别为了"看起来严谨"再往这里堆域名 —— 每堆一条就把"换订阅"变成一次复查配置的义务。
  # ★★ f7 起必须显式写 proxy_nameservers —— 不写就等于留下一条通往明文 UDP:53 的兜底分支：
  #   官方原文：「未配置时，代理 DNS 与默认 DNS 共用 Forward 规则，**未命中回退到 Bootstrap**」；
  #   配置后语义：「所有代理 DNS 查询强制走该列表，**Forward 规则会被跳过**」。
  #   只能用国内端点 —— 代理 DNS **强制直连**，境外解析器在电信线路上不可达。
  proxy_nameservers:
  - https://223.5.5.5/dns-query
  - https://223.6.6.6/dns-query
  - https://1.12.12.12/dns-query
  - https://120.53.53.53/dns-query
  - tls://223.5.5.5
  - tls://1.12.12.12
  # ⚠️ 如果你发现"节点连不上"，第一件事是注释掉这 6 行（等价于回到 f6 的行为）。
  hosts:                          # ★ 把上面 DoH 域名钉到 IP（仅当 IP 固定）
    dns.alidns.com: [223.5.5.5, 223.6.6.6]
    doh.pub: [1.12.12.12, 120.53.53.53]
    dot.pub: [1.12.12.12, 120.53.53.53]
  block_ips:                      # 丢弃空路由式污染应答；别放私网段免得误伤内网
  - 0.0.0.0
  - 127.0.0.1

rules:
# ★★ DNS 端点固定路由必须放在 rules 最前 —— geoip 带 no_resolve 后不再匹配域名，
#    主机名形式的端点会落到 default。国内端点不钉住就会被绕到境外出口。
- domain_suffix:
    match: alidns.com
    policy: DIRECT
- domain:
    match: doh.pub
    policy: DIRECT
- ip_cidr:
    match: 223.5.5.5/32
    policy: DIRECT
    no_resolve: true
# ... 223.6.6.6 / 1.12.12.12 / 120.53.53.53 同样处理
- domain:
    match: dns.google
    policy: Proxy
- domain_suffix:
    match: cloudflare-dns.com
    policy: Proxy
- ip_cidr:                        # ★ 兜住「App 硬编码 DoH IP + :443 绕过 hijack」
    match: 8.8.8.8/32
    policy: Proxy
    no_resolve: true
# ... 8.8.4.4 / 1.1.1.1 / 1.0.0.1 / 9.9.9.9 / 208.67.222.222 / 208.67.220.220
# ---- 以下是原有规则 ----
# ... 最后（顺序很关键：国内域名兜底必须在 default 之前）：
- rule_set:                      # ★★ 国内域名直连兜底（坑 17）—— 必须用域名条目足够多的那份：
    match: https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/ChinaMax/ChinaMax_All_No_Resolve.list
    policy: DIRECT               #   111332 条域名 + 12473 条 IP（IP 全带 no-resolve）
                                 #   ❌ 别用 ChinaMax.list：它只是 IP 规则集，域名只有 64 条
- domain_suffix:                  # ★ 补 .cn 直连兜底：不依赖上面那份规则集是否加载成功
    match: cn
    policy: DIRECT
- geoip:                          # ★ 不加 no_resolve 会为每次判定触发解析
    match: CN
    policy: DIRECT
    no_resolve: true
- default:
    policy: <代理组>
```

顶层另加：`ipv6: false`、`hijack_dns: ['*']`、`real_ip_domains: ['*.lan','*.local','*.push.apple.com']`。

⭐ **f10 起不要做这一步（它的反面才是对的）**：早期版本（f3）要求"把域名形式的节点逐个写成 `domain_suffix → Domestic-DNS`"，因为那时代理 DNS 会共用 `forward`。**f7 显式写出 `proxy_nameservers` 之后，代理 DNS 会跳过 `forward`** ⇒ 那些规则再也没被查询过（死代码，坑 18）。现在只需保证两件事：

1. `proxy_nameservers` **显式设置**，端点全部是**国内可达的 IP 字面量** —— 它是节点域名解析的唯一出口；
2. `forward` **只留兜底**，且兜底组「直连可达」。

⚠️ 顺序仍不能反：**先把解析路径收口（这两条），再去调 `upstreams` 里的解析器**。理由没变 —— 这些名字在隧道建立前必须被解析，而代理侧强制直连，国内根本问不到境外解析器。**但收口的手段是"把代理 DNS 钉死"，不是"在 forward 里列举域名"。**

⭐ **同理，profile 自身运行必需的域名**（`proxy_latency_test_url` / `direct_latency_test_url` / 策略组 `icon`）**也不需要单列规则**：f6 起兜底已是国内加密组，它们天然被覆盖。它们只在**兜底是境外组的配置里**才会造成持续泄露 —— 那正是 f4 加它们的场景。用 `audit_dns_forward.py --drill` 可验证任何域名（含这两类）都落到安全的兜底。
