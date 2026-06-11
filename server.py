"""
Fußball-Monopoly – SERVER
Starte diesen Server auf dem Host-Rechner (IP: 10.95.130.45).
Beide Spieler starten danach client.py.

    python server.py
"""

import socket
import threading
import json
import random
import struct
import copy

PORT = 5555


# ---------------------------------------------------------------------------
# Netzwerk-Hilfsfunktionen  (length-prefixed JSON)
# ---------------------------------------------------------------------------

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
    n = struct.unpack(">I", raw)[0]
    raw_data = _recvall(conn, n)
    return json.loads(raw_data.decode("utf-8")) if raw_data else None


# ---------------------------------------------------------------------------
# Spielserver-Logik
# ---------------------------------------------------------------------------

class GameServer:
    def __init__(self):
        with open("spielfeld.json", "r", encoding="utf-8") as f:
            self._board_template = json.load(f)["board"]
        with open("cards.json", "r", encoding="utf-8") as f:
            self._cards_data = json.load(f)["cards"]
        with open("football_nations_monopoly.json", "r", encoding="utf-8") as f:
            self._nations_data = json.load(f)

        self.lock    = threading.Lock()
        self.clients = {}        # player_id (0 or 1) -> conn
        self.state   = self._init_state()

    # ------------------------------------------------------------------
    # State initialisieren
    # ------------------------------------------------------------------
    def _init_state(self):
        fields = {}
        for d in self._board_template:
            fid = str(d["id"])
            fields[fid] = {
                "id":    d["id"],
                "name":  d["name"],
                "type":  d.get("type", "default"),
                "group": d.get("group"),
                "price": d.get("price", 0),
                "rent":  d.get("rent",  0),
                "deck":  d.get("deck"),
                "owner": None,
            }
        return {
            "players": [
                {"name": "Spieler 1", "position": 0, "money": 1500, "vereine": []},
                {"name": "Spieler 2", "position": 0, "money": 1500, "vereine": []},
            ],
            "fields":       fields,
            "current_player": 0,
            "phase":         "roll",   # roll | buy_prompt | card
            "active_card":   None,
            "buy_field_id":  None,
            "log":           "Spiel gestartet! Spieler 1 ist dran.",
        }

    # ------------------------------------------------------------------
    # Broadcast an alle verbundenen Clients
    # ------------------------------------------------------------------
    def broadcast(self):
        msg  = {"type": "state", "data": self.state}
        dead = []
        for pid, conn in list(self.clients.items()):
            try:
                send_msg(conn, msg)
            except Exception as e:
                print(f"[Broadcast] Spieler {pid + 1} nicht erreichbar: {e}")
                dead.append(pid)
        for pid in dead:
            del self.clients[pid]

    # ------------------------------------------------------------------
    # Aktionen verarbeiten
    # ------------------------------------------------------------------
    def handle_action(self, player_id, action):
        with self.lock:
            s  = self.state
            cp = s["current_player"]

            # Nicht dein Zug → ignorieren
            if player_id != cp:
                return

            player = s["players"][cp]
            phase  = s["phase"]

            # --- Würfeln ---
            if phase == "roll" and action == "roll":
                d1   = random.randint(1, 6)
                d2   = random.randint(1, 6)
                roll = d1 + d2
                new_pos          = (player["position"] + roll) % 40
                player["position"] = new_pos
                field            = s["fields"][str(new_pos)]
                s["log"] = (
                    f"🎲 {player['name']} würfelt {roll} ({d1}+{d2}) → {field['name']}"
                )
                self._handle_landing(player, field, s)

            # --- Kaufen oder Ablehnen ---
            elif phase == "buy_prompt":
                field = s["fields"][str(s["buy_field_id"])]
                if action == "buy":
                    if player["money"] >= field["price"]:
                        player["money"]  -= field["price"]
                        field["owner"]    = player["name"]
                        player["vereine"].append(field["name"])
                        s["log"] = f"✅ {player['name']} kauft {field['name']} für {field['price']}€!"
                    else:
                        s["log"] = f"❌ {player['name']} hat nicht genug Geld!"
                elif action == "decline":
                    s["log"] = f"🚫 {player['name']} kauft {field['name']} nicht."
                s["phase"]        = "roll"
                s["buy_field_id"] = None
                self._next_player(s)

            # --- Karte wegklicken ---
            elif phase == "card" and action == "dismiss_card":
                s["active_card"] = None
                s["phase"]       = "roll"
                self._next_player(s)

            self.broadcast()

    def reset(self):
        with self.lock:
            self.state = self._init_state()
            self.broadcast()
        print("🔄 Spiel wurde neu gestartet!")

    # ------------------------------------------------------------------
    # Feld-Landing-Logik
    # ------------------------------------------------------------------
    def _handle_landing(self, player, field, s):
        f_type = field["type"]

        if f_type in ("property", "TV"):
            if field["owner"] is None:
                s["phase"]        = "buy_prompt"
                s["buy_field_id"] = field["id"]
            elif field["owner"] != player["name"]:
                rent = field["rent"]
                player["money"] -= rent
                for p in s["players"]:
                    if p["name"] == field["owner"]:
                        p["money"] += rent
                s["log"] += f" | Miete {rent}€ → {field['owner']}"
                self._next_player(s)
            else:
                # Eigenes Feld
                self._next_player(s)

        elif f_type == "card":
            card_text        = self._draw_card(player, field.get("deck", ""))
            s["active_card"] = card_text
            s["phase"]       = "card"

        else:
            # GO, Gefängnis, Parkplatz …
            self._next_player(s)

    def _draw_card(self, player, deck):
        if deck == "NATION":
            nation = random.choice(self._nations_data)
            return (
                f"{nation['name']}: {nation['positive_effect']} | {nation['negative_effect']}"
            )
        elif deck and deck in self._cards_data:
            karte = random.choice(self._cards_data[deck])
            if "value" in karte:
                player["money"] += karte["value"]
            return karte.get("effekt", "Karte gezogen.")
        return "Karte gezogen."

    def _next_player(self, s):
        s["current_player"] = (s["current_player"] + 1) % len(s["players"])
        next_name = s["players"][s["current_player"]]["name"]
        s["log"]  += f"  |  Jetzt: {next_name}"


