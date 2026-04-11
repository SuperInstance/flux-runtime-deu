"""
FLUX-DEU Bridge Adapter — Kasus-basierte Brücke zum Typsystem

Exposes the German Kasus (case), Geschlecht (gender), and capability
system to the A2A type-safe cross-language bridge.

German's four cases map to capability-based access control:
    Nominativ → CAP_PUBLIC (observable)
    Akkusativ → CAP_READWRITE (mutable target)
    Dativ     → CAP_REFERENCE (reference/indirect)
    Genitiv   → CAP_TRANSFER  (ownership)

Gender (Geschlecht) maps to nominal type markers:
    Maskulinum → der → Active type
    Femininum  → die → Passive type
    Neutrum    → das → Abstract type

Interface:
    adapter = DeuBridgeAdapter()
    types = adapter.export_types()
    local = adapter.import_type(universal)
    cost = adapter.bridge_cost("zho")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from flux_deu.kasus import Kasus, Geschlecht, CapLevel, KASUS_TO_CAP
from flux_deu.kasus_capability import (
    ExtendedCap,
    KASUS_TO_EXTENDED_CAP,
)


# ══════════════════════════════════════════════════════════════════════
# Common bridge types
# ══════════════════════════════════════════════════════════════════════

@dataclass
class BridgeCost:
    numeric_cost: float
    information_loss: list[str] = field(default_factory=list)
    ambiguity_warnings: list[str] = field(default_factory=list)


@dataclass
class UniversalType:
    paradigm: str
    category: str
    constraints: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class BridgeAdapter(ABC):
    @abstractmethod
    def export_types(self) -> list[UniversalType]: ...

    @abstractmethod
    def import_type(self, universal: UniversalType) -> Any: ...

    @abstractmethod
    def bridge_cost(self, target_lang: str) -> BridgeCost: ...


# ══════════════════════════════════════════════════════════════════════
# DeuTypeSignature — German type representation
# ══════════════════════════════════════════════════════════════════════

@dataclass
class DeuTypeSignature:
    """Represents a German type for bridge export/import.

    Captures the four-dimensional German type system:
      - kasus: grammatical case (Nominativ, Akkusativ, Dativ, Genitiv)
      - geschlecht: grammatical gender (Maskulinum, Femininum, Neutrum)
      - numerus: number (Singular, Plural) — derived from context
      - capability_set: resulting capability levels from kasus combination

    Attributes:
        kasus: primary Kasus value
        geschlecht: grammatical Geschlecht (gender)
        numerus: singular or plural
        capability_set: set of ExtendedCap levels available
        cap_level: highest ExtendedCap from capability_set
    """
    kasus: Kasus
    geschlecht: Geschlecht | None = None
    numerus: str = "singular"
    capability_set: set[ExtendedCap] = field(default_factory=set)

    @property
    def cap_level(self) -> ExtendedCap:
        """Highest capability level available."""
        if not self.capability_set:
            return KASUS_TO_EXTENDED_CAP[self.kasus]
        return max(self.capability_set)

    @property
    def cap_name(self) -> str:
        return self.cap_level.name


# ══════════════════════════════════════════════════════════════════════
# Kasus → Universal Type Mapping
# ══════════════════════════════════════════════════════════════════════

_KASUS_TO_UNIVERSAL: dict[Kasus, tuple[str, str, float]] = {
    Kasus.NOMINATIV: ("Agent", "Observable subject — can read but not modify", 0.95),
    Kasus.AKKUSATIV: ("Patient", "Direct object — receives action / write target", 0.95),
    Kasus.DATIV:     ("Recipient", "Indirect object — reference / delegation scope", 0.95),
    Kasus.GENITIV:   ("Source", "Possessor — ownership / capability transfer", 0.95),
}

_GESCHLECHT_TO_UNIVERSAL: dict[Geschlecht, tuple[str, str, float]] = {
    Geschlecht.MASKULINUM: ("Active", "Agent-like / integer type (der)", 0.9),
    Geschlecht.FEMININUM:  ("Passive", "Container-like / string type (die)", 0.9),
    Geschlecht.NEUTRUM:    ("Abstract", "Conceptual / boolean type (das)", 0.9),
}

# Reverse mappings
_UNIVERSAL_TO_KASUS: dict[str, Kasus] = {
    "Agent":     Kasus.NOMINATIV,
    "Patient":   Kasus.AKKUSATIV,
    "Recipient": Kasus.DATIV,
    "Source":    Kasus.GENITIV,
}

_UNIVERSAL_TO_GESCHLECHT: dict[str, Geschlecht] = {
    "Active":   Geschlecht.MASKULINUM,
    "Passive":  Geschlecht.FEMININUM,
    "Abstract": Geschlecht.NEUTRUM,
}


# ══════════════════════════════════════════════════════════════════════
# Language affinity
# ══════════════════════════════════════════════════════════════════════

_LANG_AFFINITY: dict[str, dict[str, Any]] = {
    "deu": {"cost": 0.0, "loss": [], "ambiguity": []},
    "lat": {"cost": 0.25, "loss": ["Dativ distinction (Latin has 6 cases)"],
            "ambiguity": ["Latin cases are more granular — some Kasus map ambiguously"]},
    "san": {"cost": 0.40, "loss": ["Gender system (Sanskrit has 3 genders but 8 cases)",
            "Extended capability combinations"],
            "ambiguity": ["8 Sanskrit vibhakti compress into 4 Kasus"]},
    "zho": {"cost": 0.50, "loss": ["Kasus system (Chinese has no case inflection)",
            "Gender system (Chinese has no grammatical gender)"],
            "ambiguity": ["Chinese classifiers cannot express case/gender"]},
    "kor": {"cost": 0.45, "loss": ["Kasus system (Korean uses particles instead)",
            "Gender system (Korean has no grammatical gender)"],
            "ambiguity": ["Korean particles partially overlap with Kasus roles"]},
    "wen": {"cost": 0.55, "loss": ["Kasus system", "Gender system",
            "Capability granularity"],
            "ambiguity": ["Classical Chinese has no inflectional morphology"]},
}


# ══════════════════════════════════════════════════════════════════════
# DeuBridgeAdapter
# ══════════════════════════════════════════════════════════════════════

class DeuBridgeAdapter(BridgeAdapter):
    """Bridge adapter for the German (Deutsch) Kasus/Geschlecht type system.

    Exports all Kasus × Geschlecht combinations plus capability levels
    as UniversalType instances for cross-language bridging.

    Usage:
        adapter = DeuBridgeAdapter()
        types = adapter.export_types()
        cost = adapter.bridge_cost("san")
    """

    PARADIGM = "deu"

    def export_types(self) -> list[UniversalType]:
        """Export all German Kasus and Geschlecht combinations.

        Returns:
            List of UniversalType covering:
            - 4 Kasus roles (Agent, Patient, Recipient, Source)
            - 3 Geschlecht markers (Active, Passive, Abstract)
            - 6 ExtendedCap capability levels
        """
        exported: list[UniversalType] = []

        # Export Kasus types
        for kasus, (cat, desc, conf) in _KASUS_TO_UNIVERSAL.items():
            cap = KASUS_TO_EXTENDED_CAP[kasus]
            exported.append(UniversalType(
                paradigm=self.PARADIGM,
                category=cat,
                constraints={
                    "kasus": kasus.value,
                    "capability": cap.name,
                    "description": desc,
                    "type_kind": "kasus_role",
                },
                confidence=conf,
            ))

        # Export Geschlecht types
        for geschlecht, (cat, desc, conf) in _GESCHLECHT_TO_UNIVERSAL.items():
            exported.append(UniversalType(
                paradigm=self.PARADIGM,
                category=cat,
                constraints={
                    "geschlecht": geschlecht.value,
                    "article": geschlecht.value,
                    "description": desc,
                    "type_kind": "gender_marker",
                },
                confidence=conf,
            ))

        # Export extended capability levels
        for cap in ExtendedCap:
            exported.append(UniversalType(
                paradigm=self.PARADIGM,
                category="Capability",
                constraints={
                    "extended_cap": cap.name,
                    "cap_value": cap.value,
                    "description": f"Capability level {cap.value} — {cap.name}",
                    "type_kind": "capability_level",
                },
                confidence=0.9,
            ))

        return exported

    def import_type(self, universal: UniversalType) -> DeuTypeSignature:
        """Import a universal type into the German Kasus/Geschlecht system.

        Args:
            universal: A UniversalType from another runtime

        Returns:
            DeuTypeSignature with best-matching Kasus and Geschlecht
        """
        category = universal.category
        constraints = universal.constraints

        # Try to resolve Kasus from category
        kasus = _UNIVERSAL_TO_KASUS.get(category)

        # Check constraints for explicit kasus
        if kasus is None and "kasus" in constraints:
            for k in Kasus:
                if k.value.lower() == constraints["kasus"].lower():
                    kasus = k
                    break

        # Fallback
        if kasus is None:
            kasus = Kasus.NOMINATIV

        # Try to resolve Geschlecht from category or constraints
        geschlecht = _UNIVERSAL_TO_GESCHLECHT.get(category)
        if geschlecht is None and "geschlecht" in constraints:
            for g in Geschlecht:
                if g.value.lower() == constraints["geschlecht"].lower():
                    geschlecht = g
                    break

        # Map capability if present
        cap_set: set[ExtendedCap] = set()
        base_cap = KASUS_TO_EXTENDED_CAP[kasus]
        cap_set.add(base_cap)

        if "capability" in constraints:
            for cap in ExtendedCap:
                if cap.name == constraints["capability"]:
                    cap_set.add(cap)
                    break

        return DeuTypeSignature(
            kasus=kasus,
            geschlecht=geschlecht,
            capability_set=cap_set,
        )

    def bridge_cost(self, target_lang: str) -> BridgeCost:
        """Estimate bridge cost to another runtime.

        Args:
            target_lang: Target language code

        Returns:
            BridgeCost with estimated difficulty
        """
        target = target_lang.lower().strip()

        if target == self.PARADIGM:
            return BridgeCost(numeric_cost=0.0)

        affinity = _LANG_AFFINITY.get(target, {
            "cost": 0.6,
            "loss": ["All Kasus and Geschlecht distinctions"],
            "ambiguity": ["Unknown target language"],
        })

        return BridgeCost(
            numeric_cost=affinity["cost"],
            information_loss=list(affinity["loss"]),
            ambiguity_warnings=list(affinity["ambiguity"]),
        )

    def resolve_article(self, article: str) -> DeuTypeSignature | None:
        """Resolve a German article to a DeuTypeSignature.

        Args:
            article: German article (der, die, das, den, dem, des, ein, etc.)

        Returns:
            DeuTypeSignature if the article is recognized, None otherwise
        """
        from flux_deu.kasus import ARTICLE_KASUS, GENDER_ARTICLES, KasusValidator

        geschlecht = GENDER_ARTICLES.get(article.lower())
        possible_kasus = KasusValidator().resolve_kasus(article)

        if not possible_kasus and geschlecht is None:
            return None

        kasus = possible_kasus[0] if possible_kasus else Kasus.NOMINATIV

        return DeuTypeSignature(
            kasus=kasus,
            geschlecht=geschlecht,
            capability_set={KASUS_TO_EXTENDED_CAP[kasus]},
        )
