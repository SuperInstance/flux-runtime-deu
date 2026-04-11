"""
FLUX-deu Wortschatzsystem — Deutsche Vokabelkacheln für die Bytecode-Übersetzung.

Dieses Modul implementiert ein mehrschichtiges Vokabelsystem, bei dem deutsche
Wortmuster direkt auf FLUX-Bytecode-Vorlagen abgebildet werden. Das System
unterstützt Kasus-annotierte Einträge und lädt Vokabeldateien (.fluxvocab-deu).

Ebenen:
    Stufe 0 — Grundprimitive (laden, speichern, springe, addiere, ...)
    Stufe 1 — Zusammengesetzte Befehle (berechne, übertrage, vergleiche)
    Stufe 2 — Domänenkacheln (sortiere, filtere, aggregiere)

Jeder Vokabeleintrag kann mit einem Kasus annotiert werden, der bei der
Kompilierung die entsprechende Zugriffsebene erzwingt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flux_deu.kasus import Kasus, CapLevel, KASUS_TO_CAP


# ══════════════════════════════════════════════════════════════════════
# Vokabelstufen
# ══════════════════════════════════════════════════════════════════════

class VokabelStufe(IntEnum):
    """Stufen der Vokabelabstraktion."""
    PRIMITIV = 0     # Grundprimitive — einzelne Bytecodes
    ZUSAMMENGESETZT = 1  # Zusammengesetzt — mehrere Bytecodes
    DOMAENE = 2      # Domänenkacheln — komplexe Bytecode-Sequenzen


# ══════════════════════════════════════════════════════════════════════
# Vokabeleintrag
# ══════════════════════════════════════════════════════════════════════

@dataclass
class VokabelEintrag:
    """
    Ein einzelner Vokabeleintrag: deutsches Wortmuster → Bytecode-Vorlage.

    Attribute:
        wort:           Deutsches Schlüsselwort (z.B. "addiere", "den Wert").
        stufe:          Abstraktionsstufe (0=Primitiv, 1=Zusammengesetzt, 2=Domäne).
        muster:         Regex-Muster für die Erkennung im Quelltext.
        vorlage:        Bytecode-Assembly-Vorlage mit {platzhalter}-Ersetzungen.
        platzhalter:    Zuordnung von Platzhalternamen zu Regex-Gruppen.
        kasus:          Optionaler Kasus für die Zugriffsebene.
        beschreibung:   Deutsche Beschreibung des Eintrags.
        kategorie:      Optional: Kategorie/Tag für die Gruppierung.
        beispiele:      Liste von Beispielaufrufen.
    """
    wort: str
    stufe: VokabelStufe
    muster: re.Pattern
    vorlage: str
    platzhalter: Dict[str, int] = field(default_factory=dict)
    kasus: Optional[Kasus] = None
    beschreibung: str = ""
    kategorie: str = ""
    beispiele: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Standard-Kategorie aus dem Kasus ableiten, wenn nicht angegeben."""
        if not self.kategorie and self.kasus:
            self.kategorie = self.kasus.value

    @property
    def cap_level(self) -> Optional[CapLevel]:
        """Capability-Level aus dem Kasus ableiten."""
        if self.kasus:
            return KASUS_TO_CAP[self.kasus]
        return None

    def erkenne(self, text: str) -> Optional[Dict[str, str]]:
        """
        Erkenne dieses Vokabelmuster im übergebenen Text.

        Gibt ein Dictionary mit Platzhalter-Zuordnungen zurück oder None.
        """
        treffer = self.muster.fullmatch(text.strip())
        if not treffer:
            return None
        ergebnis = {}
        for name, group_idx in self.platzhalter.items():
            if group_idx <= len(treffer.groups()):
                ergebnis[name] = treffer.group(group_idx)
        return ergebnis

    def kompiliere(self, text: str) -> Optional[str]:
        """
        Kompiliere den Text mit diesem Vokabel zu einer Assembly-Zeichenkette.

        Gibt None zurück, wenn das Muster nicht erkannt wird.
        """
        captures = self.erkenne(text)
        if captures is None:
            return None
        assembly = self.vorlage
        for name, wert in captures.items():
            assembly = assembly.replace(f"{{{name}}}", wert.strip())
        return assembly

    def __repr__(self) -> str:
        kasus_info = f" [{self.kasus.value}]" if self.kasus else ""
        return (
            f"VokabelEintrag('{self.wort}', Stufe {self.stufe.value}{kasus_info}, "
            f"'{self.beschreibung}')"
        )


