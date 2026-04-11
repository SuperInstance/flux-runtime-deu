"""
FLUX-deu Kommandozeile — Deutsch-sprachige CLI.

Befehle:
    hallo          — Begrüßung und Statusanzeige
    kompilieren    — Quelldatei kompilieren
    ausführen      — Programm ausführen
    öffnen         — Interaktive Sitzung (REPL)
    zerlegen       — Kasus/Zerlegungsanalyse anzeigen

Flags:
    --kasus-modus  — Kasus-basierte Zugriffssteuerung aktivieren
    --detailliert  — Detaillierte Kompilierungsprotokolle anzeigen
    --datei PATH   — Quelldatei angeben
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from flux_deu import __version__
from flux_deu.interpreter import (
    FluxInterpreterDeu, ClauseType, analyze_verb_position, parse_kompositum
)
from flux_deu.kasus import Kasus, CapLevel, KasusValidator, Geschlecht


# ── Banner ─────────────────────────────────────────────────────────────

BANNER = """\
╔══════════════════════════════════════════════════════════╗
║  FLUX · Fluide Sprache Universelle Ausführung           ║
║  Deutsch-zuerst NL-Laufzeitumgebung                     ║
║  Version {version:<44s}║
╚══════════════════════════════════════════════════════════╝
"""

SEPARATOR = "─" * 58


# ── Command handlers ───────────────────────────────────────────────────

def cmd_hallo(args):
    """Begrüßung anzeigen."""
    print(BANNER.format(version=__version__))
    print(f"  Kasus-Modus: {'AKTIV' if args.kasus_modus else 'inaktiv'}")
    print(f"  Detailliert: {'ja' if args.detailliert else 'nein'}")
    print(SEPARATOR)
    print("  Bereit. Geben Sie einen deutschen Befehl ein,")
    print("  oder verwenden Sie 'öffnen' für die interaktive Sitzung.")
    print(SEPARATOR)
    return 0


def cmd_kompilieren(args):
    """Quelldatei kompilieren (ohne Ausführung)."""
    print(BANNER.format(version=__version__))

    datei = args.datei
    if not datei:
        datei = input("  Quelldatei: ").strip()

    path = Path(datei)
    if not path.exists():
        print(f"  ✗ Fehler: Datei '{datei}' nicht gefunden.")
        return 1

    source = path.read_text(encoding="utf-8")
    interp = FluxInterpreterDeu(kasus_mode=args.kasus_modus)

    print(f"  Kompiliere: {path}")
    print(SEPARATOR)

    instructions = interp.compile_program(source)

    for i, instr in enumerate(instructions):
        line_info = f"  [{i:03d}] {instr}"
        if args.detailliert and instr.source_line:
            line_info += f"  ← {instr.source_line}"
        print(line_info)

    print(SEPARATOR)
    print(f"  {len(instructions)} Anweisungen erzeugt.")

    if args.detailliert:
        print(SEPARATOR)
        print("  Kompilierungsprotokoll:")
        for log_entry in interp.get_compilation_log():
            print(f"    {log_entry}")

    return 0


def cmd_ausfuehren(args):
    """Programm kompilieren und ausführen."""
    print(BANNER.format(version=__version__))

    datei = args.datei
    if not datei:
        # Read from stdin or prompt
        if not sys.stdin.isatty():
            source = sys.stdin.read()
        else:
            print("  Programm eingeben (leere Zeile zum Beenden):")
            lines = []
            while True:
                try:
                    line = input("  > ")
                    if not line:
                        break
                    lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    break
            source = "\n".join(lines)
    else:
        path = Path(datei)
        if not path.exists():
            print(f"  ✗ Fehler: Datei '{datei}' nicht gefunden.")
            return 1
        source = path.read_text(encoding="utf-8")

    interp = FluxInterpreterDeu(kasus_mode=args.kasus_modus)

    print(SEPARATOR)
    result = interp.execute(source)

    if args.detailliert:
        state = interp.get_vm_state()
        print(SEPARATOR)
        print("  VM-Zustand nach Ausführung:")
        print(f"    Stapel (Stack):   {state['stack']}")
        print(f"    Variablen:        {state['variables']}")
        print(f"    Register:         {state['registers']}")
        print(f"    Agent-Nachrichten: {state['agent_messages']}")
        print(f"    Agent-Fragen:     {state['agent_questions']}")
        print(f"    Verzögert:        {state['deferred_count']} Anweisungen")
        print(SEPARATOR)

        print("  Kompilierungsprotokoll:")
        for entry in interp.get_compilation_log():
            print(f"    {entry}")

    print(SEPARATOR)
    if result is not None:
        print(f"  Ergebnis: {result}")
    print("  ✓ Ausführung beendet.")
    return 0


def cmd_oeffnen(args):
    """Interaktive REPL-Sitzung (öffnen)."""
    print(BANNER.format(version=__version__))
    print(f"  Kasus-Modus: {'AKTIV' if args.kasus_modus else 'inaktiv'}")
    print(SEPARATOR)
    print("  Interaktive Sitzung. Befehle:")
    print("    berechne X plus Y    — Addition")
    print("    X mal Y              — Multiplikation")
    print("    summe von X bis Y    — Summenbereich")
    print("    fakultät von X       — Fakultät")
    print("    lade register N mit V — Register laden")
    print("    sage A M             — Agent Nachricht senden")
    print("    frage A nach T       — Agent Frage stellen")
    print("    speichere V in N     — Variable speichern")
    print("    zeige N              — Wert anzeigen")
    print("    zerlege WORT         — Kasus-/Kompositum-Analyse")
    print("    hilfe                — Diese Hilfe anzeigen")
    print("    beenden              — Sitzung beenden")
    print(SEPARATOR)

    interp = FluxInterpreterDeu(kasus_mode=args.kasus_modus)

    while True:
        try:
            line = input("  flux> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Auf Wiedersehen!")
            break

        if not line:
            continue

        cmd_lower = line.lower()

        if cmd_lower in ("beenden", "exit", "quit", "ende", "tschüss"):
            print("  Auf Wiedersehen!")
            break

        if cmd_lower == "hilfe" or cmd_lower == "help":
            print("  Befehle: berechne, mal, summe, fakultät, lade,")
            print("  addiere, sage, frage, speichere, zeige, zerlege, beenden")
            continue

        if cmd_lower.startswith("zerlege "):
            word = line[8:].strip()
            _analyze_word(word, interp, args.detailliert)
            continue

        try:
            result = interp.execute_line(line)
            if result is not None:
                print(f"  ← {result}")

            if args.detailliert:
                for entry in interp.get_compilation_log():
                    print(f"    {entry}")
        except Exception as e:
            print(f"  ✗ Fehler: {e}")

    return 0


def cmd_zerlegen(args):
    """Kasus- und Zerlegungsanalyse für ein Wort/Satz."""
    print(BANNER.format(version=__version__))

    satz = args.satz
    if not satz:
        satz = input("  Satz oder Wort: ").strip()

    interp = FluxInterpreterDeu(kasus_mode=args.kasus_modus)
    _analyze_word(satz, interp, args.detailliert)
    return 0


def _analyze_word(text: str, interp: FluxInterpreterDeu, detailliert: bool):
    """Analyze a word/sentence for Kasus, Verb position, and Komposita."""
    print(SEPARATOR)
    print(f"  Analyse: '{text}'")
    print(SEPARATOR)

    # Verb position
    clause_type, verb = analyze_verb_position(text)
    print(f"  Satzart:     {clause_type.value}")
    if verb:
        print(f"  Verb:        {verb}")
        print(f"  Position:    {'2. Stelle (V2)' if clause_type == ClauseType.HAUPTSATZ else 'Endposition (V-final)' if clause_type == ClauseType.NEBENSATZ else '1. Stelle (Imperativ)'}")

    # Kasus analysis (from articles)
    validator = KasusValidator()
    words = text.split()
    articles_found = {}
    for word in words:
        cases = validator.resolve_kasus(word)
        if cases:
            articles_found[word] = cases
    if articles_found:
        print(f"  Artikel:")
        for article, cases in articles_found.items():
            case_names = ", ".join(c.value for c in cases)
            cap_names = ", ".join(Kasus.kasus_to_cap if hasattr(Kasus, 'kasus_to_cap') else "")
            print(f"    '{article}' → {case_names}")

    # Kompositum analysis
    compound = parse_kompositum(text)
    if compound:
        print(f"  Kompositum:")
        print(f"    Wort:     {compound.full_word}")
        print(f"    Teile:    {compound.parts}")
        print(f"    Typ:      {compound.type_expr}")
    else:
        # Try each word
        for word in words:
            c = parse_kompositum(word)
            if c:
                print(f"  Kompositum in '{c.full_word}': {c.parts} → {c.type_expr}")

    # Trennverb check
    detection = interp.trennverb_handler.detect_in_sentence(text)
    if detection:
        entry = detection["entry"]
        print(f"  Trennverb:")
        print(f"    Infinitiv:    {entry.infinitive}")
        print(f"    Präfix:       {entry.prefix}")
        print(f"    Stamm:        {entry.stem}")
        print(f"    Semantik:     {entry.semantic_class}")
        print(f"    Bedeutung:    {entry.description_de}")

    # Try to compile
    if detailliert:
        print(SEPARATOR)
        print("  Kompilierungsversuch:")
        instructions = interp.compile_line(text)
        for i, instr in enumerate(instructions):
            print(f"    [{i:03d}] {instr}")

    print(SEPARATOR)


# ── Argument parser ────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flux-deu",
        description="FLUX — Fluide Sprache Universelle Ausführung. Deutsch-zuerst NL-Laufzeitumgebung.",
    )

    parser.add_argument(
        "--kasus-modus",
        action="store_true",
        default=False,
        help="Kasus-basierte Zugriffssteuerung aktivieren",
    )
    parser.add_argument(
        "--detailliert",
        action="store_true",
        default=False,
        help="Detaillierte Ausgabe und Kompilierungsprotokolle",
    )
    parser.add_argument(
        "--datei",
        type=str,
        default=None,
        help="Quelldatei (.flux oder .txt)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="befehl", help="Verfügbarer Befehl")

    # hallo
    subparsers.add_parser("hallo", help="Begrüßung und Status")

    # kompilieren
    p_komp = subparsers.add_parser("kompilieren", help="Quelldatei kompilieren")
    p_komp.add_argument("--datei", type=str, default=None)

    # ausführen
    p_ausf = subparsers.add_parser("ausführen", help="Programm ausführen")
    p_ausf.add_argument("--datei", type=str, default=None)

    # öffnen
    subparsers.add_parser("öffnen", help="Interaktive Sitzung starten")

    # zerlegen
    p_zerl = subparsers.add_parser("zerlegen", help="Analyse anzeigen")
    p_zerl.add_argument("satz", nargs="?", default=None, help="Satz oder Wort")

    return parser


# ── Entry point ────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    """Haupteinstiegspunkt der FLUX-deu Kommandozeile."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if e.code is not None else 1

    # Default: show banner if no command
    if args.befehl is None:
        cmd_hallo(args)
        return 0

    dispatch = {
        "hallo": cmd_hallo,
        "kompilieren": cmd_kompilieren,
        "ausführen": cmd_ausfuehren,
        "öffnen": cmd_oeffnen,
        "zerlegen": cmd_zerlegen,
    }

    handler = dispatch.get(args.befehl)
    if handler is None:
        print(f"  ✗ Unbekannter Befehl: {args.befehl}")
        print("  Verfügbare Befehle: hallo, kompilieren, ausführen, öffnen, zerlegen")
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
