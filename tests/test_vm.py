"""
FLUX-deu VM-Testreihe — Umfassende Tests für die 64-Register-Maschine.

Testabdeckung:
  1–10:   Arithmetische Operationen (IADD, ISUB, IMUL, IDIV, IMOD, INEG, INC, DEC)
  11–15:  Bitoperationen (IAND, IOR, IXOR, INOT, ISHL, ISHR)
  16–20:  Vergleichsoperationen (CMP, ICMP, JE, JNE, JL, JGE)
  21–25:  Stapeloperationen (PUSH, POP, DUP, SWAP)
  26–30:  Steuerfluss (JMP, JZ, JNZ, CALL, RET, HALT)
  31–35:  MOVI und Registerbewegungen (MOVI, MOV, LOAD, STORE)
  36–40:  Kasus-Zugriffskontrolle (Nominativ, Akkusativ, Dativ, Genitiv)
  41–45:  Agentenprotokoll (TELL, ASK, DELEGATE, BROADCAST, TRUST_CHECK)
  46–50:  Kodierer-Tests (Englische und deutsche Mnemoniken)
  51–55:  Vokabelsystem (Primitiv, Zusammengesetzt, Domäne)
  56–60:  Fehlerbehandlung und Grenzfälle
"""

import pytest

from flux_deu.vm import (
    Op, OP_NAMEN, ANZAHL_REGISTER, THEMEN_REGISTER, OBJEKT_REGISTER,
    DATIV_REGISTER, GENITIV_REGISTER,
    FluxVmDeu, AusfuehrungsErgebnis,
    KasusFehler, VmFehler, DivisionDurchNull, StapelLeer,
    schnellausfuehrung, kasus_geschuetzte_ausfuehrung,
)
from flux_deu.encoder import (
    kodiere_assembly, schnell_kodieren, deutsche_asm_zu_bytecode,
    KodierteAnweisung, asm_mnemonik_prüfen, registernamen_prüfen,
    kombiniertes_format,
)
from flux_deu.kasus import Kasus, CapLevel, KASUS_TO_CAP
from flux_deu.vocabulary import (
    WortschatzRegister, VokabelEintrag, VokabelStufe, VokabelDateiParser,
    gib_wortschatz, kompiliere_deutsch, suche_vokabel,
)


# ══════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════

def _exec(assembly: str, kasus: bool = False, spur: bool = False) -> AusfuehrungsErgebnis:
    """Hilfsfunktion: Assembly kompilieren und ausführen."""
    bytecode = schnell_kodieren(assembly)
    return schnellausfuehrung(bytecode, kasus_pruefung=kasus, ablaufverfolgung=spur)


# ══════════════════════════════════════════════════════════════════════
# ARITHMETISCHE OPERATIONEN
# ══════════════════════════════════════════════════════════════════════

