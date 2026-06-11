import pygame
import sys
import random
import json
import os

from constants import *
from player import Player
from card_handler import handle_card_draw

# ================= FIELD CLASS =================
class Field:
    def __init__(self, data, x, y):
        self.data = data
        self.name = data["name"]
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.owner = None
        self.price = data.get("price", 0)
        self.rent = data.get("rent", 0)
        self.stadium_level = data.get("stadium_level", 0) 

    def get_rent(self, all_fields):
        if self.data.get("type") != "property":
            return self.rent
            
        g = self.data.get("group")
        if not g:
            return self.rent
            
        group_fields = [f for f in all_fields if f and f.data.get("type") == "property" and f.data.get("group") == g]
        is_full_group = all(f.owner == self.owner for f in group_fields)
        
        if self.stadium_level == 0:
            return self.rent * 2 if is_full_group else self.rent
        elif self.stadium_level == 1: return self.rent * 4
        elif self.stadium_level == 2: return self.rent * 10
        elif self.stadium_level == 3: return self.rent * 25
        elif self.stadium_level == 4: return self.rent * 40
        elif self.stadium_level == 5: return self.rent * 60
        return self.rent

    def draw(self, screen):
        pygame.draw.rect(screen, WHITE, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 1)
        
        g = self.data.get("group")
        if g and self.data.get("type") == "property":
            group_colors = {
                1: (128, 0, 128), 2: (255, 165, 0), 3: (64, 224, 208), 4: (173, 216, 230),
                5: (255, 0, 0), 6: (255, 255, 0), 7: (255, 192, 203), 8: (0, 0, 139)
            }
            pygame.draw.rect(screen, group_colors.get(g, (200, 200, 200)), (self.rect.x, self.rect.y, self.rect.width, 10))
            pygame.draw.rect(screen, BLACK, (self.rect.x, self.rect.y, self.rect.width, 10), 1)

        font = pygame.font.SysFont("Arial", 9)
        words = self.name.split(" ")
        y_offset = 12 if g else 4
        for word in words:
            txt = font.render(word, True, BLACK)
            screen.blit(txt, (self.rect.x + 3, self.rect.y + y_offset))
            y_offset += 10
            
        if self.price > 0 and self.owner is None:
            p_txt = font.render(f"{self.price}€", True, (100, 100, 100))
            screen.blit(p_txt, (self.rect.x + 3, self.rect.bottom - 12))

        if self.owner:
            dot_color = RED if "1" in self.owner else BLUE
            pygame.draw.circle(screen, dot_color, (self.rect.right - 7, self.rect.bottom - 7), 5)

        if self.data.get("type") == "property" and self.stadium_level > 0:
            if self.stadium_level <= 4:
                for i in range(self.stadium_level):
                    pygame.draw.rect(screen, (34, 139, 34), (self.rect.x + 3 + i*9, self.rect.y + 1, 6, 4))
            elif self.stadium_level == 5:
                pygame.draw.rect(screen, (255, 215, 0), (self.rect.x + 3, self.rect.y + 1, self.rect.width - 6, 5))


