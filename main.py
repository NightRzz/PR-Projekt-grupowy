import socket
import threading
import time
import json
import uuid
from enum import Enum


class LobbyState(Enum):
    WAITING = 1
    COUNTDOWN = 2
    IN_GAME = 3


class GameLobby:
    def __init__(self, host_player):
        self.id = str(uuid.uuid4())[:4].upper()
        self.host = host_player
        self.players = {}
        self.chat_history = []
        self.state = LobbyState.WAITING
        self.countdown = 2
# --- MANAGERY ---


class LobbyManager:
    def __init__(self):
        self.lobbies = {}
        self.waiting_players = {}

    def create_lobby(self, player_id, username, player_data):
        lobby = GameLobby(player_id)
        self.lobbies[lobby.id] = lobby
        self.waiting_players[player_id] = lobby.id
        lobby.players[player_id] = player_data
        return lobby

    def find_lobby(self, lobby_id):
        lobby = self.lobbies.get(lobby_id)
        if not lobby or len(lobby.players) >= 2:
            return None
        return lobby

    def join_lobby(self, player_id, lobby_id, player_data):
        lobby = self.lobbies.get(lobby_id)
        if not lobby:
            return None
        self.waiting_players[player_id] = lobby_id
        lobby.players[player_id] = player_data
        return lobby

    def exit_lobby(self, player_id, players):
        lid = self.waiting_players.get(player_id)
        if not lid:
            return None
        lobby = self.lobbies[lid]
        if player_id in lobby.players:
            del lobby.players[player_id]
        if player_id in self.waiting_players:
            del self.waiting_players[player_id]
        if player_id == lobby.host and lobby.players:
            lobby.host = next(iter(lobby.players))
        if not lobby.players:
            del self.lobbies[lid]
            return None
        return lobby

class PlayerManager:
    def __init__(self):
        self.players = {}

    def add_player(self, pid, addr, username):
        self.players[pid] = {'addr': addr, 'username': username, 'ready': False}

    def remove_player(self, pid):
        if pid in self.players:
            del self.players[pid]

    def toggle_ready(self, pid):
        if pid in self.players:
            self.players[pid]['ready'] = not self.players[pid]['ready']
            return self.players[pid]['ready']
        return False

    def set_character(self, pid, character):
        if pid in self.players:
            self.players[pid]['character'] = character


class GameSession:
    def __init__(self, lobby):
        self.lobby = lobby
        self.state = {'players': {}, 'enemies': {}}
        self.enemy_count = 1
        spawn_pos = [[271, 385], [716, 321]]
        enemy_spawn_pos = [[1031.0, 349.0]]
        for i, pid in enumerate(lobby.players):
            self.state['players'][pid] = {
                'position': spawn_pos[i],
                'velocity': [0, 0],
                'anim_state': 'idle',
                'direction': 'right'
            }
        for i in range(self.enemy_count):
            self.state['enemies'][str(uuid.uuid4())[:4].upper()] = {
                'position': enemy_spawn_pos[i],
                'velocity': [0, 0],
                'anim_state': 'idle',
                'direction': 'right',
                'character': 'Skeleton'
            }

    def update_player(self, pid, msg):
        player_state = self.state['players'].get(pid)
        if player_state:
            player_state.update({
                'position': msg.get('position', player_state['position']),
                'velocity': msg.get('velocity', player_state['velocity']),
                'anim_state': msg.get('anim_state', player_state['anim_state']),
                'direction': msg.get('direction', player_state['direction']),
            })



# --- ROUTER WIADOMOŚCI ---

