"""
FLUX-deu — Fluide Sprache Universelle Ausführung

Deutsch-zuerst NL-Laufzeitumgebung mit Kasus-basierter Zugriffssteuerung.
German-first natural-language runtime where German grammar shapes the
architecture: Kasus → scope control, Verbposition → execution order,
Getrennte Verben → continuations, Komposita → type composition.
"""

__version__ = "0.2.0"
__title__ = "FLUX-deu"

from flux_deu.kasus import Kasus, KasusValidator
from flux_deu.trennverben import TrennverbHandler
from flux_deu.interpreter import FluxInterpreterDeu
from flux_deu.vm import (
    Op, OP_NAMEN, FluxVmDeu, AusfuehrungsErgebnis,
    KasusFehler, VmFehler, schnellausfuehrung, kasus_geschuetzte_ausfuehrung,
)
from flux_deu.encoder import (
    kodiere_assembly, schnell_kodieren, deutsche_asm_zu_bytecode,
    KodierteAnweisung, kombiniertes_format,
)
from flux_deu.vocabulary import (
    WortschatzRegister, VokabelEintrag, VokabelStufe,
    gib_wortschatz, kompiliere_deutsch, suche_vokabel,
)

__all__ = [
    # Kernmodule
    "Kasus",
    "KasusValidator",
    "TrennverbHandler",
    "FluxInterpreterDeu",
    # Virtuelle Maschine
    "Op",
    "OP_NAMEN",
    "FluxVmDeu",
    "AusfuehrungsErgebnis",
    "KasusFehler",
    "VmFehler",
    "schnellausfuehrung",
    "kasus_geschuetzte_ausfuehrung",
    # Kodierer
    "kodiere_assembly",
    "schnell_kodieren",
    "deutsche_asm_zu_bytecode",
    "KodierteAnweisung",
    "kombiniertes_format",
    # Vokabelsystem
    "WortschatzRegister",
    "VokabelEintrag",
    "VokabelStufe",
    "gib_wortschatz",
    "kompiliere_deutsch",
    "suche_vokabel",
]