# ================= MAIN GUI CLASS =================
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
        self.has_rolled = False  
        self.message = None
        self.buy_field = None
        self.last_dice_text = ""
        self.last_roll_was_double = False
        self.pending_card_action = None
        
        self.buildable_fields = []
        self.build_index = 0
        self.trade_give_money = 0
        self.trade_take_money = 0
        self.trade_give_prop_idx = -1  # -1 bedeutet kein Verein ausgewählt
        self.trade_take_prop_idx = -1
        self.trade_cursor = 0          # Steuert die ausgewählte Zeile im Tauschmenü
        
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
        player.position = 10
        player.is_in_jail = True
        player.jail_turns = 0
        player.yellow_cards = 0
        self.has_rolled = True  
        self.show_message(f"ROTE KARTE / PLATZVERWEIS!\n{player.name} muss sofort auf die Strafbank (Feld 10).")
        self.state = "MESSAGE"

    def next_player(self):
        self.current = (self.current + 1) % len(self.players)
        self.has_rolled = False  
        self.speichern()

    def speichern(self, dateiname="spielstand.json"):
        daten = {
            "current_player_idx": self.current,
            "has_rolled": self.has_rolled,
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
            "field_owners": {
                str(i): {"owner": f.owner, "stadium_level": f.stadium_level} 
                for i, f in enumerate(self.fields) if f is not None and f.owner is not None
            }
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
            self.has_rolled = daten.get("has_rolled", False)
            for p, pd in zip(self.players, daten["players"]):
                p.position = pd["position"]
                p.money = pd["money"]
                p.vereine = pd["vereine"]
                p.turns_to_skip = pd.get("turns_to_skip", 0)
                p.yellow_cards = pd.get("yellow_cards", 0)
                p.is_in_jail = pd.get("is_in_jail", False)
                p.jail_turns = pd.get("jail_turns", 0)
                p.has_jail_free_card = pd.get("has_jail_free_card", 0)
                
            for idx_str, fdata in daten["field_owners"].items():
                idx = int(idx_str)
                if isinstance(fdata, dict):
                    self.fields[idx].owner = fdata["owner"]
                    self.fields[idx].stadium_level = fdata.get("stadium_level", 0)
                else:
                    self.fields[idx].owner = fdata
                    self.fields[idx].stadium_level = 0
                    
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
            if f: f.stadium_level, f.owner = 0, None
        self.current = 0
        self.has_rolled = False
        self.state = "IDLE"
        self.message = None
        self.buy_field = None
        self.last_dice_text = ""
        self.last_roll_was_double = False
        self.pending_card_action = None
        self.show_message("Das Spiel wurde neu gestartet!")
        self.state = "MESSAGE"

    def land(self, player, passed_go=False):
        prefix = "Über Los gegangen! Prämie von +200€ erhalten.\n\n" if passed_go else ""

        if player.position == 30:
            self.send_to_jail(player)
            return

        field = self.fields[player.position]
        field_type = field.data.get("type")

        if field_type == "card":
            deck = field.data.get("deck")
            handle_card_draw(self, player, deck)
            if passed_go:
                self.message = prefix + self.message
            return

        if field_type in ["property", "TV"]:
            if field.owner is None:
                self.buy_field = field
                self.show_message(prefix + f"{player.name}: {field.name} kaufen?\nPreis: {field.price}€")
                self.state = "BUY"
            elif field.owner != player.name:
                rent = field.get_rent(self.fields) 
                payment = min(player.money, rent)
                player.money -= payment
                for p in self.players:
                    if p.name == field.owner:
                        p.money += payment
                self.show_message(prefix + f"{player.name} bezahlt {payment}€ Miete (Stufe {field.stadium_level})\nan {field.owner} für {field.name}.")
                self.state = "MESSAGE"
        else:
            if passed_go:
                self.show_message(f"Über Los gegangen! (+200€)\nDu landest auf {field.name}.")
                self.state = "MESSAGE"

    def open_build_menu(self):
        player = self.players[self.current]
        owned_groups = []
        for g in range(1, 8):
            group_fields = [f for f in self.fields if f and f.data.get("type") == "property" and f.data.get("group") == g]
            if group_fields and all(f.owner == player.name for f in group_fields):
                owned_groups.append(g)
                
        self.buildable_fields = [
            f for f in self.fields 
            if f and f.data.get("type") == "property" and f.data.get("group") in owned_groups and f.stadium_level < 5
        ]
        
        if not self.buildable_fields:
            self.show_message("Du besitzt noch keine vollständige Farbgruppe\noder alle deine Stadien sind bereits voll ausgebaut!")
            self.state = "MESSAGE"
            return
            
        self.build_index = 0
        self.state = "BUILD"
        self.update_build_message()

    def update_build_message(self):
        field = self.buildable_fields[self.build_index]
        g = field.data.get("group")
        cost = 50 if g in [1, 2] else (100 if g in [3, 4] else (150 if g in [5, 6] else 200))
        
        if field.stadium_level < 4:
            txt = f"Ausbau für: {field.name}\nAktuell: {field.stadium_level} Tribüne(n)\nNächste Stufe: Tribüne {field.stadium_level + 1}\nKosten: {cost}€\n\n[J] Ausbauen  |  [N] Nächster Verein  |  [E] Beenden"
        else:
            txt = f"Ausbau Medic: {field.name}\nAktuell: 4 Tribünen\nNächste Stufe: STADION (Maximum)\nKosten: {cost}€\n\n[J] Stadion bauen  |  [N] Nächster Verein  |  [E] Beenden"
        self.show_message(txt)

    def roll_dice(self):
        player = self.players[self.current]
        if player.turns_to_skip > 0:
            player.turns_to_skip -= 1
            self.show_message(f"{player.name} muss diese Runde aussetzen!")
            self.state = "MESSAGE"
            self.has_rolled = True
            return

        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        steps = d1 + d2
        self.last_dice_text = f"{d1}+{d2}={steps}"
        pasch = (d1 == d2)
        self.last_roll_was_double = pasch

        if pasch: player.double_count += 1
        else: player.double_count = 0

        if player.double_count >= 3:
            player.double_count = 0
            self.show_message(f"{player.name} hatte 3 Pasche hintereinander!\nAb auf die Strafbank.")
            self.send_to_jail(player)
            return

        old_position = player.position
        player.position = (player.position + steps) % len(self.fields)
        passed_go = player.position < old_position  
        
        if passed_go:
            player.money += 200

        if pasch:
            self.has_rolled = False  
            self.show_message(f"PASCH! {d1}+{d2}.\nDu darfst nach der Aktion noch einmal würfeln!")
            self.state = "MESSAGE"
        else:
            self.has_rolled = True   

        self.land(player, passed_go=passed_go)

    def handle_input(self, event):
        if event.type != pygame.KEYDOWN:
            return

        player = self.players[self.current]

        other_player = self.players[(self.current + 1) % len(self.players)]
        if self.state == "TRADE_MENU":
            current_props = player.vereine
            other_props = other_player.vereine

            if event.key == pygame.K_UP:
                self.trade_cursor = (self.trade_cursor - 1) % 5
            elif event.key == pygame.K_DOWN:
                self.trade_cursor = (self.trade_cursor + 1) % 5
            elif event.key == pygame.K_LEFT:
                if self.trade_cursor == 0:   self.trade_give_money = max(0, self.trade_give_money - 10)
                elif self.trade_cursor == 1: self.trade_give_prop_idx = max(-1, self.trade_give_prop_idx - 1)
                elif self.trade_cursor == 2: self.trade_take_money = max(0, self.trade_take_money - 10)
                elif self.trade_cursor == 3: self.trade_take_prop_idx = max(-1, self.trade_take_prop_idx - 1)
            elif event.key == pygame.K_RIGHT:
                if self.trade_cursor == 0:   self.trade_give_money = min(player.money, self.trade_give_money + 10)
                elif self.trade_cursor == 1:
                    if current_props:        self.trade_give_prop_idx = min(len(current_props) - 1, self.trade_give_prop_idx + 1)
                elif self.trade_cursor == 2: self.trade_take_money = min(other_player.money, self.trade_take_money + 10)
                elif self.trade_cursor == 3:
                    if other_props:          self.trade_take_prop_idx = min(len(other_props) - 1, self.trade_take_prop_idx + 1)
            elif event.key == pygame.K_j or event.key == pygame.K_RETURN:
                if self.trade_cursor == 4 or event.key == pygame.K_RETURN:
                    if self.trade_give_money == 0 and self.trade_give_prop_idx == -1 and self.trade_take_money == 0 and self.trade_take_prop_idx == -1:
                        self.show_message("Das Angebot ist leer!")
                        self.state = "MESSAGE"
                    else:
                        self.state = "TRADE_DECISION"
            elif event.key == pygame.K_e or event.key == pygame.K_ESCAPE:
                self.state = "IDLE"
            return

        if self.state == "TRADE_DECISION":
            if event.key == pygame.K_j:
                if player.money < self.trade_give_money:
                    self.show_message(f"{player.name} hat nicht mehr genug Geld!")
                    self.state = "MESSAGE"
                elif other_player.money < self.trade_take_money:
                    self.show_message(f"{other_player.name} hat nicht genug Geld!")
                    self.state = "MESSAGE"
                else:
                    # Geld transferieren
                    player.money -= self.trade_give_money
                    other_player.money += self.trade_give_money
                    player.money += self.trade_take_money
                    other_player.money -= self.trade_take_money
                    
                    # Angebotenen Verein transferieren
                    if self.trade_give_prop_idx >= 0 and self.trade_give_prop_idx < len(player.vereine):
                        p_name = player.vereine[self.trade_give_prop_idx]
                        player.vereine.remove(p_name)
                        other_player.vereine.append(p_name)
                        for f in self.fields:
                            if f and f.name == p_name: f.owner = other_player.name
                            
                    # Geforderten Verein transferieren
                    if self.trade_take_prop_idx >= 0 and self.trade_take_prop_idx < len(other_player.vereine):
                        p_name = other_player.vereine[self.trade_take_prop_idx]
                        other_player.vereine.remove(p_name)
                        player.vereine.append(p_name)
                        for f in self.fields:
                            if f and f.name == p_name: f.owner = player.name
                            
                    self.show_message("Tausch erfolgreich abgeschlossen!")
                    self.state = "MESSAGE"
                    self.speichern()
            elif event.key == pygame.K_n:
                self.show_message("Angebot wurde abgelehnt.")
                self.state = "MESSAGE"
            return

        if self.state == "MESSAGE":
            if event.key == pygame.K_j:
                self.message = None
                if self.pending_card_action:
                    action = self.pending_card_action
                    self.pending_card_action = None
                    action()
                    return
                self.state = "IDLE"
            return

        if self.state == "BUILD":
            field = self.buildable_fields[self.build_index]
            g = field.data.get("group")
            cost = 50 if g in [1, 2] else (100 if g in [3, 4] else (150 if g in [5, 6] else 200))
            
            if event.key == pygame.K_j:
                if player.money >= cost:
                    player.money -= cost
                    field.stadium_level += 1
                    self.open_build_menu() 
                else:
                    self.show_message("Nicht genug Geld für diesen Ausbau!\n\n[N] Nächster Verein  |  [E] Beenden")
            elif event.key == pygame.K_n:
                self.build_index = (self.build_index + 1) % len(self.buildable_fields)
                self.update_build_message()
            elif event.key == pygame.K_e:
                self.message = None
                self.state = "IDLE"
            return

        if self.state == "JAIL":
            if event.key == pygame.K_j:
                if player.has_jail_free_card > 0:
                    player.has_jail_free_card -= 1
                    player.is_in_jail = False
                    self.has_rolled = False  
                    self.show_message(f"{player.name} nutzt die Freikarte!\nDu kannst jetzt normal würfeln.")
                    self.state = "MESSAGE"
                elif player.money >= 50:
                    player.money -= 50
                    player.is_in_jail = False
                    self.has_rolled = False  
                    self.show_message(f"{player.name} zahlt 50€ Strafe!\nDu kannst jetzt normal würfeln.")
                    self.state = "MESSAGE"
                else:
                    self.show_message("Nicht genug Geld für die Strafe! Du musst würfeln.")
            elif event.key == pygame.K_n:
                d1, d2 = random.randint(1, 6), random.randint(1, 6)
                steps = d1 + d2
                self.last_dice_text = f"{d1}+{d2}={steps}"
                self.has_rolled = True  
                
                if d1 == d2:
                    player.is_in_jail = False
                    player.position = (player.position + steps) % len(self.fields)
                    self.show_message(f"PASCH! {d1}+{d2}.\nDu verlässt die Strafbank und ziehst vorwärts!")
                    self.state = "MESSAGE"
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
                    if not self.has_rolled:
                        self.roll_dice()
            
            elif event.key == pygame.K_e:
                if self.has_rolled:
                    self.next_player()
                else:
                    self.show_message("Du musst in dieser Runde zuerst würfeln!")
                    self.state = "MESSAGE"
                    
            elif event.key == pygame.K_b:
                self.open_build_menu()
            # --- NEU: Tauschmenü aktivieren ---
            elif event.key == pygame.K_t:
                self.trade_give_money = 0
                self.trade_take_money = 0
                self.trade_give_prop_idx = -1
                self.trade_take_prop_idx = -1
                self.trade_cursor = 0
                self.state = "TRADE_MENU"
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
            if p.yellow_cards > 0: status_text += f" | Gelb: {p.yellow_cards}"
            if p.has_jail_free_card > 0: status_text += f" | Frei-Karten: {p.has_jail_free_card}"
            if p.is_in_jail: status_text += " [GESPERRT]"
            elif p.turns_to_skip > 0: status_text += f" (Aussetzen: {p.turns_to_skip})"
                
            txt = self.font.render(status_text, True, p.color)
            self.screen.blit(txt, (20, y))
            y += 30

        if not self.has_rolled:
            turn_str = f"Dran: {self.players[self.current].name} ([LEERTASTE] zum Würfeln)"
        else:
            turn_str = f"Dran: {self.players[self.current].name} ([E] drücken, um Zug zu beenden)"
            
        turn = self.font.render(turn_str, True, BLACK)
        self.screen.blit(turn, (20, y + 10))

        dice = self.font.render(f"Wurf: {self.last_dice_text}", True, BLACK)
        self.screen.blit(dice, (20, y + 45))
        
        shortcuts = self.small_font.render("[SPACE] Würfeln  |  [E] Beenden  |  [B] Bauen  |  [T] Tauschen  |  [S] Save", True, BLACK)
        self.screen.blit(shortcuts, (20, HEIGHT - 35))

    def draw_message_box(self):
        if self.state == "TRADE_MENU":
            box = pygame.Rect(WIDTH // 2 - 250, HEIGHT // 2 - 130, 500, 260)
            pygame.draw.rect(self.screen, DARK, box, border_radius=8)
            pygame.draw.rect(self.screen, WHITE, box, 2, border_radius=8)
            
            p_cur = self.players[self.current]
            p_oth = self.players[(self.current + 1) % len(self.players)]
            
            g_prop = p_cur.vereine[self.trade_give_prop_idx] if (self.trade_give_prop_idx >= 0 and p_cur.vereine) else "Keiner"
            t_prop = p_oth.vereine[self.trade_take_prop_idx] if (self.trade_take_prop_idx >= 0 and p_oth.vereine) else "Keiner"
            
            rows = [
                f"Geld bieten: {self.trade_give_money}€  (Max: {p_cur.money}€)",
                f"Verein bieten: {g_prop}",
                f"Geld fordern: {self.trade_take_money}€  (Max: {p_oth.money}€)",
                f"Verein fordern: {t_prop}",
                "[ ANGEBOT ABSENDEN ]"
            ]
            
            y = box.y + 20
            for i, row in enumerate(rows):
                color = (0, 255, 0) if i == self.trade_cursor else WHITE
                prefix = "> " if i == self.trade_cursor else "  "
                txt = self.small_font.render(prefix + row, True, color)
                self.screen.blit(txt, (box.x + 20, y))
                y += 32
                
            help_txt = self.small_font.render("[▲/▼] Zeile  |  [◀/▶] Wert ändern  |  [J/ENTER] Senden  |  [E] Exit", True, (200, 200, 200))
            self.screen.blit(help_txt, (box.x + 20, box.y + 215))
            return

        if self.state == "TRADE_DECISION":
            box = pygame.Rect(WIDTH // 2 - 250, HEIGHT // 2 - 110, 500, 220)
            pygame.draw.rect(self.screen, DARK, box, border_radius=8)
            pygame.draw.rect(self.screen, WHITE, box, 2, border_radius=8)
            
            p_cur = self.players[self.current]
            p_oth = self.players[(self.current + 1) % len(self.players)]
            
            g_prop = p_cur.vereine[self.trade_give_prop_idx] if self.trade_give_prop_idx >= 0 else "Keiner"
            t_prop = p_oth.vereine[self.trade_take_prop_idx] if self.trade_take_prop_idx >= 0 else "Keiner"
            
            lines = [
                f"TAUSCHANGEBOT von {p_cur.name} an {p_oth.name}:",
                f"Er bietet dir: {self.trade_give_money}€ & Verein: {g_prop}",
                f"Er fordert:     {self.trade_take_money}€ & Verein: {t_prop}",
                "",
                f"{p_oth.name}, nimmst du an?",
                "[J] = ANNEHMEN      |      [N] = ABLEHNEN"
            ]
            y = box.y + 20
            for line in lines:
                txt = self.small_font.render(line, True, WHITE)
                self.screen.blit(txt, (box.x + 20, y))
                y += 28
            return

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
            yes, no = self.small_font.render("[J] = JA", True, (0, 255, 0)), self.small_font.render("[N] = NEIN", True, (255, 0, 0))
            self.screen.blit(yes, (box.x + 20, box.y + 130))
            self.screen.blit(no,  (box.x + 150, box.y + 130))
        elif self.state == "JAIL":
            player = self.players[self.current]
            btn1 = self.small_font.render("[J] = Karte nutzen" if player.has_jail_free_card > 0 else "[J] = 50€ zahlen", True, (0, 255, 0))
            btn2 = self.small_font.render("[N] = Würfeln (Pasch)", True, (255, 255, 0))
            self.screen.blit(btn1, (box.x + 20, box.y + 130))
            self.screen.blit(btn2, (box.x + 180, box.y + 130))
        elif self.state == "BUILD":
            btn1 = self.small_font.render("[J] = Ausbauen", True, (0, 255, 0))
            btn2 = self.small_font.render("[N] = Nächster", True, (255, 255, 0))
            btn3 = self.small_font.render("[E] = Beenden", True, (255, 0, 0))
            self.screen.blit(btn1, (box.x + 20, box.y + 130))
            self.screen.blit(btn2, (box.x + 160, box.y + 130))
            self.screen.blit(btn3, (box.x + 320, box.y + 130))
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