class MessageRouter:
    def __init__(self, server):
        self.server = server
        self.handlers = {
            'create_lobby': self.handle_create_lobby,
            'find_lobby': self.handle_find_lobby,
            'join_lobby': self.handle_join_lobby,
            'exit_lobby': self.handle_exit_lobby,
            'chat_message': self.handle_chat_message,
            'toggle_ready': self.handle_toggle_ready,
            'start_game': self.handle_start_game,
            'player_input': self.handle_player_input,
            'player_ready': self.handle_player_ready,
            'enemy_status': self.handle_enemy_status,
            'character_select': self.handle_character_select
        }

    def route(self, msg, addr):
        handler = self.handlers.get(msg.get('type'), self.unknown_command)
        handler(msg, addr)

    def handle_create_lobby(self, msg, addr):
        pid = str(addr)
        username = msg.get('username', '')
        if pid in self.server.lobby_manager.waiting_players or not self.server.valid_username(username):
            self.server.send_error(addr, "Invalid or duplicate username")
            return
        self.server.player_manager.add_player(pid, addr, username)
        player_data = self.server.player_manager.players[pid]
        lobby = self.server.lobby_manager.create_lobby(pid, username, player_data)
        print(f"{username} created lobby {lobby.id}")
        self.server.send_lobby_data(lobby, pid)

    def handle_find_lobby(self, msg, addr):
        lid = msg.get('lobby_id', '').upper()
        lobby = self.server.lobby_manager.find_lobby(lid)
        if not lobby:
            self.server.send_json({'status': 'not found'}, addr)
        else:
            self.server.send_json({'status': 'found'}, addr)

    def handle_join_lobby(self, msg, addr):
        pid = str(addr)
        username = msg.get('username', '')
        lid = msg.get('lobby_id', '').upper()
        if pid in self.server.lobby_manager.waiting_players or not self.server.valid_username(username):
            self.server.send_error(addr, "Invalid or duplicate username")
            return
        self.server.player_manager.add_player(pid, addr, username)
        player_data = self.server.player_manager.players[pid]
        lobby = self.server.lobby_manager.join_lobby(pid, lid, player_data)
        if not lobby:
            self.server.send_error(addr, "Lobby not found")
            return
        print(f"{username} joined lobby {lid}")
        self.server.broadcast_lobby_update(lobby)
        self.server.send_lobby_data(lobby, pid)

    def handle_exit_lobby(self, msg, addr):
        pid = str(addr)
        lobby = self.server.lobby_manager.exit_lobby(pid, self.server.player_manager.players)
        self.server.player_manager.remove_player(pid)
        if lobby:
            self.server.broadcast_lobby_update(lobby)
            self.server.send_lobby_data(lobby, pid)

    def handle_chat_message(self, msg, addr):
        pid = str(addr)
        lid = self.server.lobby_manager.waiting_players.get(pid)
        if not lid:
            return
        lobby = self.server.lobby_manager.lobbies[lid]
        text = msg.get('text', '')[:100].strip()
        if not text:
            return
        chat = {'player': self.server.player_manager.players[pid]['username'], 'text': text, 'timestamp': time.time()}
        lobby.chat_history.append(chat)
        self.server.broadcast(lobby, {'type': 'chat_message', **chat})

    def handle_toggle_ready(self, msg, addr):
        pid = str(addr)
        lid = self.server.lobby_manager.waiting_players.get(pid)
        if not lid:
            return
        lobby = self.server.lobby_manager.lobbies[lid]
        ready = self.server.player_manager.toggle_ready(pid)
        lobby.players[pid]['ready'] = ready
        self.server.broadcast_lobby_update(lobby)

    def handle_start_game(self, msg, addr):
        pid = str(addr)
        lid = self.server.lobby_manager.waiting_players.get(pid)
        if not lid:
            return
        lobby = self.server.lobby_manager.lobbies[lid]
        if pid == lobby.host and all(p['ready'] for p in lobby.players.values()):
            lobby.state = LobbyState.COUNTDOWN
            threading.Thread(target=self.server.countdown_and_start, args=(lobby,), daemon=True).start()

    def handle_player_input(self, msg, addr):
        pid = str(addr)
        lid = self.server.lobby_manager.waiting_players.get(pid)
        session = self.server.game_sessions.get(lid)
        if session:
            session.update_player(pid, msg)

    def handle_enemy_status(self, msg, addr):
        pid = str(addr)
        lid = self.server.lobby_manager.waiting_players.get(pid)
        session = self.server.game_sessions.get(lid)
        print("xd1")
        if session:
            for eid in session.state['enemies']:
                print("xd")
                eid.update({
                    'position': msg.get('position', eid['position']),
                    'velocity': msg.get('velocity', eid['velocity']),
                    'anim_state': msg.get('anim_state', eid['anim_state']),
                    'direction': msg.get('direction', eid['direction']),
                })

    def handle_player_ready(self, msg, addr):
        pid = str(addr)
        lid = self.server.lobby_manager.waiting_players.get(pid)
        if not lid:
            return
        lobby = self.server.lobby_manager.lobbies[lid]
        lobby.ready_players = getattr(lobby, 'ready_players', set())
        lobby.ready_players.add(pid)
        session = self.server.game_sessions.get(lid)
        pid2 = 0
        for other_pid, other_p in lobby.players.items():
            if str(pid) != str(other_pid):
                pid2 = other_pid
            self.server.send_json({
                'type': 'spawn_player',
                'id': other_pid,
                'position': session.state['players'].get(other_pid, {}).get('position', [0,0]) if session else [0,0],
                'is_local': (pid == other_pid),
                'username': self.server.player_manager.players[other_pid]['username'],
                'character': self.server.player_manager.players[other_pid].get('character', 'warrior')
            }, lobby.players[pid]['addr'])
        for eid in session.state['enemies']:
            self.server.send_json({
                'type': 'spawn_enemy',
                'enemy_id': str(eid),
                'is_host': (str(pid) != str(pid2)),
                'position': session.state['enemies'].get(eid, {}).get('position', [0, 0]) if session else [0, 0],
                'character': session.state['enemies'][eid].get('character', 'Skeleton')
            }, lobby.players[pid]['addr'])

    def handle_character_select(self, msg, addr):
        pid = str(addr)
        char = msg.get('character', 'warrior')
        self.server.player_manager.set_character(pid, char)
        lid = self.server.lobby_manager.waiting_players.get(pid)
        if not lid:
            return
        lobby = self.server.lobby_manager.lobbies[lid]
        for p in lobby.players.values():
            self.server.send_json({'type': 'character_changed', 'id': pid, 'character': char}, p['addr'])

    def unknown_command(self, msg, addr):
        self.server.send_error(addr, "Unknown command")

