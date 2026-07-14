from pathlib import Path
# -*- coding: utf-8 -*-
"""
Auto-fuzz QRY_RBOSS_MOBILE_DETAIL until we get real order data.
Uses Windows Python + urllib, reuses latest cookies from session_store.json
(written by mitm addon), falls back to bare requests.
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Any

DIR = str(Path(__file__).resolve().parent)
STORE = os.path.join(DIR, "session_store.json")
OUT = os.path.join(DIR, "auto_fuzz_results.jsonl")
LOG = os.path.join(DIR, "auto_fuzz.log")

AES_KEY = "YOUR_AES_KEY_HEX_FROM_STATIC_DATA"
ORDER_PLAIN = "YOUR_14_DIGIT_ORDER_ID"
CUST_ENC = "4A115947F839DEC71FC5881CCE8576C0"
PRE_ENC_EMPTY = "15EFA8899CED3DA682198BC5C1BDAFDC"
REGION = "579"

BASES = [
    "https://interzjmcrm.zj.chinamobile.com/page/b25lU3RhdGlvblVzZXI0TW9iaWxl/phone/busi/rboss/broadband/service",
    "https://interzjmcrm.zj.chinamobile.com/page/oneStationUser4Mobile/phone/busi/rboss/broadband/service",
    "https://zj.ac.10086.cn/page/b25lU3RhdGlvblVzZXI0TW9iaWxl/phone/busi/rboss/broadband/service",
]

ACTIONS = [
    "QRY_RBOSS_MOBILE_DETAIL",
    "INIT_ORDER_SERVICE_GROUP",
    "QRY_BROADBAND_CUSTORDER_OP",
    "GET_STATIC_DATA",
]


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def dump(obj: dict) -> None:
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_session() -> dict:
    if not os.path.exists(STORE):
        return {}
    try:
        with open(STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def aes_encrypt(data: str, key_hex: str = AES_KEY) -> str:
    """AES-128-ECB PKCS7, return uppercase hex (matches CryptoJS)."""
    try:
        from Crypto.Cipher import AES  # type: ignore
    except Exception:
        try:
            from Cryptodome.Cipher import AES  # type: ignore
        except Exception:
            # pure-python fallback via cryptography
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding as sympad
            from cryptography.hazmat.backends import default_backend

            key = bytes.fromhex(key_hex)
            padder = sympad.PKCS7(128).padder()
            pt = padder.update((data or "").encode("utf-8")) + padder.finalize()
            enc = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend()).encryptor()
            ct = enc.update(pt) + enc.finalize()
            return ct.hex().upper()

    key = bytes.fromhex(key_hex)
    raw = (data or "").encode("utf-8")
    pad = 16 - (len(raw) % 16)
    raw = raw + bytes([pad]) * pad
    ct = AES.new(key, AES.MODE_ECB).encrypt(raw)
    return ct.hex().upper()


def build_variants() -> list[tuple[str, dict]]:
    """(tag, body_dict)"""
    enc_order = aes_encrypt(ORDER_PLAIN)
    enc_empty = aes_encrypt("")
    variants: list[tuple[str, dict]] = []

    # Official client shape (re-encrypt plaintext)
    variants.append(
        (
            "official_enc",
            {
                "preOrderId": enc_empty,
                "regionId": REGION,
                "customerOrderId": enc_order,
            },
        )
    )
    # Plaintext 14-char (server may want this with isconvert=false)
    variants.append(
        (
            "plain_14",
            {
                "preOrderId": "",
                "regionId": REGION,
                "customerOrderId": ORDER_PLAIN,
            },
        )
    )
    variants.append(("plain_no_pre", {"regionId": REGION, "customerOrderId": ORDER_PLAIN}))
    variants.append(("plain_orderId", {"orderId": ORDER_PLAIN, "regionId": REGION, "orderType": "0"}))
    variants.append(
        (
            "plain_group",
            {
                "orderId": ORDER_PLAIN,
                "regionId": REGION,
                "customerOrderId": ORDER_PLAIN,
                "preOrderId": "",
            },
        )
    )
    # Enc only customer
    variants.append(
        (
            "enc_cust_only",
            {"regionId": REGION, "customerOrderId": enc_order},
        )
    )
    # region as int
    variants.append(
        (
            "plain_region_int",
            {"preOrderId": "", "regionId": 579, "customerOrderId": ORDER_PLAIN},
        )
    )
    variants.append(
        (
            "enc_region_int",
            {"preOrderId": enc_empty, "regionId": 579, "customerOrderId": enc_order},
        )
    )
    # Mixed (wrong but seen in field)
    variants.append(
        (
            "mixed_enc_pre_plain_cust",
            {
                "preOrderId": PRE_ENC_EMPTY,
                "regionId": REGION,
                "customerOrderId": ORDER_PLAIN,
            },
        )
    )
    variants.append(
        (
            "double_enc_raw_url",
            {
                "preOrderId": PRE_ENC_EMPTY,
                "regionId": REGION,
                "customerOrderId": CUST_ENC,
            },
        )
    )
    # Shorter / alternate order forms
    for tag, cid in [
        ("cust_13", ORDER_PLAIN[:13]),
        ("cust_no_prefix", ORDER_PLAIN[3:]),  # 00429036210
        ("cust_last10", ORDER_PLAIN[-10:]),
        ("cust_last14_pad", ORDER_PLAIN),
    ]:
        variants.append((tag, {"customerOrderId": cid, "regionId": REGION}))
        variants.append((tag + "_enc", {"customerOrderId": aes_encrypt(cid), "regionId": REGION, "preOrderId": enc_empty}))

    # Alternate field names
    for fname in ["custOrderId", "customerOrderID", "CUST_ORDER_ID", "orderNbr", "soNbr", "acceptOrderId"]:
        variants.append((f"alt_{fname}_plain", {fname: ORDER_PLAIN, "regionId": REGION}))
        variants.append((f"alt_{fname}_enc", {fname: enc_order, "regionId": REGION}))

    # Static data smoke
    variants.append(("static_key", {"extParam": "BROADBAND_ORDER_QRY_AES_KEY"}))

    return variants


def make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # allow legacy renegotiation if available
    try:
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    except Exception:
        pass
    return ctx


def post_json(url: str, body: dict, headers: dict, timeout: float = 20.0) -> tuple[int, str, dict]:
    data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        if v:
            req.add_header(k, v)
    if "Content-Type" not in {k.title(): k for k in headers}:
        req.add_header("Content-Type", "application/json;charset=UTF-8")
    ctx = make_ssl_ctx()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            return resp.status, text, dict(resp.headers.items())
    except urllib.error.HTTPError as e:
        raw = e.read() if e.fp else b""
        text = raw.decode("utf-8", errors="replace")
        return e.code, text, dict(e.headers.items()) if e.headers else {}
    except Exception as e:
        return 0, f"ERR:{type(e).__name__}:{e}", {}


def is_success(text: str) -> bool:
    if not text or text.startswith("ERR:"):
        return False
    t = text.strip()
    if not (t.startswith("{") or t.startswith("[")):
        return False
    try:
        j = json.loads(t)
    except Exception:
        return False
    # common success shapes
    if isinstance(j, dict):
        rc = j.get("retCode", j.get("code", j.get("resultCode")))
        if rc in (200, "200", 0, "0", "0000", "00"):
            # prefer payloads with order nodes
            if j.get("order") or j.get("orders") or j.get("data") or j.get("staticDatas"):
                return True
            return True
        # some APIs nest
        data = j.get("data") or j.get("result")
        if isinstance(data, (dict, list)) and data:
            if rc is None or str(rc) in ("200", "0", "0000"):
                return True
    return False


def looks_interesting(text: str) -> bool:
    if not text or text.startswith("ERR:"):
        return False
    keys = ("retCode", "order", "retMessage", "maximum length", "staticDatas", "nodeId", "addressId")
    return any(k in text for k in keys)


def main() -> None:
    open(OUT, "w", encoding="utf-8").close()
    open(LOG, "w", encoding="utf-8").close()
    sess = load_session()
    cookie = sess.get("cookie") or ""
    ua = sess.get("user_agent") or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20"
    )
    referer = sess.get("referer") or (
        "https://interzjmcrm.zj.chinamobile.com/page/b25lU3RhdGlvblVzZXI0TW9iaWxl/phone/busi/"
        "rboss/broadband/oneStationUser.html"
    )
    origin = sess.get("origin") or "https://interzjmcrm.zj.chinamobile.com"
    extra_headers = sess.get("headers") or {}

    log(f"session cookie_len={len(cookie)} keys={list(sess.keys())}")
    try:
        log(f"aes selfcheck enc(order)={aes_encrypt(ORDER_PLAIN)} expect={CUST_ENC}")
        log(f"aes selfcheck enc('')={aes_encrypt('')} expect={PRE_ENC_EMPTY}")
    except Exception as e:
        log(f"aes selfcheck FAIL: {e}")

    base_headers = {
        "User-Agent": ua,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": origin,
        "Referer": referer,
        "Connection": "keep-alive",
    }
    if cookie:
        base_headers["Cookie"] = cookie
    for k, v in extra_headers.items():
        if k.lower() not in ("content-length", "host"):
            base_headers[k] = v

    variants = build_variants()
    query_suffixes = [
        "?isconvert=true&action={action}",
        "?isconvert=false&action={action}",
        "?action={action}",
        "?isconvert=true&action={action}&city=579",
    ]

    success: list[dict[str, Any]] = []
    interesting: list[dict[str, Any]] = []
    n = 0

    # Prefer DETAIL action first
    action_order = ["QRY_RBOSS_MOBILE_DETAIL", "INIT_ORDER_SERVICE_GROUP", "QRY_BROADBAND_CUSTORDER_OP", "GET_STATIC_DATA"]

    for base in BASES:
        for action in action_order:
            for q in query_suffixes:
                url = base + q.format(action=action)
                for tag, body in variants:
                    # skip static-only body for non-static actions and vice versa
                    if action == "GET_STATIC_DATA" and tag != "static_key":
                        continue
                    if action != "GET_STATIC_DATA" and tag == "static_key":
                        continue
                    n += 1
                    status, text, rh = post_json(url, body, base_headers)
                    rec = {
                        "n": n,
                        "tag": tag,
                        "action": action,
                        "url": url,
                        "body": body,
                        "status": status,
                        "resp": text[:4000],
                    }
                    dump(rec)
                    brief = (text or "").replace("\n", " ")[:160]
                    log(f"#{n} {tag}|{action} st={status} {brief}")
                    if is_success(text):
                        log(f"*** SUCCESS #{n} {tag} {action}")
                        success.append(rec)
                        # keep going a bit to collect more good payloads, but stop early if DETAIL with order
                        if action == "QRY_RBOSS_MOBILE_DETAIL" and ("order" in text or "addressId" in text):
                            log("Got DETAIL order data — stopping.")
                            _write_best(success, interesting)
                            return
                    elif looks_interesting(text):
                        interesting.append(rec)

    # Also try GET style (some gateways)
    for base in BASES[:1]:
        url = base + "?isconvert=true&action=QRY_RBOSS_MOBILE_DETAIL"
        for tag, body in [("plain_14", {"preOrderId": "", "regionId": REGION, "customerOrderId": ORDER_PLAIN})]:
            # form body
            form = "&".join(f"{k}={v}" for k, v in body.items())
            n += 1
            headers = dict(base_headers)
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            # reuse post via urllib with form
            data = form.encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            for k, v in headers.items():
                req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, timeout=20, context=make_ssl_ctx()) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                    status = resp.status
            except Exception as e:
                text = f"ERR:{e}"
                status = 0
            rec = {"n": n, "tag": "form_" + tag, "action": "QRY_RBOSS_MOBILE_DETAIL", "url": url, "body": body, "status": status, "resp": text[:4000]}
            dump(rec)
            log(f"#{n} form_{tag} st={status} {(text or '')[:160]}")
            if is_success(text):
                success.append(rec)

    _write_best(success, interesting)
    log(f"done n={n} success={len(success)} interesting={len(interesting)}")


def _write_best(success: list, interesting: list) -> None:
    best_path = os.path.join(DIR, "auto_fuzz_best.json")
    with open(best_path, "w", encoding="utf-8") as f:
        json.dump({"success": success, "interesting": interesting[:50]}, f, ensure_ascii=False, indent=2)
    log(f"wrote {best_path}")


if __name__ == "__main__":
    main()
