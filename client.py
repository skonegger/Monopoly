"""
client.py – Fußball Monopoly Multiplayer Client
================================================
Startet mit: python client.py [--host 127.0.0.1] [--port 5555]

Der Client empfängt den vollständigen Spielzustand vom Server und
rendert ihn mit Pygame. Eingaben werden als JSON-Aktionen gesendet.
"""

import pygame
import sys
import json
import socket
import threading
import argparse

# ── Konstanten (müssen mit constants.py übereinstimmen) ─────────────────────
WIDTH, HEIGHT = 900, 900
BOARD_SIZE    = 700
TILE_SIZE     = BOARD_SIZE // 11
FPS           = 30

WHITE  = (255, 255, 255)
BLACK  = (  0,   0,   0)
GREEN  = ( 34, 139,  34)
RED    = (200,   0,   0)
BLUE   = (  0,   0, 200)
DARK   = ( 30,  30,  30)

GROUP_COLORS = {
    1: (128,   0, 128), 2: (255, 165,   0), 3: ( 64, 224, 208),
    4: (173, 216, 230), 5: (255,   0,   0), 6: (255, 255,   0),
    7: (255, 192, 203), 8: (  0,   0, 139),
}
PLAYER_COLORS = [RED, BLUE]


# ── Netzwerk-Thread ──────────────────────────────────────────────────────────
class NetworkClient:
    def __init__(self, host, port):
        self.sock      = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.player_id = None
        self.state     = None          # letzter Snapshot
        self.lock      = threading.Lock()
        self._buf      = b""
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def _recv_loop(self):
        while True:
            try:
                chunk = self.sock.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            self._buf += chunk
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                with self.lock:
                    if msg.get("type") == "assign":
                        self.player_id = msg["player_id"]
                    elif msg.get("type") == "state":
                        self.state = msg["state"]

    def send(self, obj):
        try:
            self.sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            pass

    def get_state(self):
        with self.lock:
            return self.state

    def get_player_id(self):
        with self.lock:
            return self.player_id


# ── Feld-Rendering ───────────────────────────────────────────────────────────
def field_rect(fid):
    offset = (WIDTH - BOARD_SIZE) // 2
    i = fid
    if 0  <= i <= 10: x = offset + BOARD_SIZE - (i + 1) * TILE_SIZE; y = offset + BOARD_SIZE - TILE_SIZE
    elif 11 <= i <= 20: x = offset;                                   y = offset + BOARD_SIZE - ((i - 10) + 1) * TILE_SIZE
    elif 21 <= i <= 30: x = offset + (i - 20) * TILE_SIZE;            y = offset
    else:               x = offset + BOARD_SIZE - TILE_SIZE;          y = offset + (i - 30) * TILE_SIZE
    return pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)


def draw_field(screen, fid, fdata, small_font):
    r = field_rect(fid)
    pygame.draw.rect(screen, WHITE, r)
    pygame.draw.rect(screen, BLACK, r, 1)

    g = fdata.get("group")
    if g and fdata.get("type") == "property":
        pygame.draw.rect(screen, GROUP_COLORS.get(g, (200, 200, 200)),
                         (r.x, r.y, r.width, 10))
        pygame.draw.rect(screen, BLACK, (r.x, r.y, r.width, 10), 1)

    words    = fdata.get("name", "").split(" ")
    y_offset = 12 if g else 4
    for word in words:
        txt = small_font.render(word, True, BLACK)
        screen.blit(txt, (r.x + 3, r.y + y_offset))
        y_offset += 10

    price = fdata.get("price", 0)
    owner = fdata.get("owner")
    if price > 0 and not owner:
        pt = small_font.render(f"{price}€", True, (100, 100, 100))
        screen.blit(pt, (r.x + 3, r.bottom - 12))

    if owner:
        dot_color = RED if "1" in owner else BLUE
        pygame.draw.circle(screen, dot_color, (r.right - 7, r.bottom - 7), 5)

    sl = fdata.get("stadium_level", 0)
    if fdata.get("type") == "property" and sl > 0:
        if sl <= 4:
            for i in range(sl):
                pygame.draw.rect(screen, (34, 139, 34),
                                 (r.x + 3 + i * 9, r.y + 1, 6, 4))
        else:
            pygame.draw.rect(screen, (255, 215, 0),
                             (r.x + 3, r.y + 1, r.width - 6, 5))


