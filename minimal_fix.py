# -*- coding: utf-8 -*-
"""
浙江移动宽带「一站式订单」详情白屏 — 最简 mitm 修复

根因：前端 aesEncrypt 后提交 32 位 Hex 订单号，网关按原始字符串 length≤14 校验。
修复：详情请求改为 ≤14 位数字明文；热补 oneStationUser.js 同步去掉 aesEncrypt 组参。

用法（Windows 推荐用 start_minimal.ps1，保证环境变量传入）:
  mitmdump -p 8888 -s minimal_fix.py --ssl-insecure --set block_global=false
  ProxyBridge（管理员）: Weixin.exe;WeChatAppEx.exe → 127.0.0.1:8888

可选环境变量:
  ZJ_ORDER_ID  14 位订单号（解密失败时的兜底；强烈建议设置）
  ZJ_AES_KEY   URL/字段密文解密密钥（来自 GET_STATIC_DATA）
  ZJ_REGION    地市编码，默认 579

验收: minimal_fix.log 出现 "DETAIL body -> plain ..." 才算改写生效。
"""
from mitmproxy import http
import json, re, time, os

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "minimal_fix.log")
BEST = os.path.join(DIR, "live_best.json")

ORDER_PLAIN = os.environ.get("ZJ_ORDER_ID", "").strip()
REGION = os.environ.get("ZJ_REGION", "579").strip() or "579"
AES_KEY = os.environ.get("ZJ_AES_KEY", "").strip()


def _log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _aes_dec(hex_ct: str) -> str:
    if not AES_KEY:
        return ""
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


def _to_plain_order(v: str) -> str:
    """密文 / 杂串 → 10~14 位数字明文。"""
    v = (v or "").strip()
    if re.fullmatch(r"\d{10,14}", v):
        return v[:14]
    if re.fullmatch(r"[0-9A-Fa-f]{32,}", v):
        d = _aes_dec(v)
        if re.fullmatch(r"\d{10,14}", d or ""):
            return d[:14]
    return (ORDER_PLAIN or "")[:14]


def _is_detail(url: str, raw_body: str = "") -> bool:
    u = (url or "").upper()
    if "QRY_RBOSS_MOBILE_DETAIL" in u:
        return True
    # 少数情况 action 只在 body / 查询串变体里
    return "QRY_RBOSS_MOBILE_DETAIL" in (raw_body or "").upper()


def request(flow: http.HTTPFlow):
    url = flow.request.pretty_url or ""
    try:
        raw = flow.request.get_text(strict=False) or ""
    except Exception:
        raw = ""

    # 按 action 命中，不依赖 host 域名（微信侧有时显示为纯 IP）
    if not _is_detail(url, raw):
        return

    try:
        body = json.loads(raw) if raw.strip().startswith("{") else {}
    except Exception:
        body = {}

    pre_raw = str(body.get("preOrderId") or "")
    pre = ""
    if re.fullmatch(r"\d{0,14}", pre_raw):
        pre = pre_raw
    elif re.fullmatch(r"[0-9A-Fa-f]{32,}", pre_raw):
        d = _aes_dec(pre_raw)
        if re.fullmatch(r"\d{0,14}", d or ""):
            pre = d

    cust = _to_plain_order(str(body.get("customerOrderId") or body.get("orderId") or ""))
    if not cust:
        _log("WARN: no plain order id; set env ZJ_ORDER_ID=你的14位订单号")
        return

    new = {
        "preOrderId": pre or "",
        "regionId": str(body.get("regionId") or REGION),
        "customerOrderId": cust,
    }
    text = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
    flow.request.set_text(text)
    flow.request.headers["Content-Length"] = str(len(text.encode("utf-8")))
    _log(f"DETAIL body -> plain {text}")


