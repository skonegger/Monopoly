import pygame
from constants import WHITE, BLACK, COLORS, TILE_SIZE

class Field:
    def __init__(self, data, x, y):
        self.data  = data
        self.name  = data["name"]
        self.rect  = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.owner = None
        self.price = data.get("price", 0)
        self.rent  = data.get("rent", 0)
        
        f_type = data.get("type")
        group  = data.get("group")
        
        if f_type == "property" and group:
            self.color = COLORS.get(f"group_{group}", COLORS["default"])
        else:
            self.color = COLORS.get(f_type, COLORS["default"])

    def draw(self, screen):
        pygame.draw.rect(screen, WHITE, self.rect)
        pygame.draw.rect(screen, self.color, pygame.Rect(self.rect.x, self.rect.y, TILE_SIZE, 15))
        pygame.draw.rect(screen, BLACK, self.rect, 2)
        
        font = pygame.font.SysFont("Arial", 10, bold=True)
        text = font.render(self.name[:10], True, BLACK)
        screen.blit(text, (self.rect.x + 4, self.rect.y + 18))
        
        if self.owner:
            owner_font = pygame.font.SysFont("Arial", 9, bold=True)
            owner_text = owner_font.render(f"P: {self.owner}", True, (50, 50, 50))
            screen.blit(owner_text, (self.rect.x + 4, self.rect.y + TILE_SIZE - 12))