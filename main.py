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
        # Besitzer direkt im Feld-Objekt verwalten
        self.owner = data.get("owner") 
        self.price = data.get("price", 0)
        self.rent = data.get("rent", 0)

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
        text = font.render(self.name[:10], True, BLACK)
        surface.blit(text, (self.rect.x + 5, self.rect.y + 20))
        
        # Wenn das Feld gekauft wurde, zeichne eine kleine Markierung
        if self.owner:
            owner_font = pygame.font.SysFont("Arial", 9, bold=True)
            owner_text = owner_font.render(f"P: {self.owner}", True, (50, 50, 50))
            surface.blit(owner_text, (self.rect.x + 5, self.rect.y + TILE_SIZE - 12))

class Player:
    def __init__(self, name, color, id_num):
        self.name = name
        self.color = color
        self.id_num = id_num
        self.position = 0 
        self.money = 1500
        self.vereine = []

    def draw(self, surface, fields):
        field_rect = fields[self.position].rect
        center = field_rect.center
        # Leicht versetzen je nach Spieler-ID, damit sie sich auf demselben Feld nicht komplett verdecken
        offset_x = -10 if self.id_num == 1 else 10
        pygame.draw.circle(surface, self.color, (center[0] + offset_x, center[1]), 12)

# --- GUI ---

class MonopolyGUI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fußball-Monopoly Prototyp")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 22)
        self.dialog_font = pygame.font.SysFont("Arial", 18)
        self.nations_data = self._load_nations()
        self.show_nation_selection = False
        self.selectable_nations = []
        
        self.players = [
            Player("Spieler 1", RED, 1),
            Player("Spieler 2", BLUE, 2)
        ]
        self.current_player_idx = 0
        self.fields = self._generate_fields()
        
        # Interaktions-Variablen für Käufe
        self.active_buy_prompt = False
        self.current_field_to_buy = None

    def _load_nations(self):
        with open('football_nations_monopoly.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_board_data(self):
        with open('spielfeld.json', 'r', encoding='utf-8') as f:
            return json.load(f)["board"]

    def _generate_fields(self):
        board_data = self._load_board_data()
        fields = [None] * 40
        offset = (WIDTH - BOARD_SIZE) // 2

        for data in board_data:
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

    def handle_field_landing(self, player):
        """Prüft das Feld, auf dem der Spieler gelandet ist, und triggert Aktionen."""
        field = self.fields[player.position]
        f_type = field.data.get("type")

        # Falls es ein kaufbares Feld ist (property oder TV)
        if f_type in ["property", "TV"]:
            if field.owner is None:
                # Feld ist frei -> Kauf-Prompt aktivieren
                self.active_buy_prompt = True
                self.current_field_to_buy = field
            elif field.owner != player.name:
                # Feld gehört einem Gegner -> Miete zahlen!
                rent = field.rent
                player.money -= rent
                # Dem Besitzer das Geld gutschreiben
                for p in self.players:
                    if p.name == field.owner:
                        p.money += rent
                print(f"{player.name} bezahlt {rent}€ Miete an {field.owner} für {field.name}.")

    def draw_buy_dialog(self):
        """Zeigt in der Mitte des Spielfelds den Kaufdialog an."""
        if not self.active_buy_prompt or not self.current_field_to_buy:
            return

        # Dialog-Box im Zentrum zeichnen
        dialog_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 - 75, 300, 150)
        pygame.draw.rect(self.screen, (245, 245, 245), dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, BLACK, dialog_rect, 2, border_radius=8)

        field = self.current_field_to_buy
        p_name = self.players[self.current_player_idx].name

        # Texte rendern
        line1 = self.dialog_font.render(f"{p_name} gelandet auf:", True, BLACK)
        line2 = self.dialog_font.render(f"{field.name} ({field.price}€)", True, BLACK)
        line3 = self.dialog_font.render("[J] Kaufen  /  [N] Ablehnen", True, (0, 100, 0))

        self.screen.blit(line1, (dialog_rect.x + 20, dialog_rect.y + 20))
        self.screen.blit(line2, (dialog_rect.x + 20, dialog_rect.y + 50))
        self.screen.blit(line3, (dialog_rect.x + 20, dialog_rect.y + 100))

    def run(self):
        while True:
            self.screen.fill(WHITE)
            current_player = self.players[self.current_player_idx]
            
            # Events verarbeiten
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                    
                if event.type == pygame.KEYDOWN:
                    # Wenn gerade ein Kauf abgefragt wird, sind andere Tasten gesperrt
                    if self.active_buy_prompt:
                        if event.key == pygame.K_j:  # JA - Kaufen
                            if current_player.money >= self.current_field_to_buy.price:
                                current_player.money -= self.current_field_to_buy.price
                                self.current_field_to_buy.owner = current_player.name
                                current_player.vereine.append(self.current_field_to_buy.name)
                                print(f"{current_player.name} kauft {self.current_field_to_buy.name}!")
                            else:
                                print("Nicht genug Geld!")
                            
                            # Prompt schließen und nächster Spieler ist dran
                            self.active_buy_prompt = False
                            self.current_field_to_buy = None
                            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
                            
                        elif event.key == pygame.K_n:  # NEIN - Ablehnen
                            self.active_buy_prompt = False
                            self.current_field_to_buy = None
                            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

                    # Normaler Spielzug (Würfeln), nur wenn kein Kaufdialog offen ist
                    elif event.key == pygame.K_SPACE: 
                        steps = random.randint(1, 6) + random.randint(1, 6)
                        current_player.position = (current_player.position + steps) % len(self.fields)
                        
                        # Feldaktion ausführen
                        self.handle_field_landing(current_player)
                        
                        # Wenn kein Kauf-Dialog ausgelöst wurde, direkt zum nächsten Spieler wechseln
                        if not self.active_buy_prompt:
                            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

            # Spielfeld zeichnen
            pygame.draw.rect(self.screen, GREEN, ((WIDTH-BOARD_SIZE)//2, (HEIGHT-BOARD_SIZE)//2, BOARD_SIZE, BOARD_SIZE))
            for f in self.fields:
                f.draw(self.screen)

            # Spieler zeichnen
            for p in self.players:
                p.draw(self.screen, self.fields)

            # UI Text (Spielerdaten oben anzeigen)
            y_offset = 20
            for p in self.players:
                status_text = self.font.render(f"{p.name}: {p.money}€  |  Feld: {self.fields[p.position].name}", True, p.color)
                self.screen.blit(status_text, (20, y_offset))
                y_offset += 30

            turn_text = self.font.render(f"Dran: {self.players[self.current_player_idx].name} (Leertaste)", True, BLACK)
            self.screen.blit(turn_text, (20, y_offset + 10))

            # Kaufdialog obendrüber zeichnen, falls aktiv
            self.draw_buy_dialog()

            pygame.display.flip()
            self.clock.tick(FPS)

if __name__ == "__main__":
    game = MonopolyGUI()
    game.run()