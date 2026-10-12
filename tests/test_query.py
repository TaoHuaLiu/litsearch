from pathlib import Path

import pytest

from litsearch.cli import load_queries
from litsearch.query import (ELSEVIER, IEEE, OPENALEX, SCHOLAR, TANDF, WILEY, And, Doc, Field, Near, Not, Or,
                             QueryError, Range, Term, matches, parse, render, render_fitted,
                             year_bounds)

ROOT = Path(__file__).resolve().parent.parent


def m(q, title="", abstract="", **kw):
    return matches(parse(q), Doc(title=title, abstract=abstract, **kw))


def test_example_queries_parse_and_render():
    qs = load_queries(str(ROOT / "queries.txt"))
    assert len(qs) == 4
    for _, text in qs:
        ast = parse(text)
        assert isinstance(ast, And)
        for d in (OPENALEX, SCHOLAR, IEEE, ELSEVIER):
            assert render(ast, d)
    # en dash normalised
    assert m('"human-automation interaction"', abstract="Human–automation interaction study")


def test_precedence_and_implicit_and():
    assert parse("a OR b AND c") == Or((Term("a"), And((Term("b"), Term("c")))))
    assert parse("a b") == And((Term("a"), Term("b")))
    assert parse("a AND NOT b") == And((Term("a"), Not(Term("b"))))
    assert parse("a -b") == And((Term("a"), Not(Term("b"))))
    assert parse('-"x y"') == Not(Term("x y", True))


def test_nesting_and_case_insensitive_ops():
    assert m("(a or (b and c)) and not d", abstract="b c")
    assert not m("(a or (b and c)) and not d", abstract="b c d")


def test_phrase_and_hyphen():
    assert m('"human-robot interaction"', abstract="about human robot interaction")
    assert not m('"robot human"', abstract="human robot")


def test_wildcards():
    assert m("explain*", abstract="explainable systems")
    assert m("transparen?y", abstract="transparency")
    assert not m("explain*", abstract="plain")


def test_proximity():
    a = "transparency strongly affects user trust"
    assert m("transparency NEAR/3 trust", abstract=a)
    assert not m("transparency NEAR/1 trust", abstract=a)
    assert m("trust NEAR/3 transparency", abstract=a)          # unordered
    assert not m("trust NEXT/3 transparency", abstract=a)      # ordered
    assert m("transparency NEXT/3 trust", abstract=a)
    assert m('("explainable" OR transparency) W/3 trust', abstract=a)


def test_fields_and_year():
    assert m('title:"adaptive transparency"', title="Adaptive transparency in HAT")
    assert not m('title:"adaptive transparency"', title="x", abstract="adaptive transparency")
    assert m("author:smith", title="x", authors="John Smith")
    assert m("trust year:2020-2024", abstract="trust", year=2021)
    assert not m("trust year:>=2022", abstract="trust", year=2021)
    assert year_bounds(parse("trust year:2020-2024 year:<=2022")) == (2020, 2022)
    assert parse("year:>2019") == Range("year", 2020, None)


def test_title_abstract_boundary_not_matched():
    assert not m('"alpha beta"', title="alpha", abstract="beta")


@pytest.mark.parametrize("bad", ['("a" OR "b"', 'a AND', '"unclosed', 'a)', 'foo:"x"', 'year:abcd', ""])
def test_errors(bad):
    with pytest.raises(QueryError):
        parse(bad)


def test_render_dialects():
    ast = parse('("a b" OR c) AND -d AND x NEAR/4 y AND author:smith')
    assert render(ast, OPENALEX) == '("a b" OR c) AND NOT d AND (x AND y)'
    assert render(ast, SCHOLAR) == '("a b" OR c) -d (x y)'
    assert render(ast, IEEE) == '("a b" OR c) AND NOT d AND (x NEAR/4 y)'
    assert "W/4" in render(ast, ELSEVIER)
    assert render(parse("explain*"), SCHOLAR) == "explain"
    assert render(parse("explain*"), OPENALEX) == "explain*"


def test_fitting_limits():
    ast = parse(" AND ".join(f'("alpha{i} beta" OR "gamma{i} delta")' for i in range(10)))
    s, trunc = render_fitted(ast, SCHOLAR)
    assert trunc and len(s) <= 250
    s, trunc = render_fitted(ast, ELSEVIER)
    assert trunc and s
    s, trunc = render_fitted(parse("a OR b"), SCHOLAR)
    assert not trunc


def test_field_node_render_is_superset():
    assert render(parse('title:"x y" AND z'), OPENALEX) == '"x y" AND z'
    assert isinstance(parse("title:(a OR b)"), Field)
    assert isinstance(parse("a NEAR/2 b"), Near)


def test_tandf_and_wiley_dialects():
    ast = parse('("digital twin" OR cps) AND (maint* OR "remaining useful life") AND NOT hype? AND a NEAR/5 b')
    assert render(ast, TANDF) == ('("digital twin" OR cps) AND (maint* OR "remaining useful life") '
                                  'AND NOT hype? AND ("a b"~5)')
    # proximity needs two single words, otherwise downgraded to AND
    assert render(parse('"x y" NEAR/3 z'), TANDF) == '("x y" AND z)'
    # Wiley: no proximity, only * is kept
    assert render(ast, WILEY) == ('("digital twin" OR cps) AND (maint* OR "remaining useful life") '
                                  'AND NOT hype AND (a AND b)')


def test_scholar_allintitle():
    q = 'title:(maintenance "digital twin" -Reviews -"supply chain") year:2026'
    s, cut = render_fitted(parse(q), SCHOLAR)
    assert s == 'allintitle: maintenance "digital twin" -Reviews -"supply chain"' and not cut
    s, _ = render_fitted(parse('title:"x y" AND -title:z'), SCHOLAR)
    assert s == 'allintitle: "x y" -z'
    # mixed title / anywhere: Scholar cannot scope part of a query, keep the superset
    s, _ = render_fitted(parse('title:"x y" AND z'), SCHOLAR)
    assert s == '"x y" z'
    # other engines unchanged
    assert render_fitted(parse(q), OPENALEX)[0] == '(maintenance AND "digital twin" AND NOT Reviews AND NOT "supply chain")'


def test_scholar_allintitle_fits_limit():
    q = "title:(" + " ".join(f'"alpha{i} beta"' for i in range(30)) + ")"
    s, cut = render_fitted(parse(q), SCHOLAR)
    assert cut and s.startswith("allintitle: ") and len(s) <= 250
