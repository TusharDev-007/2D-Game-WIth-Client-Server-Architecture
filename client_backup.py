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

class GameClient:
    def __init__(self, player_name, mode):
        self.player_name = player_name
        self.mode = mode
        self.player_id = None
        self.socket = None
        self.running = True
        self.connected = False
        self.buffer = ""
        self.last_send_time = 0
        self.send_interval = 1 / 30
        self.is_shutting_down = False

        self.state = 'connecting'   # connecting, waiting, playing, game_over
        self.opponent_name = "Opponent"

        # round / score
        self.round = 0
        self.max_rounds = 5
        self.my_score = 0
        self.opp_score = 0
        self.transition_active = False
        self.transition_end_time = 0
        self.round_winner_name = ""
        self.died_this_round = False

        # final result
        self.match_result = None    # 'win' | 'loss' | 'draw'

        # health pack
        self.health_pack = None

        self.local_tank = None
        self.remote_data = {
            'x': 750, 'y': 480, 'angle': 0, 'health': 100,
            'alive': False, 'color': (220, 40, 40), 'score': 0,
            'player_id': 2,
            'target_x': 750, 'target_y': 480, 'target_angle': 0,
            'last_update_time': time.time()
        }
        self.bullets = []
        self.remote_bullets = []

        if not self.connect_to_server():
            print("[ERROR] Could not connect to server"); sys.exit(1)

        pygame.init()
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.sounds = {
                'shoot': SoundGenerator.generate_shoot_sound(),
                'explosion': SoundGenerator.generate_explosion_sound(),
                'pickup': SoundGenerator.generate_pickup_sound()
            }
        except Exception as e:
            print(f"[WARNING] Sound init failed: {e}")
            self.sounds = {}

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(f"Tank Battle - {player_name}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 20)
        self.big_font = pygame.font.Font(None, 48)
        self.winner_font = pygame.font.Font(None, 72)

    # ---------- networking ----------
    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((SERVER_IP, SERVER_PORT))
            self.socket.send((json.dumps({'type': 'join',
                                          'name': self.player_name}) + "\n").encode())

            self.socket.settimeout(5)
            data = self.socket.recv(BUFFER_SIZE).decode()
            self.socket.settimeout(None)

            for line in data.split("\n"):
                if not line.strip(): continue
                msg = json.loads(line)
                if msg['type'] == 'welcome':
                    self.player_id = msg['player_id']
                    self.connected = True
                    print(f"[CLIENT] Welcome! Player ID = {self.player_id}")

            if not self.connected: return False

            self.socket.send((json.dumps({'type': 'choose_mode',
                                          'mode': self.mode}) + "\n").encode())
            print(f"[CLIENT] Mode '{self.mode}' sent.")

            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True
        except Exception as e:
            print(f"[CLIENT] connect error: {e}")
            traceback.print_exc()
            return False

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

        if t == 'waiting':
            print("[CLIENT] Waiting for opponent...")
            self.state = 'waiting'

        elif t == 'game_start':
            self.state = 'playing'
            self.player_id = msg.get('player_id', self.player_id)
            self.opponent_name = msg.get('opponent_name', 'Opponent')
            print(f"[CLIENT] Game starting! Opponent: {self.opponent_name}")
            self.setup_tanks()

        elif t == 'round_start':
            self.round = msg['round']
            self.max_rounds = msg['max_rounds']
            self.my_score = msg['your_score']
            self.opp_score = msg['opp_score']
            self.opponent_name = msg['opponent_name']
            hp = msg['health_pack']
            self.health_pack = PowerUp(hp['x'], hp['y'], 'health')
            self.died_this_round = False
            self.transition_active = False
            # Reset tank
            self.reset_local_tank()
            self.bullets.clear()
            self.remote_bullets.clear()
            self.remote_data['alive'] = True
            self.remote_data['health'] = 100
            if self.mode == 'bot':
                self.remote_data['x'] = self.remote_data['target_x'] = 750
                self.remote_data['y'] = self.remote_data['target_y'] = 480
            print(f"[CLIENT] === ROUND {self.round}/{self.max_rounds} ===")
            print(f"[CLIENT] Score: You {self.my_score} - {self.opponent_name} {self.opp_score}")

        elif t == 'round_end':
            self.my_score = msg['your_score']
            self.opp_score = msg['opp_score']
            self.round_winner_name = msg['winner_name']
            self.transition_active = True
            self.transition_end_time = time.time() + msg.get('next_round_in', 3)
            print(f"[CLIENT] Round over — {self.round_winner_name} wins the round")

        elif t == 'match_end':
            self.match_result = msg['result']
            self.my_score = msg['your_score']
            self.opp_score = msg['opp_score']
            self.opponent_name = msg['opponent_name']
            self.state = 'game_over'
            self.transition_active = False
            print(f"[CLIENT] === MATCH OVER ===")
            print(f"[CLIENT] Result: {msg['result'].upper()} | Final: {self.my_score}-{self.opp_score}")

        elif t == 'player_input':
            if msg.get('player_id') != self.player_id:
                keys = msg.get('keys', {})
                if keys.get('up'):    self.remote_data['target_y'] -= 3; self.remote_data['target_angle'] = 0
                elif keys.get('down'):  self.remote_data['target_y'] += 3; self.remote_data['target_angle'] = 180
                elif keys.get('left'):  self.remote_data['target_x'] -= 3; self.remote_data['target_angle'] = 270
                elif keys.get('right'): self.remote_data['target_x'] += 3; self.remote_data['target_angle'] = 90
                self.remote_data['last_update_time'] = time.time()

        elif t == 'player_shoot':
            if msg.get('player_id') != self.player_id:
                bd = msg.get('bullet', {})
                b = Bullet(bd['x'], bd['y'], bd['angle'],
                           bd.get('owner_id', 'opponent'))
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
            print("[CLIENT] Opponent disconnected!")
            self.match_result = 'win'
            self.state = 'game_over'

    # ---------- setup / reset ----------
    def setup_tanks(self):
        if self.player_id == 1:
            self.local_tank = Tank(
                x=180, y=480, color=(0, 80, 220),
                controls={'up': pygame.K_w, 'down': pygame.K_s,
                          'left': pygame.K_a, 'right': pygame.K_d},
                name=self.player_name, player_id=1)
            self.remote_data['color'] = (220, 40, 40)
        else:
            self.local_tank = Tank(
                x=750, y=480, color=(220, 40, 40),
                controls={'up': pygame.K_UP, 'down': pygame.K_DOWN,
                          'left': pygame.K_LEFT, 'right': pygame.K_RIGHT},
                name=self.player_name, player_id=2)
            self.remote_data['color'] = (0, 80, 220)

    def reset_local_tank(self):
        if not self.local_tank: return
        if self.player_id == 1:
            self.local_tank.x, self.local_tank.y = 180, 480
        else:
            self.local_tank.x, self.local_tank.y = 750, 480
        self.local_tank.health = 100
        self.local_tank.alive = True
        self.local_tank.speed_boost_timer = 0
        self.local_tank.shoot_cooldown = 0

    # ---------- per-frame updates ----------
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
        # my bullets → opponent
        for b in self.bullets[:]:
            if not b.alive: continue
            if self.remote_data['alive']:
                rx, ry = self.remote_data['x'], self.remote_data['y']
                if rx < b.x < rx + 45 and ry < b.y < ry + 45:
                    b.alive = False
                    try:
                        self.socket.send((json.dumps({
                            'type': 'hit_registered',
                            'target_id': 'bot' if self.mode == 'bot' else self.remote_data.get('player_id')
                        }) + "\n").encode())
                    except: pass
                    self.bullets.remove(b)
                    continue

        # opponent's bullets → me
        for b in self.remote_bullets[:]:
            if not b.alive: continue
            if self.local_tank and self.local_tank.alive:
                if (self.local_tank.x < b.x < self.local_tank.x + self.local_tank.width and
                    self.local_tank.y < b.y < self.local_tank.y + self.local_tank.height):
                    b.alive = False
                    self.local_tank.take_damage(25)
                    if 'explosion' in self.sounds: self.sounds['explosion'].play()
                    self.remote_bullets.remove(b)
                    if not self.local_tank.alive and not self.died_this_round:
                        self.died_this_round = True
                        try:
                            self.socket.send((json.dumps({'type': 'player_died'}) + "\n").encode())
                        except: pass
                    continue

        # health pack pickup
        if self.health_pack and self.local_tank and self.local_tank.alive:
            hp = self.health_pack
            if (hp.x < self.local_tank.x + self.local_tank.width and
                hp.x + hp.width > self.local_tank.x and
                hp.y < self.local_tank.y + self.local_tank.height and
                hp.y + hp.height > self.local_tank.y):
                self.local_tank.health = min(self.local_tank.max_health,
                                             self.local_tank.health + 50)
                if 'pickup' in self.sounds: self.sounds['pickup'].play()
                print(f"[CLIENT] Health pack! HP = {self.local_tank.health}")
                self.health_pack = None

    # ---------- outbound ----------
    def send_input(self):
        if not self.connected or not self.local_tank or self.is_shutting_down: return
        if self.state != 'playing' or self.transition_active: return
        if time.time() - self.last_send_time < self.send_interval: return
        self.last_send_time = time.time()
        pk = pygame.key.get_pressed()
        keys = {}
        for kn in ['up', 'down', 'left', 'right']:
            if kn in self.local_tank.controls:
                keys[kn] = bool(pk[self.local_tank.controls[kn]])
        try:
            self.socket.send((json.dumps({'type': 'player_input',
                                          'keys': keys}) + "\n").encode())
        except: pass

    def send_shoot(self):
        if not self.connected or not self.local_tank or self.is_shutting_down: return
        if self.state != 'playing' or self.transition_active: return
        if not self.local_tank.alive: return
        b = self.local_tank.shoot()
        if b:
            self.bullets.append(b)
            if 'shoot' in self.sounds: self.sounds['shoot'].play()
            try:
                self.socket.send((json.dumps({'type': 'player_shoot',
                                              'bullet': b.get_state()}) + "\n").encode())
            except: pass

    def send_game_state(self):
        if not self.connected or not self.local_tank or self.is_shutting_down: return
        if self.state != 'playing' or self.transition_active: return
        try:
            self.socket.send((json.dumps({'type': 'game_state',
                                          'state': self.local_tank.get_state()}) + "\n").encode())
        except: pass

    # ---------- drawing ----------
    def draw_background(self):
        self.screen.fill((0, 0, 0))
        draw_sky(self.screen)
        draw_sun(self.screen)
        draw_mountains(self.screen)
        draw_water(self.screen)
        draw_grass(self.screen)
        draw_battlefield_border(self.screen)

    def draw_waiting(self):
        self.draw_background()
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170)); self.screen.blit(ov, (0, 0))
        txt = self.big_font.render("Waiting for Opponent...", True, (255, 255, 100))
        self.screen.blit(txt, txt.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40)))
        dots = "." * ((pygame.time.get_ticks() // 400) % 4)
        d = self.big_font.render(dots, True, (255, 255, 100))
        self.screen.blit(d, (WINDOW_WIDTH // 2 + 200, WINDOW_HEIGHT // 2 - 40))
        h = self.small_font.render("Another player must choose OPPONENT mode",
                                   True, (200, 200, 200))
        self.screen.blit(h, h.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 40)))

    def draw_hud(self):
        # Round indicator
        round_txt = self.font.render(f"ROUND {self.round}/{self.max_rounds}", True, (255, 255, 100))
        self.screen.blit(round_txt, round_txt.get_rect(center=(WINDOW_WIDTH // 2, 25)))

        # Scores
        score_txt = self.font.render(
            f"YOU: {self.my_score}   |   {self.opponent_name}: {self.opp_score}",
            True, (255, 255, 255))
        self.screen.blit(score_txt, (30, 25))

        # HP
        if self.local_tank:
            hp = self.small_font.render(f"HP: {self.local_tank.health}", True, (255, 255, 100))
            self.screen.blit(hp, (30, 55))
            mode_t = self.small_font.render(
                f"Mode: {'VS BOT' if self.mode == 'bot' else 'VS OPPONENT'}",
                True, (200, 200, 255))
            self.screen.blit(mode_t, (30, 80))

    def draw_round_transition(self):
        # Dark overlay
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160)); self.screen.blit(ov, (0, 0))

        # Winner text
        w = self.big_font.render(f"{self.round_winner_name} wins the round!",
                                 True, (255, 215, 0))
        self.screen.blit(w, w.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 60)))

        # Next round countdown
        remaining = max(0, self.transition_end_time - time.time())
        cd = self.font.render(f"Next round in {remaining:.1f}s", True, (255, 255, 255))
        self.screen.blit(cd, cd.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10)))

        # Running score
        sc = self.font.render(
            f"Score: You {self.my_score}  —  {self.opponent_name} {self.opp_score}",
            True, (200, 200, 200))
        self.screen.blit(sc, sc.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 60)))

    def draw_match_end(self):
        self.draw_background()
        ov = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 190)); self.screen.blit(ov, (0, 0))

        if self.match_result == 'win':
            title = "🏆 YOU WIN! 🏆"
            color = (255, 215, 0)
        elif self.match_result == 'loss':
            title = "BETTER LUCK NEXT TIME!"
            color = (255, 100, 100)
        else:
            title = "DRAW!"
            color = (200, 200, 200)

        t = self.winner_font.render(title, True, color)
        self.screen.blit(t, t.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 60)))

        final = self.font.render(
            f"Final Score: You {self.my_score}  —  {self.opponent_name} {self.opp_score}",
            True, (220, 220, 220))
        self.screen.blit(final, final.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 20)))

        hint = self.small_font.render("Press ESC to exit", True, (180, 180, 180))
        self.screen.blit(hint, hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 80)))

    # ---------- main loop ----------
    def run(self):
        print("[CLIENT] Game loop started.")

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.shutdown(); return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.shutdown(); return
                    if (self.state == 'playing' and not self.transition_active
                            and self.local_tank and self.local_tank.alive):
                        if event.key == pygame.K_SPACE and self.player_id == 1:
                            self.send_shoot()
                        elif event.key == pygame.K_RETURN and self.player_id == 2:
                            self.send_shoot()

            # ---- update ----
            if self.state == 'playing' and not self.transition_active and self.local_tank:
                pk = pygame.key.get_pressed()
                ks = {}
                for kn in ['up', 'down', 'left', 'right']:
                    if kn in self.local_tank.controls:
                        ks[self.local_tank.controls[kn]] = bool(pk[self.local_tank.controls[kn]])
                if self.local_tank.alive:
                    self.local_tank.move(ks)
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

            # ---- draw ----
            if self.state == 'waiting':
                self.draw_waiting()
            elif self.state == 'playing':
                self.draw_background()
                if self.health_pack: self.health_pack.draw(self.screen)
                for b in self.bullets: b.draw(self.screen)
                for b in self.remote_bullets: b.draw(self.screen)
                if self.local_tank: self.local_tank.draw(self.screen)
                draw_remote_tank(self.screen, self.remote_data)
                self.draw_hud()
                if self.transition_active:
                    self.draw_round_transition()
            elif self.state == 'game_over':
                self.draw_match_end()
            else:
                self.screen.fill((10, 20, 40))

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
        print("[CLIENT] Shutdown complete.")


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
        pygame.draw.rect(screen, (int(255*(1-r)), int(255*r), 0), (x - 5, y - 20, hw, 12))
    pygame.draw.rect(screen, (200, 200, 200), (x - 5, y - 20, 100, 12), 1)


if __name__ == "__main__":
    try:
        name = input("Enter your name: ").strip() or "Player"
        print()
        print("=" * 55)
        print("  You want to play with (BOT / OPPONENT)?")
        print("=" * 55)
        print("    [1] BOT      - play against AI")
        print("    [2] OPPONENT - wait for another player")
        print("=" * 55)
        while True:
            c = input("  Enter (1/2): ").strip()
            if c == '1': mode = 'bot'; break
            elif c == '2': mode = 'opponent'; break
            else: print("  Invalid choice.")

        client = GameClient(name, mode)
        client.run()
    except KeyboardInterrupt:
        print("\n[MAIN] Interrupted")
    except BaseException as e:
        print(f"\n[MAIN] FATAL: {type(e).__name__}: {e}")
        traceback.print_exc()
        try: input("\nPress Enter to exit...")
        except: pass