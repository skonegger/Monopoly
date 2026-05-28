import pygame

# Bildschirm- & Board-Abmessungen
WIDTH, HEIGHT = 800, 800
BOARD_SIZE = 600
TILE_SIZE = BOARD_SIZE // 11
FPS = 60

# Farbdefinitionen
WHITE = (255, 255, 255)
GREEN = (34, 139, 34)
BLACK = (0, 0, 0)
RED   = (200, 0, 0)
BLUE  = (0, 0, 200)
DARK  = (30, 30, 30)

# Gruppen- & Feld-Farben
COLORS = {
    "group_1": (128, 0, 128),   # Lila (Österreich)
    "group_2": (255, 165, 0),   # Orange (Niederlande)
    "group_3": (64, 224, 208),  # Türkis (Portugal)
    "group_4": (173, 216, 230), # Hellblau (Frankreich)
    "group_5": (255, 0, 0),     # Rot (Bundesliga)
    "group_6": (255, 255, 0),   # Gelb (Serie A)
    "group_7": (255, 192, 203), # Pink (Premier League)
    "group_8": (0, 0, 139),     # Dunkelblau (Spanien)
    "TV":      (0, 0, 0),       # Schwarz (TV-Rechte)
    "card":    (0, 255, 0),     # Grün (VAR/Prämie)
    "utility": (169, 169, 169), # Grau (Sponsoren)
    "default": (200, 200, 200)  # Standard-Grau (Ecken/Steuern)
}