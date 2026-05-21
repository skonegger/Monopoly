import pygame
import sys
import random
import json
import os

# ================= CONFIG & LEAGUE COLORS =================
WIDTH, HEIGHT = 800, 800
BOARD_SIZE = 600
TILE_SIZE = BOARD_SIZE // 11
FPS = 60

WHITE = (255, 255, 255)
GREEN = (34, 139, 34)
BLACK = (0, 0, 0)
RED   = (200, 0, 0)
BLUE  = (0, 0, 200)
DARK  = (30, 30, 30)

COLORS = {
    "group_1": (128, 0, 128),   # Lila (Österreich)
    "group_2": (255, 165, 0),   # Orange (Niederlande)
    "group_3": (64, 224, 208),  # Türkis (Portugal)
    "group_4": (173, 216, 230), # Hellblau (Frankreich)
    "group_5": (255, 0, 0),     # Rot (Bundesliga)
    "group_6": (255, 255, 0),   # Gelb (Serie A)
    "group_7": (255, 192, 203), # Pink (Premier League)
    "group_8": (0, 0, 139),     # Dunkelblau (Spanien)
    "TV":      (0, 0, 0),       # Schwarz (TV-Rechte)
    "card":    (0, 255, 0),     # Grün (VAR/Prämie)
    "utility": (169, 169, 169), # Grau (Sponsoren)
    "default": (200, 200, 200)  # Standard-Grau (Ecken/Steuern)
}


# ================= FIELD =================
class Field:
    def __init__(self, data, x, y):
        self.data  = data
        self.name  = data["name"]
        self.rect  = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.owner = None
        self.price = data.get("price", 0)
        self.rent  = data.get("rent", 0)
        
        f_type = data.get("type")
        group  = data.get("group")
        
        # Farbegruppe zuweisen
        if f_type == "property" and group:
            self.color = COLORS.get(f"group_{group}", COLORS["default"])
        else:
            self.color = COLORS.get(f_type, COLORS["default"])

    def draw(self, screen):
        # Feldhintergrund
        pygame.draw.rect(screen, WHITE, self.rect)
        # Farbbalken oben am Feld (15 Pixel hoch)
        pygame.draw.rect(screen, self.color, pygame.Rect(self.rect.x, self.rect.y, TILE_SIZE, 15))
        # Rahmen um das Feld
        pygame.draw.rect(screen, BLACK, self.rect, 2)
        
        # Text rendern
        font = pygame.font.SysFont("Arial", 10, bold=True)
        text = font.render(self.name[:10], True, BLACK)
        screen.blit(text, (self.rect.x + 4, self.rect.y + 18))
        
        # Besitzer anzeigen falls vorhanden
        if self.owner:
            owner_font = pygame.font.SysFont("Arial", 9, bold=True)
            owner_text = owner_font.render(f"P: {self.owner}", True, (50, 50, 50))
            screen.blit(owner_text, (self.rect.x + 4, self.rect.y + TILE_SIZE - 12))


# ================= PLAYER =================
class Player:
    def __init__(self, name, color, pid):
        self.name     = name
        self.color    = color
        self.id       = pid
        self.position = 0
        self.money    = 1500
        self.vereine  = []
        self.double_count = 0  # Pasch-Zähler
        self.turns_to_skip = 0          # Wenn > 0, setzt der Spieler aus
        self.positive_effect_disabled = False
        self.is_immune = False          # Für Medienlob (Kein negativer Effekt)

    def draw(self, screen, fields):
        center = fields[self.position].rect.center
        # Spielfiguren leicht versetzen, damit man beide auf derselben Kachel sieht
        offset = -10 if self.id == 1 else 10
        pygame.draw.circle(screen, self.color, (center[0] + offset, center[1]), 12)