def draw_player(screen, pdata, pid, fields_snap):
    pos    = pdata["position"]
    fid    = int(pos)
    r      = field_rect(fid)
    offset = 8 if pid == 0 else -8
    color  = PLAYER_COLORS[pid]
    cx = r.centerx + offset
    cy = r.centery + offset
    pygame.draw.circle(screen, color, (cx, cy), 10)
    pygame.draw.circle(screen, BLACK, (cx, cy), 10, 2)


# ── Haupt-Render-Schleife ────────────────────────────────────────────────────
def draw_ui(screen, font, small_font, gs, my_pid):
    y = 15
    for i, p in enumerate(gs["players"]):
        parts = [f"{p['name']}: {p['money']}€"]
        if p["yellow_cards"] > 0:       parts.append(f"Gelb: {p['yellow_cards']}")
        if p["has_jail_free_card"] > 0:  parts.append(f"Frei: {p['has_jail_free_card']}")
        if p["is_in_jail"]:              parts.append("[GESPERRT]")
        elif p["turns_to_skip"] > 0:     parts.append(f"Aussetzen: {p['turns_to_skip']}")
        col = PLAYER_COLORS[i]
        txt = font.render("  ".join(parts), True, col)
        screen.blit(txt, (20, y))
        y += 30

    cur = gs["current"]
    cur_name = gs["players"][cur]["name"]
    if not gs["has_rolled"]:
        ts = f"Dran: {cur_name}  [LEERTASTE] Würfeln"
    else:
        ts = f"Dran: {cur_name}  [E] Zug beenden"

    # Eigener Zug oder warten?
    if my_pid is not None and my_pid != cur:
        ts += "  (Warte auf Gegner…)"

    screen.blit(font.render(ts, True, BLACK), (20, y + 10))
    screen.blit(font.render(f"Wurf: {gs['last_dice']}", True, BLACK), (20, y + 45))

    shortcuts = small_font.render(
        "[SPACE] Würfeln  |  [E] Beenden  |  [B] Bauen  |  [R] Reset",
        True, BLACK
    )
    screen.blit(shortcuts, (20, HEIGHT - 35))

    # Spieler-ID anzeigen
    if my_pid is not None:
        id_txt = small_font.render(f"Du bist: Spieler {my_pid + 1}", True, (80, 80, 80))
        screen.blit(id_txt, (WIDTH - 160, 15))


def draw_message_box(screen, small_font, gs):
    msg   = gs.get("message", "")
    state = gs.get("state", "IDLE")
    if not msg and state not in ("BUY", "JAIL", "BUILD"):
        return

    box = pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 95, 520, 190)
    pygame.draw.rect(screen, DARK, box, border_radius=8)
    pygame.draw.rect(screen, WHITE, box, 2, border_radius=8)

    lines  = msg.split("\n")
    y      = box.y + 18
    for line in lines:
        txt = small_font.render(line, True, WHITE)
        screen.blit(txt, (box.x + 20, y))
        y += 26

    by = box.y + 148
    if state == "BUY":
        screen.blit(small_font.render("[J] JA  –  Kaufen",  True, (0, 255, 0)),  (box.x + 20,  by))
        screen.blit(small_font.render("[N] NEIN  –  Ablehnen", True, (255, 80, 80)), (box.x + 200, by))
    elif state == "JAIL":
        p = gs["players"][gs["current"]]
        lbl = "[J] Freikarte" if p["has_jail_free_card"] > 0 else "[J] 50€ zahlen"
        screen.blit(small_font.render(lbl,                True, (0, 255, 0)),   (box.x + 20,  by))
        screen.blit(small_font.render("[N] Pasch würfeln", True, (255, 255, 0)), (box.x + 220, by))
    elif state == "BUILD":
        screen.blit(small_font.render("[J] Bauen",   True, (0, 255, 0)),   (box.x + 20,  by))
        screen.blit(small_font.render("[N] Nächster",True, (255, 255, 0)), (box.x + 150, by))
        screen.blit(small_font.render("[E] Beenden", True, (255, 80, 80)), (box.x + 310, by))
    else:
        screen.blit(small_font.render("[J] OK / Weiter", True, (0, 255, 0)), (box.x + 20, by))


