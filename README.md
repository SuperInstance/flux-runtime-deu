# FLUX · Fluide Sprache Universelle Ausführung

> Deutsch-zuerst NL-Laufzeitumgebung mit Kasus-basierter Zugriffssteuerung.

> **This is the German (Deutsch) localization of [flux-runtime](https://github.com/SuperInstance/flux-runtime).**
> FLUX-deu is part of the FLUX internationalization fleet — a German-first NL runtime for the FLUX universal bytecode VM, mapping the four-case system to capability-based access control, verb position to execution ordering, and separable verbs to continuation patterns.

**FLUX-deu** ist eine Neukonzeption der FLUX-Laufzeitumgebung, bei der die deutsche Grammatik die Architektur grundlegend prägt. Die vier Kasus steuern den Zugriff, die Verbposition bestimmt die Ausführungsreihenfolge, und getrennte Verben erzeugen Fortsetzungs­muster in der Bytecode-Ebene.

---

## Entwurfsphilosophie

### Kasus als Zugriffskontrolle

Die vier deutschen Fälle werden direkt auf Capability-basierte Zugriffsstufen abgebildet:

| Kasus | Artikel | Zugriffsebene | Vertrauensstufe |
|-------|---------|---------------|-----------------|
| **Nominativ** | der/die/das | Öffentlicher Bereich | `CAP_PUBLIC` |
| **Akkusativ** | den/die/das | Lese-Schreib-Ziel | `CAP_READWRITE` |
| **Dativ** | dem/der/den | Indirekter Zugriff | `CAP_REFERENCE` |
| **Genitiv** | des/der/der | Eigentumsübertragung | `CAP_TRANSFER` |

Jede Variable wird mit einem Kasus deklariert. Der Prüfer stellt sicher, dass Zugriffe die entsprechende Vertrauensstufe nicht überschreiten.

### Verbposition als Ausführungsmodell

| Satzart | Verbposition | Ausführung |
|---------|-------------|------------|
| **Hauptsatz** | Verb 2. Stelle (V2) | Sequentiell |
| **Nebensatz** | Verb am Ende (V-final) | Verzögert / Lazy |
| **Imperativ** | Verb 1. Stelle | Sofort |

Die Position des Verbs im Satz bestimmt, ob eine Anweisung sofort oder verzögert ausgeführt wird.

### Getrennte Verben als Continuations

Deutsche trennbare Verben (`aufmachen → mach...auf`) werden als Zwei-Phasen-Fortsetzungen übersetzt:

```
aufmachen  →  CONT_PREPARE + CONT_COMPLETE
anfangen   →  SETUP + EXECUTE
ausführen  →  BUILD + RUN
```

### Komposita als Typkomposition

Zusammengesetzte Wörter werden als verschachtelte Typen interpretiert:

```
Datenbank     →  Daten<Bank>
Datenspeicher →  Daten<Speicher>
Netzwerkplan  →  Netz<werk<Plan>>
```

---

## Architektur

```
┌─────────────────────────────────────────────┐
│           Deutsch-sprachige NL-Schicht       │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ kasus.py│ │trennverb │ │ vocabulary/  │  │
│  │ 4 Fälle │ │ Getrennte│ │  math.ese    │  │
│  │ CapLevel│ │   Verben │ │  maritime.ese│  │
│  └────┬────┘ └────┬─────┘ │  a2a.ese     │  │
│       │           │        └──────────────┘  │
│  ┌────┴───────────┴──────────────────────┐   │
│  │       interpreter.py                   │   │
│  │  NL-Muster → Bytecode-Übersetzung      │   │
│  │  Verbposition-Analyse                  │   │
│  │  Kasus-Modus-Injektion                 │   │
│  └────────────────┬──────────────────────┘   │
├───────────────────┼──────────────────────────┤
│           Sprachagnostische VM-Kernschicht    │
│  ┌────────────────┴──────────────────────┐   │
│  │  MiniVM (Op, Instruction, Stack)      │   │
│  │  NOP CONST LOAD STORE ADD SUB MUL DIV │   │
│  │  SUM_RANGE FACTORIAL TELL ASK         │   │
│  │  CONT_* CAP_CHECK DEFER               │   │
│  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## Beispiele

### Grundrechenarten

```bash
$ flux-deu öffnen
  flux> berechne 3 plus 5
  ← 8
  flux> 4 mal 6
  ← 24
  flux> summe von 1 bis 10
  ← 55
  flux> fakultät von 5
  ← 120
```

### Register und Variablen

```bash
  flux> lade register null mit 42
  flux> lade register eins mit 8
  flux> addiere register null und register eins
  ← 50
  flux> speichere 99 in ergebnis
```

### Agent-Kommunikation

```bash
  flux> sage navigator berechne kurs nach norden
  flux> frage wetteragent nach windstärke
```

### Kasus-Modus

```bash
$ flux-deu --kasus-modus --detailliert kompilieren --datei programm.flux
  ↳ Muster: berechne X plus Y → addiere
  ↳ Hauptsatz erkannt (Verb: berechne) → sequenzielle Ausführung
  [000] CAP_CHECK 'kasus_vorprüfung'
  [001] CONST 3   ← berechne 3 plus 5
  [002] CONST 5
  [003] ADD
  [004] CAP_CHECK 'kasus_nachprüfung'
```

### Analyse

```bash
$ flux-deu zerlegen "wenn das Schiff fährt"
  Satzart:     Nebensatz
  Verb:        fährt
  Position:    Endposition (V-final)
```

---

## Installation

```bash
# Aus dem Quellcode
git clone <repo>
cd flux-runtime-deu
pip install -e ".[dev]"

# CLI verfügbar als
flux-deu hallo
flux-deu öffnen
flux-deu ausführen --datei programm.flux
```

## Tests

```bash
pytest tests/ -v
```

---

## Projektstruktur

```
flux-runtime-deu/
├── pyproject.toml
├── README.md
├── docs/
│   └── design.md
├── src/flux_deu/
│   ├── __init__.py
│   ├── cli.py           # Deutsch-sprachige CLI
│   ├── interpreter.py   # NL→Bytecode-Übersetzer + MiniVM
│   ├── kasus.py         # Kasus-System & Zugriffskontrolle
│   ├── trennverben.py   # Getrennte Verben → Continuations
│   └── vocabulary/
│       ├── math.ese     # Mathematische Vokabeln
│       ├── maritime.ese # Seefahrts-Vokabeln
│       └── a2a.ese      # Agent-Kommunikation
└── tests/
    └── test_interpreter_deu.py
```

---

## Lizenz

MIT

---

<img src="callsign1.jpg" width="128" alt="callsign">
