import socket
import json
import sys

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5555
BUFFER_SIZE = 4096

print("=== DEBUG START ===", flush=True)

# 1. Get name
name = input("Enter your name: ").strip() or "TestPlayer"
print(f"=== NAME: {name} ===", flush=True)

# 2. Connect
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER_IP, SERVER_PORT))
    print("=== CONNECTED ===", flush=True)
except Exception as e:
    print(f"=== CONNECTION FAILED: {e} ===", flush=True)
    sys.exit(1)

# 3. Send join
s.send((json.dumps({'type': 'join', 'name': name}) + "\n").encode())
print("=== JOIN SENT ===", flush=True)

# 4. Receive welcome
s.settimeout(5)
try:
    data = s.recv(BUFFER_SIZE).decode()
    print(f"=== RECEIVED: {repr(data)} ===", flush=True)
except Exception as e:
    print(f"=== RECV FAILED: {e} ===", flush=True)

# 5. Parse
player_id = None
for line in data.split("\n"):
    if not line.strip():
        continue
    msg = json.loads(line)
    print(f"=== PARSED: {msg} ===", flush=True)
    if msg['type'] == 'welcome':
        player_id = msg['player_id']

print(f"=== PLAYER ID: {player_id} ===", flush=True)

# 6. Choose mode
mode = input("Choose mode (1=BOT, 2=OPPONENT): ").strip()
mode_str = 'bot' if mode == '1' else 'opponent'
print(f"=== SENDING MODE: {mode_str} ===", flush=True)
s.send((json.dumps({'type': 'choose_mode', 'mode': mode_str}) + "\n").encode())

# 7. Wait for response
print("=== WAITING FOR SERVER RESPONSE ===", flush=True)
s.settimeout(10)
try:
    response = s.recv(BUFFER_SIZE).decode()
    print(f"=== SERVER SAID: {repr(response)} ===", flush=True)
except Exception as e:
    print(f"=== RECV FAILED: {e} ===", flush=True)

print("=== DEBUG END ===", flush=True)
s.close()