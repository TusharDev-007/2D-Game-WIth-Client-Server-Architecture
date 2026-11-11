import pygame
import math
import random

# ============= NETWORK CONSTANTS =============
# CHANGE THESE WHEN DEPLOYING TO CLOUD
# Example: SERVER_IP = "shuttle.proxy.rlwy.net"
#          SERVER_PORT = 15140
SERVER_IP = "altaria.proxy.rlwy.net"  # <--- Change this to Railway Domain
SERVER_PORT = 24106       # <--- Change this to Railway Port
BUFFER_SIZE = 4096
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60

# Colors
SKY_TOP = (10, 50, 150)
SKY_BOTTOM = (100, 180, 230)
GRASS_COLOR = (50, 180, 70)
MOUNTAIN_COLOR = (70, 70, 80)
MOUNTAIN_SNOW = (240, 240, 245)
BORDER_COLOR = (180, 160, 80)
WATER_COLOR = (30, 120, 200)

# ============= SOUND GENERATOR =============
# Assuming you have numpy installed based on previous steps
import numpy as np
class SoundGenerator:
    @staticmethod
    def generate_shoot_sound():
        duration = 0.1; sample_rate = 22050; n_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, n_samples, False)
        freq = np.linspace(800, 200, n_samples)
        wave = np.sin(2 * np.pi * freq * t) * 32767
        wave = wave.astype(np.int16)
        stereo_wave = np.column_stack((wave, wave))
        return pygame.sndarray.make_sound(stereo_wave)

    @staticmethod
    def generate_explosion_sound():
        duration = 0.4; sample_rate = 22050; n_samples = int(duration * sample_rate)
        noise = np.random.randint(-32768, 32767, n_samples)
        decay = np.linspace(1, 0, n_samples)
        wave = (noise * decay).astype(np.int16)
        stereo_wave = np.column_stack((wave, wave))
        return pygame.sndarray.make_sound(stereo_wave)

    @staticmethod
    def generate_pickup_sound():
        duration = 0.2; sample_rate = 22050; n_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, n_samples, False)
        freq = np.linspace(400, 1200, n_samples)
        wave = np.sin(2 * np.pi * freq * t) * 32767
        wave = wave.astype(np.int16)
        stereo_wave = np.column_stack((wave, wave))
        return pygame.sndarray.make_sound(stereo_wave)

# ============= DRAWING FUNCTIONS =============
def draw_sky(screen):
    for y in range(0, WINDOW_HEIGHT // 2, 2):
        ratio = y / (WINDOW_HEIGHT // 2)
        r = SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * ratio
        g = SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * ratio
        b = SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * ratio
        pygame.draw.line(screen, (int(r), int(g), int(b)), (0, y), (WINDOW_WIDTH, y))

def draw_sun(screen):
    sun_x = WINDOW_WIDTH - 150; sun_y = 80
    for radius in range(40, 20, -5):
        alpha = int(80 * (radius - 20) / 20)
        surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 255, 200, alpha), (radius, radius), radius)
        screen.blit(surf, (sun_x - radius, sun_y - radius))
    pygame.draw.circle(screen, (255, 255, 220), (sun_x, sun_y), 20)
    pygame.draw.circle(screen, (255, 255, 180), (sun_x, sun_y), 14)

