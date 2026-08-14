"""World Checklist of Vascular Plants — local SQLite, no live POWO.

Build from Kew's wcvp.zip (pipe-delimited wcvp_names.csv + wcvp_distribution.csv).
Lookup never touches Firebase.
"""

import csv
import io
import os
import sqlite3
import sys
import zipfile

csv.field_size_limit(sys.maxsize)

DEFAULT_ZIP = os.path.expanduser("~/whatsthatflower/wcvp/wcvp.zip")
DEFAULT_DB = os.path.expanduser("~/whatsthatflower/wcvp/wcvp.sqlite")

SCHEMA = """
CREATE TABLE names (
    plant_name_id INTEGER PRIMARY KEY,
    taxon_name TEXT NOT NULL,
    taxon_name_norm TEXT NOT NULL,
    taxon_authors TEXT,
    taxon_rank TEXT,
    taxon_status TEXT,
    family TEXT,
    genus TEXT,
    species TEXT,
    ipni_id TEXT,
    powo_id TEXT,
    accepted_plant_name_id INTEGER,
    lifeform TEXT
);
CREATE INDEX idx_names_norm ON names(taxon_name_norm);
CREATE INDEX idx_names_accepted ON names(accepted_plant_name_id);

CREATE TABLE distribution (
    plant_name_id INTEGER NOT NULL,
    l2 INTEGER NOT NULL,
    l3 TEXT,
    area TEXT,
    introduced INTEGER NOT NULL,
    extinct INTEGER NOT NULL,
    doubtful INTEGER NOT NULL
);
CREATE INDEX idx_dist_name ON distribution(plant_name_id);

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def normalize_name(name):
    if not name:
        return ""
    text = name.strip().lower()
    text = text.replace("×", "x").replace("✕", "x")
    parts = text.split()
    return " ".join(parts)


def connect(db_path=None):
    path = db_path or DEFAULT_DB
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "WCVP sqlite not found at %s. Run wcvp_sync.py first." % path
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _int_flag(value):
    if value in (None, ""):
        return 0
    return 1 if str(value).strip() not in ("0", "false", "False") else 0


def build_sqlite(zip_path=None, db_path=None, names_csv=None, dist_csv=None):
    """Load WCVP names + distributions into sqlite.

    Pass either zip_path (Kew wcvp.zip) or names_csv + dist_csv (fixtures).
    """
    dest = db_path or DEFAULT_DB
    directory = os.path.dirname(dest)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if os.path.isfile(dest):
        os.remove(dest)

    conn = sqlite3.connect(dest)
    conn.executescript(SCHEMA)

    if zip_path:
        with zipfile.ZipFile(zip_path) as archive:
            name_count = _load_names(conn, archive.open("wcvp_names.csv"))
            dist_count = _load_distribution(conn, archive.open("wcvp_distribution.csv"))
        source = zip_path
    else:
        if not names_csv or not dist_csv:
            raise ValueError("need zip_path or names_csv+dist_csv")
        with open(names_csv, "rb") as handle:
            name_count = _load_names(conn, handle)
        with open(dist_csv, "rb") as handle:
            dist_count = _load_distribution(conn, handle)
        source = names_csv

    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?)",
        ("source", os.path.abspath(source)),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?)",
        ("name_count", str(name_count)),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?)",
        ("dist_count", str(dist_count)),
    )
    conn.commit()
    conn.close()
    return {"db": dest, "names": name_count, "distributions": dist_count}


def _iter_csv(binary_handle):
    wrapper = io.TextIOWrapper(binary_handle, encoding="utf-8", newline="")
    try:
        for row in csv.DictReader(wrapper, delimiter="|"):
            yield row
    finally:
        try:
            wrapper.detach()
        except Exception:
            pass


def _load_names(conn, binary_handle):
    rows = []
    count = 0
    for item in _iter_csv(binary_handle):
        name = item.get("taxon_name") or ""
        if not name:
            continue
        accepted = item.get("accepted_plant_name_id") or item.get("plant_name_id")
        rows.append(
            (
                int(item["plant_name_id"]),
                name,
                normalize_name(name),
                item.get("taxon_authors") or "",
                item.get("taxon_rank") or "",
                item.get("taxon_status") or "",
                item.get("family") or "",
                item.get("genus") or "",
                item.get("species") or "",
                item.get("ipni_id") or "",
                item.get("powo_id") or "",
                int(accepted) if accepted else None,
                item.get("lifeform_description") or "",
            )
        )
        count += 1
        if len(rows) >= 5000:
            conn.executemany(
                "INSERT OR REPLACE INTO names VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            rows = []
    if rows:
        conn.executemany(
            "INSERT OR REPLACE INTO names VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    return count


def _load_distribution(conn, binary_handle):
    rows = []
    count = 0
    for item in _iter_csv(binary_handle):
        l2_raw = item.get("region_code_l2") or ""
        if not l2_raw:
            continue
        try:
            l2 = int(l2_raw)
        except ValueError:
            continue
        name_id = item.get("plant_name_id")
        if not name_id:
            continue
        rows.append(
            (
                int(name_id),
                l2,
                item.get("area_code_l3") or "",
                item.get("area") or "",
                _int_flag(item.get("introduced")),
                _int_flag(item.get("extinct")),
                _int_flag(item.get("location_doubtful")),
            )
        )
        count += 1
        if len(rows) >= 5000:
            conn.executemany(
                "INSERT INTO distribution VALUES (?,?,?,?,?,?,?)",
                rows,
            )
            rows = []
    if rows:
        conn.executemany(
            "INSERT INTO distribution VALUES (?,?,?,?,?,?,?)",
            rows,
        )
    return count


def _pick_name_row(conn, name):
    norm = normalize_name(name)
    rows = conn.execute(
        "SELECT * FROM names WHERE taxon_name_norm = ?",
        (norm,),
    ).fetchall()
    if not rows:
        return None
    def score(row):
        status = (row["taxon_status"] or "").lower()
        rank = (row["taxon_rank"] or "").lower()
        accepted = 2 if status == "accepted" else 1 if status == "synonym" else 0
        species = 1 if rank == "species" else 0
        return (accepted, species)

    rows = sorted(rows, key=score, reverse=True)
    return rows[0]


def _accepted_row(conn, row):
    if not row:
        return None
    status = (row["taxon_status"] or "").lower()
    accepted_id = row["accepted_plant_name_id"]
    if status == "accepted" or not accepted_id or accepted_id == row["plant_name_id"]:
        return row
    accepted = conn.execute(
        "SELECT * FROM names WHERE plant_name_id = ?",
        (accepted_id,),
    ).fetchone()
    return accepted or row


def lookup(name, db_path=None, include_introduced=True):
    """Resolve a Latin name to the accepted WCVP record + TDWG L2/L3.

    include_introduced=True matches the live identifier (plants you can
    encounter, not only the native range). Extinct and doubtful areas drop out.
    """
    conn = connect(db_path)
    try:
        hit = _pick_name_row(conn, name)
        if not hit:
            return None
        accepted = _accepted_row(conn, hit)
        if not accepted:
            return None

        dist_rows = conn.execute(
            "SELECT * FROM distribution WHERE plant_name_id = ?",
            (accepted["plant_name_id"],),
        ).fetchall()
        native_l2 = set()
        introduced_l2 = set()
        native_l3 = []
        introduced_l3 = []
        for row in dist_rows:
            if row["extinct"] or row["doubtful"]:
                continue
            if row["introduced"]:
                introduced_l2.add(row["l2"])
                if row["l3"]:
                    introduced_l3.append(row["l3"])
            else:
                native_l2.add(row["l2"])
                if row["l3"]:
                    native_l3.append(row["l3"])

        if include_introduced:
            l2 = sorted(native_l2 | introduced_l2)
            l3 = native_l3 + introduced_l3
        else:
            l2 = sorted(native_l2)
            l3 = list(native_l3)

        synonyms = []
        for row in conn.execute(
            "SELECT taxon_name, taxon_authors, ipni_id, taxon_status "
            "FROM names WHERE accepted_plant_name_id = ? AND plant_name_id != ?",
            (accepted["plant_name_id"], accepted["plant_name_id"]),
        ):
            if (row["taxon_status"] or "").lower() == "synonym":
                synonyms.append(
                    {
                        "name": row["taxon_name"],
                        "authors": row["taxon_authors"],
                        "ipni_id": row["ipni_id"],
                    }
                )

        return {
            "plant_name_id": accepted["plant_name_id"],
            "query_name": hit["taxon_name"],
            "query_status": hit["taxon_status"],
            "accepted_name": accepted["taxon_name"],
            "author": accepted["taxon_authors"],
            "rank": accepted["taxon_rank"],
            "status": accepted["taxon_status"],
            "family": accepted["family"],
            "genus": accepted["genus"],
            "species": accepted["species"],
            "ipni_id": accepted["ipni_id"],
            "powo_id": accepted["powo_id"],
            "lifeform": accepted["lifeform"],
            "l2": l2,
            "l3": l3,
            "native_l2": sorted(native_l2),
            "introduced_l2": sorted(introduced_l2),
            "native_l3": native_l3,
            "introduced_l3": introduced_l3,
            "synonyms": synonyms,
        }
    finally:
        conn.close()
