from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Record:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    publication: str = ""
    abstract: str = ""
    doi: str = ""
    doi_source: str = ""  # fournie | openalex | crossref
    doi_confidence: str = ""  # élevée | à vérifier (only for resolved DOIs)
    url: str = ""
    abstract_is_snippet: bool = False
    sources: set[str] = field(default_factory=set)
    queries: list[str] = field(default_factory=list)
    match: str = ""

    def has_abstract(self) -> bool:
        return bool(self.abstract) and not self.abstract_is_snippet


def clean_doi(doi: str | None) -> str:
    if not doi:
        return ""
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I).lower()


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()
