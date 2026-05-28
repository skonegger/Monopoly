import pygame
from constants import TILE_SIZE

class Player:
    def __init__(self, name, color, pid):
        self.name     = name
        self.color    = color
        self.id       = pid
        self.position = 0
        self.money    = 1500
        self.vereine  = []
        self.double_count  = 0
        self.turns_to_skip = 0  # Runden aussetzen Zähler

        # --- NEU: Gefängnis- & Karten-Features ---
        self.yellow_cards = 0       # Zähler für gelbe Karten (bei 2 -> Gefängnis)
        self.is_in_jail = False     # Ist der Spieler aktuell im Gefängnis?
        self.jail_turns = 0         # Wie viele Runden schon im Gefängnis (max. 3)
        self.has_jail_free_card = 0 # Anzahl der angesammelten Gefängnisfrei-Karten

    def draw(self, screen, fields):
        center = fields[self.position].rect.center
        offset = -10 if self.id == 1 else 10
        pygame.draw.circle(screen, self.color, (center[0] + offset, center[1]), 12)