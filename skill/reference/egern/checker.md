# 核对器与审计演进

> 本文是 [`SKILL.md`](../../SKILL.md) 的引用文件。 **何时读**：跑审计脚本前（命令与环境要求），或要改判据时（演进史）。

## 目录

- 命令清单（含回归测试）
- 运行目录要求：`_egern_common.py` 必须与调用它的脚本同目录
- `hostpart()` 剥 scheme 必须大小写不敏感
- 判据演进史：f3 → f4 → f5 → f6 → f7 → f8 → f10 → f10.1 / f10.2 / f10.3
- 实测基准表：原始配置 → f10
- 发布脚本卫生

---

```bash
"<venv>/Scripts/python.exe" skill/scripts/egern/check_egern_dns.py profile.yaml [more.yaml ...]
"<venv>/Scripts/python.exe" skill/scripts/egern/probe_dns_endpoints.py profile.yaml   # ★ 端点逐个实测（含证书覆盖 IP）
"<venv>/Scripts/python.exe" skill/scripts/egern/audit_ruleset_noresolve.py profile.yaml  # ★★ 规则集 IP 条目 no-resolve 审计（清单 16）
"<venv>/Scripts/python.exe" skill/scripts/egern/audit_ruleset_noresolve.py --url <ruleset-url>
"<venv>/Scripts/python.exe" skill/scripts/egern/audit_routing_coverage.py profile.yaml   # ★★ 分流覆盖审计（清单 17，域名→命中规则→策略）
"<venv>/Scripts/python.exe" skill/scripts/egern/audit_dns_forward.py profile.yaml         # ★ forward 单值性（非 reject 去向）/订阅耦合审计（清单 18）
"<venv>/Scripts/python.exe" skill/scripts/egern/audit_dns_forward.py profile.yaml --drill # ↑ --drill 可选：加合成"未来订阅"域名多演练一遍
"<venv>/Scripts/python.exe" skill/scripts/egern/audit_region_filters.py profile.yaml      # ★ 地区组 filter 与 Other Regions 负向断言的「两份拷贝」同步校验
"<venv>/Scripts/python.exe" skill/scripts/egern/audit_ruleset_refresh.py profile.yaml --strict  # ★ 刷新参数：非正值=HIGH，偏离约定值 604800=仅 --strict 判负
"<venv>/Scripts/python.exe" skill/scripts/egern/probe_doh.py                    # 只测 DoH 线格式
"<venv>/Scripts/python.exe" skill/scripts/egern/profile_ruleset.py some.list    # 规则集类型分布
"<venv>/Scripts/python.exe" skill/scripts/egern/weigh_ruleset.py some.list [--sub small.list] [--probe d]  # ★ 规则集"重量"：构成/冗余/深度/加载与匹配耗时/覆盖对比

python skill/scripts/egern/check_egern_dns.py egern/profiles/lazy.yaml egern/profiles/routing.yaml   # ★★ DNS 面回归，退出码非 0 即失败
```

⭐ **计数口径是「按脚本对账」**：阶段 1 的 5 行 fixture 每行校两个脚本（两条独立判据）⇒ 计 10 条；
   阶段 2 每份 profile 同时校 `check_egern_dns` / `audit_region_filters` / `audit_ruleset_refresh` 三条判据 ⇒ 顶层固定名四件 × 3 = 12 条；
   离线合计 22（`SKIP_NET=1` 实测），联网档再给两份完整版各加一条分流覆盖 = 24；runner 末尾的 `TOTAL:` 行就是这两个数。归档版不在检查路径上 ⇒ 这个数**不随版本累积**。
⭐ **「当前版」是固定名，不是一堆版本号**（2026-09-24 起）：顶层恒为 `routing` / `lazy`
   四个文件名（固定名四件）。
   「哪一版」只剩 profile 头注 `#! version=routing_vX.Y(.Z)`，形状与两内核一致性由
   `check_min_pair.py` 判（V1–V6 ×2 + V7 一天一版 ×2 + 跨侧 2 条）。前置检查会在 `$PROFILES/$CURRENT.yaml`
   不存在时给**退出码 2** —— 否则那份名单一条都套不上，
   当前推荐版会被当成"历史存档版"只查非正值，**看着绿、其实没审**。
   要复核历史版本：从 git 历史取出对应文件，带着路径直接调对应脚本。
   `.min` **不手工同步**：改完完整版跑 `python skill/tests/make_min.py --family routing|lazy|all`
   （默认只出计划，`--apply` 才写盘）—— Egern 侧它是纯函数（去注释 + 规范空白，与 `check_min_pair.py`
   共用同一套判据 ⇒ 生成即过拍）。

