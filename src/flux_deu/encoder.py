"""
FLUX-deu Kodierer — Deutsche und englische Assembly-Mnemoniken → FLUX-Bytecode.

Dieser Kodierer übersetzt Assembly-Text in FLUX-Bytecode. Er unterstützt sowohl
die englischen Standard-Mnemoniken (MOV, ADD, etc.) als auch deutsche Mnemoniken
(BEWEGEN, ADDIEREN, etc.) und deutsche Registernamen (Null, Eins, Zwei, ...).

Eigenschaften:
    - Englische und deutsche Mnemoniken
    - Deutsche Registernamen: Null(0)–Dreiundsechzig(63) oder R0–R63
    - Vorwärtsreferenzen und Marken (Labels)
    - Kommentare (# oder //)
    - Rückgabe: (bytearray, Anweisungsliste, Markentabelle)
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from flux_deu.vm import Op, OP_NAMEN


# ══════════════════════════════════════════════════════════════════════
# Datenstrukturen
# ══════════════════════════════════════════════════════════════════════

@dataclass
class KodierteAnweisung:
    """
    Eine einzelne kodierte Assembly-Anweisung.

    Attribute:
        versatz:     Byte-Offset im ausgebenen Bytecode.
        opcode:      Opcode-Nummer.
        operanden:   Liste der Operandenwerte.
        groesse:     Anzahl der Bytes dieser Anweisung.
        mnemonik:    Verwendetes Mnemonik (englisch oder deutsch).
    """
    versatz: int
    opcode: int
    operanden: List[int] = field(default_factory=list)
    groesse: int = 1
    mnemonik: str = ""

    def __repr__(self) -> str:
        ops = ", ".join(str(o) for o in self.operanden)
        return f"[{self.versatz:04d}] {self.mnemonik:<16s} {ops}"


# ══════════════════════════════════════════════════════════════════════
# Deutsche Mnemonik-Zuordnung
# ══════════════════════════════════════════════════════════════════════

# Englisch → Opcode (direkt aus der Op-Klasse)
_ENGLISCH_ZU_OPCODE: Dict[str, int] = {}
for _name, _code in list(vars(Op).items()):
    if isinstance(_code, int) and not _name.startswith("_") and _name.isupper():
        _ENGLISCH_ZU_OPCODE[_name] = _code

# Deutsch → Opcode (Konzept-zu-Bytecode-Abbildung)
_DEUTSCH_ZU_OPCODE: Dict[str, int] = {
    # Steuerfluss
    "NICHTS": Op.NOP,
    "BEWEGEN": Op.MOV,
    "LADEN": Op.LOAD,
    "SPEICHERN": Op.STORE,
    "SPRINGE": Op.JMP,
    "SPRINGE_NULL": Op.JZ,
    "SPRINGE_NICHT_NULL": Op.JNZ,
    "AUFRUFEN": Op.CALL,

    # Ganzzahlarithmetik
    "ADDIEREN": Op.IADD,
    "SUBTRAHIEREN": Op.ISUB,
    "MULTIPLIZIEREN": Op.IMUL,
    "TEILEN": Op.IDIV,
    "REST": Op.IMOD,
    "NEGIEREN": Op.INEG,
    "ERHÖHEN": Op.INC,
    "VERRINGERN": Op.DEC,

    # Bitoperationen
    "UND": Op.IAND,
    "ODER": Op.IOR,
    "ENTWEDER_ODER": Op.IXOR,
    "NICHT_BIT": Op.INOT,
    "SCHIEBE_LINKS": Op.ISHL,
    "SCHIEBE_RECHTS": Op.ISHR,
    "ROTIERE_LINKS": Op.ROTL,
    "ROTIERE_RECHTS": Op.ROTR,

    # Vergleiche
    "VERGLEICH_I": Op.ICMP,
    "GLEICH": Op.IEQ,
    "KLEINER": Op.ILT,
    "KLEINER_GLEICH": Op.ILE,
    "GRÖßER": Op.IGT,
    "GRÖßER_GLEICH": Op.IGE,
    "PRÜFE": Op.TEST,
    "SETZE_FLAGS": Op.SETCC,

    # Stapeloperationen
    "LEGE_AB": Op.PUSH,
    "NEHME": Op.POP,
    "VERDOPPELE": Op.DUP,
    "TAUSCHE": Op.SWAP,
    "DREHE": Op.ROT,
    "BETRETE": Op.ENTER,
    "VERLASSE": Op.LEAVE,
    "PLATZ_SCHAFFEN": Op.ALLOCA,

    # Funktionsoperationen
    "RÜCKKEHR": Op.RET,
    "AUFRUFEN_IND": Op.CALL_IND,
    "ENDEAUFRUF": Op.TAILCALL,
    "LADE_SOFORT": Op.MOVI,
    "VERGLEICH": Op.CMP,
    "SPRINGE_GLEICH": Op.JE,
    "SPRINGE_UNGLEICH": Op.JNE,

    # Speicherverwaltung
    "BEREICH_ERZEUGEN": Op.REGION_CREATE,
    "BEREICH_ZERSTÖREN": Op.REGION_DESTROY,
    "BEREICH_ÜBERTRAGEN": Op.REGION_TRANSFER,
    "SPEICHER_KOPIEREN": Op.MEMCOPY,
    "SPEICHER_FÜLLEN": Op.MEMSET,
    "SPEICHER_VERGLEICHEN": Op.MEMCMP,
    "SPRINGE_KLEINER": Op.JL,
    "SPRINGE_GRÖßER_GLEICH": Op.JGE,

    # Typoperationen
    "UMWANDELN": Op.CAST,
    "VERPACKEN": Op.BOX,
    "AUSPACKEN": Op.UNBOX,
    "PRÜFE_TYP": Op.CHECK_TYPE,
    "PRÜFE_GRENZEN": Op.CHECK_BOUNDS,

    # Gleitkommaarithmetik
    "F_ADDIEREN": Op.FADD,
    "F_SUBTRAHIEREN": Op.FSUB,
    "F_MULTIPLIZIEREN": Op.FMUL,
    "F_TEILEN": Op.FDIV,
    "F_NEGIEREN": Op.FNEG,
    "F_ABSOLUT": Op.FABS,
    "F_MINIMUM": Op.FMIN,
    "F_MAXIMUM": Op.FMAX,

    # Zeichenkettenoperationen
    "ZEICHENKETTE_LÄNGE": Op.SLEN,
    "ZEICHENKETTE_VERBINDEN": Op.SCONCAT,
    "ZEICHENKETTE_ZEICHEN": Op.SCHAR,
    "ZEICHENKETTE_TEIL": Op.SSUB,
    "ZEICHENKETTE_VERGLEICH": Op.SCMP,

    # Agentenprotokoll
    "SAGE": Op.TELL,
    "FRAGE": Op.ASK,
    "DELEGIERE": Op.DELEGATE,
    "RUNDSENDEN": Op.BROADCAST,
    "VERTRAUEN_PRÜFEN": Op.TRUST_CHECK,
    "FÄHIGKEIT_FORDERN": Op.CAP_REQUIRE,

    # System
    "AUSGEBEN": Op.PRINT,
    "HALT": Op.HALT,
    "ANHALTEN": Op.HALT,
}

# Vereinigte Mnemonik-Tabelle (Deutsch zuerst, dann Englisch)
_MNEMONIK_ZU_OPCODE: Dict[str, int] = {}
_MNEMONIK_ZU_OPCODE.update(_DEUTSCH_ZU_OPCODE)
_MNEMONIK_ZU_OPCODE.update(_ENGLISCH_ZU_OPCODE)


# ══════════════════════════════════════════════════════════════════════
# Deutsche Registernamen
# ══════════════════════════════════════════════════════════════════════

_DEUTSCHE_REGISTER: Dict[str, int] = {
    "null": 0, "eins": 1, "zwei": 2, "drei": 3,
    "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7,
    "acht": 8, "neun": 9, "zehn": 10, "elf": 11,
    "zwölf": 12, "dreizehn": 13, "vierzehn": 14,
    "fünfzehn": 15, "sechzehn": 16, "siebzehn": 17,
    "achtzehn": 18, "neunzehn": 19, "zwanzig": 20,
    # Kurzform für höhere Register
    "einundzwanzig": 21, "zweiundzwanzig": 22,
    "dreiundzwanzig": 23, "vierundzwanzig": 24,
    "fünfundzwanzig": 25, "sechsundzwanzig": 26,
    "siebenundzwanzig": 27, "achtundzwanzig": 28,
    "neunundzwanzig": 29, "dreißig": 30,
    # Themenregister (spezielle Namen)
    "thema": 60,
    "objekt": 61,
    "referenz": 62,
    "besitz": 63,
}

# Opcode-Namen-Rückwärtstabelle (für die Mnemonik-Spalte)
_OPCODE_ZU_NAME: Dict[int, str] = {}
for name, code in _MNEMONIK_ZU_OPCODE.items():
    if code not in _OPCODE_ZU_NAME:
        _OPCODE_ZU_NAME[code] = name


# ══════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════

def _registernummer_lesen(s: str) -> int:
    """
    Lese eine Registernummer aus einem String.

    Akzeptiert:
        - R0, R1, ..., R63 (Groß-/Kleinschreibung egal)
        - Null, Eins, Zwei, ..., Dreißig (deutsche Namen)
        - Thema, Objekt, Referenz, Besitz (spezielle Register)
        - Numerische Werte 0–63
    """
    s = s.strip()

    # R-Präfix
    m = re.match(r"^R(\d+)$", s, re.IGNORECASE)
    if m:
        nummer = int(m.group(1))
        if 0 <= nummer < 64:
            return nummer
        raise ValueError(f"Register außerhalb des Bereichs: R{nummer} (gültig: R0–R63)")

    # Deutscher Name (case-insensitive)
    if s.lower() in _DEUTSCHE_REGISTER:
        return _DEUTSCHE_REGISTER[s.lower()]

    # Numerisch
    try:
        nummer = int(s)
        if 0 <= nummer < 64:
            return nummer
        raise ValueError(f"Register außerhalb des Bereichs: {nummer} (gültig: 0–63)")
    except ValueError:
        pass

    raise ValueError(
        f"Ungültiger Registername: '{s}'. "
        f"Verwende R0–R63 oder deutsche Namen (Null, Eins, ..., Thema, Besitz)."
    )


def _unmittelbaren_wert_lesen(s: str) -> int:
    """Lese einen unmittelbaren Wert (Immediate) aus einem String."""
    s = s.strip()

    # Dezimal
    try:
        return int(s)
    except ValueError:
        pass

    # Hexadezimal
    if s.startswith("0x") or s.startswith("0X"):
        try:
            return int(s, 16)
        except ValueError:
            pass

    # Binär
    if s.startswith("0b") or s.startswith("0B"):
        try:
            return int(s, 2)
        except ValueError:
            pass

    # Deutsches Zahlwort (einfache Fälle)
    einfache_zahlen = {
        "null": 0, "eins": 1, "zwei": 2, "drei": 3, "vier": 4,
        "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
        "zehn": 10, "elf": 11, "zwölf": 12, "zwanzig": 20,
        "hundert": 100, "tausend": 1000,
    }
    if s.lower() in einfache_zahlen:
        return einfache_zahlen[s.lower()]

    raise ValueError(f"Ungültiger unmittelbarer Wert: '{s}'")


def _kodiere_u16(wert: int) -> bytes:
    """Kodiere eine 16-Bit-Ganzzahl als Little-Endian Bytes."""
    wert = wert & 0xFFFF
    return bytes([wert & 0xFF, (wert >> 8) & 0xFF])


def _schätze_anweisungsgröße(mnemonik: str, argumente: List[str]) -> int:
    """
    Schätze die Anzahl der Bytes einer Anweisung (für Marken-Berechnung).

    Dies muss mit der tatsächlichen Kodierung übereinstimmen.
    """
    opcode = _MNEMONIK_ZU_OPCODE.get(mnemonik.upper(), 0)

    # Null-Operanden-Befehle
    if opcode in (Op.NOP, Op.HALT, Op.RET, Op.LEAVE):
        return 1

    # Ein-Register-Befehle
    if opcode in (Op.INC, Op.DEC, Op.INEG, Op.INOT, Op.PRINT, Op.DUP, Op.SWAP,
                  Op.ENTER, Op.ALLOCA, Op.PUSH, Op.POP,
                  Op.REGION_CREATE, Op.REGION_DESTROY):
        return 2

    # Zwei-Register-Befehle
    if opcode in (Op.MOV, Op.LOAD, Op.STORE, Op.CMP, Op.ICMP,
                  Op.FEQ, Op.FLT, Op.FLE, Op.FGT, Op.FGE,
                  Op.SLEN, Op.SCHAR, Op.SSUB, Op.SCMP,
                  Op.CAST, Op.BOX, Op.UNBOX, Op.CHECK_TYPE, Op.CHECK_BOUNDS,
                  Op.FNEG, Op.FABS, Op.FMIN, Op.FMAX,
                  Op.TELL, Op.ASK, Op.DELEGATE, Op.BROADCAST,
                  Op.TRUST_CHECK, Op.CAP_REQUIRE,
                  Op.REGION_TRANSFER, Op.TEST, Op.SETCC):
        return 3

    # Drei-Register-Befehle
    if opcode in (Op.IADD, Op.ISUB, Op.IMUL, Op.IDIV, Op.IMOD,
                  Op.IAND, Op.IOR, Op.IXOR, Op.ISHL, Op.ISHR,
                  Op.ROTL, Op.ROTR, Op.FADD, Op.FSUB, Op.FMUL, Op.FDIV,
                  Op.SCONCAT, Op.MEMCOPY, Op.MEMSET, Op.MEMCMP):
        return 4

    # Unmittelbare Werte (MOVI)
    if opcode == Op.MOVI:
        return 4

    # Bedingte Sprünge
    if opcode in (Op.JZ, Op.JNZ, Op.JE, Op.JNE, Op.JL, Op.JGE):
        return 4

    # Unbedingter Sprung
    if opcode == Op.JMP:
        return 3

    # Aufruf
    if opcode == Op.CALL:
        return 3

    return 1  # Standard: 1 Byte


# ══════════════════════════════════════════════════════════════════════
# Anweisungs-Kodierung
# ══════════════════════════════════════════════════════════════════════

def _kodiere_anweisung(
    mnemonik: str,
    argumente: List[str],
    marken: Dict[str, int],
) -> Dict[str, Any]:
    """
    Kodiere eine einzelne Assembly-Anweisung.

    Returns:
        Dictionary mit 'bytes', 'operanden'.
    """
    mnemonik_upper = mnemonik.upper()
    opcode = _MNEMONIK_ZU_OPCODE.get(mnemonik_upper, Op.NOP)

    # ── Null-Operanden ──────────────────────────────────────────────
    if opcode in (Op.NOP, Op.HALT, Op.RET, Op.LEAVE):
        return {"bytes": bytes([opcode]), "operanden": []}

    # ── Ein-Register ────────────────────────────────────────────────
    if opcode in (Op.INC, Op.DEC, Op.INEG, Op.INOT, Op.PRINT):
        r = _registernummer_lesen(argumente[0]) if argumente else 0
        return {"bytes": bytes([opcode, r]), "operanden": [r]}

    if opcode in (Op.PUSH, Op.POP):
        r = _registernummer_lesen(argumente[0]) if argumente else 0
        return {"bytes": bytes([opcode, r]), "operanden": [r]}

    if opcode in (Op.DUP, Op.SWAP, Op.ENTER, Op.ALLOCA):
        return {"bytes": bytes([opcode, 0]), "operanden": [0]}

    if opcode in (Op.REGION_CREATE, Op.REGION_DESTROY):
        r = _registernummer_lesen(argumente[0]) if argumente else 0
        return {"bytes": bytes([opcode, r]), "operanden": [r]}

    # ── Zwei-Register ──────────────────────────────────────────────
    if opcode in (Op.MOV, Op.LOAD, Op.STORE):
        rd = _registernummer_lesen(argumente[0])
        rs = _registernummer_lesen(argumente[1])
        return {"bytes": bytes([opcode, rd, rs]), "operanden": [rd, rs]}

    # ── Drei-Register ───────────────────────────────────────────────
    drei_reg_ops = {
        Op.IADD, Op.ISUB, Op.IMUL, Op.IDIV, Op.IMOD,
        Op.IAND, Op.IOR, Op.IXOR, Op.ISHL, Op.ISHR,
        Op.ROTL, Op.ROTR, Op.FADD, Op.FSUB, Op.FMUL, Op.FDIV,
        Op.SCONCAT, Op.MEMCOPY, Op.MEMSET, Op.MEMCMP,
    }
    if opcode in drei_reg_ops:
        rd = _registernummer_lesen(argumente[0])
        ra = _registernummer_lesen(argumente[1])
        rb = _registernummer_lesen(argumente[2]) if len(argumente) > 2 else 0
        return {"bytes": bytes([opcode, rd, ra, rb]), "operanden": [rd, ra, rb]}

    # ── Unmittelbarer Wert (MOVI) ───────────────────────────────────
    if opcode == Op.MOVI:
        r = _registernummer_lesen(argumente[0])
        imm = _unmittelbaren_wert_lesen(argumente[1])
        return {"bytes": bytes([opcode, r]) + _kodiere_u16(imm), "operanden": [r, imm]}

    # ── Vergleiche ──────────────────────────────────────────────────
    vergleich_ops = {
        Op.CMP, Op.ICMP, Op.FEQ, Op.FLT, Op.FLE, Op.FGT, Op.FGE,
        Op.SLEN, Op.SCHAR, Op.SSUB, Op.SCMP,
        Op.CAST, Op.BOX, Op.UNBOX, Op.CHECK_TYPE, Op.CHECK_BOUNDS,
        Op.FNEG, Op.FABS, Op.FMIN, Op.FMAX,
        Op.TELL, Op.ASK, Op.DELEGATE, Op.BROADCAST,
        Op.TRUST_CHECK, Op.CAP_REQUIRE,
        Op.REGION_TRANSFER, Op.TEST, Op.SETCC,
    }
    if opcode in vergleich_ops:
        a = _registernummer_lesen(argumente[0])
        b = _registernummer_lesen(argumente[1]) if len(argumente) > 1 else 0
        return {"bytes": bytes([opcode, a, b]), "operanden": [a, b]}

    # ── Bedingte Sprünge ────────────────────────────────────────────
    bedingte_spruenge = {Op.JZ, Op.JNZ, Op.JE, Op.JNE, Op.JL, Op.JGE}
    if opcode in bedingte_spruenge:
        r = _registernummer_lesen(argumente[0])
        ziel = argumente[1] if len(argumente) > 1 else "0"
        if ziel in marken:
            addr = marken[ziel]
        else:
            addr = _unmittelbaren_wert_lesen(ziel)
        return {"bytes": bytes([opcode, r]) + _kodiere_u16(addr), "operanden": [r, addr]}

    # ── Unbedingter Sprung ─────────────────────────────────────────
    if opcode == Op.JMP:
        ziel = argumente[0] if argumente else "0"
        if ziel in marken:
            addr = marken[ziel]
        else:
            addr = _unmittelbaren_wert_lesen(ziel)
        return {"bytes": bytes([opcode]) + _kodiere_u16(addr), "operanden": [addr]}

    # ── Aufruf ─────────────────────────────────────────────────────
    if opcode == Op.CALL:
        ziel = argumente[0] if argumente else "0"
        if ziel in marken:
            addr = marken[ziel]
        else:
            addr = _unmittelbaren_wert_lesen(ziel)
        return {"bytes": bytes([opcode]) + _kodiere_u16(addr), "operanden": [addr]}

    # ── Unbekannter Opcode ──────────────────────────────────────────
    return {"bytes": bytes([Op.NOP]), "operanden": []}


# ══════════════════════════════════════════════════════════════════════
# Hauptkodierungsfunktion
# ══════════════════════════════════════════════════════════════════════

def kodiere_assembly(
    assembly: str,
) -> Tuple[bytearray, List[KodierteAnweisung], Dict[str, int]]:
    """
    Kodiere Assembly-Text in FLUX-Bytecode.

    Unterstützt:
        - Englische Mnemoniken: MOV, ADD, IADD, MOVI, JMP, HALT, ...
        - Deutsche Mnemoniken: BEWEGEN, ADDIEREN, LADE_SOFORT, SPRINGE, ANHALTEN, ...
        - Register: R0–R63 oder deutsche Namen (Null, Eins, ..., Thema, Besitz)
        - Marken: name: (Marke wird zu Byte-Offset aufgelöst)
        - Vorwärtsreferenzen: Sprünge zu noch nicht definierten Marken
        - Kommentare: # oder //

    Args:
        assembly: Assembly-Text (mehrzeilig erlaubt).

    Returns:
        (bytearray, Anweisungsliste, Markentabelle)

    Example:
        >>> code, instrs, marks = kodiere_assembly(
        ...     "LADE_SOFORT Null, 42\\n"
        ...     "LADE_SOFORT Eins, 8\\n"
        ...     "ADDIEREN Null, Null, Eins\\n"
        ...     "ANHALTEN"
        ... )
        >>> code[0]  # MOVI
        43
        >>> code[1]  # Register 0
        0
    """
    zeilen = assembly.split("\n")
    marken: Dict[str, int] = {}
    roh_zeilen: List[Tuple[str, int]] = []
    anweisungen: List[KodierteAnweisung] = []

    # ── Erster Durchlauf: Marken sammeln und Byte-Offsets berechnen ─
    byte_versatz = 0

    for i, zeile in enumerate(zeilen):
        bereinigt = zeile.strip()

        # Leere Zeilen und Kommentare überspringen
        if not bereinigt or bereinigt.startswith("#") or bereinigt.startswith("//"):
            continue

        # Marke erkennen (endet mit ':')
        if bereinigt.endswith(":"):
            markenname = bereinigt[:-1].strip()
            marken[markenname] = byte_versatz
            continue

        roh_zeilen.append((bereinigt, i))

        # Mnemonik und Argumente trennen
        teile = re.split(r"[\s,]+", bereinigt)
        teile = [t for t in teile if t]
        mnemonik = teile[0].upper()
        args = [a.strip() for a in ",".join(teile[1:]).split(",") if a.strip()]

        byte_versatz += _schätze_anweisungsgröße(mnemonik, args)

    # ── Zweiter Durchlauf: Kodieren ─────────────────────────────────
    puffer = bytearray()

    for zeile_text, _zeilennummer in roh_zeilen:
        versatz = len(puffer)

        teile = re.split(r"[\s,]+", zeile_text.strip())
        teile = [t for t in teile if t]
        mnemonik = teile[0].upper()
        args = [a.strip() for a in ",".join(teile[1:]).split(",") if a.strip()]

        kodiert = _kodiere_anweisung(mnemonik, args, marken)
        puffer.extend(kodiert["bytes"])

        # Mnemonik-Name für die Anweisung bestimmen
        mnemonik_anzeige = _OPCODE_ZU_NAME.get(
            kodiert["bytes"][0] if kodiert["bytes"] else 0,
            mnemonik,
        )

        anweisungen.append(KodierteAnweisung(
            versatz=versatz,
            opcode=kodiert["bytes"][0] if kodiert["bytes"] else 0,
            operanden=kodiert["operanden"],
            groesse=len(kodiert["bytes"]),
            mnemonik=mnemonik_anzeige,
        ))

    return puffer, anweisungen, marken


# ══════════════════════════════════════════════════════════════════════
# Abkürzende Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════

def schnell_kodieren(assembly: str) -> bytearray:
    """
    Schnellkodierung: Assembly-String → bytearray.

    Gibt nur den Bytecode zurück (keine Anweisungsliste oder Marken).
    """
    puffer, _, _ = kodiere_assembly(assembly)
    return puffer


def deutsche_asm_zu_bytecode(deutsch_asm: str) -> bytearray:
    """
    Deutsche Assembly → FLUX-Bytecode.

    Speziell für rein deutsche Mnemoniken optimiert.
    """
    return schnell_kodieren(deutsch_asm)


def kombiniertes_format(anweisungen: List[KodierteAnweisung]) -> str:
    """
    Formatiere eine Liste kodiesrter Anweisungen als lesbaren Text.

    Gibt eine Tabelle mit Offset, Mnemonik und Operanden zurück.
    """
    zeilen = []
    for a in anweisungen:
        ops = ", ".join(str(o) for o in a.operanden)
        zeilen.append(f"  {a.versatz:04d}:  {a.mnemonik:<16s} {ops}")
    return "\n".join(zeilen)


def asm_mnemonik_prüfen(mnemonik: str) -> bool:
    """Prüfe ob ein Mnemonik (deutsch oder englisch) bekannt ist."""
    return mnemonik.upper() in _MNEMONIK_ZU_OPCODE


def registernamen_prüfen(name: str) -> bool:
    """Prüfe ob ein Registername (deutsch oder R-Notation) gültig ist."""
    try:
        _registernummer_lesen(name)
        return True
    except ValueError:
        return False
