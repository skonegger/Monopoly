import sys
import socket
import threading
import json
import struct

import pygame

# ---------------------------------------------------------------------------
# Serveradresse  ← hier anpassen falls nötig
# ---------------------------------------------------------------------------
SERVER_IP = "10.95.130.45"
PORT      = 5555

# ---------------------------------------------------------------------------
# Fenster & Brett  (identisch mit dem Original)
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 900, 900
FPS           = 60

TILE_SIZE  = 75
INNER_SIZE = 360
BOARD_SIZE = INNER_SIZE + 2 * TILE_SIZE   # 510
SIDE_TILE  = INNER_SIZE // 9              # 40

# ---------------------------------------------------------------------------
# Farben
# ---------------------------------------------------------------------------
WHITE  = (255, 255, 255)
GREEN  = ( 34, 139,  34)
BLACK  = (  0,   0,   0)
RED    = (200,   0,   0)
BLUE   = (  0,   0, 200)
GRAY   = (160, 160, 160)

PLAYER_COLORS = [RED, BLUE]

COLORS = {
    "group_1": (128,   0, 128),
    "group_2": (255, 165,   0),
    "group_3": ( 64, 224, 208),
    "group_4": (173, 216, 230),
    "group_5": (255,   0,   0),
    "group_6": (255, 255,   0),
    "group_7": (255, 192, 203),
    "group_8": (  0,   0, 139),
    "TV":      (  0,   0,   0),
    "card":    (  0, 255,   0),
    "utility": (169, 169, 169),
    "default": (200, 200, 200),
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def field_color(f):
    f_type = f.get("type")
    group  = f.get("group")
    if f_type == "property" and group:
        return COLORS.get(f"group_{group}", COLORS["default"])
    return COLORS.get(f_type, COLORS["default"])


def field_rect(i):
    """Gibt pygame.Rect für Feld i zurück – identische Logik wie im Original."""
    off = (WIDTH - BOARD_SIZE) // 2
    T   = TILE_SIZE
    S   = SIDE_TILE

    if i == 0:
        x, y, w, h = off + BOARD_SIZE - T, off + BOARD_SIZE - T, T, T
    elif 1 <= i <= 9:
        x = off + T + (9 - i) * S
        y, w, h = off + BOARD_SIZE - T, S, T
    elif i == 10:
        x, y, w, h = off, off + BOARD_SIZE - T, T, T
    elif 11 <= i <= 19:
        y = off + T + (9 - (i - 10)) * S
        x, w, h = off, T, S
    elif i == 20:
        x, y, w, h = off, off, T, T
    elif 21 <= i <= 29:
        x = off + T + (i - 21) * S
        y, w, h = off, S, T
    elif i == 30:
        x, y, w, h = off + BOARD_SIZE - T, off, T, T
    else:                      # 31–39
        y = off + T + (i - 31) * S
        x, w, h = off + BOARD_SIZE - T, T, S

    return pygame.Rect(x, y, w, h)


def _recvall(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def send_msg(conn, data):
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    conn.sendall(struct.pack(">I", len(payload)) + payload)


def recv_msg(conn):
    raw = _recvall(conn, 4)
    if not raw:
        return None
    n       = struct.unpack(">I", raw)[0]
    raw_data = _recvall(conn, n)
    return json.loads(raw_data.decode("utf-8")) if raw_data else None


def wrap_text(text, font, max_width):
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = line + word + " "
        if font.size(test)[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line.rstrip())
            line = word + " "
    if line:
        lines.append(line.rstrip())
    return lines


# ---------------------------------------------------------------------------
# Client-Klasse
# ---------------------------------------------------------------------------

class MonopolyClient:

    def __init__(self):
        pygame.init()
        self.screen      = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fußball-Monopoly – Multiplayer")
        self.clock       = pygame.time.Clock()
        self.font        = pygame.font.SysFont("Arial", 22)
        self.dialog_font = pygame.font.SysFont("Arial", 18)
        self.small_font  = pygame.font.SysFont("Arial",  9, bold=True)
        self.tiny_font   = pygame.font.SysFont("Arial",  8, bold=True)

        # Netzwerk
        print(f"Verbinde mit {SERVER_IP}:{PORT} …")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_IP, PORT))
        print("Verbunden! Warte auf Spielerzuweisung …")

        self.player_id  = None
        self.state      = None
        self.state_lock = threading.Lock()
        self.connected  = True

        t = threading.Thread(target=self._receive_loop, daemon=True)
        t.start()

        # Warten bis Zuweisung angekommen ist
        while self.player_id is None:
            pygame.time.wait(50)
        print(f"Du bist Spieler {self.player_id + 1}!")

    # ------------------------------------------------------------------
    # Netzwerk-Empfang (läuft in eigenem Thread)
    # ------------------------------------------------------------------
    def _receive_loop(self):
        while self.connected:
            try:
                msg = recv_msg(self.sock)
                if msg is None:
                    self.connected = False
                    break
                if msg["type"] == "assign":
                    self.player_id = msg["player_id"]
                elif msg["type"] == "state":
                    with self.state_lock:
                        self.state = msg["data"]
            except Exception as e:
                print(f"Verbindungsfehler: {e}")
                self.connected = False

    def _send_action(self, action):
        try:
            send_msg(self.sock, {"type": "action", "action": action})
        except Exception as e:
            print(f"Sendefehler: {e}")

    def _send_reset(self):
        try:
            send_msg(self.sock, {"type": "reset"})
        except Exception as e:
            print(f"Sendefehler: {e}")

    # ------------------------------------------------------------------
    # Zeichenmethoden
    # ------------------------------------------------------------------

    def _draw_board(self, state):
        off = (WIDTH - BOARD_SIZE) // 2
        pygame.draw.rect(self.screen, GREEN, (off, off, BOARD_SIZE, BOARD_SIZE))
        pygame.draw.rect(
            self.screen, GREEN,
            (off + TILE_SIZE, off + TILE_SIZE, INNER_SIZE, INNER_SIZE),
        )

        for i in range(40):
            f    = state["fields"][str(i)]
            rect = field_rect(i)
            col  = field_color(f)

            # Hintergrund & Farbstreifen
            pygame.draw.rect(self.screen, WHITE, rect)
            stripe_size = 10
            if rect.width >= rect.height:
                stripe = pygame.Rect(rect.x, rect.y, rect.width, stripe_size)
            else:
                stripe = pygame.Rect(rect.x, rect.y, stripe_size, rect.height)
            pygame.draw.rect(self.screen, col, stripe)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

            # Name
            label = f["name"][:10]
            self.screen.blit(
                self.small_font.render(label, True, BLACK),
                (rect.x + 3, rect.y + stripe_size + 3),
            )

            # Besitzer
            if f["owner"]:
                self.screen.blit(
                    self.tiny_font.render(f"P:{f['owner'][0]}", True, (50, 50, 50)),
                    (rect.x + 3, rect.bottom - 11),
                )

    def _draw_players(self, state):
        for i, p in enumerate(state["players"]):
            rect     = field_rect(p["position"])
            cx, cy   = rect.center
            offset_x = -10 if i == 0 else 10
            pygame.draw.circle(self.screen, PLAYER_COLORS[i], (cx + offset_x, cy), 12)
            pygame.draw.circle(self.screen, BLACK,             (cx + offset_x, cy), 12, 2)

    def _draw_buy_dialog(self, state):
        if state["phase"] != "buy_prompt":
            return
        field  = state["fields"][str(state["buy_field_id"])]
        cp     = state["current_player"]
        player = state["players"][cp]

        dialog_rect = pygame.Rect(WIDTH // 2 - 180, HEIGHT // 2 - 80, 360, 160)
        pygame.draw.rect(self.screen, (245, 245, 245), dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, BLACK,           dialog_rect, 2, border_radius=8)

        self.screen.blit(
            self.dialog_font.render(f"{player['name']} gelandet auf:", True, BLACK),
            (dialog_rect.x + 20, dialog_rect.y + 20),
        )
        self.screen.blit(
            self.dialog_font.render(f"{field['name']} ({field['price']}€)", True, BLACK),
            (dialog_rect.x + 20, dialog_rect.y + 55),
        )

        if self.player_id == cp:
            self.screen.blit(
                self.dialog_font.render("[J] Kaufen  /  [N] Ablehnen", True, (0, 120, 0)),
                (dialog_rect.x + 20, dialog_rect.y + 110),
            )
        else:
            self.screen.blit(
                self.dialog_font.render("Warte auf Entscheidung …", True, GRAY),
                (dialog_rect.x + 20, dialog_rect.y + 110),
            )

    def _draw_card_dialog(self, state):
        if state["phase"] != "card" or not state.get("active_card"):
            return
        text  = state["active_card"]
        lines = wrap_text(text, self.dialog_font, 400)
        box_h = 30 + len(lines) * 25 + 35

        dialog_rect = pygame.Rect(WIDTH // 2 - 220, HEIGHT // 2 - box_h // 2, 440, box_h)
        pygame.draw.rect(self.screen, (245, 245, 245), dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, BLACK,           dialog_rect, 2, border_radius=8)

        for idx, line in enumerate(lines):
            self.screen.blit(
                self.dialog_font.render(line, True, BLACK),
                (dialog_rect.x + 20, dialog_rect.y + 15 + idx * 25),
            )

        cp = state["current_player"]
        if self.player_id == cp:
            self.screen.blit(
                self.dialog_font.render("[Beliebige Taste] Weiter", True, (0, 120, 0)),
                (dialog_rect.x + 20, dialog_rect.bottom - 28),
            )
        else:
            self.screen.blit(
                self.dialog_font.render("Warte auf anderen Spieler …", True, GRAY),
                (dialog_rect.x + 20, dialog_rect.bottom - 28),
            )

    def _draw_hud(self, state):
        off = (WIDTH - BOARD_SIZE) // 2
        cp  = state["current_player"]

        # Dran-Anzeige
        cp_name    = state["players"][cp]["name"]
        is_my_turn = self.player_id == cp
        turn_text  = (
            f"Dran: {cp_name}  (Leertaste = Würfeln)"
            if is_my_turn
            else f"Dran: {cp_name}  – bitte warten …"
        )
        self.screen.blit(
            self.font.render(turn_text, True, PLAYER_COLORS[cp]),
            (20, off - 32),
        )

        # Spieler-Info
        y = off + BOARD_SIZE + 10
        for i, p in enumerate(state["players"]):
            suffix = "  ← DU" if i == self.player_id else ""
            label  = (
                f"{p['name']}: {p['money']}€  |  "
                f"Feld: {state['fields'][str(p['position'])]['name']}{suffix}"
            )
            self.screen.blit(
                self.font.render(label, True, PLAYER_COLORS[i]),
                (20, y),
            )
            y += 28

        self.screen.blit(
            self.font.render("[R] Neu starten", True, BLACK),
            (20, y + 6),
        )

        # Log-Zeile
        log = state.get("log", "")
        self.screen.blit(
            pygame.font.SysFont("Arial", 15).render(log[-90:], True, (60, 60, 60)),
            (20, off - 54),
        )

        # Eigene Spieler-Farbe als kleiner Indikator oben rechts
        my_name = state["players"][self.player_id]["name"]
        self.screen.blit(
            self.dialog_font.render(f"Du:  {my_name}", True, PLAYER_COLORS[self.player_id]),
            (WIDTH - 195, off - 32),
        )

    # ------------------------------------------------------------------
    # Hauptschleife
    # ------------------------------------------------------------------

    def run(self):
        while True:
            self.screen.fill(WHITE)
            self.clock.tick(FPS)

            # --- Verbindung verloren ---
            if not self.connected:
                self.screen.blit(
                    self.font.render("❌ Verbindung zum Server verloren!", True, RED),
                    (WIDTH // 2 - 230, HEIGHT // 2),
                )
                pygame.display.flip()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit(); sys.exit()
                continue

            # --- Warten auf State ---
            with self.state_lock:
                state = self.state

            if state is None:
                msg = (
                    "Verbunden – warte auf zweiten Spieler …"
                    if self.player_id is not None
                    else "Verbinde …"
                )
                self.screen.blit(self.font.render(msg, True, BLACK), (WIDTH // 2 - 230, HEIGHT // 2))
                pygame.display.flip()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit(); sys.exit()
                continue

            cp         = state["current_player"]
            phase      = state["phase"]
            is_my_turn = self.player_id == cp

            # --- Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.sock.close()
                    pygame.quit(); sys.exit()

                if event.type == pygame.KEYDOWN:

                    # Karte wegklicken
                    if phase == "card" and is_my_turn:
                        self._send_action("dismiss_card")

                    # Kaufen-Dialog
                    elif phase == "buy_prompt" and is_my_turn:
                        if event.key == pygame.K_j:
                            self._send_action("buy")
                        elif event.key == pygame.K_n:
                            self._send_action("decline")

                    # Würfeln
                    elif phase == "roll" and is_my_turn and event.key == pygame.K_SPACE:
                        self._send_action("roll")

                    # Neu starten (jeder kann)
                    elif event.key == pygame.K_r:
                        self._send_reset()

            # --- Brett zeichnen ---
            self._draw_board(state)
            self._draw_players(state)
            self._draw_hud(state)
            self._draw_buy_dialog(state)
            self._draw_card_dialog(state)

            pygame.display.flip()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    MonopolyClient().run()
