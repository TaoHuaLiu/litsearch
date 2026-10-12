"""Boolean query parser, per-source renderer and client-side matcher."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FIELDS = {
    "title": "title", "ti": "title",
    "abstract": "abstract", "ab": "abstract",
    "author": "author", "authors": "author", "au": "author",
    "publication": "publication", "source": "publication", "journal": "publication",
}


class QueryError(ValueError):
    pass


# ---------------------------------------------------------------- AST
@dataclass(frozen=True)
class Term:
    text: str
    phrase: bool = False


@dataclass(frozen=True)
class And:
    items: tuple


@dataclass(frozen=True)
class Or:
    items: tuple


@dataclass(frozen=True)
class Not:
    item: object


@dataclass(frozen=True)
class Near:
    a: object
    b: object
    n: int
    ordered: bool = False


@dataclass(frozen=True)
class Field:
    name: str
    item: object


@dataclass(frozen=True)
class Range:
    field: str
    lo: int | None
    hi: int | None


# ---------------------------------------------------------------- tokenizer
_NORM = str.maketrans({
    "“": '"', "”": '"', "„": '"', "‟": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‐": "-", "‑": "-", "‒": "-",
    "–": "-", "—": "-", "−": "-", " ": " ",
})


def normalize(text: str) -> str:
    return text.translate(_NORM)


_PROX = re.compile(r"^(NEAR|NEXT|W|PRE|ONEAR)/(\d+)$", re.I)


@dataclass
class _Tok:
    kind: str  # LP RP AND OR NOT NEG NEAR PHRASE WORD FIELD RANGE
    value: object
    pos: int


def _tokenize(q: str) -> list[_Tok]:
    toks: list[_Tok] = []
    i, n = 0, len(q)
    while i < n:
        c = q[i]
        if c.isspace():
            i += 1
        elif c == "(":
            toks.append(_Tok("LP", c, i)); i += 1
        elif c == ")":
            toks.append(_Tok("RP", c, i)); i += 1
        elif c == '"':
            j = q.find('"', i + 1)
            if j < 0:
                raise QueryError(f"Unclosed quote at position {i}")
            toks.append(_Tok("PHRASE", q[i + 1:j].strip(), i)); i = j + 1
        else:
            start = i
            if c == "-" and i + 1 < n and not q[i + 1].isspace():
                toks.append(_Tok("NEG", "-", i)); i += 1
                continue
            fm = re.match(r"([A-Za-z]+):(?=[^\s:])", q[start:])
            if fm and fm.group(1).lower() in FIELDS and fm.group(1).lower() != "year":
                toks.append(_Tok("FIELD", FIELDS[fm.group(1).lower()], start))
                i = start + fm.end()
                continue
            while i < n and not q[i].isspace() and q[i] not in '()"':
                i += 1
            w = q[start:i]
            up = w.upper()
            m = _PROX.match(w)
            if up in ("AND", "&&"):
                toks.append(_Tok("AND", w, start))
            elif up in ("OR", "||"):
                toks.append(_Tok("OR", w, start))
            elif up == "NOT":
                toks.append(_Tok("NOT", w, start))
            elif m:
                kind = m.group(1).upper()
                toks.append(_Tok("NEAR", (int(m.group(2)), kind in ("NEXT", "PRE", "ONEAR")), start))
            elif w.endswith(":") and w[:-1].lower() in FIELDS:
                toks.append(_Tok("FIELD", FIELDS[w[:-1].lower()], start))
            elif w.lower().startswith("year:"):
                val = w[5:]
                if not val:  # "year: 2020"
                    while i < n and q[i].isspace():
                        i += 1
                    s2 = i
                    while i < n and not q[i].isspace() and q[i] not in "()":
                        i += 1
                    val = q[s2:i]
                toks.append(_Tok("RANGE", _parse_range(val, start), start))
            elif w.endswith(":") and ":" not in w[:-1] and w[:-1].isalpha():
                raise QueryError(f"Unknown field '{w}' at position {start} "
                                 f"(allowed: {', '.join(sorted(set(FIELDS)))}, year)")
            else:
                toks.append(_Tok("WORD", w, start))
    return toks


def _parse_range(v: str, pos: int) -> Range:
    v = v.strip()
    m = re.fullmatch(r"(>=|<=|>|<)?\s*(\d{4})", v)
    if m:
        op, y = m.group(1), int(m.group(2))
        if op in (">=",): return Range("year", y, None)
        if op == ">": return Range("year", y + 1, None)
        if op == "<=": return Range("year", None, y)
        if op == "<": return Range("year", None, y - 1)
        return Range("year", y, y)
    m = re.fullmatch(r"(\d{4})?-(\d{4})?", v)
    if m and (m.group(1) or m.group(2)):
        return Range("year", int(m.group(1)) if m.group(1) else None,
                     int(m.group(2)) if m.group(2) else None)
    raise QueryError(f"Bad year range '{v}' at position {pos} (use 2020, 2020-2024, >=2020, <=2024)")


# ---------------------------------------------------------------- parser
_START = {"LP", "PHRASE", "WORD", "NOT", "NEG", "FIELD", "RANGE"}


class _Parser:
    def __init__(self, toks: list[_Tok]):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        tok = self.t[self.i]; self.i += 1
        return tok

    def or_expr(self):
        items = [self.and_expr()]
        while (p := self.peek()) and p.kind == "OR":
            self.take(); items.append(self.and_expr())
        return _flat(Or, items)

    def and_expr(self):
        items = [self.not_expr()]
        while (p := self.peek()):
            if p.kind == "AND":
                self.take()
            elif p.kind not in _START:
                break
            items.append(self.not_expr())
        return _flat(And, items)

    def not_expr(self):
        p = self.peek()
        if p and p.kind in ("NOT", "NEG"):
            self.take()
            return Not(self.not_expr() if p.kind == "NOT" else self.near_expr())
        return self.near_expr()

    def near_expr(self):
        left = self.atom()
        while (p := self.peek()) and p.kind == "NEAR":
            self.take()
            n, ordered = p.value
            left = Near(left, self.atom(), n, ordered)
        return left

    def atom(self):
        p = self.peek()
        if p is None:
            raise QueryError("Unexpected end of query: a term was expected")
        if p.kind == "LP":
            self.take()
            node = self.or_expr()
            q = self.peek()
            if q is None or q.kind != "RP":
                raise QueryError(f"Missing ')' for '(' at position {p.pos}")
            self.take()
            return node
        if p.kind == "FIELD":
            self.take()
            return Field(p.value, self.atom())
        if p.kind == "PHRASE":
            self.take()
            if not p.value:
                raise QueryError(f"Empty phrase at position {p.pos}")
            return Term(p.value, True)
        if p.kind == "WORD":
            self.take()
            return Term(p.value, False)
        if p.kind == "RANGE":
            self.take()
            return p.value
        raise QueryError(f"Unexpected '{p.value if isinstance(p.value, str) else p.kind}' "
                         f"at position {p.pos}: a term was expected")


def _flat(cls, items):
    out = []
    for it in items:
        out.extend(it.items if isinstance(it, cls) else [it])
    return out[0] if len(out) == 1 else cls(tuple(out))


def parse(query: str):
    toks = _tokenize(normalize(query))
    if not toks:
        raise QueryError("Empty query")
    p = _Parser(toks)
    node = p.or_expr()
    if p.peek() is not None:
        raise QueryError(f"Unexpected '{p.peek().value}' at position {p.peek().pos} (unbalanced ')'?)")
    return node


def year_bounds(ast) -> tuple[int | None, int | None]:
    """Year range from top-level year: restrictors (intersection)."""
    items = ast.items if isinstance(ast, And) else (ast,)
    lo = hi = None
    for it in items:
        if isinstance(it, Range):
            if it.lo is not None: lo = it.lo if lo is None else max(lo, it.lo)
            if it.hi is not None: hi = it.hi if hi is None else min(hi, it.hi)
    return lo, hi


# ---------------------------------------------------------------- renderer
@dataclass
class Dialect:
    name: str
    and_sep: str = " AND "
    or_sep: str = " OR "
    not_fmt: str = "NOT {}"
    near_fmt: str | None = None          # e.g. "{a} NEAR/{n} {b}"
    onear_fmt: str | None = None         # ordered variant
    wildcards: bool = True               # keep * and ? in terms
    max_chars: int | None = None
    max_ops: int | None = None
    wildcard_chars: str = "*?"           # wildcard characters the engine understands
    phrase_wildcard_fmt: str | None = None  # how to write a phrase containing a wildcard, e.g. '"{}"~0'


# OpenAlex rejects wildcards inside a plain quoted phrase; "a b*"~0 (adjacent words) is accepted.
OPENALEX = Dialect("openalex", phrase_wildcard_fmt='"{}"~0')
SCHOLAR = Dialect("scholar", and_sep=" ", not_fmt="-{}", wildcards=False, max_chars=250)
IEEE = Dialect("ieee", near_fmt="{a} NEAR/{n} {b}", onear_fmt="{a} ONEAR/{n} {b}")
ELSEVIER = Dialect("elsevier", near_fmt="{a} W/{n} {b}", onear_fmt="{a} PRE/{n} {b}", max_ops=8)
# Taylor & Francis Online: "a b"~n is unordered proximity and only works between two single words
# (the check in render() falls back to AND otherwise). Syntax taken from library guides, not T&F docs.
TANDF = Dialect("tandf", near_fmt='"{a} {b}"~{n}')
# Wiley Online Library: only AND/OR/NOT, quotes, parentheses and * are documented; no proximity.
WILEY = Dialect("wiley", wildcard_chars="*")

_OPS = re.compile(r"\b(?:AND|OR|NOT)\b|\b(?:NEAR|ONEAR|W|PRE)/\d+")


def _term(t: Term, d: Dialect) -> str:
    txt = t.text.replace('"', "")
    for ch in "*?":
        if not d.wildcards or ch not in d.wildcard_chars:
            txt = txt.replace(ch, "")
    if (t.phrase or " " in txt) and d.phrase_wildcard_fmt and any(c in txt for c in "*?"):
        return d.phrase_wildcard_fmt.format(txt)
    return f'"{txt}"' if t.phrase or " " in txt else txt


def render(node, d: Dialect) -> str | None:
    """Render node in a dialect. Unsupported constructs are dropped (None) or
    downgraded (NEAR -> AND); the client-side matcher enforces the full query."""
    if isinstance(node, Term):
        return _term(node, d)
    if isinstance(node, Range):
        return None
    if isinstance(node, Field):
        return None if node.name == "author" else render(node.item, d)  # superset
    if isinstance(node, Not):
        inner = render(node.item, d)
        return d.not_fmt.format(_wrap(node.item, inner)) if inner else None
    if isinstance(node, Near):
        fmt = d.onear_fmt if node.ordered else d.near_fmt
        if fmt and isinstance(node.a, (Term, Or)) and isinstance(node.b, (Term, Or)):
            a, b = render(node.a, d), render(node.b, d)
            single = lambda x: x and not re.search(r'[\s"()]', x)
            if a and b and (fmt != TANDF.near_fmt or (single(a) and single(b))):
                return "(" + fmt.format(a=_wrap(node.a, a), b=_wrap(node.b, b), n=node.n) + ")"
        both = render(And((node.a, node.b)), d)
        return f"({both})" if both else None
    if isinstance(node, And):
        parts = [(c, render(c, d)) for c in node.items]
        parts = [(c, s) for c, s in parts if s]
        if not parts:
            return None
        return d.and_sep.join(_wrap(c, s) for c, s in parts)
    if isinstance(node, Or):
        parts = [(c, render(c, d)) for c in node.items]
        if any(s is None for _, s in parts):
            return None
        return d.or_sep.join(_wrap(c, s) for c, s in parts)
    raise TypeError(node)


def _wrap(node, s: str) -> str:
    if isinstance(node, (And, Or)) or (isinstance(node, Field) and isinstance(node.item, (And, Or))):
        return f"({s})"
    return s


def _fits(s: str | None, d: Dialect) -> bool:
    if not s:
        return False
    if d.max_chars and len(s) > d.max_chars:
        return False
    if d.max_ops and len(_OPS.findall(s)) > d.max_ops:
        return False
    return True


ALLINTITLE = "allintitle: "


def title_only(ast):
    """If every searchable clause is a title: field (or its negation), return the
    query with the fields unwrapped, else None. Lets Scholar use allintitle:."""
    items = ast.items if isinstance(ast, And) else (ast,)
    out = []
    for it in items:
        if isinstance(it, Range):
            continue
        neg = isinstance(it, Not)
        f = it.item if neg else it
        if not (isinstance(f, Field) and f.name == "title"):
            return None
        if neg:
            out.append(Not(f.item))
        else:
            out.extend(f.item.items if isinstance(f.item, And) else [f.item])
    if not out:
        return None
    return out[0] if len(out) == 1 else And(tuple(out))


def render_fitted(ast, d: Dialect) -> tuple[str | None, bool]:
    """Render and, if the dialect has size limits, keep the AND-clauses that
    fit. Returns (query, truncated)."""
    if d is SCHOLAR and (inner := title_only(ast)) is not None:
        short = Dialect(**{**d.__dict__, "max_chars": d.max_chars - len(ALLINTITLE)})
        s, cut = render_fitted(inner, short)
        return (ALLINTITLE + s if s else None), cut
    s = render(ast, d)
    if s is None or _fits(s, d) or not (d.max_chars or d.max_ops):
        return s, False
    clauses = list(ast.items) if isinstance(ast, And) else [ast]
    chosen: list = []
    for c in clauses:
        trial = render(And(tuple(chosen + [c])) if chosen else c, d)
        if _fits(trial, d):
            chosen.append(c)
    if not chosen:  # even the first clause is too big: trim OR alternatives
        c = next((c for c in clauses if render(c, d)), None)
        if isinstance(c, Or):
            alts = list(c.items)
            while len(alts) > 1:
                alts.pop()
                trial = render(Or(tuple(alts)) if len(alts) > 1 else alts[0], d)
                if _fits(trial, d):
                    return trial, True
        return (render(c, d) if c else None), True
    return render(And(tuple(chosen)) if len(chosen) > 1 else chosen[0], d), True


# ---------------------------------------------------------------- matcher
_TOK = re.compile(r"[\w*?]+")
SENT = "¶"


def tokens(text: str) -> list[str]:
    return _TOK.findall(normalize(text or "").lower())


@dataclass
class Doc:
    title: str = ""
    abstract: str = ""
    authors: str = ""
    publication: str = ""
    year: int | None = None
    _cache: dict = field(default_factory=dict, repr=False)

    def toks(self, name: str) -> list[str]:
        if name not in self._cache:
            if name == "default":
                self._cache[name] = tokens(self.title) + [SENT] + tokens(self.abstract)
            else:
                self._cache[name] = tokens(getattr(self, name if name != "author" else "authors"))
        return self._cache[name]


def _tok_matcher(t: str):
    if "*" in t or "?" in t:
        rx = re.compile("".join(r"\w*" if ch == "*" else r"\w" if ch == "?" else re.escape(ch) for ch in t))
        return rx.fullmatch
    return t.__eq__


def _term_spans(term: Term, toks: list[str]) -> list[tuple[int, int]]:
    pat = [_tok_matcher(t) for t in tokens(term.text)]
    n = len(pat)
    if not n:
        return []
    return [(i, i + n - 1) for i in range(len(toks) - n + 1)
            if all(m(toks[i + k]) for k, m in enumerate(pat))]


def _spans(node, toks):
    if isinstance(node, Term):
        return _term_spans(node, toks)
    if isinstance(node, Or):
        out = []
        for c in node.items:
            s = _spans(c, toks)
            if s is None:
                return None
            out += s
        return out
    return None


def matches(node, doc: Doc, fld: str = "default") -> bool:
    if isinstance(node, Term):
        return bool(_term_spans(node, doc.toks(fld)))
    if isinstance(node, And):
        return all(matches(c, doc, fld) for c in node.items)
    if isinstance(node, Or):
        return any(matches(c, doc, fld) for c in node.items)
    if isinstance(node, Not):
        return not matches(node.item, doc, fld)
    if isinstance(node, Field):
        return matches(node.item, doc, node.name)
    if isinstance(node, Range):
        if doc.year is None:
            return False
        return (node.lo is None or doc.year >= node.lo) and (node.hi is None or doc.year <= node.hi)
    if isinstance(node, Near):
        toks = doc.toks(fld)
        sa, sb = _spans(node.a, toks), _spans(node.b, toks)
        if sa is None or sb is None:
            return matches(node.a, doc, fld) and matches(node.b, doc, fld)
        for a0, a1 in sa:
            for b0, b1 in sb:
                if node.ordered:
                    ok = b0 > a1 and b0 - a1 - 1 <= node.n
                else:
                    ok = (b0 > a1 and b0 - a1 - 1 <= node.n) or (a0 > b1 and a0 - b1 - 1 <= node.n)
                if ok:
                    return True
        return False
    raise TypeError(node)
