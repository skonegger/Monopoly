import pygame
import sys
import random
import json

# ================= CONFIG =================
WIDTH, HEIGHT = 800, 800
BOARD_SIZE = 600
TILE_SIZE = BOARD_SIZE // 11
FPS = 60

WHITE = (255, 255, 255)
GREEN = (34, 139, 34)
BLACK = (0, 0, 0)

RED = (200, 0, 0)
BLUE = (0, 0, 200)

DARK = (30, 30, 30)


# ================= FIELD =================
class Field:

    def __init__(self, data, x, y):

        self.data = data
        self.name = data["name"]

        self.rect = pygame.Rect(
            x,
            y,
            TILE_SIZE,
            TILE_SIZE
        )

        self.owner = None

        self.price = data.get("price", 0)
        self.rent = data.get("rent", 0)

    def draw(self, screen):

        pygame.draw.rect(screen, WHITE, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)

        font = pygame.font.SysFont("Arial", 10)

        text = font.render(
            self.name[:10],
            True,
            BLACK
        )

        screen.blit(
            text,
            (self.rect.x + 4, self.rect.y + 18)
        )

        # Besitzer anzeigen
        if self.owner:

            owner = font.render(
                self.owner,
                True,
                (90, 90, 90)
            )

            screen.blit(
                owner,
                (self.rect.x + 4, self.rect.y + 38)
            )


# ================= PLAYER =================
class Player:

    def __init__(self, name, color, pid):

        self.name = name
        self.color = color
        self.id = pid

        self.position = 0
        self.money = 1500

        # Pasch-System
        self.double_count = 0

    def draw(self, screen, fields):

        center = fields[self.position].rect.center

        offset = -10 if self.id == 1 else 10

        pygame.draw.circle(
            screen,
            self.color,
            (center[0] + offset, center[1]),
            12
        )