# ══════════════════════════════════════════════════════════════════════
# Vokabeldatei-Parser (.fluxvocab-deu)
# ══════════════════════════════════════════════════════════════════════

class VokabelDateiParser:
    """
    Parser für .fluxvocab-deu Dateien.

    Dateiformat:
        # Kommentarzeilen beginnen mit #
        @version 1.0
        @lang deu

        # Stufe 0 — Grundprimitive
        laden       PRIM   ADDIEREN       "MOVI {ziel}, {wert}"     ziel=1 wert=2
        speichern   PRIM   SPEICHERN      "STORE R{ziel}, R{wert}"  ziel=1 wert=2
        springe     PRIM   SPRINGEN       "JMP {adresse}"           adresse=1

        # Kasus-annotierte Einträge
        den Wert    PRIM   WERT_AKK       "MOVI R0, {zahl}"         zahl=1   @kasus:akkusativ

    Feldtrenner: Zwei oder mehr Leerzeichen / Tabulatoren.
    """

    @staticmethod
    def parse_dateiinhalt(inhalt: str) -> List[VokabelEintrag]:
        """
        Parst den Inhalt einer .fluxvocab-deu Datei.

        Returns:
            Liste der geparsten Vokabeleinträge.
        """
        eintraege: List[VokabelEintrag] = []
        metadaten: Dict[str, str] = {}

        for zeile in inhalt.splitlines():
            zeile = zeile.strip()

            # Leere Zeilen und Kommentare überspringen
            if not zeile or zeile.startswith("#"):
                continue

            # Metadaten erfassen
            if zeile.startswith("@"):
                teile = zeile.split(None, 1)
                if len(teile) == 2:
                    metadaten[teile[0]] = teile[1]
                continue

            # Vokabelzeile parsen
            eintrag = VokabelDateiParser._parse_zeile(zeile)
            if eintrag:
                eintraege.append(eintrag)

        return eintraege

    @staticmethod
    def _parse_zeile(zeile: str) -> Optional[VokabelEintrag]:
        """Parst eine einzelne Vokabelzeile."""
        # Kasus-Annotation extrahieren
        kasus: Optional[Kasus] = None
        kasus_match = re.search(r"@kasus:(\w+)", zeile, re.IGNORECASE)
        if kasus_match:
            kasus_name = kasus_match.group(1).upper()
            kasus_map = {
                "NOMINATIV": Kasus.NOMINATIV,
                "AKKUSATIV": Kasus.AKKUSATIV,
                "DATIV": Kasus.DATIV,
                "GENITIV": Kasus.GENITIV,
                "NOM": Kasus.NOMINATIV,
                "AKK": Kasus.AKKUSATIV,
                "DAT": Kasus.DATIV,
                "GEN": Kasus.GENITIV,
            }
            kasus = kasus_map.get(kasus_name)
            zeile = zeile[:kasus_match.start()].strip()

        # Felder trennen (mindestens 2 Leerzeichen)
        teile = re.split(r"\s{2,}", zeile.strip())
        if len(teile) < 3:
            return None

        wort = teile[0]
        stufe_str = teile[1].upper()
        beschreibung = teile[2] if len(teile) > 2 else ""

        # Stufe bestimmen
        stufe_map = {"PRIM": VokabelStufe.PRIMITIV, "KOMP": VokabelStufe.ZUSAMMENGESETZT, "DOM": VokabelStufe.DOMAENE}
        stufe = stufe_map.get(stufe_str, VokabelStufe.PRIMITIV)

        # Vorlage und Platzhalter extrahieren
        vorlage = ""
        platzhalter: Dict[str, int] = {}
        if len(teile) > 3:
            vorlage_teil = teile[3]
            # Versuche, Vorlage von Platzhaltern zu trennen
            vorlage_match = re.match(r'"(.+?)"', vorlage_teil)
            if vorlage_match:
                vorlage = vorlage_match.group(1)
            else:
                vorlage = vorlage_teil

        # Platzhalter aus den restlichen Teilen parsen
        for teil in teile[4:]:
            if "=" in teil:
                name, idx = teil.split("=", 1)
                try:
                    platzhalter[name.strip()] = int(idx.strip())
                except ValueError:
                    pass

        # Regex-Muster aus dem Wort erstellen
        # Ersetze {}-Platzhalter durch Regex-Gruppen
        muster_str = wort
        muster_str = re.escape(muster_str)
        # Platzhalter wie {ziel} → benannte Gruppe
        platzhalter_idx = 1
        for pname in platzhalter:
            muster_str = muster_str.replace(
                re.escape("{" + pname + "}"),
                f"(?P<{pname}>\\S+)"
            )
            platzhalter_idx += 1

        try:
            muster = re.compile(muster_str, re.IGNORECASE)
        except re.error:
            # Fallback: einfaches Wort-Muster
            muster = re.compile(re.escape(wort), re.IGNORECASE)

        return VokabelEintrag(
            wort=wort,
            stufe=stufe,
            muster=muster,
            vorlage=vorlage,
            platzhalter=platzhalter,
            kasus=kasus,
            beschreibung=beschreibung,
        )


