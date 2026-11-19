"""Fill data/llm_cache/ with AI (xKiro) answers for every demo screenshot (RU + KK).

Run once with a key before the stage, then commit data/llm_cache/: on stage `make demo`
serves these answers without internet. Uses exactly the same request path as the API,
so cache keys match.

    XKIRO_API_KEY=... in .env
    .venv/bin/python scripts/warm_llm_cache.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("QAQPAN_DEMO", None)

from api import llm, msgcheck  # noqa: E402


def main() -> None:
    samples = msgcheck.load_samples()
    ok = 0
    for sid, sample in samples.items():
        for lang in ("ru", "kk"):
            res = msgcheck.check(None, None, "image/png", sid, lang)
            mark = "AI " if res.source in ("llm", "cache") else "RULES"
            ok += res.source in ("llm", "cache")
            print(f"[{mark}] {sid:16} {lang}  {res.verdict:10} {res.scheme_name or ''}")
            if llm.status()["live_disabled"]:
                print("\nИИ недоступен:", llm.status()["live_disabled"])
                print("Задайте XKIRO_API_KEY в .env и запустите снова.")
                return
    print(f"\nВ кэше ответов ИИ: {ok} из {len(samples) * 2}. Закоммитьте data/llm_cache/.")


if __name__ == "__main__":
    main()