# ── Eingabe-Verarbeitung ─────────────────────────────────────────────────────
def handle_key(net, key, gs, my_pid):
    cur   = gs["current"]
    state = gs["state"]

    # Nur eigene Eingaben senden
    if my_pid is not None and my_pid != cur:
        return

    if key == pygame.K_r:
        net.send({"action": "reset"})
        return

    if state == "MESSAGE":
        if key == pygame.K_j:
            net.send({"action": "confirm_message"})
        return

    if state == "BUILD":
        if key == pygame.K_j:   net.send({"action": "build"})
        elif key == pygame.K_n: net.send({"action": "build_next"})
        elif key == pygame.K_e: net.send({"action": "build_cancel"})
        return

    if state == "BUY":
        if key == pygame.K_j:   net.send({"action": "buy", "answer": True})
        elif key == pygame.K_n: net.send({"action": "buy", "answer": False})
        return

    p = gs["players"][cur]
    if state == "JAIL" or (state == "IDLE" and p["is_in_jail"]):
        if key == pygame.K_j:
            choice = "pay"  # zahlen oder Freikarte
        elif key == pygame.K_n:
            choice = "roll"
        else:
            choice = None
        if choice:
            net.send({"action": "jail", "choice": choice})
        return

    if state == "IDLE":
        if key == pygame.K_SPACE and not gs["has_rolled"]:
            net.send({"action": "roll"})
        elif key == pygame.K_e and gs["has_rolled"]:
            net.send({"action": "end_turn"})
        elif key == pygame.K_b:
            net.send({"action": "open_build"})


# ── Haupt-Einstiegspunkt ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Fußball Monopoly Client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    print(f"[CLIENT] Verbinde mit {args.host}:{args.port} …")
    net = NetworkClient(args.host, args.port)
    print("[CLIENT] Verbunden! Warte auf Spielzustand …")

    pygame.init()
    screen     = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Fußball Monopoly – Multiplayer")
    clock      = pygame.time.Clock()
    font       = pygame.font.SysFont("Arial", 22)
    small_font = pygame.font.SysFont("Arial", 9)
    ui_font    = pygame.font.SysFont("Arial", 16)

    # Warte-Bildschirm
    waiting_font = pygame.font.SysFont("Arial", 32)

    while True:
        gs  = net.get_state()
        pid = net.get_player_id()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and gs:
                handle_key(net, event.key, gs, pid)

        screen.fill(WHITE)

        if gs is None:
            # Noch kein State empfangen
            txt = waiting_font.render("Warte auf Mitspieler …", True, BLACK)
            screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2))
        else:
            # Brett zeichnen
            offset = (WIDTH - BOARD_SIZE) // 2
            pygame.draw.rect(screen, GREEN, (offset, offset, BOARD_SIZE, BOARD_SIZE))

            for fid_str, fdata in gs["fields"].items():
                draw_field(screen, int(fid_str), fdata, small_font)

            for i, p in enumerate(gs["players"]):
                draw_player(screen, p, i, gs["fields"])

            draw_ui(screen, font, ui_font, gs, pid)
            draw_message_box(screen, ui_font, gs)

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
