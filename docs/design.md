# FLUX-deu Entwurfsdokument

> Kasus als Zugriffskontrolle · Verbposition als Ausführungsmodell · Getrennte Verben als Continuations · Komposita als Typkomposition

---

## 1. Einleitung

FLUX-deu ist eine konzeptgetriebene Neugestaltung der FLUX-Laufzeitumgebung. Anstatt eine internationale NL-Schicht über eine sprachagnostische VM zu legen, wird hier die deutsche Grammatik selbst zum architektonischen Fundament. Jede grammatikalische Eigenschaft des Deutschen wird auf ein Programmierkonzept abgebildet:

- **Kasus (4 Fälle)** → Zugriffskontrolle (Capability Security)
- **Verbposition (V2 / V-final)** → Ausführungsreihenfolge (eager / lazy)
- **Getrennte Verben** → Fortsetzungsmuster (Continuations / Coroutinen)
- **Komposita** → Typkomposition ( verschachtelte generische Typen)
- **Geschlecht (der/die/das)** → Nominale Typklassen (3 Geschlechterklassen)

Die VM-Kernschicht bleibt 100% sprachagnostisch. Die Neuentwicklung betrifft ausschließlich die NL-Oberfläche.

---

## 2. Kasus als Zugriffskontrolle

### 2.1 Die vier Fälle und ihre Vertrauensstufen

Die deutsche Sprache kennt vier Kasus (Fälle). Jeder Kasus wird auf eine Capability-Stufe abgebildet:

```
Nominativ  ───  CAP_PUBLIC     (0)  ── Öffentlich sichtbar
Akkusativ  ───  CAP_READWRITE  (2)  ── Direktes Lese-Schreib-Ziel
Dativ      ───  CAP_REFERENCE  (1)  ── Indirekter Referenzzugriff
Genitiv    ───  CAP_TRANSFER   (3)  ── Eigentumsübertragung
```

Die Stufen sind geordnet: `CAP_TRANSFER > CAP_READWRITE > CAP_REFERENCE > CAP_PUBLIC`.

### 2.2 Artikel als Kasus-Indikatoren

Bestimmte Artikel geben den Kasus an:

| Artikel | Mögliche Kasus |
|---------|----------------|
| der     | Nominativ (mask.), Genitiv (fem./neut.) |
| die     | Nominativ (fem./pl.), Akkusativ (fem./pl.) |
| das     | Nominativ (neut.), Akkusativ (neut.) |
| den     | Akkusativ (mask.) |
| dem     | Dativ (mask./neut.) |
| des     | Genitiv (mask.) |

### 2.3 Umsetzung in der VM

Wenn der Kasus-Modus aktiviert ist (`--kasus-modus`), werden `CAP_CHECK`-Anweisungen vor und nach jeder Operation eingefügt. Der `KasusValidator` prüft, ob die aktuelle Kasus-Berechtigung für die angeforderte Operation ausreicht.

```
# Ohne Kasus-Modus:
CONST 3
CONST 5
ADD

# Mit Kasus-Modus:
CAP_CHECK "kasus_vorprüfung"
CONST 3
CONST 5
ADD
CAP_CHECK "kasus_nachprüfung"
```

### 2.4 Beispiel

```
# Nominativ — öffentliche Variable
Der Wert ist sichtbar.
→ define_scope("wert", Kasus.NOMINATIV)
→ can_access(CAP_PUBLIC) = True
→ can_access(CAP_READWRITE) = False

# Akkusativ — direktes Ziel
Den Wert ändere ich.
→ define_scope("wert", Kasus.AKKUSATIV)
→ can_access(CAP_READWRITE) = True

# Genitiv — Eigentumsübertragung
Die Daten des Sensors werden übertragen.
→ define_scope("daten", Kasus.GENITIV, owner="Sensor")
→ can_access(CAP_TRANSFER) = True
```

---

## 3. Verbposition als Ausführungsmodell

### 3.1 Deutsche Satzarten und Verbstellung

Im Deutschen bestimmt die Position des Verbs die Satzart:

- **Hauptsatz (V2):** Das Verb steht an zweiter Stelle.
  - *Ich berechne den Kurs.*
  - Übersetzung: Sequentielle, sofortige Ausführung.

