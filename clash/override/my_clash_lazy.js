// ============================================================================
//  my_clash_lazy 覆写脚本 — 把任意订阅改造成「懒人版」结构
// ============================================================================
//
//  作用
//    对任意 mihomo 订阅配置做整体覆写，使其与本仓库 profiles/lazy.yaml 一致：
//      · 3 个策略组（Proxy / AI / AD）
//      · 10 份规则集（5 份 MRS + 5 份 yaml）+ 11 条规则
//      · DNS 双层广告拦截（fake-ip-filter + nameserver-policy rcode://success）
//      · 订阅内的节点直接成为组内成员 —— 不再需要 Airport 订阅槽位
//
//  与 my_clash.js（分流版脚本）的关系
//    两者是同一骨架的两个切面，DNS / 过滤口径 / 图标基址 / IPv6 处理完全一致；
//    差别只在策略组粒度（3 组 vs 25 组）与规则数量（11 条 vs 27 条）。
//    想要「按应用 + 按地区」的细分，用 my_clash.js；想要极简单出口，用本文件。
//
//  用法（Mihomo Party / Mihomo Purity 等支持 JS 覆写的客户端）
//    1) 把本文件放到可访问的 URL（或本地导入）；
//    2) 在客户端的「覆写」中导入，再绑到目标订阅上。
//
//  注意
//    · 本脚本会**整体替换** proxy-groups / rule-providers / rules / dns，
//      订阅自带的同名配置将被丢弃（节点 proxies 保留）；
//    · port / mixed-port 等入站端口不覆盖，交给客户端决定。
// ============================================================================

