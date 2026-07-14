from pathlib import Path
# -*- coding: utf-8 -*-
"""
浙江移动 一站式订单详情 — mitm 修复 v6

Fixes:
1) DETAIL API: force PLAINTEXT order ids (max 14) — proven retCode 200
2) showPreTimeAndTimeAreaNew.js "module was broken":
   - Server often returns empty body without proper cookie/path
   - Inject cached full module when response empty/short/HTML error
   - Patch oneStationUser.js to NEVER require New.js (use old module)
   - Wrap dynamic require in try/catch so init cannot hard-fail
"""
from mitmproxy import http
import json, os, re, time, urllib.request, ssl

DIR = str(Path(__file__).resolve().parent)
OUT = os.path.join(DIR, "flows.jsonl")
LOG = os.path.join(DIR, "capture.log")
STORE = os.path.join(DIR, "session_store.json")
BEST = os.path.join(DIR, "live_best.json")
FUZZLOG = os.path.join(DIR, "live_fuzz.log")
JS_DIR = os.path.join(DIR, "js_modules")

AES_KEY = "YOUR_AES_KEY_HEX_FROM_STATIC_DATA"
ORDER_PLAIN = "YOUR_14_DIGIT_ORDER_ID"
REGION = "579"

# local module fallbacks (downloaded with valid session)
MODULE_FALLBACKS = {
    "showPreTimeAndTimeAreaNew.js": os.path.join(JS_DIR, "showPreTimeAndTimeAreaNew.js"),
    "showPreTimeAndTimeArea.js": os.path.join(JS_DIR, "showPreTimeAndTimeArea.js"),
    "chooseScheduledTime.js": os.path.join(JS_DIR, "chooseScheduledTime.js"),
    "jquery.countdown.js": os.path.join(JS_DIR, "jquery.countdown.js"),
}


def _log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    for p in (LOG, FUZZLOG):
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def _dump(obj):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _safe_text(msg):
    try:
        return (msg.get_text(strict=False) or "")[:30000]
    except Exception:
        return ""


def _read_fallback(name: str) -> str | None:
    path = MODULE_FALLBACKS.get(name)
    if not path or not os.path.exists(path):
        # try net_ prefix
        alt = os.path.join(JS_DIR, "net_" + name)
        path = alt if os.path.exists(alt) else path
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            t = f.read()
        if "define" in t and len(t) > 500:
            return t
    except Exception as e:
        _log(f"fallback read fail {name}: {e}")
    return None


def _aes_dec(hex_ct: str) -> str | None:
    try:
        from Crypto.Cipher import AES
    except Exception:
        return None
    try:
        if not re.fullmatch(r"[0-9A-Fa-f]+", hex_ct or "") or len(hex_ct) % 32 != 0:
            return None
        key = bytes.fromhex(AES_KEY)
        pt = AES.new(key, AES.MODE_ECB).decrypt(bytes.fromhex(hex_ct))
        pad = pt[-1]
        if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
            pt = pt[:-pad]
        return pt.decode("utf-8")
    except Exception:
        return None