# ================= GAME =================
class MonopolyGUI:

    def __init__(self):

        pygame.init()

        self.screen = pygame.display.set_mode(
            (WIDTH, HEIGHT)
        )

        pygame.display.set_caption(
            "Fußball Monopoly"
        )

        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont(
            "Arial",
            22
        )

        self.small_font = pygame.font.SysFont(
            "Arial",
            16
        )

        # Spieler
        self.players = [
            Player("Rot", RED, 1),
            Player("Blau", BLUE, 2)
        ]

        self.current = 0

        # Spielfeld
        self.fields = self.load_board()

        # Karten
        self.cards = self.load_cards()

        # Zustände:
        # IDLE
        # BUY
        # MESSAGE
        self.state = "IDLE"

        self.message = None
        self.buy_field = None

        # Würfelanzeige
        self.last_dice_text = ""

        # Pasch
        self.last_roll_was_double = False

    # ================= LOAD =================
    def load_board(self):

        with open(
            "spielfeld.json",
            "r",
            encoding="utf-8"
        ) as f:

            board = json.load(f)["board"]

        fields = [None] * 40

        offset = (WIDTH - BOARD_SIZE) // 2

        for data in board:

            i = data["id"]

            if 0 <= i <= 10:

                x = offset + BOARD_SIZE - (
                    i + 1
                ) * TILE_SIZE

                y = offset + BOARD_SIZE - TILE_SIZE

            elif 11 <= i <= 20:

                x = offset

                y = offset + BOARD_SIZE - (
                    (i - 10) + 1
                ) * TILE_SIZE

            elif 21 <= i <= 30:

                x = offset + (
                    i - 20
                ) * TILE_SIZE

                y = offset

            else:

                x = offset + BOARD_SIZE - TILE_SIZE

                y = offset + (
                    i - 30
                ) * TILE_SIZE

            fields[i] = Field(data, x, y)

        return fields

    def load_cards(self):

        with open(
            "cards.json",
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)["cards"]

    # ================= MESSAGE =================
    def show_message(self, text):

        self.message = text

    # ================= NEXT PLAYER =================
    def next_player(self):

        self.current = (
            self.current + 1
        ) % len(self.players)

    # ================= CARDS =================
    def draw_card(self, player, typ):

        card = random.choice(
            self.cards[typ]
        )

        self.apply_card(player, card)

        self.show_message(
            card["effekt"]
        )

        self.state = "MESSAGE"

    def apply_card(self, player, card):

        text = card["effekt"]

        # Geld
        if "value" in card:

            player.money += card["value"]

            # ❌ KEIN NEGATIVES GELD
            if player.money < 0:
                player.money = 0

        # Bewegung
        if "Gehe 3 Felder zurück" in text:

            player.position = (
                player.position - 3
            ) % len(self.fields)

        elif "Gehe 2 Felder zurück" in text:

            player.position = (
                player.position - 2
            ) % len(self.fields)

        elif "Gehe 1 Feld zurück" in text:

            player.position = (
                player.position - 1
            ) % len(self.fields)

    # ================= LAND =================
    def land(self, player):

        field = self.fields[
            player.position
        ]

        field_type = field.data.get("type")

        # 🎴 KARTEN
        if field_type == "card":

            if field.name.upper() == "VAR":

                self.draw_card(
                    player,
                    "VAR"
                )

            else:

                self.draw_card(
                    player,
                    "PRÄMIE"
                )

            return

        # 🏟 VEREIN
        if field_type in ["property", "TV"]:

            # Frei
            if field.owner is None:

                self.buy_field = field

                self.show_message(
                    f"{player.name}: {field.name} kaufen?\n"
                    f"Preis: {field.price}€"
                )

                self.state = "BUY"

            # Miete
            elif field.owner != player.name:

                rent = field.rent

                # ❌ KEIN GAME OVER
                payment = min(
                    player.money,
                    rent
                )

                player.money -= payment

                for p in self.players:

                    if p.name == field.owner:
                        p.money += payment

                self.show_message(
                    f"{player.name} zahlt "
                    f"{payment}€ an "
                    f"{field.owner}"
                )

                self.state = "MESSAGE"

    # ================= DICE =================
    def roll_dice(self):

        player = self.players[
            self.current
        ]

        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)

        steps = dice1 + dice2

        # 🎲 Würfelanzeige
        self.last_dice_text = (
            f"{dice1}+{dice2}={steps}"
        )

        # 🎲 PASCH
        pasch = dice1 == dice2

        self.last_roll_was_double = pasch

        if pasch:
            player.double_count += 1
        else:
            player.double_count = 0

        # 🚔 3 Pasche
        if player.double_count >= 3:

            player.double_count = 0

            self.show_message(
                f"{player.name} hatte "
                f"3 Pasche!"
            )

            self.state = "MESSAGE"

            return

        # Bewegung
        player.position = (
            player.position + steps
        ) % len(self.fields)

        # Feldaktion
        self.land(player)

        # Wenn nix passiert
        if self.state == "IDLE":

            if pasch:

                self.show_message(
                    "PASCH!\n"
                    "Nochmal würfeln."
                )

                self.state = "MESSAGE"

            else:

                self.next_player()

    # ================= INPUT =================
    def handle_input(self, event):

        if event.type != pygame.KEYDOWN:
            return

        player = self.players[
            self.current
        ]

        # ================= MESSAGE =================
        if self.state == "MESSAGE":

            if event.key == pygame.K_j:

                self.message = None

                # Pasch
                if self.last_roll_was_double:

                    self.last_roll_was_double = False

                    self.state = "IDLE"

                else:

                    self.state = "IDLE"

                    self.next_player()

            return

        # ================= BUY =================
        if self.state == "BUY":

            # JA
            if event.key == pygame.K_j:

                if player.money >= self.buy_field.price:

                    player.money -= self.buy_field.price

                    self.buy_field.owner = player.name

                    self.show_message(
                        f"{player.name} kauft\n"
                        f"{self.buy_field.name}"
                    )

                else:

                    self.show_message(
                        "Nicht genug Geld!"
                    )

                self.state = "MESSAGE"

            # NEIN
            elif event.key == pygame.K_n:

                self.show_message(
                    "Nicht gekauft."
                )

                self.state = "MESSAGE"

            self.buy_field = None

            return

        # ================= IDLE =================
        if self.state == "IDLE":

            if event.key == pygame.K_SPACE:

                self.roll_dice()

    # ================= UI =================
    def draw_ui(self):

        y = 10

        # Geld
        for p in self.players:

            txt = self.font.render(
                f"{p.name}: {p.money}€",
                True,
                p.color
            )

            self.screen.blit(
                txt,
                (20, y)
            )

            y += 30

        # Spieler dran
        turn = self.font.render(
            f"Dran: {self.players[self.current].name}",
            True,
            BLACK
        )

        self.screen.blit(
            turn,
            (20, y + 10)
        )

        # 🎲 Würfelanzeige
        dice = self.font.render(
            f"Wurf: {self.last_dice_text}",
            True,
            BLACK
        )

        self.screen.blit(
            dice,
            (20, y + 45)
        )

    # ================= MESSAGE BOX =================
    def draw_message_box(self):

        if not self.message:
            return

        box = pygame.Rect(
            150,
            520,
            500,
            150
        )

        pygame.draw.rect(
            self.screen,
            DARK,
            box
        )

        pygame.draw.rect(
            self.screen,
            WHITE,
            box,
            2
        )

        lines = self.message.split("\n")

        y = 545

        for line in lines:

            txt = self.small_font.render(
                line,
                True,
                WHITE
            )

            self.screen.blit(
                txt,
                (170, y)
            )

            y += 28

        # BUY
        if self.state == "BUY":

            yes = self.small_font.render(
                "J = JA",
                True,
                (0, 255, 0)
            )

            no = self.small_font.render(
                "N = NEIN",
                True,
                (255, 0, 0)
            )

            self.screen.blit(
                yes,
                (170, 630)
            )

            self.screen.blit(
                no,
                (320, 630)
            )

        # MESSAGE
        else:

            ok = self.small_font.render(
                "J = OK",
                True,
                (0, 255, 0)
            )

            self.screen.blit(
                ok,
                (170, 630)
            )

    # ================= MAIN LOOP =================
    def run(self):

        while True:

            self.screen.fill(WHITE)

            # EVENTS
            for event in pygame.event.get():

                if event.type == pygame.QUIT:

                    pygame.quit()
                    sys.exit()

                self.handle_input(event)

            # BOARD
            pygame.draw.rect(
                self.screen,
                GREEN,
                (
                    (WIDTH - BOARD_SIZE) // 2,
                    (HEIGHT - BOARD_SIZE) // 2,
                    BOARD_SIZE,
                    BOARD_SIZE
                )
            )

            # FIELDS
            for field in self.fields:

                if field:
                    field.draw(self.screen)

            # PLAYERS
            for player in self.players:

                player.draw(
                    self.screen,
                    self.fields
                )

            # UI
            self.draw_ui()

            # MESSAGE
            self.draw_message_box()

            pygame.display.flip()

            self.clock.tick(FPS)


# ================= START =================
if __name__ == "__main__":

    game = MonopolyGUI()
    game.run()