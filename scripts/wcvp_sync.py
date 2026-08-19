"""Download Kew WCVP and build the local sqlite cache. No Firebase."""

import argparse
import os
import sys
import urllib.request

from sources import wcvp
from sources.httputil import USER_AGENT

WCVP_ZIP_URL = "https://sftp.kew.org/pub/data-repositories/WCVP/wcvp.zip"


def download_zip(dest, url=WCVP_ZIP_URL):
    directory = os.path.dirname(dest)
    if directory:
        os.makedirs(directory, exist_ok=True)
    print("downloading %s" % url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as incoming:
        with open(dest, "wb") as outgoing:
            while True:
                chunk = incoming.read(1024 * 1024)
                if not chunk:
                    break
                outgoing.write(chunk)
    print("wrote %s (%s bytes)" % (dest, os.path.getsize(dest)))
    return dest


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Build local WCVP sqlite. Never writes to Firebase."
    )
    parser.add_argument(
        "--zip",
        default=wcvp.DEFAULT_ZIP,
        help="Path to Kew wcvp.zip (default: %s)" % wcvp.DEFAULT_ZIP,
    )
    parser.add_argument(
        "--db",
        default=wcvp.DEFAULT_DB,
        help="Output sqlite path (default: %s)" % wcvp.DEFAULT_DB,
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download wcvp.zip from Kew before building.",
    )
    parser.add_argument(
        "--names-csv",
        help="Fixture names CSV (pipe-delimited). Skips the zip.",
    )
    parser.add_argument(
        "--dist-csv",
        help="Fixture distribution CSV (pipe-delimited). Skips the zip.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.names_csv:
        summary = wcvp.build_sqlite(
            db_path=args.db, names_csv=args.names_csv, dist_csv=args.dist_csv
        )
    else:
        zip_path = args.zip
        if args.download or not os.path.isfile(zip_path):
            zip_path = download_zip(zip_path)
        print("building sqlite from %s" % zip_path)
        summary = wcvp.build_sqlite(zip_path=zip_path, db_path=args.db)
    print(
        "names: %s  distributions: %s  db: %s"
        % (summary["names"], summary["distributions"], summary["db"])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
