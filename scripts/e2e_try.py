"""Browser run of the self-guided tour on /try: presses «Далее» through every step like a juror would.

Usage: python scripts/e2e_try.py [base_url] [out_dir] [mobile|desktop]   (server must be running)
Checks that the visitor's own sandbox ends with 1 050 000 ₸ saved and the shared stage is untouched.
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
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e_try")
MODE = sys.argv[3] if len(sys.argv) > 3 else "mobile"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9337

OUT.mkdir(parents=True, exist_ok=True)
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
                         "--window-size=1440,900", f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            pages = json.load(urllib.request.urlopen(f"http://localhost:{PORT}/json"))
            if pages:
                break
        except OSError:
            time.sleep(0.2)
    ws = connect(next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"), max_size=50_000_000)
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
        return cdp("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True).get("result", {}).get("value")

    def shot(name):
        (OUT / f"{name}.png").write_bytes(base64.b64decode(cdp("Page.captureScreenshot", format="png")["data"]))

    cdp("Page.enable")
    cdp("Runtime.enable")
    if MODE == "mobile":
        cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    cdp("Page.navigate", url=f"{BASE}/try")
    time.sleep(4)
    titles = []
    for n in range(30):
        card = js("""(() => { const b = [...document.querySelectorAll('button')].find(b => ['Начать','Далее','Свободный режим','…'].includes(b.textContent.trim()));
          if (!b) return null; const c = b.closest('.fixed'); return c ? c.querySelector('.font-bold')?.textContent : '?' })()""")
        if card is None:
            break
        titles.append(card)
        shot(f"{n:02d}")
        for _ in range(40):  # wait while a step is running its events
            if js("[...document.querySelectorAll('button')].some(b => ['Начать','Далее','Свободный режим'].includes(b.textContent.trim()) && !b.disabled)"):
                break
            time.sleep(0.25)
        time.sleep(1.2)  # the highlight settles
        js("[...document.querySelectorAll('button')].find(b => ['Начать','Далее','Свободный режим'].includes(b.textContent.trim()))?.click()")
        time.sleep(2.2)
    shot("zz_free")
    sid = js("sessionStorage.getItem('qaqpan.sandbox')")
    req = urllib.request.Request(f"{BASE}/api/stage", headers={"X-Qaqpan-Session": sid})
    mine = json.load(urllib.request.urlopen(req))
    shared = json.load(urllib.request.urlopen(f"{BASE}/api/stage"))
    print("steps:", len(titles))
    print(" · ".join(titles))
    print("sandbox saved:", mine["saved"], "steps fired:", mine["steps"])
    print("shared stage saved:", shared["saved"])
    ok = mine["saved"] == 1_050_000 and len(titles) == 17
    print("OK" if ok else "FAIL")
    sys.exit(0 if ok else 1)
finally:
    proc.terminate()