# ================= GAME / GUI =================
class MonopolyGUI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fußball Monopoly Pro")
        self.clock = pygame.time.Clock()
        
        self.font       = pygame.font.SysFont("Arial", 22)
        self.small_font = pygame.font.SysFont("Arial", 16)
        
        # Datendateien laden
        with open('football_nations_monopoly.json', 'r', encoding='utf-8') as f:
            self.nations_data = json.load(f)
        with open('cards.json', 'r', encoding='utf-8') as f:
            self.cards = json.load(f)["cards"]

        # Spieler initialisieren
        self.players = [
            Player("Spieler 1", RED, 1),
            Player("Spieler 2", BLUE, 2)
        ]
        self.current = 0
        
        # Spielfeld generieren
        self.fields = self.load_board()
        
        # Zustandsverwaltung (IDLE, BUY, MESSAGE)
        self.state = "IDLE"
        self.message = None
        self.buy_field = None
        self.last_dice_text = ""
        self.last_roll_was_double = False
        
        # Automatisch gespeicherten Spielstand laden (falls vorhanden)
        self.laden()

    def load_board(self):
        with open("spielfeld.json", "r", encoding="utf-8") as f:
            board = json.load(f)["board"]
            
        fields = [None] * 40
        offset = (WIDTH - BOARD_SIZE) // 2
        
        for data in board:
            i = data["id"]
            if 0 <= i <= 10:
                x = offset + BOARD_SIZE - (i + 1) * TILE_SIZE
                y = offset + BOARD_SIZE - TILE_SIZE
            elif 11 <= i <= 20:
                x = offset
                y = offset + BOARD_SIZE - ((i - 10) + 1) * TILE_SIZE
            elif 21 <= i <= 30:
                x = offset + (i - 20) * TILE_SIZE
                y = offset
            else:
                x = offset + BOARD_SIZE - TILE_SIZE
                y = offset + (i - 30) * TILE_SIZE
                
            fields[i] = Field(data, x, y)
        return fields

    def show_message(self, text):
        self.message = text

    def next_player(self):
        self.current = (self.current + 1) % len(self.players)
        self.speichern()

    # ================= SAVE & LOAD =================
    def speichern(self, dateiname="spielstand.json"):
        daten = {
            "current_player_idx": self.current,
            "players": [{"position": p.position, "money": p.money, "vereine": p.vereine} for p in self.players],
            "field_owners": {str(i): f.owner for i, f in enumerate(self.fields) if f is not None and f.owner is not None}
        }
        with open(dateiname, "w", encoding="utf-8") as datei:
            json.dump(daten, datei, indent=4, ensure_ascii=False)

    def laden(self, dateiname="spielstand.json"):
        if not os.path.exists(dateiname):
            return
        try:
            with open(dateiname, "r", encoding="utf-8") as datei:
                daten = json.load(datei)
            self.current = daten["current_player_idx"]
            for p, pd in zip(self.players, daten["players"]):
                p.position, p.money, p.vereine = pd["position"], pd["money"], pd["vereine"]
            for idx_str, owner in daten["field_owners"].items():
                self.fields[int(idx_str)].owner = owner
            self.show_message("Spielstand erfolgreich geladen!")
            self.state = "MESSAGE"
        except Exception:
            pass

    def neu_starten(self):
        if os.path.exists("spielstand.json"):
            os.remove("spielstand.json")
        for p in self.players:
            p.position, p.money, p.vereine, p.double_count = 0, 1500, [], 0
        for f in self.fields:
            if f: f.owner = None
        self.current = 0
        self.state = "IDLE"
        self.message = None
        self.buy_field = None
        self.last_dice_text = ""
        self.last_roll_was_double = False
        self.show_message("Das Spiel wurde neu gestartet!")
        self.state = "MESSAGE"

    # ================= CARDS LOGIC =================
    def draw_card(self, player, typ):
        if typ == "NATION":
            nation = random.choice(self.nations_data)
            text = f"{nation['name']}:\n{nation['positive_effect']}\n{nation['negative_effect']}"
        else:
            card = random.choice(self.cards[typ])
            text = card["effekt"]
            # Geldeffekt verrechnen
            if "value" in card:
                player.money += card["value"]
                if player.money < 0: player.money = 0

        card = random.choice(self.cards[typ])
        text = card["effekt"]
        card_id = card["id"]  # Wir nutzen die ID aus deiner JSON!

        # Standard-Geld-Effekt (falls vorhanden)
        if "value" in card:
             # Falls der Spieler nicht immun ist oder es sich um einen positiven Effekt handelt
            if not (player.is_immune and card["value"] < 0):
                player.money += card["value"]
                if player.money < 0: player.money = 0
            
        # --- SPEZIFISCHE LOGIK NACH CARD-ID ---
    
        # ID 4 oder ähnliche: Gehe X Felder zurück
        if card_id == 4:  
            player.position = (player.position - 3) % len(self.fields)
        
        # ID 6 / ID 39: Reisechaos / Verletzung -> 1 Runde aussetzen
        elif card_id in [6, 39]: 
            player.turns_to_skip = 1
        
        # ID 2: Handspiel -> Positiver Effekt deaktiviert
        elif card_id == 2:
            player.positive_effect_disabled = True
        
        # ID 44: Medienlob -> Immun gegen den nächsten negativen Effekt
        elif card_id == 44:
            player.is_immune = True
        
        # ID 45: Spielplanänderung -> Positionen tauschen
        elif card_id == 45:
            other_player = self.players[1] if self.current == 0 else self.players[0]
            player.position, other_player.position = other_player.position, player.position

        # Immunität verfällt nach der Runde, wenn sie aktiv war und ein Schaden abgewendet wurde
        if player.is_immune and card.get("value", 0) < 0:
            player.is_immune = False

        self.show_message(text)
        self.state = "MESSAGE"

    # ================= LAND LOGIC =================
    def land(self, player):
        field = self.fields[player.position]
        field_type = field.data.get("type")

        # KARTENFELDER
        if field_type == "card":
            deck = field.data.get("deck")
            if deck == "NATION":
                self.draw_card(player, "NATION")
            elif field.name.upper() == "VAR":
                self.draw_card(player, "VAR")
            else:
                self.draw_card(player, "PRÄMIE")
            return

        # VEREIN / TV-RECHTE
        if field_type in ["property", "TV"]:
            # Ungekauftes Feld
            if field.owner is None:
                self.buy_field = field
                self.show_message(f"{player.name}: {field.name} kaufen?\nPreis: {field.price}€")
                self.state = "BUY"
            # Fremdes Feld -> Miete zahlen
            elif field.owner != player.name:
                rent = field.rent
                payment = min(player.money, rent) # Schutz vor unendlichen Minusschulden
                player.money -= payment
                
                for p in self.players:
                    if p.name == field.owner:
                        p.money += payment
                        
                self.show_message(f"{player.name} bezahlt {payment}€ Miete\nan {field.owner} für {field.name}.")
                self.state = "MESSAGE"

    # ================= DICE LOGIC =================
    def roll_dice(self):
        player = self.players[self.current]
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        steps = d1 + d2
        
        self.last_dice_text = f"{d1}+{d2}={steps}"
        pasch = (d1 == d2)
        self.last_roll_was_double = pasch

        if pasch:
            player.double_count += 1
        else:
            player.double_count = 0

        # Strafe bei 3 Paschen hintereinander
        if player.double_count >= 3:
            player.double_count = 0
            self.show_message(f"{player.name} hatte 3 Pasche hintereinander!\nDer Zug ist sofort vorbei.")
            self.state = "MESSAGE"
            return

        # Bewegung ausführen
        player.position = (player.position + steps) % len(self.fields)
        self.land(player)

        # Wenn nach der Landung kein Dialog/Karten-Event aktiv wurde:
        if self.state == "IDLE":
            if pasch:
                self.show_message("PASCH!\nDu darfst noch einmal würfeln.")
                self.state = "MESSAGE"
            else:
                self.next_player()

    # ================= INPUT PROCESSING =================
    def handle_input(self, event):
        if event.type != pygame.KEYDOWN:
            return

        player = self.players[self.current]

        # Zustand: TEXTANZEIGE
        if self.state == "MESSAGE":
            if event.key == pygame.K_j:
                self.message = None
                if self.last_roll_was_double:
                    self.last_roll_was_double = False
                    self.state = "IDLE"
                else:
                    self.state = "IDLE"
                    self.next_player()
            return

        # Zustand: KAUFOPTION
        if self.state == "BUY":
            if event.key == pygame.K_j:  # JA
                if player.money >= self.buy_field.price:
                    player.money -= self.buy_field.price
                    self.buy_field.owner = player.name
                    player.vereine.append(self.buy_field.name)
                    self.show_message(f"{player.name} kauft {self.buy_field.name}!")
                else:
                    self.show_message("Nicht genug Geld auf dem Konto!")
                self.state = "MESSAGE"
            elif event.key == pygame.K_n:  # NEIN
                self.show_message("Kauf abgelehnt.")
                self.state = "MESSAGE"
                
            self.buy_field = None
            return

        # Zustand: AUSGANGSLAGE (Warten auf Würfelwurf)
        if self.state == "IDLE":
            if event.key == pygame.K_SPACE:
                self.roll_dice()
            elif event.key == pygame.K_s:
                self.speichern()
                self.show_message("Spielstand manuell gespeichert!")
                self.state = "MESSAGE"
            elif event.key == pygame.K_r:
                self.neu_starten()

    # ================= DRAW METHODS =================
    def draw_ui(self):
        y = 15
        # Geldstände
        for p in self.players:
            txt = self.font.render(f"{p.name}: {p.money}€", True, p.color)
            self.screen.blit(txt, (20, y))
            y += 30

        # Welcher Spieler ist am Zug?
        turn = self.font.render(f"Dran: {self.players[self.current].name} (Leertaste)", True, BLACK)
        self.screen.blit(turn, (20, y + 10))

        # Letztes Würfelergebnis
        dice = self.font.render(f"Wurf: {self.last_dice_text}", True, BLACK)
        self.screen.blit(dice, (20, y + 45))
        
        # Shortcut-Hinweise am unteren Spielfeldrand
        shortcuts = self.small_font.render("[S] Speichern  |  [R] Zurücksetzen", True, BLACK)
        self.screen.blit(shortcuts, (20, HEIGHT - 35))

    def draw_message_box(self):
        if not self.message:
            return

        box = pygame.Rect(WIDTH // 2 - 250, HEIGHT // 2 - 85, 500, 170)
        pygame.draw.rect(self.screen, DARK, box, border_radius=8)
        pygame.draw.rect(self.screen, WHITE, box, 2, border_radius=8)

        lines = self.message.split("\n")
        y = box.y + 20
        
        for line in lines:
            txt = self.small_font.render(line, True, WHITE)
            self.screen.blit(txt, (box.x + 20, y))
            y += 26

        # Aktionsanweisungen in der Box zeichnen
        if self.state == "BUY":
            yes = self.small_font.render("[J] = JA", True, (0, 255, 0))
            no  = self.small_font.render("[N] = NEIN", True, (255, 0, 0))
            self.screen.blit(yes, (box.x + 20, box.y + 130))
            self.screen.blit(no,  (box.x + 150, box.y + 130))
        else:
            ok = self.small_font.render("[J] = Bestätigen", True, (0, 255, 0))
            self.screen.blit(ok, (box.x + 20, box.y + 130))

    def run(self):
        while True:
            self.screen.fill(WHITE)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.speichern()
                    pygame.quit()
                    sys.exit()
                self.handle_input(event)

            # Grüner Innenbereich des Fußballplatzes
            offset = (WIDTH - BOARD_SIZE) // 2
            pygame.draw.rect(self.screen, GREEN, (offset, offset, BOARD_SIZE, BOARD_SIZE))

            # Spielfelder rendern
            for field in self.fields:
                if field:
                    field.draw(self.screen)

            # Spielfiguren rendern
            for player in self.players:
                player.draw(self.screen, self.fields)

            # Kontostände und Infotexte
            self.draw_ui()

            # Dialog- / Kartenbox im Zentrum
            self.draw_message_box()

            pygame.display.flip()
            self.clock.tick(FPS)


# ================= EXECUTION =================
if __name__ == "__main__":
    game = MonopolyGUI()
    game.run()