# shared.py
class GameState:
    def __init__(self):
        self.players = [
            {"name": "Spieler 1", "position": 0, "money": 1500, "vereine": [], "color": (200, 0, 0)},
            {"name": "Spieler 2", "position": 0, "money": 1500, "vereine": [], "color": (0, 0, 200)}
        ]
        self.current_player_idx = 0
        self.field_owners = {str(i): None for i in range(40)}
        self.active_buy_prompt = False
        self.current_field_to_buy_idx = None
        self.active_card = None
        self.game_started = False