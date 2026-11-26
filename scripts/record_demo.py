"""Record the stage demo as an MP4 with on-screen narration.

Drives /stage in headless Chrome at a human pace, shows a caption panel next to the phones,
highlights every tap, and assembles the screencast with ffmpeg.

    make demo                                   # server on :8000 (another terminal)
    .venv/bin/python scripts/record_demo.py http://localhost:8000 video/qaqpan_demo.mp4

Interface language and voice-over are Russian. Voice: macOS `say` (QAQPAN_VOICE, default Milena;
install a better «Enhanced/Premium» Russian voice in System Settings → Accessibility → Spoken Content).
"""

import base64
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import warnings
from pathlib import Path

from websockets.sync.client import connect

warnings.filterwarnings("ignore", category=DeprecationWarning)

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "video/qaqpan_demo.mp4")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9335
W, H = 1920, 1080

OVERLAY_JS = r"""
(() => {
  if (window.__qv) return;
  const css = document.createElement('style');
  css.textContent = `
    #qv-cap{position:fixed;left:28px;top:150px;width:330px;z-index:9999;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
      color:#1C1B19;transition:opacity .4s;background:#fff;padding:16px 18px 18px;border-radius:20px;
      box-shadow:0 2px 6px rgba(28,27,25,.06),0 18px 50px rgba(28,27,25,.16);box-sizing:border-box}
    #qv-cap.bottom{left:50%;top:auto;bottom:40px;width:980px;transform:translateX(-50%)}
    #qv-cap .tag{display:inline-block;background:#F26B1D;color:#fff;font-weight:800;font-size:15px;letter-spacing:.04em;
      text-transform:uppercase;padding:6px 12px;border-radius:999px}
    #qv-cap .txt{margin-top:14px;font-size:24px;line-height:1.35;font-weight:600}
    #qv-ring{position:fixed;width:64px;height:64px;margin:-32px 0 0 -32px;border-radius:50%;border:5px solid #f59e0b;
      box-shadow:0 0 0 8px rgba(245,158,11,.25);z-index:9998;pointer-events:none;transition:transform .25s,opacity .25s}
    #qv-card{position:fixed;inset:0;z-index:10000;background:#F6F5F2;display:flex;flex-direction:column;align-items:center;
      justify-content:center;text-align:center;color:#1C1B19;font-family:-apple-system,Segoe UI,Roboto,sans-serif;transition:opacity .6s}
    #qv-card .logo{width:96px;height:96px;border-radius:28px;background:#F26B1D;display:grid;place-items:center;margin-bottom:28px}
    #qv-card h1{font-size:72px;font-weight:900;margin:0;letter-spacing:-.02em}
    #qv-card p{font-size:30px;color:#4A4744;max-width:1200px;line-height:1.4;margin:18px 0 0}
    #qv-card small{font-size:20px;color:#8A857E;margin-top:36px}`;
  document.head.appendChild(css);
  const cap = document.createElement('div'); cap.id = 'qv-cap'; cap.style.opacity = 0;
  cap.innerHTML = '<span class="tag"></span><div class="txt"></div>';
  document.body.appendChild(cap);
  const ring = document.createElement('div'); ring.id = 'qv-ring'; ring.style.opacity = 0;
  document.body.appendChild(ring);
  window.__qv = {
    caption(tag, txt) {
      cap.style.opacity = 0;
      setTimeout(() => { cap.querySelector('.tag').textContent = tag; cap.querySelector('.txt').textContent = txt; cap.style.opacity = 1 }, 250);
    },
    card(title, text, small) {
      let c = document.getElementById('qv-card');
      if (!c) { c = document.createElement('div'); c.id = 'qv-card'; document.body.appendChild(c) }
      c.style.opacity = 1;
      c.innerHTML = `<div class="logo"><svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"
        stroke-linejoin="round"><path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z"/></svg></div>
        <h1>${title}</h1><p>${text}</p>${small ? `<small>${small}</small>` : ''}`;
    },
    dock(where) { cap.classList.toggle('bottom', where === 'bottom') },
    hideCard() { const c = document.getElementById('qv-card'); if (c) { c.style.opacity = 0; setTimeout(() => c.remove(), 700) } },
    ring(x, y) {
      ring.style.left = x + 'px'; ring.style.top = y + 'px'; ring.style.opacity = 1; ring.style.transform = 'scale(1.25)';
      setTimeout(() => ring.style.transform = 'scale(.9)', 250);
      setTimeout(() => ring.style.opacity = 0, 700);
    },
  };
})()
"""


