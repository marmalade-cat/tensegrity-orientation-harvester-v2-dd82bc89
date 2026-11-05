import os
import sys
import csv
import json
import hashlib
import urllib.request
from urllib.parse import urlparse
from datetime import datetime

# Small prototype: normalize CSV and simple JSON time-series/orientation data into a standard CSV.
# Produces a provenance report (JSON) with source, checksum, and notes.

STANDARD_HEADERS = [
    "module_id",      # identifier for module or series
    "timestamp",      # ISO 8601 or numeric time
    "qx", "qy", "qz", "qw",  # quaternion orientation (preferred)
    "x", "y", "z",  # optional position
]

def sha256_of_bytes(b):
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def fetch_bytes(path_or_url):
    parsed = urlparse(path_or_url)
    if parsed.scheme in ("http", "https"):
        with urllib.request.urlopen(path_or_url) as r:
            data = r.read()
        return data
    else:
        with open(path_or_url, "rb") as f:
            return f.read()

def parse_csv_bytes(b):
    text = b.decode("utf-8")
    reader = csv.DictReader(text.splitlines())
    rows = [row for row in reader]
    return rows

def parse_json_bytes(b):
    obj = json.loads(b.decode("utf-8"))
    # Accept either list of records or dict with 'data' key
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], list):
        return obj["data"]
    # Heuristic: if dict of time->pose, convert
    if isinstance(obj, dict):
        rows = []
        for k, v in obj.items():
            row = {"timestamp": k}
            if isinstance(v, dict):
                row.update(v)
            else:
                row["value"] = v
            rows.append(row)
        return rows
    return []

def normalize_record(rec):
    # Create normalized record with standard headers; best-effort mapping.
    out = {h: "" for h in STANDARD_HEADERS}
    # module id
    if "module" in rec:
        out["module_id"] = str(rec.get("module"))
    elif "id" in rec:
        out["module_id"] = str(rec.get("id"))
    elif "module_id" in rec:
        out["module_id"] = str(rec.get("module_id"))

    # timestamp
    for tkey in ("timestamp", "time", "t"):
        if tkey in rec:
            out["timestamp"] = str(rec.get(tkey))
            break

    # quaternion
    if all(k in rec for k in ("qx", "qy", "qz", "qw")):
        out.update({k: str(rec[k]) for k in ("qx", "qy", "qz", "qw")})
    # alternative: orientation as array
    elif "orientation" in rec and isinstance(rec["orientation"], (list, tuple)):
        arr = rec["orientation"]
        if len(arr) == 4:
            out.update({"qx": str(arr[0]), "qy": str(arr[1]), "qz": str(arr[2]), "qw": str(arr[3])})
    # positions
    for p in ("x", "y", "z"):
        if p in rec:
            out[p] = str(rec[p])

    return out

def write_standard_csv(rows, outpath):
    with open(outpath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_HEADERS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def process_source(path_or_url, out_dir):
    print(f"Processing: {path_or_url}")
    b = fetch_bytes(path_or_url)
    checksum = sha256_of_bytes(b)
    # try CSV
    try:
        records = parse_csv_bytes(b)
        notes = "parsed as CSV"
    except Exception:
        try:
            records = parse_json_bytes(b)
            notes = "parsed as JSON"
        except Exception:
            records = []
            notes = "unrecognized format"
    normalized = [normalize_record(r) for r in records]
    base = os.path.basename(urlparse(path_or_url).path) or "source"
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_csv = os.path.join(out_dir, f"{base}.{timestamp}.standard.csv")
    write_standard_csv(normalized, out_csv)
    prov = {
        "source": path_or_url,
        "output_csv": out_csv,
        "checksum_sha256": checksum,
        "record_count": len(normalized),
        "notes": notes,
    }
    return prov

def ensure_dir(p):
    if not os.path.exists(p):
        os.makedirs(p)

def main(argv):
    if len(argv) < 2:
        print("Usage: python main.py <path_or_url> [<path_or_url> ...]")
        print("Or provide a directory containing sample files.")
        sys.exit(1)
    inputs = argv[1:]
    # If single arg is a directory, expand
    if len(inputs) == 1 and os.path.isdir(inputs[0]):
        dirp = inputs[0]
        inputs = [os.path.join(dirp, fn) for fn in os.listdir(dirp) if os.path.isfile(os.path.join(dirp, fn))]
    out_dir = "harvest_output"
    ensure_dir(out_dir)
    provenance = {"generated_at": datetime.utcnow().isoformat() + "Z", "sources": []}
    for src in inputs:
        try:
            prov = process_source(src, out_dir)
            provenance["sources"].append(prov)
            print(f" -> wrote {prov['output_csv']} (records: {prov['record_count']})")
        except Exception as e:
            provenance["sources"].append({"source": src, "error": str(e)})
            print(f"Error processing {src}: {e}")
    prov_path = os.path.join(out_dir, "provenance.json")
    with open(prov_path, "w") as f:
        json.dump(provenance, f, indent=2)
    print(f"Provenance written to {prov_path}")

if __name__ == "__main__":
    main(sys.argv)
