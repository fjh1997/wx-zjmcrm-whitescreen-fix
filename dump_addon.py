from mitmproxy import http
from pathlib import Path
import json, time, os, re

DIR = str(Path(__file__).resolve().parent)
OUT = os.path.join(DIR, "flows.jsonl")
LOG = os.path.join(DIR, "capture.log")
os.makedirs(DIR, exist_ok=True)

INTEREST = re.compile(
    r"10086|oneStation|OrderDetail|interzj|rboss|AES|GET_STATIC|QRY_|broadband|staticData|preOrder|authentication|wap\.zj\.|chinamobile|servicewechat",
    re.I,
)

def _log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def _safe_text(msg):
    try:
        t = msg.get_text(strict=False)
        if t is None:
            return ""
        # drop non-printable for json safety
        return t.encode("utf-8", "replace").decode("utf-8", "replace")[:30000]
    except Exception:
        try:
            c = msg.raw_content or b""
            return f"[binary {len(c)} bytes]"
        except Exception:
            return ""

def _dump(obj: dict):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def request(flow: http.HTTPFlow):
    url = flow.request.pretty_url or ""
    host = flow.request.pretty_host or ""
    # skip mmtls noise
    if "/mmtls/" in url or host.startswith("240") and "/mmtls" in (flow.request.path or ""):
        return
    hit = bool(INTEREST.search(url) or INTEREST.search(host))
    if not hit and not any(x in host for x in ("10086", "weixin", "servicewechat", "qq.com", "qpic")):
        return
    body = _safe_text(flow.request) if hit else ""
    row = {
        "type": "request",
        "ts": time.time(),
        "method": flow.request.method,
        "url": url[:2000],
        "host": host,
        "path": (flow.request.path or "")[:500],
        "body": body[:8000],
        "hit": hit,
    }
    _dump(row)
    if hit:
        _log(f"REQ {flow.request.method} {url[:180]}")

def response(flow: http.HTTPFlow):
    url = flow.request.pretty_url or ""
    host = flow.request.pretty_host or ""
    if "/mmtls/" in url:
        return
    hit = bool(INTEREST.search(url) or INTEREST.search(host))
    if not hit and "10086" not in host and "servicewechat" not in host:
        return
    body = _safe_text(flow.response)
    row = {
        "type": "response",
        "ts": time.time(),
        "method": flow.request.method,
        "url": url[:2000],
        "host": host,
        "status": flow.response.status_code if flow.response else None,
        "body": body[:30000],
        "hit": hit,
    }
    _dump(row)
    if hit:
        _log(f"RES {row['status']} {url[:160]} | {body.replace(chr(10),' ')[:180]}")

def load(l):
    # reset files
    open(OUT, "w", encoding="utf-8").close()
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"start {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    _log("addon loaded v2 - open 浙江移动 then click 查看进度")
