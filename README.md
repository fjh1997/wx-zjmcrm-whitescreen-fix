# PC 微信 · 浙江移动宽带「一站式订单」详情白屏修复工具

在 **不使用 Frida** 的前提下，用 **ProxyBridge（进程级强制代理）+ mitmproxy** 抓包并热修复 PC 微信 WebView 中浙江移动宽带进度详情页的白屏问题。

> 仅供个人自有账号排障与技术研究。请勿用于未授权访问。仓库内脚本已去掉真实 Cookie / 订单号 / AES 密钥，使用前请自行替换占位符。

## 现象

- 列表可看到「其它群组组网」等订单
- 点「查看进度」进入「一站式订单查询」后整页白屏（PC / 手机 H5 均可能出现）

## 已验证根因（按优先级）

1. **详情接口字段形态**  
   `QRY_RBOSS_MOBILE_DETAIL` 对 `customerOrderId` 按 **最大 14 字符**校验。  
   前端 `aesEncrypt` 后提交 32 位 Hex 密文 → `retCode -9999`：`strings of this type must have a maximum length of 14`。  
   **明文 14 位订单号**可返回 `retCode 200` 与 `order` 进度节点。

2. **SeaJS 空模块**  
   `showPreTimeAndTimeAreaNew.js` 在无有效会话 Cookie 时经常 **HTTP 200 + body 为空**，SeaJS 报 `module was broken`，打断 `init`。

3. **关于 `AESKey is not defined`**  
   早期逆向曾怀疑模块内外 `AESKey` 作用域问题。实际排查中，**用户侧最初白屏并未报该文案**；该错误多出现在 **mitm 注入补丁** 之后（补丁里对空密钥主动 `throw new Error('AESKey is not defined')`），属于**次生问题**，不宜写成原始根因。

## 架构

```text
WeChatAppEx / Weixin.exe
        │ HTTPS
        ▼
  ProxyBridge（仅代理微信进程）
        │
        ▼
  mitmdump :8888  + live_fuzz_addon.py
        │  · DETAIL body → 明文 14 位
        │  · 禁用/跳过 TimeAreaNew 空模块
        │  · 空 JS 响应注入本地缓存
        ▼
  interzjmcrm.zj.chinamobile.com
```

## 目录

| 文件 | 说明 |
|------|------|
| `live_fuzz_addon.py` | mitm 主插件（与 `fix_whitescreen.py` 同步） |
| `session_bootstrap_fuzz.py` | 用 nonce/encpn bootstrap 会话后 fuzz 详情 API |
| `auto_fuzz.py` | 基于 `session_store.json` 的批量参数探索 |
| `dump_addon.py` | 轻量请求/响应 dump |
| `start_proxybridge.ps1` / `run_pb_admin.ps1` / `stop_capture.ps1` | 代理启停 |
| `js_modules/` | 有效会话下缓存的 TimeArea 等完整 JS（空包时注入） |

## 依赖

- Windows 10/11
- Python 3.10+，`pip install mitmproxy pycryptodome`
- [ProxyBridge](https://github.com/) 或同类进程强制代理（将 Weixin/WeChatAppEx 指到 `127.0.0.1:8888`）
- 已安装 mitm CA 或使用 `--ssl-insecure`（仅调试）

## 快速开始

```powershell
# 1. 安装依赖
pip install mitmproxy pycryptodome

# 2. 启动 mitm（在本仓库目录）
mitmdump -p 8888 -s .\live_fuzz_addon.py --set block_global=false --ssl-insecure

# 3. 另开管理员窗口，用 ProxyBridge 强制 Weixin.exe / WeChatAppEx.exe → 127.0.0.1:8888
#    可参考 start_proxybridge.ps1 / run_pb_admin.ps1（按本机 ProxyBridge 路径修改）

# 4. 完全关闭小程序后重新打开，进入订单 → 查看进度
# 5. 观察 capture.log：应出现 DETAIL -> PLAIN / INJECT module / rewrote oneStationUser.js
```

### 替换占位符

在 `live_fuzz_addon.py` / `session_bootstrap_fuzz.py` 中：

- `YOUR_14_DIGIT_ORDER_ID`：14 位订单号  
- `YOUR_AES_KEY_HEX_FROM_STATIC_DATA`：`GET_STATIC_DATA` 下发的 AES 密钥（仅用于解密 URL 参数 / 本地自检）  
- `YOUR_NONCE` / `YOUR_ENCPN` / `YOUR_SESSION`：从真实列表页 URL 或 LocalStorage 获取（fuzz 用）

### 离线 fuzz

```powershell
# 先把有效 Cookie 写入 session_store.json，或依赖 bootstrap 里的 nonce/encpn
python .\session_bootstrap_fuzz.py
# 成功时生成 live_best.json
```

## 成功响应形态（脱敏）

```json
{
  "retCode": "200",
  "order": [
    { "nodeId": "6", "nodeInfo": [{ "msg": "您的订单已取消", "time": "..." }] },
    { "nodeId": "0", "nodeInfo": [{ "msg": "预约上门...", "time": "..." }] }
  ]
}
```

## License

MIT（脚本与文档）。业务站点 JS 缓存文件版权归原厂，仅作联调兜底，请勿二次分发用于其它用途。