class Browser:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
             f"--window-size={W},{H}", f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                pages = json.load(urllib.request.urlopen(f"http://localhost:{PORT}/json"))
                if pages:
                    break
            except OSError:
                time.sleep(0.2)
        self.ws = connect(next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"), max_size=100_000_000)
        self.seq = 0
        self.waiting: dict[int, queue.Queue] = {}
        self.lock = threading.Lock()
        self.frames: list[tuple[float, bytes]] = []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        try:
            for raw in self.ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self.waiting:
                    self.waiting.pop(msg["id"]).put(msg)
                elif msg.get("method") == "Page.screencastFrame":
                    p = msg["params"]
                    self.frames.append((p["metadata"]["timestamp"], base64.b64decode(p["data"])))
                    self.send("Page.screencastFrameAck", sessionId=p["sessionId"])
        except Exception:
            pass

    def send(self, method: str, **params) -> queue.Queue:
        with self.lock:
            self.seq += 1
            q: queue.Queue = queue.Queue()
            self.waiting[self.seq] = q
            self.ws.send(json.dumps({"id": self.seq, "method": method, "params": params}))
        return q

    def cdp(self, method: str, **params) -> dict:
        msg = self.send(method, **params).get(timeout=30)
        if "error" in msg:
            raise RuntimeError(msg["error"])
        return msg.get("result", {})

    def js(self, expr: str):
        return self.cdp("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True).get("result", {}).get("value")

    def close(self) -> None:
        self.proc.terminate()


VOICE = os.getenv("QAQPAN_VOICE", "Milena")
RATE = os.getenv("QAQPAN_VOICE_RATE", "182")

# narration = what the voice says; captions show the same text on screen
N = {
    "intro": "Qaqpan — капкан для мошенников внутри приложения банка. Любое мошенничество проходит четыре шага, и на каждом стоит слой защиты.",
    "cast": "Перед вами три клиента банка: Айгерим, пятьдесят два года, её сын Ержан — доверенное лицо, и Мадина. Наверху — четыре шага мошенничества.",
    "s1a": "Шаг первый: написали. Айгерим приходит SMS: срок вашей ЭЦП истекает, перейдите по ссылке. Она проверяет его в Qaqpan одним нажатием.",
    "s1b": "Ответ за секунду: мошенничество. Опасные слова подсвечены, и у каждого — объяснение: ссылка подделана под eGov, а ЭЦП по SMS не продлевают.",
    "s2a": "Шаг второй: позвонили. Звонит служба безопасности банка. Номер на экране можно подделать, а журнал звонков банка — нельзя.",
    "s2b": "Qaqpan сверился с банком: никто из сотрудников ей сейчас не звонит. На этот номер уже жаловались.",
    "a1": "А можно просто спросить помощника Qaqpan. Он видит, что идёт звонок, и сам сверяется с журналом банка.",
    "a2": "Ответ за пару секунд, простыми словами и с учётом её ситуации. На вопросы не про безопасность денег помощник не отвлекается.",
    "s3a": "Шаг третий: уговорили перевести. Мошенник диктует перевод девятисот тысяч тенге на безопасный счёт.",
    "s3b": "Qaqpan видит: идёт звонок, новый получатель, больше половины всех денег. Перевод на паузе, три вопроса.",
    "s3c": "Мошенник подсказал ответы: нет на все вопросы. Но перевод новому получателю больше лимита всё равно ждёт решения сына. Разбить сумму на части или положить трубку не поможет.",
    "f1": "Ержан на работе. Ему приходит уведомление: маму, возможно, обманывают.",
    "f2": "Всё простыми словами: что происходит, что Qaqpan видел сегодня и что делать. Без его ответа деньги не уйдут.",
    "f3": "Ержан отклоняет перевод. Деньги мамы остаются на её счёте.",
    "s4a": "Шаг четвёртый: получили деньги. Айгерим сообщает о мошенниках. Перевод остановлен во время звонка, поэтому жалоба подтверждённая: счёт помечается для всех клиентов банка.",
    "s4b": "Через минуту Мадина покупает айфон на OLX и платит сто пятьдесят тысяч тенге на тот же счёт.",
    "s4c": "Мадину предупредили: на этот счёт жаловались. Другая легенда, другой человек, а счёт тот же.",
    "s4d": "Одна остановленная попытка защитила всех. Миллион пятьдесят тысяч тенге спасено.",
    "b1": "А это взгляд банка. Счёт мошенника найден как вероятный дроп: за сутки на него переводили два разных клиента.",
    "b2": "Искусственный интеллект пишет аналитику короткую сводку, а решение — заблокировать или разрешить — остаётся за банком.",
    "h1": "И сразу — готовое заявление о попытке мошенничества: номер и счёт проверит полиция. А если деньги всё же ушли — заявление о хищении и что делать прямо сейчас.",
    "d1": "А если мошенник скажет: отключите семейный щит?",
    "d2": "Щит выключится только через двадцать четыре часа, а сын сразу получает уведомление.",
    "outro": "Банк видит операцию. Qaqpan видит давление. Дыру одного слоя закрывает следующий, а за человеком стоят семья и тысячи других клиентов. Qaqpan.",
}


def synth(out_dir: Path) -> dict[str, tuple[Path, float]]:
    clips = {}
    for key, text in N.items():
        path = out_dir / f"{key}.aiff"
        subprocess.run(["say", "-v", VOICE, "-r", RATE, "-o", str(path), text], check=True)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                   capture_output=True, text=True, check=True).stdout.strip())
        clips[key] = (path, dur)
    return clips


