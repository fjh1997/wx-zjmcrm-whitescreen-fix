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

```powershell
pip install mitmproxy pycryptodome

$env:ZJ_ORDER_ID = "你的14位订单号"
# 可选：$env:ZJ_AES_KEY = "从 GET_STATIC_DATA 拿到的密钥"

mitmdump -p 8888 -s .\minimal_fix.py --ssl-insecure --set block_global=false
# ProxyBridge：Weixin.exe / WeChatAppEx.exe → 127.0.0.1:8888
```

插件会：

1. 拦截 `QRY_RBOSS_MOBILE_DETAIL`，body 改为明文 ≤14  
2. 热补 `oneStationUser.js`，去掉组参时的 `aesEncrypt`  

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
| `start_proxybridge.ps1` / `run_pb_admin.ps1` | 进程代理参考 |
| 其它脚本 | 可选扩展，一般不需要 |

## License

MIT。仅供自有账号排障学习。
