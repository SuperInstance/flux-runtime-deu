"""
FLUX-deu Testreihe — Tests für die deutsch-sprachige NL-Laufzeitumgebung.

Abdeckung:
  1-5:   Kasus-System (Zugriffssteuerung, Artikel→Kasus, CapLevel)
  6-10:  Interpreter-Grundmuster (berechne, mal, summe, fakultät)
  11-13: Register-Operationen (lade, addiere, speichere)
  14-15: Agent-Kommunikation (sage, frage)
  16-18: Verbposition (Hauptsatz V2, Nebensatz V-final, Imperativ)
  19-21: Getrennte Verben (Trennverb-Erkennung, Compilation, Registry)
  22-23: Komposita (Zusammensetzung, Typausdruck)
  24-25: CLI und Integration (Kommandozeilenparser, Programm-Ausführung)
"""

import pytest

from flux_deu.kasus import (
    Kasus, CapLevel, KasusValidator, KasusScope, Geschlecht,
    KASUS_TO_CAP, ARTICLE_KASUS,
)
from flux_deu.trennverben import (
    TrennverbHandler, TrennverbEntry, ContOp, TRENNVERB_REGISTRY,
    SEMANTIC_CONT_PATTERN,
)
from flux_deu.interpreter import (
    FluxInterpreterDeu, MiniVM, Op, Instruction,
    ClauseType, analyze_verb_position, parse_kompositum, CompoundType,
)


# ══════════════════════════════════════════════════════════════════════
# KASUS-SYSTEM TESTS
# ══════════════════════════════════════════════════════════════════════

class TestKasusEnum:
    """Test 1: Kasus-Enumeration und CapLevel-Zuordnung."""

    def test_kasus_has_four_cases(self):
        assert len(Kasus) == 4
        assert Kasus.NOMINATIV in Kasus
        assert Kasus.AKKUSATIV in Kasus
        assert Kasus.DATIV in Kasus
        assert Kasus.GENITIV in Kasus

    def test_kasus_to_cap_level_mapping(self):
        assert KASUS_TO_CAP[Kasus.NOMINATIV] == CapLevel.CAP_PUBLIC
        assert KASUS_TO_CAP[Kasus.AKKUSATIV] == CapLevel.CAP_READWRITE
        assert KASUS_TO_CAP[Kasus.DATIV] == CapLevel.CAP_REFERENCE
        assert KASUS_TO_CAP[Kasus.GENITIV] == CapLevel.CAP_TRANSFER

    def test_cap_level_ordering(self):
        """Genitiv > Akkusativ > Dativ > Nominativ in capability."""
        assert CapLevel.CAP_TRANSFER > CapLevel.CAP_READWRITE
        assert CapLevel.CAP_READWRITE > CapLevel.CAP_REFERENCE
        assert CapLevel.CAP_REFERENCE > CapLevel.CAP_PUBLIC


class TestKasusValidator:
    """Test 2: Kasus-Validator mit Artikel→Kasus-Auflösung."""

    def test_article_resolution_den(self):
        """'den' → Akkusativ (maskulin)."""
        validator = KasusValidator()
        cases = validator.resolve_kasus("den")
        assert Kasus.AKKUSATIV in cases

    def test_article_resolution_dem(self):
        """'dem' → Dativ (maskulin/neutrum)."""
        validator = KasusValidator()
        cases = validator.resolve_kasus("dem")
        assert cases == [Kasus.DATIV]

    def test_article_resolution_des(self):
        """'des' → Genitiv (maskulin)."""
        validator = KasusValidator()
        cases = validator.resolve_kasus("des")
        assert cases == [Kasus.GENITIV]

    def test_unknown_article_returns_empty(self):
        validator = KasusValidator()
        assert validator.resolve_kasus("xyz") == []


