import pygame
import socket
import json
import threading
import sys
import math
import random
import time
import traceback
from shared import *

# ==========================================
# UI COMPONENTS (Text Box and Button)
# ==========================================
class TextBox:
    def __init__(self, x, y, w, h, is_password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = ""
        self.is_password = is_password
        self.active = False
        self.color_inactive = pygame.Color('lightslategray')
        self.color_active = pygame.Color('dodgerblue2')
        self.color = self.color_inactive
        self.font = pygame.font.Font(None, 32)
        self.txt_surface = self.font.render(self.text, True, (255, 255, 255))
        self.cursor_timer = 0
        self.show_cursor = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = not self.active
            else:
                self.active = False
            self.color = self.color_active if self.active else self.color_inactive
        
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
                self.color = self.color_inactive
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                if len(self.text) < 15:
                    self.text += event.unicode

    def update(self):
        width = max(200, self.txt_surface.get_width() + 10)
        self.rect.w = width
        display_text = "*" * len(self.text) if self.is_password else self.text
        self.txt_surface = self.font.render(display_text, True, (255, 255, 255))
        
        self.cursor_timer += 1
        if self.cursor_timer >= 30:
            self.show_cursor = not self.show_cursor
            self.cursor_timer = 0

    def draw(self, screen):
        screen.blit(self.txt_surface, (self.rect.x + 10, self.rect.y + 10))
        pygame.draw.rect(screen, self.color, self.rect, 2)
        
        if self.active and self.show_cursor:
            cursor_x = self.rect.x + 10 + self.txt_surface.get_width()
            pygame.draw.line(screen, (255, 255, 255), (cursor_x, self.rect.y + 8), (cursor_x, self.rect.y + 30), 2)

class Button:
    def __init__(self, x, y, w, h, text, color, hover_color):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.current_color = color
        self.font = pygame.font.Font(None, 30)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self.current_color = self.hover_color
            else:
                self.current_color = self.color
                
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, screen):
        pygame.draw.rect(screen, self.current_color, self.rect, border_radius=5)
        pygame.draw.rect(screen, (255, 255, 255), self.rect, 2, border_radius=5)
        text_surface = self.font.render(self.text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

# ==========================================
# MAIN CLIENT CLASS
# ==========================================
class GameClient:
    def __init__(self):
        self.player_name = ""
        self.mode = ""
        self.auth_type = ""
        self.password = ""
        self.player_id = None
        self.role = None
        self.socket = None
        self.running = True
        self.connected = False
        self.buffer = ""
        self.last_send_time = 0
        self.send_interval = 1 / 30
        self.is_shutting_down = False
        
        self.state = 'login' 
        self.error_message = ""
        self.stats = None
        self.show_leaderboard = False
        self.leaderboard_data = []

        self.round = 0
        self.max_rounds = 5
        self.my_score = 0
        self.opp_score = 0
        self.transition_active = False
        self.transition_end_time = 0
        self.round_winner_name = ""
        self.died_this_round = False
        self.match_result = None
        self.health_pack = None
        self.opponent_name = "Opponent"

        self.local_tank = None
        self.remote_data = {
            'x': 750, 'y': 480, 'angle': 0, 'health': 100,
            'alive': False, 'color': (220, 40, 40), 'score': 0,
            'player_id': 2, 'target_x': 750, 'target_y': 480,
            'target_angle': 0, 'last_update_time': time.time()
        }
        self.bullets = []
        self.remote_bullets = []

        pygame.init()
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.sounds = {
                'shoot': SoundGenerator.generate_shoot_sound(),
                'explosion': SoundGenerator.generate_explosion_sound(),
                'pickup': SoundGenerator.generate_pickup_sound()
            }
        except:
            self.sounds = {}

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Tank Battle Arena")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 20)
        self.big_font = pygame.font.Font(None, 48)
        self.winner_font = pygame.font.Font(None, 72)

        self.username_box = TextBox(WINDOW_WIDTH//2 - 150, 250, 300, 40)
        self.password_box = TextBox(WINDOW_WIDTH//2 - 150, 320, 300, 40, is_password=True)
        
        self.btn_login = Button(WINDOW_WIDTH//2 - 160, 400, 140, 45, "LOGIN", (0, 150, 0), (0, 200, 0))
        self.btn_register = Button(WINDOW_WIDTH//2 + 20, 400, 140, 45, "REGISTER", (150, 100, 0), (200, 150, 0))
        
        self.btn_bot = Button(WINDOW_WIDTH//2 - 160, 300, 320, 50, "PLAY VS BOT", (0, 80, 200), (0, 120, 255))
        self.btn_opponent = Button(WINDOW_WIDTH//2 - 160, 380, 320, 50, "PLAY VS OPPONENT", (200, 50, 50), (255, 80, 80))

    # ---------------- NETWORKING ----------------
    def _recv_one_message(self, timeout=5):
        self.socket.settimeout(timeout)
        try:
            while "\n" not in self.buffer:
                try:
                    data = self.socket.recv(BUFFER_SIZE)
                except socket.timeout:
                    return None
                if not data:
                    return None
                self.buffer += data.decode()
        finally:
            self.socket.settimeout(None)

        line, self.buffer = self.buffer.split("\n", 1)
        if not line.strip():
            return self._recv_one_message(timeout)
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return self._recv_one_message(timeout)

    def attempt_auth(self, auth_type):
        self.player_name = self.username_box.text.strip()
        self.password = self.password_box.text.strip()
        self.auth_type = auth_type

        if not self.player_name or not self.password:
            self.error_message = "Username and Password required!"
            return

        self.state = 'connecting'
        self.error_message = ""
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((SERVER_IP, SERVER_PORT))
            self.socket.send((json.dumps({'type': 'join', 'name': self.player_name}) + "\n").encode())

            # Read welcome
            msg = self._recv_one_message()
            if msg and msg.get('type') == 'welcome':
                self.player_id = msg['player_id']

            # Send Auth
            self.socket.send((json.dumps({
                'type': 'register' if auth_type == 'register' else 'login',
                'username': self.player_name,
                'password': self.password
            }) + "\n").encode())

            # Wait for Auth Response
            auth_ok = False
            for _ in range(5):
                msg = self._recv_one_message()
                if msg is None: break
                if msg.get('type') == 'auth_response':
                    if msg['success']:
                        self.connected = True
                        self.stats = msg['stats']
                        auth_ok = True
                    else:
                        self.error_message = msg.get('message', 'Auth failed')
                    break

            if auth_ok:
                self.socket.settimeout(None)
                self.state = 'mode_select'
                threading.Thread(target=self.receive_messages, daemon=True).start()
            else:
                self.state = 'login'
                if self.socket: self.socket.close()
        except Exception as e:
            print(f"[CLIENT] Auth error: {e}")
            self.error_message = "Connection failed. Server offline."
            self.state = 'login'
            if self.socket: self.socket.close()

    def receive_messages(self):
        while self.running and self.connected:
            try:
                data = self.socket.recv(BUFFER_SIZE)
                if not data: break
                self.buffer += data.decode()
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if not line.strip(): continue
                    try:
                        self.handle_server_message(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                if self.running and not self.is_shutting_down:
                    print(f"[CLIENT] Receive error: {e}")
                self.connected = False
                break

    def handle_server_message(self, msg):
        t = msg.get('type')
        if t == 'leaderboard':
            self.leaderboard_data = msg.get('data', [])
            self.show_leaderboard = True
            return
        if t == 'stats_update':
            self.stats = msg.get('stats', self.stats)
            return
        if t == 'waiting':
            self.state = 'waiting'
        elif t == 'game_start':
            self.state = 'playing'
            self.player_id = msg.get('player_id', self.player_id)
            self.role = msg.get('role', 'p1' if self.player_id == 1 else 'p2')
            self.opponent_name = msg.get('opponent_name', 'Opponent')
            self.setup_tanks()
        elif t == 'round_start':
            if 'role' in msg: self.role = msg['role']
            self.round = msg['round']
            self.max_rounds = msg['max_rounds']
            self.my_score = msg['your_score']
            self.opp_score = msg['opp_score']
            self.opponent_name = msg['opponent_name']
            hp = msg['health_pack']
            self.health_pack = PowerUp(hp['x'], hp['y'], 'health')
            self.died_this_round = False
            self.transition_active = False
            self.reset_local_tank()
            self.bullets.clear()
            self.remote_bullets.clear()
            self.remote_data['alive'] = True
            self.remote_data['health'] = 100
            if self.mode == 'bot':
                self.remote_data['x'] = self.remote_data['target_x'] = 750
                self.remote_data['y'] = self.remote_data['target_y'] = 480
        elif t == 'round_end':
            self.my_score = msg['your_score']
            self.opp_score = msg['opp_score']
            self.round_winner_name = msg['winner_name']
            self.transition_active = True
            self.transition_end_time = time.time() + msg.get('next_round_in', 3)
        elif t == 'match_end':
            self.match_result = msg['result']
            self.my_score = msg['your_score']
            self.opp_score = msg['opp_score']
            self.opponent_name = msg['opponent_name']
            self.state = 'game_over'
            self.transition_active = False
            try:
                self.socket.send((json.dumps({'type': 'get_stats'}) + "\n").encode())
            except: pass
        elif t == 'player_input':
            if msg.get('player_id') != self.player_id:
                keys = msg.get('keys', {})
                if keys.get('up'): self.remote_data['target_y'] -= 3; self.remote_data['target_angle'] = 0
                elif keys.get('down'): self.remote_data['target_y'] += 3; self.remote_data['target_angle'] = 180
                elif keys.get('left'): self.remote_data['target_x'] -= 3; self.remote_data['target_angle'] = 270
                elif keys.get('right'): self.remote_data['target_x'] += 3; self.remote_data['target_angle'] = 90
                self.remote_data['last_update_time'] = time.time()
        elif t == 'player_shoot':
            if msg.get('player_id') != self.player_id:
                bd = msg.get('bullet', {})
                b = Bullet(bd['x'], bd['y'], bd['angle'], bd.get('owner_id', 'opponent'))
                self.remote_bullets.append(b)
                if 'shoot' in self.sounds: self.sounds['shoot'].play()
        elif t == 'game_state':
            if msg.get('player_id') != self.player_id:
                s = msg.get('state', {})
                self.remote_data['target_x'] = s.get('x', self.remote_data['target_x'])
                self.remote_data['target_y'] = s.get('y', self.remote_data['target_y'])
                self.remote_data['target_angle'] = s.get('angle', self.remote_data['target_angle'])
                self.remote_data['health'] = s.get('health', self.remote_data['health'])
                self.remote_data['alive'] = s.get('alive', self.remote_data['alive'])
                self.remote_data['last_update_time'] = time.time()
        elif t == 'bot_hit':
            self.remote_data['health'] = msg['health']
            self.remote_data['alive'] = msg['alive']
            if 'explosion' in self.sounds: self.sounds['explosion'].play()
        elif t == 'opponent_disconnected':
            self.match_result = 'win'
            self.state = 'game_over'

    # ---------------- GAME LOGIC ----------------
    def setup_tanks(self):
        if self.role == 'p1':
            self.local_tank = Tank(x=180, y=480, color=(0, 80, 220),
                controls={'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},
                name=self.player_name, player_id=self.player_id)
            self.remote_data['color'] = (220, 40, 40)
        else:
            self.local_tank = Tank(x=750, y=480, color=(220, 40, 40),
                controls={'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT},
                name=self.player_name, player_id=self.player_id)
            self.remote_data['color'] = (0, 80, 220)

    def reset_local_tank(self):
        if not self.local_tank: return
        if self.role == 'p1': self.local_tank.x, self.local_tank.y = 180, 480
        else: self.local_tank.x, self.local_tank.y = 750, 480
        self.local_tank.health = 100
        self.local_tank.alive = True
        self.local_tank.speed_boost_timer = 0
        self.local_tank.shoot_cooldown = 0

    def interpolate_remote(self):
        if not self.remote_data['alive']: return
        if time.time() - self.remote_data['last_update_time'] > 0.5: return
        lerp = 0.15
        self.remote_data['x'] += (self.remote_data['target_x'] - self.remote_data['x']) * lerp
        self.remote_data['y'] += (self.remote_data['target_y'] - self.remote_data['y']) * lerp
        ad = self.remote_data['target_angle'] - self.remote_data['angle']
        if ad > 180: ad -= 360
        elif ad < -180: ad += 360
        self.remote_data['angle'] += ad * lerp

    def check_collisions(self):
        for b in self.bullets[:]:
            if not b.alive: continue
            if self.remote_data['alive']:
                rx, ry = self.remote_data['x'], self.remote_data['y']
                if rx < b.x < rx + 45 and ry < b.y < ry + 45:
                    b.alive = False
                    try: self.socket.send((json.dumps({'type': 'hit_registered', 'target_id': 'bot' if self.mode == 'bot' else self.remote_data.get('player_id')}) + "\n").encode())
                    except: pass
                    self.bullets.remove(b)
                    continue
        for b in self.remote_bullets[:]:
            if not b.alive: continue
            if self.local_tank and self.local_tank.alive:
                if (self.local_tank.x < b.x < self.local_tank.x + self.local_tank.width and self.local_tank.y < b.y < self.local_tank.y + self.local_tank.height):
                    b.alive = False
                    self.local_tank.take_damage(25)
                    if 'explosion' in self.sounds: self.sounds['explosion'].play()
                    self.remote_bullets.remove(b)
                    if not self.local_tank.alive and not self.died_this_round:
                        self.died_this_round = True
                        try: self.socket.send((json.dumps({'type': 'player_died'}) + "\n").encode())
                        except: pass
                    continue
        if self.health_pack and self.local_tank and self.local_tank.alive:
            hp = self.health_pack
            if (hp.x < self.local_tank.x + self.local_tank.width and hp.x + hp.width > self.local_tank.x and hp.y < self.local_tank.y + self.local_tank.height and hp.y + hp.height > self.local_tank.y):
                self.local_tank.health = min(self.local_tank.max_health, self.local_tank.health + 50)
                if 'pickup' in self.sounds: self.sounds['pickup'].play()
                self.health_pack = None

    def send_input(self):
        if not self.connected or not self.local_tank or self.is_shutting_down: return
        if self.state != 'playing' or self.transition_active: return
        if time.time() - self.last_send_time < self.send_interval: return
        self.last_send_time = time.time()
        pk = pygame.key.get_pressed()
        keys = {}
        for kn in ['up', 'down', 'left', 'right']:
            if kn in self.local_tank.controls: keys[kn] = bool(pk[self.local_tank.controls[kn]])
        try: self.socket.send((json.dumps({'type': 'player_input', 'keys': keys}) + "\n").encode())
        except: pass

    def send_shoot(self):
        if not self.connected or not self.local_tank or self.is_shutting_down: return
        if self.state != 'playing' or self.transition_active: return
        if not self.local_tank.alive: return
        b = self.local_tank.shoot()
        if b:
            self.bullets.append(b)
            if 'shoot' in self.sounds: self.sounds['shoot'].play()
            try: self.socket.send((json.dumps({'type': 'player_shoot', 'bullet': b.get_state()}) + "\n").encode())
            except: pass

    def send_game_state(self):
        if not self.connected or not self.local_tank or self.is_shutting_down: return
        if self.state != 'playing' or self.transition_active: return
        try: self.socket.send((json.dumps({'type': 'game_state', 'state': self.local_tank.get_state()}) + "\n").encode())
        except: pass

    # ---------------- DRAWING METHODS ----------------
    def draw_background(self):
        self.screen.fill((0, 0, 0))
        draw_sky(self.screen); draw_sun(self.screen); draw_mountains(self.screen)
        draw_water(self.screen); draw_grass(self.screen); draw_battlefield_border(self.screen)

    def draw_login_screen(self):
        self.draw_background()
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180)); self.screen.blit(ov, (0, 0))
        
        title = self.winner_font.render("TANK BATTLE ARENA", True, (255, 215, 0))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH//2, 100)))
        
        sub = self.font.render("Cloud Multiplayer", True, (200, 200, 200))
        self.screen.blit(sub, sub.get_rect(center=(WINDOW_WIDTH//2, 150)))

        lbl_user = self.font.render("Username", True, (255, 255, 255))
        self.screen.blit(lbl_user, (WINDOW_WIDTH//2 - 150, 225))
        self.username_box.draw(self.screen)

        lbl_pass = self.font.render("Password", True, (255, 255, 255))
        self.screen.blit(lbl_pass, (WINDOW_WIDTH//2 - 150, 295))
        self.password_box.draw(self.screen)

        self.btn_login.draw(self.screen)
        self.btn_register.draw(self.screen)

        if self.error_message:
            err = self.small_font.render(self.error_message, True, (255, 80, 80))
            self.screen.blit(err, err.get_rect(center=(WINDOW_WIDTH//2, 480)))

    def draw_mode_select(self):
        self.draw_background()
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180)); self.screen.blit(ov, (0, 0))
        
        title = self.big_font.render(f"Welcome, {self.player_name}!", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH//2, 150)))
        
        if self.stats:
            stats_txt = self.font.render(f"Wins: {self.stats['wins']}  |  Losses: {self.stats['losses']}", True, (200, 255, 200))
            self.screen.blit(stats_txt, stats_txt.get_rect(center=(WINDOW_WIDTH//2, 200)))

        self.btn_bot.draw(self.screen)
        self.btn_opponent.draw(self.screen)

    def draw_waiting(self):
        self.draw_background()
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170)); self.screen.blit(ov, (0, 0))
        txt = self.big_font.render("Waiting for Opponent...", True, (255, 255, 100))
        self.screen.blit(txt, txt.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40)))
        dots = "." * ((pygame.time.get_ticks() // 400) % 4)
        d = self.big_font.render(dots, True, (255, 255, 100))
        self.screen.blit(d, (WINDOW_WIDTH // 2 + 200, WINDOW_HEIGHT // 2 - 40))
    
    def draw_hud(self):
        round_txt = self.font.render(f"ROUND {self.round}/{self.max_rounds}", True, (255, 255, 100))
        self.screen.blit(round_txt, round_txt.get_rect(center=(WINDOW_WIDTH // 2, 25)))
        score_txt = self.font.render(f"YOU: {self.my_score}   |   {self.opponent_name}: {self.opp_score}", True, (255, 255, 255))
        self.screen.blit(score_txt, (30, 25))
        if self.local_tank:
            hp = self.small_font.render(f"HP: {self.local_tank.health}", True, (255, 255, 100))
            self.screen.blit(hp, (30, 55))
    
    def draw_round_transition(self):
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160)); self.screen.blit(ov, (0, 0))
        w = self.big_font.render(f"{self.round_winner_name} wins the round!", True, (255, 215, 0))
        self.screen.blit(w, w.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 60)))
        remaining = max(0, self.transition_end_time - time.time())
        cd = self.font.render(f"Next round in {remaining:.1f}s", True, (255, 255, 255))
        self.screen.blit(cd, cd.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10)))

    def draw_match_end(self):
        self.draw_background()
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 190)); self.screen.blit(ov, (0, 0))
        if self.match_result == 'win': title = "🏆 YOU WIN! 🏆"; color = (255, 215, 0)
        elif self.match_result == 'loss': title = "BETTER LUCK NEXT TIME!"; color = (255, 100, 100)
        else: title = "DRAW!"; color = (200, 200, 200)
        t = self.winner_font.render(title, True, color)
        self.screen.blit(t, t.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80)))
        final = self.font.render(f"Final Score: You {self.my_score}  —  {self.opponent_name} {self.opp_score}", True, (220, 220, 220))
        self.screen.blit(final, final.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 10)))
        if self.stats:
            st = self.font.render(f"Stats — W: {self.stats['wins']}  L: {self.stats['losses']}  Total: {self.stats['total_matches']}", True, (200, 255, 200))
            self.screen.blit(st, st.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 50)))
        lb_hint = self.small_font.render("Press L for Leaderboard  |  ESC to Exit", True, (200, 200, 100))
        self.screen.blit(lb_hint, lb_hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 110)))

    def draw_leaderboard(self):
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 200)); self.screen.blit(ov, (0, 0))
        title = self.big_font.render("🏆 LEADERBOARD — TOP 10 🏆", True, (255, 215, 0))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 80)))
        header = self.font.render("#    Username                Wins    Losses   Played", True, (180, 180, 255))
        self.screen.blit(header, (140, 150))
        for i, entry in enumerate(self.leaderboard_data):
            y = 200 + i * 38
            color = (255, 215, 0) if i == 0 else (200, 200, 200)
            line = (f"{i + 1:<4} {entry['username']:<22} {entry['wins']:<7} {entry['losses']:<8} {entry['total_matches']}")
            txt = self.font.render(line, True, color)
            self.screen.blit(txt, (140, y))
        hint = self.small_font.render("Press L to close", True, (180, 180, 180))
        self.screen.blit(hint, hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 40)))

    # ---------------- MAIN LOOP ----------------
    def run(self):
        while self.running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.shutdown(); return

                if self.state == 'login':
                    self.username_box.handle_event(event)
                    self.password_box.handle_event(event)
                    if self.btn_login.is_clicked(event): threading.Thread(target=self.attempt_auth, args=('login',), daemon=True).start()
                    if self.btn_register.is_clicked(event): threading.Thread(target=self.attempt_auth, args=('register',), daemon=True).start()
                
                elif self.state == 'mode_select':
                    if self.btn_bot.is_clicked(event):
                        self.mode = 'bot'
                        self.socket.send((json.dumps({'type': 'choose_mode', 'mode': 'bot'}) + "\n").encode())
                        self.state = 'connecting'
                    if self.btn_opponent.is_clicked(event):
                        self.mode = 'opponent'
                        self.socket.send((json.dumps({'type': 'choose_mode', 'mode': 'opponent'}) + "\n").encode())
                        self.state = 'connecting'

                elif self.state == 'playing' and not self.transition_active and self.local_tank and self.local_tank.alive:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE: self.shutdown(); return
                        if event.key == pygame.K_SPACE and self.role == 'p1': self.send_shoot()
                        elif event.key == pygame.K_RETURN and self.role == 'p2': self.send_shoot()
                
                elif self.state == 'game_over':
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE: self.shutdown(); return
                        if event.key == pygame.K_l:
                            if not self.show_leaderboard:
                                try: self.socket.send((json.dumps({'type': 'get_leaderboard'}) + "\n").encode())
                                except: pass
                            else: self.show_leaderboard = False

            if self.state == 'login':
                self.username_box.update()
                self.password_box.update()
                self.btn_login.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pygame.mouse.get_pos()))
                self.btn_register.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pygame.mouse.get_pos()))
            elif self.state == 'mode_select':
                self.btn_bot.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pygame.mouse.get_pos()))
                self.btn_opponent.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pygame.mouse.get_pos()))

            elif self.state == 'playing' and not self.transition_active and self.local_tank:
                pk = pygame.key.get_pressed()
                ks = {self.local_tank.controls[kn]: bool(pk[self.local_tank.controls[kn]]) for kn in ['up', 'down', 'left', 'right'] if kn in self.local_tank.controls}
                if self.local_tank.alive: self.local_tank.move(ks)
                self.local_tank.update()
                self.interpolate_remote()
                for b in self.bullets[:]:
                    b.move()
                    if not b.alive: self.bullets.remove(b)
                for b in self.remote_bullets[:]:
                    b.move()
                    if not b.alive: self.remote_bullets.remove(b)
                self.check_collisions()
                self.send_input()
                self.send_game_state()

            if self.state == 'login':
                self.draw_login_screen()
            elif self.state == 'mode_select':
                self.draw_mode_select()
            elif self.state == 'connecting':
                self.draw_background()
                txt = self.big_font.render("Connecting...", True, (255, 255, 255))
                self.screen.blit(txt, txt.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2)))
            elif self.state == 'waiting':
                self.draw_waiting()
            elif self.state == 'playing':
                self.draw_background()
                if self.health_pack: self.health_pack.draw(self.screen)
                for b in self.bullets: b.draw(self.screen)
                for b in self.remote_bullets: b.draw(self.screen)
                if self.local_tank: self.local_tank.draw(self.screen)
                draw_remote_tank(self.screen, self.remote_data)
                self.draw_hud()
                if self.transition_active: self.draw_round_transition()
            elif self.state == 'game_over':
                self.draw_match_end()
                if self.show_leaderboard: self.draw_leaderboard()

            pygame.display.flip()
            self.clock.tick(60)

    def shutdown(self):
        if self.is_shutting_down: return
        self.is_shutting_down = True
        self.running = False
        self.connected = False
        if self.socket:
            try: self.socket.close()
            except: pass
        pygame.quit()
        sys.exit()

