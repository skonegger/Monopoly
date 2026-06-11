"""
server.py – Fußball Monopoly Multiplayer Server
================================================
Startet mit: python server.py [--port 5555]

Der Server hält den kompletten Spielzustand im Speicher und verteilt
nach jeder Aktion einen aktualisierten Snapshot an alle Clients.

Protokoll (TCP, JSON-Zeilen, UTF-8):
  Client → Server:  {"action": "roll"} | {"action": "end_turn"} |
                    {"action": "buy", "answer": true/false} |
                    {"action": "jail", "choice": "pay"|"roll"|"card"} |
                    {"action": "build", "field_id": 3} |
                    {"action": "build_next"} | {"action": "reset"}
  Server → Client:  {"type": "state", "state": <GameState>}
                    {"type": "error", "msg": "..."}
                    {"type": "assign", "player_id": 0|1}
"""

import socket
import threading
import json
import random
import argparse
import os

# ── Spielkonstanten ─────────────────────────────────────────────────────────
STARTING_MONEY = 1500
MAX_PLAYERS    = 2


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────
def send_msg(conn, obj):
    """Sendet ein JSON-Objekt als einzelne Zeile."""
    try:
        conn.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    except OSError:
        pass


def recv_lines(conn):
    """Generator: liefert vollständige JSON-Zeilen vom Socket."""
    buf = b""
    while True:
        try:
            chunk = conn.recv(4096)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if line:
                yield line.decode("utf-8", errors="replace")


