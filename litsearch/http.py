from __future__ import annotations

import os
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_local = threading.local()


def session() -> requests.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        retry = Retry(total=5, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset({"GET", "PUT", "POST"}), respect_retry_after_header=True)
        s.mount("https://", HTTPAdapter(max_retries=retry))
        mail = os.getenv("OPENALEX_EMAIL", "")
        s.headers["User-Agent"] = "litsearch/1.0" + (f" (mailto:{mail})" if mail else "")
        _local.s = s
    return s


def get_json(url, params=None, headers=None, timeout=40):
    r = session().get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def put_json(url, body, headers=None, timeout=40):
    r = session().put(url, json=body, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()