⚠️ **运行目录要求**：`skill/scripts/egern/` 的 10 个脚本里有 8 个 import 同目录的
`_egern_common.py`（共享工具）。**它必须和被调用的脚本同目录**，否则报 `ModuleNotFoundError`。
`_egern_common.py` 收编了 `DOMESTIC_RESOLVER_IPS` / `hostpart` / `ip_literal` —— 从结构上消灭了
"同一判据两份拷贝、改一处漏另一处"的隐患（详见"审计演进"节 f10.2）。

⚠️ **`hostpart()` 剥 scheme 必须用大小写不敏感的通用正则，不能用白名单。**
白名单（`("https://", "tls://", ...)`）会让 scheme 的**拼法**参与审计结论：端点写成
`HTTPS://223.5.5.5/dns-query` 时白名单失配，`HTTPS` 被当成主机名，端点从「IP 字面量」
误判成「待解析域名」，同一份配置读数从 0 high 翻成 9 high。`skill/tests/egern/scheme_case.yaml` 是这条的守卫。

`check_egern_dns.py` 输出 `OK / LOW / HIGH` 三类，有 `HIGH` 时退出码 1，覆盖上面清单 1–15 项。
清单 16 由 `audit_ruleset_noresolve.py` 单独覆盖（要下载**全部被引用的**规则集，几十秒，不塞进同一个脚本；有 `.ruleset-cache/` 本地缓存，加 `--offline` 可只读缓存）。实测判别力：**原始配置 → HIGH（`Apple_All.list` 13 条），f7 → OK（20 个全过）**。⚠️ 数量会随配置变化：f10 是 **19 个**（少的那 1 个 = `forward` 不再引用 `ChinaDomain.list`）；2026-09-21 新增 `white-guard` / `ads` 两条后为 **21 个**，`routing_v3.4` 时代实抓 **22 个**（历史锚点，当时实测对象即 v3.4） —— 报数变化时先确认是"少引用"而不是"漏扫"。

f3 起新增：① **节点域名覆盖检查**（从 `proxies[].server` 自动提取域名，逐个查 `forward` 是否有非兜底规则接住）；② **兜底语义识别**（`domain_wildcard:'*'` 与 `domain_regex:'.'` 都认，不再依赖"必须在最后一条"）。
⚠️ **①在 f7/f10 后已反转**：`proxy_nameservers` 一旦显式设置，代理 DNS 就跳过 `forward` ⇒ 该检查的判据改为"`proxy_nameservers` 是否显式设置且端点全为 IP 字面量"，而"forward 里有没有为节点域名单列规则"变成**要主动避免的事**（坑 18）。
f4 起新增：③ ⭐ **「profile 自身必需解析」覆盖检查** —— 把两个 latency test URL 与 `policy_groups[].icon` 的域名按 `domain`/`domain_suffix`/`domain_keyword`/`domain_wildcard`/`domain_regex` 语义去匹配 `forward`，看有没有"兜底之前"的规则接住。**兜底组不安全时**：延迟测试端点漏接 = HIGH（每轮测速都触发，持续泄露）；图标漏接 = LOW。
⚠️ **③在 f6 后降级**：兜底一旦换成直连可达的国内组，这些名字落到兜底就不再构成泄露（现为 LOW）—— 它们只在"兜底不安全"的配置里才是事故（坑 18）。
f5 起新增：④ **明文回退面检查** —— `bootstrap` 含 `system` → HIGH（主动接进运营商 DNS）；`bootstrap` 只有 1 个 → LOW；`forward` 的 `value` 出现 `system` → HIGH、出现 `bootstrap` → LOW。
f6 起（⭐ 本版最重要的收紧）：⑤ **兜底组「直连可达」判定（`group_reach()`）** —— 判据从"端点写 IP + 有显式路由"改为"**端点写 IP + 至少一个在 `rules` 里判给 `DIRECT`**"。只判给 Proxy 的组报 HIGH：**兜底组依赖代理**（坑 13）。这条判据是本次事故的直接产物 —— f5 在旧判据下 `0 high`，用户实测却出 `upstream: bootstrap`。同时**撤回 f2 的一条错判**："兜底指向国内组 = HIGH"是错的 —— 致命的是**明文**，"答案可能被污染"是另一个量级的问题；现在兜底 = 直连可达的国内组判 **OK + 一条 LOW 说明**。

