import pygame
import json
from player import Player


# Loading config with variables
json_data = {}
with open("config.json", "rt") as f:
    json_data = json.load(f)

PLAYER_COLORS = json_data["player_colors"]
SCREEN_WIDTH = json_data["screen_width"]
SCREEN_HEIGHT = json_data["screen_height"]
SCREEN_SAFE_LEFT = json_data["screen_offset_left"]
SCREEN_SAFE_RIGHT = SCREEN_WIDTH - json_data["screen_offset_right"]
SCREEN_SAFE_TOP = json_data["screen_offset_top"]
SCREEN_SAFE_BOTTOM = SCREEN_HEIGHT - json_data["screen_offset_bottom"]
MIN_NODES_DIST = json_data["node_min_dist_between"]
MIN_NODE_RADIUS = json_data["node_min_radius"]
MAX_NODE_RADIUS = max(json_data["node_max_radius"],json_data["node_min_radius"] + 1)
NODE_RANDOM_PLACEMENT_ADDITIONAL_POINTS = json_data["node_placement_random_additional_points"]
NODE_PLACEMENT_METHOD = json_data["node_placement_method"]
PLAYER_POSITION = json_data["player_position"]
TARGET_POSITION = json_data["target_position"]
PLAYER = []


# load images
background = pygame.image.load(json_data["background_img"])
node = pygame.image.load(json_data["node_img"])
goal = pygame.image.load(json_data["goal_img"])
player = pygame.image.load(json_data["player_img"])

# generate colored images
colored_players = [
    player.copy(),
    player.copy(),
    player.copy(),
    player.copy(),
    player.copy()
]

colored_nodes = [
    node.copy(),
    node.copy(),
    node.copy(),
    node.copy(),
    node.copy()
]

for i in range(len(PLAYER_COLORS)):
    colored_players[i].fill(PLAYER_COLORS[i], special_flags=pygame.BLEND_RGBA_MIN)
    colored_nodes[i].fill(PLAYER_COLORS[i], special_flags=pygame.BLEND_RGBA_MIN)

# generate players
PLAYER = Player()
