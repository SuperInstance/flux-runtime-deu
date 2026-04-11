"""
FLUX-deu Interpreter — Deutsch-sprachige NL-Mustererkennung und -übersetzung.

Compiles German natural language patterns into FLUX VM bytecodes.

Supported patterns:
    berechne $a plus $b           → compute a + b
    $a mal $b                     → multiply
    summe von $a bis $b           → sum from a to b
    fakultät von $a               → factorial
    lade register null mit $val   → load register
    addiere register null und register eins → add registers
    sage $agent $nachricht        → tell agent message
    frage $agent nach $thema      → ask agent topic

Case-scope enforcement (Kasus):
    der Nominativ → CAP_PUBLIC
    den Akkusativ → CAP_READWRITE
    dem Dativ     → CAP_REFERENCE
    des Genitiv   → CAP_TRANSFER

Verb position compilation:
    Hauptsatz (V2):    verb in 2nd position → sequential execution
    Nebensatz (V-final): verb at end → deferred/lazy execution
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from flux_deu.kasus import (
    Kasus, CapLevel, KasusValidator, Geschlecht, KASUS_TO_CAP
)
from flux_deu.trennverben import TrennverbHandler, ContOp


# ── Mini-VM Bytecode (embedded, language-agnostic core) ───────────────

class Op(Enum):
    """Core FLUX VM bytecodes."""
    NOP = auto()
    CONST = auto()        # push constant
    LOAD = auto()         # load variable
    STORE = auto()        # store variable
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    JMP = auto()          # unconditional jump
    JZ = auto()           # jump if zero
    CALL = auto()         # call function
    RET = auto()          # return
    TELL = auto()         # agent→agent message
    ASK = auto()          # agent question
    SUM_RANGE = auto()    # sum from a to b
    FACTORIAL = auto()    # factorial
    HALT = auto()
    # Continuation ops (from Trennverben)
    CONT_PREPARE = auto()
    CONT_COMPLETE = auto()
    CONT_SUSPEND = auto()
    CONT_RESUME = auto()
    # Scope/capability ops (from Kasus)
    CAP_CHECK = auto()
    SCOPE_PUSH = auto()
    SCOPE_POP = auto()
    # Deferred execution (V-final)
    DEFER = auto()
    EXECUTE_DEFERRED = auto()


@dataclass
class Instruction:
    """A single VM instruction."""
    op: Op
    arg: Any = None
    source_line: str = ""

    def __repr__(self):
        if self.arg is not None:
            return f"{self.op.name} {self.arg!r}"
        return self.op.name


# ── Mini-VM execution engine ──────────────────────────────────────────

class MiniVM:
    """
    Lightweight FLUX virtual machine for executing compiled bytecodes.

    This is the language-agnostic execution core. The German NL layer
    compiles INTO this VM's instruction set.
    """

    def __init__(self):
        self.stack: List[Any] = []
        self.registers: Dict[str, Any] = {}
        self.variables: Dict[str, Any] = {}
        self.program: List[Instruction] = []
        self.pc: int = 0
        self.deferred: List[Instruction] = []
        self.agent_messages: List[Tuple[str, str, str]] = []  # (from, to, msg)
        self.agent_questions: List[Tuple[str, str, str]] = []

    def load_program(self, instructions: List[Instruction]):
        self.program = instructions
        self.pc = 0

    def push(self, value: Any):
        self.stack.append(value)

    def pop(self) -> Any:
        if not self.stack:
            raise RuntimeError("VM-Fehler: Stapel ist leer (stack underflow)")
        return self.stack.pop()

    def run(self) -> Any:
        """Execute loaded program until HALT or end."""
        max_steps = 100_000
        steps = 0
        while self.pc < len(self.program) and steps < max_steps:
            instr = self.program[self.pc]
            self._exec(instr)
            steps += 1
            if instr.op == Op.HALT:
                break
        return self.stack[-1] if self.stack else None

    def _exec(self, instr: Instruction):
        op = instr.op

        if op == Op.NOP:
            self.pc += 1

        elif op == Op.CONST:
            self.push(instr.arg)
            self.pc += 1

        elif op == Op.LOAD:
            name = instr.arg
            if name in self.variables:
                self.push(self.variables[name])
            elif name in self.registers:
                self.push(self.registers[name])
            else:
                raise RuntimeError(f"VM-Fehler: Unbekannter Name '{name}'")
            self.pc += 1

        elif op == Op.STORE:
            val = self.pop()
            name = instr.arg
            if name.startswith("r") and name[1:].isdigit():
                self.registers[name] = val
            else:
                self.variables[name] = val
            self.pc += 1

        elif op == Op.ADD:
            b, a = self.pop(), self.pop()
            self.push(a + b)
            self.pc += 1

        elif op == Op.SUB:
            b, a = self.pop(), self.pop()
            self.push(a - b)
            self.pc += 1

        elif op == Op.MUL:
            b, a = self.pop(), self.pop()
            self.push(a * b)
            self.pc += 1

        elif op == Op.DIV:
            b, a = self.pop(), self.pop()
            self.push(a / b)
            self.pc += 1

        elif op == Op.MOD:
            b, a = self.pop(), self.pop()
            self.push(a % b)
            self.pc += 1

        elif op == Op.JMP:
            self.pc = instr.arg

        elif op == Op.JZ:
            val = self.pop()
            if val == 0:
                self.pc = instr.arg
            else:
                self.pc += 1

        elif op == Op.CALL:
            # Simple built-in dispatch
            fname = instr.arg
            if fname == "sum_range":
                end, start = self.pop(), self.pop()
                self.push(sum(range(start, end + 1)))
            elif fname == "factorial":
                n = self.pop()
                result = 1
                for i in range(2, int(n) + 1):
                    result *= i
                self.push(result)
            else:
                raise RuntimeError(f"VM-Fehler: Unbekannte Funktion '{fname}'")
            self.pc += 1

        elif op == Op.RET:
            self.pc += 1

        elif op == Op.SUM_RANGE:
            end, start = self.pop(), self.pop()
            self.push(sum(range(start, end + 1)))
            self.pc += 1

        elif op == Op.FACTORIAL:
            n = self.pop()
            result = 1
            for i in range(2, int(n) + 1):
                result *= i
            self.push(result)
            self.pc += 1

        elif op == Op.TELL:
            msg = self.pop()
            agent = self.pop()
            sender = self.pop() if self.stack else "system"
            self.agent_messages.append((sender, agent, msg))
            self.pc += 1

        elif op == Op.ASK:
            topic = self.pop()
            agent = self.pop()
            sender = self.pop() if self.stack else "system"
            self.agent_questions.append((sender, agent, topic))
            self.pc += 1

        elif op == Op.DEFER:
            self.deferred.append(instr)
            self.pc += 1

        elif op == Op.EXECUTE_DEFERRED:
            for d_instr in self.deferred:
                self._exec(d_instr)
            self.deferred.clear()
            self.pc += 1

        elif op == Op.CAP_CHECK:
            # Kasus-based capability check (symbolic)
            # In real VM this would query the KasusValidator
            self.pc += 1

        elif op == Op.SCOPE_PUSH:
            self.pc += 1

        elif op == Op.SCOPE_POP:
            self.pc += 1

        elif op in (Op.CONT_PREPARE, Op.CONT_COMPLETE):
            # Continuation ops — track state
            self.pc += 1

        elif op == Op.CONT_SUSPEND:
            self.pc += 1

        elif op == Op.CONT_RESUME:
            self.pc += 1

        elif op == Op.HALT:
            self.pc += 1

        else:
            raise RuntimeError(f"VM-Fehler: Unbekannter Opcode {op}")

    def reset(self):
        self.stack.clear()
        self.registers.clear()
        self.variables.clear()
        self.program.clear()
        self.pc = 0
        self.deferred.clear()
        self.agent_messages.clear()
        self.agent_questions.clear()


# ── Verb position analysis ────────────────────────────────────────────

class ClauseType(Enum):
    """German clause types based on verb position."""
    HAUPTSATZ = "Hauptsatz"        # V2 — verb in 2nd position → sequential
    NEBENSATZ = "Nebensatz"        # V-final — verb at end → deferred
    IMPERATIV = "Imperativ"        # verb-first → immediate


def analyze_verb_position(sentence: str) -> Tuple[ClauseType, Optional[str]]:
    """
    Analyze verb position in a German sentence.

    Returns (ClauseType, detected_verb_or_None).
    """
    words = sentence.strip().split()
    if not words:
        return (ClauseType.HAUPTSATZ, None)

    # Known German verbs (simplified for pattern matching)
    verbs = {
        "berechne", "addiere", "subtrahiere", "multipliziere", "dividiere",
        "lade", "speichere", "sage", "frage", "gib", "zeige", "öffne",
        "schließe", "starte", "stoppe", "prüfe", "wenn", "dass", "ob",
        "summe", "fakultät", "hilfe",
    }

    first_word = words[0].lower().rstrip(".,!?")
    last_word = words[-1].lower().rstrip(".,!?")

    # Check for subordinate conjunctions → Nebensatz
    sub_conjunctions = {"wenn", "dass", "ob", "weil", "da", "falls",
                        "sobald", "bevor", "nachdem", "obwohl", "während"}
    if first_word in sub_conjunctions:
        return (ClauseType.NEBENSATZ, last_word if last_word in verbs else None)

    # Verb in first position → Imperativ
    if first_word in verbs:
        return (ClauseType.IMPERATIV, first_word)

    # Check V2: 2nd position has verb
    if len(words) >= 2:
        second_word = words[1].lower().rstrip(".,!?")
        if second_word in verbs:
            return (ClauseType.HAUPTSATZ, second_word)

    # Check V-final: last position has verb
    if last_word in verbs:
        return (ClauseType.NEBENSATZ, last_word)

    return (ClauseType.HAUPTSATZ, None)


# ── Komposita (compound word) parser ──────────────────────────────────

@dataclass
class CompoundType:
    """A decomposed German compound word as type composition."""
    full_word: str
    parts: List[str]
    type_expr: str  # e.g., "Daten<Bank<Speicher>>"


def parse_kompositum(word: str) -> Optional[CompoundType]:
    """
    Attempt to decompose a German compound word into parts.

    Simple heuristic: try splitting at known component boundaries.
    E.g., "Datenbank" → ["Daten", "bank"]
          "Flusslaufzeit" → ["Fluss", "lauf", "zeit"]
    """
    known_components = [
        "daten", "bank", "speicher", "zeit", "lauf", "fluss", "netz",
        "werk", "zeug", "raum", "stelle", "plan", "buch", "karte",
        "tabelle", "liste", "baum", "knoten", "feld", "wert",
        "matrix", "vektor", "tensor", "netzwerk", "system",
    ]

    word_lower = word.lower()
    remaining = word_lower
    parts = []

    # Greedy left-to-right decomposition
    while remaining:
        found = False
        for comp in sorted(known_components, key=len, reverse=True):
            if remaining.startswith(comp):
                parts.append(comp)
                remaining = remaining[len(comp):]
                found = True
                break
        if not found:
            # Add remainder as a part
            if remaining:
                parts.append(remaining)
            break

    if len(parts) >= 2:
        type_expr = "<".join(p.capitalize() for p in parts) + ">" * (len(parts) - 1)
        return CompoundType(full_word=word, parts=parts, type_expr=type_expr)

    return None


# ── German NL pattern rules ───────────────────────────────────────────

@dataclass
class PatternRule:
    """A compiled NL pattern rule."""
    name: str
    pattern: re.Pattern
    handler: Callable
    description: str


# ── Main Interpreter ──────────────────────────────────────────────────

class FluxInterpreterDeu:
    """
    German-first FLUX interpreter.

    Compiles German natural language into VM bytecodes and executes them.
    Integrates Kasus scope checking, verb-position analysis, and
    Trennverb continuation patterns.
    """

    # German word → register name mapping
    REGISTER_MAP = {
        "null": 0, "eins": 1, "zwei": 2, "drei": 3,
        "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7,
        "acht": 8, "neun": 9, "zehn": 10,
    }

    def __init__(self, kasus_mode: bool = False):
        self.vm = MiniVM()
        self.kasus_validator = KasusValidator()
        self.trennverb_handler = TrennverbHandler()
        self.kasus_mode = kasus_mode
        self.compilation_log: List[str] = []
        self._patterns: List[PatternRule] = []
        self._register_patterns()

    def _register_patterns(self):
        """Register all German NL pattern rules."""

        # berechne $a plus $b
        self._patterns.append(PatternRule(
            name="berechne_plus",
            pattern=re.compile(
                r"berechne\s+(.+?)\s+plus\s+(.+)",
                re.IGNORECASE
            ),
            handler=self._handle_berechne_plus,
            description="berechne X plus Y → addiere",
        ))

        # $a mal $b (multiplication)
        self._patterns.append(PatternRule(
            name="multipliziere_mal",
            pattern=re.compile(
                r"(\S+)\s+mal\s+(\S+)",
                re.IGNORECASE
            ),
            handler=self._handle_multipliziere_mal,
            description="X mal Y → multipliziere",
        ))

        # summe von $a bis $b
        self._patterns.append(PatternRule(
            name="summe_von_bis",
            pattern=re.compile(
                r"summe\s+von\s+(\S+)\s+bis\s+(\S+)",
                re.IGNORECASE
            ),
            handler=self._handle_summe_von_bis,
            description="summe von X bis Y → Summenbereich",
        ))

        # fakultät von $a
        self._patterns.append(PatternRule(
            name="fakultaet",
            pattern=re.compile(
                r"fakultät\s+von\s+(\S+)",
                re.IGNORECASE
            ),
            handler=self._handle_fakultaet,
            description="fakultät von X → Fakultätsberechnung",
        ))

        # lade register $name mit $val
        self._patterns.append(PatternRule(
            name="lade_register",
            pattern=re.compile(
                r"lade\s+register\s+(\S+)\s+mit\s+(.+)",
                re.IGNORECASE
            ),
            handler=self._handle_lade_register,
            description="lade register X mit Y → Register laden",
        ))

        # addiere register $a und register $b
        self._patterns.append(PatternRule(
            name="addiere_register",
            pattern=re.compile(
                r"addiere\s+register\s+(\S+)\s+und\s+register\s+(\S+)",
                re.IGNORECASE
            ),
            handler=self._handle_addiere_register,
            description="addiere register X und register Y → Register addieren",
        ))

        # sage $agent $nachricht
        self._patterns.append(PatternRule(
            name="sage_agent",
            pattern=re.compile(
                r"sage\s+(\S+)\s+(.+)",
                re.IGNORECASE
            ),
            handler=self._handle_sage_agent,
            description="sage X Y → Agent-Nachricht senden",
        ))

        # frage $agent nach $thema
        self._patterns.append(PatternRule(
            name="frage_agent",
            pattern=re.compile(
                r"frage\s+(\S+)\s+nach\s+(.+)",
                re.IGNORECASE
            ),
            handler=self._handle_frage_agent,
            description="frage X nach Y → Agent-Frage stellen",
        ))

        # speichere $val in $name
        self._patterns.append(PatternRule(
            name="speichere_in",
            pattern=re.compile(
                r"speichere\s+(.+?)\s+in\s+(\S+)",
                re.IGNORECASE
            ),
            handler=self._handle_speichere,
            description="speichere X in Y → Variable speichern",
        ))

        # zeige $name
        self._patterns.append(PatternRule(
            name="zeige",
            pattern=re.compile(
                r"zeige\s+(.+)",
                re.IGNORECASE
            ),
            handler=self._handle_zeige,
            description="zeige X → Wert anzeigen",
        ))

    # ── Value resolution ──────────────────────────────────────────────

    def _resolve_value(self, token: str) -> Any:
        """Resolve a token to a numeric value or variable reference."""
        token = token.strip().rstrip(".,!?")

        # Try integer
        try:
            return int(token)
        except ValueError:
            pass

        # Try float
        try:
            return float(token)
        except ValueError:
            pass

        # Try German number words
        german_numbers = {
            "null": 0, "eins": 1, "zwei": 2, "drei": 3,
            "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7,
            "acht": 8, "neun": 9, "zehn": 10, "elf": 11,
            "zwölf": 12, "hundert": 100, "tausend": 1000,
        }
        if token.lower() in german_numbers:
            return german_numbers[token.lower()]

        # Variable reference — look up in VM
        if token in self.vm.variables:
            return self.vm.variables[token]

        # Register reference
        reg_name = f"r_{token.lower()}"
        if token.lower() in self.REGISTER_MAP:
            reg_idx = self.REGISTER_MAP[token.lower()]
            reg_name = f"r{reg_idx}"
            if reg_name in self.vm.registers:
                return self.vm.registers[reg_name]

        return token  # Return as string

    def _resolve_register_name(self, name: str) -> str:
        """Resolve German register name to internal name."""
        name_lower = name.strip().lower()
        if name_lower in self.REGISTER_MAP:
            return f"r{self.REGISTER_MAP[name_lower]}"
        return f"r_{name_lower}"

    # ── Pattern handlers ──────────────────────────────────────────────

    def _handle_berechne_plus(self, match) -> List[Instruction]:
        a_token, b_token = match.group(1), match.group(2)
        a = self._resolve_value(a_token)
        b = self._resolve_value(b_token)
        return [
            Instruction(Op.CONST, a, f"berechne {a_token} plus {b_token}"),
            Instruction(Op.CONST, b),
            Instruction(Op.ADD),
        ]

    def _handle_multipliziere_mal(self, match) -> List[Instruction]:
        a_token, b_token = match.group(1), match.group(2)
        a = self._resolve_value(a_token)
        b = self._resolve_value(b_token)
        return [
            Instruction(Op.CONST, a, f"{a_token} mal {b_token}"),
            Instruction(Op.CONST, b),
            Instruction(Op.MUL),
        ]

    def _handle_summe_von_bis(self, match) -> List[Instruction]:
        a_token, b_token = match.group(1), match.group(2)
        a = self._resolve_value(a_token)
        b = self._resolve_value(b_token)
        return [
            Instruction(Op.CONST, a, f"summe von {a_token} bis {b_token}"),
            Instruction(Op.CONST, b),
            Instruction(Op.SUM_RANGE),
        ]

    def _handle_fakultaet(self, match) -> List[Instruction]:
        a_token = match.group(1)
        a = self._resolve_value(a_token)
        return [
            Instruction(Op.CONST, a, f"fakultät von {a_token}"),
            Instruction(Op.FACTORIAL),
        ]

    def _handle_lade_register(self, match) -> List[Instruction]:
        reg_token, val_token = match.group(1), match.group(2)
        reg_name = self._resolve_register_name(reg_token)
        val = self._resolve_value(val_token)
        return [
            Instruction(Op.CONST, val, f"lade register {reg_token} mit {val_token}"),
            Instruction(Op.STORE, reg_name),
        ]

    def _handle_addiere_register(self, match) -> List[Instruction]:
        a_token, b_token = match.group(1), match.group(2)
        reg_a = self._resolve_register_name(a_token)
        reg_b = self._resolve_register_name(b_token)
        return [
            Instruction(Op.LOAD, reg_a, f"addiere register {a_token} und register {b_token}"),
            Instruction(Op.LOAD, reg_b),
            Instruction(Op.ADD),
        ]

    def _handle_sage_agent(self, match) -> List[Instruction]:
        agent, nachricht = match.group(1), match.group(2).strip()
        return [
            Instruction(Op.CONST, "system", f"sage {agent} {nachricht}"),
            Instruction(Op.CONST, agent),
            Instruction(Op.CONST, nachricht),
            Instruction(Op.TELL),
        ]

    def _handle_frage_agent(self, match) -> List[Instruction]:
        agent, thema = match.group(1), match.group(2).strip()
        return [
            Instruction(Op.CONST, "system", f"frage {agent} nach {thema}"),
            Instruction(Op.CONST, agent),
            Instruction(Op.CONST, thema),
            Instruction(Op.ASK),
        ]

    def _handle_speichere(self, match) -> List[Instruction]:
        val_token, name = match.group(1), match.group(2).strip()
        val = self._resolve_value(val_token)
        return [
            Instruction(Op.CONST, val, f"speichere {val_token} in {name}"),
            Instruction(Op.STORE, name),
        ]

    def _handle_zeige(self, match) -> List[Instruction]:
        name = match.group(1).strip()
        return [
            Instruction(Op.LOAD, name, f"zeige {name}"),
        ]

    # ── Kasus-aware compilation ───────────────────────────────────────

    def _inject_kasus_checks(self, instructions: List[Instruction]) -> List[Instruction]:
        """Inject CAP_CHECK instructions when kasus_mode is active."""
        if not self.kasus_mode:
            return instructions
        result = [Instruction(Op.CAP_CHECK, "kasus_vorprüfung")]
        result.extend(instructions)
        result.append(Instruction(Op.CAP_CHECK, "kasus_nachprüfung"))
        return result

    # ── Verb-position-aware compilation ───────────────────────────────

    def _apply_verb_position(self, sentence: str,
                              instructions: List[Instruction]) -> List[Instruction]:
        """
        Apply verb-position compilation strategy.

        Hauptsatz (V2) → sequential (instructions as-is)
        Nebensatz (V-final) → deferred (wrapped in DEFER)
        Imperativ → immediate (instructions as-is)
        """
        clause_type, verb = analyze_verb_position(sentence)

        if clause_type == ClauseType.NEBENSATZ:
            self.compilation_log.append(
                f"  ↳ Nebensatz erkannt (Verb-final: {verb}) → verzögerte Ausführung"
            )
            # Wrap all instructions in DEFER blocks
            deferred = []
            for instr in instructions:
                deferred.append(Instruction(Op.DEFER, instr.source_line))
            deferred.append(Instruction(Op.EXECUTE_DEFERRED))
            return deferred
        else:
            if verb:
                self.compilation_log.append(
                    f"  ↳ {clause_type.value} erkannt (Verb: {verb}) → sequenzielle Ausführung"
                )
            return instructions

    # ── Trennverb detection ───────────────────────────────────────────

    def _check_trennverben(self, sentence: str) -> List[Instruction]:
        """Check for separable verb patterns and compile continuations."""
        detection = self.trennverb_handler.detect_in_sentence(sentence)
        if detection:
            entry = detection["entry"]
            self.compilation_log.append(
                f"  ↳ Trennverb erkannt: {entry.infinitive} "
                f"({entry.prefix}+{entry.stem}) → {entry.semantic_class}"
            )
            cont_ops = self.trennverb_handler.compile_continuation(entry)
            instructions = []
            for cont_op, label in cont_ops:
                op_map = {
                    ContOp.CONT_PREPARE: Op.CONT_PREPARE,
                    ContOp.CONT_COMPLETE: Op.CONT_COMPLETE,
                    ContOp.CONT_SUSPEND: Op.CONT_SUSPEND,
                    ContOp.CONT_RESUME: Op.CONT_RESUME,
                }
                instructions.append(Instruction(op_map[cont_op], label))
            return instructions
        return []

    # ── Public API ────────────────────────────────────────────────────

    def compile_line(self, line: str) -> List[Instruction]:
        """
        Compile a single German NL line into VM instructions.

        Returns list of Instruction objects.
        """
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            return []

        self.compilation_log.append(f"Kompiliere: {line}")

        # Check for separable verb patterns first
        trenn_instrs = self._check_trennverben(line)

        # Try pattern matching
        for rule in self._patterns:
            match = rule.pattern.fullmatch(line)
            if match:
                self.compilation_log.append(f"  ↳ Muster: {rule.description}")
                instructions = rule.handler(match)

                # Apply verb-position strategy
                instructions = self._apply_verb_position(line, instructions)

                # Inject Kasus checks if enabled
                instructions = self._inject_kasus_checks(instructions)

                # Prepend Trennverb instructions if any
                if trenn_instrs:
                    instructions = trenn_instrs + instructions

                return instructions

        # Try separable verb as standalone (e.g., just the infinitive)
        entry = self.trennverb_handler.detect_infinitive(line.lower())
        if entry:
            cont_ops = self.trennverb_handler.compile_continuation(entry)
            self.compilation_log.append(
                f"  ↳ Trennverb: {entry.infinitive} → {entry.semantic_class}"
            )
            return [
                Instruction(Op.CONT_PREPARE, f"{entry.prefix}_{entry.stem}_prepare"),
                Instruction(Op.CONT_COMPLETE, f"{entry.prefix}_{entry.stem}_complete"),
            ]

        self.compilation_log.append(f"  ↳ Kein Muster erkannt — NOP")
        return [Instruction(Op.NOP)]

    def compile_program(self, source: str) -> List[Instruction]:
        """
        Compile a multi-line German NL program.

        Each line is compiled separately and concatenated with HALT at end.
        """
        all_instructions = []
        for line in source.strip().splitlines():
            line = line.strip()
            if line:
                instrs = self.compile_line(line)
                all_instructions.extend(instrs)
        all_instructions.append(Instruction(Op.HALT))
        return all_instructions

    def execute(self, source: str) -> Any:
        """
        Compile and execute a German NL program.

        Returns the top-of-stack value after execution.
        """
        self.vm.reset()
        self.compilation_log.clear()
        self.trennverb_handler.reset()

        instructions = self.compile_program(source)
        self.vm.load_program(instructions)
        result = self.vm.run()
        return result

    def execute_line(self, line: str) -> Any:
        """Compile and execute a single line."""
        self.vm.reset()
        self.compilation_log.clear()

        instructions = self.compile_line(line)
        instructions.append(Instruction(Op.HALT))
        self.vm.load_program(instructions)
        return self.vm.run()

    def define_kasus_scope(self, symbol: str, kasus: Kasus,
                            gender: Optional[Geschlecht] = None,
                            owner: Optional[str] = None):
        """Define a Kasus-scoped symbol in the validator."""
        return self.kasus_validator.define_scope(symbol, kasus, gender, owner)

    def check_access(self, symbol: str, required_level: CapLevel) -> bool:
        """Check Kasus-based access for a symbol."""
        return self.kasus_validator.check_access(symbol, required_level)

    def get_compilation_log(self) -> List[str]:
        return list(self.compilation_log)

    def get_vm_state(self) -> Dict[str, Any]:
        """Get current VM state for debugging."""
        return {
            "stack": list(self.vm.stack),
            "variables": dict(self.vm.variables),
            "registers": dict(self.vm.registers),
            "agent_messages": list(self.vm.agent_messages),
            "agent_questions": list(self.vm.agent_questions),
            "deferred_count": len(self.vm.deferred),
        }