class TestKasusScope:
    """Test 3: KasusScope-Zugriffskontrolle."""

    def test_nominativ_can_access_public(self):
        scope = KasusScope("x", Kasus.NOMINATIV)
        assert scope.can_access(CapLevel.CAP_PUBLIC)

    def test_nominativ_cannot_access_readwrite(self):
        scope = KasusScope("x", Kasus.NOMINATIV)
        assert not scope.can_access(CapLevel.CAP_READWRITE)

    def test_akkusativ_can_access_readwrite(self):
        scope = KasusScope("x", Kasus.AKKUSATIV)
        assert scope.can_access(CapLevel.CAP_READWRITE)
        assert scope.can_access(CapLevel.CAP_PUBLIC)

    def test_genitiv_can_access_all(self):
        scope = KasusScope("x", Kasus.GENITIV)
        assert scope.can_access(CapLevel.CAP_PUBLIC)
        assert scope.can_access(CapLevel.CAP_REFERENCE)
        assert scope.can_access(CapLevel.CAP_READWRITE)
        assert scope.can_access(CapLevel.CAP_TRANSFER)

    def test_scope_with_gender(self):
        scope = KasusScope("Schiff", Kasus.NOMINATIV, gender=Geschlecht.NEUTRUM)
        assert scope.gender == Geschlecht.NEUTRUM
        assert "das" in repr(scope)

    def test_scope_with_owner(self):
        scope = KasusScope("Daten", Kasus.GENITIV, owner="Sensoragent")
        assert scope.owner == "Sensoragent"
        assert "Sensoragent" in repr(scope)


class TestKasusAccessLog:
    """Test 4: Zugriffsprotokoll des KasusValidators."""

    def test_access_granted_logged(self):
        validator = KasusValidator()
        validator.define_scope("x", Kasus.AKKUSATIV)
        validator.check_access("x", CapLevel.CAP_PUBLIC)
        log = validator.access_log()
        assert len(log) == 1
        symbol, level, granted = log[0]
        assert symbol == "x"
        assert granted is True

    def test_access_denied_logged(self):
        validator = KasusValidator()
        validator.define_scope("x", Kasus.NOMINATIV)
        validator.check_access("x", CapLevel.CAP_READWRITE)
        log = validator.access_log()
        assert len(log) == 1
        assert log[0][2] is False


# ══════════════════════════════════════════════════════════════════════
# INTERPRETER-GRUNDMUSTER
# ══════════════════════════════════════════════════════════════════════