def draw_remote_tank(screen, data):
    if not data['alive']: return
    x, y, angle, color = data['x'], data['y'], data['angle'], data['color']
    pygame.draw.rect(screen, (0, 0, 0), (x + 4, y + 5, 45, 45))
    pygame.draw.rect(screen, color, (x, y, 45, 45))
    pygame.draw.rect(screen, (0, 0, 0), (x, y, 45, 45), 2)
    pygame.draw.rect(screen, (40, 40, 40), (x - 3, y + 5, 6, 35))
    pygame.draw.rect(screen, (40, 40, 40), (x + 42, y + 5, 6, 35))
    cx, cy = x + 22, y + 22
    pygame.draw.circle(screen, (200, 200, 200), (cx, cy), 14)
    pygame.draw.circle(screen, color, (cx, cy), 12)
    pygame.draw.circle(screen, (0, 0, 0), (cx, cy), 12, 1)
    rad = math.radians(angle)
    ex, ey = cx + 25 * math.sin(rad), cy - 25 * math.cos(rad)
    pygame.draw.line(screen, (30, 30, 30), (cx, cy), (ex, ey), 6)
    pygame.draw.line(screen, (150, 150, 150), (cx, cy), (ex, ey), 4)
    pygame.draw.rect(screen, (40, 40, 40), (x - 5, y - 20, 100, 12))
    hw = int((data['health'] / 100) * 100)
    if hw > 0:
        r = data['health'] / 100
        pygame.draw.rect(screen, (int(255 * (1 - r)), int(255 * r), 0), (x - 5, y - 20, hw, 12))
    pygame.draw.rect(screen, (200, 200, 200), (x - 5, y - 20, 100, 12), 1)

if __name__ == "__main__":
    try:
        client = GameClient()
        client.run()
    except KeyboardInterrupt:
        print("\n[MAIN] Interrupted")