import pygame

import config


class SourcePoint:
    def __init__(self, pos):
        self.rect = pygame.Rect(pos[0] - 10, pos[1] - 10, 20, 20)
        self.pos = pos

    def update(self):
        pass

    def draw(self, screen):
        screen.blit(config.goal, (self.pos[0] - 16, self.pos[1] - 16))
