# Client.py
import pygame
import sys
import socket
import pickle
import threading
import json
from Shared import GameState

WIDTH, HEIGHT = 800, 800
BOARD_SIZE = 600
TILE_SIZE = BOARD_SIZE // 11
FPS = 60

WHITE = (255, 255, 255)
GREEN = (34, 139, 34)
BLACK = (0, 0, 0)

COLORS = {
    "group_1": (128, 0, 128), "group_2": (255, 165, 0), "group_3": (64, 224, 208),
    "group_4": (173, 216, 230), "group_5": (255, 0, 0), "group_6": (255, 255, 0),
    "group_7": (255, 192, 203), "group_8": (0, 0, 139), "TV": (0, 0, 0),
    "card": (0, 255, 0), "utility": (169, 169, 169), "default": (200, 200, 200)
}

SERVER_IP = "10.95.130.45"
PORT = 5555

class FieldGUI:
    def __init__(self, data, x, y):
        self.data = data
        self.name = data["name"]
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.price = data.get("price", 0)
        f_type = data.get("type")
        group = data.get("group")
        self.color = COLORS.get(f"group_{group}", COLORS["default"]) if f_type == "property" and group else COLORS.get(f_type, COLORS["default"])

    def draw(self, surface, owner_name):
        pygame.draw.rect(surface, WHITE, self.rect)
        pygame.draw.rect(surface, self.color, pygame.Rect(self.rect.x, self.rect.y, TILE_SIZE, 15))
        pygame.draw.rect(surface, BLACK, self.rect, 2)
        font = pygame.font.SysFont("Arial", 10, bold=True)
        surface.blit(font.render(self.name[:10], True, BLACK), (self.rect.x + 5, self.rect.y + 20))
        if owner_name:
            f2 = pygame.font.SysFont("Arial", 9, bold=True)
            surface.blit(f2.render(f"P: {owner_name}", True, (50, 50, 50)), (self.rect.x + 5, self.rect.y + TILE_SIZE - 12))

class MonopolyClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fußball-Monopoly Multiplayer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 22)
        self.dialog_font = pygame.font.SysFont("Arial", 18)
        
        self.game_state = None
        self.my_id = None
        self.fields = self._generate_fields()
        
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((SERVER_IP, PORT))
            self.my_id = pickle.loads(self.client_socket.recv(1024))
        except Exception as e:
            print(f"Verbindung fehlgeschlagen: {e}")
            pygame.quit()
            sys.exit()
            
        t = threading.Thread(target=self.receive_data)
        t.daemon = True
        t.start()

    def _generate_fields(self):
        try:
            with open('spielfeld.json', 'r', encoding='utf-8') as f:
                board_data = json.load(f)["board"]
        except Exception:
            board_data = [{"id": i, "name": f"Feld {i}", "type": "default"} for i in range(40)]
            
        fields = [None] * 40
        offset = (WIDTH - BOARD_SIZE) // 2
        for data in board_data:
            i = data["id"]
            if 0 <= i <= 10: x, y = offset + BOARD_SIZE - (i + 1) * TILE_SIZE, offset + BOARD_SIZE - TILE_SIZE
            elif 11 <= i <= 20: x, y = offset, offset + BOARD_SIZE - ((i - 10) + 1) * TILE_SIZE
            elif 21 <= i <= 30: x, y = offset + (i - 20) * TILE_SIZE, offset
            else: x, y = offset + BOARD_SIZE - TILE_SIZE, offset + (i - 30) * TILE_SIZE
            fields[i] = FieldGUI(data, x, y)
        return fields

    def receive_data(self):
        while True:
            try:
                data = self.client_socket.recv(16384)
                if not data: break
                state = pickle.loads(data)
                if isinstance(state, GameState): self.game_state = state
            except Exception: break

    def send_action(self, action):
        try: self.client_socket.sendall(pickle.dumps(action))
        except Exception: pass

    def draw_buy_dialog(self):
        if not self.game_state or not self.game_state.active_buy_prompt: return
        dialog_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 - 75, 300, 150)
        pygame.draw.rect(self.screen, (245, 245, 245), dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, BLACK, dialog_rect, 2, border_radius=8)
        
        field_idx = self.game_state.current_field_to_buy_idx
        field_gui = self.fields[field_idx]
        p_name = self.game_state.players[self.game_state.current_player_idx]["name"]
        
        self.screen.blit(self.dialog_font.render(f"{p_name} gelandet auf:", True, BLACK), (dialog_rect.x + 20, dialog_rect.y + 20))
        self.screen.blit(self.dialog_font.render(f"{field_gui.name} ({field_gui.price}€)", True, BLACK), (dialog_rect.x + 20, dialog_rect.y + 50))
        
        if self.my_id == self.game_state.current_player_idx:
            self.screen.blit(self.dialog_font.render("[J] Kaufen  /  [N] Ablehnen", True, (0, 100, 0)), (dialog_rect.x + 20, dialog_rect.y + 100))
        else:
            self.screen.blit(self.dialog_font.render("Warte auf Entscheidung...", True, (150, 50, 50)), (dialog_rect.x + 20, dialog_rect.y + 100))

    def draw_card_dialog(self):
        if not self.game_state or not self.game_state.active_card: return
        dialog_rect = pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 60, 400, 120)
        pygame.draw.rect(self.screen, (245, 245, 245), dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, BLACK, dialog_rect, 2, border_radius=8)
        
        words = self.game_state.active_card.split()
        lines, line = [], ""
        for w in words:
            if self.dialog_font.size(line + w)[0] < 360: line += w + " "
            else:
                lines.append(line)
                line = w + " "
        lines.append(line)
        for i, l in enumerate(lines):
            self.screen.blit(self.dialog_font.render(l, True, BLACK), (dialog_rect.x + 20, dialog_rect.y + 15 + i * 25))
            
        if self.my_id == self.game_state.current_player_idx:
            self.screen.blit(self.dialog_font.render("[Beliebige Taste zum Schließen]", True, (0, 100, 0)), (dialog_rect.x + 20, dialog_rect.y + 90))
        else:
            self.screen.blit(self.dialog_font.render("Spieler liest Karte...", True, (150, 50, 50)), (dialog_rect.x + 20, dialog_rect.y + 90))

    def run(self):
        while True:
            self.screen.fill(WHITE)
            if not self.game_state or not self.game_state.game_started:
                font_wait = pygame.font.SysFont("Arial", 30)
                text = font_wait.render("Warte auf Mitspieler...", True, BLACK)
                self.screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - text.get_height() // 2))
                pygame.display.flip()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                self.clock.tick(FPS)
                continue

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and self.my_id == self.game_state.current_player_idx:
                    if self.game_state.active_card: self.send_action("CLOSE_CARD")
                    elif self.game_state.active_buy_prompt:
                        if event.key == pygame.K_j: self.send_action("BUY_YES")
                        elif event.key == pygame.K_n: self.send_action("BUY_NO")
                    elif event.key == pygame.K_SPACE: self.send_action("DICE")

            pygame.draw.rect(self.screen, GREEN, ((WIDTH - BOARD_SIZE) // 2, (HEIGHT - BOARD_SIZE) // 2, BOARD_SIZE, BOARD_SIZE))
            for idx, f in enumerate(self.fields):
                owner = self.game_state.field_owners.get(str(idx))
                f.draw(self.screen, owner)
                
            for idx, p in enumerate(self.game_state.players):
                center = self.fields[p["position"]].rect.center
                offset_x = -10 if idx == 0 else 10
                pygame.draw.circle(self.screen, p["color"], (center[0] + offset_x, center[1]), 12)

            offset = (HEIGHT - BOARD_SIZE) // 2
            active_p_name = self.game_state.players[self.game_state.current_player_idx]["name"]
            status_text = f"DU BIST DRAN! ({active_p_name}) - Leertaste drücken" if self.my_id == self.game_state.current_player_idx else f"Warten auf: {active_p_name}..."
            self.screen.blit(self.font.render(status_text, True, BLACK), (20, offset - 30))

            y = offset + BOARD_SIZE + 10
            for idx, p in enumerate(self.game_state.players):
                prefix = "STOLZER BESITZER (Du): " if idx == self.my_id else ""
                f_name = self.fields[p["position"]].name
                self.screen.blit(self.font.render(f"{prefix}{p['name']}: {p['money']}€ | Feld: {f_name}", True, p["color"]), (20, y))
                y += 30

            self.draw_buy_dialog()
            self.draw_card_dialog()
            pygame.display.flip()
            self.clock.tick(FPS)

if __name__ == "__main__":
    MonopolyClient().run()