f7 起（本条不是脚本新增检查，而是**判据层面的补完**）：⑥ **清单 16 的规则集审计独立成脚本** —— 因为"强制解析"这类缺陷**完全不在 profile 文本里**，`check_egern_dns.py` 再怎么写也看不见。**这是本项目第二次栽在"审计器只能验证自己编码进去的假设"（坑 3、坑 9）上**：f6 在 `check_egern_dns.py` 下已是 `0 high`，用户实测仍有泄露。结论固化下来：**任何一次"审计通过但用户仍报泄露"，都必须假设"存在审计器看不见的维度"，并把该维度补成一个可复跑的脚本。**

f8 起：⑦ **分流覆盖审计独立成脚本（清单 17）** —— 第三次栽在同一个道理上：f7 在 `check_egern_dns.py` / `audit_ruleset_noresolve.py` 下**双双通过**（`0 high` + `OK 20/20`），用户实测却是"国内域名全落 final"。原因是两个脚本一个只看 DNS 面、一个只看"会不会强制解析"，**都看不见路由本身对不对**。⇒ 新增 `audit_routing_coverage.py`。**结论再收紧一层：DNS 审计全绿 ≠ 配置可用；只要动过 `no_resolve` 或换过任何规则集，分流必须单独复测（可用域名走一遍规则）。**

f10 起：⑧ **forward 单值性 / 订阅耦合审计独立成脚本（清单 18）** —— 这一次不是"泄露或分流坏了"，而是**可维护性**：用户指出"节点域名写在配置里，换订阅就失效"。核查发现那几条规则**自 f7 起已是死代码**（`proxy_nameservers` 让代理 DNS 跳过 forward；且全部 forward 规则 value 相同 ⇒ 顺序与域名清单都不影响结果）。⇒ `forward` 塌缩为 2 条兜底，新增 `audit_dns_forward.py`。**教训：审计器要同时盯"安全"和"耦合面" —— 一条没功能、却让人以为"配置依赖订阅"的规则，本身就是缺陷。**

f10.2 起（2026-09-20，二次核查报告触发）：⑩ **「靠注释提醒同步两份拷贝」被证明不可靠 —— 改成共享模块 + fixture 回归。**
背景：上一条 f10.1 我在两个脚本里各写了一份同样的判据，并加了注释"改一处要同步另一处"。**注释没能阻止我漏改**：
- 判据**本体**同步了，但**喂给判据的 helper 没同步** —— `audit_dns_forward.py` 自己的 `ep_ip()`
  用 `rsplit(":", 1)[0]` 切端口，把 IPv6 的 `[2400:3200::1]` 截成 `'[2400:3200:'`；
  而 `check_egern_dns.py` 的 `hostpart()` 有方括号专处理、返回正确值。
  ⇒ **同一份 IPv6 profile，两个脚本给出相反结论**（0 high/exit 0 vs 需确认/exit 1）——
  比"没有脚本"更糟，因为用户不知道信谁。
- 同一时期还暴露：`audit_dns_forward.py` **不带 `--drill` 直接崩**（`UnboundLocalError: fails`）——
  `fails = []` 只写在 `if probes:` 块里，而 README / docs / skill 里给的命令**正是不带参数的形态**。
  这个崩溃**旧版就有**，但因为它只被手工喂给 `check_egern_dns.py`，一直没被发现。

⇒ 固化五条：
1. ⭐⭐ **共用逻辑必须收编成一个模块，不靠注释同步。** 现为 `skill/scripts/egern/_egern_common.py`，
   收 `DOMESTIC_RESOLVER_IPS` / `hostpart` / `ip_literal`；两个脚本都 import 它。
   **判据可以有两处调用点，但实现只能有一处。**
2. ⭐⭐ **构造的反例必须喂给"所有"脚本，而不是常跑的那一个。**（原 fixture 套件已随精简删除，反例直接构造临时 yaml 喂脚本）
   阶段 1（5 fixture × 2 脚本 = 10 断言）+ 阶段 2（全部 profile × 2 脚本），**改脚本 / 改 profile 后手动跑一次**。
   经验：**"只差一点就能抓到"的 bug，恰恰是因为守卫只覆盖了一半**。加守卫时要问："这条断言有没有在
   **每一个**消费方上跑过？"
