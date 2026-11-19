"""Accuracy of the message checker on data/messages_eval.jsonl -> docs/METRICS.md.

Flagged = verdict in {scam, suspicious}. Reports rules-only always, and Claude when it is reachable.
The set is small and partly constructed: it shows behaviour, not production accuracy.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import llm, msgcheck  # noqa: E402

DATA = ROOT / "data" / "messages_eval.jsonl"
OUT = ROOT / "docs" / "METRICS.md"


def score(rows, preds):
    tp = sum(1 for r, p in zip(rows, preds) if r["label"] == "scam" and p != "safe")
    fn = sum(1 for r, p in zip(rows, preds) if r["label"] == "scam" and p == "safe")
    fp = sum(1 for r, p in zip(rows, preds) if r["label"] == "legit" and p != "safe")
    tn = sum(1 for r, p in zip(rows, preds) if r["label"] == "legit" and p == "safe")
    recall = tp / (tp + fn) if tp + fn else 0
    precision = tp / (tp + fp) if tp + fp else 0
    acc = (tp + tn) / len(rows)
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "recall": recall, "precision": precision, "accuracy": acc}


def main() -> None:
    rows = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    rules = [msgcheck.check_rules(r["text"], r["lang"]).verdict for r in rows]
    results = {"Правила (офлайн)": rules}

    if os.getenv("QAQPAN_EVAL_LLM") == "1":
        llm_preds = []
        for r in rows:
            res = msgcheck.check_llm(r["text"], None, "image/png", r["lang"], {"text": r["text"], "img": ""})
            llm_preds.append(res.verdict if res else "n/a")
        if "n/a" not in llm_preds:
            results[f"ИИ ({llm.MODEL})"] = llm_preds
            # what the app actually does: rules + AI, AI may raise but never soften a confident rules verdict
            results["Правила + ИИ (как в приложении)"] = [msgcheck.check(r["text"], None, "image/png", None, r["lang"]).verdict for r in rows]

    counts = Counter((r["label"], r["origin"]) for r in rows)
    lines = [
        "# Качество проверки сообщений",
        "",
        "Генерируется `make eval` (`scripts/eval_messages.py`). «Поймано» = вердикт «мошенничество» или «подозрительно».",
        "",
        f"Набор: {len(rows)} сообщений — мошеннических {counts[('scam', 'news')] + counts[('scam', 'constructed')]} "
        f"(из них {counts[('scam', 'news')]} фрагментов из новостей со ссылками, остальные сконструированы по описанным в "
        f"новостях схемам), обычных {counts[('legit', 'constructed')]} (уведомления банка, eGov, почты, семья, OLX).",
        "",
        "**Ограничение.** Набор маленький и в основном сконструирован нами, поэтому это проверка поведения, а не оценка "
        "точности в бою. Инструкция для ИИ уточнялась после первого прогона на этом же наборе (до уточнения: ИИ — 100% "
        "пойманных при 4 мягких тревогах «подозрительно» из 18), поэтому цифры ИИ оптимистичны. Настоящая метрика — "
        "на обезличенных жалобах клиентов банка (первый шаг пилота).",
        "",
        "| Модель | Поймано мошенничества (recall) | Точность тревог (precision) | Ложные тревоги | Пропуски | Accuracy |",
        "|---|---|---|---|---|---|",
    ]
    for name, preds in results.items():
        m = score(rows, preds)
        lines.append(f"| {name} | {m['recall']:.0%} ({m['tp']}/{m['tp'] + m['fn']}) | {m['precision']:.0%} | "
                     f"{m['fp']} из {m['fp'] + m['tn']} | {m['fn']} | {m['accuracy']:.0%} |")
    misses = [(r, p) for r, p in zip(rows, rules) if (r["label"] == "scam") == (p == "safe")]
    if misses:
        lines += ["", "## Ошибки правил", "", "| id | Ожидалось | Вердикт | Текст |", "|---|---|---|---|"]
        lines += [f"| {r['id']} | {r['label']} | {p} | {r['text'][:90]} |" for r, p in misses]
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
