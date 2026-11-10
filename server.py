import socket
import threading
import json
import time
import random
import math
import os  # <--- ADDED FOR CLOUD
from database import Database

SERVER_IP = "0.0.0.0"  # <--- CHANGED FOR CLOUD (Accepts connections from anywhere)
SERVER_PORT = int(os.environ.get("PORT", 5555)) # <--- CHANGED FOR CLOUD
BUFFER_SIZE = 4096
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
MAX_ROUNDS = 5
TRANSITION_SECONDS = 3

class GameServer:
    def __init__(self):
        self.players = {}
        self.waiting = []
        self.matches = {}
        self.next_pid = 1
        self.next_mid = 1
        self.running = True
        self.db = Database()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((SERVER_IP, SERVER_PORT))
            self.server_socket.listen(10)
            print(f"[SERVER] Started on {SERVER_IP}:{SERVER_PORT}")
            print("[SERVER] Waiting for players...\n")
        except Exception as e:
            print(f"[ERROR] {e}")
            self.running = False

    def send_to(self, pid, msg):
        if pid == 'bot' or pid not in self.players:
            return
        try:
            self.players[pid]['socket'].send((json.dumps(msg) + "\n").encode())
        except:
            pass

    def create_bot(self):
        return {'x': 750, 'y': 480, 'angle': 0, 'health': 100,
                'alive': True, 'player_id': 'bot', 'shoot_timer': 0}

    def start_match(self, p1_id, p2_id, mode):
        mid = self.next_mid
        self.next_mid += 1
        self.matches[mid] = {
            'p1': p1_id, 'p2': p2_id, 'mode': mode,
            'round': 0, 'p1_score': 0, 'p2_score': 0,
            'health_pack': None, 'state': 'starting',
            'transition_timer': 0,
            'bot_data': self.create_bot() if mode == 'bot' else None,
            'bot_respawn': 0,
        }
        self.players[p1_id]['match_id'] = mid
        self.players[p1_id]['state'] = 'playing'
        if p2_id != 'bot':
            self.players[p2_id]['match_id'] = mid
            self.players[p2_id]['state'] = 'playing'

        opp1_name = self.players[p2_id]['name'] if p2_id != 'bot' else 'BOT'
        opp2_name = self.players[p1_id]['name']
        
        # ROLE FIX APPLIED
        self.send_to(p1_id, {'type': 'game_start', 'player_id': p1_id,
                             'role': 'p1', 'mode': mode, 'opponent_name': opp1_name})
        if p2_id != 'bot':
            self.send_to(p2_id, {'type': 'game_start', 'player_id': p2_id,
                                 'role': 'p2', 'mode': mode, 'opponent_name': opp2_name})

        print(f"[SERVER] Match {mid} started: P{p1_id} vs {p2_id} ({mode})")
        self.start_round(mid)

    def start_round(self, mid):
        m = self.matches[mid]
        m['round'] += 1
        m['state'] = 'active'

        hp_x = random.randint(150, WINDOW_WIDTH - 200)
        hp_y = random.randint(WINDOW_HEIGHT // 2 + 80, WINDOW_HEIGHT - 120)
        m['health_pack'] = {'x': hp_x, 'y': hp_y}

        if m['bot_data']:
            m['bot_data']['health'] = 100
            m['bot_data']['alive'] = True
            m['bot_data']['x'] = random.randint(600, WINDOW_WIDTH - 100)
            m['bot_data']['y'] = random.randint(WINDOW_HEIGHT // 2 + 80, WINDOW_HEIGHT - 120)
            m['bot_data']['shoot_timer'] = 0

        def send_round_start(pid, role):
            your_score = m['p1_score'] if role == 'p1' else m['p2_score']
            opp_score  = m['p2_score'] if role == 'p1' else m['p1_score']
            opp_name = ('BOT' if m['p2'] == 'bot' else self.players[m['p2']]['name']) if role == 'p1' \
                       else self.players[m['p1']]['name']
            
            # ROLE FIX APPLIED
            self.send_to(pid, {
                'type': 'round_start',
                'role': role,
                'round': m['round'],
                'max_rounds': MAX_ROUNDS,
                'your_score': your_score,
                'opp_score': opp_score,
                'opponent_name': opp_name,
                'health_pack': {'x': hp_x, 'y': hp_y}
            })

        send_round_start(m['p1'], 'p1')
        if m['p2'] != 'bot':
            send_round_start(m['p2'], 'p2')
        print(f"[SERVER] Round {m['round']}/{MAX_ROUNDS} started")

    def end_round(self, mid, winner_id):
        m = self.matches[mid]
        m['state'] = 'transition'
        m['transition_timer'] = TRANSITION_SECONDS * 60

        if winner_id == m['p1']: m['p1_score'] += 1
        elif winner_id == m['p2']: m['p2_score'] += 1

        winner_name = 'BOT' if winner_id == 'bot' else self.players[winner_id]['name']

        def send_end(pid, role):
            your_score = m['p1_score'] if role == 'p1' else m['p2_score']
            opp_score  = m['p2_score'] if role == 'p1' else m['p1_score']
            opp_name = ('BOT' if m['p2'] == 'bot' else self.players[m['p2']]['name']) if role == 'p1' \
                       else self.players[m['p1']]['name']
            self.send_to(pid, {
                'type': 'round_end',
                'winner_name': winner_name,
                'your_score': your_score,
                'opp_score': opp_score,
                'opponent_name': opp_name,
                'next_round_in': TRANSITION_SECONDS
            })

        send_end(m['p1'], 'p1')
        if m['p2'] != 'bot': send_end(m['p2'], 'p2')
        print(f"[SERVER] Round {m['round']} → {winner_name}. Score {m['p1_score']}-{m['p2_score']}")

    def end_match(self, mid):
        m = self.matches[mid]
        m['state'] = 'over'
        p1s, p2s = m['p1_score'], m['p2_score']

        if p1s > p2s:  winner = m['p1']
        elif p2s > p1s: winner = m['p2']
        else:           winner = None

        p1_name = self.players[m['p1']]['name']
        p2_name = 'BOT' if m['p2'] == 'bot' else self.players[m['p2']]['name']

        if winner is None: winner_name = 'Draw'
        elif winner == m['p1']: winner_name = p1_name
        else: winner_name = p2_name

        self.db.save_match(p1_name, p2_name, p1s, p2s, winner_name, m['mode'])

        if m['p2'] != 'bot':
            self.db.update_player_stats(p1_name, p1s > p2s, draw=(p1s == p2s))
            self.db.update_player_stats(p2_name, p2s > p1s, draw=(p1s == p2s))
        else:
            self.db.update_player_stats(p1_name, p1s > p2s, draw=(p1s == p2s))

        def send_end(pid, role):
            your_score = p1s if role == 'p1' else p2s
            opp_score  = p2s if role == 'p1' else p1s
            if winner is None: result = 'draw'
            elif winner == pid: result = 'win'
            else: result = 'loss'
            opp_name = ('BOT' if m['p2'] == 'bot' else self.players[m['p2']]['name']) if role == 'p1' \
                       else self.players[m['p1']]['name']
            self.send_to(pid, {
                'type': 'match_end',
                'result': result,
                'your_score': your_score,
                'opp_score': opp_score,
                'opponent_name': opp_name
            })

        send_end(m['p1'], 'p1')
        if m['p2'] != 'bot': send_end(m['p2'], 'p2')
        print(f"[SERVER] MATCH {mid} OVER. Final: {p1s}-{p2s}")

    def handle_message(self, pid, msg):
        t = msg.get('type')

        if t == 'register':
            username = msg.get('username', '').strip()
            password = msg.get('password', '')
            if not username or not password:
                self.send_to(pid, {'type': 'auth_response', 'success': False, 'message': 'Username and password required'})
                return
            success, result = self.db.register_user(username, password)
            if success:
                self.players[pid]['name'] = username
                self.players[pid]['auth'] = True
                self.send_to(pid, {'type': 'auth_response', 'success': True, 'stats': result})
            else:
                self.send_to(pid, {'type': 'auth_response', 'success': False, 'message': result})
            return

        if t == 'login':
            username = msg.get('username', '').strip()
            password = msg.get('password', '')
            success, result = self.db.login_user(username, password)
            if success:
                self.players[pid]['name'] = username
                self.players[pid]['auth'] = True
                self.send_to(pid, {'type': 'auth_response', 'success': True, 'stats': result})
            else:
                self.send_to(pid, {'type': 'auth_response', 'success': False, 'message': result})
            return

        if t == 'get_leaderboard':
            lb = self.db.get_leaderboard()
            self.send_to(pid, {'type': 'leaderboard', 'data': lb})
            return

        if t == 'get_stats':
            stats = self.db.get_stats(self.players[pid]['name'])
            if stats:
                self.send_to(pid, {'type': 'stats_update', 'stats': stats})
            return

        if t == 'choose_mode':
            mode = msg.get('mode')
            if mode == 'bot':
                self.start_match(pid, 'bot', 'bot')
            elif mode == 'opponent':
                matched = False
                while self.waiting:
                    other = self.waiting.pop(0)
                    if other in self.players:
                        self.start_match(other, pid, 'human')
                        matched = True
                        break
                if not matched:
                    self.waiting.append(pid)
                    self.send_to(pid, {'type': 'waiting'})
                    print(f"[SERVER] {self.players[pid]['name']} waiting...")

        elif t in ('player_input', 'player_shoot', 'game_state'):
            mid = self.players[pid].get('match_id')
            if not mid or mid not in self.matches: return
            m = self.matches[mid]
            other = m['p2'] if m['p1'] == pid else m['p1']
            if other != 'bot':
                self.send_to(other, {'type': t, 'player_id': pid, **({k: v for k, v in msg.items() if k != 'type'})})

        elif t == 'hit_registered':
            mid = self.players[pid].get('match_id')
            if not mid or mid not in self.matches: return
            m = self.matches[mid]
            if m['mode'] != 'bot' or m['state'] != 'active': return
            bot = m['bot_data']
            if bot and bot['alive']:
                bot['health'] -= 25
                if bot['health'] <= 0:
                    bot['health'] = 0
                    bot['alive'] = False
                    self.send_to(pid, {'type': 'bot_hit', 'health': 0, 'alive': False})
                    self.end_round(mid, pid)
                else:
                    self.send_to(pid, {'type': 'bot_hit', 'health': bot['health'], 'alive': True})

        elif t == 'player_died':
            mid = self.players[pid].get('match_id')
            if not mid or mid not in self.matches: return
            m = self.matches[mid]
            if m['state'] != 'active': return
            other = m['p2'] if m['p1'] == pid else m['p1']
            self.end_round(mid, other)

    def handle_client(self, sock, addr, pid):
        buf = ""
        try:
            while self.running:
                data = sock.recv(BUFFER_SIZE)
                if not data: break
                buf += data.decode()
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if not line.strip(): continue
                    try:
                        self.handle_message(pid, json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[ERROR] Client {pid}: {e}")
        finally:
            self.disconnect(pid)

    def disconnect(self, pid):
        if pid not in self.players: return
        name = self.players[pid]['name']
        mid = self.players[pid].get('match_id')
        if mid and mid in self.matches:
            m = self.matches[mid]
            other = m['p2'] if m['p1'] == pid else m['p1']
            if other != 'bot':
                self.send_to(other, {'type': 'opponent_disconnected'})
                if other in self.players:
                    self.players[other]['match_id'] = None
                    self.players[other]['state'] = 'choosing'
            del self.matches[mid]
        if pid in self.waiting:
            self.waiting.remove(pid)
        try: self.players[pid]['socket'].close()
        except: pass
        del self.players[pid]
        print(f"[SERVER] {name} disconnected")

    def game_loop(self):
        while self.running:
            time.sleep(1 / 60)
            for mid in list(self.matches.keys()):
                if mid not in self.matches: continue
                m = self.matches[mid]

                if (m['mode'] == 'bot' and m['bot_data'] and m['state'] == 'active' and m['bot_data']['alive']):
                    bot = m['bot_data']
                    if random.random() < 0.03: bot['angle'] = random.randint(0, 360)
                    rad = math.radians(bot['angle'])
                    bot['x'] += 2 * math.sin(rad)
                    bot['y'] -= 2 * math.cos(rad)
                    bot['x'] = max(65, min(WINDOW_WIDTH - 110, bot['x']))
                    bot['y'] = max(380, min(WINDOW_HEIGHT - 110, bot['y']))

                    bot['shoot_timer'] += 1
                    if bot['shoot_timer'] > 90:
                        bot['shoot_timer'] = 0
                        self.send_to(m['p1'], {
                            'type': 'player_shoot', 'player_id': 'bot',
                            'bullet': {'x': bot['x'], 'y': bot['y'], 'angle': random.randint(0, 360), 'owner_id': 'bot'}
                        })
                    self.send_to(m['p1'], {'type': 'game_state', 'player_id': 'bot', 'state': bot})

                if m['state'] == 'transition':
                    m['transition_timer'] -= 1
                    if m['transition_timer'] <= 0:
                        if m['round'] >= MAX_ROUNDS: self.end_match(mid)
                        else: self.start_round(mid)

    def accept_clients(self):
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                sock, addr = self.server_socket.accept()
                self.server_socket.settimeout(None)

                pid = self.next_pid
                self.next_pid += 1

                data = sock.recv(BUFFER_SIZE)
                try:
                    msg = json.loads(data.decode().strip())
                    name = msg.get('name', f'Player{pid}')
                except: name = f'Player{pid}'

                self.players[pid] = {'socket': sock, 'address': addr, 'name': name, 'state': 'choosing', 'match_id': None, 'auth': False}

                sock.send((json.dumps({'type': 'welcome', 'player_id': pid}) + "\n").encode())
                sock.send((json.dumps({'type': 'choose_mode'}) + "\n").encode())
                print(f"[SERVER] {name} connected (ID: {pid})")

                threading.Thread(target=self.handle_client, args=(sock, addr, pid), daemon=True).start()
            except socket.timeout: continue
            except Exception as e:
                if self.running: print(f"[ERROR] Accept: {e}")

    def run(self):
        threading.Thread(target=self.game_loop, daemon=True).start()
        self.accept_clients()

if __name__ == "__main__":
    server = GameServer()
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        server.running = False
        server.server_socket.close()