"""Accuracy of the message checker on data/messages_eval.jsonl -> docs/METRICS.md.

Flagged = verdict in {scam, suspicious}. Reports rules-only always, and the AI (xKiro) when it is reachable.
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
HOLDOUT = ROOT / "data" / "messages_holdout.jsonl"  # collected after the rules and the prompt are frozen
OUT = ROOT / "docs" / "METRICS.md"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for k successes of n — honest error bars for a small set."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def score(rows, preds):
    tp = sum(1 for r, p in zip(rows, preds) if r["label"] == "scam" and p != "safe")
    fn = sum(1 for r, p in zip(rows, preds) if r["label"] == "scam" and p == "safe")
    fp = sum(1 for r, p in zip(rows, preds) if r["label"] == "legit" and p != "safe")
    tn = sum(1 for r, p in zip(rows, preds) if r["label"] == "legit" and p == "safe")
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn}


def ci(k: int, n: int) -> str:
    if n == 0:
        return "—"
    lo, hi = wilson(k, n)
    return f"{k / n:.0%} ({k} из {n}; 95%: {lo:.0%}–{hi:.0%})"


def predict(rows):
    results = {"Правила (офлайн)": [msgcheck.check_rules(r["text"], r["lang"]).verdict for r in rows]}
    if os.getenv("QAQPAN_EVAL_LLM") == "1":
        llm_preds = []
        for r in rows:
            res = msgcheck.check_llm(r["text"], None, "image/png", r["lang"], {"text": r["text"], "img": ""})
            llm_preds.append(res.verdict if res else "n/a")
        if "n/a" not in llm_preds:
            results[f"ИИ ({llm.MODEL})"] = llm_preds
            # what the app actually does: rules + AI, the AI never makes the verdict softer than the rules
            results["Правила + ИИ (как в приложении)"] = [msgcheck.check(r["text"], None, "image/png", None, r["lang"]).verdict
                                                         for r in rows]
    return results


def table(rows, results) -> list[str]:
    out = ["| Модель | Язык | Поймано мошенничества | Ложные тревоги на обычных |", "|---|---|---|---|"]
    for name, preds in results.items():
        for lang, label in (("all", "все"), ("ru", "рус"), ("kk", "каз")):
            pairs = [(r, p) for r, p in zip(rows, preds) if lang == "all" or r["lang"] == lang]
            if not pairs:
                continue
            m = score([r for r, _ in pairs], [p for _, p in pairs])
            out.append(f"| {name if lang == 'all' else ''} | {label} | {ci(m['tp'], m['tp'] + m['fn'])} | "
                       f"{ci(m['fp'], m['fp'] + m['tn'])} |")
    return out


def load(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def main() -> None:
    rows = load(DATA)
    results = predict(rows)
    counts = Counter((r["label"], r["origin"]) for r in rows)
    lines = [
        "# Качество проверки сообщений",
        "",
        "Генерируется `make eval` (`scripts/eval_messages.py`). «Поймано» = вердикт «мошенничество» или «подозрительно». "
        "В скобках — 95% интервал Уилсона: на маленьком наборе важна именно ширина интервала.",
        "",
        "## Набор настройки",
        "",
        f"{len(rows)} сообщений: мошеннических {counts[('scam', 'news')] + counts[('scam', 'constructed')]} "
        f"(из них {counts[('scam', 'news')]} фрагментов из новостей со ссылками, остальные сконструированы по описанным в "
        f"новостях схемам), обычных {counts[('legit', 'constructed')]} (уведомления и предупреждения банков, eGov, почта, "
        f"семья, OLX). Казахских — {sum(r['lang'] == 'kk' for r in rows)}.",
        "",
        "**Ограничение.** На этом наборе мы настраивали и правила, и инструкцию для ИИ (последний раз — после внешнего "
        "разбора 21.11: добавили «жаңа нөмір», «не кладите трубку», отрицания в предупреждениях банков). Поэтому это "
        "проверка поведения, а не точность. Честная цифра — на контрольном наборе ниже и на обезличенных жалобах "
        "клиентов банка (первый шаг пилота).",
        "",
        *table(rows, results),
    ]
    misses = [(r, p) for r, p in zip(rows, results["Правила (офлайн)"]) if (r["label"] == "scam") == (p == "safe")]
    if misses:
        lines += ["", "### Ошибки правил", "", "| id | Ожидалось | Вердикт | Текст |", "|---|---|---|---|"]
        lines += [f"| {r['id']} | {r['label']} | {p} | {r['text'][:90]} |" for r, p in misses]

    hold = load(HOLDOUT)
    lines += ["", "## Контрольный набор (не используется для настройки)", ""]
    if len(hold) >= 10:
        lines += [f"{len(hold)} реальных сообщений, собраны после того, как правила и инструкция ИИ зафиксированы "
                  "(`data/messages_holdout.jsonl`).", "", *table(hold, predict(hold))]
    else:
        lines += ["Ещё не собран. Нужно не меньше 30 реальных сообщений (SMS и мессенджеры родных и знакомых, официальные "
                  "предупреждения банков как обычные сообщения) в `data/messages_holdout.jsonl`, тот же формат. "
                  "Правила и инструкцию ИИ перед прогоном не менять."]
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
