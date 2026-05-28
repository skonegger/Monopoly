import random

def handle_card_draw(game, player, typ):
    if typ == "NATION":
        nation = random.choice(game.nations_data)
        text = f"{nation['name']}:\n{nation['positive_effect']}\n{nation['negative_effect']}\n\n(Nationen-Features folgen im nächsten Update)"
        game.show_message(text)
        game.state = "MESSAGE"
        return

    card = random.choice(game.cards[typ])
    text = card["effekt"]
    card_id = card["id"]
    
    other_player = game.players[1] if game.current == 0 else game.players[0]

    # Standard-Geldeffekte verrechnen
    if "value" in card and not (typ == "VAR" and card_id in [4, 12]):
        player.money += card["value"]

    # ---------------- VAR DECK LOGIK ----------------
    if typ == "VAR":
        if card_id in [3, 39, 46]: # Rote Karten / Direkt ins Gefängnis
            def act():
                game.send_to_jail(player)
            game.pending_card_action = act

        elif card_id == 4: # 3 Felder zurück
            def act():
                player.position = (player.position - 3) % len(game.fields)
                game.land(player)
            game.pending_card_action = act
            
        elif card_id in [6, 11, 25, 31, 33]: # Setze 1 Runde aus
            player.turns_to_skip = 1
            
        elif card_id == 9: # Beide setzen 1 Runde aus
            player.turns_to_skip = 1
            other_player.turns_to_skip = 1
            
        elif card_id == 12: # 2 Felder zurück
            def act():
                player.position = (player.position - 2) % len(game.fields)
                game.land(player)
            game.pending_card_action = act
            
        elif card_id in [13, 26, 32]: # Noch mal würfeln / Extra-Zug
            game.last_roll_was_double = True
            
        elif card_id == 17: # Alle setzen aus (Rudelbildung)
            for p in game.players:
                p.turns_to_skip = 1

        elif card_id in [18, 42]: # Gelbe Karte erhalten
            player.yellow_cards += 1
            if player.yellow_cards >= 2:
                text += "\n-> Gelb-Rote Karte! Du musst auf die Strafbank!"
                def act():
                    game.send_to_jail(player)
                game.pending_card_action = act
            
        elif card_id == 19: # Gegner kriegt Zug
            game.last_roll_was_double = False
            
        elif card_id == 29: # Reise zu Real Madrid (Feld 37)
            def act():
                player.position = 37
                game.land(player)
            game.pending_card_action = act
            
        elif card_id == 37: # Alle gehen 1 Feld zurück
            def act():
                for p in game.players:
                    p.position = (p.position - 1) % len(game.fields)
                game.land(player)
            game.pending_card_action = act

        elif card_id == 38: # Gefängnisfrei-Karte erhalten
            player.has_jail_free_card += 1
            
        elif card_id == 43: # 1 Feld zurück
            def act():
                player.position = (player.position - 1) % len(game.fields)
                game.land(player)
            game.pending_card_action = act
            
        elif card_id == 44: # Positionen tauschen
            def act():
                player.position, other_player.position = other_player.position, player.position
                game.land(player)
            game.pending_card_action = act
            
        elif card_id == 48: # Reise zu PSG (Feld 19)
            def act():
                player.position = 19
                game.land(player)
            game.pending_card_action = act
            
        elif card_id == 49: # Reise zu Bayern München (Feld 24)
            def act():
                player.position = 24
                game.land(player)
            game.pending_card_action = act
            
        elif card_id == 50: # Alle zahlen 50€
            other_player.money -= 50

    # ---------------- PRÄMIEN DECK LOGIK ----------------
    elif typ == "PRÄMIE":
        if card_id == 1: # 20€ von jedem Spieler klauen
            amt = min(other_player.money, 20)
            other_player.money -= amt
            player.money += amt
            
        elif card_id == 4: # 25€ pro eigenen Verein
            player.money += (len(player.vereine) * 25)
            
        elif card_id in [5, 19, 24, 31, 39, 47]: # Setze 1 Runde aus
            player.turns_to_skip = 1
            
        elif card_id in [26, 45]: # Positionen tauschen
            def act():
                player.position, other_player.position = other_player.position, player.position
                game.land(player)
            game.pending_card_action = act
            
        elif card_id == 40: # Alle Spieler erhalten +10€
            other_player.money += 10

    # Schutz vor negativem Kontostand
    for p in game.players:
        if p.money < 0: p.money = 0

    game.show_message(text)
    game.state = "MESSAGE"