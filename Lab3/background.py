import config


class Background:
    def __init__(self):
        self.image = config.background

    def update(self):
        pass

    def draw(self, screen):
        screen.blit(self.image, (0, 0))