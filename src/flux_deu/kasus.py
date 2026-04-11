"""
Kasus-Modul — Kasus-basierte Zugriffssteuerung.

German cases map directly to capability-based access control:

    Nominativ  → visible scope    (CAP_PUBLIC)    — subject is observable
    Akkusativ  → object scope     (CAP_READWRITE) — direct read/write target
    Dativ      → indirect scope   (CAP_REFERENCE) — reference/indirect access
    Genitiv    → owner scope      (CAP_TRANSFER)  — capability transfer

Each Kasus maps to a CAP_REQUIRE trust level enforced by the VM.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Kasus-Enumeration ──────────────────────────────────────────────────

class Kasus(enum.Enum):
    """Die vier deutschen Fälle mit ihren Zugriffsstufen."""

    NOMINATIV = "Nominativ"
    AKKUSATIV = "Akkusativ"
    DATIV = "Dativ"
    GENITIV = "Genitiv"


# ── Capability levels (parallel to Kasus) ─────────────────────────────

class CapLevel(enum.IntEnum):
    """Capability trust levels mapped from Kasus."""
    CAP_PUBLIC = 0      # Nominativ — freely visible
    CAP_REFERENCE = 1   # Dativ — reference access
    CAP_READWRITE = 2   # Akkusativ — read-write target
    CAP_TRANSFER = 3    # Genitiv — ownership transfer


# Kasus → CapLevel mapping
KASUS_TO_CAP: Dict[Kasus, CapLevel] = {
    Kasus.NOMINATIV: CapLevel.CAP_PUBLIC,
    Kasus.AKKUSATIV: CapLevel.CAP_READWRITE,
    Kasus.DATIV: CapLevel.CAP_REFERENCE,
    Kasus.GENITIV: CapLevel.CAP_TRANSFER,
}

# Inverse mapping
CAP_TO_KASUS: Dict[CapLevel, Kasus] = {v: k for k, v in KASUS_TO_CAP.items()}


# ── German article lookup for case detection ──────────────────────────

# Each article determines the case (narrowing down from context)
ARTICLE_KASUS: Dict[str, List[Kasus]] = {
    # Definite articles
    "der": [Kasus.NOMINATIV, Kasus.GENITIV],   # mask. Nom / fem/neut Gen
    "die": [Kasus.NOMINATIV, Kasus.AKKUSATIV],  # fem/plural Nom+Acc
    "das": [Kasus.NOMINATIV, Kasus.AKKUSATIV],  # neut Nom+Acc
    "den": [Kasus.AKKUSATIV],                    # mask Akk
    "dem": [Kasus.DATIV],                        # mask/neut Dat
    "des": [Kasus.GENITIV],                      # mask Gen
    "derer": [Kasus.GENITIV],                    # plural Gen
    # Indefinite articles
    "ein": [Kasus.NOMINATIV, Kasus.AKKUSATIV],
    "eine": [Kasus.NOMINATIV, Kasus.AKKUSATIV],
    "einem": [Kasus.DATIV],
    "eines": [Kasus.GENITIV],
    # Demonstrative
    "dieser": [Kasus.NOMINATIV, Kasus.GENITIV],
    "diese": [Kasus.NOMINATIV, Kasus.AKKUSATIV],
    "dieses": [Kasus.NOMINATIV, Kasus.AKKUSATIV],
    "diesem": [Kasus.DATIV],
    "diesen": [Kasus.AKKUSATIV],
}


# ── Geschlecht (Gender) as nominal typing ──────────────────────────────

class Geschlecht(enum.Enum):
    """German grammatical gender as type class marker."""
    MASKULINUM = "der"
    FEMININUM = "die"
    NEUTRUM = "das"


GENDER_ARTICLES: Dict[str, Geschlecht] = {
    "der": Geschlecht.MASKULINUM,
    "die": Geschlecht.FEMININUM,
    "das": Geschlecht.NEUTRUM,
}


# ── KasusScope — a scoped binding with case annotation ─────────────────

@dataclass
class KasusScope:
    """
    A variable binding annotated with its Kasus-derived capability level.

    The scope tracks what case-level access the current context holds
    for a given symbol.
    """
    symbol: str
    kasus: Kasus
    cap_level: CapLevel = field(init=False)
    gender: Optional[Geschlecht] = None
    owner: Optional[str] = None  # For Genitiv: who owns this?

    def __post_init__(self):
        self.cap_level = KASUS_TO_CAP[self.kasus]

    def can_access(self, required: CapLevel) -> bool:
        """Check if this scope's capability meets the required level."""
        return self.cap_level >= required

    def __repr__(self):
        g = f" [{self.gender.value}]" if self.gender else ""
        o = f" (von {self.owner})" if self.owner else ""
        return f"KasusScope({self.symbol}, {self.kasus.value}, {self.cap_level.name}{g}{o})"


# ── KasusValidator ─────────────────────────────────────────────────────

class KasusValidator:
    """
    Validates and enforces Kasus-based access control.

    Usage:
        validator = KasusValidator()
        validator.define_scope("x", Kasus.AKKUSATIV)
        validator.check_access("x", CapLevel.CAP_READWRITE)  # True
        validator.check_access("x", CapLevel.CAP_TRANSFER)   # False
    """

    def __init__(self):
        self._scopes: Dict[str, KasusScope] = {}
        self._access_log: List[Tuple[str, CapLevel, bool]] = []

    def define_scope(
        self,
        symbol: str,
        kasus: Kasus,
        gender: Optional[Geschlecht] = None,
        owner: Optional[str] = None,
    ) -> KasusScope:
        """Define a new Kasus-scoped symbol."""
        scope = KasusScope(
            symbol=symbol,
            kasus=kasus,
            gender=gender,
            owner=owner,
        )
        self._scopes[symbol] = scope
        return scope

    def resolve_kasus(self, article: str) -> List[Kasus]:
        """Given a German article, return possible Kasus values."""
        return ARTICLE_KASUS.get(article.lower(), [])

    def check_access(self, symbol: str, required: CapLevel) -> bool:
        """Check whether `symbol`'s current scope permits `required` level."""
        scope = self._scopes.get(symbol)
        if scope is None:
            return False
        allowed = scope.can_access(required)
        self._access_log.append((symbol, required, allowed))
        return allowed

    def get_scope(self, symbol: str) -> Optional[KasusScope]:
        return self._scopes.get(symbol)

    def all_scopes(self) -> Dict[str, KasusScope]:
        return dict(self._scopes)

    def access_log(self) -> List[Tuple[str, CapLevel, bool]]:
        return list(self._access_log)

    def clear(self):
        self._scopes.clear()
        self._access_log.clear()