def _save_session(flow: http.HTTPFlow):
    host = flow.request.pretty_host or ""
    if "chinamobile.com" not in host and "10086.cn" not in host:
        return
    cookie = flow.request.headers.get("Cookie", "") or flow.request.headers.get("cookie", "")
    ua = flow.request.headers.get("User-Agent", "")
    referer = flow.request.headers.get("Referer", "")
    origin = flow.request.headers.get("Origin", "")
    prev = {}
    if os.path.exists(STORE):
        try:
            with open(STORE, "r", encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = {}
    jar_map = {}
    for part in ((prev.get("cookie") or "") + "; " + cookie).split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            jar_map[k.strip()] = v.strip()
    data = {
        "cookie": "; ".join(f"{k}={v}" for k, v in jar_map.items() if k),
        "user_agent": ua or prev.get("user_agent", ""),
        "referer": referer or prev.get("referer", ""),
        "origin": origin or prev.get("origin", "") or f"https://{host}",
        "last_url": (flow.request.pretty_url or "")[:500],
        "ts": time.time(),
    }
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _to_plain_id(val: str, fallback: str = "") -> str:
    v = (val or "").strip()
    if not v:
        return fallback
    if re.fullmatch(r"\d{10,14}", v):
        return v[:14]
    dec = _aes_dec(v)
    if dec is not None:
        if re.fullmatch(r"\d{0,14}", dec or ""):
            return dec
        if len(dec) <= 14:
            return dec
    if re.fullmatch(r"[0-9A-Fa-f]{32,}", v):
        return fallback
    return v[:14] if len(v) > 14 else v


def _rewrite_detail_to_plain(flow: http.HTTPFlow):
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

    pre = _to_plain_id(str(body.get("preOrderId") or ""), "")
    cust = _to_plain_id(str(body.get("customerOrderId") or body.get("orderId") or ""), ORDER_PLAIN)
    if not cust:
        cust = ORDER_PLAIN
    if len(cust) > 14:
        cust = cust[:14]
    if len(pre) > 14:
        pre = ""

    region = body.get("regionId") or REGION
    new = {
        "preOrderId": pre or "",
        "regionId": str(region),
        "customerOrderId": cust,
    }
    new_text = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
    if new_text != raw.strip():
        flow.request.set_text(new_text)
        flow.request.headers["Content-Length"] = str(len(new_text.encode("utf-8")))
        _log(f"DETAIL -> PLAIN {new_text}")
        _dump({"type": "rewrite_plain", "from": body, "to": new, "url": url[:300]})


def _body_looks_broken(text: str) -> bool:
    if not text or len(text.strip()) < 50:
        return True
    t = text.lstrip()
    if t.startswith("<!DOCTYPE") or t.startswith("<html") or "无法访问" in text:
        return True
    if "define" not in text and "module.exports" not in text and "function" not in text[:200]:
        return True
    return False


def _inject_js_module(flow: http.HTTPFlow) -> bool:
    """If busi JS module response is empty/broken, inject local good copy."""
    url = flow.request.pretty_url or ""
    if ".js" not in url or "chinamobile.com" not in (flow.request.pretty_host or ""):
        return False
    # match module filenames
    name = None
    for key in MODULE_FALLBACKS:
        if key in url:
            name = key
            break
    if not name:
        # still catch empty broadband js
        if "/rboss/broadband/js/" in url or "/busi/rboss/broadband/js/" in url:
            base = url.split("?")[0].rstrip("/").split("/")[-1]
            if base.endswith(".js"):
                name = base
        else:
            return False

    try:
        text = flow.response.get_text(strict=False) or ""
    except Exception:
        text = ""

    # also cache good responses for future
    if not _body_looks_broken(text) and name:
        try:
            os.makedirs(JS_DIR, exist_ok=True)
            path = os.path.join(JS_DIR, name)
            if (not os.path.exists(path)) or os.path.getsize(path) < len(text):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                _log(f"cached good module {name} len={len(text)}")
        except Exception:
            pass
        return False

    fb = _read_fallback(name) if name else None
    if not fb:
        # New broken -> use old as stand-in (same exports shape)
        if name == "showPreTimeAndTimeAreaNew.js":
            fb = _read_fallback("showPreTimeAndTimeArea.js")
            if fb:
                _log("New.js broken -> using OLD showPreTimeAndTimeArea.js as fallback content")
    if not fb:
        _log(f"module broken but no fallback: {name or url[:80]} resp_len={len(text)}")
        return False

    flow.response.status_code = 200
    flow.response.set_text(fb)
    flow.response.headers["content-type"] = "application/javascript; charset=utf-8"
    flow.response.headers["cache-control"] = "no-store, no-cache"
    flow.response.headers["content-length"] = str(len(fb.encode("utf-8")))
    _log(f"INJECT module {name} len={len(fb)} (was broken/empty len={len(text)})")
    _dump({"type": "inject_js", "name": name, "url": url[:300], "was_len": len(text), "new_len": len(fb)})
    return True


# ---- oneStationUser.js patches ----
PATCH_INIT = r"""
init:function(){
       var self=this;
       var keyParam = {"extParam": "BROADBAND_ORDER_QRY_AES_KEY"};
       window.AESKey = window.AESKey || "YOUR_AES_KEY_HEX_FROM_STATIC_DATA";
       var afterKey = function() {
           try {
               window.AESKey = window.AESKey || "YOUR_AES_KEY_HEX_FROM_STATIC_DATA";
               try { AESKey = window.AESKey; } catch (e0) {}
               PRE_ORDER_ID = Request("PRE_ORDER_ID") || "";
               CUST_ORDER_ID = Request("CUST_ORDER_ID") || "";
               ORDER_ID = Request("ORDER_ID") || "";
               var skipRegex = /^57[0-9]|^580/;
               if (PRE_ORDER_ID && !skipRegex.test(PRE_ORDER_ID)) {
                   try { PRE_ORDER_ID = aesDecrypt(PRE_ORDER_ID); } catch (e1) { PRE_ORDER_ID = ""; }
               }
               if (CUST_ORDER_ID && !skipRegex.test(CUST_ORDER_ID)) {
                   try { CUST_ORDER_ID = aesDecrypt(CUST_ORDER_ID); } catch (e2) {}
               }
               if (ORDER_ID && !skipRegex.test(ORDER_ID)) {
                   try { ORDER_ID = aesDecrypt(ORDER_ID); } catch (e3) {}
               }
               if (PRE_ORDER_ID && PRE_ORDER_ID.length > 14) PRE_ORDER_ID = "";
               if (CUST_ORDER_ID && CUST_ORDER_ID.length > 14) {
                   if (ORDER_ID && ORDER_ID.length <= 14) CUST_ORDER_ID = ORDER_ID;
                   else CUST_ORDER_ID = CUST_ORDER_ID.slice(0,14);
               }
               console.log("[FIX v6] PRE", PRE_ORDER_ID, "CUST", CUST_ORDER_ID, "city", Request("city"));
               // do NOT let time-area module crash detail page
               try { self.qryTimeAreaConfig(Request("city")); } catch (eT) { console.warn("[FIX] qryTimeAreaConfig", eT); }
               self.showOrder();
           } catch (e) {
               console.error("[FIX] init", e);
               try { showInfo("订单初始化失败: " + (e && e.message ? e.message : e)); } catch (e6) {}
           }
       };
       var applyKeyFromJson = function(json, status) {
           if (status && json && json.staticDatas && json.staticDatas.length > 0) {
               for (var k = 0; k < json.staticDatas.length; k++) {
                   if (json.staticDatas[k].codeValue == "01") {
                       window.AESKey = json.staticDatas[k].codeName;
                       try { AESKey = window.AESKey; } catch (e7) {}
                       break;
                   }
               }
           }
           if (!window.AESKey) window.AESKey = "YOUR_AES_KEY_HEX_FROM_STATIC_DATA";
           try { AESKey = window.AESKey; } catch (e10) {}
           afterKey();
       };
       try {
           if (Rose && Rose.ajax && Rose.ajax.postJson) {
               Rose.ajax.postJson(srvMap.get("getStaticData"), keyParam, applyKeyFromJson);
           } else {
               applyKeyFromJson(null, false);
           }
       } catch (e) { applyKeyFromJson(null, false); }
       },
"""

PATCH_PARAM = (
    'var param={\n'
    '\t\t\t    "preOrderId": (PRE_ORDER_ID && PRE_ORDER_ID.length<=14) ? PRE_ORDER_ID : "",\n'
    '\t\t\t    "regionId" : REGION_ID,\n'
    '\t\t\t    "customerOrderId" : (function(){ var c=CUST_ORDER_ID||ORDER_ID||""; if(c.length>14) c=c.slice(0,14); return c; })()\n'
    '\t\t\t };'
)

# Force use old time-area module; never load New.js (broken empty responses)
PATCH_QRY_TIME = r"""
	   qryTimeAreaConfig:function(regionId){
		   cache.isNewPreTimeArea = false;
		   // FIX v6: skip dynamic require of showPreTimeAndTimeAreaNew.js (often empty -> "module was broken")
		   // keep preTimeAndTimeAreaJS from top-level require(showPreTimeAndTimeArea.js)
		   try {
			   var param = {
				   paraType: "TIME_AREA_CONFIG",
				   paraCode: "TIME_AREA_CONFIG",
				   regionId: regionId
			   };
			   if (Rose && Rose.ajax && Rose.ajax.postJsonSync) {
				   Rose.ajax.postJsonSync(srvMap.get('getParaDetail'), param, function(json, status) {
					   // ignore switch to New.js
					   cache.isNewPreTimeArea = false;
				   });
			   }
		   } catch (e) {
			   console.warn("[FIX v6] qryTimeAreaConfig soft-fail", e);
			   cache.isNewPreTimeArea = false;
		   }
	   },
"""


def patch_js(body: str) -> str:
    if "/*WX_WHITE_SCREEN_FIX_V6*/" in body:
        return body
    body = "/*WX_WHITE_SCREEN_FIX_V6*/\nwindow.AESKey = window.AESKey || 'YOUR_AES_KEY_HEX_FROM_STATIC_DATA';\n" + body

    m = re.search(
        r"init\s*:\s*function\s*\(\s*\)\s*\{.*?\},\s*\n\s*qryAESKey\s*:\s*function",
        body,
        re.S,
    )
    if m:
        body = body[: m.start()] + PATCH_INIT + "\n   qryAESKey:function" + body[m.end() :]
        _log("patched init v6")

    # replace qryTimeAreaConfig block entirely
    m2 = re.search(
        r"qryTimeAreaConfig\s*:\s*function\s*\(\s*regionId\s*\)\s*\{.*?\},\s*\n\s*juage_oper\s*:",
        body,
        re.S,
    )
    if m2:
        body = body[: m2.start()] + PATCH_QRY_TIME + "\n\t   juage_oper:" + body[m2.end() :]
        _log("patched qryTimeAreaConfig v6 (no New.js)")
    else:
        # soft: neuter require of New.js
        body = body.replace(
            "preTimeAndTimeAreaJS = require('rboss/broadband/js/showPreTimeAndTimeAreaNew.js');",
            "/* FIX skip New.js */ try{ /* keep old */ }catch(e){} // preTimeAndTimeAreaJS = require('...New.js');",
        )
        _log("WARN: qryTimeAreaConfig block not found, used string neuter")

    body2, n = re.subn(
        r'var\s+param\s*=\s*\{\s*"preOrderId"\s*:\s*aesEncrypt\(\s*PRE_ORDER_ID\s*\)\s*,\s*"regionId"\s*:\s*REGION_ID\s*,\s*"customerOrderId"\s*:\s*aesEncrypt\(\s*CUST_ORDER_ID\s*\)\s*\}\s*;',
        PATCH_PARAM,
        body,
        count=1,
        flags=re.S,
    )
    if n:
        body = body2
        _log("patched showOrder param -> PLAINTEXT v6")
    else:
        _log("WARN: showOrder param not found")

    # showOrder calls qryTimeAreaConfig — already safe; also guard inside showOrder duplicate call
    body = body.replace(
        "self.qryTimeAreaConfig(REGION_ID);",
        "try{ self.qryTimeAreaConfig(REGION_ID); }catch(eQ){ console.warn('[FIX] qryTimeArea',eQ); }",
    )

    body = body.replace(
        "Rose.ajax.postJson(srvMap.get(\"oneStationDetail\"), param, function(json, status) {\n     if(status){",
        "Rose.ajax.postJson(srvMap.get(\"oneStationDetail\"), param, function(json, status) {\n"
        "     if(status && json && (json.retCode==200 || json.retCode==\"200\" || json.order)){",
    )
    body = body.replace(
        "for(var i=0;i<json.order.length;i++){",
        "if(!json||!json.order||!json.order.length){ try{$(\"#ui-loader\").hide();}catch(e){} try{showInfo((json&&(json.retMessage||json.userMsg||json.msg))||\"订单详情为空\");}catch(e){} return; }\n"
        "     for(var i=0;i<json.order.length;i++){",
    )

    safe_encrypt = (
        "function aesEncrypt(data) {\n"
        "  if (!window.AESKey) { window.AESKey='YOUR_AES_KEY_HEX_FROM_STATIC_DATA'; }\n"
        "  var key = CryptoJS.enc.Hex.parse(window.AESKey);\n"
        "  var srcs = CryptoJS.enc.Utf8.parse(data || '');\n"
        "  var encrypted = CryptoJS.AES.encrypt(srcs, key, {iv:'',mode:CryptoJS.mode.ECB,padding:CryptoJS.pad.Pkcs7});\n"
        "  return encrypted.ciphertext.toString().toUpperCase();\n"
        "}"
    )
    safe_decrypt = (
        "function aesDecrypt(encrypted) {\n"
        "  if (!window.AESKey) { window.AESKey='YOUR_AES_KEY_HEX_FROM_STATIC_DATA'; }\n"
        "  var key = CryptoJS.enc.Hex.parse(window.AESKey);\n"
        "  var srcs = CryptoJS.format.Hex.parse(encrypted);\n"
        "  var decrypt = CryptoJS.AES.decrypt(srcs, key, {iv:'',mode:CryptoJS.mode.ECB,padding:CryptoJS.pad.Pkcs7});\n"
        "  return CryptoJS.enc.Utf8.stringify(decrypt);\n"
        "}"
    )
    if re.search(r"function\s+aesEncrypt\s*\(", body):
        body = re.sub(r"function\s+aesEncrypt\s*\([^)]*\)\s*\{.*?\n\}", safe_encrypt, body, count=2, flags=re.S)
    if re.search(r"function\s+aesDecrypt\s*\(", body):
        body = re.sub(r"function\s+aesDecrypt\s*\([^)]*\)\s*\{.*?\n\}", safe_decrypt, body, count=2, flags=re.S)

    # Guard top-level require of time area so page can still define module
    body = body.replace(
        "var preTimeAndTimeAreaJS = require('rboss/broadband/js/showPreTimeAndTimeArea.js');",
        "var preTimeAndTimeAreaJS = (function(){ try { return require('rboss/broadband/js/showPreTimeAndTimeArea.js'); } catch(e){ console.warn('[FIX] old timeArea require',e); return {initParam:function(){},init:function(o){if(o&&o.callback)o.callback([]);},showPreTimeAndTimeArea:function(){}}; } })();",
    )

    _log(f"JS patched v6 len={len(body)}")
    return body


def _ssl():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.options |= 0x4
    except Exception:
        pass
    return ctx


def _post(url: str, body: dict, headers: dict) -> tuple[int, str]:
    data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        if v:
            req.add_header(k, v)
    if "Content-Type" not in {x.title(): x for x in headers}:
        req.add_header("Content-Type", "application/json;charset=UTF-8")
    try:
        with urllib.request.urlopen(req, timeout=12, context=_ssl()) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        if hasattr(e, "read"):
            try:
                return getattr(e, "code", 0) or 0, e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
        return 0, f"ERR:{e}"


def _is_good(text: str) -> bool:
    if not text or not text.strip().startswith("{"):
        return False
    try:
        j = json.loads(text)
    except Exception:
        return False
    if not isinstance(j, dict):
        return False
    if "maximum length" in str(j.get("retMessage") or ""):
        return False
    if j.get("order") or (j.get("addressId") is not None and j.get("clock")):
        return True
    rc = j.get("retCode")
    return rc in (200, "200", 0, "0")


def request(flow: http.HTTPFlow):
    url = flow.request.pretty_url or ""
    _save_session(flow)
    if any(x in url for x in ["QRY_RBOSS", "GET_STATIC", "INIT_ORDER", "action=", "BDNewInstall", "oneStation", "showPreTime", "TimeArea"]):
        if "/mmtls/" in url:
            return
        body = _safe_text(flow.request)
        cookie = flow.request.headers.get("Cookie", "")
        _dump({"type": "request", "ts": time.time(), "method": flow.request.method, "url": url[:2000], "body": body[:4000], "cookie_len": len(cookie)})
        _log(f"REQ {flow.request.method} cookie={len(cookie)} {url[:140]}")
        _rewrite_detail_to_plain(flow)


def response(flow: http.HTTPFlow):
    if not flow.response:
        return
    url = flow.request.pretty_url or ""
    host = flow.request.pretty_host or ""

    # merge Set-Cookie
    if "chinamobile.com" in host or "10086.cn" in host:
        sc = []
        try:
            sc = flow.response.headers.get_all("Set-Cookie")
        except Exception:
            v = flow.response.headers.get("Set-Cookie")
            if v:
                sc = [v]
        if sc:
            try:
                prev = {}
                if os.path.exists(STORE):
                    with open(STORE, "r", encoding="utf-8") as f:
                        prev = json.load(f)
                jar = {}
                for part in (prev.get("cookie") or "").split(";"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        jar[k.strip()] = v.strip()
                for c in sc:
                    first = c.split(";", 1)[0]
                    if "=" in first:
                        k, v = first.split("=", 1)
                        jar[k.strip()] = v.strip()
                prev["cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
                prev["ts"] = time.time()
                with open(STORE, "w", encoding="utf-8") as f:
                    json.dump(prev, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    # Inject broken modules FIRST
    if ".js" in url and ("broadband/js" in url or "showPreTime" in url or "TimeArea" in url or "chooseScheduled" in url or "countdown" in url):
        try:
            _inject_js_module(flow)
        except Exception as e:
            _log(f"inject js fail: {e}")

    if "oneStationUser.js" in url and "chinamobile.com" in host:
        try:
            text = flow.response.get_text(strict=False) or ""
            if text and "oneStationDetail" in text:
                flow.response.set_text(patch_js(text))
                flow.response.headers["cache-control"] = "no-store, no-cache"
                _log("rewrote oneStationUser.js v6")
        except Exception as e:
            _log(f"JS rewrite fail: {e}")

    if "QRY_RBOSS_MOBILE_DETAIL" in url:
        body = _safe_text(flow.response)
        _dump({"type": "response", "ts": time.time(), "url": url[:2000], "status": flow.response.status_code, "body": body[:20000]})
        _log(f"RES DETAIL {flow.response.status_code} | {body.replace(chr(10),' ')[:180]}")
        if _is_good(body):
            try:
                j = json.loads(body)
                with open(BEST, "w", encoding="utf-8") as f:
                    json.dump({"source": "live", "url": url, "resp": j}, f, ensure_ascii=False, indent=2)
                _log("saved BEST live DETAIL")
            except Exception:
                pass
            return
        if "maximum length" in body or '"retCode":"-9999"' in body.replace(" ", "") or '"retCode":-9999' in body.replace(" ", ""):
            cookie = flow.request.headers.get("Cookie", "")
            ua = flow.request.headers.get("User-Agent", "")
            referer = flow.request.headers.get("Referer", "")
            origin = flow.request.headers.get("Origin", "") or "https://interzjmcrm.zj.chinamobile.com"
            headers = {
                "User-Agent": ua,
                "Cookie": cookie,
                "Referer": referer,
                "Origin": origin,
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            }
            base = url.split("?")[0]
            variants = [
                {"preOrderId": "", "regionId": REGION, "customerOrderId": ORDER_PLAIN},
                {"regionId": REGION, "customerOrderId": ORDER_PLAIN},
            ]
            for b in variants:
                for q in ("?isconvert=true&action=QRY_RBOSS_MOBILE_DETAIL", "?isconvert=false&action=QRY_RBOSS_MOBILE_DETAIL"):
                    st, text = _post(base + q, b, headers)
                    _log(f"SYNC plain retry st={st} {(text or '')[:100]}")
                    if _is_good(text):
                        flow.response.set_text(text)
                        flow.response.headers["content-type"] = "application/json;charset=UTF-8"
                        try:
                            with open(BEST, "w", encoding="utf-8") as f:
                                json.dump({"source": "sync_retry", "body": b, "resp": json.loads(text)}, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        _log("*** injected successful PLAIN DETAIL")
                        return
            if os.path.exists(BEST):
                try:
                    with open(BEST, "r", encoding="utf-8") as f:
                        best = json.load(f)
                    resp = best.get("resp") or best
                    if isinstance(resp, dict) and resp.get("order"):
                        flow.response.set_text(json.dumps(resp, ensure_ascii=False))
                        flow.response.headers["content-type"] = "application/json;charset=UTF-8"
                        _log("injected cached BEST DETAIL")
                except Exception as e:
                    _log(f"inject best fail: {e}")

    if any(x in url for x in ["GET_STATIC", "INIT_ORDER", "BDNewInstall", "ProcessQry", "action=", "GET_PARA"]):
        if "QRY_RBOSS_MOBILE_DETAIL" in url or "/mmtls/" in url:
            return
        body = _safe_text(flow.response)
        if body.strip().startswith("{"):
            _dump({"type": "response", "ts": time.time(), "url": url[:2000], "status": flow.response.status_code, "body": body[:12000]})
            _log(f"RES {flow.response.status_code} {url[:100]} | {body.replace(chr(10),' ')[:140]}")


def load(l):
    open(OUT, "w", encoding="utf-8").close()
    open(FUZZLOG, "w", encoding="utf-8").close()
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"start {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    # verify fallbacks exist
    for k, p in MODULE_FALLBACKS.items():
        exists = os.path.exists(p) or os.path.exists(os.path.join(JS_DIR, "net_" + k))
        _log(f"fallback {k}: {'OK' if exists else 'MISSING'}")
    _log("FIX v6 ready — inject broken TimeArea JS + skip New.js + PLAIN DETAIL")
