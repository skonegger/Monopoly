import pygame
import sys
import random
import json
import os

from constants import *
from player import Player
from field import Field
from card_handler import handle_card_draw

class MonopolyGUI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fußball Monopoly Pro")
        self.clock = pygame.time.Clock()
        
        self.font       = pygame.font.SysFont("Arial", 22)
        self.small_font = pygame.font.SysFont("Arial", 16)
        
        with open('football_nations_monopoly.json', 'r', encoding='utf-8') as f:
            self.nations_data = json.load(f)
        with open('cards.json', 'r', encoding='utf-8') as f:
            self.cards = json.load(f)["cards"]

        self.players = [
            Player("Spieler 1", RED, 1),
            Player("Spieler 2", BLUE, 2)
        ]
        self.current = 0
        self.fields = self.load_board()
        
        self.state = "IDLE"
        self.message = None
        self.buy_field = None
        self.last_dice_text = ""
        self.last_roll_was_double = False
        self.pending_card_action = None
        
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

    def send_to_jail(self, player):
        player.position = 10  # Feld 10 ist das Gefängnis
        player.is_in_jail = True
        player.jail_turns = 0
        player.yellow_cards = 0  # Nach Platzverweis zurücksetzen
        self.last_roll_was_double = False # Beendet den Zug trotz Pasch
        self.show_message(f"ROTE KARTE / PLATZVERWEIS!\n{player.name} muss sofort auf die Strafbank (Feld 10).")
        self.state = "MESSAGE"

    def next_player(self):
        self.current = (self.current + 1) % len(self.players)
        self.speichern()

    def speichern(self, dateiname="spielstand.json"):
        daten = {
            "current_player_idx": self.current,
            "players": [{
                "position": p.position, 
                "money": p.money, 
                "vereine": p.vereine, 
                "turns_to_skip": p.turns_to_skip,
                "yellow_cards": p.yellow_cards,
                "is_in_jail": p.is_in_jail,
                "jail_turns": p.jail_turns,
                "has_jail_free_card": p.has_jail_free_card
            } for p in self.players],
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
                p.position = pd["position"]
                p.money = pd["money"]
                p.vereine = pd["vereine"]
                p.turns_to_skip = pd.get("turns_to_skip", 0)
                p.yellow_cards = pd.get("yellow_cards", 0)
                p.is_in_jail = pd.get("is_in_jail", False)
                p.jail_turns = pd.get("jail_turns", 0)
                p.has_jail_free_card = pd.get("has_jail_free_card", 0)
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
            p.position, p.money, p.vereine, p.double_count, p.turns_to_skip = 0, 1500, [], 0, 0
            p.yellow_cards, p.is_in_jail, p.jail_turns, p.has_jail_free_card = 0, False, 0, 0
        for f in self.fields:
            if f: f.owner = None
        self.current = 0
        self.state = "IDLE"
        self.message = None
        self.buy_field = None
        self.last_dice_text = ""
        self.last_roll_was_double = False
        self.pending_card_action = None
        self.show_message("Das Spiel wurde neu gestartet!")
        self.state = "MESSAGE"

    def land(self, player):
        # Klassisches "Geh ins Gefängnis" Feld (Feldindex 30)
        if player.position == 30:
            self.send_to_jail(player)
            return

        field = self.fields[player.position]
        field_type = field.data.get("type")

        if field_type == "card":
            deck = field.data.get("deck")
            handle_card_draw(self, player, deck)
            return

        if field_type in ["property", "TV"]:
            if field.owner is None:
                self.buy_field = field
                self.show_message(f"{player.name}: {field.name} kaufen?\nPreis: {field.price}€")
                self.state = "BUY"
            elif field.owner != player.name:
                rent = field.rent
                payment = min(player.money, rent)
                player.money -= payment
                for p in self.players:
                    if p.name == field.owner:
                        p.money += payment
                self.show_message(f"{player.name} bezahlt {payment}€ Miete\nan {field.owner} für {field.name}.")
                self.state = "MESSAGE"

    def roll_dice(self):
        player = self.players[self.current]
        
        if player.turns_to_skip > 0:
            player.turns_to_skip -= 1
            self.show_message(f"{player.name} muss diese Runde aussetzen!")
            self.state = "MESSAGE"
            return

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

        if player.double_count >= 3:
            player.double_count = 0
            self.show_message(f"{player.name} hatte 3 Pasche hintereinander!\nAb auf die Strafbank.")
            self.send_to_jail(player)
            return

        player.position = (player.position + steps) % len(self.fields)
        self.land(player)

        if self.state == "IDLE":
            if pasch:
                self.show_message("PASCH!\nDu darfst noch einmal würfeln.")
                self.state = "MESSAGE"
            else:
                self.next_player()

    def handle_input(self, event):
        if event.type != pygame.KEYDOWN:
            return

        player = self.players[self.current]

        if self.state == "MESSAGE":
            if event.key == pygame.K_j:
                self.message = None
                if self.pending_card_action:
                    action = self.pending_card_action
                    self.pending_card_action = None
                    action()
                    return

                if self.last_roll_was_double:
                    self.last_roll_was_double = False
                    self.state = "IDLE"
                else:
                    self.state = "IDLE"
                    self.next_player()
            return

        if self.state == "JAIL":
            if event.key == pygame.K_j:  # Freikaufen oder Karte nutzen
                if player.has_jail_free_card > 0:
                    player.has_jail_free_card -= 1
                    player.is_in_jail = False
                    self.show_message(f"{player.name} nutzt die Freikarte und ist frei!\nWürfle jetzt ganz normal.")
                    self.state = "MESSAGE"
                    self.last_roll_was_double = True  # Trick, um im IDLE dieses Spielers zu bleiben
                elif player.money >= 50:
                    player.money -= 50
                    player.is_in_jail = False
                    self.show_message(f"{player.name} zahlt 50€ Strafe und ist frei!\nWürfle jetzt ganz normal.")
                    self.state = "MESSAGE"
                    self.last_roll_was_double = True
                else:
                    self.show_message("Nicht genug Geld für die Strafe! Du musst würfeln.")
            elif event.key == pygame.K_n:  # Pasch-Versuch
                d1 = random.randint(1, 6)
                d2 = random.randint(1, 6)
                steps = d1 + d2
                self.last_dice_text = f"{d1}+{d2}={steps}"
                
                if d1 == d2:
                    player.is_in_jail = False
                    player.position = (player.position + steps) % len(self.fields)
                    self.show_message(f"PASCH! {d1}+{d2}.\nDu verlässt die Strafbank und ziehst vorwärts!")
                    self.state = "MESSAGE"
                    self.last_roll_was_double = False  # Aus dem Gefängnis heraus gibt es keinen Extra-Zug
                    self.land(player)
                else:
                    player.jail_turns += 1
                    if player.jail_turns >= 3:
                        payment = min(player.money, 50)
                        player.money -= payment
                        player.is_in_jail = False
                        player.position = (player.position + steps) % len(self.fields)
                        self.show_message(f"Kein Pasch ({d1}+{d2}). 3. Versuch vorbei!\nDu zahlst 50€ Kaution und ziehst vorwärts.")
                        self.state = "MESSAGE"
                        self.land(player)
                    else:
                        self.show_message(f"Kein Pasch ({d1}+{d2}).\nDu bleibst auf der Strafbank.")
                        self.state = "MESSAGE"
            return

        if self.state == "BUY":
            if event.key == pygame.K_j:
                if player.money >= self.buy_field.price:
                    player.money -= self.buy_field.price
                    self.buy_field.owner = player.name
                    player.vereine.append(self.buy_field.name)
                    self.show_message(f"{player.name} kauft {self.buy_field.name}!")
                else:
                    self.show_message("Nicht genug Geld auf dem Konto!")
                self.state = "MESSAGE"
            elif event.key == pygame.K_n:
                self.show_message("Kauf abgelehnt.")
                self.state = "MESSAGE"
            self.buy_field = None
            return

        if self.state == "IDLE":
            if event.key == pygame.K_SPACE:
                if player.is_in_jail:
                    self.state = "JAIL"
                    if player.has_jail_free_card > 0:
                        self.show_message(f"{player.name} ist gesperrt!\n[J] Freikarte nutzen ({player.has_jail_free_card}x)\n[N] Pasch versuchen (Runde {player.jail_turns+1}/3)")
                    else:
                        self.show_message(f"{player.name} ist gesperrt!\n[J] 50€ Strafe zahlen\n[N] Pasch versuchen (Runde {player.jail_turns+1}/3)")
                else:
                    self.roll_dice()
            elif event.key == pygame.K_s:
                self.speichern()
                self.show_message("Spielstand manuell gespeichert!")
                self.state = "MESSAGE"
            elif event.key == pygame.K_r:
                self.neu_starten()

    def draw_ui(self):
        y = 15
        for p in self.players:
            status_text = f"{p.name}: {p.money}€"
            if p.yellow_cards > 0:
                status_text += f" | Gelb: {p.yellow_cards}"
            if p.has_jail_free_card > 0:
                status_text += f" | Frei-Karten: {p.has_jail_free_card}"
            
            if p.is_in_jail:
                status_text += " [GESPERRT]"
            elif p.turns_to_skip > 0:
                status_text += f" (Aussetzen: {p.turns_to_skip})"
                
            txt = self.font.render(status_text, True, p.color)
            self.screen.blit(txt, (20, y))
            y += 30

        turn = self.font.render(f"Dran: {self.players[self.current].name} (Leertaste)", True, BLACK)
        self.screen.blit(turn, (20, y + 10))

        dice = self.font.render(f"Wurf: {self.last_dice_text}", True, BLACK)
        self.screen.blit(dice, (20, y + 45))
        
        shortcuts = self.small_font.render("[S] Speichern  |  [R] Zurücksetzen", True, BLACK)
        self.small_font.render("[S] Speichern  |  [R] Zurücksetzen", True, BLACK)
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

        if self.state == "BUY":
            yes = self.small_font.render("[J] = JA", True, (0, 255, 0))
            no  = self.small_font.render("[N] = NEIN", True, (255, 0, 0))
            self.screen.blit(yes, (box.x + 20, box.y + 130))
            self.screen.blit(no,  (box.x + 150, box.y + 130))
        elif self.state == "JAIL":
            player = self.players[self.current]
            if player.has_jail_free_card > 0:
                btn1 = self.small_font.render("[J] = Karte nutzen", True, (0, 255, 0))
            else:
                btn1 = self.small_font.render("[J] = 50€ zahlen", True, (0, 255, 0))
            btn2 = self.small_font.render("[N] = Würfeln (Pasch)", True, (255, 255, 0))
            self.screen.blit(btn1, (box.x + 20, box.y + 130))
            self.screen.blit(btn2, (box.x + 180, box.y + 130))
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

            offset = (WIDTH - BOARD_SIZE) // 2
            pygame.draw.rect(self.screen, GREEN, (offset, offset, BOARD_SIZE, BOARD_SIZE))

            for field in self.fields:
                if field: field.draw(self.screen)
            for player in self.players:
                player.draw(self.screen, self.fields)

            self.draw_ui()
            self.draw_message_box()
            pygame.display.flip()
            self.clock.tick(FPS)

if __name__ == "__main__":
    game = MonopolyGUI()
    game.run()