function main(config) {
  // ── 0. 兜底：确保关键字段存在 ──────────────────────────────────────────
  if (!config.proxies) config.proxies = [];

  // IPv6 显式关闭（顶层开关）：与 dns.ipv6 配套，双栈站点一律回落 IPv4，
  // 避免本机真实 IPv6 绕过 TUN 出网导致出口 IP 与节点不符。
  config.ipv6 = false;

  // 节点过滤口径（与分流版脚本一致）
  //   filter          —— 正向保留，作用于 include-all-proxies
  //   exclude-filter  —— 反向排除，作用于 include-all-proxies
  const NODIRECT = "^((?!(直连|DIRECT)).)*$";
  const NOJUNK = "剩余|流量|到期|过期|官网|订阅|重置|续费|Traffic|Expire|GB";

  // 通用健康检查参数
  const HC_URL = "https://www.gstatic.com/generate_204";
  const HC_INT = 300;

  // 图标基址（本仓库自带 icons/，与姊妹仓 Self-Configuration 同源）
  const ICON = "https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/main/icons/";
  // 本仓 raw 基址（自托管清单 rules/ 用）
  const RAW = "https://raw.githubusercontent.com/RiverFlowsInUUU/Clash/main/";
  // MetaCubeX MRS 规则集基址
  const JS = "https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo";

  // 节点来源开关：
  //   include-all-proxies 引入内联 proxies（订阅转换后的常见形态）；
  //   若订阅额外带了 proxy-providers，则 include-all-proxies 不会包含它们，
  //   此时改用 include-all（= proxies + providers）避免节点成孤儿。
  const HAS_PROVIDERS =
    config["proxy-providers"] && Object.keys(config["proxy-providers"]).length > 0;
  const ALL_KEY = HAS_PROVIDERS ? "include-all" : "include-all-proxies";
  const allNodes = {};
  allNodes[ALL_KEY] = true;

  // ── 1. 策略组（3 个）───────────────────────────────────────────────────
  //  Proxy  主出口 —— 全池 url-test 自动择优
  //  AI     AI 流量出口 —— 默认随 Proxy，可手动指定
  //  AD     广告拦截 —— 默认 REJECT
  config["proxy-groups"] = [
    {
      name: "Proxy",
      type: "url-test",
      ...allNodes,
      filter: NODIRECT,
      "exclude-filter": NOJUNK,
      url: HC_URL,
      interval: HC_INT,
      tolerance: 50,
      icon: ICON + "Proxy.png",
    },
    {
      name: "AI",
      type: "select",
      proxies: ["Proxy"],
      ...allNodes,
      filter: NODIRECT,
      "exclude-filter": NOJUNK,
      icon: ICON + "grok.png",
    },
    {
      name: "AD",
      type: "select",
      // 单成员 REJECT —— 与姊妹仓懒人版同口径（该仓 893b406 有意收敛）。
      // 分流版脚本才是 REJECT / DIRECT 二选一。
      proxies: ["REJECT"],
      icon: ICON + "AdBlock.png",
    },
  ];

  // ── 2. 规则集（10 份）──────────────────────────────────────────────────
  const rp = {};
  config["rule-providers"] = rp;

  // 5 份 MRS（原 GEOSITE / GEOIP 原生层，改为远程集以摆脱 geosite.dat 依赖）
  [
    { n: "private", b: "domain" },
    { n: "cn", b: "domain" },
    { n: "category-ai-chat-!cn", b: "domain" },
  ].forEach(function (c) {
    rp[c.n] = {
      type: "http",
      behavior: c.b,
      format: "mrs",
      url: JS + "/geosite/" + c.n + ".mrs",
      path: "./rule_provider/" + c.n + ".mrs",
      interval: 86400,
    };
  });
  [
    { n: "private", b: "ipcidr" },
    { n: "cn", b: "ipcidr" },
  ].forEach(function (c) {
    rp["geoip-" + c.n] = {
      type: "http",
      behavior: c.b,
      format: "mrs",
      url: JS + "/geoip/" + c.n + ".mrs",
      path: "./rule_provider/geoip-" + c.n + ".mrs",
      interval: 86400,
    };
  });

  // 广告拦截第 2 条（上游提供 mihomo 二进制格式）
  rp["AWAvenue-Ads"] = {
    type: "http",
    behavior: "domain",
    format: "mrs",
    url: "https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/Filters/AWAvenue-Ads-Rule-Clash.mrs",
    path: "./rule_provider/AWAvenue-Ads-Rule-Clash.mrs",
    interval: 86400,
  };

  // Jinx 白名单 / 广告主清单（自托管 Jinx 仓，命名与分流版一致）
  rp["Jinx-CN"] = {
    type: "http",
    behavior: "classical",
    format: "yaml",
    url: "https://raw.githubusercontent.com/RiverFlowsInUUU/Jinx/main/mihomo-direct.yaml",
    path: "./rule_provider/Jinx-CN.yaml",
    interval: 86400,
  };
  rp["Jinx-Ads"] = {
    type: "http",
    behavior: "classical",
    format: "yaml",
    url: "https://raw.githubusercontent.com/RiverFlowsInUUU/Jinx/main/mihomo-ads.yaml",
    path: "./rule_provider/Jinx-Ads.yaml",
    interval: 86400,
  };

  // 本仓自托管清单（上游无对应集）—— 与分流版共用同一份文件
  rp["AI_Domains"] = {
    type: "http",
    behavior: "classical",
    format: "yaml",
    url: RAW + "rules/AI_Domains.yaml",
    path: "./rule_provider/AI_Domains.yaml",
    interval: 86400,
  };
  rp["apple-system"] = {
    type: "http",
    behavior: "classical",
    format: "yaml",
    url: RAW + "rules/apple_system.yaml",
    path: "./rule_provider/apple_system.yaml",
    interval: 86400,
  };

  // ── 3. 分流规则（11 条）────────────────────────────────────────────────
  // 次序与 profiles/lazy.yaml 逐位一致：
  //   ① 白名单  ② 广告拦截 ×2  ③ 内网 ×2  ④ Apple 系统服务
  //   ⑤ AI 分流 ×2  ⑥ 国内域名 + 国内 IP  ⑦ 兜底
  config.rules = [
    // ① 白名单 —— 抢在广告规则之前放行
    "RULE-SET,Jinx-CN,DIRECT",
    // ② 广告拦截 —— 两条并列清单，同一出口 AD
    "RULE-SET,Jinx-Ads,AD",
    "RULE-SET,AWAvenue-Ads,AD",
    // ③ 内网：私有 IP 段 + 私有域名，一律直连
    "RULE-SET,geoip-private,DIRECT,no-resolve",
    "RULE-SET,private,DIRECT",
    // ④ Apple 系统服务（激活 / 推送 / 定位 / 配对）
    "RULE-SET,apple-system,DIRECT",
    // ⑤ AI 分流：通用 AI 类目兜底在前，伴生域/宽后缀随后整域收编
    "RULE-SET,category-ai-chat-!cn,AI",
    "RULE-SET,AI_Domains,AI",
    // ⑥ 国内：域名集在前、IP 集在后，都直连
    "RULE-SET,cn,DIRECT",
    "RULE-SET,geoip-cn,DIRECT,no-resolve",
    // ⑦ 兜底
    "MATCH,Proxy",
  ];

  // ── 4. DNS（含双层广告拦截）────────────────────────────────────────────
  // 关键：广告域名必须同时出现在
  //   ① fake-ip-filter  —— 否则 withFakeIP 对 A/AAAA 直接返回假 IP，
  //                        请求永远到不了 nameserver-policy；
  //   ② nameserver-policy = rcode://success —— 返回空回答，DNS 层拦截。
  // 且 nameserver-policy 中广告项必须写在 rule-set:private,cn 之前。
  config.dns = {
    enable: true,
    // 不返回 AAAA 记录，双栈站点自动回落 IPv4
    ipv6: false,
    "enhanced-mode": "fake-ip",
    "fake-ip-range": "198.18.0.1/16",
    "respect-rules": true,
    "use-hosts": true,
    "use-system-hosts": false,
    "prefer-h3": false,

    // 引导解析器：只用于解析 DoH 端点自身的域名
    "default-nameserver": ["223.5.5.5", "119.29.29.29"],
    // 只解析**代理节点域名**（连节点前还没有代理可用，鸡生蛋问题）
    "proxy-server-nameserver": [
      "https://223.5.5.5/dns-query",
      "https://120.53.53.53/dns-query",
    ],
    // 只解析 DIRECT 出站的域名 —— 直连流量也不碰系统 DNS
    "direct-nameserver": [
      "https://223.5.5.5/dns-query",
      "https://120.53.53.53/dns-query",
    ],
    // 主解析器
    nameserver: [
      "https://dns.cloudflare.com/dns-query",
      "https://dns.google/dns-query",
    ],

    "nameserver-policy": {
      // 广告两项**必须排在** geosite:private,cn 之前 —— 否则先命中 cn 就拿不到空回答；
      // 且必须同时在 fake-ip-filter 里列一遍（见下），否则拦截不生效。
      "rule-set:AWAvenue-Ads": "rcode://success",
      "rule-set:Jinx-Ads": "rcode://success",
      "geosite:private,cn": [
        "https://223.5.5.5/dns-query",
        "https://120.53.53.53/dns-query",
      ],
    },

    "fake-ip-filter": [
      "*.lan",
      "*.local",
      "*.localdomain",
      "*.home.arpa",
      "+.msftconnecttest.com",
      "+.msftncsi.com",
      "localhost.ptlogin2.qq.com",
      "+.srv.nintendo.net",
      "+.stun.playstation.net",
      "+.xboxlive.com",
      "stun.*",
      "time.*.com",
      "ntp.*.com",
      "+.pool.ntp.org",
      "+.market.xiaomi.com",
      // 广告清单：与 nameserver-policy 中的广告项一一对应
      "rule-set:AWAvenue-Ads",
      "rule-set:Jinx-Ads",
    ],
  };

  return config;
}
