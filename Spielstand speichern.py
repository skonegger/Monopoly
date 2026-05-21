import json

# Spieler-Klasse
class Spieler:
    def __init__(self, name, nation):
        self.name = name
        self.nation = nation

        # Startwerte
        self.position = 0
        self.kontostand = 1500

        # Listen für Besitz und Karten
        self.vereine = []
        self.karten = []

    # Spielerinformationen als Dictionary speichern
    def zu_dict(self):
        return {
            "name": self.name,
            "nation": self.nation,
            "position": self.position,
            "kontostand": self.kontostand,
            "vereine": self.vereine,
            "karten": self.karten
        }

    # Dictionary wieder in Spieler umwandeln
    @staticmethod
    def von_dict(daten):
        spieler = Spieler(daten["name"], daten["nation"])
        spieler.position = daten["position"]
        spieler.kontostand = daten["kontostand"]
        spieler.vereine = daten["vereine"]
        spieler.karten = daten["karten"]
        return spieler
    
# Spiel-Klasse
class Spiel:
    def __init__(self):
        self.spieler_liste = []

    # Spieler hinzufügen
    def spieler_hinzufuegen(self, spieler):
        self.spieler_liste.append(spieler)

    # Spielstand speichern
    def speichern(self, dateiname="spielstand.json"):
        daten = []

        for spieler in self.spieler_liste:
            daten.append(spieler.zu_dict())

        with open(dateiname, "w", encoding="utf-8") as datei:
            json.dump(daten, datei, indent=4)

        print("Spielstand gespeichert!")

    # Spielstand laden
    def laden(self, dateiname="spielstand.json"):
        with open(dateiname, "r", encoding="utf-8") as datei:
            daten = json.load(datei)

        self.spieler_liste = []

        for spieler_daten in daten:
            spieler = Spieler.von_dict(spieler_daten)
            self.spieler_liste.append(spieler)

        print("Spielstand geladen!")

    # Informationen anzeigen
    def anzeigen(self):
        print("\n--- AKTUELLER SPIELSTAND ---")

        for spieler in self.spieler_liste:
            print(f"\nName: {spieler.name}")
            print(f"Nation: {spieler.nation}")
            print(f"Position: {spieler.position}")
            print(f"Kontostand: {spieler.kontostand} Mio")
            print(f"Vereine: {spieler.vereine}")
            print(f"Karten: {spieler.karten}")