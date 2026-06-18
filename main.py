import pygame
import sys
import random
import json
import os

from constants import *
from player import Player
from card_handler import handle_card_draw

BG_DARK      = (15, 23, 42)     # Edles Anthrazit/Tiefblau für den Hintergrund
PITCH_GREEN  = (20, 83, 45)     # Sattes Stadion-Rasen-Grün
PANEL_BG     = (30, 41, 59)     # Hintergrund für Scorecards und Menüs
PANEL_BORDER = (71, 85, 105)    # Dezente Rahmenlinien
FIELD_LIGHT  = (248, 250, 252)  # Hochwertiges Off-White für die Standardfelder
TEXT_WHITE   = (241, 245, 249)  # Klar lesbarer Text
TEXT_MUTED   = (148, 163, 184)  # Sekundäre Informationen (Grau)
ACCENT_GOLD  = (234, 179, 8)    # Highlight-Farbe für Max-Stadien & wichtige Events

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
        # Basis-Feld
        pygame.draw.rect(screen, FIELD_LIGHT, self.rect)
        pygame.draw.rect(screen, PANEL_BORDER, self.rect, 1)
        
        # Farbgruppen-Header
        g = self.data.get("group")
        if g and self.data.get("type") == "property":
            group_colors = {
                1: (147, 51, 234), 2: (249, 115, 22), 3: (20, 184, 166), 4: (56, 189, 248),
                5: (239, 68, 68),  6: (234, 179, 8),  7: (236, 72, 153), 8: (29, 78, 216)
            }
            pygame.draw.rect(screen, group_colors.get(g, (200, 200, 200)), (self.rect.x, self.rect.y, self.rect.width, 12))
            pygame.draw.rect(screen, PANEL_BORDER, (self.rect.x, self.rect.y, self.rect.width, 12), 1)

        # Text-Formatierung (Zentrierter & kompakter)
        font = pygame.font.SysFont("Segoe UI", 9, bold=True)
        words = self.name.split(" ")
        y_offset = 15 if g else 6
        for word in words:
            txt = font.render(word, True, BG_DARK)
            txt_rect = txt.get_rect(center=(self.rect.x + TILE_SIZE // 2, self.rect.y + y_offset))
            screen.blit(txt, txt_rect)
            y_offset += 10
            
        # Preis-Anzeige
        if self.price > 0 and self.owner is None:
            p_txt = font.render(f"{self.price}€", True, (100, 116, 139))
            p_rect = p_txt.get_rect(center=(self.rect.x + TILE_SIZE // 2, self.rect.bottom - 8))
            screen.blit(p_txt, p_rect)

        # Besitzer-Markierung (Cleanerer Ring-Indikator)
        if self.owner:
            dot_color = (239, 68, 68) if "1" in self.owner else (59, 130, 246)
            pygame.draw.circle(screen, dot_color, (self.rect.right - 8, self.rect.bottom - 8), 6)
            pygame.draw.circle(screen, FIELD_LIGHT, (self.rect.right - 8, self.rect.bottom - 8), 3)

        # Tribünen & Stadien (Modernere Symbole)
        if self.data.get("type") == "property" and self.stadium_level > 0:
            if self.stadium_level <= 4:
                for i in range(self.stadium_level):
                    pygame.draw.rect(screen, (34, 197, 94), (self.rect.x + 4 + i*8, self.rect.y + 2, 5, 3))
            elif self.stadium_level == 5:
                pygame.draw.rect(screen, ACCENT_GOLD, (self.rect.x + 4, self.rect.y + 2, self.rect.width - 8, 4))


# ================= MAIN GUI CLASS =================
class MonopolyGUI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fußball Monopoly Pro")
        self.clock = pygame.time.Clock()
        
        self.font       = pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.small_font = pygame.font.SysFont("Segoe UI", 15)
        self.title_font = pygame.font.SysFont("Segoe UI", 26, bold=True)
        
        with open('football_nations_monopoly.json', 'r', encoding='utf-8') as f:
            self.nations_data = json.load(f)
        with open('cards.json', 'r', encoding='utf-8') as f:
            self.cards = json.load(f)["cards"]

        self.players = [
            Player("Spieler 1", (239, 68, 68), 1), # Echtes Material-Rot
            Player("Spieler 2", (59, 130, 246), 2) # Echtes Material-Blau
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
        self.trade_give_prop_idx = -1  
        self.trade_take_prop_idx = -1
        self.trade_cursor = 0          
        
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

        if field_type == "tax":
            amount = field.data.get("effect", 0)
            player.money -= amount
            self.show_message(prefix + f"{player.name} landet auf {field.name}.\nFinanzstrafe: -{amount}€!")
            self.state = "MESSAGE"
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
        for g in range(1, 9): 
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
        self.last_dice_text = f"{d1} + {d2} = {steps}"
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
                    player.money -= self.trade_give_money
                    other_player.money += self.trade_give_money
                    player.money += self.trade_take_money
                    other_player.money -= self.trade_take_money
                    
                    if self.trade_give_prop_idx >= 0 and self.trade_give_prop_idx < len(player.vereine):
                        p_name = player.vereine[self.trade_give_prop_idx]
                        player.vereine.remove(p_name)
                        other_player.vereine.append(p_name)
                        for f in self.fields:
                            if f and f.name == p_name: f.owner = other_player.name
                            
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
        # --- TOP DISPLAY: PLAYER CARD DASHBOARDS ---
        card_w, card_h = 320, 70
        for idx, p in enumerate(self.players):
            x_pos = 20 if idx == 0 else WIDTH - card_w - 20
            y_pos = 15
            
            # Highlight aktiver Spieler (Glow-Effekt am Rand)
            is_active = (idx == self.current)
            border_clr = p.color if is_active else PANEL_BORDER
            thickness = 3 if is_active else 1
            
            # Card Container
            pygame.draw.rect(self.screen, PANEL_BG, (x_pos, y_pos, card_w, card_h), border_radius=6)
            pygame.draw.rect(self.screen, border_clr, (x_pos, y_pos, card_w, card_h), thickness, border_radius=6)
            
            # Spielername & Kontostand
            name_txt = self.font.render(p.name, True, p.color)
            self.screen.blit(name_txt, (x_pos + 12, y_pos + 8))
            
            money_txt = self.font.render(f"{p.money} €", True, TEXT_WHITE)
            self.screen.blit(money_txt, (x_pos + card_w - money_txt.get_width() - 12, y_pos + 8))
            
            # Sub-Status Zeile
            status_items = []
            if p.yellow_cards > 0: status_items.append(f"Gelb: {p.yellow_cards}")
            if p.has_jail_free_card > 0: status_items.append(f"Freikarten: {p.has_jail_free_card}")
            if p.is_in_jail: status_items.append("GESPERRT")
            elif p.turns_to_skip > 0: status_items.append(f"Aussetzen: {p.turns_to_skip}")
            if not status_items: status_items.append(f"Vereine: {len(p.vereine)}")
            
            sub_txt = self.small_font.render(" | ".join(status_items), True, TEXT_MUTED)
            self.screen.blit(sub_txt, (x_pos + 12, y_pos + 38))

        # --- CENTER LOGO / MATCH INFO ---
        center_x = WIDTH // 2
        
        # Würfel-Visualisierung im Center
        dice_lbl = self.small_font.render("LETZTER WURF", True, TEXT_MUTED)
        self.screen.blit(dice_lbl, (center_x - dice_lbl.get_width()//2, 22))
        
        dice_val = self.title_font.render(self.last_dice_text if self.last_dice_text else "- / -", True, ACCENT_GOLD)
        self.screen.blit(dice_val, (center_x - dice_val.get_width()//2, 42))

        # --- BOTTOM SHORTCUT BAR ---
        bar_rect = pygame.Rect(0, HEIGHT - 40, WIDTH, 40)
        pygame.draw.rect(self.screen, PANEL_BG, bar_rect)
        pygame.draw.rect(self.screen, PANEL_BORDER, bar_rect, 1)
        
        shortcuts_str = "[SPACE] Würfeln   •   [E] Zug beenden   •   [B] Stadion ausbauen   •   [T] Transfermarkt (Trade)   •   [S] Save"
        shortcuts = self.small_font.render(shortcuts_str, True, TEXT_WHITE)
        self.screen.blit(shortcuts, (WIDTH // 2 - shortcuts.get_width() // 2, HEIGHT - 28))

    def draw_message_box(self):
        # Kinematische Verdunklung bei Overlays
        if self.state in ["MESSAGE", "BUY", "JAIL", "BUILD", "TRADE_MENU", "TRADE_DECISION"]:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((15, 23, 42, 180)) # Transparenter Schleier
            self.screen.blit(overlay, (0, 0))

        if self.state == "TRADE_MENU":
            box = pygame.Rect(WIDTH // 2 - 250, HEIGHT // 2 - 130, 500, 260)
            pygame.draw.rect(self.screen, PANEL_BG, box, border_radius=8)
            pygame.draw.rect(self.screen, TEXT_WHITE, box, 2, border_radius=8)
            
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
            
            y = box.y + 25
            for i, row in enumerate(rows):
                color = (34, 197, 94) if i == self.trade_cursor else TEXT_WHITE
                prefix = "▶  " if i == self.trade_cursor else "   "
                txt = self.small_font.render(prefix + row, True, color)
                self.screen.blit(txt, (box.x + 30, y))
                y += 34
                
            help_txt = self.small_font.render("[▲/▼] Zeile  |  [◀/▶] Ändern  |  [J/ENTER] Senden  |  [E] Exit", True, TEXT_MUTED)
            self.screen.blit(help_txt, (box.x + 30, box.y + 220))
            return

        if self.state == "TRADE_DECISION":
            box = pygame.Rect(WIDTH // 2 - 250, HEIGHT // 2 - 110, 500, 220)
            pygame.draw.rect(self.screen, PANEL_BG, box, border_radius=8)
            pygame.draw.rect(self.screen, TEXT_WHITE, box, 2, border_radius=8)
            
            p_cur = self.players[self.current]
            p_oth = self.players[(self.current + 1) % len(self.players)]
            
            g_prop = p_cur.vereine[self.trade_give_prop_idx] if self.trade_give_prop_idx >= 0 else "Keiner"
            t_prop = p_oth.vereine[self.trade_take_prop_idx] if self.trade_take_prop_idx >= 0 else "Keiner"
            
            lines = [
                f"TAUSCHANGEBOT von {p_cur.name}:",
                f"Bietet: {self.trade_give_money}€ & Verein: {g_prop}",
                f"Fordert: {self.trade_take_money}€ & Verein: {t_prop}",
                "",
                f"{p_oth.name}, nimmst du an?",
                "[J] Annehmen      |      [N] Ablehnen"
            ]
            y = box.y + 20
            for line in lines:
                txt = self.small_font.render(line, True, TEXT_WHITE)
                self.screen.blit(txt, (box.x + 30, y))
                y += 28
            return

        if not self.message:
            return

        # Standard Message Box
        box = pygame.Rect(WIDTH // 2 - 240, HEIGHT // 2 - 80, 480, 160)
        pygame.draw.rect(self.screen, PANEL_BG, box, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, box, 2, border_radius=8)

        lines = self.message.split("\n")
        y = box.y + 22
        for line in lines:
            txt = self.small_font.render(line, True, TEXT_WHITE)
            self.screen.blit(txt, (box.x + 25, y))
            y += 25

        if self.state == "BUY":
            yes = self.small_font.render("[J] Kaufen", True, (34, 197, 94))
            no = self.small_font.render("[N] Ablehnen", True, (239, 68, 68))
            self.screen.blit(yes, (box.x + 25, box.y + 120))
            self.screen.blit(no,  (box.x + 160, box.y + 120))
        elif self.state == "JAIL":
            player = self.players[self.current]
            btn1 = self.small_font.render("[J] Freikarte nutzen" if player.has_jail_free_card > 0 else "[J] 50€ Strafe", True, (34, 197, 94))
            btn2 = self.small_font.render("[N] Pasch versuchen", True, ACCENT_GOLD)
            self.screen.blit(btn1, (box.x + 25, box.y + 120))
            self.screen.blit(btn2, (box.x + 200, box.y + 120))
        elif self.state == "BUILD":
            btn1 = self.small_font.render("[J] Ausbauen", True, (34, 197, 94))
            btn2 = self.small_font.render("[N] Nächster", True, ACCENT_GOLD)
            btn3 = self.small_font.render("[E] Beenden", True, (239, 68, 68))
            self.screen.blit(btn1, (box.x + 25, box.y + 120))
            self.screen.blit(btn2, (box.x + 165, box.y + 120))
            self.screen.blit(btn3, (box.x + 300, box.y + 120))
        else:
            ok = self.small_font.render("[J] Bestätigen", True, (34, 197, 94))
            self.screen.blit(ok, (box.x + 25, box.y + 120))

    def run(self):
        while True:
            self.screen.fill(BG_DARK) # Neuer Background-Fill
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.speichern()
                    pygame.quit()
                    sys.exit()
                self.handle_input(event)

            offset = (WIDTH - BOARD_SIZE) // 2
            pygame.draw.rect(self.screen, PITCH_GREEN, (offset, offset, BOARD_SIZE, BOARD_SIZE)) # Stadion-Rasen

            # Spielfeld & Raster zeichnen
            for field in self.fields:
                if field: field.draw(self.screen)
                
            # Spieler zeichnen (Nutzt dein Player-Token-System)
            for player in self.players:
                player.draw(self.screen, self.fields)

            self.draw_ui()
            self.draw_message_box()
            pygame.display.flip()
            self.clock.tick(FPS)

if __name__ == "__main__":
    game = MonopolyGUI()
    game.run()