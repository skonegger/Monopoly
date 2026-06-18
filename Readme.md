
# Fußball Monopoly Pro 

Eine moderne, auf **Pygame** basierende Fußball-Variante des weltberühmten Brettspielklassikers. Anstelle von Straßen kaufst du hier internationale Top-Vereine, verhandelst über TV-Übertragungsrechte, sicherst dir exklusive Sponsorenverträge und baust deine Stadien von einfachen Tribünen bis hin zur High-Tech-Arena aus. Aber pass auf: Der VAR schläft nicht und eine Rote Karte bringt dich direkt auf die Strafbank!

---

## Features

- **Modernes Premium-Design:** Edle Dark-Mode-Farbpalette kombiniert mit sattem Stadion-Rasen-Grün und übersichtlichen Dashboards für beide Spieler.
- **Vollwertiges Wirtschaftssystem:**
  - **Vereine (Properties):** Kaufe Clubs aus 8 verschiedenen Farbgruppen/Nationen.
  - **Stadienausbau:** Investiere in bis zu 4 Tribünen oder baue das maximale Stadion (Medic-Stufe) für massive Mietsteigerungen.
  - **TV-Sender:** Sichere dir Medienrechte wie Sky oder Prime Video.
  - **Sponsoren (Utilities):** Komplett integrierte Sponsorenfelder. Landet ein Mitspieler darauf, zahlt er eine leistungsbezogene Miete in Höhe des aktuellen **Würfelwurfs × 10**.
- **Dynamischer Transfermarkt (Trade-System):** Ein interaktives und fehlerfreies Tauschmenü. Handle mit deinem Mitspieler um Geld und Verträge. Dank ID-basierter Übertragung wechseln auch namensgleiche Felder (wie die Sponsoren) immer fehlerfrei den Besitzer.
- **Ereignis- & Aktionskarten:** Integriertes Kartensystem mit zwei Decks (**VAR** und **PRÄMIE**), gesteuert über einen externen Handler.
- **Erweiterte Spielregeln:** - Pasch-Mechanik (Wer 3-mal hintereinander Pasch würfelt, fliegt vom Platz).
  - Umfassende Strafbank-Logik (Kaution zahlen, Freikarte nutzen oder auf Pasch hoffen).
- **Automatisches & Manuelles Speichern:** Der Spielstand wird nach jedem Zug sowie manuell verschlüsselt in der `spielstand.json` gesichert und beim Start automatisch wieder geladen.

---

## Projektstruktur

```text
├── main.py                          # Hauptspielschleife, GUI-Rendering und Input-Verarbeitung
├── player.py                        # Spieler-Klasse (Position, Geld, Besitztümer, Kartenstatus)
├── card_handler.py                 # Auswertungslogik für gezogene VAR- und Prämienkarten
├── constants.py                     # Globale Konstanten (Spielfeldgröße, FPS, TILE_SIZE)
├── spielfeld.json                   # Konfiguration aller 40 Felder (Preise, Gruppen, IDs)
├── cards.json                       # Kartentexte und numerische Effekte für VAR und PRÄMIE
├── football_nations_monopoly.json   # Eigenschaften und Spezialeffekte der Nationalteams
└── spielstand.json                  # (Wird automatisch generiert) Gespeicherter Spielstand

```

---

## Installation & Start

### Voraussetzungen

Stelle sicher, dass du **Python 3.x** sowie die Bibliothek **Pygame** installiert hast.

```bash
# Pygame installieren (falls noch nicht vorhanden)
pip install pygame

# Das Spiel starten
python main.py

```

---

## Tastaturbelegung & Steuerung

Das Spiel wird komplett über die Tastatur gesteuert. Im unteren Bereich des Bildschirms befindet sich zudem eine dynamische Statusleiste.

### Im Hauptspiel (IDLE)

* `[LEERTASTE]` – Würfeln und Spielfigur bewegen.
* `[E]` – Aktuellen Zug beenden und zum nächsten Spieler wechseln (nur nach dem Würfeln möglich).
* `[B]` – **Stadions-Ausbaumenü** öffnen (setzt den Besitz einer vollständigen Farbgruppe voraus).
* `[T]` – **Transfermarkt** öffnen (Tauschmenü mit dem Mitspieler).
* `[S]` – Spielstand manuell abspeichern.
* `[R]` – Laufendes Spiel komplett zurücksetzen und neu starten (löscht die `spielstand.json`).

### In Menüs & Dialogen

* **Meldungsfenster / Kauf-Prompts:** - `[J]` – Bestätigen / Ja / Kaufen
* `[N]` – Ablehnen / Nein


* **Stadionbau-Menü:**
* `[J]` – Ausgewählten Verein um eine Stufe ausbauen (Kosten variieren je nach Farbgruppe).
* `[N]` – Zum nächsten ausbaubaren Verein durchwechseln.
* `[E]` – Ausbaumenü beenden.


* **Transfermarkt (Tauschmenü):**
* `[▲ / ▼]` – Durch die Optionen navigieren (Geld bieten, Objekt bieten, Geld fordern, Objekt fordern, Absenden).
* `[◀ / ▶]` – Beträge ändern (in 10€-Schritten) oder durch deine Besitztümer blättern.
* `[J / ENTER]` – Angebot an den Mitspieler absenden.
* `[E / ESC]` – Transfermarkt unverrichteter Dinge verlassen.



---

## Spiellogik & Regelwerk (Auszug)

### 1. Sponsorenfelder (Utilities)

Landet ein Spieler auf einem Sponsorenfeld, das bereits jemand anderem gehört, wird die Miete dynamisch berechnet. Der Wert des letzten Würfelwurfs (z. B. eine $4$ und eine $5 = 9$) wird mit **10** multipliziert. In diesem Fall müsste der Spieler $90€$ Miete zahlen.

### 2. Farbgruppen & Mieten

Besitzt ein Spieler alle Vereine einer Farbgruppe, verdoppelt sich die Basismiete der unbebauten Vereine automatisch. Sobald Tribünen (bis zu 4) oder das finale Stadion (Stufe 5) gebaut werden, greift der jeweilige Multiplikator der Miete (bis zu **60x** der Basismiete auf Stufe 5).

### 3. Die Strafbank (Feld 10)

Wer auf Feld 30 ("Rote Karte") landet oder dreimal in Folge ein Pasch würfelt, muss sofort auf die Strafbank. Dort angekommen, hat der Spieler zu Beginn seines Zuges 3 Optionen:

1. Eine vorhandene Freikarte nutzen.
2. Eine Strafe von $50€$ zahlen, um sofort normal weiterzuwürfeln.
3. Einen Pasch-Versuch wagen. Gelingt der Pasch nicht innerhalb von 3 Runden, wird man nach dem 3. Versuch gezwungen, die $50€$ zu zahlen, und zieht mit dem geworfenen Wert vorwärts.
