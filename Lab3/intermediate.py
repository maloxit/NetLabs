import math
import random
import pygame

import config


class IntermediatePoint:
    def __init__(self, pos, radius, is_master=False):
        self.rect = pygame.Rect(pos[0] - 16, pos[1] - 16, 32, 32)
        self.pos = pos
        self.radius = radius
        self.health = 100
        self.is_master = is_master
        self.connection_pos = None
        self.active = False
        self.heat_mult = random.randrange(1, 4)

    def update(self):
        self.health += 1
        if self.is_master:
            self.health = 100
        if self.health >= 100:
            self.active = True
            self.health = 100
        if self.active and self.health <= 0:
            self.active = False

        self.connection_pos = None

    def drawConnections(self, screen, font):
        if self.connection_pos != None:
            pygame.draw.line(screen, config.PLAYER_COLORS[1], self.pos, self.connection_pos, 10)

    def draw(self, screen, font):
        if self.active:
            color_id = 1
            color = config.PLAYER_COLORS[1]
        else:
            color_id = 0
            color = config.PLAYER_COLORS[0]

        alpha_color = [color[0], color[1], color[2], 50]
        pygame.draw.circle(screen, alpha_color, self.pos, self.radius, 1)

        if self.active:
            pygame.draw.circle(screen, color, self.pos, self.radius, 1)
            pygame.draw.circle(screen, color, self.pos, 20, 0)

        if self.is_master:
            screen.blit(config.colored_players[color_id], (self.pos[0] - 16, self.pos[1] - 16))
        else:
            screen.blit(config.colored_nodes[color_id], (self.pos[0] - 16, self.pos[1] - 16))

        text = font.render(str(self.health), True, (255, 255, 255))
        screen.blit(text, (self.pos[0] - 10, self.pos[1] + 10))

    def getNeighborsIndices(self, all_neighbors):
        res = []
        for i in range(len(all_neighbors)):
            if self.pos[0] == all_neighbors[i].pos[0] and self.pos[1] == all_neighbors[i].pos[1]:
                continue
            if (self.pos[0] - all_neighbors[i].pos[0]) ** 2 + (self.pos[1] - all_neighbors[i].pos[1]) ** 2 < self.radius ** 2:
                res.append(i)
        return res

    def getActiveNeighborsIndices(self, all_neighbors):
        res = []
        for i in range(len(all_neighbors)):
            if self.pos[0] == all_neighbors[i].pos[0] and self.pos[1] == all_neighbors[i].pos[1]:
                continue
            if all_neighbors[i].active:
                if (self.pos[0] - all_neighbors[i].pos[0]) ** 2 + (self.pos[1] - all_neighbors[i].pos[1]) ** 2 < self.radius ** 2:
                    res.append(i)
        return res

    def connect(self, connection_pos):
        self.connection_pos = connection_pos