"""Pulls the current-year World Athletics top 50 (men & women) for each event
and saves them to data.json. Run nightly by GitHub Actions."""
import json, re, sys, time
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

YEAR = datetime.now(timezone.utc).year
TOP_N = 50
WIND = "regular"   # "regular" = legal wind only. Change to "all" to include wind-aided marks.

# (display name, URL path, genders that compete in it)
EVENTS = [
    ("100m", "sprints/100-metres", "MW"),
    ("200m", "sprints/200-metres", "MW"),
    ("400m", "sprints/400-metres", "MW"),
    ("800m", "middle-distance/800-metres", "MW"),
    ("1500m", "middle-distance/1500-metres", "MW"),
    ("5000m", "long-distance/5000-metres", "MW"),
    ("10,000m", "long-distance/10000-metres", "MW"),
    ("110m Hurdles", "hurdles/110-metres-hurdles", "M"),
    ("100m Hurdles", "hurdles/100-metres-hurdles", "W"),
    ("400m Hurdles", "hurdles/400-metres-hurdles", "MW"),
    ("3000m Steeplechase", "steeplechase/3000-metres-steeplechase", "MW"),
    ("High Jump", "jumps/high-jump", "MW"),
    ("Pole Vault", "jumps/pole-vault", "MW"),
    ("Long Jump", "jumps/long-jump", "MW"),
    ("Triple Jump", "jumps/triple-jump", "MW"),
    ("Shot Put", "throws/shot-put", "MW"),
    ("Discus Throw", "throws/discus-throw", "MW"),
    ("Hammer Throw", "throws/hammer-throw", "MW"),
    ("Javelin Throw", "throws/javelin-throw", "MW"),
    ("Decathlon", "combined-events/decathlon", "M"),
    ("Heptathlon", "combined-events/heptathlon", "W"),
]
GENDER = {"M": "men", "W": "women"}
HEADERS = {"User-Agent": "Mozilla/5.0 (personal top-lists viewer)"}

def clean(t):
    return re.sub(r"\s+", " ", t).strip()

def fetch(path, gender):
    url = (f"https://worldathletics.org/records/toplists/{path}/outdoor/{gender}/senior/{YEAR}"
           f"?regionType=world&timing=electronic&windReading={WIND}&page=1&bestResultsOnly=true")
    r = requests.get(url, headers=HEADERS, timeout=40)
    r.raise_for_status()
    table = BeautifulSoup(r.text, "html.parser").find("table")
    if table is None:
        raise ValueError("no results table found")
    heads = [clean(th.get_text()).lower() for th in table.find_all("th")]
    def col(*names):
        for i, h in enumerate(heads):
            if any(n in h for n in names):
                return i
        return None
    idx = {"mark": col("mark"), "wind": col("wind"), "name": col("competitor", "athlete"),
           "nat": col("nat"), "venue": col("venue"), "date": col("date")}
    # the "date" header can match DOB too; take the last date-like column
    dates = [i for i, h in enumerate(heads) if "date" in h or "dob" in h]
    if dates:
        idx["date"] = dates[-1]
    rows = []
    for tr in table.find_all("tr"):
        tds = [clean(td.get_text()) for td in tr.find_all("td")]
        if len(tds) < len(heads) - 1 or not tds:
            continue
        get = lambda k: tds[idx[k]] if idx[k] is not None and idx[k] < len(tds) else ""
        rows.append({"rank": len(rows) + 1, "mark": get("mark"), "wind": get("wind"),
                     "athlete": get("name"), "nat": get("nat"),
                     "venue": get("venue"), "date": get("date")})
        if len(rows) == TOP_N:
            break
    if not rows:
        raise ValueError("table had no rows")
    return rows

def main():
    try:
        with open("data.json") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("results", {})
    errors = total = 0
    for name, path, genders in EVENTS:
        for g in genders:
            key = f"{GENDER[g]}|{name}"
            total += 1
            try:
                data["results"][key] = fetch(path, GENDER[g])
                print("ok  ", key, len(data["results"][key]))
            except Exception as e:
                errors += 1
                print("FAIL", key, e, file=sys.stderr)  # keeps yesterday's data
            time.sleep(2)
    data["year"] = YEAR
    data["events"] = [{"name": n, "genders": [GENDER[g] for g in gs]} for n, _, gs in EVENTS]
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open("data.json", "w") as f:
        json.dump(data, f, indent=1)
    if errors == total:  # everything failed
        sys.exit(1)

main()