# ══════════════════════════════════════════════════════════════════════
# Wortschatzregister — Zentrales Vokabelverzeichnis
# ══════════════════════════════════════════════════════════════════════

class WortschatzRegister:
    """
    Zentrales Verzeichnis aller deutschen Vokabeln für die FLUX-Übersetzung.

    Verwaltet Vokabeleinträge nach Stufe und Kategorie, und bietet
    Such- und Kompilierungsfunktionen.
    """

    def __init__(self):
        self._eintraege: List[VokabelEintrag] = []
        self._nach_wort: Dict[str, VokabelEintrag] = {}
        self._nach_stufe: Dict[VokabelStufe, List[VokabelEintrag]] = {
            stufe: [] for stufe in VokabelStufe
        }
        self._nach_kasus: Dict[Optional[Kasus], List[VokabelEintrag]] = {}
        self._nach_kategorie: Dict[str, List[VokabelEintrag]] = {}

    # ── Verwaltung ──────────────────────────────────────────────────

    def eintragen(self, eintrag: VokabelEintrag) -> None:
        """Trage einen neuen Vokabeleintrag in das Register ein."""
        self._eintraege.append(eintrag)
        self._nach_wort[eintrag.wort.lower()] = eintrag
        self._nach_stufe[eintrag.stufe].append(eintrag)

        kasus_schluessel = eintrag.kasus
        if kasus_schluessel not in self._nach_kasus:
            self._nach_kasus[kasus_schluessel] = []
        self._nach_kasus[kasus_schluessel].append(eintrag)

        if eintrag.kategorie:
            if eintrag.kategorie not in self._nach_kategorie:
                self._nach_kategorie[eintrag.kategorie] = []
            self._nach_kategorie[eintrag.kategorie].append(eintrag)

    def entfernen(self, wort: str) -> bool:
        """Entferne einen Eintrag nach seinem Wort."""
        wort_lower = wort.lower()
        eintrag = self._nach_wort.pop(wort_lower, None)
        if eintrag is None:
            return False
        self._eintraege.remove(eintrag)
        self._nach_stufe[eintrag.stufe].remove(eintrag)
        if eintrag.kasus in self._nach_kasus:
            self._nach_kasus[eintrag.kasus].remove(eintrag)
        if eintrag.kategorie and eintrag.kategorie in self._nach_kategorie:
            self._nach_kategorie[eintrag.kategorie].remove(eintrag)
        return True

    def laden_aus_datei(self, pfad: str | Path) -> int:
        """
        Lade Vokabeln aus einer .fluxvocab-deu Datei.

        Returns:
            Anzahl der erfolgreich geladenen Einträge.
        """
        pfad = Path(pfad)
        if not pfad.exists():
            return 0

        inhalt = pfad.read_text(encoding="utf-8")
        eintraege = VokabelDateiParser.parse_dateiinhalt(inhalt)
        for eintrag in eintraege:
            self.eintragen(eintrag)
        return len(eintraege)

    def laden_standardvokabeln(self) -> None:
        """Lade die integrierten Standardvokabeln aller Stufen."""
        for eintrag in _erstelle_standardvokabeln():
            self.eintragen(eintrag)

    # ── Abfrage ─────────────────────────────────────────────────────

    def suche(self, text: str, stufe: Optional[VokabelStufe] = None) -> List[VokabelEintrag]:
        """
        Suche nach Vokabeleinträgen, die den Text matchen.

        Args:
            text:   Zu suchender Text.
            stufe:  Optional: Nur Einträge dieser Stufe durchsuchen.
        """
        ergebnisse: List[VokabelEintrag] = []
        quellen = self._eintraege if stufe is None else self._nach_stufe.get(stufe, [])
        for eintrag in quellen:
            if eintrag.erkenne(text) is not None:
                ergebnisse.append(eintrag)
        return ergebnisse

    def kompiliere_text(self, text: str) -> Optional[str]:
        """
        Kompiliere einen deutschen Text zu FLUX-Assembly.

        Sucht in allen Stufen (0→1→2) nach einem passenden Eintrag
        und gibt die resultierende Assembly zurück.
        """
        # Zuerst Stufe 0, dann 1, dann 2 versuchen
        for stufe in VokabelStufe:
            for eintrag in self._nach_stufe[stufe]:
                assembly = eintrag.kompiliere(text)
                if assembly is not None:
                    return assembly
        return None

    def gib_eintrag(self, wort: str) -> Optional[VokabelEintrag]:
        """Gib einen Eintrag nach seinem Wort zurück."""
        return self._nach_wort.get(wort.lower())

    def gib_stufe(self, stufe: VokabelStufe) -> List[VokabelEintrag]:
        """Gib alle Einträge einer bestimmten Stufe zurück."""
        return list(self._nach_stufe.get(stufe, []))

    def gib_kasus(self, kasus: Kasus) -> List[VokabelEintrag]:
        """Gib alle Einträge mit einem bestimmten Kasus zurück."""
        return list(self._nach_kasus.get(kasus, []))

    def gib_kategorie(self, kategorie: str) -> List[VokabelEintrag]:
        """Gib alle Einträge einer bestimmten Kategorie zurück."""
        return list(self._nach_kategorie.get(kategorie, []))

    @property
    def anzahl(self) -> int:
        """Gesamtzahl der eingetragenen Vokabeln."""
        return len(self._eintraege)

    def alle_eintraege(self) -> List[VokabelEintrag]:
        """Gib alle eingetragenen Vokabeln zurück."""
        return list(self._eintraege)