- **Nebensatz (V-final):** Das Verb steht am Ende.
  - *Wenn der Wind stärker wird, ...*
  - Übersetzung: Verzögerte (lazy) Ausführung. Die Anweisung wird in einen `DEFER`-Block eingeschlossen.

- **Imperativ (V1):** Das Verb steht an erster Stelle.
  - *Berechne den Kurs!*
  - Übersetzung: Sofortige Ausführung.

### 3.2 Einleitende Konjunktionen

Folgende Wörter leiten einen Nebensatz ein und erzwingen V-final:

```
wenn, dass, ob, weil, da, falls, sobald, bevor, nachdem, obwohl, während
```

### 3.3 Bytecode-Auswirkung

```
# Hauptsatz: "ich berechne 3 plus 5"
CONST 3
CONST 5
ADD        ← sofort ausgeführt

# Nebensatz: "wenn x größer ist als 5"
DEFER      ← nicht sofort ausgeführt
  CONST x
  CONST 5
  COMPARE_GT
EXECUTE_DEFERRED  ← erst bei Bedarf
```

---

## 4. Getrennte Verben als Continuations

### 4.1 Das Prinzip

Deutsche Verben mit trennbarem Präfix bestehen aus zwei Teilen, die im Satz getrennt stehen:

```
aufmachen  →  Ich mache die Tür auf.
anfangen   →  Ich fange die Arbeit an.
ausführen  →  Ich führe das Programm aus.
```

Dieses Muster wird auf Coroutine/Continuation-Bytecode abgebildet:

```
aufmachen  →  CONT_PREPARE → CONT_SUSPEND → CONT_RESUME → CONT_COMPLETE
```

### 4.2 Registrierte Trennverben

| Infinitiv | Präfix | Stamm | Semantische Klasse |
|-----------|--------|-------|---------------------|
| anfangen  | an     | fangen | SETUP_EXECUTE |
| aufbauen  | auf    | bauen  | SETUP_EXECUTE |
| aufmachen | auf    | machen | PREPARE_ACTIVATE |
| ausführen | aus    | führen | BUILD_RUN |
| abschließen | ab  | schließen | FINALIZE_CLOSE |
| einrichten | ein  | richten | INIT_CONFIGURE |
| herunterladen | herunter | laden | DOWNLOAD_STORE |
| zurückgeben | zurück | geben | DOWNLOAD_STORE |

### 4.3 Bytecode-Erzeugung

Jedes Trennverb erzeugt eine 4-Phasen-Sequenz:

```
Phase 1: CONT_PREPARE  — Vorbereitung (Präfix-Teil)
Phase 2: CONT_SUSPEND  — Unterbrechungspunkt
Phase 3: CONT_RESUME   — Fortsetzung
Phase 4: CONT_COMPLETE — Abschluss (Suffix-Teil)
```

### 4.4 Erkennung

Der `TrennverbHandler` erkennt Trennverben auf drei Wegen:

1. **Infinitiv-Lookup:** Direkte Suche in der Registry
2. **Präfix-Spaltung:** Versuch, ein Wort in Präfix + Stamm zu zerlegen
3. **Satzmuster:** Erkennung von "Stamm ... Präfix" am Satzanfang/-ende

---

## 5. Komposita als Typkomposition

### 5.1 Das Prinzip

Deutsche Komposita (zusammengesetzte Wörter) werden als verschachtelte generische Typen interpretiert:

```
Datenbank     →  Daten<Bank>       — eine Bank für Daten
Datenspeicher →  Daten<Speicher>    — ein Speicher für Daten
Netzwerkplan  →  Netz<werk<Plan>>  — ein Plan für ein Werk für ein Netz
```

### 5.2 Zerlegungsalgorithmus

Der Algorithmus arbeitet gierig von links nach rechts und versucht, bekannte Wortbestandteile zu identifizieren:

1. Beginne mit dem vollständigen Wort
2. Versuche, das längste bekannte Präfix zu finden
3. Fahre mit dem Rest fort
4. Wiederhole, bis nichts mehr übrig ist

### 5.3 Bekannte Bestandteile

```
daten, bank, speicher, zeit, lauf, fluss, netz, werk, zeug,
raum, stelle, plan, buch, karte, tabelle, liste, baum, knoten,
feld, wert, matrix, vektor, tensor, system
```