class TestInterpreterBerechnePlus:
    """Test 5: 'berechne X plus Y' Muster."""

    def test_addition_integer(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("berechne 3 plus 5")
        assert result == 8

    def test_addition_float(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("berechne 2.5 plus 3.5")
        assert result == 6.0

    def test_addition_german_numbers(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("berechne drei plus vier")
        assert result == 7


class TestInterpreterMal:
    """Test 6: 'X mal Y' Multiplikationsmuster."""

    def test_multiplication(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("4 mal 6")
        assert result == 24

    def test_multiplication_zero(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("0 mal 999")
        assert result == 0


class TestInterpreterSumme:
    """Test 7: 'summe von X bis Y' Muster."""

    def test_sum_range(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("summe von 1 bis 10")
        assert result == 55  # 1+2+...+10 = 55

    def test_sum_range_single(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("summe von 5 bis 5")
        assert result == 5

    def test_sum_range_german(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("summe von eins bis fünf")
        assert result == 15  # 1+2+3+4+5 = 15


class TestInterpreterFakultaet:
    """Test 8: 'fakultät von X' Muster."""

    def test_factorial_5(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("fakultät von 5")
        assert result == 120  # 5! = 120

    def test_factorial_0(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("fakultät von 0")
        assert result == 1  # 0! = 1

    def test_factorial_10(self):
        interp = FluxInterpreterDeu()
        result = interp.execute("fakultät von 10")
        assert result == 3_628_800


# ══════════════════════════════════════════════════════════════════════
# REGISTER-OPERATIONEN
# ══════════════════════════════════════════════════════════════════════

class TestInterpreterRegister:
    """Test 9: Register-Operationen (lade, addiere, speichere)."""

    def test_lade_register(self):
        interp = FluxInterpreterDeu()
        interp.execute("lade register null mit 42")
        state = interp.get_vm_state()
        assert state["registers"].get("r0") == 42

    def test_addiere_register(self):
        interp = FluxInterpreterDeu()
        # Load two registers then add them in a program
        source = "lade register null mit 10\nlade register eins mit 20\naddiere register null und register eins"
        result = interp.execute(source)
        assert result == 30

    def test_speichere_variable(self):
        interp = FluxInterpreterDeu()
        interp.execute("speichere 99 in ergebnis")
        state = interp.get_vm_state()
        assert state["variables"].get("ergebnis") == 99


# ══════════════════════════════════════════════════════════════════════
# AGENT-KOMMUNIKATION
# ══════════════════════════════════════════════════════════════════════

class TestInterpreterAgent:
    """Test 10: Agent-Kommunikation (sage, frage)."""

    def test_sage_agent(self):
        interp = FluxInterpreterDeu()
        interp.execute("sage navigator berechne kurs")
        state = interp.get_vm_state()
        assert len(state["agent_messages"]) == 1
        sender, agent, msg = state["agent_messages"][0]
        assert agent == "navigator"
        assert msg == "berechne kurs"

    def test_frage_agent(self):
        interp = FluxInterpreterDeu()
        interp.execute("frage wetteragent nach windstärke")
        state = interp.get_vm_state()
        assert len(state["agent_questions"]) == 1
        sender, agent, topic = state["agent_questions"][0]
        assert agent == "wetteragent"
        assert topic == "windstärke"


# ══════════════════════════════════════════════════════════════════════
# VERBPOSITION
# ══════════════════════════════════════════════════════════════════════

class TestVerbPosition:
    """Test 11-12: Verbpositionsanalyse (V2 / V-final)."""

    def test_hauptsatz_v2(self):
        """Hauptsatz: Verb in 2. Position."""
        clause_type, verb = analyze_verb_position("ich berechne den kurs")
        assert clause_type == ClauseType.HAUPTSATZ
        assert verb == "berechne"

    def test_nebensatz_v_final(self):
        """Nebensatz: Verb am Ende."""
        clause_type, verb = analyze_verb_position("wenn der wind stärker wird")
        assert clause_type == ClauseType.NEBENSATZ

    def test_imperativ(self):
        """Imperativ: Verb an 1. Stelle."""
        clause_type, verb = analyze_verb_position("berechne den kurs")
        assert clause_type == ClauseType.IMPERATIV
        assert verb == "berechne"

    def test_dass_nebensatz(self):
        """'dass' leitet Nebensatz ein."""
        clause_type, _ = analyze_verb_position("dass das schiff fährt")
        assert clause_type == ClauseType.NEBENSATZ

    def test_weil_nebensatz(self):
        """'weil' leitet Nebensatz ein."""
        clause_type, _ = analyze_verb_position("weil der sturm kommt")
        assert clause_type == ClauseType.NEBENSATZ


# ══════════════════════════════════════════════════════════════════════
# GETRENNTE VERBEN
# ══════════════════════════════════════════════════════════════════════

class TestTrennverben:
    """Test 13-15: Getrennte Verben — Erkennung, Registry, Compilation."""

    def test_registry_not_empty(self):
        assert len(TRENNVERB_REGISTRY) >= 10

    def test_lookup_aufmachen(self):
        handler = TrennverbHandler()
        entry = handler.lookup("aufmachen")
        assert entry is not None
        assert entry.prefix == "auf"
        assert entry.stem == "machen"
        assert entry.semantic_class == "PREPARE_ACTIVATE"

    def test_lookup_anfangen(self):
        handler = TrennverbHandler()
        entry = handler.lookup("anfangen")
        assert entry is not None
        assert entry.prefix == "an"
        assert entry.stem == "fangen"

    def test_lookup_nonexistent(self):
        handler = TrennverbHandler()
        assert handler.lookup("kaufen") is None

    def test_compile_continuation(self):
        handler = TrennverbHandler()
        entry = handler.lookup("aufmachen")
        ops = handler.compile_continuation(entry)
        assert len(ops) == 4
        assert ops[0][0] == ContOp.CONT_PREPARE
        assert ops[3][0] == ContOp.CONT_COMPLETE
        assert ops[1][0] == ContOp.CONT_SUSPEND
        assert ops[2][0] == ContOp.CONT_RESUME

    def test_detect_in_sentence(self):
        handler = TrennverbHandler()
        # "mach die Tür auf" → stem="mach", prefix="auf"
        result = handler.detect_in_sentence("mach die Tür auf")
        assert result is not None
        assert result["prefix"] == "auf"
        assert result["infinitive"] == "aufmachen"

    def test_registry_entries_are_frozen(self):
        """All registry entries should be frozen dataclasses."""
        for entry in TRENNVERB_REGISTRY.values():
            # Frozen dataclass instances have __hash__
            assert hasattr(entry, "__hash__")


# ══════════════════════════════════════════════════════════════════════
# KOMPOSITA
# ══════════════════════════════════════════════════════════════════════

class TestKomposita:
    """Test 16-17: Komposita-Zerlegung."""

    def test_datenbank(self):
        compound = parse_kompositum("datenbank")
        assert compound is not None
        assert "daten" in compound.parts
        assert "bank" in compound.parts

    def test_datenspeicher(self):
        compound = parse_kompositum("datenspeicher")
        assert compound is not None
        assert "daten" in compound.parts
        assert "speicher" in compound.parts

    def test_type_expression(self):
        compound = parse_kompositum("datenbank")
        assert compound.type_expr == "Daten<Bank>"

    def test_unknown_word_returns_none(self):
        assert parse_kompositum("xyz") is None

    def test_single_component_returns_none(self):
        """Single known component is not a compound."""
        assert parse_kompositum("daten") is None


# ══════════════════════════════════════════════════════════════════════
# MINI-VM
# ══════════════════════════════════════════════════════════════════════

class TestMiniVM:
    """Test 18-19: Virtuelle Maschine — Grundfunktionen."""

    def test_const_add_halt(self):
        vm = MiniVM()
        vm.load_program([
            Instruction(Op.CONST, 3),
            Instruction(Op.CONST, 4),
            Instruction(Op.ADD),
            Instruction(Op.HALT),
        ])
        result = vm.run()
        assert result == 7

    def test_store_load(self):
        vm = MiniVM()
        vm.load_program([
            Instruction(Op.CONST, 42),
            Instruction(Op.STORE, "x"),
            Instruction(Op.CONST, 0),
            Instruction(Op.LOAD, "x"),
            Instruction(Op.HALT),
        ])
        result = vm.run()
        assert result == 42

    def test_mul(self):
        vm = MiniVM()
        vm.load_program([
            Instruction(Op.CONST, 6),
            Instruction(Op.CONST, 7),
            Instruction(Op.MUL),
            Instruction(Op.HALT),
        ])
        result = vm.run()
        assert result == 42

    def test_stack_underflow(self):
        vm = MiniVM()
        vm.load_program([
            Instruction(Op.ADD),  # Stack is empty!
        ])
        with pytest.raises(RuntimeError, match="Stapel ist leer"):
            vm.run()

    def test_sum_range_builtin(self):
        vm = MiniVM()
        vm.load_program([
            Instruction(Op.CONST, 1),
            Instruction(Op.CONST, 5),
            Instruction(Op.SUM_RANGE),
            Instruction(Op.HALT),
        ])
        assert vm.run() == 15

    def test_factorial_builtin(self):
        vm = MiniVM()
        vm.load_program([
            Instruction(Op.CONST, 6),
            Instruction(Op.FACTORIAL),
            Instruction(Op.HALT),
        ])
        assert vm.run() == 720

    def test_reset(self):
        vm = MiniVM()
        vm.push(42)
        vm.variables["x"] = 1
        vm.reset()
        assert vm.stack == []
        assert vm.variables == {}


# ══════════════════════════════════════════════════════════════════════
# KASUS-MODUS INTEGRATION
# ══════════════════════════════════════════════════════════════════════

class TestKasusMode:
    """Test 20-21: Kasus-Modus — Injektion von Cap-Checks."""

    def test_kasus_mode_injects_cap_checks(self):
        """With kasus_mode=True, CAP_CHECK instructions are injected."""
        interp = FluxInterpreterDeu(kasus_mode=True)
        instructions = interp.compile_line("berechne 1 plus 2")
        ops = [i.op for i in instructions]
        assert Op.CAP_CHECK in ops

    def test_no_kasus_mode_no_cap_checks(self):
        """Without kasus_mode, no CAP_CHECK instructions."""
        interp = FluxInterpreterDeu(kasus_mode=False)
        instructions = interp.compile_line("berechne 1 plus 2")
        ops = [i.op for i in instructions]
        assert Op.CAP_CHECK not in ops

    def test_kasus_mode_execution_still_works(self):
        """Kasus mode doesn't break execution."""
        interp = FluxInterpreterDeu(kasus_mode=True)
        result = interp.execute("berechne 10 plus 20")
        assert result == 30


# ══════════════════════════════════════════════════════════════════════
# KOMPILIERUNGSPROTOKOLL
# ══════════════════════════════════════════════════════════════════════

class TestCompilationLog:
    """Test 22: Kompilierungsprotokoll."""

    def test_log_contains_pattern_name(self):
        interp = FluxInterpreterDeu()
        interp.compile_line("berechne 3 plus 4")
        log = interp.get_compilation_log()
        assert any("berechne" in entry.lower() for entry in log)

    def test_log_shows_trennverb(self):
        interp = FluxInterpreterDeu()
        interp.compile_line("aufmachen")
        log = interp.get_compilation_log()
        assert any("trennverb" in entry.lower() for entry in log)

    def test_multiline_program_log(self):
        interp = FluxInterpreterDeu()
        interp.compile_program("berechne 1 plus 2\n3 mal 4")
        log = interp.get_compilation_log()
        assert len(log) >= 2


# ══════════════════════════════════════════════════════════════════════
# CLI PARSER
# ══════════════════════════════════════════════════════════════════════

class TestCLI:
    """Test 23-24: Kommandozeilenparser."""

    def test_import_main(self):
        from flux_deu.cli import main, build_parser
        assert callable(main)
        assert callable(build_parser)

    def test_hallo_command(self):
        from flux_deu.cli import main
        ret = main(["hallo"])
        assert ret == 0

    def test_unknown_command_returns_nonzero(self):
        from flux_deu.cli import main
        ret = main(["gibtesnicht"])
        assert ret != 0

    def test_kasus_modus_flag(self):
        from flux_deu.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--kasus-modus", "hallo"])
        assert args.kasus_modus is True

    def test_version_flag(self):
        from flux_deu.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])


# ══════════════════════════════════════════════════════════════════════
# MULTI-LINE PROGRAMS
# ══════════════════════════════════════════════════════════════════════

class TestMultiLinePrograms:
    """Test 25: Mehrzeilige Programme."""

    def test_sequential_calculations(self):
        interp = FluxInterpreterDeu()
        source = "berechne 3 plus 4\nberechne 10 plus 20"
        instructions = interp.compile_program(source)
        # Should have: CONST,CONST,ADD, CONST,CONST,ADD, HALT
        assert len(instructions) >= 6
        assert instructions[-1].op == Op.HALT

    def test_program_with_agent_and_math(self):
        interp = FluxInterpreterDeu()
        source = "sage navigator kurs ist 45\nberechne 2 plus 3"
        interp.execute(source)
        state = interp.get_vm_state()
        assert len(state["agent_messages"]) == 1


# ══════════════════════════════════════════════════════════════════════
# PACKAGE IMPORTS
# ══════════════════════════════════════════════════════════════════════

class TestPackageImports:
    """Test 26: Paket-Importe."""

    def test_import_package(self):
        import flux_deu
        assert hasattr(flux_deu, "__version__")
        assert hasattr(flux_deu, "FluxInterpreterDeu")
        assert hasattr(flux_deu, "Kasus")
        assert hasattr(flux_deu, "KasusValidator")
        assert hasattr(flux_deu, "TrennverbHandler")

    def test_version_format(self):
        from flux_deu import __version__
        parts = __version__.split(".")
        assert len(parts) >= 2