3. ⭐ **文档里给的命令必须逐条照着执行一遍。** 这次崩溃的命令就印在 README 和 skill/ 的文档里。
   文档里的命令是**接口契约**，改脚本后要回填验证（`--drill` 这类可选参数尤其要显式标注"可选"）。
4. ⭐ **`_egern_common.py` 必须与调用它的脚本同目录。** 用户如果只拷走单个脚本会报 `ModuleNotFoundError`；
   分发/打包时整个 `skill/scripts/egern/` 目录（11 件，含 `_egern_common.py`）要一起走。
5. ⭐⭐ **断言对象要选"能真正测到它的那个输入"—— 合成 fixture 测不到的东西，别硬塞进去当绿。**
   （2026-09-21 新增 `audit_region_filters.py` 时发现）该脚本校验的是 `policy_groups` 段的地区组 filter，
   而 `tests/` 那五份 fixture 是 **DNS 面的合成配置、根本没有地区组** —— 喂给它只会走"无需校验"分支，
   **看着绿，其实一个断言都没执行**。所以对**顶层固定名四件真实 profile** 逐份跑它。
   判据：**如果一份输入必然走"跳过 / 无此项"分支，那它就不构成断言** —— 加守卫时先问
   "这份输入里，被判的东西**存在**吗？"

f10.3 起（2026-09-20，三次核查报告触发）：⑪ **"收编共用逻辑"这个动作本身会引入回归 —— 收编时把实现悄悄换掉，比两份拷贝更难发现。**
本次事故：把 `hostpart` 收进 `_egern_common.py` 时，剥 scheme 从「通用剥离 `if "://" in s: split("://",1)[1]`」
退化成「大小写敏感白名单 `("https://", "tls://", ...)`」。于是端点写成 `HTTPS://223.5.5.5/dns-query`
时白名单失配，`HTTPS` 被当成主机名 ⇒ 端点从 IP 字面量误判成待解析域名 ⇒ 同一份配置读数从
**0 high 翻成 9 high**。发布模板端点全是小写所以没暴露；换任何一个大写 scheme 的配置就翻。
⇒ 固化三条：
1. ⭐⭐ **重构"等价改写"必须逐输入对拍，不能只看测试是否还绿。** 测试绿只说明**已覆盖的输入**没变，
   说明不了"改写等价"。写一个把新旧实现按同一批输入逐一对比的脚本（这次是 16 个输入），
   差异为 0 才叫等价。
2. ⭐⭐ **解析器里出现"枚举白名单"就是气味。** `scheme` / 大小写 / 编码这类**输入的表层拼法**，
   不该有能力改变判定结果。凡是要枚举，先问"漏一个会怎样"——这里漏一个就从 0 high 变 9 high。
3. ⭐ **"读到的数字"和"声称的结论"要分开核。** 本轮还发现 README/commit 声称"已加上某物"、
   实际那个文件**从未上传** —— 发布脚本遇到失败会**摘掉该文件继续推**，
   于是"推成功了"和"东西真的在那儿"是两回事。**发布后要用 `git ls-files` 核对交付物，
   而不是相信发布脚本的 commit message。**（换任何一个"声称已交付 X"的场合都成立。）

f10.1 起（2026-09-20，外部审查报告触发）：⑨ **判据本身会随配置演进失效 —— 改配置后必须重跑判据，且改判据要用"双向回归"守住收紧面。**
本次事故：f10 删掉了 15 条 DNS 端点路由规则（依据是 `upstreams` 全是 IP 字面量 ⇒ 不需要路由），**我验证了配置侧、没验证脚本侧** —— 而 `group_reach` 的判据有一半是「至少一个端点判给 `DIRECT`」。删掉那些规则 ⇒ 这半句永远不成立 ⇒ 插件把**自有模板**误判 `3 high`、退出码 1。报告结论准确。
⇒ 固化三条：
1. ⭐ **凡是"判据依赖的对象会被别的改动删掉"的检查，改动后必须重跑。** 判据是**双向**的（A 且 B），只验证其中一端（A）不等于判据成立 —— 这跟坑 3/9/坑 16/17/18 是同一个母题的第 N 次复发：**审计器只能验证你编码进去的假设，而假设会腐烂。**
2. ⭐ **放宽判据必须同时保留收紧面。** 正解是**二选一**（旧判据「≥1 端点 DIRECT」**或**新判据「≥1 端点是国内知名解析器 IP」），**不是**「端点全为 IP 即充分」（那会回退到坑 13 的 f5 事故：全境外 IP 组被误判安全）。改完用三份合成 profile 做**双向回归**：全境外 IP → 必须 HIGH；主机名端点 → 必须 HIGH；显式 `ip_cidr→DIRECT` → 必须通过。
3. ⭐ **同一判据有第二份实现时，注释里必须互指。** `audit_dns_forward.py` 的 `endpoint_route`/`direct_ips` 与 `check_egern_dns.py` 的 `group_reach` 是同一判据的两个副本 —— 只改一处就会让两个脚本给出**相反**结论（比没有脚本更糟）。改判据 = 两处一起改 + 两个脚本一起复跑。