### 5.4 Typausdruck

Für ein Wort mit N Teilen wird der Typausdruck als verschachtelte Generics erzeugt:

```
Teile: [A, B, C]  →  Typ: A<B<C>>
```

---

## 6. Geschlecht als nominale Typklassen

### 6.1 Die drei Geschlechter

Jedes Nomen gehört zu einer der drei Klassen:

| Geschlecht | Artikel | Beispiel | Typklasse |
|-----------|---------|----------|-----------|
| Maskulinum | der | der Kurs, der Wind | Klasse M |
| Femininum | die | die Nachricht, die Karte | Klasse F |
| Neutrum | das | das Schiff, das Ergebnis | Klasse N |

### 6.2 Bedeutung für das System

Geschlecht dient als zusätzliche Typinformation. Zwei Nomen desselben Geschlechts gehören zur gleichen Typklasse und können in Kontexten verwendet werden, die ein bestimmtes Geschlecht erwarten.

---

## 7. MiniVM — Der sprachagnostische Kern

### 7.1 Befehlssatz

| Opcode | Operand | Beschreibung |
|--------|---------|-------------|
| `NOP` | — | Keine Operation |
| `CONST` | Wert | Konstante auf den Stapel legen |
| `LOAD` | Name | Variable/Register laden |
| `STORE` | Name | In Variable/Register speichern |
| `ADD` | — | Zwei Werte addieren |
| `SUB` | — | Zwei Werte subtrahieren |
| `MUL` | — | Zwei Werte multiplizieren |
| `DIV` | — | Zwei Werte dividieren |
| `SUM_RANGE` | — | Summe eines Bereichs |
| `FACTORIAL` | — | Fakultät berechnen |
| `TELL` | — | Agent-Nachricht senden |
| `ASK` | — | Agent-Frage stellen |
| `JMP` | Adresse | Unbedingter Sprung |
| `JZ` | Adresse | Sprung bei Null |
| `CAP_CHECK` | Bezeichner | Kasus-Berechtigungsprüfung |
| `SCOPE_PUSH` | — | Kasus-Bereich betreten |
| `SCOPE_POP` | — | Kasus-Bereich verlassen |
| `CONT_PREPARE` | Label | Fortsetzung vorbereiten |
| `CONT_COMPLETE` | Label | Fortsetzung abschließen |
| `CONT_SUSPEND` | Label | Anhaltepunkt |
| `CONT_RESUME` | Label | Wiederaufnahme |
| `DEFER` | — | Anweisung verzögern |
| `EXECUTE_DEFERRED` | — | Verzögerte Anweisungen ausführen |
| `HALT` | — | Programm anhalten |

### 7.2 Stapelmaschine

Die VM arbeitet als Stapelmaschine (Stack Machine):
- `CONST x` legt x auf den Stapel
- `ADD` nimmt die obersten zwei Werte, addiert sie, und legt das Ergebnis zurück
- Alle arithmetischen Operationen folgen diesem Muster

---

## 8. Wortschatzdateien (.ese)

Wortschatzdateien liegen im `vocabulary/`-Verzeichnis:

| Datei | Inhalt |
|-------|--------|
| `math.ese` | Mathematische Vokabeln (Grundrechenarten, Funktionen, Zahlen) |
| `maritime.ese` | Seefahrtsbegriffe (Richtungen, Messungen, Schiffsteile) |
| `a2a.ese` | Agent-Kommunikation (sage, frage, Vertrauensstufen) |

### Format

```ese
# Kommentar
@version 1.0
@lang deu

wort   POS   KATEGORIE   Übersetzung/Bedeutung
```

---

## 9. Zukunftsausblick

### Geplante Erweiterungen

1. **Temperatur-Kasus:** Grammatische Kongruenzprüfung zwischen Subjekt und Prädikat
2. **Adjektivdeklination:** Eigenschaftsbeschränkungen (starke/schwache Deklination → starke/schwache Typsysteme)
3. **Satzgefüge:** Komplexe Nebensatzeinbindung mit explizitem Datenfluss
4. **Ergänzungsfragen (W-Fragen):** Wer, was, wo, wann, warum → Abfragemuster
5. **Vokabel-Erweiterung:** Weitere Fachgebiete (Medizin, Recht, Technik)