# ── Spielstand-Klasse ────────────────────────────────────────────────────────
class GameState:
    def __init__(self, board_path, cards_path):
        with open(board_path, "r", encoding="utf-8") as f:
            self.board_data = json.load(f)["board"]
        with open(cards_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # cards.json kann {"cards": [...]} oder direkt [...] sein
        cards_raw = raw["cards"] if isinstance(raw, dict) else raw
        # Jede Karte normalisieren: String → {"text": str, "type": "info"}
        self.cards = [
            c if isinstance(c, dict) else {"text": str(c), "type": "info"}
            for c in cards_raw
        ]

        self.players = [
            {"name": "Spieler 1", "money": STARTING_MONEY, "position": 0,
             "vereine": [], "yellow_cards": 0, "is_in_jail": False,
             "jail_turns": 0, "has_jail_free_card": 0, "turns_to_skip": 0,
             "double_count": 0},
            {"name": "Spieler 2", "money": STARTING_MONEY, "position": 0,
             "vereine": [], "yellow_cards": 0, "is_in_jail": False,
             "jail_turns": 0, "has_jail_free_card": 0, "turns_to_skip": 0,
             "double_count": 0},
        ]
        # Feldzustand: {id: {owner: str|None, stadium_level: int}}
        self.fields = {
            d["id"]: {"owner": None, "stadium_level": 0, **d}
            for d in self.board_data
        }
        self.current      = 0      # Index des aktiven Spielers
        self.has_rolled   = False
        self.state        = "IDLE" # IDLE | MESSAGE | BUY | JAIL | BUILD
        self.message      = ""
        self.last_dice    = ""
        self.buy_field_id = None
        self.buildable    = []     # Liste von Feld-IDs die gebaut werden können
        self.build_idx    = 0
        # Karten-Aktionen werden als Lambda serialisiert – wir speichern sie
        # als "pending_card" dict statt Lambda, damit der Server sie ausführen kann.
        self.pending_card = None   # dict mit Feldern: typ, wert, …

    # ── Hilfsmethoden ──────────────────────────────────────────────────────
    def player(self, idx=None):
        return self.players[self.current if idx is None else idx]

    def field(self, fid):
        return self.fields[fid]

    def show(self, msg, new_state="MESSAGE"):
        self.message = msg
        self.state   = new_state

    def next_player(self):
        self.current    = (self.current + 1) % MAX_PLAYERS
        self.has_rolled = False
        self.state      = "IDLE"
        self.message    = ""

    def send_to_jail(self, p):
        p["position"]   = 10
        p["is_in_jail"] = True
        p["jail_turns"] = 0
        p["yellow_cards"] = 0
        self.has_rolled = True
        self.show(f"ROTE KARTE / PLATZVERWEIS!\n{p['name']} muss auf die Strafbank (Feld 10).")

    def get_rent(self, fid):
        f = self.fields[fid]
        if f.get("type") != "property":
            return f.get("rent", 0)
        g = f.get("group")
        if not g:
            return f.get("rent", 0)
        base = f.get("rent", 0)
        sl   = f["stadium_level"]
        group_fields = [fv for fv in self.fields.values()
                        if fv.get("type") == "property" and fv.get("group") == g]
        full = all(fv["owner"] == f["owner"] for fv in group_fields)
        if sl == 0: return base * 2 if full else base
        if sl == 1: return base * 4
        if sl == 2: return base * 10
        if sl == 3: return base * 25
        if sl == 4: return base * 40
        if sl == 5: return base * 60
        return base

    # ── Würfeln & Landen ───────────────────────────────────────────────────
    def do_roll(self):
        p = self.player()
        if p["turns_to_skip"] > 0:
            p["turns_to_skip"] -= 1
            self.has_rolled = True
            self.show(f"{p['name']} muss diese Runde aussetzen!")
            return

        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        steps  = d1 + d2
        pasch  = (d1 == d2)
        self.last_dice = f"{d1}+{d2}={steps}"

        if pasch: p["double_count"] += 1
        else:     p["double_count"]  = 0

        if p["double_count"] >= 3:
            p["double_count"] = 0
            self.send_to_jail(p)
            return

        old_pos     = p["position"]
        p["position"] = (old_pos + steps) % 40
        passed_go   = p["position"] < old_pos
        if passed_go:
            p["money"] += 200

        if pasch:
            self.has_rolled = False
            self.show(f"PASCH! {d1}+{d2}.\nNoch einmal würfeln!")
            self.state = "MESSAGE"
        else:
            self.has_rolled = True

        self.land(p, passed_go)

    def land(self, p, passed_go=False):
        prefix = "Über Los! +200€\n\n" if passed_go else ""
        fid    = p["position"]

        if fid == 30:
            self.send_to_jail(p)
            return

        f     = self.fields[fid]
        ftype = f.get("type")

        if ftype == "card":
            self._draw_card(p, f.get("deck"), prefix)
            return

        if ftype in ["property", "TV"]:
            if f["owner"] is None:
                self.buy_field_id = fid
                self.show(prefix + f"{p['name']}: {f['name']} kaufen?\nPreis: {f['price']}€", "BUY")
            elif f["owner"] != p["name"]:
                rent    = self.get_rent(fid)
                payment = min(p["money"], rent)
                p["money"] -= payment
                for op in self.players:
                    if op["name"] == f["owner"]:
                        op["money"] += payment
                self.show(prefix + f"{p['name']} zahlt {payment}€ Miete\nan {f['owner']} für {f['name']}.")
        else:
            if passed_go:
                self.show(f"Über Los! (+200€)\nDu landest auf: {f['name']}.")

    def _draw_card(self, p, deck, prefix=""):
        """Zieht eine Karte aus dem angegebenen Deck und führt die Aktion aus."""
        deck_cards = [c for c in self.cards if c.get("deck") == deck]
        if not deck_cards:
            self.show(prefix + "Keine Karte im Deck.")
            return
        card = random.choice(deck_cards)
        text = card.get("text", "")
        ctype = card.get("type")

        if ctype == "money":
            amount = card.get("amount", 0)
            if amount >= 0:
                p["money"] += amount
                self.show(prefix + f"Karte: {text}\n+{amount}€ erhalten!")
            else:
                pay = min(p["money"], abs(amount))
                p["money"] -= pay
                self.show(prefix + f"Karte: {text}\n{abs(amount)}€ bezahlt.")

        elif ctype == "move":
            dest = card.get("destination")
            if dest is not None:
                old = p["position"]
                p["position"] = dest
                if dest < old:
                    p["money"] += 200
                    self.show(prefix + f"Karte: {text}\nÜber Los! +200€ – ziehe zu Feld {dest}.")
                else:
                    self.show(prefix + f"Karte: {text}\nZiehe zu Feld {dest}.")
                self.land(p)
                return
            steps = card.get("steps", 0)
            p["position"] = (p["position"] + steps) % 40
            self.show(prefix + f"Karte: {text}\nZiehe {steps} Felder.")
            self.land(p)
            return

        elif ctype == "jail_free":
            p["has_jail_free_card"] += 1
            self.show(prefix + f"Karte: {text}\nFreikarte erhalten!")

        elif ctype == "go_to_jail":
            self.send_to_jail(p)
            return

        elif ctype == "yellow_card":
            p["yellow_cards"] += 1
            if p["yellow_cards"] >= 2:
                self.send_to_jail(p)
                return
            self.show(prefix + f"Karte: {text}\nGelbe Karte! ({p['yellow_cards']}/2)")

        elif ctype == "skip":
            turns = card.get("turns", 1)
            p["turns_to_skip"] += turns
            self.show(prefix + f"Karte: {text}\nAussetzen für {turns} Runde(n).")

        else:
            self.show(prefix + f"Karte: {text}")

    # ── Aktionen ───────────────────────────────────────────────────────────
    def action_buy(self, answer):
        p = self.player()
        if self.buy_field_id is None:
            return
        f = self.fields[self.buy_field_id]
        if answer:
            if p["money"] >= f["price"]:
                p["money"] -= f["price"]
                f["owner"]   = p["name"]
                p["vereine"].append(f["name"])
                self.show(f"{p['name']} kauft {f['name']}!")
            else:
                self.show("Nicht genug Geld!")
        else:
            self.show("Kauf abgelehnt.")
        self.buy_field_id = None
        self.state = "MESSAGE"

    def action_jail(self, choice):
        p = self.player()
        if choice == "pay":
            if p["has_jail_free_card"] > 0:
                p["has_jail_free_card"] -= 1
                p["is_in_jail"] = False
                self.has_rolled = False
                self.show(f"{p['name']} nutzt die Freikarte! Würfle jetzt.")
            elif p["money"] >= 50:
                p["money"]    -= 50
                p["is_in_jail"] = False
                self.has_rolled = False
                self.show(f"{p['name']} zahlt 50€ Strafe. Würfle jetzt.")
            else:
                self.show("Nicht genug Geld! Würfle auf Pasch.")
        elif choice == "roll":
            d1, d2 = random.randint(1, 6), random.randint(1, 6)
            steps  = d1 + d2
            self.last_dice = f"{d1}+{d2}={steps}"
            self.has_rolled = True
            if d1 == d2:
                p["is_in_jail"] = False
                p["position"]   = (p["position"] + steps) % 40
                self.show(f"PASCH! {d1}+{d2}. Du verlässt die Strafbank!")
                self.land(p)
            else:
                p["jail_turns"] += 1
                if p["jail_turns"] >= 3:
                    pay = min(p["money"], 50)
                    p["money"] -= pay
                    p["is_in_jail"] = False
                    p["position"]   = (p["position"] + steps) % 40
                    self.show(f"Kein Pasch ({d1}+{d2}). 3. Versuch – 50€ Kaution, vorwärts!")
                    self.land(p)
                else:
                    self.show(f"Kein Pasch ({d1}+{d2}). Du bleibst auf der Strafbank.")

    def _buildable(self):
        p = self.player()
        owned_groups = set()
        for g in range(1, 9):
            gf = [fv for fv in self.fields.values()
                  if fv.get("type") == "property" and fv.get("group") == g]
            if gf and all(fv["owner"] == p["name"] for fv in gf):
                owned_groups.add(g)
        return [
            fid for fid, fv in self.fields.items()
            if fv.get("type") == "property"
            and fv.get("group") in owned_groups
            and fv["stadium_level"] < 5
        ]

    def action_open_build(self):
        self.buildable = self._buildable()
        if not self.buildable:
            self.show("Keine vollständige Farbgruppe oder alles ausgebaut!")
            return
        self.build_idx = 0
        self.state = "BUILD"
        self._update_build_msg()

    def _update_build_msg(self):
        fid = self.buildable[self.build_idx]
        f   = self.fields[fid]
        g   = f.get("group", 1)
        cost = 50 if g in [1, 2] else (100 if g in [3, 4] else (150 if g in [5, 6] else 200))
        sl  = f["stadium_level"]
        if sl < 4:
            txt = (f"Ausbau: {f['name']}\nStufe {sl} → {sl+1}\nKosten: {cost}€\n"
                   "[J] Ausbauen  [N] Nächster  [E] Beenden")
        else:
            txt = (f"Stadion bauen: {f['name']}\n4 Tribünen → STADION\nKosten: {cost}€\n"
                   "[J] Stadion  [N] Nächster  [E] Beenden")
        self.message = txt
        self._current_build_cost = cost

    def action_build(self):
        if not self.buildable:
            return
        fid  = self.buildable[self.build_idx]
        f    = self.fields[fid]
        p    = self.player()
        g    = f.get("group", 1)
        cost = 50 if g in [1, 2] else (100 if g in [3, 4] else (150 if g in [5, 6] else 200))
        if p["money"] >= cost:
            p["money"] -= cost
            f["stadium_level"] += 1
            self.action_open_build()
        else:
            self.show("Nicht genug Geld!\n[N] Nächster  [E] Beenden")

    def action_build_next(self):
        if not self.buildable:
            return
        self.build_idx = (self.build_idx + 1) % len(self.buildable)
        self._update_build_msg()

    # ── Snapshot ───────────────────────────────────────────────────────────
    def snapshot(self):
        """Gibt den vollständigen Spielzustand zurück (JSON-serialisierbar)."""
        return {
            "players":      self.players,
            "fields":       {str(k): v for k, v in self.fields.items()},
            "current":      self.current,
            "has_rolled":   self.has_rolled,
            "state":        self.state,
            "message":      self.message,
            "last_dice":    self.last_dice,
            "buy_field_id": self.buy_field_id,
            "buildable":    self.buildable,
            "build_idx":    self.build_idx,
        }


# ── Server-Klasse ────────────────────────────────────────────────────────────
class MonopolyServer:
    def __init__(self, host="0.0.0.0", port=5555):
        self.host     = host
        self.port     = port
        self.clients  = {}   # player_id → conn
        self.lock     = threading.Lock()
        self.gs       = GameState("spielfeld.json", "cards.json")

    def broadcast(self):
        snap = self.gs.snapshot()
        msg  = {"type": "state", "state": snap}
        dead = []
        for pid, conn in list(self.clients.items()):
            try:
                send_msg(conn, msg)
            except OSError:
                dead.append(pid)
        for pid in dead:
            del self.clients[pid]

    def handle_client(self, conn, addr, player_id):
        print(f"[SERVER] Spieler {player_id + 1} verbunden von {addr}")
        send_msg(conn, {"type": "assign", "player_id": player_id})
        with self.lock:
            self.broadcast()

        for raw in recv_lines(conn):
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            with self.lock:
                gs  = self.gs
                cur = gs.current

                # Nur der aktive Spieler darf handeln
                if player_id != cur and msg.get("action") != "reset":
                    send_msg(conn, {"type": "error", "msg": "Nicht dein Zug!"})
                    continue

                action = msg.get("action")

                if action == "roll" and gs.state == "IDLE" and not gs.has_rolled:
                    gs.do_roll()

                elif action == "end_turn":
                    if gs.has_rolled and gs.state in ("IDLE", "MESSAGE"):
                        gs.next_player()

                elif action == "confirm_message" and gs.state == "MESSAGE":
                    gs.message = ""
                    gs.state   = "IDLE"

                elif action == "buy":
                    if gs.state == "BUY":
                        gs.action_buy(msg.get("answer", False))

                elif action == "jail":
                    if gs.state == "JAIL" or (gs.state == "IDLE" and gs.player()["is_in_jail"]):
                        gs.state = "JAIL"
                        gs.action_jail(msg.get("choice", "roll"))

                elif action == "open_build" and gs.state == "IDLE":
                    gs.action_open_build()

                elif action == "build" and gs.state == "BUILD":
                    gs.action_build()

                elif action == "build_next" and gs.state == "BUILD":
                    gs.action_build_next()

                elif action == "build_cancel":
                    gs.state   = "IDLE"
                    gs.message = ""

                elif action == "reset":
                    gs.__init__("spielfeld.json", "cards.json")

                else:
                    send_msg(conn, {"type": "error", "msg": f"Unbekannte Aktion: {action}"})
                    continue

                self.broadcast()

        with self.lock:
            if player_id in self.clients:
                del self.clients[player_id]
        print(f"[SERVER] Spieler {player_id + 1} getrennt.")

    def run(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(MAX_PLAYERS)
        print(f"[SERVER] Lausche auf {self.host}:{self.port} …")

        next_id = 0
        while next_id < MAX_PLAYERS:
            conn, addr = server_sock.accept()
            with self.lock:
                self.clients[next_id] = conn
            t = threading.Thread(target=self.handle_client,
                                 args=(conn, addr, next_id), daemon=True)
            t.start()
            next_id += 1

        print("[SERVER] Beide Spieler verbunden! Das Spiel läuft.")
        # Halte den Server am Leben (Threads laufen als Daemon)
        import time
        while True:
            time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fußball Monopoly Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    MonopolyServer(args.host, args.port).run()
