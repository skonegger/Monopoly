import pygame
import sys
import random

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

# --- GRUNDGERÜST ---

class Field:
    def __init__(self, name, x, y, f_type="Verein"):
        self.name = name
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.f_type = f_type

    def draw(self, surface):
        pygame.draw.rect(surface, BLACK, self.rect, 2)
        # Kurzer Name auf dem Feld anzeigen
        font = pygame.font.SysFont("Arial", 12)
        text = font.render(self.name[:8], True, BLACK)
        surface.blit(text, (self.rect.x + 5, self.rect.y + 5))

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

        # 1. Setup: Spieler-Eingabe (vereinfacht für Prototyp)
        self.players = [
            Player("Spieler 1", RED),
            Player("Spieler 2", BLUE)
        ]
        self.current_player_idx = 0

        # 2. Board erstellen (nur die Ecken und Kanten)
        self.fields = self._generate_fields()

    def _generate_fields(self):
        fields = []
        # Offset, um das Board mittig zu platzieren
        offset = (WIDTH - BOARD_SIZE) // 2
    
        # Unten Rechts nach Unten Links
        for i in range(11):
            fields.append(Field(f"Feld {len(fields)}", offset + BOARD_SIZE - (i+1)*TILE_SIZE, offset + BOARD_SIZE - TILE_SIZE))
        # Unten Links nach Oben Links
        for i in range(1, 10):
            fields.append(Field(f"Feld {len(fields)}", offset, offset + BOARD_SIZE - (i+1)*TILE_SIZE))
        # Oben Links nach Oben Rechts
        for i in range(11):
            fields.append(Field(f"Feld {len(fields)}", offset + i*TILE_SIZE, offset))
        # Oben Rechts nach Unten Rechts
        for i in range(1, 10):
            fields.append(Field(f"Feld {len(fields)}", offset + BOARD_SIZE - TILE_SIZE, offset + i*TILE_SIZE))
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
            