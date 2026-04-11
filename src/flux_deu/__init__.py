"""
FLUX-deu — Fluide Sprache Universelle Ausführung

Deutsch-zuerst NL-Laufzeitumgebung mit Kasus-basierter Zugriffssteuerung.
German-first natural-language runtime where German grammar shapes the
architecture: Kasus → scope control, Verbposition → execution order,
Getrennte Verben → continuations, Komposita → type composition.
"""

__version__ = "0.1.0"
__title__ = "FLUX-deu"

from flux_deu.kasus import Kasus, KasusValidator
from flux_deu.trennverben import TrennverbHandler
from flux_deu.interpreter import FluxInterpreterDeu

__all__ = [
    "Kasus",
    "KasusValidator",
    "TrennverbHandler",
    "FluxInterpreterDeu",
]