# ---------------------------------------------------------------------------
# Client-Thread
# ---------------------------------------------------------------------------

def client_thread(conn, player_id, game):
    print(f"✅ Spieler {player_id + 1} verbunden.")
    send_msg(conn, {"type": "assign", "player_id": player_id})
    game.broadcast()
    try:
        while True:
            msg = recv_msg(conn)
            if msg is None:
                break
            if msg.get("type") == "action":
                game.handle_action(player_id, msg["action"])
            elif msg.get("type") == "reset":
                game.reset()
    except Exception as e:
        print(f"[Thread] Spieler {player_id + 1}: {e}")
    finally:
        conn.close()
        game.clients.pop(player_id, None)
        print(f"❌ Spieler {player_id + 1} getrennt.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    game = GameServer()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", PORT))
    server_sock.listen(2)

    print("=" * 50)
    print("  🎮 Fußball-Monopoly – Multiplayer-Server")
    print(f"  Port: {PORT}   →  Warte auf 2 Spieler …")
    print("=" * 50)

    player_id = 0
    while player_id < 2:
        conn, addr = server_sock.accept()
        game.clients[player_id] = conn
        t = threading.Thread(
            target=client_thread, args=(conn, player_id, game), daemon=True
        )
        t.start()
        player_id += 1
        print(f"  Spieler {player_id} verbunden von {addr[0]}")

    print("\n  ✅ Beide Spieler verbunden – Spiel läuft!\n")

    try:
        threading.Event().wait()          # Main-Thread am Leben halten
    except KeyboardInterrupt:
        print("\n🛑 Server wird beendet.")
        server_sock.close()


if __name__ == "__main__":
    main()
