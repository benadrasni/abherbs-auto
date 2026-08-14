"""Wikidata/IPNI id replacements previously hardcoded in add_plant.py."""

import json
import os

_OVERRIDES = None


def _data_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "data", "ipni_overrides.json")


def load_overrides():
    global _OVERRIDES
    if _OVERRIDES is None:
        with open(_data_path(), encoding="utf-8") as handle:
            _OVERRIDES = json.load(handle)
    return _OVERRIDES


def apply(ipni_id):
    if not ipni_id:
        return ipni_id
    return load_overrides().get(ipni_id, ipni_id)
