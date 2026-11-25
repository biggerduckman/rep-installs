#!/usr/bin/env python3
"""Read data/jobs.csv, apply the shared rules, geocode rows that are missing
coordinates (Tennessee 911 address points, Census as fallback), and write
data/jobs.json for the app. Rewrites the CSV only when names are cleaned or
coordinates are filled in, so Gunnar can edit the CSV on github.com.

Run from the repo root or from this script's folder:
    python3 scripts/build_from_csv.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "jobs.csv"
JSON_PATH = ROOT / "data" / "jobs.json"

EXCLUDE = {"KNX-10408"}
LIEN = re.compile(r"lien", re.I)
KEEP_CAPS = {"HOA", "VFW", "LLC", "RJ", "WJ", "II", "III", "IV", "JR", "SR"}
NAME_OVERRIDE = {
    "GMET-1363": "Alice Bell Baptist Church",
    "KNX-10292": "Richard Agnew",
    "KNX-1137": "Randy Paterson",
    "GMET-1464": "Elizabeth Crowe-Green",
    "KNX-805": "Urimare Freijanes Duquella",
}
NAME_BLANK = {"GMET-1385"}
COMPANY_ALIASES = {
    "gold medal": "Gold Medal Roofing",
    "gold medal roofing": "Gold Medal Roofing",
    "gmet": "Gold Medal Roofing",
    "perimeter": "Perimeter Roofing",
    "perimeter roofing": "Perimeter Roofing",
    "knx": "Perimeter Roofing",
}
COLS = [
    "job_id", "company", "homeowner", "address", "city", "date",
    "roof_type", "carrier_or_retail", "lat", "lng", "notes",
]
TN_URL = "https://tnmap.tn.gov/arcgis/rest/services/LOCATORS/TN_ADDRESSPOINTS/GeocodeServer/findAddressCandidates"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
UA = {"User-Agent": "rep-installs-builder/1.0"}


def ws(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def tidy(s):
    s = ws(s)
    if s and (s.islower() or s.isupper()):
        s = " ".join(
            w if re.fullmatch(r"(N|S|E|W|NE|NW|SE|SW|II|III|IV)", w.upper()) and w.isupper()
            else w.capitalize()
            for w in s.split()
        )
    return s


def clean_name(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\s*#\s*\d+", "", s)
    s = re.sub(r"[-\s]*\bRental\b", "", s, flags=re.I)
    s = re.sub(r"\*+", "", s)
    s = re.sub(r"(?<![\w'])\d+(?![\w'])", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -,/&")
    w = []
    for x in s.split(" "):
        if len(x) >= 3 and x.isupper() and x not in KEEP_CAPS:
            x = x.capitalize()
        elif re.fullmatch(r"[A-Z]{2}[a-z]+", x):
            x = x[0] + x[1:].lower()
        w.append(x)
    return " ".join(w)


def company_of(s):
    return COMPANY_ALIASES.get(ws(s).lower(), ws(s))


def parse_date(s):
    s = ws(s)
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s


def parse_coord(v):
    s = ws(v)
    if not s:
        return ""
    try:
        return round(float(s), 6)
    except ValueError:
        return ""


def http_json(url, params, timeout=30, tries=3):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(url + "?" + q, headers=UA)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def geocode(address, city):
    """Return (lat, lng, source) or None. TN 911 PointAddress first, then Census."""
    line = ", ".join(p for p in (ws(address), ws(city)) if p)
    if not line:
        return None
    num = re.match(r"\d+", ws(address) or line)
    num = num.group(0) if num else None
    try:
        j = http_json(TN_URL, dict(
            SingleLine=line, outSR=4326, maxLocations=5,
            outFields="Addr_type,AddNum,Match_addr,Score", f="json",
        ))
        pts = [c for c in j.get("candidates") or [] if (c.get("attributes") or {}).get("Addr_type") == "PointAddress"]
        if not pts and j.get("candidates"):
            pts = [c for c in j["candidates"] if float(c.get("score") or 0) >= 90]
        if pts:
            # Prefer a house-number match with a strong score
            def rank(c):
                a = c.get("attributes") or {}
                hit = 1 if num and str(a.get("AddNum") or "") == num else 0
                return (hit, float(c.get("score") or 0))
            pts.sort(key=rank, reverse=True)
            best = pts[0]
            if float(best.get("score") or 0) >= 80:
                loc = best["location"]
                return float(loc["y"]), float(loc["x"]), "tn911"
    except Exception as e:
        print("TN 911 error for", line, ":", e, flush=True)
    try:
        j = http_json(CENSUS_URL, dict(address=line, benchmark="Public_AR_Current", format="json"))
        matches = (j.get("result") or {}).get("addressMatches") or []
        if matches:
            c = matches[0]["coordinates"]
            return float(c["y"]), float(c["x"]), "census"
    except Exception as e:
        print("Census error for", line, ":", e, flush=True)
    return None


def job_type(carrier):
    c = ws(carrier)
    if c.lower() == "retail":
        return "Retail"
    if not c or c.lower() == "unknown":
        return ""
    return "Insurance"


def read_csv(path):
    raw = path.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(raw.splitlines()))
    # Accept a few friendly header aliases in case the file was edited in Excel
    aliases = {
        "id": "job_id", "job number": "job_id", "job_number": "job_id",
        "name": "homeowner", "homeowner name": "homeowner",
        "street": "address",
        "completed": "date", "date_completed": "date",
        "roof": "roof_type", "rooftype": "roof_type",
        "carrier": "carrier_or_retail", "insurance": "carrier_or_retail",
        "latitude": "lat", "longitude": "lng", "lon": "lng",
    }
    out = []
    for r in rows:
        n = {}
        for k, v in r.items():
            key = (k or "").strip()
            key = aliases.get(key.lower().replace(" ", "_"), key)
            n[key] = v
        out.append(n)
    return out


def main():
    if not CSV_PATH.exists():
        sys.exit(f"Missing {CSV_PATH}")
    incoming = read_csv(CSV_PATH)
    stats = dict(read=len(incoming), excluded=0, lien=0, no_coords=0, geocoded=0, cleaned=0, dups=0, published=0)
    skipped = []
    cleaned_rows = []
    seen = set()

    for raw in incoming:
        jid = ws(raw.get("job_id") or raw.get("id") or "")
        if not jid:
            continue
        if jid in EXCLUDE:
            stats["excluded"] += 1
            skipped.append((jid, "excluded"))
            continue
        homeowner_in = raw.get("homeowner") or raw.get("name") or ""
        notes_in = raw.get("notes") or ""
        if LIEN.search(str(homeowner_in)) or LIEN.search(str(notes_in)):
            stats["lien"] += 1
            skipped.append((jid, "lien"))
            continue
        company = company_of(raw.get("company") or "")
        if jid in NAME_BLANK:
            name = ""
        else:
            name = NAME_OVERRIDE.get(jid) or tidy(clean_name(homeowner_in))
        if ws(name) != ws(homeowner_in):
            stats["cleaned"] += 1
        address = tidy(re.sub(r"^#\s*", "", ws(raw.get("address") or "").split(",")[0]))
        city = ws(raw.get("city") or "")
        carrier = ws(raw.get("carrier_or_retail") or raw.get("carrier") or "")
        lat = parse_coord(raw.get("lat"))
        lng = parse_coord(raw.get("lng"))
        row = {
            "job_id": jid,
            "company": company,
            "homeowner": name,
            "address": address,
            "city": city,
            "date": parse_date(raw.get("date") or ""),
            "roof_type": ws(raw.get("roof_type") or ""),
            "carrier_or_retail": carrier,
            "lat": lat,
            "lng": lng,
            "notes": ws(notes_in),
        }
        key = "|".join([company, name, address, carrier]).lower()
        if key in seen:
            stats["dups"] += 1
            skipped.append((jid, "duplicate"))
            continue
        seen.add(key)
        cleaned_rows.append(row)

    # Geocode anything still missing a pin
    for row in cleaned_rows:
        if row["lat"] != "" and row["lng"] != "":
            continue
        hit = geocode(row["address"], row["city"])
        if hit:
            row["lat"], row["lng"] = round(hit[0], 6), round(hit[1], 6)
            stats["geocoded"] += 1
            print(f"geocoded {row['job_id']} {row['address']} -> {row['lat']},{row['lng']} ({hit[2]})", flush=True)
            time.sleep(0.15)
        else:
            stats["no_coords"] += 1
            print(f"no coordinates {row['job_id']} {row['address']}, {row['city']}", flush=True)

    # Rewrite the CSV (stable column order) so filled coordinates are saved
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    def csv_cell(row, k):
        v = row[k]
        return "" if v is None else str(v)

    buf_lines = []
    # Write through the csv module for correct quoting
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for row in cleaned_rows:
        w.writerow({k: csv_cell(row, k) for k in COLS})
    new_csv = buf.getvalue()
    old_csv = CSV_PATH.read_text(encoding="utf-8") if CSV_PATH.exists() else ""
    # Normalize the previous file enough to compare (BOM / CRLF)
    old_cmp = old_csv.replace("\r\n", "\n").lstrip("\ufeff")
    csv_changed = old_cmp != new_csv
    if csv_changed:
        CSV_PATH.write_text(new_csv, encoding="utf-8")

    jobs = []
    for row in cleaned_rows:
        if row["lat"] == "" or row["lng"] == "":
            continue
        typ = job_type(row["carrier_or_retail"])
        rec = {
            "id": row["job_id"],
            "company": row["company"],
            "name": row["homeowner"],
            "address": row["address"],
            "lat": float(row["lat"]),
            "lng": float(row["lng"]),
            "carrier": row["carrier_or_retail"],
        }
        # city is kept for Directions / geocoding only — the app must not display it
        if row["city"]:
            rec["city"] = row["city"]
        if typ:
            rec["type"] = typ
        if row["date"]:
            rec["date"] = row["date"]
        if row["roof_type"]:
            rec["roofType"] = row["roof_type"]
        if row["notes"]:
            rec["notes"] = row["notes"]
        jobs.append(rec)
    jobs.sort(key=lambda r: r["id"])
    stats["published"] = len(jobs)

    payload = {
        "version": 5,
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jobs": jobs,
    }
    json_changed = True
    if JSON_PATH.exists():
        try:
            json_changed = json.loads(JSON_PATH.read_text(encoding="utf-8")).get("jobs") != jobs
        except Exception:
            json_changed = True
    if json_changed:
        JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    gm = sum(1 for r in jobs if r["company"] == "Gold Medal Roofing")
    pm = sum(1 for r in jobs if r["company"] == "Perimeter Roofing")
    print(f"-> {CSV_PATH} ({'updated' if csv_changed else 'unchanged'})")
    print(f"-> {JSON_PATH} ({JSON_PATH.stat().st_size:,} bytes, {'updated' if json_changed else 'unchanged'})")
    print(f"read {stats['read']} | published {stats['published']} | Gold Medal {gm} | Perimeter {pm}")
    print(
        f"excluded {stats['excluded']} | lien {stats['lien']} | duplicates {stats['dups']} | "
        f"names cleaned {stats['cleaned']} | geocoded {stats['geocoded']} | still no pin {stats['no_coords']}"
    )
    if skipped:
        print("skipped:", ", ".join(f"{i} ({why})" for i, why in skipped[:20]), ("…" if len(skipped) > 20 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
