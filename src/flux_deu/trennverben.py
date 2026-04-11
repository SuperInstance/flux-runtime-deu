"""
Trennverben-Modul — Getrennte Verben als Continuation-Muster.

German separable-prefix verbs (anfangen→fang...an, aufmachen→mach...auf)
map to continuation/coroutine bytecode patterns:

    aufmachen → PREPARE + ACTIVATE (two-phase)
    anfangen  → SETUP   + EXECUTE  (two-phase)
    ausführen → BUILD   + RUN      (compile then execute)
    abschließen → FINALIZE + CLOSE (finalize then close)
    einrichten → INIT    + CONFIGURE (init then configure)

The prefix is compiled as a CONT_PREPARE instruction, and the
separated suffix (at clause end) emits CONT_COMPLETE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Tuple


# ── Continuation opcodes (bytecode level) ─────────────────────────────

class ContOp(Enum):
    """Bytecode continuation operations mapped from Trennverb patterns."""
    CONT_PREPARE = auto()    # prefix part: prepare / setup / build
    CONT_COMPLETE = auto()   # suffix part: activate / execute / run
    CONT_SUSPEND = auto()    # yield point in between
    CONT_RESUME = auto()     # resume after CONT_SUSPEND


# ── Separable verb registry ───────────────────────────────────────────

@dataclass(frozen=True)
class TrennverbEntry:
    """
    A registered separable verb with its prefix and stem.

    Example: aufmachen → prefix="auf", stem="machen"
    The semantic class determines what CONT pattern it maps to.
    """
    infinitive: str         # "aufmachen"
    prefix: str             # "auf"
    stem: str               # "machen"
    semantic_class: str     # "PREPARE_ACTIVATE"
    description_de: str     # "vorbereiten und dann aktivieren"


# Core Trennverb registry
TRENNVERB_REGISTRY: Dict[str, TrennverbEntry] = {}


def _register(infinitive: str, prefix: str, stem: str,
              semantic_class: str, description_de: str):
    entry = TrennverbEntry(infinitive, prefix, stem, semantic_class, description_de)
    TRENNVERB_REGISTRY[infinitive] = entry


# ── Register standard separable verbs ─────────────────────────────────

# Phase: SETUP → EXECUTE
_register("anfangen",  "an",   "fangen",  "SETUP_EXECUTE",     "einrichten und dann ausführen")
_register("aufbauen",  "auf",  "bauen",   "SETUP_EXECUTE",     "konstruieren und aufstellen")

# Phase: PREPARE → ACTIVATE
_register("aufmachen", "auf",  "machen",  "PREPARE_ACTIVATE",  "vorbereiten und dann aktivieren")
_register("einschalten", "ein", "schalten", "PREPARE_ACTIVATE", "einschalten und starten")

# Phase: BUILD → RUN
_register("ausführen", "aus",  "führen",  "BUILD_RUN",         "bauen und dann ausführen")
_register("herstellen","her",  "stellen", "BUILD_RUN",         "erzeugen und bereitstellen")

# Phase: FINALIZE → CLOSE
_register("abschließen","ab",  "schließen","FINALIZE_CLOSE",   "abschließen und beenden")
_register("zumachen",  "zu",   "machen",  "FINALIZE_CLOSE",    "schließen und beenden")

# Phase: INIT → CONFIGURE
_register("einrichten","ein",  "richten", "INIT_CONFIGURE",    "initialisieren und konfigurieren")
_register("aufstellen","auf",  "stellen", "INIT_CONFIGURE",    "aufbauen und einrichten")

# Phase: DOWNLOAD → STORE
_register("herunterladen", "herunter", "laden", "DOWNLOAD_STORE", "herunterladen und speichern")
_register("zurückgeben", "zurück", "geben", "DOWNLOAD_STORE", "zurückgeben und ablegen")


# ── Semantic class → continuation pattern mapping ─────────────────────

SEMANTIC_CONT_PATTERN: Dict[str, Tuple[ContOp, ContOp]] = {
    "SETUP_EXECUTE":      (ContOp.CONT_PREPARE, ContOp.CONT_COMPLETE),
    "PREPARE_ACTIVATE":   (ContOp.CONT_PREPARE, ContOp.CONT_COMPLETE),
    "BUILD_RUN":          (ContOp.CONT_PREPARE, ContOp.CONT_COMPLETE),
    "FINALIZE_CLOSE":     (ContOp.CONT_PREPARE, ContOp.CONT_COMPLETE),
    "INIT_CONFIGURE":     (ContOp.CONT_PREPARE, ContOp.CONT_COMPLETE),
    "DOWNLOAD_STORE":     (ContOp.CONT_PREPARE, ContOp.CONT_COMPLETE),
}


# ── TrennverbHandler ──────────────────────────────────────────────────

class TrennverbHandler:
    """
    Detects, parses, and compiles German separable-prefix verbs
    into continuation bytecode patterns.

    Detection strategy:
    1. Look up infinitive in TRENNVERB_REGISTRY (exact match)
    2. Try prefix-stem splitting on known prefixes
    3. Regex fallback for stem...prefix patterns in text
    """

    KNOWN_PREFIXES = sorted(
        {e.prefix for e in TRENNVERB_REGISTRY.values()},
        key=len,
        reverse=True,
    )

    # Pattern to match "stem + ... + prefix" in running text
    # e.g., "mach die Tür auf" → stem="mach", prefix="auf"
    _SPLIT_PATTERN = re.compile(
        r"(\w+)\s+(?:.*?)\s+(\w{2,6})\s*$",
    )

    def __init__(self):
        self._detected: List[TrennverbEntry] = []
        self._bytecode: List[Tuple[ContOp, str]] = []

    def lookup(self, infinitive: str) -> Optional[TrennverbEntry]:
        """Look up a separable verb by infinitive form."""
        return TRENNVERB_REGISTRY.get(infinitive)

    def detect_infinitive(self, verb: str) -> Optional[TrennverbEntry]:
        """Try to detect if `verb` is a registered separable verb."""
        return TRENNVERB_REGISTRY.get(verb)

    def try_split(self, word: str) -> Optional[Tuple[str, str]]:
        """
        Try to split `word` into (prefix, stem).
        Returns (prefix, stem) if found, None otherwise.
        """
        word_lower = word.lower()
        for prefix in self.KNOWN_PREFIXES:
            if word_lower.startswith(prefix):
                stem = word_lower[len(prefix):]
                # Verify: the full infinitive must exist in registry
                if f"{prefix}{stem}" in TRENNVERB_REGISTRY:
                    return (prefix, stem)
        return None

    def detect_in_sentence(self, sentence: str) -> Optional[Dict]:
        """
        Detect separable verb pattern in a sentence.

        Looks for pattern: "stem ... prefix" at sentence boundaries.
        E.g., "mach die Tür auf" → stem="mach", prefix="auf",
              infinitive="aufmachen"

        Returns dict with detection info or None.
        """
        sentence_lower = sentence.lower().strip()
        # Try to find stem...prefix pattern
        for prefix in self.KNOWN_PREFIXES:
            # Check if sentence ends with the prefix as a separate word
            if sentence_lower.endswith(f" {prefix}"):
                # Find potential stem verb earlier in sentence
                words = sentence_lower.split()
                if len(words) >= 2:
                    potential_stem = words[0]
                    # Direct match
                    infinitive = f"{prefix}{potential_stem}"
                    if infinitive in TRENNVERB_REGISTRY:
                        entry = TRENNVERB_REGISTRY[infinitive]
                        return {
                            "infinitive": entry.infinitive,
                            "prefix": prefix,
                            "stem": potential_stem,
                            "sentence": sentence,
                            "entry": entry,
                        }
                    # Try with common conjugation suffixes appended
                    for suffix in ("en", "n", "e", "t", "st", "ern"):
                        infinitive = f"{prefix}{potential_stem}{suffix}"
                        if infinitive in TRENNVERB_REGISTRY:
                            entry = TRENNVERB_REGISTRY[infinitive]
                            return {
                                "infinitive": entry.infinitive,
                                "prefix": prefix,
                                "stem": potential_stem,
                                "sentence": sentence,
                                "entry": entry,
                            }
        return None

    def compile_continuation(self, entry: TrennverbEntry) -> List[Tuple[ContOp, str]]:
        """
        Compile a separable verb into continuation bytecode pairs.

        Returns a list of (ContOp, label) tuples.
        """
        pattern = SEMANTIC_CONT_PATTERN.get(entry.semantic_class)
        if pattern is None:
            pattern = (ContOp.CONT_PREPARE, ContOp.CONT_COMPLETE)

        ops = [
            (pattern[0], f"{entry.prefix}_{entry.stem}_prepare"),
            (ContOp.CONT_SUSPEND, f"{entry.prefix}_{entry.stem}_yield"),
            (ContOp.CONT_RESUME, f"{entry.prefix}_{entry.stem}_resume"),
            (pattern[1], f"{entry.prefix}_{entry.stem}_complete"),
        ]
        self._bytecode.extend(ops)
        return ops

    def detected(self) -> List[TrennverbEntry]:
        return list(self._detected)

    def bytecode(self) -> List[Tuple[ContOp, str]]:
        return list(self._bytecode)

    def reset(self):
        self._detected.clear()
        self._bytecode.clear()

    @property
    def registry_size(self) -> int:
        return len(TRENNVERB_REGISTRY)
