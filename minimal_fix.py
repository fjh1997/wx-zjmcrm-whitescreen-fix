# -*- coding: utf-8 -*-
"""
最简修复：一站式订单详情白屏

根因（对照实验）：
  前端: customerOrderId = aesEncrypt(订单号)  → 32 位 Hex
  网关: 按原始字符串 length ≤ 14 校验
  结果: retCode -9999 → 无 order → 白屏
  明文 14 位订单号 → retCode 200

本脚本只做两件事（够用）：
  1) 改写 QRY_RBOSS_MOBILE_DETAIL 请求体为明文 ≤14
  2) 热补 oneStationUser.js 里那一行 aesEncrypt 组参（可选，有缓存时更稳）

用法:
  mitmdump -p 8888 -s minimal_fix.py --ssl-insecure --set block_global=false
  ProxyBridge: Weixin.exe;WeChatAppEx.exe → 127.0.0.1:8888
"""
from mitmproxy import http
import json, re, time, os

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "minimal_fix.log")
# 可选兜底订单号（列表里看到的 14 位）；也可环境变量 ZJ_ORDER_ID
ORDER_FALLBACK = os.environ.get("ZJ_ORDER_ID", "")
AES_KEY = os.environ.get("ZJ_AES_KEY", "21dab857ae3ac48ebc1f74fbc47b0ae6")


def _log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _aes_dec(hex_ct: str) -> str:
    try:
        from Crypto.Cipher import AES
        if not re.fullmatch(r"[0-9A-Fa-f]{32,}", hex_ct or ""):
            return ""
        key = bytes.fromhex(AES_KEY)
        pt = AES.new(key, AES.MODE_ECB).decrypt(bytes.fromhex(hex_ct))
        pad = pt[-1]
        if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
            pt = pt[:-pad]
        return pt.decode("utf-8")
    except Exception:
        return ""


def _to_plain(v: str) -> str:
    v = (v or "").strip()
    if re.fullmatch(r"\d{10,14}", v):
        return v[:14]
    if re.fullmatch(r"[0-9A-Fa-f]{32,}", v):
        d = _aes_dec(v)
        if re.fullmatch(r"\d{0,14}", d or ""):
            return d or ""
        return ORDER_FALLBACK[:14] if ORDER_FALLBACK else ""
    return v[:14] if len(v) > 14 else v


def request(flow: http.HTTPFlow):
    url = flow.request.pretty_url or ""
    if "QRY_RBOSS_MOBILE_DETAIL" not in url:
        return
    try:
        raw = flow.request.get_text(strict=False) or ""
        if not raw.strip().startswith("{"):
            return
        body = json.loads(raw)
    except Exception:
        return

    pre = _to_plain(str(body.get("preOrderId") or ""))
    cust = _to_plain(str(body.get("customerOrderId") or body.get("orderId") or ""))
    if not cust and ORDER_FALLBACK:
        cust = ORDER_FALLBACK[:14]
    if len(pre) > 14:
        pre = ""
    if len(cust) > 14:
        cust = cust[:14]

    new = {
        "preOrderId": pre or "",
        "regionId": str(body.get("regionId") or "579"),
        "customerOrderId": cust,
    }
    text = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
    if text != raw.strip():
        flow.request.set_text(text)
        flow.request.headers["Content-Length"] = str(len(text.encode("utf-8")))
        _log(f"PLAIN {text}")


def response(flow: http.HTTPFlow):
    """可选：把源码里的 aesEncrypt 组参改成明文，减少对请求改写的依赖。"""
    if not flow.response:
        return
    url = flow.request.pretty_url or ""
    if "oneStationUser.js" not in url:
        return
    try:
        body = flow.response.get_text(strict=False) or ""
    except Exception:
        return
    if "oneStationDetail" not in body or "/*MINIMAL_PLAIN_FIX*/" in body:
        return

    # 最简一行逻辑：不要 aesEncrypt
    old = re.compile(
        r'"preOrderId"\s*:\s*aesEncrypt\(\s*PRE_ORDER_ID\s*\)\s*,\s*'
        r'"regionId"\s*:\s*REGION_ID\s*,\s*'
        r'"customerOrderId"\s*:\s*aesEncrypt\(\s*CUST_ORDER_ID\s*\)',
        re.S,
    )
    new = (
        '"preOrderId": (PRE_ORDER_ID||"").length>14?"":(PRE_ORDER_ID||""), '
        '"regionId": REGION_ID, '
        '"customerOrderId": (function(){var c=CUST_ORDER_ID||ORDER_ID||"";'
        "if(c.length>14)c=c.slice(0,14);return c;})()"
    )
    body2, n = old.subn(new, body, count=1)
    if not n:
        _log("WARN: param pattern not found (request rewrite still works)")
        return

    # 防止 -9999 时还去读 json.order.length 抛错
    body2 = body2.replace(
        "if(status){",
        'if(status && json && (json.retCode==200||json.retCode=="200"||(json.order&&json.order.length))){',
        1,
    )
    body2 = "/*MINIMAL_PLAIN_FIX*/\n" + body2
    flow.response.set_text(body2)
    flow.response.headers["cache-control"] = "no-store"
    _log("patched oneStationUser.js showOrder → plain ids")


def load(l):
    open(LOG, "w", encoding="utf-8").write(
        f"start {time.strftime('%Y-%m-%d %H:%M:%S')} minimal plain≤14 fix\n"
    )
    _log("minimal_fix ready: DETAIL body → 14-digit plain (root fix only)")
