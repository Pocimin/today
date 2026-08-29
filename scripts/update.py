"""today - a journal that writes itself. runs from a cron via github actions."""

import json
import os
import random
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = ROOT / "entries"
DATA = ROOT / "data"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MOONS = ["new moon", "waxing crescent", "first quarter", "waxing gibbous",
         "full moon", "waning gibbous", "last quarter", "waning crescent"]
MOON_SYMBOLS = ["\U0001F311", "\U0001F312", "\U0001F313", "\U0001F314",
                "\U0001F315", "\U0001F316", "\U0001F317", "\U0001F318"]
NEW_MOON = date(2024, 1, 11)
LUNAR_CYCLE = 29.530588853
MOODS = ["calm", "focused", "slightly feral", "cosy", "wired", "fried",
         "optimistic", "leave me alone", "blessed", "restless", "nerdy",
         "sleepy but fine", "unstoppable", "unkillable", "deployed", "floating"]

STATS_START = "<!-- today:stats -->"
STATS_END = "<!-- /today:stats -->"


def now_utc():
    return datetime.now(timezone.utc)


def read_lines(name):
    text = (DATA / name).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.startswith("#")]


def pick(day, lines):
    return lines[day.toordinal() % len(lines)]


def moon_for(day):
    phase = (day - NEW_MOON).days % LUNAR_CYCLE / LUNAR_CYCLE * 8
    index = min(7, int(phase))
    return f"{MOON_SYMBOLS[index]} {MOONS[index]}"


def fetch_quote():
    url = "https://api.quotable.io/random"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.load(response)
        return f"\"{data['content']}\" \u2014 {data['author']}"
    except Exception:
        return None


def day_path(day):
    return ENTRIES / f"{day.isoformat()}.md"


def write_entry(day, facts, words, quotes):
    mood = random.Random(str(day)).choice(MOODS)
    quote = fetch_quote() or pick(day, quotes)
    text = f"""# {day.isoformat()} \u00b7 {WEEKDAYS[day.weekday()]}

vibe check: {mood}

- fact: {pick(day, facts)}
- word: {pick(day, words)}
- quote: {quote}
- moon: {moon_for(day)}
- checked in at {now_utc().strftime('%H:%M')} UTC
"""
    day_path(day).write_text(text, encoding="utf-8")


def add_checkin(day, number):
    line = f"- check-in #{number} at {now_utc().strftime('%H:%M')} UTC\n"
    with day_path(day).open("a", encoding="utf-8") as handle:
        handle.write(line)


def entry_dates():
    dates = []
    for file in ENTRIES.glob("*.md"):
        try:
            dates.append(date.fromisoformat(file.stem))
        except ValueError:
            continue
    return sorted(dates)


def longest_streak(dates):
    if not dates:
        return 0
    best = run = 1
    for earlier, later in zip(dates, dates[1:]):
        run = run + 1 if (later - earlier).days == 1 else 1
        best = max(best, run)
    return best


def current_streak(dates, day):
    if not dates:
        return 0
    run = 0
    cursor = day if day in dates else day - timedelta(days=1)
    while cursor in dates:
        run += 1
        cursor -= timedelta(days=1)
    return run


def chart(dates, day, weeks=16):
    day_set = set(dates)
    monday = day - timedelta(days=day.weekday())
    start = monday - timedelta(weeks=weeks - 1)
    header = "      M T W T F S S"
    lines = [header]
    for index in range(weeks):
        week_start = start + timedelta(weeks=index)
        week = [week_start + timedelta(days=offset) for offset in range(7)]
        cells = "".join("\u2588" if d in day_set else "\u00b7" for d in week)
        label = week_start.strftime("%m-%d")
        lines.append(f"{label}: {cells}")
    return "\n".join(lines)


def stats_markdown(dates, day, weeks):
    started = dates[0].isoformat() if dates else "you tell me"
    last_week = sum(1 for d in dates if d > day - timedelta(days=7))
    active = sum(1 for d in dates if d > day - timedelta(weeks=weeks))
    body = f"""**update {now_utc().strftime('%Y-%m-%d %H:%M')} UTC**

| | |
|---|---|
| entries | {len(dates)} |
| started | {started} |
| current streak | {current_streak(dates, day)} days |
| longest streak | {longest_streak(dates)} days |
| wakes last 7 days | {last_week} |
| active last {weeks} weeks | {active}/{weeks * 7} days |

last {weeks} weeks:

```
{chart(dates, day, weeks)}
```

\u00b7 = quiet day, \u2588 = wrote something"""
    return body


def rebuild_readme(dates, day, weeks=16):
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    block = f"{STATS_START}\n\n{stats_markdown(dates, day, weeks)}\n\n{STATS_END}"
    pattern = re.escape(STATS_START) + ".*?" + re.escape(STATS_END)
    text = re.sub(pattern, block, text, flags=re.S)
    readme.write_text(text, encoding="utf-8")


def main():
    facts = read_lines("facts.txt")
    words = read_lines("words.txt")
    quotes = read_lines("quotes.txt")
    ENTRIES.mkdir(exist_ok=True)
    day = now_utc().date()
    path = day_path(day)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        number = current.count("check-in #") + 1
        add_checkin(day, number)
        kind = "checkin"
    else:
        write_entry(day, facts, words, quotes)
        kind = "entry"
    dates = entry_dates()
    rebuild_readme(dates, day)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"kind={kind}\n")
    print(f"{kind} for {day.isoformat()} \u00b7 {len(dates)} entries total")


if __name__ == "__main__":
    main()
