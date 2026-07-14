# 浙江移动宽带「一站式订单」详情白屏 — 最简修复

列表有订单，点「查看进度」详情白屏。

## 原因

详情接口 `QRY_RBOSS_MOBILE_DETAIL` 要求 `customerOrderId` 为 **≤14 位数字明文**。  
前端 `aesEncrypt` 后提交 **32 位 Hex** → 网关 `retCode -9999`（maximum length of 14）→ 无进度 → 白屏。

```text
订单号(14位) --aesEncrypt--> 32Hex --POST--> 网关拒收 --> 白屏
订单号(14位) --明文提交------> 网关接受 --> 正常显示
```

## 修复

让详情接口只收到明文 14 位订单号。

### 源码（若能改前端）

```javascript
// 改前
"customerOrderId": aesEncrypt(CUST_ORDER_ID)

// 改后
"customerOrderId": CUST_ORDER_ID  // 10~14 位数字
```

### 无源码：mitm 插件 `minimal_fix.py`

**依赖：** Python 3.10+、`mitmproxy`、`pycryptodome`、Windows 上可用的进程代理（如 [ProxyBridge](https://github.com/InterceptSuite/ProxyBridge)）。

```powershell
git clone https://github.com/fjh1997/wx-zjmcrm-whitescreen-fix.git
cd wx-zjmcrm-whitescreen-fix
pip install mitmproxy pycryptodome

# 推荐：用脚本启动（保证 ZJ_ORDER_ID 传入 mitmdump）
$env:ZJ_ORDER_ID = "你的14位订单号"   # 必填兜底
# 可选：$env:ZJ_AES_KEY = "从 GET_STATIC_DATA 拿到的密钥"
.\start_minimal.ps1
```

手动启动时请用 **同一 cmd 会话** 设环境变量（`Start-Process` 容易丢 env）：

```powershell
cmd /c "set ZJ_ORDER_ID=你的14位订单号&& mitmdump -p 8888 -s minimal_fix.py --ssl-insecure --set block_global=false"
```

然后：

1. **以管理员身份**启动 ProxyBridge：`Weixin.exe` / `WeChatAppEx.exe` → `http://127.0.0.1:8888`  
   （非管理员会立刻退出，等于没挂代理）
2. 完全退出并重启微信 PC 端  
3. 打开一站式订单 → 查看进度  

插件会：

1. 拦截 `QRY_RBOSS_MOBILE_DETAIL`（**按 action 路径命中，不依赖域名**；IP 访问也能改）  
2. body 改为明文 ≤14  
3. 热补 `oneStationUser.js`，去掉组参时的 `aesEncrypt`  

### 验收（必看）

打开 `minimal_fix.log`，成功时应有：

```text
DETAIL body -> plain {"preOrderId":"","regionId":"579","customerOrderId":"你的14位"}
DETAIL resp retCode=200 order_nodes=...
```

或：

```text
rewrote oneStationUser.js
```

**只有一行 `ready`、没有 `DETAIL body`** → 微信流量没进 mitm（检查 ProxyBridge 是否管理员、是否重启微信）。

### 排障

| 现象 | 原因 | 处理 |
|------|------|------|
| 仍白屏，log 无 DETAIL | 流量未进代理 | 管理员跑 ProxyBridge；杀干净微信再开 |
| log 有 WARN no plain order id | 解不出密文且未设订单号 | 设置 `ZJ_ORDER_ID` 后重启 mitmdump |
| 系统异常 / 请输入正确的 URL | 误改了 Host/CONNECT | **不要**把其它 IP 强行改成 CRM 域名 |
| 偶发 HTTPS/H2 异常 | 微信 UA 尾空格等 | 可试 `--set http2=false`（可选） |
| 证书告警 | 未信任 mitm CA | 安装 `~/.mitmproxy/mitmproxy-ca-cert.cer` 到受信任根证书 |

核心请求改写：

```python
new = {
    "preOrderId": "",
    "regionId": str(body.get("regionId") or "579"),
    "customerOrderId": plain_14_digit_order_id,
}
flow.request.set_text(json.dumps(new, separators=(",", ":")))
```

## 目录

| 文件 | 说明 |
|------|------|
| **`minimal_fix.py`** | 推荐使用的 mitm 脚本 |
| **`start_minimal.ps1`** | 启动 mitmdump（注入 env）+ 提示/拉起 ProxyBridge |
| `start_proxybridge.ps1` / `run_pb_admin.ps1` | 进程代理参考（需管理员） |
| 其它脚本 | 可选扩展，一般不需要 |

## License

MIT。仅供自有账号排障学习。