def main() -> None:
    audio_dir = Path(tempfile.mkdtemp())
    clips = synth(audio_dir)
    print(f"voice-over: {len(clips)} clips, {sum(d for _, d in clips.values()):.0f}s")
    b = Browser()
    spoken: list[tuple[float, Path]] = []
    voice = {"until": 0.0}

    def speak(key: str) -> None:
        """Start a narration clip after the previous one has finished."""
        wait = voice["until"] - time.time()
        if wait > 0:
            time.sleep(wait)
        path, dur = clips[key]
        spoken.append((time.time(), path))
        voice["until"] = time.time() + dur + 0.35

    def wait_voice(extra: float = 0.0) -> None:
        time.sleep(max(0.0, voice["until"] - time.time()) + extra)

    def director(action: str, pause: float = 1.4) -> None:
        urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/director/{action}", method="POST", data=b""))
        time.sleep(pause)

    def caption(tag: str, key: str, pause: float = 1.0) -> None:
        speak(key)
        b.js(f"window.__qv.caption({json.dumps(tag)}, {json.dumps(N[key])})")
        time.sleep(pause)

    def tap(phone: int, text: str, exact: bool = False, nth: int = 0, pause: float = 1.6) -> None:
        cond = "b.textContent.trim() === t" if exact else "b.textContent.includes(t)"
        rect = b.js(f"""(() => {{
          const root = document.querySelectorAll('main > div')[{phone}];
          const t = {json.dumps(text)};
          const els = [...root.querySelectorAll('button, a')].filter(b => !b.disabled && ({cond}));
          const el = els[{nth}]; if (!el) return null;
          el.scrollIntoView({{block: 'nearest'}});
          const r = el.getBoundingClientRect(); window.__qvEl = el;
          return [r.left + r.width / 2, r.top + r.height / 2]; }})()""")
        if not rect:
            raise SystemExit(f"button not found on phone {phone}: {text!r}")
        b.js(f"window.__qv.ring({rect[0]}, {rect[1]})")
        time.sleep(0.55)
        b.js("window.__qvEl.click()")
        time.sleep(pause)

    def back(phone: int, pause: float = 1.0) -> None:
        rect = b.js(f"""(() => {{ const el = document.querySelectorAll('main > div')[{phone}].querySelector('button[aria-label="back"]');
          if (!el) return null; window.__qvEl = el; const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()""")
        if not rect:
            raise SystemExit(f"back button not found on phone {phone}")
        b.js(f"window.__qv.ring({rect[0]}, {rect[1]})")
        time.sleep(0.5)
        b.js("window.__qvEl.click()")
        time.sleep(pause)

    def scroll(phone: int, selector: str, dy: int, pause: float = 2.0) -> None:
        b.js(f"""(() => {{ const root = document.querySelectorAll('main > div')[{phone}];
          const el = [...root.querySelectorAll({json.dumps(selector)})].pop(); if (el) el.scrollBy({{top: {dy}, behavior: 'smooth'}}); }})()""")
        time.sleep(pause)

    try:
        b.cdp("Page.enable")
        b.cdp("Runtime.enable")
        director("reset", 0.3)
        for cid in ("aigerim", "erzhan", "madina"):  # Russian interface on every phone
            urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/phone/{cid}/lang/ru", method="POST", data=b""))
        b.cdp("Page.navigate", url=f"{BASE}/stage?light")
        time.sleep(3)
        b.js(OVERLAY_JS)
        b.js("window.__qv.card('Qaqpan', 'Капкан для мошенников внутри приложения банка.<br>4 шага мошенничества — 4 слоя защиты, которые передают сигнал друг другу.', 'ITU Hackathon 2026 · Fintech case · Банк ЦентрКредит')")
        b.cdp("Page.startScreencast", format="jpeg", quality=85, maxWidth=W, maxHeight=H, everyNthFrame=1)
        time.sleep(0.8)
        speak("intro")
        wait_voice(0.3)
        b.js("window.__qv.hideCard()")
        time.sleep(1)

        caption("На сцене", "cast")
        wait_voice()

        # 1 «Написали»
        caption("Шаг 1 · Написали", "s1a", 1.5)
        director("sms", 2.5)
        wait_voice()
        tap(0, "Нажмите, чтобы проверить", pause=1.6)
        tap(0, "Проверить", exact=True, pause=1.2)
        caption("Шаг 1 · Написали", "s1b")
        wait_voice(0.5)

        # 2 «Позвонили»
        back(0, 0.8)
        caption("Шаг 2 · Позвонили", "s2a", 1.5)
        director("call", 1.5)
        wait_voice()
        tap(0, "Ответить", exact=True, pause=1.5)
        tap(0, "Банк мне звонит?", pause=1.2)
        caption("Шаг 2 · Позвонили", "s2b")
        wait_voice(0.5)
        tap(0, "Готово", exact=True, pause=0.8)

        # AI assistant that sees the client's situation
        caption("Помощник Qaqpan", "a1", 1.5)
        tap(0, "Спросить Qaqpan", pause=1.2)
        wait_voice()
        tap(0, "Мне звонят из банка", pause=0.5)
        for _ in range(40):  # wait for the AI answer bubble
            if (b.js("""[...document.querySelectorAll('main > div')[0].querySelectorAll('.rounded-bl-md')]
                .filter(e => e.textContent.includes('Qaqpan')).length""") or 0) >= 2:
                break
            time.sleep(0.4)
        caption("Помощник Qaqpan", "a2", 1)
        wait_voice(1.2)
        back(0, 0.8)

        # 3 «Уговорили перевести»
        caption("Шаг 3 · Уговорили", "s3a", 1)
        director("transfer_aigerim", 1.5)
        wait_voice()
        tap(0, "Перевести 900", pause=2.6)
        caption("Шаг 3 · Уговорили", "s3b")
        wait_voice()
        caption("Шаг 3 · Уговорили", "s3c", 2.5)
        for i in range(3):
            tap(0, "Нет", exact=True, nth=i, pause=0.7)
        tap(0, "Ответить", exact=True, pause=1.5)
        wait_voice()

        # family shield
        caption("Семейный щит", "f1")
        wait_voice()
        tap(1, "возможно, обманывают", pause=1.2)
        caption("Семейный щит", "f2", 3)
        scroll(1, ".overflow-y-auto", 260, 1)
        wait_voice()
        caption("Семейный щит", "f3", 1.5)
        tap(1, "Отклонить перевод", pause=1.5)
        wait_voice(0.5)

        # 4 «Получили деньги»
        caption("Шаг 4 · Получили", "s4a", 2.5)
        tap(0, "Сообщить о мошенниках", pause=1)
        wait_voice()
        caption("Шаг 4 · Получили", "s4b", 2.5)
        director("transfer_madina", 1.5)
        tap(2, "Перевести 150", pause=2.4)
        wait_voice()
        caption("Шаг 4 · Получили", "s4c", 3)
        tap(2, "Да", exact=True, nth=0, pause=0.6)
        tap(2, "Да", exact=True, nth=1, pause=0.6)
        tap(2, "Нет", exact=True, nth=2, pause=0.6)
        tap(2, "Ответить", exact=True, pause=1)
        wait_voice()
        caption("Шаг 4 · Получили", "s4d")
        wait_voice(0.5)

        # the bank's side: the antifraud console with the drop account
        b.cdp("Page.navigate", url=f"{BASE}/bank")
        time.sleep(2.5)
        b.js(OVERLAY_JS)
        b.js("window.__qv.dock('bottom')")  # the console fills the left side: captions go under it
        caption("Взгляд банка", "b1", 1)
        wait_voice(0.8)
        caption("Взгляд банка", "b2", 0.5)
        wait_voice(1)
        b.cdp("Page.navigate", url=f"{BASE}/stage")
        time.sleep(3)
        b.js(OVERLAY_JS)

        # help
        caption("Если всё же обманули", "h1", 0.5)
        director("victim", 2)
        scroll(0, ".overflow-y-auto", 420, 1)
        wait_voice(1)

        # shield cannot be switched off instantly
        back(0, 0.8)
        caption("Защита от уговоров", "d1", 1)
        wait_voice()
        tap(0, "Семейный щит", pause=1.2)
        tap(0, "Отключить щит", pause=1.2)
        caption("Защита от уговоров", "d2")
        wait_voice(1)

        b.js("window.__qv.card('Банк видит операцию. Qaqpan видит давление', 'Дыру одного слоя закрывает следующий,<br>а за человеком стоят семья и тысячи других клиентов.', 'Qaqpan · ITU Hackathon 2026')")
        time.sleep(0.8)
        speak("outro")
        wait_voice(1.5)
        b.cdp("Page.stopScreencast")
        time.sleep(0.5)
    finally:
        b.close()

    frames = sorted(b.frames)
    t0 = frames[0][0]
    if abs(t0 - spoken[0][0]) > 30:  # frame timestamps are not wall-clock: align by the first frame we saw
        t0 = spoken[0][0] - 0.8
    print(f"frames: {len(frames)}, length {frames[-1][0] - frames[0][0]:.1f}s")
    tmp = Path(tempfile.mkdtemp())
    lines = []
    for i, (ts, data) in enumerate(frames):
        (tmp / f"f{i:05d}.jpg").write_bytes(data)
        dur = (frames[i + 1][0] - ts) if i + 1 < len(frames) else 2.0
        lines += [f"file 'f{i:05d}.jpg'", f"duration {max(dur, 0.001):.4f}"]
    lines.append(f"file 'f{len(frames) - 1:05d}.jpg'")
    (tmp / "list.txt").write_text("\n".join(lines))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    silent = tmp / "silent.mp4"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                    "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "21", str(silent)], check=True)

    inputs, chains = ["-i", str(silent)], []
    for i, (ts, path) in enumerate(spoken):
        delay = max(0, int((ts - t0) * 1000))
        inputs += ["-i", str(path)]
        chains.append(f"[{i + 1}:a]aresample=44100,adelay={delay}:all=1[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(spoken)))
    graph = ";".join(chains) + f";{mix}amix=inputs={len(spoken)}:normalize=0:dropout_transition=0,volume=1.6[aout]"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "0:v", "-map", "[aout]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(OUT)], check=True)
    shutil.rmtree(tmp)
    shutil.rmtree(audio_dir)
    print(f"video -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB), voice-over clips: {len(spoken)}")


if __name__ == "__main__":
    main()