# --- GŁÓWNY SERWER ---

class GameServer:
    def __init__(self, host='192.168.0.164', port=9999):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.lobby_manager = LobbyManager()
        self.player_manager = PlayerManager()
        self.game_sessions = {}
        self.running = True
        self.lock = threading.Lock()
        self.router = MessageRouter(self)

    def start(self):
        print(f"Server started on {self.sock.getsockname()}")
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def receive_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                msg = json.loads(data.decode())
                with self.lock:
                    self.router.route(msg, addr)
            except Exception as e:
                print(f"Error: {e}")

    def countdown_and_start(self, lobby):
        for i in range(2, 0, -1):
            with self.lock:
                if lobby.state != LobbyState.COUNTDOWN:
                    return
                lobby.countdown = i
                self.broadcast_lobby_update(lobby)
            time.sleep(1)
        with self.lock:
            for p in lobby.players.values():
                self.send_json({'type': 'game'}, p['addr'])
            self.init_game(lobby)

    def init_game(self, lobby):
        lobby.state = LobbyState.IN_GAME
        session = GameSession(lobby)
        self.game_sessions[lobby.id] = session
        threading.Thread(target=self.game_loop, args=(lobby, session), daemon=True).start()

    def game_loop(self, lobby, session):
        while self.running and lobby.id in self.game_sessions:
            with self.lock:
                state = session.state['players']
                for pid, pdata in state.items():
                    for p in lobby.players.values():
                        self.send_json({
                            'type': 'player_position',
                            'id': pid,
                            **pdata
                        }, p['addr'])
                        self.send_json({
                            'type': 'enemy_sync',
                            'enemies': session.state['enemies']
                        }, p['addr'])
            time.sleep(0.01)

    # --- WSPÓLNE METODY ---

    def broadcast_lobby_update(self, lobby):
        data = {
            'type': 'lobby_update',
            'countdown': lobby.countdown,
            'players': [
                {'username': p['username'], 'ready': p['ready'], 'character': p.get('character')}
                for p in lobby.players.values()
            ]
        }
        self.broadcast(lobby, data)

    def send_lobby_data(self, lobby, pid):
        data = {
            'type': 'lobby_joined',
            'lobby_id': lobby.id,
            'host': lobby.host == pid,
            'players': [
                {'username': p['username'], 'ready': p['ready'], 'character': p.get('character', '')}
                for p in lobby.players.values()
            ],
            'chat_history': lobby.chat_history[-10:]
        }
        self.send_json(data, self.player_manager.players[pid]['addr'])

    def broadcast(self, lobby, data):
        for p in lobby.players.values():
            self.send_json(data, p['addr'])

    def send_json(self, data, addr):
        try:
            self.sock.sendto(json.dumps(data).encode(), addr)
        except Exception as e:
            print(f"Send error: {e}")

    def send_error(self, addr, msg):
        self.send_json({'type': 'error', 'message': msg}, addr)

    def valid_username(self, username):
        return 3 <= len(username) <= 16 and username.isalnum()

    def stop(self):
        self.running = False
        self.sock.close()

if __name__ == "__main__":
    server = GameServer()
    try:
        server.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("Server stopped")
