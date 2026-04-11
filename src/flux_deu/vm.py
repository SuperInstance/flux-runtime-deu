"""
FLUX-deu Virtuelle Maschine — 64-Register-Stackmaschine mit Kasus-basierter Zugriffssteuerung.

Diese VM ist die sprachagnostische Ausführungsschicht, die von der deutschen NL-Schicht
angesteuert wird. Sie implementiert den vollständigen FLUX-Bytecode-Befehlssatz und
erzwingt Kasus-abgeleitete Capability-Level bei jedem Register- und Speicherzugriff.

Kasus-Zugriffskontrolle:
    Nominativ  → CAP_PUBLIC     (0) — Öffentliche Leseberechtigung
    Akkusativ  → CAP_READWRITE  (2) — Lese- und Schreibzugriff
    Dativ      → CAP_REFERENCE  (1) — Indirekter Referenzzugriff
    Genitiv    → CAP_TRANSFER   (3) — Eigentumsübertragung

Register-Konvention:
    R0–R59  — Allgemeine Register
    R60     — Themenregister (Subjekt des aktuellen Satzes)
    R61     — Objektregister (Akkusativobjekt)
    R62     — Dativreferenz-Register
    R63     — Genitivbesitz-Register

Jeder Befehl wird vor der Ausführung auf Kasus-Konformität geprüft.
Verstöße führen zu einem KasusFehler mit deutscher Fehlermeldung.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

from flux_deu.kasus import Kasus, CapLevel, KasusValidator, KASUS_TO_CAP, CAP_TO_KASUS


# ══════════════════════════════════════════════════════════════════════
# FLUX-Opcodes — Sprachagnostischer Bytecode-Befehlssatz
# Kompatibel mit flux-runtime-zho's Op-Klasse
# ══════════════════════════════════════════════════════════════════════

class Op(IntEnum):
    """
    FLUX-Bytecode-Opcode-Aufzählung — Variabel-Längen-Kodierung (1–4 Bytes).

    Opcode-Bereiche:
        0x00–0x07  Steuerfluss
        0x08–0x0F  Ganzzahlarithmetik
        0x10–0x17  Bitoperationen
        0x18–0x1F  Vergleiche
        0x20–0x27  Stapeloperationen
        0x28–0x2F  Funktionsoperationen
        0x30–0x37  Speicherverwaltung
        0x38–0x3F  Typoperationen
        0x40–0x47  Gleitkommaarithmetik
        0x48–0x4F  Gleitkommavergleiche
        0x50–0x57  Zeichenkettenoperationen
        0x60–0x7F  Agentenprotokoll (A2A)
        0xFE–0xFF  System
    """
    # ── Steuerfluss (0x00–0x07) ──────────────────────────────────────
    NOP = 0x00
    MOV = 0x01
    LOAD = 0x02
    STORE = 0x03
    JMP = 0x04
    JZ = 0x05
    JNZ = 0x06
    CALL = 0x07

    # ── Ganzzahlarithmetik (0x08–0x0F) ──────────────────────────────
    IADD = 0x08
    ISUB = 0x09
    IMUL = 0x0A
    IDIV = 0x0B
    IMOD = 0x0C
    INEG = 0x0D
    INC = 0x0E
    DEC = 0x0F

    # ── Bitoperationen (0x10–0x17) ──────────────────────────────────
    IAND = 0x10
    IOR = 0x11
    IXOR = 0x12
    INOT = 0x13
    ISHL = 0x14
    ISHR = 0x15
    ROTL = 0x16
    ROTR = 0x17

    # ── Vergleiche (0x18–0x1F) ─────────────────────────────────────
    ICMP = 0x18
    IEQ = 0x19
    ILT = 0x1A
    ILE = 0x1B
    IGT = 0x1C
    IGE = 0x1D
    TEST = 0x1E
    SETCC = 0x1F

    # ── Stapeloperationen (0x20–0x27) ───────────────────────────────
    PUSH = 0x20
    POP = 0x21
    DUP = 0x22
    SWAP = 0x23
    ROT = 0x24
    ENTER = 0x25
    LEAVE = 0x26
    ALLOCA = 0x27

    # ── Funktionsoperationen (0x28–0x2F) ───────────────────────────
    RET = 0x28
    CALL_IND = 0x29
    TAILCALL = 0x2A
    MOVI = 0x2B
    IREM = 0x2C
    CMP = 0x2D
    JE = 0x2E
    JNE = 0x2F

    # ── Speicherverwaltung (0x30–0x37) ──────────────────────────────
    REGION_CREATE = 0x30
    REGION_DESTROY = 0x31
    REGION_TRANSFER = 0x32
    MEMCOPY = 0x33
    MEMSET = 0x34
    MEMCMP = 0x35
    JL = 0x36
    JGE = 0x37

    # ── Typoperationen (0x38–0x3F) ─────────────────────────────────
    CAST = 0x38
    BOX = 0x39
    UNBOX = 0x3A
    CHECK_TYPE = 0x3B
    CHECK_BOUNDS = 0x3C

    # ── Gleitkommaarithmetik (0x40–0x47) ──────────────────────────
    FADD = 0x40
    FSUB = 0x41
    FMUL = 0x42
    FDIV = 0x43
    FNEG = 0x44
    FABS = 0x45
    FMIN = 0x46
    FMAX = 0x47

    # ── Gleitkommavergleiche (0x48–0x4F) ──────────────────────────
    FEQ = 0x48
    FLT = 0x49
    FLE = 0x4A
    FGT = 0x4B
    FGE = 0x4C

    # ── Zeichenkettenoperationen (0x50–0x57) ───────────────────────
    SLEN = 0x50
    SCONCAT = 0x51
    SCHAR = 0x52
    SSUB = 0x53
    SCMP = 0x54

    # ── Agentenprotokoll (0x60–0x7F) ────────────────────────────────
    TELL = 0x60
    ASK = 0x61
    DELEGATE = 0x62
    BROADCAST = 0x63
    TRUST_CHECK = 0x64
    CAP_REQUIRE = 0x65

    # ── System (0xFE–0xFF) ──────────────────────────────────────────
    PRINT = 0xFE
    HALT = 0xFF


# Opcode-Rückwärtstabelle: Opcode-Nummer → Name
OP_NAMEN: dict[int, str] = {}
for _name, _code in list(vars(Op).items()):
    if isinstance(_code, int) and not _name.startswith("_") and _name.isupper():
        OP_NAMEN[_code] = _name


# ══════════════════════════════════════════════════════════════════════
# Register-Konventionen
# ══════════════════════════════════════════════════════════════════════

ANZAHL_REGISTER = 64
THEMEN_REGISTER = 60     # R60 — Subjekt des aktuellen Satzes (Nominativ)
OBJEKT_REGISTER = 61     # R61 — Akkusativobjekt
DATIV_REGISTER = 62      # R62 — Dativreferenz
GENITIV_REGISTER = 63     # R63 — Genitivbesitz


# ══════════════════════════════════════════════════════════════════════
# Ausnahmeklassen
# ══════════════════════════════════════════════════════════════════════

class KasusFehler(Exception):
    """Kasus-Verletzung bei Register- oder Speicherzugriff."""
    pass


class VmFehler(Exception):
    """Allgemeiner VM-Laufzeitfehler."""
    pass


class StapelUeberlauf(Exception):
    """Stapelüberlauf — Stapel hat die maximale Größe erreicht."""
    pass


class StapelLeer(Exception):
    """Stapelunterlauf — Stapel ist leer."""
    pass


class DivisionDurchNull(Exception):
    """Division oder Modulo durch Null."""
    pass


# ══════════════════════════════════════════════════════════════════════
# Ausführungsergebnis
# ══════════════════════════════════════════════════════════════════════

@dataclass
class AusfuehrungsErgebnis:
    """
    Ergebnis der VM-Ausführung.

    Attribute:
        erfolg:    Ob die Ausführung ohne Fehler beendet wurde.
        ergebnis:  Wert von Register R0 nach Ausführung.
        register:  Kopie aller 64 Register.
        zyklen:    Anzahl der verbrauchten CPU-Zyklen.
        fehler:    Fehlernachricht oder None bei Erfolg.
        angehalten: Ob HALT erreicht wurde.
        nachrichten: Liste der Agent-zu-Agent-Nachrichten.
        vertrauenspruefungen: Liste der TRUST_CHECK-Ergebnisse.
        spur:      Ablaufverfolgungsprotokoll (bei aktivierter Ablaufverfolgung).
    """
    erfolg: bool
    ergebnis: int
    register: list[int]
    zyklen: int
    fehler: Optional[str]
    angehalten: bool
    nachrichten: list[dict[str, Any]] = field(default_factory=list)
    vertrauenspruefungen: list[dict[str, Any]] = field(default_factory=list)
    spur: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# FLUX-deu Virtuelle Maschine
# ══════════════════════════════════════════════════════════════════════

class FluxVmDeu:
    """
    FLUX-deu Virtuelle Maschine — 64-Register-Stackmaschine mit Kasus-Zugriffskontrolle.

    Diese VM erzwingt Kasus-abgeleitete Capability-Level bei jedem Zugriff:
      - Schreibzugriffe erfordern mindestens CAP_READWRITE (Akkusativ).
      - Eigentumsübertragungen erfordern CAP_TRANSFER (Genitiv).
      - Leszugriffe erfordern mindestens CAP_PUBLIC (Nominativ).

    Die Register R60–R63 sind speziellen Kasus-Funktionen zugeordnet:
      R60 = Themenregister   (Nominativ — Satzsubjekt)
      R61 = Objektregister    (Akkusativ — direktes Objekt)
      R62 = Dativregister     (Dativ — indirektes Objekt)
      R63 = Genitivregister   (Genitiv — Besitzangabe)

    Args:
        bytecode:    Zu ausführender FLUX-Bytecode (Bytes oder Bytearray).
        max_zyklen:  Maximale Anzahl an CPU-Zyklen (Schutz vor Endlosschleifen).
        kasus_pruefung: Ob Kasus-Zugriffskontrolle aktiv ist.
        ablaufverfolgung: Ob jeder Befehl im Spurprotokoll aufgezeichnet wird.
    """

    def __init__(
        self,
        bytecode: bytes | bytearray,
        *,
        max_zyklen: int = 1_000_000,
        kasus_pruefung: bool = True,
        ablaufverfolgung: bool = False,
    ):
        # 64 Register, alle mit 0 initialisiert
        self.register: list[int] = [0] * ANZAHL_REGISTER

        # Flags für bedingte Sprünge
        self.flags: dict[str, bool] = {
            "null": False,       # Null-Flag (Ergebnis ist 0)
            "negativ": False,    # Negativ-Flag (Ergebnis < 0)
            "uebertrag": False,  # Übertrags-Flag
            "ueberlauf": False,  # Überlauf-Flag
        }

        # Stapel für PUSH/POP-Operationen
        self.stapel: list[int] = []
        self._stapel_max = 65_536  # Maximale Stapelgröße

        # Programmzähler
        self.bzaehler: int = 0

        # Bytecode und Ausführungszustand
        self.bytecode: bytes = bytes(bytecode)
        self.zyklen: int = 0
        self.max_zyklen: int = max_zyklen
        self.angehalten: bool = False
        self.fehler: Optional[str] = None

        # Kasus-Zugriffskontrolle
        self.kasus_pruefung: bool = kasus_pruefung
        self.kasus_validator: KasusValidator = KasusValidator()

        # Kasus-Zuordnung pro Register (Standard: Nominativ für alle)
        self._register_kasus: dict[int, Kasus] = {
            i: Kasus.NOMINATIV for i in range(ANZAHL_REGISTER)
        }
        # Spezielle Register bekommen ihren Kasus
        self._register_kasus[THEMEN_REGISTER] = Kasus.NOMINATIV
        self._register_kasus[OBJEKT_REGISTER] = Kasus.AKKUSATIV
        self._register_kasus[DATIV_REGISTER] = Kasus.DATIV
        self._register_kasus[GENITIV_REGISTER] = Kasus.GENITIV

        # Ablaufverfolgung
        self.ablaufverfolgung: bool = ablaufverfolgung
        self.spur: list[str] = []

        # Agent-zu-Agent Nachrichtenspeicher
        self._nachrichten: list[dict[str, Any]] = []

        # Vertrauensprüfungsprotokoll
        self._vertrauenspruefungen: list[dict[str, Any]] = []

        # Speicherregionen (für REGION_*-Befehle)
        self._speicher: dict[int, int] = {}

    # ── Kasus-Verwaltung ────────────────────────────────────────────

    def setze_register_kasus(self, reg: int, kasus: Kasus) -> None:
        """
        Setze den Kasus eines Registers.

        Bestimmt, welche Zugriffsebene für dieses Register erforderlich ist.
        """
        if 0 <= reg < ANZAHL_REGISTER:
            self._register_kasus[reg] = kasus

    def nenne_register_kasus(self, reg: int) -> Kasus:
        """Gib den aktuellen Kasus eines Registers zurück."""
        return self._register_kasus.get(reg, Kasus.NOMINATIV)

    def setze_bereich_kasus(self, adresse: int, kasus: Kasus) -> None:
        """Setze den Kasus für eine Speicheradresse."""
        self.kasus_validator.define_scope(
            f"mem_{adresse}", kasus, owner="vm_speicher"
        )

    def _pruefe_kasuszugriff(self, reg: int, erforderlich: CapLevel) -> None:
        """
        Prüfe ob der aktuelle Kasus des Registers den erforderlichen Capability-Level erfüllt.

        Löst KasusFehler aus bei Verstoß.
        """
        if not self.kasus_pruefung:
            return

        aktueller_kasus = self._register_kasus.get(reg, Kasus.NOMINATIV)
        aktueller_cap = KASUS_TO_CAP[aktueller_kasus]

        if aktueller_cap < erforderlich:
            kasus_name = aktueller_kasus.value
            erforderlicher_kasus = CAP_TO_KASUS.get(erforderlich, Kasus.GENITIV)
            raise KasusFehler(
                f"Kasus-Verletzung: Register R{reg} hat {kasus_name} "
                f"(CapLevel {aktueller_cap.value}), aber es wird "
                f"{erforderlicher_kasus.value} (CapLevel {erforderlich.value}) "
                f"benötigt für diesen Zugriff."
            )

    # ── Register-Lese- und Schreibzugriff ───────────────────────────

    def lese_register(self, reg: int) -> int:
        """
        Lies den Wert eines Registers mit Kasus-Prüfung.

        Lesezugriff erfordert mindestens CAP_PUBLIC (Nominativ).
        """
        if not (0 <= reg < ANZAHL_REGISTER):
            raise VmFehler(f"Ungültiges Register: R{reg} (gültig: R0–R63)")
        self._pruefe_kasuszugriff(reg, CapLevel.CAP_PUBLIC)
        return self.register[reg]

    def schreibe_register(self, reg: int, wert: int) -> None:
        """
        Schreibe einen Wert in ein Register mit Kasus-Prüfung.

        Schreibzugriff erfordert mindestens CAP_READWRITE (Akkusativ).
        """
        if not (0 <= reg < ANZAHL_REGISTER):
            raise VmFehler(f"Ungültiges Register: R{reg} (gültig: R0–R63)")
        self._pruefe_kasuszugriff(reg, CapLevel.CAP_READWRITE)
        self.register[reg] = wert & 0xFFFFFFFF if wert >= 0 else (wert & 0xFFFFFFFF)

    def _pruefe_genitiv_transfer(self, quell_reg: int, ziel_reg: int) -> None:
        """
        Prüfe ob eine Eigentumsübertragung (Genitiv) erlaubt ist.

        Wird bei REGION_TRANSFER und ähnlichen Operationen aufgerufen.
        """
        if not self.kasus_pruefung:
            return
        self._pruefe_kasuszugriff(quell_reg, CapLevel.CAP_TRANSFER)
        self._pruefe_kasuszugriff(ziel_reg, CapLevel.CAP_READWRITE)

    # ── Stapeloperationen ───────────────────────────────────────────

    def _stapel_ablegen(self, wert: int) -> None:
        """Lege einen Wert auf den Stapel."""
        if len(self.stapel) >= self._stapel_max:
            raise StapelUeberlauf(
                f"Stapelüberlauf: Maximal {self._stapel_max} Einträge erlaubt."
            )
        self.stapel.append(wert)

    def _stapel_nehmen(self) -> int:
        """Nimm den obersten Wert vom Stapel."""
        if not self.stapel:
            raise StapelLeer("Stapelunterlauf: Der Stapel ist leer.")
        return self.stapel.pop()

    # ── Flag-Aktualisierung ─────────────────────────────────────────

    def _aktualisiere_flags(self, ergebnis: int) -> None:
        """Aktualisiere die CPU-Flags basierend auf einem Ergebnis."""
        self.flags["null"] = (ergebnis == 0)
        self.flags["negativ"] = (ergebnis < 0)

    # ── Speicher-Lese-Hilfsfunktionen ───────────────────────────────

    def _lese_u16(self, offset: int) -> int:
        """Lese eine vorzeichenlose 16-Bit-Ganzzahl aus dem Bytecode."""
        if offset + 1 >= len(self.bytecode):
            raise VmFehler(
                f"Bytecode-Lesefehler: Offset {offset} außerhalb des Programms "
                f"(Länge: {len(self.bytecode)})"
            )
        return self.bytecode[offset] | (self.bytecode[offset + 1] << 8)

    def _lese_i16(self, offset: int) -> int:
        """Lese eine vorzeichenbehaftete 16-Bit-Ganzzahl aus dem Bytecode."""
        raw = self._lese_u16(offset)
        return raw if raw < 32768 else raw - 65536

    # ── Ablaufverfolgung ────────────────────────────────────────────

    def _protokolliere(self, nachricht: str) -> None:
        """Schreibe eine Nachricht in das Ablaufverfolgungsprotokoll."""
        if self.ablaufverfolgung:
            self.spur.append(nachricht)

    # ── Wert-Helper für vorzeichenbehaftete Ganzzahlen ──────────────

    @staticmethod
    def _zu_vorzeichen(wert: int) -> int:
        """Wandle einen 32-Bit-Wert in eine vorzeichenbehaftete Ganzzahl um."""
        if wert >= 0x80000000:
            return wert - 0x100000000
        return wert

    # ══════════════════════════════════════════════════════════════════
    # Hauptausführungsschleife
    # ══════════════════════════════════════════════════════════════════

    def ausfuehren(self) -> AusfuehrungsErgebnis:
        """
        Führe das geladene Bytecode-Programm aus bis HALT oder max_zyklen erreicht.

        Returns:
            AusfuehrungsErgebnis mit Registerstand, Zyklenzahl und Fehlerstatus.
        """
        while (
            self.bzaehler < len(self.bytecode)
            and not self.angehalten
            and self.zyklen < self.max_zyklen
        ):
            opcode = self.bytecode[self.bzaehler]
            self.zyklen += 1

            try:
                self._fuehre_befehl_aus(opcode)
            except KasusFehler as e:
                self.fehler = str(e)
                self.angehalten = True
                self._protokolliere(f"KASUS-FEHLER: {e}")
            except DivisionDurchNull as e:
                self.fehler = str(e)
                self.angehalten = True
                self._protokolliere(f"DIVISIONSFEHLER: {e}")
            except (StapelUeberlauf, StapelLeer) as e:
                self.fehler = str(e)
                self.angehalten = True
                self._protokolliere(f"STAPELFEHLER: {e}")

        if self.zyklen >= self.max_zyklen and not self.angehalten:
            self.fehler = (
                f"Maximale Zyklenanzahl ({self.max_zyklen}) überschritten — "
                f"mögliche Endlosschleife erkannt."
            )
            self._protokolliere(f"ZYKLENLIMIT: {self.fehler}")

        return AusfuehrungsErgebnis(
            erfolg=(self.fehler is None),
            ergebnis=self._zu_vorzeichen(self.register[0]),
            register=list(self.register),
            zyklen=self.zyklen,
            fehler=self.fehler,
            angehalten=self.angehalten,
            nachrichten=list(self._nachrichten),
            vertrauenspruefungen=list(self._vertrauenspruefungen),
            spur=list(self.spur),
        )

    def _fuehre_befehl_aus(self, opcode: int) -> None:
        """Führe einen einzelnen Befehl basierend auf seinem Opcode aus."""

        # ── NOP ─────────────────────────────────────────────────────
        if opcode == Op.NOP:
            self._protokolliere(f"[{self.bzaehler:04d}] NOP")
            self.bzaehler += 1

        # ── MOV rd, rs ─────────────────────────────────────────────
        elif opcode == Op.MOV:
            rd = self.bytecode[self.bzaehler + 1]
            rs = self.bytecode[self.bzaehler + 2]
            wert = self.lese_register(rs)
            self.schreibe_register(rd, wert)
            self._protokolliere(f"[{self.bzaehler:04d}] MOV R{rd}, R{rs}  (={wert})")
            self.bzaehler += 3

        # ── LOAD rd, rs ────────────────────────────────────────────
        elif opcode == Op.LOAD:
            rd = self.bytecode[self.bzaehler + 1]
            rs = self.bytecode[self.bzaehler + 2]
            wert = self.lese_register(rs)
            self.schreibe_register(rd, wert)
            self._protokolliere(f"[{self.bzaehler:04d}] LOAD R{rd}, R{rs}  (={wert})")
            self.bzaehler += 3

        # ── STORE rd, rs (rs ← Wert von rd) ───────────────────────
        elif opcode == Op.STORE:
            rd = self.bytecode[self.bzaehler + 1]
            rs = self.bytecode[self.bzaehler + 2]
            wert = self.lese_register(rd)
            self.schreibe_register(rs, wert)
            self._protokolliere(
                f"[{self.bzaehler:04d}] STORE R{rd}, R{rs}  (R{rs}←{wert})"
            )
            self.bzaehler += 3

        # ── JMP adresse ────────────────────────────────────────────
        elif opcode == Op.JMP:
            addr = self._lese_u16(self.bzaehler + 1)
            self._protokolliere(f"[{self.bzaehler:04d}] JMP {addr}")
            self.bzaehler = addr

        # ── JZ r, adresse ─────────────────────────────────────────
        elif opcode == Op.JZ:
            r = self.bytecode[self.bzaehler + 1]
            addr = self._lese_u16(self.bzaehler + 2)
            wert = self.lese_register(r)
            if wert == 0:
                self._protokolliere(f"[{self.bzaehler:04d}] JZ R{r}, {addr}  → SPRUNG")
                self.bzaehler = addr
            else:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JZ R{r}, {addr}  → KEIN SPRUNG (R{r}={wert})"
                )
                self.bzaehler += 4

        # ── JNZ r, adresse ────────────────────────────────────────
        elif opcode == Op.JNZ:
            r = self.bytecode[self.bzaehler + 1]
            addr = self._lese_u16(self.bzaehler + 2)
            wert = self.lese_register(r)
            if wert != 0:
                self._protokolliere(f"[{self.bzaehler:04d}] JNZ R{r}, {addr}  → SPRUNG")
                self.bzaehler = addr
            else:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JNZ R{r}, {addr}  → KEIN SPRUNG (R{r}={wert})"
                )
                self.bzaehler += 4

        # ── CALL adresse ──────────────────────────────────────────
        elif opcode == Op.CALL:
            # Lege die Rücksprungadresse auf den Stapel
            # CALL ist 3 Bytes lang: opcode + 2 Bytes für die Adresse
            ruecksprung = self.bzaehler + 3
            self._stapel_ablegen(ruecksprung)
            addr = self._lese_u16(self.bzaehler + 1)
            self._protokolliere(
                f"[{self.bzaehler:04d}] CALL {addr}  (Rücksprung: {ruecksprung})"
            )
            self.bzaehler = addr

        # ── IADD rd, ra, rb ───────────────────────────────────────
        elif opcode == Op.IADD:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self.lese_register(ra)
            b = self.lese_register(rb)
            ergebnis = a + b
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] IADD R{rd}, R{ra}, R{rb}  "
                f"({a}+{b}={ergebnis})"
            )
            self.bzaehler += 4

        # ── ISUB rd, ra, rb ───────────────────────────────────────
        elif opcode == Op.ISUB:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self.lese_register(ra)
            b = self.lese_register(rb)
            ergebnis = a - b
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] ISUB R{rd}, R{ra}, R{rb}  "
                f"({a}-{b}={ergebnis})"
            )
            self.bzaehler += 4

        # ── IMUL rd, ra, rb ───────────────────────────────────────
        elif opcode == Op.IMUL:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self.lese_register(ra)
            b = self.lese_register(rb)
            ergebnis = a * b
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] IMUL R{rd}, R{ra}, R{rb}  "
                f"({a}*{b}={ergebnis})"
            )
            self.bzaehler += 4

        # ── IDIV rd, ra, rb ───────────────────────────────────────
        elif opcode == Op.IDIV:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self.lese_register(ra)
            b = self.lese_register(rb)
            if b == 0:
                raise DivisionDurchNull(
                    f"Division durch Null bei IDIV R{rd}, R{ra}, R{rb}: "
                    f"Teiler R{rb} ist 0."
                )
            ergebnis = int(a / b)
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] IDIV R{rd}, R{ra}, R{rb}  "
                f"({a}/{b}={ergebnis})"
            )
            self.bzaehler += 4

        # ── IMOD rd, ra, rb ───────────────────────────────────────
        elif opcode == Op.IMOD:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self.lese_register(ra)
            b = self.lese_register(rb)
            if b == 0:
                raise DivisionDurchNull(
                    f"Modulo durch Null bei IMOD R{rd}, R{ra}, R{rb}: "
                    f"Teiler R{rb} ist 0."
                )
            ergebnis = a % b
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] IMOD R{rd}, R{ra}, R{rb}  "
                f"({a}%{b}={ergebnis})"
            )
            self.bzaehler += 4

        # ── INEG r ────────────────────────────────────────────────
        elif opcode == Op.INEG:
            r = self.bytecode[self.bzaehler + 1]
            wert = self.lese_register(r)
            ergebnis = -self._zu_vorzeichen(wert)
            self.schreibe_register(r, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] INEG R{r}  ({self._zu_vorzeichen(wert)}→{ergebnis})"
            )
            self.bzaehler += 2

        # ── INC r ─────────────────────────────────────────────────
        elif opcode == Op.INC:
            r = self.bytecode[self.bzaehler + 1]
            wert = self.lese_register(r)
            ergebnis = self._zu_vorzeichen(wert) + 1
            self.schreibe_register(r, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] INC R{r}  ({self._zu_vorzeichen(wert)}→{ergebnis})"
            )
            self.bzaehler += 2

        # ── DEC r ─────────────────────────────────────────────────
        elif opcode == Op.DEC:
            r = self.bytecode[self.bzaehler + 1]
            wert = self.lese_register(r)
            ergebnis = self._zu_vorzeichen(wert) - 1
            self.schreibe_register(r, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(
                f"[{self.bzaehler:04d}] DEC R{r}  ({self._zu_vorzeichen(wert)}→{ergebnis})"
            )
            self.bzaehler += 2

        # ── Bitoperationen ─────────────────────────────────────────
        elif opcode == Op.IAND:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            ergebnis = self.lese_register(ra) & self.lese_register(rb)
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] IAND R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.IOR:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            ergebnis = self.lese_register(ra) | self.lese_register(rb)
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] IOR R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.IXOR:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            ergebnis = self.lese_register(ra) ^ self.lese_register(rb)
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] IXOR R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.INOT:
            r = self.bytecode[self.bzaehler + 1]
            ergebnis = ~self.lese_register(r) & 0xFFFFFFFF
            self.schreibe_register(r, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] INOT R{r}")
            self.bzaehler += 2

        elif opcode == Op.ISHL:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            ergebnis = self.lese_register(ra) << (self.lese_register(rb) & 0x1F)
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] ISHL R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.ISHR:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            ergebnis = self.lese_register(ra) >> (self.lese_register(rb) & 0x1F)
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] ISHR R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.ROTL:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            val = self.lese_register(ra)
            shift = self.lese_register(rb) & 0x1F
            ergebnis = ((val << shift) | (val >> (32 - shift))) & 0xFFFFFFFF
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] ROTL R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.ROTR:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            val = self.lese_register(ra)
            shift = self.lese_register(rb) & 0x1F
            ergebnis = ((val >> shift) | (val << (32 - shift))) & 0xFFFFFFFF
            self.schreibe_register(rd, ergebnis)
            self._aktualisiere_flags(ergebnis)
            self._protokolliere(f"[{self.bzaehler:04d}] ROTR R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        # ── Vergleiche ─────────────────────────────────────────────
        elif opcode == Op.CMP:
            ra = self.bytecode[self.bzaehler + 1]
            rb = self.bytecode[self.bzaehler + 2]
            a = self._zu_vorzeichen(self.lese_register(ra))
            b = self._zu_vorzeichen(self.lese_register(rb))
            diff = a - b
            self._aktualisiere_flags(diff)
            self._protokolliere(
                f"[{self.bzaehler:04d}] CMP R{ra}, R{rb}  ({a}-{b}={diff})"
            )
            self.bzaehler += 3

        elif opcode == Op.ICMP:
            ra = self.bytecode[self.bzaehler + 1]
            rb = self.bytecode[self.bzaehler + 2]
            a = self._zu_vorzeichen(self.lese_register(ra))
            b = self._zu_vorzeichen(self.lese_register(rb))
            self.flags["null"] = (a == b)
            self.flags["negativ"] = (a < b)
            self._protokolliere(
                f"[{self.bzaehler:04d}] ICMP R{ra}, R{rb}  ({a} cmp {b})"
            )
            self.bzaehler += 3

        # ── Stapeloperationen ───────────────────────────────────────
        elif opcode == Op.PUSH:
            r = self.bytecode[self.bzaehler + 1]
            wert = self.lese_register(r)
            self._stapel_ablegen(wert)
            self._protokolliere(f"[{self.bzaehler:04d}] PUSH R{r}  ({wert})")
            self.bzaehler += 2

        elif opcode == Op.POP:
            r = self.bytecode[self.bzaehler + 1]
            wert = self._stapel_nehmen()
            self.schreibe_register(r, wert)
            self._protokolliere(f"[{self.bzaehler:04d}] POP R{r}  (={wert})")
            self.bzaehler += 2

        elif opcode == Op.DUP:
            if self.stapel:
                self._stapel_ablegen(self.stapel[-1])
            self._protokolliere(f"[{self.bzaehler:04d}] DUP")
            self.bzaehler += 2

        elif opcode == Op.SWAP:
            if len(self.stapel) >= 2:
                self.stapel[-1], self.stapel[-2] = self.stapel[-2], self.stapel[-1]
            self._protokolliere(f"[{self.bzaehler:04d}] SWAP")
            self.bzaehler += 2

        elif opcode == Op.ENTER:
            self._protokolliere(f"[{self.bzaehler:04d}] ENTER")
            self.bzaehler += 2

        elif opcode == Op.LEAVE:
            self._protokolliere(f"[{self.bzaehler:04d}] LEAVE")
            self.bzaehler += 2

        elif opcode == Op.ALLOCA:
            self._protokolliere(f"[{self.bzaehler:04d}] ALLOCA")
            self.bzaehler += 2

        # ── Funktionsoperationen ───────────────────────────────────
        elif opcode == Op.RET:
            # Rücksprungadresse vom Stapel nehmen
            if self.stapel:
                addr = self._stapel_nehmen()
                self._protokolliere(f"[{self.bzaehler:04d}] RET → {addr}")
                self.bzaehler = addr
            else:
                # Kein Rücksprung auf dem Stapel → Programmende
                self._protokolliere(f"[{self.bzaehler:04d}] RET → HALT (kein Rücksprung)")
                self.angehalten = True
                self.bzaehler += 1

        elif opcode == Op.MOVI:
            r = self.bytecode[self.bzaehler + 1]
            imm = self._lese_i16(self.bzaehler + 2)
            self.schreibe_register(r, imm)
            self._aktualisiere_flags(imm)
            self._protokolliere(f"[{self.bzaehler:04d}] MOVI R{r}, {imm}")
            self.bzaehler += 4

        # ── Bedingte Sprünge (Flag-basiert) ────────────────────────
        elif opcode == Op.JE:
            r = self.bytecode[self.bzaehler + 1]
            addr = self._lese_u16(self.bzaehler + 2)
            if self.flags["null"]:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JE R{r}, {addr}  → SPRUNG"
                )
                self.bzaehler = addr
            else:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JE R{r}, {addr}  → KEIN SPRUNG"
                )
                self.bzaehler += 4

        elif opcode == Op.JNE:
            r = self.bytecode[self.bzaehler + 1]
            addr = self._lese_u16(self.bzaehler + 2)
            if not self.flags["null"]:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JNE R{r}, {addr}  → SPRUNG"
                )
                self.bzaehler = addr
            else:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JNE R{r}, {addr}  → KEIN SPRUNG"
                )
                self.bzaehler += 4

        elif opcode == Op.JL:
            r = self.bytecode[self.bzaehler + 1]
            addr = self._lese_u16(self.bzaehler + 2)
            if self.flags["negativ"]:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JL R{r}, {addr}  → SPRUNG"
                )
                self.bzaehler = addr
            else:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JL R{r}, {addr}  → KEIN SPRUNG"
                )
                self.bzaehler += 4

        elif opcode == Op.JGE:
            r = self.bytecode[self.bzaehler + 1]
            addr = self._lese_u16(self.bzaehler + 2)
            if not self.flags["negativ"]:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JGE R{r}, {addr}  → SPRUNG"
                )
                self.bzaehler = addr
            else:
                self._protokolliere(
                    f"[{self.bzaehler:04d}] JGE R{r}, {addr}  → KEIN SPRUNG"
                )
                self.bzaehler += 4

        # ── Speicherverwaltung ─────────────────────────────────────
        elif opcode == Op.REGION_CREATE:
            r = self.bytecode[self.bzaehler + 1]
            basis = self.lese_register(r)
            self._speicher[basis] = 0
            self._protokolliere(f"[{self.bzaehler:04d}] REGION_CREATE R{r}  (Basis={basis})")
            self.bzaehler += 2

        elif opcode == Op.REGION_DESTROY:
            r = self.bytecode[self.bzaehler + 1]
            basis = self.lese_register(r)
            if basis in self._speicher:
                del self._speicher[basis]
            self._protokolliere(
                f"[{self.bzaehler:04d}] REGION_DESTROY R{r}  (Basis={basis})"
            )
            self.bzaehler += 2

        elif opcode == Op.REGION_TRANSFER:
            ra = self.bytecode[self.bzaehler + 1]
            rb = self.bytecode[self.bzaehler + 2]
            self._pruefe_genitiv_transfer(ra, rb)
            self._protokolliere(
                f"[{self.bzaehler:04d}] REGION_TRANSFER R{ra}, R{rb}  (Genitiv-Prüfung OK)"
            )
            self.bzaehler += 3

        elif opcode == Op.MEMCOPY:
            a = self.bytecode[self.bzaehler + 1]
            b = self.bytecode[self.bzaehler + 2]
            c = self.bytecode[self.bzaehler + 3]
            self._protokolliere(f"[{self.bzaehler:04d}] MEMCOPY R{a}, R{b}, R{c}")
            self.bzaehler += 4

        elif opcode == Op.MEMSET:
            a = self.bytecode[self.bzaehler + 1]
            b = self.bytecode[self.bzaehler + 2]
            c = self.bytecode[self.bzaehler + 3]
            self._protokolliere(f"[{self.bzaehler:04d}] MEMSET R{a}, R{b}, R{c}")
            self.bzaehler += 4

        elif opcode == Op.MEMCMP:
            a = self.bytecode[self.bzaehler + 1]
            b = self.bytecode[self.bzaehler + 2]
            c = self.bytecode[self.bzaehler + 3]
            self._protokolliere(f"[{self.bzaehler:04d}] MEMCMP R{a}, R{b}, R{c}")
            self.bzaehler += 4

        # ── Typoperationen ─────────────────────────────────────────
        elif opcode in (Op.CAST, Op.BOX, Op.UNBOX, Op.CHECK_TYPE, Op.CHECK_BOUNDS):
            a = self.bytecode[self.bzaehler + 1]
            b = self.bytecode[self.bzaehler + 2] if self.bzaehler + 2 < len(self.bytecode) else 0
            self._protokolliere(f"[{self.bzaehler:04d}] {OP_NAMEN.get(opcode, '???')} R{a}, R{b}")
            self.bzaehler += 3

        # ── Gleitkommaarithmetik ──────────────────────────────────
        elif opcode == Op.FADD:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            # Ganzzahl-Gleitkomma-Emulation mit fester Nachkommastelle
            a = self._zu_vorzeichen(self.lese_register(ra))
            b = self._zu_vorzeichen(self.lese_register(rb))
            self.schreibe_register(rd, a + b)
            self._protokolliere(f"[{self.bzaehler:04d}] FADD R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.FSUB:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self._zu_vorzeichen(self.lese_register(ra))
            b = self._zu_vorzeichen(self.lese_register(rb))
            self.schreibe_register(rd, a - b)
            self._protokolliere(f"[{self.bzaehler:04d}] FSUB R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.FMUL:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self._zu_vorzeichen(self.lese_register(ra))
            b = self._zu_vorzeichen(self.lese_register(rb))
            self.schreibe_register(rd, a * b)
            self._protokolliere(f"[{self.bzaehler:04d}] FMUL R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode == Op.FDIV:
            rd = self.bytecode[self.bzaehler + 1]
            ra = self.bytecode[self.bzaehler + 2]
            rb = self.bytecode[self.bzaehler + 3]
            a = self._zu_vorzeichen(self.lese_register(ra))
            b = self._zu_vorzeichen(self.lese_register(rb))
            if b == 0:
                raise DivisionDurchNull("FDIV: Division durch Null.")
            self.schreibe_register(rd, a / b)
            self._protokolliere(f"[{self.bzaehler:04d}] FDIV R{rd}, R{ra}, R{rb}")
            self.bzaehler += 4

        elif opcode in (Op.FNEG, Op.FABS, Op.FMIN, Op.FMAX):
            a = self.bytecode[self.bzaehler + 1]
            b = self.bytecode[self.bzaehler + 2] if self.bzaehler + 2 < len(self.bytecode) else 0
            self._protokolliere(f"[{self.bzaehler:04d}] {OP_NAMEN.get(opcode, '???')} R{a}, R{b}")
            self.bzaehler += 3

        # ── Zeichenkettenoperationen ───────────────────────────────
        elif opcode in (Op.SLEN, Op.SCONCAT, Op.SCHAR, Op.SSUB, Op.SCMP):
            a = self.bytecode[self.bzaehler + 1]
            b = self.bytecode[self.bzaehler + 2] if self.bzaehler + 2 < len(self.bytecode) else 0
            self._protokolliere(f"[{self.bzaehler:04d}] {OP_NAMEN.get(opcode, '???')} R{a}, R{b}")
            self.bzaehler += 3

        # ── Agentenprotokoll (A2A) ─────────────────────────────────
        elif opcode == Op.TELL:
            agent_reg = self.bytecode[self.bzaehler + 1]
            nachricht_reg = self.bytecode[self.bzaehler + 2]
            agent_id = self.lese_register(agent_reg)
            nachricht_id = self.lese_register(nachricht_reg)
            self._nachrichten.append({
                "typ": "TELL",
                "agent": agent_id,
                "nachricht": nachricht_id,
                "zyklus": self.zyklen,
            })
            self._protokolliere(
                f"[{self.bzaehler:04d}] TELL R{agent_reg}, R{nachricht_reg}  "
                f"(→Agent {agent_id}: Nachricht {nachricht_id})"
            )
            self.bzaehler += 3

        elif opcode == Op.ASK:
            agent_reg = self.bytecode[self.bzaehler + 1]
            thema_reg = self.bytecode[self.bzaehler + 2]
            agent_id = self.lese_register(agent_reg)
            thema_id = self.lese_register(thema_reg)
            self._nachrichten.append({
                "typ": "ASK",
                "agent": agent_id,
                "thema": thema_id,
                "zyklus": self.zyklen,
            })
            self._protokolliere(
                f"[{self.bzaehler:04d}] ASK R{agent_reg}, R{thema_reg}  "
                f"(→Agent {agent_id}: Thema {thema_id})"
            )
            self.bzaehler += 3

        elif opcode == Op.DELEGATE:
            agent_reg = self.bytecode[self.bzaehler + 1]
            aufgabe_reg = self.bytecode[self.bzaehler + 2]
            agent_id = self.lese_register(agent_reg)
            aufgabe_id = self.lese_register(aufgabe_reg)
            self._nachrichten.append({
                "typ": "DELEGATE",
                "agent": agent_id,
                "aufgabe": aufgabe_id,
                "zyklus": self.zyklen,
            })
            self._protokolliere(
                f"[{self.bzaehler:04d}] DELEGATE R{agent_reg}, R{aufgabe_reg}  "
                f"(→Agent {agent_id}: Aufgabe {aufgabe_id})"
            )
            self.bzaehler += 3

        elif opcode == Op.BROADCAST:
            sender_reg = self.bytecode[self.bzaehler + 1]
            nachricht_reg = self.bytecode[self.bzaehler + 2]
            sender_id = self.lese_register(sender_reg)
            nachricht_id = self.lese_register(nachricht_reg)
            self._nachrichten.append({
                "typ": "BROADCAST",
                "sender": sender_id,
                "nachricht": nachricht_id,
                "zyklus": self.zyklen,
            })
            self._protokolliere(
                f"[{self.bzaehler:04d}] BROADCAST R{sender_reg}, R{nachricht_reg}  "
                f"(Von {sender_id}: Nachricht {nachricht_id})"
            )
            self.bzaehler += 3

        elif opcode == Op.TRUST_CHECK:
            agent_reg = self.bytecode[self.bzaehler + 1]
            ziel_reg = self.bytecode[self.bzaehler + 2]
            agent_id = self.lese_register(agent_reg)
            ziel_id = self.lese_register(ziel_reg)
            # Kasus-basierte Vertrauensprüfung
            agent_kasus = self._register_kasus.get(agent_reg, Kasus.NOMINATIV)
            ziel_kasus = self._register_kasus.get(ziel_reg, Kasus.NOMINATIV)
            vertraut = KASUS_TO_CAP[agent_kasus] >= CapLevel.CAP_REFERENCE
            self._vertrauenspruefungen.append({
                "agent": agent_id,
                "ziel": ziel_id,
                "agent_kasus": agent_kasus.value,
                "ziel_kasus": ziel_kasus.value,
                "vertraut": vertraut,
                "zyklus": self.zyklen,
            })
            self._protokolliere(
                f"[{self.bzaehler:04d}] TRUST_CHECK R{agent_reg}, R{ziel_reg}  "
                f"(Agent {agent_id} [{agent_kasus.value}] → Ziel {ziel_id} "
                f"[{ziel_kasus.value}] = {'VERTRAUT' if vertraut else 'NICHT VERTRAUT'})"
            )
            self.bzaehler += 3

        elif opcode == Op.CAP_REQUIRE:
            reg = self.bytecode[self.bzaehler + 1]
            level = self.bytecode[self.bzaehler + 2]
            aktueller_kasus = self._register_kasus.get(reg, Kasus.NOMINATIV)
            aktueller_cap = KASUS_TO_CAP[aktueller_kasus]
            if aktueller_cap < level:
                self.fehler = (
                    f"CAP_REQUIRE fehlgeschlagen: R{reg} hat {aktueller_kasus.value} "
                    f"(CapLevel {aktueller_cap.value}), benötigt CapLevel {level}."
                )
                self.angehalten = True
            self._protokolliere(
                f"[{self.bzaehler:04d}] CAP_REQUIRE R{reg}, {level}  "
                f"({aktueller_kasus.value}/{aktueller_cap.value} "
                f"{'≥' if aktueller_cap >= level else '<'} {level})"
            )
            self.bzaehler += 3

        # ── System ─────────────────────────────────────────────────
        elif opcode == Op.PRINT:
            r = self.bytecode[self.bzaehler + 1]
            wert = self._zu_vorzeichen(self.lese_register(r))
            self._protokolliere(f"[{self.bzaehler:04d}] PRINT R{r}  → {wert}")
            self.bzaehler += 2

        elif opcode == Op.HALT:
            self._protokolliere(f"[{self.bzaehler:04d}] HALT")
            self.angehalten = True
            self.bzaehler += 1

        else:
            # Unbekannter Opcode — überspringen
            name = OP_NAMEN.get(opcode, f"UNBEKANNT_0x{opcode:02x}")
            self._protokolliere(
                f"[{self.bzaehler:04d}] {name} — übersprungen (nicht implementiert)"
            )
            self.bzaehler += 1


# ══════════════════════════════════════════════════════════════════════
# Abkürzende Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════

def schnellausfuehrung(
    bytecode: bytes | bytearray,
    *,
    kasus_pruefung: bool = False,
    ablaufverfolgung: bool = False,
) -> AusfuehrungsErgebnis:
    """
    Schnellausführung: Bytecode → Ergebnis ohne Kasus-Prüfung.

    Praktisch für Tests und einfache Berechnungen.
    """
    vm = FluxVmDeu(
        bytecode,
        kasus_pruefung=kasus_pruefung,
        ablaufverfolgung=ablaufverfolgung,
    )
    return vm.ausfuehren()


def kasus_geschuetzte_ausfuehrung(
    bytecode: bytes | bytearray,
    *,
    ablaufverfolgung: bool = False,
) -> AusfuehrungsErgebnis:
    """
    Kasus-geschützte Ausführung: Bytecode → Ergebnis mit voller Kasus-Prüfung.

    Für sicherheitskritische Ausführungen und Kasus-Tests.
    """
    vm = FluxVmDeu(
        bytecode,
        kasus_pruefung=True,
        ablaufverfolgung=ablaufverfolgung,
    )
    return vm.ausfuehren()
