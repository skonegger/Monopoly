import pygame
import sys
import random
import json

# --- KONFIGURATION & FARBEN ---
WIDTH, HEIGHT = 800, 800
BOARD_SIZE = 600
TILE_SIZE = BOARD_SIZE // 11
FPS = 60

WHITE = (255, 255, 255)
GREEN = (34, 139, 34) 
BLACK = (0, 0, 0)
RED   = (200, 0, 0)
BLUE  = (0, 0, 200)

# Erweitere deine Farbkonstanten
COLORS = {
    "group_1": (128, 0, 128),   # Lila (Österreich)
    "group_2": (255, 165, 0),   # Orange (Niederlande)
    "group_3": (64, 224, 208),  # Türkis (Portugal)
    "group_4": (173, 216, 230), # Hellblau (Frankreich)
    "group_5": (255, 0, 0),     # Rot (Bundesliga)
    "group_6": (255, 255, 0),   # Gelb (Serie A)
    "group_7": (255, 192, 203), # Pink (Premier League)
    "group_8": (0, 0, 139),     # Dunkelblau (Spanien)
    "TV": (0, 0, 0),            # Schwarz
    "card": (0, 255, 0),        # Grün (VAR/Prämie)
    "utility": (169, 169, 169), # Grau (Sponsoren)
    "default": (200, 200, 200)  # Standard-Grau für LOS/Steuern
}

# --- GRUNDGERÜST ---

class Field:
    def __init__(self, data, x, y):
        self.data = data
        self.name = data["name"]
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.color = self._determine_color()

    def _determine_color(self):
        f_type = self.data.get("type")
        group = self.data.get("group")
        
        if f_type == "property" and group:
            return COLORS.get(f"group_{group}", COLORS["default"])
        return COLORS.get(f_type, COLORS["default"])

    def draw(self, surface):
        # Hintergrund des Feldes
        pygame.draw.rect(surface, WHITE, self.rect)
        # Farbbalken oben am Feld
        header_height = 15
        header_rect = pygame.Rect(self.rect.x, self.rect.y, TILE_SIZE, header_height)
        pygame.draw.rect(surface, self.color, header_rect)
        # Rahmen
        pygame.draw.rect(surface, BLACK, self.rect, 2)
        
        # Name anzeigen
        font = pygame.font.SysFont("Arial", 10, bold=True)
        # Text umbrechen oder kürzen, falls zu lang
        text = font.render(self.name[:10], True, BLACK)
        surface.blit(text, (self.rect.x + 5, self.rect.y + 20))

class Player:
    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.position = 0 
        self.money = 1500

    def draw(self, surface, fields):
        # Zeichne den Spieler als Kreis auf dem aktuellen Feld
        field_rect = fields[self.position].rect
        center = field_rect.center
        pygame.draw.circle(surface, self.color, center, 15)

# --- GUI ---

class MonopolyGUI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fußball-Monopoly Prototyp")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 24)
        self.nations_data = self._load_nations()
        self.show_nation_selection = False
        self.selectable_nations = []
        self.players = [
            Player("Spieler 1", RED),
            Player("Spieler 2", BLUE)
        ]
        self.current_player_idx = 0
        # 2. Board erstellen (nur die Ecken und Kanten)
        self.fields = self._generate_fields()

    def _load_nations(self):
        with open('football_nations_monopoly.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def trigger_nation_selection(self):
        # Wählt 3 zufällige Nationen aus
        self.selectable_nations = random.sample(self.nations_data, 3)
        self.show_nation_selection = True

    def draw_nation_cards(self):
        if not self.show_nation_selection:
            return

        # Hintergrund-Overlay (halbtransparent)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Zeichne 3 Karten
        card_width = 180
        card_height = 250
        start_x = (WIDTH - (3 * card_width + 40)) // 2
        
        for i, nation in enumerate(self.selectable_nations):
            card_rect = pygame.Rect(start_x + i * (card_width + 20), HEIGHT // 2 - 125, card_width, card_height)
            pygame.draw.rect(self.screen, (240, 240, 240), card_rect, border_radius=10)
            pygame.draw.rect(self.screen, BLACK, card_rect, 2, border_radius=10)

            # Text auf Karte (Nation, Positiv, Negativ)[cite: 1]
            name_text = self.font.render(nation['name'], True, BLACK)
            self.screen.blit(name_text, (card_rect.x + 10, card_rect.y + 10))
            
            # Effekte (vereinfacht für UI)
            small_font = pygame.font.SysFont("Arial", 12)
            pos_text = small_font.render(f"+ {nation['positive_effect'][:25]}...", True, (0, 100, 0))
            neg_text = small_font.render(f"- {nation['negative_effect'][:25]}...", True, (150, 0, 0))
            self.screen.blit(pos_text, (card_rect.x + 10, card_rect.y + 60))
            self.screen.blit(neg_text, (card_rect.x + 10, card_rect.y + 100))

    def _load_board_data(self):
        with open('spielfeld.json', 'r', encoding='utf-8') as f:
            return json.load(f)["board"]

    def _generate_fields(self):
        board_data = self._load_board_data()
        fields = [None] * 40
        offset = (WIDTH - BOARD_SIZE) // 2

        for data in board_data:
            i = data["id"]
            
            # UNTEN (0 bis 10): Von Rechts nach Links
            if 0 <= i <= 10:
                x = offset + BOARD_SIZE - (i + 1) * TILE_SIZE
                y = offset + BOARD_SIZE - TILE_SIZE
            
            # LINKS (11 bis 20): Von Unten nach Oben
            elif 11 <= i <= 20:
                x = offset
                y = offset + BOARD_SIZE - ((i - 10) + 1) * TILE_SIZE
            
            # OBEN (21 bis 30): Von Links nach Rechts
            elif 21 <= i <= 30:
                x = offset + (i - 20) * TILE_SIZE
                y = offset
            
            # RECHTS (31 bis 39): Von Oben nach Unten
            else:
                x = offset + BOARD_SIZE - TILE_SIZE
                # i-30 berechnet den Abstand zur Ecke oben rechts (ID 30)
                # Wir multiplizieren mit TILE_SIZE, damit Feld 31 genau unter Feld 30 liegt
                y = offset + (i - 30) * TILE_SIZE
            
            fields[i] = Field(data, x, y)
        return fields

    def run(self):
        while True:
            self.screen.fill(WHITE)
            
            # Events verarbeiten
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE: # Würfeln simulieren
                        steps = random.randint(1, 6) + random.randint(1, 6)
                        p = self.players[self.current_player_idx]
                        p.position = (p.position + steps) % len(self.fields)
                        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

            # Spielfeld zeichnen
            pygame.draw.rect(self.screen, GREEN, ((WIDTH-BOARD_SIZE)//2, (HEIGHT-BOARD_SIZE)//2, BOARD_SIZE, BOARD_SIZE))
            for f in self.fields:
                f.draw(self.screen)

            # Spieler zeichnen
            for p in self.players:
                p.draw(self.screen, self.fields)

            # UI Text
            info_text = self.font.render(f"Dran: {self.players[self.current_player_idx].name} (Leertaste zum Ziehen)", True, BLACK)
            self.screen.blit(info_text, (20, 20))

            pygame.display.flip()
            self.clock.tick(FPS)

if __name__ == "__main__":
    game = MonopolyGUI()
    game.run()
            