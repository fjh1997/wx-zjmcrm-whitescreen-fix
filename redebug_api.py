import os
# -*- coding: utf-8 -*-
"""Re-debug DETAIL API with bootstrap session (nonce/encpn)."""
import http.cookiejar
import json
import ssl
import urllib.parse
import urllib.request
from Crypto.Cipher import AES

KEY = os.environ.get("ZJ_AES_KEY", "")
ORDER = os.environ.get("ZJ_ORDER_ID", "")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20"
)
BASE = (
    "https://interzjmcrm.zj.chinamobile.com/page/"
    "b25lU3RhdGlvblVzZXI0TW9iaWxl/phone/busi/rboss/broadband/service"
)
SESSIONS = [
    {
        "encpn": "19e0d8c882c0ea820aaeca3f2e3ce1d0",
        "nonce": "THNUpoN7D4s9p466",
        "cf": "10113",
    },
    {
        "encpn": "3055b8474853f381943112503b1572ce",
        "nonce": "SJOXDSYa356W26uX",
        "cf": "10113",
    },
    {
        "encpn": "975063631e22b7de482edf4f1bd2c318",
        "nonce": "o408SdIyn3VTnDGG",
        "cf": "10113",
    },
]


def enc(s: str) -> str:
    key = bytes.fromhex(KEY)
    raw = (s or "").encode("utf-8")
    pad = 16 - (len(raw) % 16)
    raw += bytes([pad]) * pad
    return AES.new(key, AES.MODE_ECB).encrypt(raw).hex().upper()


def ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.options |= 0x4
    except Exception:
        pass
    return ctx


def main():
    print("enc('')", enc(""))
    print("enc(order)", enc(ORDER), "len", len(enc(ORDER)))
    print("double", enc(enc(ORDER)), "len", len(enc(enc(ORDER))))

    ctx = ssl_ctx()
    for sess in SESSIONS:
        print("\n======== session", sess["nonce"], sess["encpn"][:12])
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=ctx),
        )
        q = urllib.parse.urlencode(
            {
                "nonce": sess["nonce"],
                "encpn": sess["encpn"],
                "extSysCode": "20049127",
                "cf": sess["cf"],
                "PRE_ORDER_ID": enc(""),
                "city": "579",
                "CUST_ORDER_ID": enc(ORDER),
            }
        )
        page = "https://interzjmcrm.zj.chinamobile.com/page/oneStationUser4Mobile?" + q
        try:
            r = op.open(
                urllib.request.Request(page, headers={"User-Agent": UA}), timeout=15
            )
            body = r.read()
            print("page", r.status, len(body), "cookies", [(c.name, c.value[:12]) for c in cj])
            # if error page, try next session
            if b"error" in body[:500].lower() and b"oneStation" not in body[:2000]:
                # still may have set JSESSIONID
                pass
        except Exception as e:
            print("page fail", e)
            continue

        cookie = "; ".join(f"{c.name}={c.value}" for c in cj)
        if not cookie:
            print("no cookie, skip")
            continue

        def post(tag, body, qs="?isconvert=true&action=QRY_RBOSS_MOBILE_DETAIL"):
            url = BASE + qs
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={
                    "User-Agent": UA,
                    "Cookie": cookie,
                    "Content-Type": "application/json;charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://interzjmcrm.zj.chinamobile.com",
                    "Referer": page,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                },
            )
            try:
                with op.open(req, timeout=15) as resp:
                    t = resp.read().decode("utf-8", "replace")
            except Exception as e:
                if hasattr(e, "read"):
                    try:
                        t = e.read().decode("utf-8", "replace")
                    except Exception:
                        t = f"ERR:{e}"
                else:
                    t = f"ERR:{e}"
            if t.strip().startswith("{"):
                try:
                    j = json.loads(t)
                    print(
                        f"  {tag}: retCode={j.get('retCode')} order_n={len(j.get('order') or [])} msg={(j.get('retMessage') or '')[:70]}"
                    )
                    return j
                except Exception:
                    print(f"  {tag}: bad json", t[:100])
            else:
                print(f"  {tag}: NON-JSON {t[:80].replace(chr(10),' ')}")
            return None

        cases = [
            ("A_official_enc", {"preOrderId": enc(""), "regionId": "579", "customerOrderId": enc(ORDER)}),
            ("B_plain_14", {"preOrderId": "", "regionId": "579", "customerOrderId": ORDER}),
            ("C_double_enc", {"preOrderId": enc(enc("")), "regionId": "579", "customerOrderId": enc(enc(ORDER))}),
            ("D_url_cipher_raw", {"preOrderId": enc(""), "regionId": "579", "customerOrderId": enc(ORDER)}),  # same A
            ("E_encrypt_of_cipher", {"preOrderId": enc(enc("")), "regionId": "579", "customerOrderId": enc(enc(ORDER))}),
            ("F_plain_15", {"preOrderId": "", "regionId": "579", "customerOrderId": ORDER + "X"}),
            ("G_plain_only_cust", {"customerOrderId": ORDER, "regionId": "579"}),
        ]
        got_json = False
        for tag, body in cases:
            j = post(tag, body)
            if j is not None:
                got_json = True
        # isconvert false for plain and enc
        post("H_plain_isconvert_false", {"preOrderId": "", "regionId": "579", "customerOrderId": ORDER},
             "?isconvert=false&action=QRY_RBOSS_MOBILE_DETAIL")
        post("I_enc_isconvert_false", {"preOrderId": enc(""), "regionId": "579", "customerOrderId": enc(ORDER)},
             "?isconvert=false&action=QRY_RBOSS_MOBILE_DETAIL")
        if got_json:
            print("got JSON API responses with this session — stop")
            return
    print("all sessions failed to get JSON")


if __name__ == "__main__":
    main()
