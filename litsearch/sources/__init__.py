from . import acm, ieee, openalex, scholar, sciencedirect, tandf, wiley
from ..query import ELSEVIER, IEEE, OPENALEX, SCHOLAR, TANDF, WILEY

ALL = {m.NAME: m for m in (openalex, scholar, ieee, sciencedirect, acm, tandf, wiley)}
DIALECTS = {"openalex": OPENALEX, "scholar": SCHOLAR, "ieee": IEEE, "sciencedirect": ELSEVIER,
            "acm": OPENALEX, "tandf": TANDF, "wiley": WILEY}
