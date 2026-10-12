import litsearch.doi as D
from litsearch.models import Record

R = Record(title="Adaptive Transparency: A Study of Trust", authors=["A Smith", "B Jones"], year=2025)


def test_judge_high_confidence():
    assert D.judge(R, "Adaptive transparency - a study of trust", 2025, ["Alice Smith"]) == D.HIGH


def test_judge_year_and_author_rejections():
    assert D.judge(R, R.title, 2019, ["Alice Smith"]) is None          # year too far
    assert D.judge(R, R.title, 2024, ["Alice Smith"]) == D.HIGH        # ±1 accepted (preprint vs published)
    assert D.judge(R, R.title, 2025, ["Zed Other"]) is None            # different first author
    assert D.judge(R, "Completely different title about something", 2025, ["Alice Smith"]) is None


def test_judge_missing_info_is_to_check():
    assert D.judge(Record(title=R.title, authors=["A Smith"]), R.title, 2025, ["Alice Smith"]) == D.CHECK
    assert D.judge(Record(title=R.title, year=2025), R.title, 2025, ["Alice Smith"]) == D.CHECK


def test_truncated_title_prefix():
    r = Record(title="Adaptive Transparency: A Study of …", authors=["A Smith"], year=2025)
    assert D.judge(r, "Adaptive Transparency: A Study of Trust in Autonomous Agents", 2025, ["Alice Smith"]) == D.CHECK
    short = Record(title="Adaptive …", authors=["A Smith"], year=2025)  # too short to trust
    assert D.judge(short, "Adaptive Transparency: A Study of Trust in Autonomous Agents", 2025, ["Alice Smith"]) is None


def test_surname_formats():
    assert D.surname("Smith, J") == D.surname("J Smith") == D.surname("Jane Smith") == "smith"


def test_resolve_falls_back_to_crossref_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake(url, params=None, **kw):
        calls.append(url)
        if "openalex" in url:
            return {"results": []}
        return {"message": {"items": [{"DOI": "10.1/XYZ", "title": [R.title], "issued": {"date-parts": [[2025]]},
                                       "author": [{"family": "Smith"}]}]}}

    monkeypatch.setattr(D, "get_json", fake)
    recs = [Record(title=R.title, authors=R.authors, year=2025), Record(title="Has one", doi="https://doi.org/10.5/A")]
    cache = tmp_path / "c.json"
    D.resolve(recs, log=lambda m: None, cache_path=cache)
    assert (recs[0].doi, recs[0].doi_source, recs[0].doi_confidence) == ("10.1/xyz", "crossref", D.HIGH)
    assert (recs[1].doi, recs[1].doi_source) == ("10.5/a", "fournie")
    n = len(calls)
    again = [Record(title=R.title, authors=R.authors, year=2025)]
    D.resolve(again, log=lambda m: None, cache_path=cache)
    assert again[0].doi == "10.1/xyz" and len(calls) == n  # served from cache


def test_network_error_not_cached(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("net")
    monkeypatch.setattr(D, "get_json", boom)
    r = Record(title=R.title, authors=R.authors, year=2025)
    cache = tmp_path / "c.json"
    D.resolve([r], log=lambda m: None, cache_path=cache)
    assert not r.doi and "error" not in cache.read_text()


def test_provided_doi_wins_over_resolved_on_merge():
    from litsearch.enrich import dedupe
    a = Record(title="X Y Z study", year=2020, doi="10.1/a", doi_source="openalex", doi_confidence=D.HIGH, sources={"pop"})
    b = Record(title="X Y Z study", year=2020, doi="10.1/a", doi_source="fournie", sources={"ebsco"})
    (r,) = dedupe([a, b])
    assert (r.doi_source, r.doi_confidence) == ("fournie", "")
