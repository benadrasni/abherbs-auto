"""HTTP helpers with a stable User-Agent. No Firebase."""

import json
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "whatsthatflower-ingest/0.1 (hobby; support@whatsthatflower.com)"
DEFAULT_TIMEOUT = 30


def request(url, timeout=DEFAULT_TIMEOUT, headers=None):
    merged = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, headers=merged)
    return urllib.request.urlopen(req, timeout=timeout)


def get_bytes(url, timeout=DEFAULT_TIMEOUT, headers=None):
    with request(url, timeout=timeout, headers=headers) as handle:
        return handle.read()


def get_text(url, timeout=DEFAULT_TIMEOUT, encoding="utf-8", headers=None):
    return get_bytes(url, timeout=timeout, headers=headers).decode(encoding)


def get_json(url, timeout=DEFAULT_TIMEOUT, headers=None):
    return json.loads(get_text(url, timeout=timeout, headers=headers))


def urlencode(params):
    return urllib.parse.urlencode(params)
