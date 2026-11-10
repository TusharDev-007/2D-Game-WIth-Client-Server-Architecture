import pygame
import sys
import math
import random

# Initialize Pygame
pygame.init()

# Constants
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

# Create window
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Tank Battle Arena")
clock = pygame.time.Clock()

# ============= GAME STATE =============
clouds = []
craters = []
particles = []
shell_casings = []

# ============= CLOUD FUNCTIONS =============

def generate_cloud_shape(width):
    """Generate natural cloud shape with overlapping circles"""
    circles = []
    
    # Main body
    num_main = random.randint(3, 5)
    for i in range(num_main):
        x = random.randint(width // 5, width - width // 5)
        y = random.randint(15, 35)
        radius = random.randint(22, 40)
        circles.append((x, y, radius))
    
    # Top bumps
    num_top = random.randint(2, 4)
    for i in range(num_top):
        x = random.randint(width // 6, width - width // 6)
        y = random.randint(5, 25)
        radius = random.randint(15, 30)
        circles.append((x, y, radius))
    
    # Bottom flat-ish circles
    num_bottom = random.randint(2, 3)
    for i in range(num_bottom):
        x = random.randint(width // 4, width - width // 4)
        y = random.randint(30, 45)
        radius = random.randint(18, 28)
        circles.append((x, y, radius))
    
    # Edge details
    for _ in range(2):
        x = random.randint(0, width)
        y = random.randint(20, 35)
        radius = random.randint(8, 18)
        circles.append((x, y, radius))
    
    return circles

def init_clouds():
    global clouds
    clouds = []
    # Fixed cloud positions - NO MOVEMENT
    cloud_positions = [
        (50, 40, 150),
        (250, 60, 120),
        (450, 30, 180),
        (700, 70, 130),
        (900, 45, 160),
        (150, 120, 110),
        (600, 110, 140),
        (850, 130, 100)
    ]
    
    for x, y, width in cloud_positions:
        clouds.append({
            'x': x,
            'y': y,
            'width': width,
            'opacity': random.randint(160, 210),
            'circles': generate_cloud_shape(width)
        })

init_clouds()

# ============= DRAWING FUNCTIONS =============

def draw_sky():
    """Gradient sky"""
    for y in range(0, WINDOW_HEIGHT // 2, 2):
        ratio = y / (WINDOW_HEIGHT // 2)
        r = SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * ratio
        g = SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * ratio
        b = SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * ratio
        pygame.draw.line(screen, (int(r), int(g), int(b)), (0, y), (WINDOW_WIDTH, y))

def draw_sun():
    """Simple sun"""
    sun_x = WINDOW_WIDTH - 150
    sun_y = 80
    # Glow
    for radius in range(40, 20, -5):
        alpha = int(80 * (radius - 20) / 20)
        surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 255, 200, alpha), (radius, radius), radius)
        screen.blit(surf, (sun_x - radius, sun_y - radius))
    # Core
    pygame.draw.circle(screen, (255, 255, 220), (sun_x, sun_y), 20)
    pygame.draw.circle(screen, (255, 255, 180), (sun_x, sun_y), 14)

def draw_clouds():
    """Static clouds - NO MOVEMENT, NO TRAILS"""
    for cloud in clouds:
        cloud_x = cloud['x']
        cloud_y = cloud['y']
        opacity = cloud['opacity']
        
        for x, y, radius in cloud['circles']:
            # Create a surface for each circle with alpha
            surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            # Main circle
            pygame.draw.circle(surf, (255, 255, 255, opacity // 2), (radius, radius), radius)
            # Highlight
            pygame.draw.circle(surf, (255, 255, 255, opacity // 6), (radius - 2, radius - 3), radius - 4)
            # Blit to screen
            screen.blit(surf, (cloud_x + x - radius, cloud_y + y - radius))

def draw_mountains():
    """Mountain range"""
    mountain_data = [
        [(0, 370), (100, 260), (200, 370)],
        [(150, 370), (280, 210), (410, 370)],
        [(350, 370), (480, 250), (610, 370)],
        [(550, 370), (680, 190), (810, 370)],
        [(750, 370), (880, 230), (1010, 370)],
    ]
    
    for points in mountain_data:
        pygame.draw.polygon(screen, MOUNTAIN_COLOR, points)
        # Snow
        top = min(points, key=lambda p: p[1])
        idx = points.index(top)
        left = points[(idx - 1) % len(points)]
        right = points[(idx + 1) % len(points)]
        snow = [
            top,
            ((top[0] + left[0]) // 2, (top[1] + left[1]) // 2 - 5),
            ((top[0] + right[0]) // 2, (top[1] + right[1]) // 2 - 5)
        ]
        pygame.draw.polygon(screen, MOUNTAIN_SNOW, snow)

def draw_water():
    """Simple pond"""
    pond_rect = pygame.Rect(880, 510, 100, 80)
    pygame.draw.ellipse(screen, WATER_COLOR, pond_rect)
    pygame.draw.ellipse(screen, (20, 80, 150), pond_rect, 2)

def draw_grass():
    """Grass with texture"""
    pygame.draw.rect(screen, GRASS_COLOR, (0, WINDOW_HEIGHT // 2, WINDOW_WIDTH, WINDOW_HEIGHT // 2))
    
    # Grass blades
    for _ in range(80):
        x = random.randint(0, WINDOW_WIDTH)
        y = random.randint(WINDOW_HEIGHT // 2 + 10, WINDOW_HEIGHT - 10)
        height = random.randint(3, 7)
        shade = random.randint(-15, 15)
        color = (GRASS_COLOR[0] + shade, GRASS_COLOR[1] + shade, GRASS_COLOR[2] + shade)
        pygame.draw.line(screen, color, (x, y), (x, y - height), 1)

def draw_craters():
    """Destructible terrain"""
    for crater in craters:
        for radius in range(crater['size'], 0, -4):
            alpha = int(60 * (radius / crater['size']))
            color = (40, 30, 20, alpha)
            surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (radius, radius), radius)
            screen.blit(surf, (crater['x'] - radius, crater['y'] - radius))

def draw_battlefield_border():
    """Arena border"""
    border_rect = pygame.Rect(25, WINDOW_HEIGHT // 2 + 35, WINDOW_WIDTH - 50, WINDOW_HEIGHT // 2 - 70)
    pygame.draw.rect(screen, BORDER_COLOR, border_rect, 3)
    
    # Corners
    corners = [
        (border_rect.left, border_rect.top),
        (border_rect.right, border_rect.top),
        (border_rect.left, border_rect.bottom),
        (border_rect.right, border_rect.bottom)
    ]
    for cx, cy in corners:
        size = 20
        pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx + size, cy), 3)
        pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx, cy + size), 3)
        if cx > WINDOW_WIDTH // 2:
            pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx - size, cy), 3)
        if cy > WINDOW_HEIGHT // 2:
            pygame.draw.line(screen, BORDER_COLOR, (cx, cy), (cx, cy - size), 3)

def draw_health_bar(screen, x, y, health, max_health, color, width=100, height=12):
    """Health bar"""
    pygame.draw.rect(screen, (40, 40, 40), (x, y, width, height))
    health_width = int((health / max_health) * width)
    if health_width > 0:
        health_ratio = health / max_health
        r = int(255 * (1 - health_ratio))
        g = int(255 * health_ratio)
        pygame.draw.rect(screen, (r, g, 0), (x, y, health_width, height))
    pygame.draw.rect(screen, (200, 200, 200), (x, y, width, height), 1)

# ============= CLASSES =============

class Tank:
    def __init__(self, x, y, color, controls, name):
        self.x = x
        self.y = y
        self.color = color
        self.controls = controls
        self.name = name
        self.angle = 0
        self.speed = 3
        self.width = 45
        self.height = 45
        self.alive = True
        self.health = 100
        self.max_health = 100
        self.respawn_timer = 0
        self.shoot_cooldown = 0
        self.track_offset = 0
        self.muzzle_flash_timer = 0
    
    def move(self, keys):
        if not self.alive:
            return
            
        moved = False
        if keys[self.controls['up']]:
            self.y -= self.speed
            self.angle = 0
            moved = True
        elif keys[self.controls['down']]:
            self.y += self.speed
            self.angle = 180
            moved = True
        elif keys[self.controls['left']]:
            self.x -= self.speed
            self.angle = 270
            moved = True
        elif keys[self.controls['right']]:
            self.x += self.speed
            self.angle = 90
            moved = True
        
        if moved:
            self.track_offset = (self.track_offset + 1) % 8
        
        # Keep inside battlefield
        padding = 40
        min_x = 25 + padding
        max_x = WINDOW_WIDTH - 25 - self.width - padding
        min_y = WINDOW_HEIGHT // 2 + 35 + padding
        max_y = WINDOW_HEIGHT - 25 - self.height - padding
        
        self.x = max(min_x, min(max_x, self.x))
        self.y = max(min_y, min(max_y, self.y))
    
    def draw(self, screen):
        if not self.alive:
            return
        
        # Shadow
        shadow_rect = pygame.Rect(self.x + 4, self.y + 5, self.width, self.height)
        pygame.draw.rect(screen, (0, 0, 0, 40), shadow_rect)
        
        # Body
        tank_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, self.color, tank_rect)
        pygame.draw.rect(screen, (0, 0, 0), tank_rect, 2)
        
        # Tracks
        track_color = (40, 40, 40)
        pygame.draw.rect(screen, track_color, (self.x - 3, self.y + 5, 6, self.height - 10))
        pygame.draw.rect(screen, track_color, (self.x + self.width - 3, self.y + 5, 6, self.height - 10))
        
        # Track treads
        for i in range(4):
            offset = (i * 10 + self.track_offset) % 20
            pygame.draw.line(screen, (80, 80, 80), 
                           (self.x - 1, self.y + 8 + offset), 
                           (self.x + 1, self.y + 8 + offset), 1)
            pygame.draw.line(screen, (80, 80, 80), 
                           (self.x + self.width - 1, self.y + 8 + offset), 
                           (self.x + self.width + 1, self.y + 8 + offset), 1)
        
        # Turret
        center_x = self.x + self.width // 2
        center_y = self.y + self.height // 2
        pygame.draw.circle(screen, (200, 200, 200), (center_x, center_y), 14)
        pygame.draw.circle(screen, self.color, (center_x, center_y), 12)
        pygame.draw.circle(screen, (0, 0, 0), (center_x, center_y), 12, 1)
        
        # Barrel
        barrel_length = 25
        angle_rad = math.radians(self.angle)
        end_x = center_x + barrel_length * math.sin(angle_rad)
        end_y = center_y - barrel_length * math.cos(angle_rad)
        pygame.draw.line(screen, (30, 30, 30), (center_x, center_y), (end_x, end_y), 6)
        pygame.draw.line(screen, (150, 150, 150), (center_x, center_y), (end_x, end_y), 4)
        pygame.draw.circle(screen, (200, 100, 50), (int(end_x), int(end_y)), 3)
        
        # Muzzle flash
        if self.muzzle_flash_timer > 0:
            self.muzzle_flash_timer -= 1
            flash_size = 15 - self.muzzle_flash_timer
            pygame.draw.circle(screen, (255, 255, 200), (int(end_x), int(end_y)), flash_size)
        
        # Health bar
        health_bar_x = self.x - 5
        health_bar_y = self.y - 20
        draw_health_bar(screen, health_bar_x, health_bar_y, self.health, self.max_health, self.color)
        
        # Name
        font = pygame.font.Font(None, 14)
        name_text = font.render(self.name, True, (255, 255, 255))
        name_rect = name_text.get_rect(center=(center_x, self.y - 28))
        screen.blit(name_text, name_rect)
    
    def shoot(self):
        if not self.alive or self.shoot_cooldown > 0:
            return None
        
        self.shoot_cooldown = 15
        self.muzzle_flash_timer = 6
        center_x = self.x + self.width // 2
        center_y = self.y + self.height // 2
        
        shell_casings.append({
            'x': center_x,
            'y': center_y,
            'speed_x': random.uniform(-1.5, 1.5),
            'speed_y': random.uniform(-3, -1),
            'life': 40
        })
        
        return Bullet(center_x, center_y, self.angle, self)
    
    def update(self):
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        
        if not self.alive:
            self.respawn_timer += 1
            if self.respawn_timer > 120:
                self.respawn()
    
    def respawn(self):
        self.alive = True
        self.health = self.max_health
        self.respawn_timer = 0
        side = random.choice(['left', 'right'])
        if side == 'left':
            self.x = random.randint(40, 200)
        else:
            self.x = random.randint(WINDOW_WIDTH - 250, WINDOW_WIDTH - 60)
        self.y = random.randint(WINDOW_HEIGHT // 2 + 50, WINDOW_HEIGHT - 100)
        
        for _ in range(15):
            particles.append(Particle(
                self.x + self.width//2,
                self.y + self.height//2,
                (100, 255, 100),
                random.randint(3, 8),
                random.uniform(-5, 5),
                random.uniform(-5, 5)
            ))
    
    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.health = 0
            self.alive = False
            # Explosion
            for _ in range(25):
                particles.append(Particle(
                    self.x + self.width//2 + random.randint(-15, 15),
                    self.y + self.height//2 + random.randint(-15, 15),
                    (255, 200, 50),
                    random.randint(3, 12),
                    random.uniform(-8, 8),
                    random.uniform(-8, 8)
                ))
            for _ in range(15):
                particles.append(Particle(
                    self.x + self.width//2 + random.randint(-20, 20),
                    self.y + self.height//2 + random.randint(-20, 20),
                    (255, 100, 50),
                    random.randint(3, 10),
                    random.uniform(-6, 6),
                    random.uniform(-10, 3)
                ))
            craters.append({
                'x': self.x + self.width//2,
                'y': self.y + self.height//2,
                'size': random.randint(25, 40)
            })

class Bullet:
    def __init__(self, x, y, angle, owner):
        self.x = x
        self.y = y
        self.angle = angle
        self.owner = owner
        self.speed = 9
        self.alive = True
        self.trail = []
        self.dx = self.speed * math.sin(math.radians(angle))
        self.dy = -self.speed * math.cos(math.radians(angle))
    
    def move(self):
        self.trail.append((int(self.x), int(self.y)))
        if len(self.trail) > 8:
            self.trail.pop(0)
        
        self.x += self.dx
        self.y += self.dy
        
        if (self.x < 25 or self.x > WINDOW_WIDTH - 25 or 
            self.y < WINDOW_HEIGHT // 2 + 35 or self.y > WINDOW_HEIGHT - 25):
            self.alive = False
    
    def draw(self, screen):
        if not self.alive:
            return
        
        # Trail
        for i, pos in enumerate(self.trail):
            alpha = int(150 * (i / len(self.trail)))
            size = int(3 * (i / len(self.trail)) + 1)
            color = (255, 200, 50, alpha)
            surf = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (size, size), size)
            screen.blit(surf, (pos[0] - size, pos[1] - size))
        
        # Bullet
        pygame.draw.circle(screen, (255, 255, 200), (int(self.x), int(self.y)), 4)
        pygame.draw.circle(screen, (255, 200, 50), (int(self.x), int(self.y)), 5, 1)

class Particle:
    def __init__(self, x, y, color, size=0, speed_x=0, speed_y=0):
        self.x = x
        self.y = y
        self.color = color
        self.size = size if size > 0 else random.randint(3, 8)
        self.speed_x = speed_x if speed_x != 0 else random.uniform(-3, 3)
        self.speed_y = speed_y if speed_y != 0 else random.uniform(-5, 2)
        self.life = random.randint(15, 40)
        self.max_life = self.life
        self.gravity = random.uniform(0.1, 0.25)
    
    def update(self):
        self.x += self.speed_x
        self.y += self.speed_y
        self.speed_y += self.gravity
        self.life -= 1
        self.size *= 0.96
    
    def draw(self, screen):
        if self.life > 0:
            alpha = int(255 * (self.life / self.max_life))
            color = (self.color[0], self.color[1], self.color[2], alpha)
            surf = pygame.Surface((int(self.size*2), int(self.size*2)), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (int(self.size), int(self.size)), int(self.size))
            screen.blit(surf, (int(self.x - self.size), int(self.y - self.size)))

# ============= CREATE OBJECTS =============

player1 = Tank(
    x=180, y=480, color=(0, 80, 220),
    controls={'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
    name="P1"
)

player2 = Tank(
    x=750, y=480, color=(220, 40, 40),
    controls={'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT},
    name="P2"
)

bullets = []

# ============= GAME LOOP =============

running = True

while running:
    keys = pygame.key.get_pressed()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                bullet = player1.shoot()
                if bullet:
                    bullets.append(bullet)
            if event.key == pygame.K_RETURN:
                bullet = player2.shoot()
                if bullet:
                    bullets.append(bullet)
    
    # Update tanks
    player1.move(keys)
    player2.move(keys)
    player1.update()
    player2.update()
    
    # Update bullets
    for bullet in bullets[:]:
        bullet.move()
        if not bullet.alive:
            bullets.remove(bullet)
            continue
        
        # Collision with Player 1
        if bullet.owner != player1 and player1.alive:
            if (player1.x < bullet.x < player1.x + player1.width and 
                player1.y < bullet.y < player1.y + player1.height):
                player1.take_damage(25)
                for _ in range(10):
                    particles.append(Particle(
                        bullet.x, bullet.y,
                        (255, 200, 50),
                        random.randint(2, 5),
                        random.uniform(-3, 3),
                        random.uniform(-3, 3)
                    ))
                bullets.remove(bullet)
                continue
        
        # Collision with Player 2
        if bullet.owner != player2 and player2.alive:
            if (player2.x < bullet.x < player2.x + player2.width and 
                player2.y < bullet.y < player2.y + player2.height):
                player2.take_damage(25)
                for _ in range(10):
                    particles.append(Particle(
                        bullet.x, bullet.y,
                        (255, 200, 50),
                        random.randint(2, 5),
                        random.uniform(-3, 3),
                        random.uniform(-3, 3)
                    ))
                bullets.remove(bullet)
    
    # Update particles
    for particle in particles[:]:
        particle.update()
        if particle.life <= 0 or particle.size < 0.5:
            particles.remove(particle)
    
    # Update shell casings
    for casing in shell_casings[:]:
        casing['x'] += casing['speed_x']
        casing['y'] += casing['speed_y']
        casing['speed_y'] += 0.3
        casing['life'] -= 1
        if casing['life'] <= 0:
            shell_casings.remove(casing)
    
    # ============= DRAW =============
    
    # Background
    draw_sky()
    draw_sun()
    draw_clouds()
    draw_mountains()
    draw_water()
    draw_grass()
    draw_craters()
    draw_battlefield_border()
    
    # Shell casings
    for casing in shell_casings:
        pygame.draw.rect(screen, (180, 150, 80), (casing['x'], casing['y'], 4, 6))
    
    # Bullets
    for bullet in bullets:
        bullet.draw(screen)
    
    # Tanks
    player1.draw(screen)
    player2.draw(screen)
    
    # Particles
    for particle in particles:
        particle.draw(screen)
    
    # ============= HUD =============
    font = pygame.font.Font(None, 22)
    p1_text = font.render(f"P1: {player1.health} HP", True, (100, 180, 255))
    screen.blit(p1_text, (30, 25))
    p2_text = font.render(f"P2: {player2.health} HP", True, (255, 100, 100))
    p2_rect = p2_text.get_rect(topright=(WINDOW_WIDTH - 30, 25))
    screen.blit(p2_text, p2_rect)
    
    # Controls
    controls_font = pygame.font.Font(None, 14)
    controls_text = controls_font.render("WASD: Move | SPACE: Shoot", True, (200, 200, 200))
    screen.blit(controls_text, (30, WINDOW_HEIGHT - 25))
    controls_text2 = controls_font.render("ARROWS: Move | ENTER: Shoot", True, (200, 200, 200))
    screen.blit(controls_text2, (WINDOW_WIDTH - 280, WINDOW_HEIGHT - 25))
    
    # Game over
    if not player1.alive and not player2.alive:
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))
        go_font = pygame.font.Font(None, 70)
        go_text = go_font.render("DRAW!", True, (255, 255, 200))
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 40))
        screen.blit(go_text, go_rect)
        restart_font = pygame.font.Font(None, 24)
        restart_text = restart_font.render("Press R to restart", True, (200, 200, 200))
        restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 + 20))
        screen.blit(restart_text, restart_rect)
        if keys[pygame.K_r]:
            player1.respawn()
            player2.respawn()
            bullets.clear()
            particles.clear()
            craters.clear()
    
    elif not player1.alive:
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        screen.blit(overlay, (0, 0))
        go_font = pygame.font.Font(None, 70)
        go_text = go_font.render("P2 WINS!", True, (255, 80, 80))
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 40))
        screen.blit(go_text, go_rect)
        
    elif not player2.alive:
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        screen.blit(overlay, (0, 0))
        go_font = pygame.font.Font(None, 70)
        go_text = go_font.render("P1 WINS!", True, (80, 150, 255))
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 40))
        screen.blit(go_text, go_rect)
    
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()