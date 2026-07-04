#!/usr/bin/env python3
"""CLI-отчёт аналитики RallyAI. Запуск: .venv/bin/python stats_report.py"""

from analytics import format_analytics_report
from storage import get_analytics_summary


def main() -> None:
    data = get_analytics_summary()
    print(format_analytics_report(data))


if __name__ == "__main__":
    main()
