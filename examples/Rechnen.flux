# ══════════════════════════════════════════════════════════════════════════
# FLUX-deu Beispielprogramm — Rechnen mit Kasus-basierter Zugriffssteuerung
# ══════════════════════════════════════════════════════════════════════════
#
# Dieses Programm demonstriert die Kernkonzepte von FLUX-deu:
#   1. Kasus-basierte Variablendeklaration (Nominativ, Akkusativ, Dativ, Genitiv)
#   2. Arithmetik mit deutschen Zahlwörtern
#   3. Agent-zu-Agent Kommunikation (TELL, ASK)
#   4. Kontrollfluss mit deutschen Schlüsselwörtern
#
# Ausführung:
#   flux-deu ausführen --datei examples/Rechnen.flux --detailliert
# ══════════════════════════════════════════════════════════════════════════

# ── Abschnitt 1: Kasus-basierte Variablendeklarationen ──────────────────
# Nominativ: Öffentlich sichtbare Variable (lesbar)
# Akkusativ: Lese-Schreib-Variable (den Wert → Ziel des Zugriffs)
# Dativ: Referenzvariable (dem Agenten → indirekter Zugriff)
# Genitiv: Besitzvariable (des Sensors → Eigentumsübertragung)

# ── Abschnitt 2: Arithmetik mit deutschen Zahlwörtern ──────────────────

# Grundrechenarten
berechne drei plus vier
berechne zehn minus drei
vier mal sechs
berechne zwanzig durch fünf

# Erweiterte Berechnungen
berechne 15 plus 27
berechne 100 minus 37
12 mal 8

# ── Abschnitt 3: Summen und Bereiche ──────────────────────────────────

summe von eins bis zehn
summe von 1 bis 100

# Fakultät
fakultät von 5
fakultät von 10

# ── Abschnitt 4: Register-Operationen ─────────────────────────────────

# Register mit Werten laden (Register = deutsche Zahlwörter 0–10)
lade register null mit 42
lade register eins mit 8
lade register zwei mit 100

# Register addieren
addiere register null und register eins

# Ergebnis speichern
speichere 99 in ergebnis

# ── Abschnitt 5: Agent-zu-Agent Kommunikation ────────────────────────

# Nominativ → Wer handelt? (Der Navigationsagent berechnet.)
# sage navigationsagent berechne kurs

# Akkusativ → Wer ist das Ziel? (Den Wetteragenten frage ich.)
# frage wetteragent nach windstärke

# Dativ → Wem sage ich es? (Dem Koordinator melde ich.)
# sage koordinator ergebnis ist 42

# Genitiv → Wem gehört es? (Die Daten des Sensoragenten.)
# delegiere analyse an sensoragent

# ── Abschnitt 6: Verbposition und Satztyp ─────────────────────────────
#
# Hauptsatz (V2): Verb an 2. Stelle → sofortige Ausführung
#   Ich berechne den Kurs.         → sofort
#   Der Agent startet die Analyse. → sofort
#
# Nebensatz (V-final): Verb am Ende → verzögerte Ausführung
#   Wenn der Wind stärker wird...  → verzögert
#   Dass das Schiff fährt...       → verzögert
#
# Imperativ: Verb an 1. Stelle → unmittelbare Ausführung
#   Berechne den Kurs!            → unmittelbar
#   Starte die Analyse!           → unmittelbar

# ── Abschnitt 7: Getrennte Verben als Continuations ───────────────────
#
# aufmachen  → CONT_PREPARE + CONT_COMPLETE (vorbereiten → aktivieren)
# anfangen   → SETUP + EXECUTE (einrichten → ausführen)
# ausführen  → BUILD + RUN (bauen → starten)
# einrichten → INIT + CONFIGURE (initialisieren → konfigurieren)

# ── Abschnitt 8: Kasus-Beispiel (Maritimer Kontext) ──────────────────
#
# Nominativ: Das Schiff fährt nach Norden.
#   → Schiff ist im öffentlichen Geltungsbereich (CAP_PUBLIC)
#
# Akkusativ: Den Kurs ändere ich auf null-null-fünf.
#   → Kurs ist Lese-Schreib-Ziel (CAP_READWRITE)
#
# Dativ: Dem Navigationsgerät vertraue ich.
#   → NavGerät ist Referenzquelle (CAP_REFERENCE)
#
# Genitiv: Die Koordinaten des Hafens werden geladen.
#   → Hafen besitzt Koordinaten (CAP_TRANSFER)

# ── Abschnitt 9: Domänenkacheln (Stufe 2) ────────────────────────────
#
# sortiere die reihe daten
# filtere die reihe werte nach größer 10
# aggregiere die reihe messungen als summe

# ══════════════════════════════════════════════════════════════════════
# Ende des Beispielprogramms
# ══════════════════════════════════════════════════════════════════════
