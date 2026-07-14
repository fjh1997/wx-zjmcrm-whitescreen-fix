# 浙江移动宽带「一站式订单」详情白屏 — 最简修复

列表有订单，点「查看进度」详情白屏。

## 原因

详情接口 `QRY_RBOSS_MOBILE_DETAIL` 要求 `customerOrderId` **原始字符串长度 ≤ 14**。  
前端却 `aesEncrypt` 后提交 **32 位 Hex** → `retCode -9999` → 没有进度数据 → 白屏。

| 请求体 | 结果 |
|--------|------|
| 32 位密文 | `-9999` maximum length of 14 |
| **14 位明文** | `200` + `order` 进度 |

```text
订单号(14位) --aesEncrypt--> 32Hex --POST--> 网关拒收(length>14) --> 白屏
订单号(14位) --明文提交------> 网关接受 --> 正常显示
```

## 最简修复

**只让详情接口收到 ≤14 位明文订单号。**

### 源码（若能改）

```javascript
// 改前
"customerOrderId": aesEncrypt(CUST_ORDER_ID)

// 改后
"customerOrderId": CUST_ORDER_ID   // 已是 ≤14 明文时
```

### 无源码（mitm）

```powershell
pip install mitmproxy pycryptodome
mitmdump -p 8888 -s .\minimal_fix.py --ssl-insecure --set block_global=false
# ProxyBridge: Weixin.exe / WeChatAppEx.exe → 127.0.0.1:8888
```

可选：`$env:ZJ_ORDER_ID="你的14位订单号"`

`minimal_fix.py` 会：

1. 把 `QRY_RBOSS_MOBILE_DETAIL` 的 body 改成明文 ≤14  
2. （可选）热补 `oneStationUser.js` 去掉组参时的 `aesEncrypt`

## 目录

| 文件 | 说明 |
|------|------|
| **`minimal_fix.py`** | **推荐：最简 mitm 修复** |
| `live_fuzz_addon.py` | 完整版（含模块兜底等，一般不需要） |
| `js_modules/` | 完整版用的 JS 缓存 |
| `start_proxybridge.ps1` 等 | 代理启停参考 |

## License

MIT。业务站点脚本版权归原厂。仅供自有账号排障学习。