def response(flow: http.HTTPFlow):
    if not flow.response:
        return
    url = flow.request.pretty_url or ""
    path = flow.request.path or ""

    try:
        rb = flow.response.get_text(strict=False) or ""
    except Exception:
        rb = ""

    if _is_detail(url) and flow.request.method == "POST":
        bad = "maximum length" in rb or '"retCode":"-9999"' in rb.replace(" ", "")
        good = False
        try:
            j = json.loads(rb)
            good = bool(j.get("order")) and j.get("retCode") in (200, "200")
            _log(
                f"DETAIL resp retCode={j.get('retCode')} "
                f"order_nodes={len(j.get('order') or [])}"
            )
        except Exception:
            pass
        if (bad or not good) and os.path.exists(BEST):
            try:
                best = json.load(open(BEST, encoding="utf-8"))
                resp = best.get("resp") or best
                if isinstance(resp, dict) and resp.get("order"):
                    resp = dict(resp)
                    resp["retCode"] = "200"
                    flow.response.set_text(json.dumps(resp, ensure_ascii=False))
                    flow.response.headers["content-type"] = "application/json;charset=UTF-8"
                    _log("DETAIL fail -> inject live_best.json")
            except Exception as e:
                _log(f"inject fail: {e}")
        return

    # JS 热补：按路径名命中，不强制 host 含 chinamobile（IP 访问时 pretty_host 是数字）
    if "oneStationUser.js" not in url and "oneStationUser.js" not in path:
        return
    if "oneStationDetail" not in rb and "showOrder" not in rb and "CUST_ORDER_ID" not in rb:
        return
    if "/*MINIMAL_PLAIN_FIX*/" in rb:
        return

    key_line = (
        f"window.AESKey=window.AESKey||'{AES_KEY}';\n"
        if AES_KEY
        else "window.AESKey=window.AESKey||'';\n"
    )
    body = "/*MINIMAL_PLAIN_FIX*/\n" + key_line + "try{AESKey=window.AESKey;}catch(e){}\n" + rb

    order_js = ORDER_PLAIN or ""
    pat = re.compile(
        r'"preOrderId"\s*:\s*aesEncrypt\(\s*PRE_ORDER_ID\s*\)\s*,\s*'
        r'"regionId"\s*:\s*REGION_ID\s*,\s*'
        r'"customerOrderId"\s*:\s*aesEncrypt\(\s*CUST_ORDER_ID\s*\)',
        re.S,
    )
    repl = f'"preOrderId":"","regionId":REGION_ID,"customerOrderId":"{order_js}"'
    body2, n = pat.subn(repl, body, count=1)
    if n:
        body = body2
        _log("patched showOrder: plain order id")
    else:
        body2, _ = re.subn(r"aesEncrypt\(\s*PRE_ORDER_ID\s*\)", '""', body, count=1)
        body3, n2 = re.subn(
            r"aesEncrypt\(\s*CUST_ORDER_ID\s*\)",
            f'"{order_js}"' if order_js else "CUST_ORDER_ID",
            body2,
            count=1,
        )
        if n2:
            body = body3
            _log("patched aesEncrypt calls -> plain")

    marker = 'srvMap.get("oneStationDetail")'
    idx = body.find(marker)
    if idx >= 0:
        sub = body[idx : idx + 400]
        if "json.retCode" not in sub:
            body = (
                body[:idx]
                + sub.replace(
                    "if(status){",
                    'if(status&&json&&(json.retCode==200||json.retCode=="200"||(json.order&&json.order.length))){',
                    1,
                )
                + body[idx + 400 :]
            )

    body = body.replace(
        "preTimeAndTimeAreaJS = require('rboss/broadband/js/showPreTimeAndTimeAreaNew.js');",
        "cache.isNewPreTimeArea=false;",
    )

    flow.response.set_text(body)
    flow.response.headers["cache-control"] = "no-store, no-cache"
    _log("rewrote oneStationUser.js")


def load(l):
    open(LOG, "w", encoding="utf-8").write(f"start {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    if not ORDER_PLAIN:
        _log(
            "ready: plain order ≤14; WARN ZJ_ORDER_ID unset "
            "(set before start if AES decrypt unavailable)"
        )
    else:
        _log(f"ready: force plain order id ≤14 (ZJ_ORDER_ID={ORDER_PLAIN})")
