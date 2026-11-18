"""Browser end-to-end run of the demo on /stage through Chrome DevTools Protocol.

Clicks through the whole script like the presenter would and saves screenshots.
Usage: python scripts/e2e_stage.py [base_url] [out_dir]   (server must be running)
Needs Google Chrome; uses only `websockets` (installed with uvicorn[standard]).
"""

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
import warnings
from pathlib import Path

from websockets.sync.client import connect

warnings.filterwarnings("ignore", category=DeprecationWarning)

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e_shots")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333

OUT.mkdir(parents=True, exist_ok=True)
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
                         "--window-size=1920,1080", f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            pages = json.load(urllib.request.urlopen(f"http://localhost:{PORT}/json"))
            if pages:
                break
        except OSError:
            time.sleep(0.2)
    ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
    ws = connect(ws_url, max_size=50_000_000)
    seq = 0

    def cdp(method, **params):
        global seq
        seq += 1
        ws.send(json.dumps({"id": seq, "method": method, "params": params}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == seq:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def js(expr):
        r = cdp("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def director(action):
        urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/director/{action}", method="POST", data=b""))
        time.sleep(1.3)

    def click(phone: int, text: str, exact=False):
        ok = js(f"""(() => {{
          const root = document.querySelectorAll('main > div')[{phone}];
          const els = [...root.querySelectorAll('button')].filter(b => !b.disabled);
          const t = {json.dumps(text)};
          const el = els.find(b => {'b.textContent.trim() === t' if exact else 'b.textContent.includes(t)'});
          if (!el) return false; el.click(); return true; }})()""")
        if not ok:
            shot(f"FAIL_{text[:20]}")
            raise SystemExit(f"button not found on phone {phone}: {text!r}")
        time.sleep(0.9)

    def shot(name):
        data = cdp("Page.captureScreenshot", format="png")["data"]
        (OUT / f"{name}.png").write_bytes(base64.b64decode(data))
        print("shot", name)

    cdp("Page.enable")
    cdp("Runtime.enable")
    director("reset")
    cdp("Page.navigate", url=f"{BASE}/stage")
    time.sleep(2.5)

    # 1 «Написали»
    director("sms")
    click(0, "Тексеру үшін")
    click(0, "Тексеру", exact=True)
    time.sleep(1)
    shot("01_message_scam")
    click(0, "")  # header back button is the first button
    # 2 «Позвонили»
    director("call")
    click(0, "Жауап беру", exact=True)
    click(0, "Банк қоңырау")
    shot("02_call_not_bank")
    click(0, "Дайын", exact=True)
    # 3 «Уговорили»: scammer coached her to say «no»
    director("transfer_aigerim")
    click(0, "Аудару 900")
    shot("03_questions")
    for _ in range(3):
        js("""(() => { const root = document.querySelectorAll('main > div')[0];
          const b = [...root.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Жоқ' && !b.className.includes('bg-slate-800'));
          if (b[0]) b[0].click(); })()""")
        time.sleep(0.3)
    click(0, "Жауап беру", exact=True)
    time.sleep(1.2)
    shot("04_family_request")
    click(1, "Отклонить перевод")
    time.sleep(1.5)
    shot("05_family_declined")
    # 4 «Получили»: complaint protects Madina
    click(0, "Алаяқтар туралы хабарлау")
    director("transfer_madina")
    click(2, "Перевести 150")
    time.sleep(0.8)
    shot("06_madina_protected")
    # finale
    director("victim")
    time.sleep(1.5)
    shot("07_victim_help")
    print("stage:", json.load(urllib.request.urlopen(f"{BASE}/api/stage"))["steps"])
finally:
    proc.terminate()