# ══════════════════════════════════════════════════════════════════════
# Standardvokabeln — Eingebauter deutscher Grundwortschatz
# ══════════════════════════════════════════════════════════════════════

def _erstelle_standardvokabeln() -> List[VokabelEintrag]:
    """
    Erstelle die eingebauten Standardvokabeln für alle Stufen.

    Stufe 0 — Grundprimitive:
        laden, speichern, springe, addiere, subtrahiere, multipliziere, teile

    Stufe 1 — Zusammengesetzte Befehle:
        berechne, übertrage, vergleiche

    Stufe 2 — Domänenkacheln:
        sortiere, filtere, aggregiere
    """
    eintraege: List[VokabelEintrag] = []

    # ── Stufe 0: Grundprimitive ─────────────────────────────────────

    # laden — Lade einen Wert in ein Register
    eintraege.append(VokabelEintrag(
        wort="laden",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"lade\s+(?:register\s+)?(\S+)\s+mit\s+(.+)", re.IGNORECASE),
        vorlage="MOVI {register}, {wert}",
        platzhalter={"register": 1, "wert": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Lade einen Wert in ein Register",
        beispiele=["lade register null mit 42", "lade R0 mit 100"],
    ))

    # speichern — Speichere einen Wert
    eintraege.append(VokabelEintrag(
        wort="speichern",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"speichere\s+(.+?)\s+in\s+(?:register\s+)?(\S+)", re.IGNORECASE),
        vorlage="STORE R{ziel}, R{quelle}",
        platzhalter={"quelle": 1, "ziel": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Speichere einen Wert (Akkusativ-Zugriff)",
        beispiele=["speichere 42 in R1"],
    ))

    # springe — Unbedingter Sprung
    eintraege.append(VokabelEintrag(
        wort="springe",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"springe\s+(?:nach\s+)?(\S+)", re.IGNORECASE),
        vorlage="JMP {ziel}",
        platzhalter={"ziel": 1},
        beschreibung="Unbedingter Sprung zum Ziel",
        beispiele=["springe anfang", "springe nach Schleife"],
    ))

    # addiere — Ganzzahl-Addition
    eintraege.append(VokabelEintrag(
        wort="addiere",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(
            r"addiere\s+(?:register\s+)?(\S+)\s+(?:und\s+)?(?:register\s+)?(\S+)",
            re.IGNORECASE
        ),
        vorlage="IADD R0, R{a}, R{b}",
        platzhalter={"a": 1, "b": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Addiere zwei Registerwerte",
        beispiele=["addiere R0 und R1"],
    ))

    # subtrahiere — Ganzzahl-Subtraktion
    eintraege.append(VokabelEintrag(
        wort="subtrahiere",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(
            r"subtrahiere\s+(?:register\s+)?(\S+)\s+(?:und\s+)?(?:register\s+)?(\S+)",
            re.IGNORECASE
        ),
        vorlage="ISUB R0, R{a}, R{b}",
        platzhalter={"a": 1, "b": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Subtrahiere zwei Registerwerte",
        beispiele=["subtrahiere R0 und R1"],
    ))

    # multipliziere — Ganzzahl-Multiplikation
    eintraege.append(VokabelEintrag(
        wort="multipliziere",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(
            r"multipliziere\s+(?:register\s+)?(\S+)\s+(?:und\s+)?(?:register\s+)?(\S+)",
            re.IGNORECASE
        ),
        vorlage="IMUL R0, R{a}, R{b}",
        platzhalter={"a": 1, "b": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Multipliziere zwei Registerwerte",
        beispiele=["multipliziere R0 und R1"],
    ))

    # teile — Ganzzahl-Division
    eintraege.append(VokabelEintrag(
        wort="teile",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(
            r"teile\s+(?:register\s+)?(\S+)\s+durch\s+(?:register\s+)?(\S+)",
            re.IGNORECASE
        ),
        vorlage="IDIV R0, R{a}, R{b}",
        platzhalter={"a": 1, "b": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Teile einen Registerwert durch einen anderen",
        beispiele=["teile R0 durch R1"],
    ))

    # vergleiche — Vergleich (niedrigste Stufe)
    eintraege.append(VokabelEintrag(
        wort="vergleiche",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(
            r"vergleiche\s+(?:register\s+)?(\S+)\s+mit\s+(?:register\s+)?(\S+)",
            re.IGNORECASE
        ),
        vorlage="CMP R{a}, R{b}",
        platzhalter={"a": 1, "b": 2},
        kasus=Kasus.NOMINATIV,
        beschreibung="Vergleiche zwei Registerwerte",
        beispiele=["vergleiche R0 mit R1"],
    ))

    # incremented — Erhöhe ein Register
    eintraege.append(VokabelEintrag(
        wort="erhöhe",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"erhöhe\s+(?:register\s+)?(\S+)", re.IGNORECASE),
        vorlage="INC R{register}",
        platzhalter={"register": 1},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Erhöhe ein Register um 1",
        beispiele=["erhöhe R0"],
    ))

    # verringere — Vermindere ein Register
    eintraege.append(VokabelEintrag(
        wort="verringere",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"verringere\s+(?:register\s+)?(\S+)", re.IGNORECASE),
        vorlage="DEC R{register}",
        platzhalter={"register": 1},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Verringere ein Register um 1",
        beispiele=["verringere R0"],
    ))

    # negiere — Negiere ein Register
    eintraege.append(VokabelEintrag(
        wort="negiere",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"negiere\s+(?:register\s+)?(\S+)", re.IGNORECASE),
        vorlage="INEG R{register}",
        platzhalter={"register": 1},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Negiere den Wert eines Registers",
        beispiele=["negiere R0"],
    ))

    # gib aus — Drucke/Registerwert ausgeben
    eintraege.append(VokabelEintrag(
        wort="gib aus",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"gib\s+(?:register\s+)?(\S+)\s+aus", re.IGNORECASE),
        vorlage="PRINT R{register}",
        platzhalter={"register": 1},
        kasus=Kasus.NOMINATIV,
        beschreibung="Gib den Wert eines Registers aus",
        beispiele=["gib R0 aus"],
    ))

    # halte an — Programm anhalten
    eintraege.append(VokabelEintrag(
        wort="halte an",
        stufe=VokabelStufe.PRIMITIV,
        muster=re.compile(r"halte\s+an", re.IGNORECASE),
        vorlage="HALT",
        beschreibung="Halte das Programm an",
        beispiele=["halte an"],
    ))

    # ── Stufe 1: Zusammengesetzte Befehle ───────────────────────────

    # berechne — Allgemeine Berechnung (entspricht einem konkreten Opcode)
    eintraege.append(VokabelEintrag(
        wort="berechne",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"berechne\s+(.+?)\s+plus\s+(.+)", re.IGNORECASE),
        vorlage="MOVI R0, {a}\nMOVI R1, {b}\nIADD R0, R0, R1",
        platzhalter={"a": 1, "b": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Berechne die Summe zweier Werte",
        beispiele=["berechne 3 plus 5"],
        kategorie="arithmetik",
    ))

    eintraege.append(VokabelEintrag(
        wort="berechne minus",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"berechne\s+(.+?)\s+minus\s+(.+)", re.IGNORECASE),
        vorlage="MOVI R0, {a}\nMOVI R1, {b}\nISUB R0, R0, R1",
        platzhalter={"a": 1, "b": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Berechne die Differenz zweier Werte",
        beispiele=["berechne 10 minus 3"],
        kategorie="arithmetik",
    ))

    # übertrage — Wert von einem Register in ein anderes
    eintraege.append(VokabelEintrag(
        wort="übertrage",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(
            r"übertrage\s+(?:register\s+)?(\S+)\s+nach\s+(?:register\s+)?(\S+)",
            re.IGNORECASE
        ),
        vorlage="MOV R{ziel}, R{quelle}",
        platzhalter={"quelle": 1, "ziel": 2},
        kasus=Kasus.GENITIV,
        beschreibung="Übertrage einen Wert (Genitiv = Eigentumswechsel)",
        beispiele=["übertrage R0 nach R1"],
        kategorie="transfer",
    ))

    # vergleiche und springe — Vergleich mit bedingtem Sprung
    eintraege.append(VokabelEintrag(
        wort="vergleiche und springe",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(
            r"wenn\s+(?:register\s+)?(\S+)\s+gleich\s+(?:register\s+)?(\S+)\s+dann\s+springe\s+(\S+)",
            re.IGNORECASE
        ),
        vorlage="CMP R{a}, R{b}\nJE R{a}, {ziel}",
        platzhalter={"a": 1, "b": 2, "ziel": 3},
        kasus=Kasus.NOMINATIV,
        beschreibung="Vergleiche und springe bei Gleichheit",
        beispiele=["wenn R0 gleich R1 dann springe ende"],
        kategorie="steuerung",
    ))

    # fakultät — Berechne Fakultät (zusammengesetzt)
    eintraege.append(VokabelEintrag(
        wort="fakultät",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"fakultät\s+von\s+(\S+)", re.IGNORECASE),
        vorlage=(
            "MOVI R0, {n}\n"
            "MOVI R1, 1\n"
            "MOV R2, R0\n"
            "fak_schleife:\n"
            "JZ R2, fak_ende\n"
            "IMUL R1, R1, R2\n"
            "DEC R2\n"
            "JMP fak_schleife\n"
            "fak_ende:\n"
            "MOV R0, R1"
        ),
        platzhalter={"n": 1},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Berechne die Fakultät einer Zahl",
        beispiele=["fakultät von 5"],
        kategorie="arithmetik",
    ))

    # sage — Agent-zu-Agent Nachricht senden
    eintraege.append(VokabelEintrag(
        wort="sage",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"sage\s+(\S+)\s+(.+)", re.IGNORECASE),
        vorlage="MOVI R{agent}, {agent_id}\nMOVI R{nachricht}, {msg_id}\nTELL R{agent}, R{nachricht}",
        platzhalter={"agent": 1, "nachricht": 2, "agent_id": 1, "msg_id": 2},
        kasus=Kasus.DATIV,
        beschreibung="Sende eine Nachricht an einen Agenten (Dativ = indirekter Empfang)",
        beispiele=["sage navigator berechne kurs"],
        kategorie="a2a",
    ))

    # frage — Agent eine Frage stellen
    eintraege.append(VokabelEintrag(
        wort="frage",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"frage\s+(\S+)\s+nach\s+(.+)", re.IGNORECASE),
        vorlage="MOVI R{agent}, {agent_id}\nMOVI R{thema}, {topic_id}\nASK R{agent}, R{thema}",
        platzhalter={"agent": 1, "thema": 2, "agent_id": 1, "topic_id": 2},
        kasus=Kasus.DATIV,
        beschreibung="Stelle einem Agenten eine Frage (Dativ = indirekter Empfang)",
        beispiele=["frage wetteragent nach windstärke"],
        kategorie="a2a",
    ))

    # ── Stufe 2: Domänenkacheln ─────────────────────────────────────

    # sortiere — Sortiere eine Reihe
    eintraege.append(VokabelEintrag(
        wort="sortiere",
        stufe=VokabelStufe.DOMAENE,
        muster=re.compile(r"sortiere\s+(?:die\s+)?(?:reihe\s+)?(?:von\s+)?(\S+)", re.IGNORECASE),
        vorlage=(
            "MOVI R10, {daten}\n"
            "# Sortieralgorithmus (Bubblesort)\n"
            "sort_außen:\n"
            "DEC R10\n"
            "JZ R10, sort_fertig\n"
            "MOV R11, R10\n"
            "sort_innen:\n"
            "JZ R11, sort_außen\n"
            "DEC R11\n"
            "JMP sort_innen\n"
            "sort_fertig:"
        ),
        platzhalter={"daten": 1},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Sortiere eine Datenreihe (Domänenkachel)",
        beispiele=["sortiere die reihe daten"],
        kategorie="algorithmus",
    ))

    # filtere — Filtere eine Datenreihe
    eintraege.append(VokabelEintrag(
        wort="filtere",
        stufe=VokabelStufe.DOMAENE,
        muster=re.compile(
            r"filtere\s+(?:die\s+)?(?:reihe\s+)?(?:von\s+)?(\S+)\s+nach\s+(.+)",
            re.IGNORECASE
        ),
        vorlage=(
            "MOVI R10, {daten}\n"
            "MOVI R11, {bedingung}\n"
            "# Filteralgorithmus\n"
            "filter_schleife:\n"
            "JZ R10, filter_fertig\n"
            "DEC R10\n"
            "JMP filter_schleife\n"
            "filter_fertig:"
        ),
        platzhalter={"daten": 1, "bedingung": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Filtere eine Datenreihe nach einer Bedingung",
        beispiele=["filtere die reihe werte nach größer 10"],
        kategorie="algorithmus",
    ))

    # aggregiere — Aggregiere eine Datenreihe
    eintraege.append(VokabelEintrag(
        wort="aggregiere",
        stufe=VokabelStufe.DOMAENE,
        muster=re.compile(
            r"aggregiere\s+(?:die\s+)?(?:reihe\s+)?(?:von\s+)?(\S+)\s+als\s+(\S+)",
            re.IGNORECASE
        ),
        vorlage=(
            "MOVI R10, {daten}\n"
            "MOVI R11, 0\n"
            "# Aggregationsalgorithmus\n"
            "agg_schleife:\n"
            "JZ R10, agg_fertig\n"
            "IADD R11, R11, R10\n"
            "DEC R10\n"
            "JMP agg_schleife\n"
            "agg_fertig:\n"
            "MOV R0, R11"
        ),
        platzhalter={"daten": 1, "funktion": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Aggregiere eine Datenreihe (Summe, Durchschnitt, etc.)",
        beispiele=["aggregiere die reihe werte als summe"],
        kategorie="algorithmus",
    ))

    # summe von bis — Summenbereich (zusamengesetzt, wird oft auf Stufe 1 genutzt)
    eintraege.append(VokabelEintrag(
        wort="summe von bis",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"summe\s+von\s+(\S+)\s+bis\s+(\S+)", re.IGNORECASE),
        vorlage=(
            "MOVI R0, {anfang}\n"
            "MOVI R1, {ende}\n"
            "MOV R2, R0\n"
            "summe_schleife:\n"
            "IADD R2, R2, R1\n"
            "DEC R1\n"
            "CMP R0, R1\n"
            "JL summe_schleife\n"
            "MOV R0, R2"
        ),
        platzhalter={"anfang": 1, "ende": 2},
        kasus=Kasus.AKKUSATIV,
        beschreibung="Berechne die Summe eines Zahlenbereichs",
        beispiele=["summe von 1 bis 10"],
        kategorie="arithmetik",
    ))

    # delegiere — Aufgabe an Agenten delegieren
    eintraege.append(VokabelEintrag(
        wort="delegiere",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"delegiere\s+(\S+)\s+an\s+(\S+)", re.IGNORECASE),
        vorlage="MOVI R0, {agent}\nMOVI R1, {aufgabe}\nDELEGATE R0, R1",
        platzhalter={"aufgabe": 1, "agent": 2},
        kasus=Kasus.GENITIV,
        beschreibung="Delegiere eine Aufgabe an einen Agenten (Genitiv = Übertragung)",
        beispiele=["delegiere berechnung an navigator"],
        kategorie="a2a",
    ))

    # vertraue — Vertrauensprüfung
    eintraege.append(VokabelEintrag(
        wort="vertraue",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"vertraue\s+(?:register\s+)?(\S+)\s+mit\s+(?:register\s+)?(\S+)", re.IGNORECASE),
        vorlage="TRUST_CHECK R{agent}, R{ziel}",
        platzhalter={"agent": 1, "ziel": 2},
        kasus=Kasus.GENITIV,
        beschreibung="Führe eine Kasus-basierte Vertrauensprüfung durch",
        beispiele=["vertraue R60 mit R61"],
        kategorie="sicherheit",
    ))

    # fordere capability — Capability-Level anfordern
    eintraege.append(VokabelEintrag(
        wort="fordere",
        stufe=VokabelStufe.ZUSAMMENGESETZT,
        muster=re.compile(r"fordere\s+(?:cap\s+)?(\S+)\s+für\s+(?:register\s+)?(\S+)", re.IGNORECASE),
        vorlage="MOVI R2, {cap}\nCAP_REQUIRE R{register}, R2",
        platzhalter={"cap": 1, "register": 2},
        kasus=Kasus.GENITIV,
        beschreibung="Fordere einen bestimmten Capability-Level für ein Register",
        beispiele=["fordere 3 für R61"],
        kategorie="sicherheit",
    ))

    return eintraege


# ══════════════════════════════════════════════════════════════════════
# Globale Instanz und öffentliche API
# ══════════════════════════════════════════════════════════════════════

# Globales Wortschatzregister (Standardvokabeln vorinstalliert)
_standard_register: Optional[WortschatzRegister] = None


def gib_wortschatz() -> WortschatzRegister:
    """
    Gib das globale Wortschatzregister zurück.

    Erstellt beim ersten Aufruf die Instanz mit Standardvokabeln.
    """
    global _standard_register
    if _standard_register is None:
        _standard_register = WortschatzRegister()
        _standard_register.laden_standardvokabeln()
    return _standard_register


def kompiliere_deutsch(text: str) -> Optional[str]:
    """
    Kompiliere einen deutschen Text zu FLUX-Assembly.

    Durchsucht alle Vokabelstufen nach einem passenden Eintrag.
    """
    register = gib_wortschatz()
    return register.kompiliere_text(text)


def suche_vokabel(text: str) -> List[VokabelEintrag]:
    """Suche nach passenden Vokabeleinträgen für den Text."""
    register = gib_wortschatz()
    return register.suche(text)
