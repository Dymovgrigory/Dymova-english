"""Прогон бенчмарка через настоящую модель — с отчётом по качеству.

Тестовый прогон (`pytest tests/test_benchmark.py`) идёт без модели и
проверяет запреты: они обязаны соблюдаться всегда. Здесь проверяется то, что
без модели проверить нельзя, — как ответы звучат. Каждый ответ оценивает
критик (`app.critic.score`), результаты сводятся в таблицу по категориям.

Запуск:

    python scripts/run_benchmark.py                # все сценарии
    python scripts/run_benchmark.py --category Эмоции
    python scripts/run_benchmark.py --limit 20 --json отчёт.json

Требует настроенного провайдера (LLM_API_KEY). Прогон платный: сто с лишним
сценариев — это несколько сотен запросов, поэтому по умолчанию печатается
оценка объёма и спрашивается подтверждение.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app import critic, sales  # noqa: E402
from app.ai_core import handle_message  # noqa: E402
from app.llm import get_llm  # noqa: E402
from app.memory import get_store  # noqa: E402

SCENARIOS = Path(__file__).resolve().parents[1] / "tests" / "benchmark" / "scenarios.yaml"


def load(category: str = "", limit: int = 0) -> list[dict]:
    groups = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))
    cases: list[dict] = []
    for group in groups:
        if category and group["category"] != category:
            continue
        for case in group["cases"]:
            cases.append({"category": group["category"], **case})
    return cases[:limit] if limit else cases


async def run_case(case: dict) -> dict:
    conv_id = f"bench-live-{case['id']}"
    get_store().reset(conv_id)
    reply = ""
    for message in case["messages"]:
        reply = await handle_message(conv_id, message)

    conv = get_store().get(conv_id)
    issues = critic.inspect(reply, _history_without_last(conv), sales.offer_allowed(conv))
    scores = await critic.score(reply, case["messages"][-1]) or {}
    return {
        "id": case["id"],
        "category": case["category"],
        "reply": reply,
        "issues": issues,
        "scores": scores,
    }


def _history_without_last(conv):
    class _View:
        history = conv.history[:-1]

    return _View()


def report(results: list[dict]) -> str:
    lines = ["", "СВОДКА ПО КАТЕГОРИЯМ", "=" * 60]
    by_category: dict[str, list[dict]] = {}
    for item in results:
        by_category.setdefault(item["category"], []).append(item)

    for category, items in by_category.items():
        problems = [i for i in items if i["issues"]]
        rewrites = [i for i in items if i["scores"].get("verdict") == "rewrite"]
        natural = [i["scores"]["natural"] for i in items if "natural" in i["scores"]]
        average = sum(natural) / len(natural) if natural else 0.0
        lines.append(
            f"{category:<28} сценариев: {len(items):>3}  "
            f"нарушений: {len(problems):>3}  "
            f"на переписывание: {len(rewrites):>3}  "
            f"естественность: {average:.1f}"
        )

    flagged = [i for i in results if i["issues"] or i["scores"].get("verdict") == "rewrite"]
    if flagged:
        lines += ["", "ЧТО ПОСМОТРЕТЬ РУКАМИ", "=" * 60]
        for item in flagged:
            reason = ", ".join(item["issues"]) or item["scores"].get("reason", "")
            lines.append(f"\n[{item['id']}] {reason}\n  {item['reply']}")
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", default="", help="прогнать одну категорию")
    parser.add_argument("--limit", type=int, default=0, help="ограничить число сценариев")
    parser.add_argument("--json", default="", help="куда сохранить подробный результат")
    parser.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")
    args = parser.parse_args()

    if not get_llm().enabled:
        print("Модель не настроена: задайте LLM_API_KEY. Прогон без модели — это pytest.")
        return 1

    cases = load(args.category, args.limit)
    if not cases:
        print("Под условия не подошёл ни один сценарий.")
        return 1

    turns = sum(len(case["messages"]) for case in cases)
    print(f"Сценариев: {len(cases)}, реплик: {turns}. Плюс по одной оценке на сценарий.")
    if not args.yes:
        answer = input("Запускать? [y/N] ").strip().lower()
        if answer not in ("y", "yes", "д", "да"):
            return 0

    results = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        try:
            results.append(await run_case(case))
        except Exception as error:  # прогон не должен падать из-за одного случая
            results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "reply": "",
                    "issues": ["exception"],
                    "scores": {"reason": str(error)},
                }
            )

    print(report(results))
    if args.json:
        Path(args.json).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nПодробности: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