def draw_mountains(screen):
    mountain_data = [
        [(0, 370), (100, 260), (200, 370)],
        [(150, 370), (280, 210), (410, 370)],
        [(350, 370), (480, 250), (610, 370)],
        [(550, 370), (680, 190), (810, 370)],
        [(750, 370), (880, 230), (1010, 370)],
    ]
    for points in mountain_data:
        pygame.draw.polygon(screen, MOUNTAIN_COLOR, points)
        top = min(points, key=lambda p: p[1])
        idx = points.index(top)
        left = points[(idx - 1) % len(points)]
        right = points[(idx + 1) % len(points)]
        snow = [top, ((top[0] + left[0]) // 2, (top[1] + left[1]) // 2 - 5), ((top[0] + right[0]) // 2, (top[1] + right[1]) // 2 - 5)]
        pygame.draw.polygon(screen, MOUNTAIN_SNOW, snow)

def draw_water(screen):
    pond_rect = pygame.Rect(880, 510, 100, 80)
    pygame.draw.ellipse(screen, WATER_COLOR, pond_rect)
    pygame.draw.ellipse(screen, (20, 80, 150), pond_rect, 2)

def draw_grass(screen):
    pygame.draw.rect(screen, GRASS_COLOR, (0, WINDOW_HEIGHT // 2, WINDOW_WIDTH, WINDOW_HEIGHT // 2))
    random.seed(42)
    for _ in range(80):
        x = random.randint(0, WINDOW_WIDTH)
        y = random.randint(WINDOW_HEIGHT // 2 + 10, WINDOW_HEIGHT - 10)
        height = random.randint(3, 7); shade = random.randint(-15, 15)
        color = (GRASS_COLOR[0] + shade, GRASS_COLOR[1] + shade, GRASS_COLOR[2] + shade)
        pygame.draw.line(screen, color, (x, y), (x, y - height), 1)
    random.seed()

def draw_battlefield_border(screen):
    border_rect = pygame.Rect(25, WINDOW_HEIGHT // 2 + 35, WINDOW_WIDTH - 50, WINDOW_HEIGHT // 2 - 70)
    pygame.draw.rect(screen, BORDER_COLOR, border_rect, 3)
    corners = [(border_rect.left, border_rect.top), (border_rect.right, border_rect.top), (border_rect.left, border_rect.bottom), (border_rect.right, border_rect.bottom)]
    for cx, cy in corners:
        size = 20
        pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx + size, cy), 3)
        pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx, cy + size), 3)
        if cx > WINDOW_WIDTH // 2: pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx - size, cy), 3)
        if cy > WINDOW_HEIGHT // 2: pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx, cy - size), 3)

class PowerUp:
    def __init__(self, x, y, p_type):
        self.x = x; self.y = y; self.type = p_type
        self.width = 30; self.height = 30
        self.active = True; self.pulse = 0
    def update(self):
        self.pulse += 0.1
        return self.active
    def draw(self, screen):
        if not self.active: return
        size_offset = math.sin(self.pulse) * 3
        rect = pygame.Rect(self.x - size_offset, self.y - size_offset, self.width + size_offset*2, self.height + size_offset*2)
        if self.type == 'health':
            pygame.draw.rect(screen, (0, 255, 0), rect, border_radius=5)
            pygame.draw.line(screen, (255, 255, 255), (self.x + 15, self.y + 5), (self.x + 15, self.y + 25), 3)
            pygame.draw.line(screen, (255, 255, 255), (self.x + 5, self.y + 15), (self.x + 25, self.y + 15), 3)

class Tank:
    def __init__(self, x, y, color, controls, name, player_id=1):
        self.x = x; self.y = y; self.color = color; self.controls = controls
        self.name = name; self.player_id = player_id; self.angle = 0
        self.base_speed = 3; self.speed = 3; self.width = 45; self.height = 45
        self.alive = True; self.health = 100; self.max_health = 100
        self.respawn_timer = 0; self.shoot_cooldown = 0; self.track_offset = 0
        self.muzzle_flash_timer = 0; self.speed_boost_timer = 0; self.score = 0

    def move(self, keys):
        if not self.alive: return
        moved = False
        if keys.get(self.controls.get('up'), False): self.y -= self.speed; self.angle = 0; moved = True
        elif keys.get(self.controls.get('down'), False): self.y += self.speed; self.angle = 180; moved = True
        elif keys.get(self.controls.get('left'), False): self.x -= self.speed; self.angle = 270; moved = True
        elif keys.get(self.controls.get('right'), False): self.x += self.speed; self.angle = 90; moved = True
        if moved: self.track_offset = (self.track_offset + 1) % 8
        padding = 40
        self.x = max(25 + padding, min(WINDOW_WIDTH - 25 - self.width - padding, self.x))
        self.y = max(WINDOW_HEIGHT // 2 + 35 + padding, min(WINDOW_HEIGHT - 25 - self.height - padding, self.y))

    def draw(self, screen):
        if not self.alive: return
        pygame.draw.rect(screen, (0, 0, 0, 40), (self.x + 4, self.y + 5, self.width, self.height))
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))
        pygame.draw.rect(screen, (0, 0, 0), (self.x, self.y, self.width, self.height), 2)
        pygame.draw.rect(screen, (40, 40, 40), (self.x - 3, self.y + 5, 6, self.height - 10))
        pygame.draw.rect(screen, (40, 40, 40), (self.x + self.width - 3, self.y + 5, 6, self.height - 10))
        for i in range(4):
            offset = (i * 10 + self.track_offset) % 20
            pygame.draw.line(screen, (80, 80, 80), (self.x - 1, self.y + 8 + offset), (self.x + 1, self.y + 8 + offset), 1)
            pygame.draw.line(screen, (80, 80, 80), (self.x + self.width - 1, self.y + 8 + offset), (self.x + self.width + 1, self.y + 8 + offset), 1)
        cx, cy = self.x + self.width // 2, self.y + self.height // 2
        pygame.draw.circle(screen, (200, 200, 200), (cx, cy), 14)
        pygame.draw.circle(screen, self.color, (cx, cy), 12)
        pygame.draw.circle(screen, (0, 0, 0), (cx, cy), 12, 1)
        rad = math.radians(self.angle)
        ex, ey = cx + 25 * math.sin(rad), cy - 25 * math.cos(rad)
        pygame.draw.line(screen, (30, 30, 30), (cx, cy), (ex, ey), 6)
        pygame.draw.line(screen, (150, 150, 150), (cx, cy), (ex, ey), 4)
        pygame.draw.rect(screen, (40, 40, 40), (self.x - 5, self.y - 20, 100, 12))
        hw = int((self.health / self.max_health) * 100)
        if hw > 0:
            r = self.health / self.max_health
            pygame.draw.rect(screen, (int(255*(1-r)), int(255*r), 0), (self.x - 5, self.y - 20, hw, 12))
        pygame.draw.rect(screen, (200, 200, 200), (self.x - 5, self.y - 20, 100, 12), 1)
        if self.speed_boost_timer > 0: pygame.draw.rect(screen, (255, 255, 0), (self.x - 5, self.y - 35, 100, 5))

    def shoot(self):
        if not self.alive or self.shoot_cooldown > 0: return None
        self.shoot_cooldown = 15; self.muzzle_flash_timer = 6
        return Bullet(self.x + self.width // 2, self.y + self.height // 2, self.angle, self.player_id)

    def update(self):
        if self.shoot_cooldown > 0: self.shoot_cooldown -= 1
        if self.speed_boost_timer > 0: self.speed_boost_timer -= 1; self.speed = self.base_speed + 2
        else: self.speed = self.base_speed
        if not self.alive:
            self.respawn_timer += 1
            if self.respawn_timer > 120: self.respawn()

    def respawn(self):
        self.alive = True; self.health = self.max_health; self.respawn_timer = 0
        self.x = random.choice([random.randint(40, 200), random.randint(WINDOW_WIDTH - 250, WINDOW_WIDTH - 60)])
        self.y = random.randint(WINDOW_HEIGHT // 2 + 50, WINDOW_HEIGHT - 100)

    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0: self.health = 0; self.alive = False; return True
        return False

    def get_state(self):
        return {'x': self.x, 'y': self.y, 'angle': self.angle, 'health': self.health, 'alive': self.alive, 'player_id': self.player_id}

class Bullet:
    def __init__(self, x, y, angle, owner_id):
        self.x = x; self.y = y; self.angle = angle; self.owner_id = owner_id
        self.speed = 9; self.alive = True; self.trail = []
        self.dx = self.speed * math.sin(math.radians(angle)); self.dy = -self.speed * math.cos(math.radians(angle))
    def move(self):
        self.trail.append((int(self.x), int(self.y)))
        if len(self.trail) > 8: self.trail.pop(0)
        self.x += self.dx; self.y += self.dy
        if (self.x < 25 or self.x > WINDOW_WIDTH - 25 or self.y < WINDOW_HEIGHT // 2 + 35 or self.y > WINDOW_HEIGHT - 25): self.alive = False
    def draw(self, screen):
        if not self.alive: return
        for i, pos in enumerate(self.trail):
            alpha = int(150 * (i / len(self.trail))); size = int(3 * (i / len(self.trail)) + 1)
            surf = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 200, 50, alpha), (size, size), size)
            screen.blit(surf, (pos[0] - size, pos[1] - size))
        pygame.draw.circle(screen, (255, 255, 200), (int(self.x), int(self.y)), 4)
        pygame.draw.circle(screen, (255, 200, 50), (int(self.x), int(self.y)), 5, 1)
    def get_state(self):
        return {'x': self.x, 'y': self.y, 'angle': self.angle, 'owner_id': self.owner_id, 'alive': self.alive}