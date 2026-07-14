from pathlib import Path
# -*- coding: utf-8 -*-
"""
Bootstrap session via captured nonce/encpn/session, then fuzz DETAIL until real data.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
from Crypto.Cipher import AES

DIR = str(Path(__file__).resolve().parent)
OUT = os.path.join(DIR, "bootstrap_fuzz.jsonl")
LOG = os.path.join(DIR, "bootstrap_fuzz.log")
BEST = os.path.join(DIR, "live_best.json")
STORE = os.path.join(DIR, "session_store.json")

AES_KEY = "YOUR_AES_KEY_HEX_FROM_STATIC_DATA"
ORDER = "YOUR_14_DIGIT_ORDER_ID"
REGION = "579"
CUST_ENC = "YOUR_CUST_ORDER_CIPHER_HEX"
PRE_ENC = "YOUR_PRE_ORDER_CIPHER_HEX"

# from WeChat LocalStorage (most recent first)
SESSIONS = [
    {
        "encpn": "YOUR_ENCPN",
        "nonce": "YOUR_NONCE",
        "session": "YOUR_SESSION",
        "cf": "10113",
        "openid": "YOUR_OPENID",
    },
    {
        "encpn": "YOUR_ENCPN",
        "nonce": "YOUR_NONCE",
        "session": "YOUR_SESSION",
        "cf": "10113",
        "openid": "YOUR_OPENID",
    },
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20 "
    "NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF"
)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def dump(obj: dict) -> None:
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def aes_enc(data: str) -> str:
    key = bytes.fromhex(AES_KEY)
    raw = (data or "").encode("utf-8")
    pad = 16 - (len(raw) % 16)
    raw += bytes([pad]) * pad
    return AES.new(key, AES.MODE_ECB).encrypt(raw).hex().upper()


def ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.options |= 0x4
    except Exception:
        pass
    return ctx


class Client:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=ssl_ctx()),
        )

    def cookie_header(self) -> str:
        return "; ".join(f"{c.name}={c.value}" for c in self.cj)

    def request(self, method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 20):
        h = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in h.items():
            if v is not None:
                req.add_header(k, v)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                body = resp.read()
                return resp.status, dict(resp.headers.items()), body, resp.geturl()
        except Exception as e:
            if hasattr(e, "read"):
                try:
                    body = e.read()
                    return getattr(e, "code", 0) or 0, dict(getattr(e, "headers", {}) or {}), body, url
                except Exception:
                    pass
            return 0, {}, str(e).encode(), url


def variants():
    eo, ee = aes_enc(ORDER), aes_enc("")
    return [
        ("official_enc", {"preOrderId": ee, "regionId": REGION, "customerOrderId": eo}),
        ("plain_14", {"preOrderId": "", "regionId": REGION, "customerOrderId": ORDER}),
        ("plain_no_pre", {"regionId": REGION, "customerOrderId": ORDER}),
        ("enc_cust_only", {"regionId": REGION, "customerOrderId": eo}),
        ("orderId", {"orderId": ORDER, "orderType": "0", "regionId": REGION}),
        ("group", {"orderId": ORDER, "customerOrderId": ORDER, "preOrderId": "", "regionId": REGION}),
        ("raw_captured", {"preOrderId": PRE_ENC, "regionId": REGION, "customerOrderId": CUST_ENC}),
        ("mixed_enc_pre_plain", {"preOrderId": ee, "regionId": REGION, "customerOrderId": ORDER}),
        ("region_int", {"preOrderId": ee, "regionId": 579, "customerOrderId": eo}),
        ("only_cust_plain", {"customerOrderId": ORDER}),
        ("pre_plain_empty_cust_enc", {"preOrderId": "", "regionId": REGION, "customerOrderId": eo}),
    ]


def is_good(text: str) -> bool:
    if not text or not text.strip().startswith("{"):
        return False
    try:
        j = json.loads(text)
    except Exception:
        return False
    if not isinstance(j, dict):
        return False
    rc = j.get("retCode", j.get("code"))
    msg = str(j.get("retMessage") or j.get("msg") or "")
    if "maximum length" in msg:
        return False
    if rc in (200, "200", 0, "0", "0000"):
        return True
    # order present
    if j.get("order") or j.get("addressId"):
        return True
    return False


def is_json(text: str) -> bool:
    return bool(text and text.strip().startswith("{") and "retCode" in text)


def main():
    open(OUT, "w", encoding="utf-8").close()
    open(LOG, "w", encoding="utf-8").close()
    log(f"aes check {aes_enc(ORDER)} == {CUST_ENC}? {aes_enc(ORDER)==CUST_ENC}")

    page_bases = [
        "https://interzjmcrm.zj.chinamobile.com/page/oneStationUser4Mobile",
        "https://interzjmcrm.zj.chinamobile.com/page/b25lU3RhdGlvblVzZXI0TW9iaWxl/phone/busi/rboss/broadband/oneStationUser.html",
    ]
    service_bases = [
        "https://interzjmcrm.zj.chinamobile.com/page/b25lU3RhdGlvblVzZXI0TW9iaWxl/phone/busi/rboss/broadband/service",
        "https://interzjmcrm.zj.chinamobile.com/page/oneStationUser4Mobile/phone/busi/rboss/broadband/service",
        "https://interzjmcrm.zj.chinamobile.com/page/null/phone/busi/rboss/broadband/service",
    ]
    qs_list = [
        "?isconvert=true&action=QRY_RBOSS_MOBILE_DETAIL",
        "?isconvert=false&action=QRY_RBOSS_MOBILE_DETAIL",
        "?action=QRY_RBOSS_MOBILE_DETAIL",
        "?isconvert=true&action=INIT_ORDER_SERVICE_GROUP",
        "?isconvert=true&action=GET_STATIC_DATA",
    ]

    n = 0
    for sess in SESSIONS:
        client = Client()
        log(f"=== session nonce={sess['nonce']} encpn={sess['encpn'][:12]}...")

        # 1) bootstrap: load detail HTML with auth query
        for page in page_bases:
            q = {
                "nonce": sess["nonce"],
                "encpn": sess["encpn"],
                "extSysCode": "20049127",
                "cf": sess["cf"],
                "PRE_ORDER_ID": PRE_ENC,
                "city": REGION,
                "CUST_ORDER_ID": CUST_ENC,
                "session": sess["session"],
                "openid": sess.get("openid", ""),
            }
            url = page + "?" + urllib.parse.urlencode(q)
            st, hdrs, body, final = client.request("GET", url, headers={"Referer": "https://app.m.zj.chinamobile.com/"})
            text = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
            log(f"PAGE GET st={st} cookies={client.cookie_header()[:120]} final={final[:100]} body={text[:100].replace(chr(10),' ')}")
            dump({"type": "page", "url": url, "status": st, "cookies": client.cookie_header(), "body": text[:3000]})
            # also POST same (some gateways use POST)
            st2, _, body2, _ = client.request(
                "POST",
                url,
                data=b"",
                headers={
                    "Referer": "https://app.m.zj.chinamobile.com/",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://interzjmcrm.zj.chinamobile.com",
                },
            )
            t2 = body2.decode("utf-8", "replace") if isinstance(body2, (bytes, bytearray)) else str(body2)
            log(f"PAGE POST st={st2} cookies={client.cookie_header()[:120]} body={t2[:80].replace(chr(10),' ')}")

        # also hit app.m host with session params
        app_urls = [
            f"https://app.m.zj.chinamobile.com/#/broadBand/broadBandZone?openid={sess.get('openid','')}&sc=11&cf={sess['cf']}&session={sess['session']}&encpn={sess['encpn']}&nonce={sess['nonce']}",
            f"https://wap.zj.10086.cn/",
        ]
        for u in app_urls:
            st, _, body, final = client.request("GET", u)
            log(f"APP GET st={st} final={str(final)[:80]} cookies={client.cookie_header()[:100]}")

        # save session
        with open(STORE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "cookie": client.cookie_header(),
                    "user_agent": UA,
                    "referer": "https://interzjmcrm.zj.chinamobile.com/page/oneStationUser4Mobile",
                    "origin": "https://interzjmcrm.zj.chinamobile.com",
                    "sess": sess,
                    "ts": time.time(),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        # 2) fuzz APIs with cookies
        referer = (
            f"https://interzjmcrm.zj.chinamobile.com/page/oneStationUser4Mobile?"
            f"nonce={sess['nonce']}&encpn={sess['encpn']}&city={REGION}&CUST_ORDER_ID={CUST_ENC}&PRE_ORDER_ID={PRE_ENC}"
        )
        headers_base = {
            "Referer": referer,
            "Origin": "https://interzjmcrm.zj.chinamobile.com",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        for base in service_bases:
            for q in qs_list:
                url = base + q
                for tag, body in variants():
                    if "GET_STATIC_DATA" in q:
                        body = {"extParam": "BROADBAND_ORDER_QRY_AES_KEY"}
                        tag = "static_key"
                    elif tag == "static_key":
                        continue
                    n += 1
                    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    st, hdrs, resp, final = client.request("POST", url, data=raw, headers=headers_base)
                    text = resp.decode("utf-8", "replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
                    brief = text.replace("\n", " ")[:160]
                    log(f"#{n} {tag}|{q[1:40]} st={st} {brief}")
                    dump({"n": n, "tag": tag, "url": url, "body": body, "status": st, "resp": text[:5000], "cookies": client.cookie_header()})
                    if is_good(text):
                        log(f"*** SUCCESS #{n} {tag}")
                        j = json.loads(text)
                        with open(BEST, "w", encoding="utf-8") as f:
                            json.dump({"tag": tag, "url": url, "body": body, "resp": j}, f, ensure_ascii=False, indent=2)
                        return
                    if is_json(text):
                        log(f"  JSON interest: {brief}")

        # 3) try form-encoded too
        for base in service_bases[:1]:
            url = base + "?isconvert=true&action=QRY_RBOSS_MOBILE_DETAIL"
            for tag, body in variants()[:4]:
                n += 1
                form = urllib.parse.urlencode({k: str(v) for k, v in body.items()}).encode()
                st, _, resp, _ = client.request(
                    "POST",
                    url,
                    data=form,
                    headers={**headers_base, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                )
                text = resp.decode("utf-8", "replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
                log(f"#{n} form_{tag} st={st} {text.replace(chr(10),' ')[:140]}")
                dump({"n": n, "tag": "form_" + tag, "url": url, "body": body, "status": st, "resp": text[:5000]})
                if is_good(text):
                    with open(BEST, "w", encoding="utf-8") as f:
                        json.dump({"tag": "form_" + tag, "url": url, "body": body, "resp": json.loads(text)}, f, ensure_ascii=False, indent=2)
                    log("*** SUCCESS form")
                    return

    log(f"done n={n} no success — waiting for live WeChat cookie via mitm")


if __name__ == "__main__":
    main()