**配套的发布脚本卫生**：dry-run 一定要**逐条看文件清单** —— 本轮 dry-run 才发现会把 `__pycache__/*.pyc` 推上去（`os.walk` 型发布脚本的常客），必须靠剪枝 + 后缀过滤拦掉；远端历史残留（改名前的旧文件、误提交的字节码）要用 `sha: None` 的 tree 条目删除。另：`probe_doh.py` 与 `probe_dns_endpoints.py` 的**证书校验开关必须一致**（单个脚本偷偷关校验 ⇒ 测不出"证书不覆盖该 IP"这类真问题；需要关时必须显式 `--no-verify` 且打印警示）。

实测基准（同一份机场模板；f1→f7 三天内迭代。数字均为**当前判据**下、同一天复跑所得）：

| 版本 | `check_egern_dns.py` | `audit_ruleset_noresolve.py` | 关键问题 |
|---|---|---|---|
| 原始配置 | **5 high** / 13 low / 3 ok | **HIGH**（`Apple_All.list` 13 条） | `Foreign-DNS` 两个主机名端点；兜底组不安全；两个 latency 域名落兜底；规则集强制解析 |
| f1（我第一版） | 3 high / 8 low / 12 ok | HIGH | 同上；另私自加了 `proxy_nameservers`，把泄露从"偶发"变成"确定" |
| f3 | 3 high / 3 low / 16 ok | HIGH | 兜底组依赖代理 + 两个 latency 域名仍落兜底 |
| f4 | 2 high / 2 low / 19 ok | HIGH | 兜底组依赖代理 |
| f5 | **1 high** / 2 low / 35 ok | HIGH | **兜底组依赖代理** |
| f6 | 0 high / 2 low / 37 ok | **HIGH** ← 假安心 | 兜底已修，但 **`Apple_All.list` 的强制解析还在**；用户实测仍报 `upstream: bootstrap` |
| **f7** | **0 high** / 3 low / 43 ok | **OK（20/20）** | — 但 **分流坏了**：国内域名 7/15 落 Final（该维度当时还没有脚本，见 f8） |
| **f8** | **0 high** / 3 low / 43 ok | **OK（20/20）** | — （`ChinaMax.list` → `ChinaMax_All_No_Resolve.list`；分流 15/15 DIRECT、境外无误判） |
| **f9** | **0 high** / 3 low / 43 ok | **OK（20/20）** | — （删顶层 `mitm` 段；与 f8 **三项审计逐字相同**，纯删除不动 DNS/分流） |
| **f10** | **0 high** / 3 low / 43 ok | **OK（19/19）** | — （`forward` 10 条 → 2 条兜底，删掉 8 条结构性冗余；`dns` 与节点域名耦合 4 → 0。规则集数 20 → 19 是因为不再引用 `ChinaDomain.list`。四项审计中前三项与 f9 完全一致，`audit_dns_forward.py` 新增通过） |

⚠️ f1/f2/f3/f5 的 `0 high` **全是假安心**：f1/f2 靠加 `proxy_nameservers` 把 HIGH 压下去（代价是把泄露从偶发变成确定）；f3 是审计盲区（脚本没看 latency 域名）；**f5 是判据不足（"路由确定"被当成了"不依赖代理"）**；**f6 是审计维度缺失（只看 profile、不看它引用的规则集）**。**审计通过 ≠ 没有泄露 —— 必须回到机制层推导 + 按链路做实测（见"定位泄露到运营商"一节）。**
