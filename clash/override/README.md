# 覆写脚本

对**任意订阅**做整体覆写，使其结构与 [`profiles/routing.yaml`](../profiles/routing.yaml)（分流版）一致 —— 该文件即由本脚本生成。

## 文件

| 文件 | 作用 |
|:-----|:-----|
| [`my_clash.js`](my_clash.js) | JS 覆写脚本 —— 改造成**分流版**结构（25 组 / 27 条规则） |
| [`my_clash_lazy.js`](my_clash_lazy.js) | JS 覆写脚本 —— 改造成**懒人版**结构（3 组 / 11 条规则） |

两者同一骨架，DNS / 过滤口径 / 图标基址 / IPv6 处理完全一致，差别只在
策略组粒度与规则数量。要细分用 `my_clash.js`，要极简用 `my_clash_lazy.js`。

## 与静态模板的区别

静态模板用 `use: [Airport]` 引入订阅；脚本改用 **`include-all-proxies: true`**，
让订阅里已有的 `proxies` **直接成为各组成员** —— 于是不再需要单独占一个订阅槽位。

```
静态模板：  proxy-groups → use: [Airport] → proxy-providers.Airport.url
覆写脚本：  proxy-groups → include-all-proxies: true → 订阅自身的 proxies
```

> 若订阅除 `proxies` 外还带 `proxy-providers`，脚本会自动改用 `include-all`
> （= proxies + providers），避免 provider 里的节点成为孤儿。

## 覆写内容

| 项 | 处理 |
|:---|:-----|
| `proxies` | **保留**（订阅的节点原样） |
| `proxy-groups` | **整体替换**为 20 组 |
| `rule-providers` | **整体重建**为 20 份（13 geosite `.mrs` + 4 geoip `.mrs` + 3 自定义）；订阅自带的**一律丢弃** |
| `rules` | **整体替换**为 26 条 |
| `dns` | **整体替换**（含双层广告拦截）；不设 `listen`，由客户端决定 |
| 入站端口 | **不覆盖**，交给客户端决定 |

### 节点筛选

`Smart` / `Select` 与 5 个地区组通过 `filter` + `exclude-filter` 选节点：

| 字段 | 值 | 作用 |
|:-----|:---|:-----|
| `filter` | `^((?!(直连|DIRECT)).)*$` | 排掉直连类节点 |
| `exclude-filter` | `剩余\|流量\|到期\|过期\|官网\|订阅\|重置\|续费\|Traffic\|Expire\|GB` | 排掉机场常见的「剩余流量 / 套餐到期 / 官网」信息节点 |

> 信息节点不可用，若不排除会进入 `url-test` 测速池、污染择优结果。
> 二者均按内核 `groupbase.go` 的 `GetProxies()` 实现，作用于最终合并后的成员列表
> （含 `include-all-proxies` / `use` 引入的节点）。

## 双层广告拦截

```
广告域名查询
    ↓
① fake-ip-filter: "rule-set:AWAvenue-Ads" / "rule-set:jinx-ads-delta"
   → 跳过 fake-ip
    ↓
② nameserver-policy: rcode://success
   → 返回空回答，DNS 层拦截
    ↓
③ rules: RULE-SET,xxx,AD[REJECT]
   → 连接层兜底（IP 直连 / DoH / 缓存）
```

⚠️ **必要条件**：`nameserver-policy` 里返回 `rcode` 的域名，**必须同时在 `fake-ip-filter` 中列一遍**。
否则 `withFakeIP` 中间件对 A / AAAA 查询直接返回假 IP（见内核 `dns/middleware.go`，
`withFakeIP` 先于 `withResolver` 返回），请求永远到不了 `nameserver-policy`。
另：广告 policy 必须写在 `rule-set:private,cn` **之前**，否则先命中 `cn` 拿不到空回答。

机制先例见 [mihomo Discussion #668](https://github.com/MetaCubeX/mihomo/discussions/668)。

## 用法

### Mihomo Party / Mihomo Purity

1. 复制 `my_clash.js` 的 raw 直连地址；
2. 客户端「覆写」页面粘贴导入；
3. 订阅管理 → 目标订阅 → 编辑信息 → 覆写 → 选择该脚本。

### 本地验证

脚本输出 `config` 对象，可用 Node 模拟后交给内核校验：

```bash
node -e "
const fs=require('fs');
eval(fs.readFileSync('override/my_clash.js','utf8'));
const out = main({ proxies:[/* ... */], rules:['MATCH,DIRECT'] });
fs.writeFileSync('out.json', JSON.stringify(out));
"
# JSON → YAML 后:
mihomo -t -d . -f test.yaml
```

## 实测

本地内核 v1.19.32，模拟含「信息节点」的订阅：

```
Smart     all=['🇭🇰 香港01','🇺🇸 美国01']
Select    all=['🇭🇰 香港01','🇺🇸 美国01']

排除结果：
  剩余流量：100GB        ✅ 已排除
  套餐到期：2027-01-01   ✅ 已排除
  官网：example.com      ✅ 已排除
```

地区组筛选（5 节点订阅，港/日/新/台/美）：

```
HongKong         all=['🇭🇰 香港01']
United States    all=['🇺🇸 美国01']
Japan            all=['🇯🇵 日本01']
Taiwan           all=['🇹🇼 台湾01']
Singapore        all=['🇸🇬 新加坡01']
```

DNS（手工构造查询）：

| 域名 | rcode | answer | 结果 |
|:-----|:--:|:--:|:-----|
| `ad.doubleclick.net` | 0 | 0 | ★ 拦截 |
| `ad.qq.com` | 0 | 0 | ★ 拦截 |
| `ucc.umeng.com` | 0 | 0 | ★ 拦截 |
| `www.baidu.com` | 0 | 1 | `198.18.0.4` |
| `www.google.com` | 0 | 1 | `198.18.0.5` |