class TestArithmetikGrundrechenarten:
    """Tests 1–5: Arithmetische Grundrechenarten."""

    def test_addition_zwei_werte(self):
        """Test 1: IADD — 3 + 5 = 8."""
        ergebnis = _exec("MOVI R0, 3\nMOVI R1, 5\nIADD R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 8

    def test_subtraktion_zwei_werte(self):
        """Test 2: ISUB — 10 − 4 = 6."""
        ergebnis = _exec("MOVI R0, 10\nMOVI R1, 4\nISUB R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 6

    def test_multiplikation_zwei_werte(self):
        """Test 3: IMUL — 7 × 6 = 42."""
        ergebnis = _exec("MOVI R0, 7\nMOVI R1, 6\nIMUL R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 42

    def test_division_zwei_werte(self):
        """Test 4: IDIV — 20 / 4 = 5."""
        ergebnis = _exec("MOVI R0, 20\nMOVI R1, 4\nIDIV R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 5

    def test_modulo_zwei_werte(self):
        """Test 5: IMOD — 17 % 5 = 2."""
        ergebnis = _exec("MOVI R0, 17\nMOVI R1, 5\nIMOD R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 2


class TestArithmetikErweitert:
    """Tests 6–10: Erweiterte arithmetische Operationen."""

    def test_negation(self):
        """Test 6: INEG — Negiere 42 → -42."""
        ergebnis = _exec("MOVI R0, 42\nINEG R0\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == -42

    def test_inkrement(self):
        """Test 7: INC — 99 + 1 = 100."""
        ergebnis = _exec("MOVI R0, 99\nINC R0\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 100

    def test_dekrement(self):
        """Test 8: DEC — 100 − 1 = 99."""
        ergebnis = _exec("MOVI R0, 100\nDEC R0\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 99

    def test_null_wert_erhalten(self):
        """Test 9: Arithmetik mit Null — 0 + 0 = 0."""
        ergebnis = _exec("MOVI R0, 0\nMOVI R1, 0\nIADD R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 0

    def test_negative_werte(self):
        """Test 10: Subtraktion ergibt negatives Ergebnis."""
        ergebnis = _exec("MOVI R0, 3\nMOVI R1, 10\nISUB R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == -7


# ══════════════════════════════════════════════════════════════════════
# BITOPERATIONEN
# ══════════════════════════════════════════════════════════════════════

class TestBitoperationen:
    """Tests 11–15: Bitweise Operationen."""

    def test_bitweises_und(self):
        """Test 11: IAND — 0b1100 & 0b1010 = 0b1000 = 8."""
        ergebnis = _exec("MOVI R0, 12\nMOVI R1, 10\nIAND R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 8

    def test_bitweises_oder(self):
        """Test 12: IOR — 0b1100 | 0b1010 = 0b1110 = 14."""
        ergebnis = _exec("MOVI R0, 12\nMOVI R1, 10\nIOR R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 14

    def test_bitweises_xor(self):
        """Test 13: IXOR — 0b1100 ^ 0b1010 = 0b0110 = 6."""
        ergebnis = _exec("MOVI R0, 12\nMOVI R1, 10\nIXOR R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 6

    def test_bitweises_nicht(self):
        """Test 14: INOT — ~0 = 0xFFFFFFFF (als vorzeichenbehaftet: -1)."""
        ergebnis = _exec("MOVI R0, 0\nINOT R0\nHALT")
        assert ergebnis.erfolg is True
        # ~0 & 0xFFFFFFFF = 0xFFFFFFFF, als signed = -1
        assert ergebnis.ergebnis == -1

    def test_schiebe_links(self):
        """Test 15: ISHL — 1 << 4 = 16."""
        ergebnis = _exec("MOVI R0, 1\nMOVI R1, 4\nISHL R0, R0, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 16


# ══════════════════════════════════════════════════════════════════════
# VERGLEICHSOPERATIONEN
# ══════════════════════════════════════════════════════════════════════

class TestVergleiche:
    """Tests 16–20: Vergleichs- und bedingte Sprungoperationen."""

    def test_cmp_gleichheit(self):
        """Test 16: CMP gleiche Werte setzen Null-Flag."""
        ergebnis = _exec(
            "MOVI R0, 5\nMOVI R1, 5\nCMP R0, R1\nHALT"
        )
        assert ergebnis.erfolg is True

    def test_je_sprung(self):
        """Test 17: JE — Springe wenn Null-Flag gesetzt (gleiche Werte)."""
        asm = (
            "MOVI R0, 7\nMOVI R1, 7\nCMP R0, R1\n"
            "JE R0, ziel\nMOVI R2, 0\nHALT\n"
            "ziel:\nMOVI R2, 99\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[2] == 99

    def test_jne_kein_sprung_bei_gleichheit(self):
        """Test 18: JNE — Kein Sprung bei gleicher Werte."""
        asm = (
            "MOVI R0, 10\nMOVI R1, 10\nCMP R0, R1\n"
            "JNE R0, ziel\nMOVI R2, 1\nHALT\n"
            "ziel:\nMOVI R2, 0\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[2] == 1

    def test_jl_sprung_bei_kleiner(self):
        """Test 19: JL — Springe wenn Negativ-Flag gesetzt (kleiner)."""
        asm = (
            "MOVI R0, 3\nMOVI R1, 7\nCMP R0, R1\n"
            "JL R0, ziel\nMOVI R2, 0\nHALT\n"
            "ziel:\nMOVI R2, 42\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[2] == 42

    def test_jge_kein_sprung_bei_kleiner(self):
        """Test 20: JGE — Kein Sprung wenn Negativ-Flag gesetzt."""
        asm = (
            "MOVI R0, 3\nMOVI R1, 7\nCMP R0, R1\n"
            "JGE R0, ziel\nMOVI R2, 42\nHALT\n"
            "ziel:\nMOVI R2, 0\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[2] == 42


# ══════════════════════════════════════════════════════════════════════
# STAPELOPERATIONEN
# ══════════════════════════════════════════════════════════════════════

class TestStapel:
    """Tests 21–25: Stapeloperationen."""

    def test_push_pop(self):
        """Test 21: PUSH und POP — Wert auf Stapel legen und zurückholen."""
        asm = "MOVI R0, 42\nPUSH R0\nMOVI R0, 0\nPOP R0\nHALT"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 42

    def test_push_pop_mehrmals(self):
        """Test 22: Mehrfache PUSH/POP-Operationen."""
        asm = (
            "MOVI R0, 10\nPUSH R0\n"
            "MOVI R0, 20\nPUSH R0\n"
            "MOVI R0, 30\nPUSH R0\n"
            "POP R1\nPOP R2\nPOP R3\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[1] == 30  # Zuletzt gelegt = zuerst genommen
        assert ergebnis.register[2] == 20
        assert ergebnis.register[3] == 10

    def test_dup(self):
        """Test 23: DUP — Obersten Stapelwert verdoppeln."""
        asm = "MOVI R0, 7\nPUSH R0\nDUP\nPOP R1\nPOP R2\nHALT"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[1] == 7
        assert ergebnis.register[2] == 7

    def test_swap(self):
        """Test 24: SWAP — Oberste zwei Stapelwerte vertauschen."""
        asm = (
            "MOVI R0, 10\nPUSH R0\n"
            "MOVI R0, 20\nPUSH R0\n"
            "SWAP\nPOP R1\nPOP R2\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[1] == 10  # Ursprünglich unten
        assert ergebnis.register[2] == 20  # Ursprünglich oben


# ══════════════════════════════════════════════════════════════════════
# STEUERFLUSS
# ══════════════════════════════════════════════════════════════════════

class TestSteuerfluss:
    """Tests 25–30: Sprünge, Schleifen und Unterprogramme."""

    def test_unbedingter_sprung(self):
        """Test 25: JMP — Unbedingter Sprung überspringt Code."""
        asm = (
            "JMP ziel\nMOVI R0, 0\nHALT\n"
            "ziel:\nMOVI R0, 42\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 42

    def test_jz_sprung_bei_null(self):
        """Test 26: JZ — Springe wenn Register 0 ist."""
        asm = (
            "MOVI R0, 0\nJZ R0, ziel\nMOVI R0, 99\nHALT\n"
            "ziel:\nMOVI R0, 1\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 1

    def test_jz_kein_sprung_bei_nicht_null(self):
        """Test 27: JZ — Kein Sprung wenn Register nicht 0 ist."""
        asm = (
            "MOVI R0, 5\nJZ R0, ziel\nMOVI R0, 1\nHALT\n"
            "ziel:\nMOVI R0, 0\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 1

    def test_jnz_sprung_bei_nicht_null(self):
        """Test 28: JNZ — Springe wenn Register nicht 0 ist."""
        asm = (
            "MOVI R0, 7\nJNZ R0, ziel\nMOVI R0, 0\nHALT\n"
            "ziel:\nMOVI R0, 1\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 1

    def test_schleife_mit_dec(self):
        """Test 29: Einfache Zählschleife — 1 + 2 + 3 + 4 + 5 = 15."""
        asm = (
            "MOVI R0, 0\nMOVI R1, 5\n"
            "schleife:\n"
            "IADD R0, R0, R1\n"
            "DEC R1\n"
            "JNZ R1, schleife\n"
            "HALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 15

    def test_call_und_ret(self):
        """Test 30: CALL/RET — Unterprogrammaufruf und Rueckkehr."""
        asm = (
            "MOVI R0, 10\n"
            "CALL unterprogramm\n"
            "HALT\n"
            "unterprogramm:\n"
            "MOV R1, R0\n"
            "INC R1\n"
            "RET"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[1] == 11


# ══════════════════════════════════════════════════════════════════════
# MOVI UND REGISTERBEWEGUNGEN
# ══════════════════════════════════════════════════════════════════════

class TestRegisteroperationen:
    """Tests 31–35: MOVI, MOV, LOAD, STORE."""

    def test_movi_mit_wert(self):
        """Test 31: MOVI — Lade unmittelbaren Wert in Register."""
        ergebnis = _exec("MOVI R0, 123\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 123

    def test_mov_kopie(self):
        """Test 32: MOV — Kopiere Registerinhalt."""
        ergebnis = _exec("MOVI R0, 42\nMOV R1, R0\nMOV R0, 0\nMOV R2, R1\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.register[2] == 42

    def test_nop_keine_aenderung(self):
        """Test 33: NOP — Keine Änderung an Registern."""
        ergebnis = _exec("MOVI R0, 7\nNOP\nNOP\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 7

    def test_mehrmere_register_unabhängig(self):
        """Test 34: Mehrere Register arbeiten unabhängig."""
        asm = (
            "MOVI R0, 1\nMOVI R1, 2\nMOVI R2, 3\nMOVI R3, 4\n"
            "IADD R4, R0, R1\nISUB R5, R2, R3\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.register[4] == 3
        assert ergebnis.register[5] == 4294967295  # -1 als unsigned 32-bit

    def test_zyklenzaehler(self):
        """Test 35: Zyklenzähler wird korrekt inkrementiert."""
        ergebnis = _exec("MOVI R0, 1\nINC R0\nINC R0\nHALT")
        assert ergebnis.erfolg is True
        assert ergebnis.zyklen == 4  # MOVI + INC + INC + HALT


# ══════════════════════════════════════════════════════════════════════
# KASUS-ZUGRIFFSKONTROLLE
# ══════════════════════════════════════════════════════════════════════

class TestKasusZugriff:
    """Tests 36–40: Kasus-basierte Zugriffskontrolle."""

    def test_nominativ_lesen_erlaubt(self):
        """Test 36: Nominativ erlaubt öffentliches Lesen."""
        # MOV (kopieren) liest R0 — braucht nur CAP_PUBLIC, schreibt in R1
        bytecode = schnell_kodieren("MOVI R1, 0\nMOV R1, R0\nHALT")
        vm = FluxVmDeu(bytecode, kasus_pruefung=True)
        vm.setze_register_kasus(0, Kasus.NOMINATIV)
        vm.setze_register_kasus(1, Kasus.AKKUSATIV)
        ergebnis = vm.ausfuehren()
        assert ergebnis.erfolg is True

    def test_akkusativ_schreiben_erlaubt(self):
        """Test 37: Akkusativ erlaubt Lese- und Schreibzugriff."""
        bytecode = schnell_kodieren("MOVI R0, 99\nHALT")
        vm = FluxVmDeu(bytecode, kasus_pruefung=True)
        vm.setze_register_kasus(0, Kasus.AKKUSATIV)
        ergebnis = vm.ausfuehren()
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 99

    def test_nominativ_schreiben_verboten(self):
        """Test 38: Nominativ verbietet Schreibzugriff."""
        bytecode = schnell_kodieren("MOVI R0, 42\nHALT")
        vm = FluxVmDeu(bytecode, kasus_pruefung=True)
        vm.setze_register_kasus(0, Kasus.NOMINATIV)
        ergebnis = vm.ausfuehren()
        assert ergebnis.erfolg is False
        assert "Kasus-Verletzung" in (ergebnis.fehler or "")
        assert "Nominativ" in (ergebnis.fehler or "")

    def test_dativ_lesen_aber_kein_schreiben(self):
        """Test 39: Dativ erlaubt Lesen, aber verbietet Schreiben."""
        # MOV liest R0 (Dativ=CAP_REFERENCE ≥ CAP_PUBLIC → OK)
        # aber schreibt in R1 (braucht CAP_READWRITE > CAP_REFERENCE → Fehler)
        bytecode = schnell_kodieren("MOV R1, R0\nHALT")
        vm = FluxVmDeu(bytecode, kasus_pruefung=True)
        vm.setze_register_kasus(0, Kasus.DATIV)
        vm.setze_register_kasus(1, Kasus.DATIV)
        ergebnis = vm.ausfuehren()
        # Dativ hat CAP_REFERENCE(1), Schreiben braucht CAP_READWRITE(2) → Verletzung
        assert ergebnis.erfolg is False
        assert "Kasus-Verletzung" in (ergebnis.fehler or "")

    def test_genitiv_vollzugriff(self):
        """Test 40: Genitiv erlaubt alle Zugriffsebenen."""
        bytecode = schnell_kodieren("MOVI R0, 100\nMOVI R1, 200\nIADD R0, R0, R1\nHALT")
        vm = FluxVmDeu(bytecode, kasus_pruefung=True)
        vm.setze_register_kasus(0, Kasus.GENITIV)
        vm.setze_register_kasus(1, Kasus.GENITIV)
        ergebnis = vm.ausfuehren()
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 300

    def test_kasus_pruefung_deaktivierbar(self):
        """Test 40b: Kasus-Prüfung kann deaktiviert werden."""
        bytecode = schnell_kodieren("MOVI R0, 42\nHALT")
        vm = FluxVmDeu(bytecode, kasus_pruefung=False)
        vm.setze_register_kasus(0, Kasus.NOMINATIV)
        ergebnis = vm.ausfuehren()
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 42


def schnell_kodiere_nur_lese() -> bytes:
    """Erstelle Bytecode der nur Lesezugriffe ausführt (LOAD)."""
    return schnell_kodieren("MOVI R0, 0\nMOVI R1, 10\nLOAD R0, R1\nHALT")


# ══════════════════════════════════════════════════════════════════════
# AGENTENPROTOKOLL (A2A)
# ══════════════════════════════════════════════════════════════════════

class TestAgentenprotokoll:
    """Tests 41–45: Agent-zu-Agent-Kommunikationsopcodes."""

    def test_tell_nachricht(self):
        """Test 41: TELL — Sende Nachricht an Agenten."""
        asm = "MOVI R0, 1\nMOVI R1, 42\nTELL R0, R1\nHALT"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert len(ergebnis.nachrichten) == 1
        assert ergebnis.nachrichten[0]["typ"] == "TELL"
        assert ergebnis.nachrichten[0]["agent"] == 1
        assert ergebnis.nachrichten[0]["nachricht"] == 42

    def test_ask_frage(self):
        """Test 42: ASK — Stelle Frage an Agenten."""
        asm = "MOVI R0, 2\nMOVI R1, 99\nASK R0, R1\nHALT"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert len(ergebnis.nachrichten) == 1
        assert ergebnis.nachrichten[0]["typ"] == "ASK"
        assert ergebnis.nachrichten[0]["thema"] == 99

    def test_delegate_aufgabe(self):
        """Test 43: DELEGATE — Delegiere Aufgabe an Agenten."""
        asm = "MOVI R0, 5\nMOVI R1, 77\nDELEGATE R0, R1\nHALT"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert len(ergebnis.nachrichten) == 1
        assert ergebnis.nachrichten[0]["typ"] == "DELEGATE"
        assert ergebnis.nachrichten[0]["aufgabe"] == 77

    def test_broadcast_rundsendung(self):
        """Test 44: BROADCAST — Sende Broadcast an alle."""
        asm = "MOVI R0, 0\nMOVI R1, 255\nBROADCAST R0, R1\nHALT"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert len(ergebnis.nachrichten) == 1
        assert ergebnis.nachrichten[0]["typ"] == "BROADCAST"

    def test_trust_check_vertrauensprüfung(self):
        """Test 45: TRUST_CHECK — Kasus-basierte Vertrauensprüfung."""
        bytecode = schnell_kodieren("MOVI R0, 1\nMOVI R1, 2\nTRUST_CHECK R0, R1\nHALT")
        vm = FluxVmDeu(bytecode, kasus_pruefung=True, ablaufverfolgung=True)
        vm.setze_register_kasus(0, Kasus.GENITIV)    # MOVI → Schreiben → Genitiv reicht
        vm.setze_register_kasus(1, Kasus.AKKUSATIV) # MOVI → Schreiben → Akkusativ nötig
        ergebnis = vm.ausfuehren()
        assert ergebnis.erfolg is True
        assert len(ergebnis.vertrauenspruefungen) == 1
        pruefung = ergebnis.vertrauenspruefungen[0]
        assert pruefung["agent_kasus"] == "Genitiv"
        assert pruefung["ziel_kasus"] == "Akkusativ"
        assert pruefung["vertraut"] is True


# ══════════════════════════════════════════════════════════════════════
# KODIERER-TESTS
# ══════════════════════════════════════════════════════════════════════

class TestKodiererEnglisch:
    """Tests 46–48: Englische Mnemoniken."""

    def test_englische_mnemonik_mov(self):
        """Test 46: MOV wird korrekt kodiert."""
        puffer, anweisungen, marken = kodiere_assembly("MOV R0, R1\nHALT")
        assert puffer[0] == Op.MOV
        assert anweisungen[0].mnemonik in ("BEWEGEN", "MOV")

    def test_englische_mnemonik_halt(self):
        """Test 47: HALT wird korrekt kodiert."""
        puffer, _, _ = kodiere_assembly("HALT")
        assert len(puffer) == 1
        assert puffer[0] == Op.HALT

    def test_marken_vorwaertsreferenz(self):
        """Test 48: Vorwärtsreferenz auf Marke wird aufgelöst."""
        asm = "JMP ende\nMOVI R0, 0\nHALT\nende:\nMOVI R0, 42\nHALT"
        puffer, anweisungen, marken = kodiere_assembly(asm)
        assert "ende" in marken
        assert puffer[0] == Op.JMP
        ergebnis = schnellausfuehrung(puffer)
        assert ergebnis.ergebnis == 42


class TestKodiererDeutsch:
    """Tests 49–52: Deutsche Mnemoniken."""

    def test_deutsche_mnemonik_bewegen(self):
        """Test 49: BEWEGEN (deutsch für MOV) wird kodiert."""
        puffer, anweisungen, _ = kodiere_assembly("BEWEGEN R0, R1\nANHALTEN")
        assert puffer[0] == Op.MOV

    def test_deutsche_mnemonik_addieren(self):
        """Test 50: ADDIEREN (deutsch für IADD) wird kodiert."""
        puffer, _, _ = kodiere_assembly("ADDIEREN R0, R1, R2\nANHALTEN")
        assert puffer[0] == Op.IADD

    def test_deutsche_registernamen(self):
        """Test 51: Deutsche Registernamen (Null, Eins, Zwei)."""
        asm = "LADE_SOFORT Null, 42\nLADE_SOFORT Eins, 8\nADDIEREN Null, Null, Eins\nANHALTEN"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 50

    def test_deutsche_schleife(self):
        """Test 52: Vollständige deutsche Schleife (SPRINGE, ERHÖHEN, VERRINGERN)."""
        asm = (
            "LADE_SOFORT Null, 0\nLADE_SOFORT Eins, 10\n"
            "schleife:\n"
            "ADDIEREN Null, Null, Eins\n"
            "VERRINGERN Eins\n"
            "SPRINGE_NICHT_NULL Eins, schleife\n"
            "ANHALTEN"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 55  # 10 + 9 + 8 + ... + 1 = 55

    def test_themen_register(self):
        """Test 53: Spezielles Register 'Thema' (R60) wird erkannt."""
        asm = "LADE_SOFORT Thema, 42\nBEWEGEN Null, Thema\nANHALTEN"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 42

    def test_mnemonik_prüfung_deutsch(self):
        """Test 54: asm_mnemonik_prüfung erkennt gueltige Mnemoniken."""
        assert asm_mnemonik_prüfen("ADDIEREN") is True
        assert asm_mnemonik_prüfen("IADD") is True
        assert asm_mnemonik_prüfen("ANHALTEN") is True
        assert asm_mnemonik_prüfen("HALT") is True
        assert asm_mnemonik_prüfen("GIBTESNICHT") is False


# ══════════════════════════════════════════════════════════════════════
# VOKABELSYSTEM
# ══════════════════════════════════════════════════════════════════════

class TestVokabelsystem:
    """Tests 55–58: Wortschatzregister und Vokabelkacheln."""

    def test_standardvokabeln_geladen(self):
        """Test 55: Standardvokabeln werden beim ersten Zugriff geladen."""
        register = gib_wortschatz()
        assert register.anzahl > 0

    def test_suche_vokabel(self):
        """Test 56: Vokabelsuche findet passende Einträge."""
        ergebnisse = suche_vokabel("lade register null mit 42")
        assert len(ergebnisse) > 0

    def test_kompiliere_deutsch(self):
        """Test 57: kompiliere_deutsch gibt Assembly zurück."""
        assembly = kompiliere_deutsch("berechne 3 plus 5")
        assert assembly is not None
        assert "MOVI" in assembly or "IADD" in assembly

    def test_stufen_klassifizierung(self):
        """Test 58: Vokabeln sind korrekt nach Stufen klassifiziert."""
        register = gib_wortschatz()
        primitive = register.gib_stufe(VokabelStufe.PRIMITIV)
        zusammengesetzt = register.gib_stufe(VokabelStufe.ZUSAMMENGESETZT)
        domaene = register.gib_stufe(VokabelStufe.DOMAENE)
        assert len(primitive) > 0
        assert len(zusammengesetzt) > 0
        assert len(domaene) > 0

    def test_kasus_annotierte_vokabeln(self):
        """Test 59: Kasus-annotierte Vokabeln haben richtige CapLevel."""
        register = gib_wortschatz()
        akkusativ_vokabeln = register.gib_kasus(Kasus.AKKUSATIV)
        assert len(akkusativ_vokabeln) > 0
        for v in akkusativ_vokabeln:
            assert v.kasus == Kasus.AKKUSATIV
            assert v.cap_level == CapLevel.CAP_READWRITE

    def test_kategorie_suche(self):
        """Test 60: Kategorie-Suche findet gruppierte Vokabeln."""
        register = gib_wortschatz()
        arithmetik = register.gib_kategorie("arithmetik")
        a2a = register.gib_kategorie("a2a")
        assert len(arithmetik) > 0
        assert len(a2a) > 0


# ══════════════════════════════════════════════════════════════════════
# FEHLERBEHANDLUNG UND GRENZFÄLLE
# ══════════════════════════════════════════════════════════════════════

class TestFehlerbehandlung:
    """Tests 61–65: Fehlerbehandlung und Grenzfälle."""

    def test_division_durch_null(self):
        """Test 61: IDIV durch Null erzeugt Fehler."""
        ergebnis = _exec("MOVI R0, 10\nMOVI R1, 0\nIDIV R0, R0, R1\nHALT")
        assert ergebnis.erfolg is False
        assert ergebnis.fehler is not None
        assert "Null" in ergebnis.fehler

    def test_modulo_durch_null(self):
        """Test 62: IMOD durch Null erzeugt Fehler."""
        ergebnis = _exec("MOVI R0, 10\nMOVI R1, 0\nIMOD R0, R0, R1\nHALT")
        assert ergebnis.erfolg is False

    def test_leeres_programm(self):
        """Test 63: Leeres Programm gibt Ergebnis 0."""
        ergebnis = schnellausfuehrung(b"")
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 0

    def test_nur_halt(self):
        """Test 64: Nur HALT-Anweisung."""
        ergebnis = _exec("HALT")
        assert ergebnis.erfolg is True
        assert ergebnis.angehalten is True

    def test_zyklenlimit(self):
        """Test 65: Endlosschleife wird durch Zyklenlimit gestoppt."""
        asm = "schleife:\nJMP schleife"
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is False
        assert "Zyklen" in (ergebnis.fehler or "")

    def test_ablaufverfolgung(self):
        """Test 66: Ablaufverfolgung zeichnet jeden Befehl auf."""
        ergebnis = _exec("MOVI R0, 1\nINC R0\nHALT", spur=True)
        assert len(ergebnis.spur) == 3
        assert any("MOVI" in s for s in ergebnis.spur)
        assert any("INC" in s for s in ergebnis.spur)
        assert any("HALT" in s for s in ergebnis.spur)


# ══════════════════════════════════════════════════════════════════════
# KOMPLEXE PROGRAMME
# ══════════════════════════════════════════════════════════════════════

class TestKomplexeProgramme:
    """Tests 67–70: Komplexere Programme mit mehreren Konzepten."""

    def test_fakultät_von_fünf(self):
        """Test 67: Berechne 5! = 120."""
        asm = (
            "MOVI R0, 5\nMOVI R1, 1\nMOV R2, R0\n"
            "fak:\nJZ R2, fak_ende\nIMUL R1, R1, R2\nDEC R2\nJMP fak\n"
            "fak_ende:\nMOV R0, R1\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 120

    def test_fibonacci_zehn(self):
        """Test 68: Berechne die 10. Fibonacci-Zahl."""
        asm = (
            "MOVI R0, 0\nMOVI R1, 1\nMOVI R2, 10\n"
            "fib:\nJZ R2, fib_ende\n"
            "MOV R3, R1\nIADD R1, R0, R1\nMOV R0, R3\n"
            "DEC R2\nJMP fib\n"
            "fib_ende:\nMOV R0, R1\nHALT"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 89  # 10 Iterationen → Fib(11) = 89

    def test_agent_kommunikation_mit_vertrauen(self):
        """Test 69: Agent kommuniziert nach Vertrauensprüfung."""
        bytecode = schnell_kodieren(
            "MOVI R0, 1\nMOVI R1, 2\nMOVI R2, 42\n"
            "TRUST_CHECK R0, R1\n"
            "TELL R0, R2\n"
            "HALT"
        )
        vm = FluxVmDeu(bytecode, kasus_pruefung=True)
        vm.setze_register_kasus(0, Kasus.GENITIV)     # MOVI + TRUST_READ → Genitiv (vollzugriff)
        vm.setze_register_kasus(1, Kasus.AKKUSATIV)   # MOVI schreibt → Akkusativ nötig
        vm.setze_register_kasus(2, Kasus.AKKUSATIV)   # MOVI schreibt → Akkusativ nötig
        ergebnis = vm.ausfuehren()
        assert ergebnis.erfolg is True
        assert len(ergebnis.nachrichten) == 1

    def test_deutsches_programm_vollstaendig(self):
        """Test 70: Vollständiges Programm mit deutschen Mnemoniken und Registern."""
        asm = (
            "# Berechne die Summe von 1 bis 10 mit deutschen Mnemoniken\n"
            "LADE_SOFORT Null, 0\n"
            "LADE_SOFORT Eins, 10\n"
            "LADE_SOFORT Zwei, 0\n"
            "summierung:\n"
            "ADDIEREN Null, Null, Eins\n"
            "VERRINGERN Eins\n"
            "ERHÖHEN Zwei\n"
            "SPRINGE_NICHT_NULL Eins, summierung\n"
            "BEWEGEN Null, Null\n"
            "ANHALTEN"
        )
        ergebnis = _exec(asm)
        assert ergebnis.erfolg is True
        assert ergebnis.ergebnis == 55  # 10 + 9 + ... + 1


# ══════════════════════════════════════════════════════════════════════
# OPCODE-KOMPLETTHEIT
# ══════════════════════════════════════════════════════════════════════

class TestOpcodeTabelle:
    """Tests 71–75: Opcode-Tabelle und Mnemonik-Zuordnung."""

    def test_alle_opcodes_haben_namen(self):
        """Test 71: Alle Opcodes haben einen Namen in der Rückwärtstabelle."""
        for op in Op:
            assert op in OP_NAMEN, f"Opcode {op} ({op:#x}) hat keinen Namen"

    def test_deutsche_mnemonik_tabelle_vollstaendig(self):
        """Test 72: Deutsche Mnemoniktabelle enthält alle wichtigen Befehle."""
        from flux_deu.encoder import _DEUTSCH_ZU_OPCODE
        assert Op.NOP in _DEUTSCH_ZU_OPCODE.values()
        assert Op.IADD in _DEUTSCH_ZU_OPCODE.values()
        assert Op.ISUB in _DEUTSCH_ZU_OPCODE.values()
        assert Op.HALT in _DEUTSCH_ZU_OPCODE.values()
        assert Op.MOVI in _DEUTSCH_ZU_OPCODE.values()
        assert Op.TELL in _DEUTSCH_ZU_OPCODE.values()

    def test_register_konventionen(self):
        """Test 73: Register-Konventionen sind korrekt."""
        assert THEMEN_REGISTER == 60
        assert OBJEKT_REGISTER == 61
        assert DATIV_REGISTER == 62
        assert GENITIV_REGISTER == 63
        assert ANZAHL_REGISTER == 64

    def test_kodierte_anweisung_darstellung(self):
        """Test 74: KodierteAnweisung hat lesbare Darstellung."""
        anweisung = KodierteAnweisung(
            versatz=0, opcode=Op.IADD, operanden=[0, 1, 2], groesse=4, mnemonik="IADD"
        )
        text = repr(anweisung)
        assert "IADD" in text
        assert "0" in text

    def test_kombiniertes_format(self):
        """Test 75: kombiniertes_format gibt lesbare Tabelle zurück."""
        anweisungen = [
            KodierteAnweisung(0, Op.MOVI, [0, 42], 4, "MOVI"),
            KodierteAnweisung(4, Op.HALT, [], 1, "HALT"),
        ]
        text = kombiniertes_format(anweisungen)
        assert "0000:" in text
        assert "MOVI" in text
        assert "HALT" in text
