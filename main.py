import socket
import threading
import time
import json
import uuid
from enum import Enum
from collections import deque

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

class GameServer:
    def __init__(self, host='192.168.0.164', port=9999):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.lobbies = {}
        self.players = {}
        self.waiting_players = {}
        self.game_states = {}
        self.running = True
        self.lock = threading.Lock()

    def start(self):
        print(f"Server started on {self.sock.getsockname()}")
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def receive_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                self.handle_message(json.loads(data.decode()), addr)
            except Exception as e:
                print(f"Error: {e}")

    def handle_message(self, msg, addr):
        handlers = {
            'create_lobby': self.create_lobby,
            'find_lobby': self.find_lobby,
            'join_lobby': self.join_lobby,
            'exit_lobby': self.exit_lobby,
            'chat_message': self.chat_message,
            'toggle_ready': self.toggle_ready,
            'start_game': self.start_game,
            'player_input': self.player_input,
            'player_ready': self.player_ready,
            'character_select': self.character_select,
        }
        with self.lock:
            handler = handlers.get(msg.get('type'), self.unknown_command)
            handler(msg, addr)

    def create_lobby(self, msg, addr):
        pid = str(addr)
        if pid in self.waiting_players or not self.valid_username(msg.get('username', '')):
            self.send_error(addr, "Invalid or duplicate username")
            return
        lobby = GameLobby(pid)
        self.lobbies[lobby.id] = lobby
        self.waiting_players[pid] = lobby.id
        self.players[pid] = {'addr': addr, 'username': msg['username'], 'ready': False}
        lobby.players[pid] = self.players[pid]
        print(f"{msg['username']} created lobby {lobby.id}")
        self.send_lobby_data(lobby, pid)

    def find_lobby(self, msg, addr):
        lid = msg.get('lobby_id', '').upper()
        lobby = self.lobbies.get(lid)
        if not lobby or len(lobby.players) >= 2:
            self.send_json({'status': 'not found'}, addr)
        self.send_json({'status': 'found'}, addr)

    def join_lobby(self, msg, addr):
        pid = str(addr)
        lid = msg.get('lobby_id', '').upper()
        if pid in self.waiting_players or not self.valid_username(msg.get('username', '')):
            self.send_error(addr, "Invalid or duplicate username")
            return
        lobby = self.lobbies.get(lid)
        self.waiting_players[pid] = lid
        self.players[pid] = {'addr': addr, 'username': msg['username'], 'ready': False}
        lobby.players[pid] = self.players[pid]
        print(f"{msg['username']} joined lobby {lid}")
        self.broadcast_lobby_update(lobby)
        self.send_lobby_data(lobby, pid)

    def exit_lobby(self, msg, addr):
        pid = str(addr)
        lid = self.waiting_players.get(pid)
        lobby = self.lobbies[lid]
        if pid in lobby.players: del lobby.players[pid]
        if pid in self.players: del self.players[pid]
        if pid in self.waiting_players: del self.waiting_players[pid]
        if pid == lobby.host and lobby.players:
            lobby.host = next(iter(lobby.players))
        if not lobby.players:
            del self.lobbies[lid]
            return
        self.broadcast_lobby_update(lobby)
        self.send_lobby_data(lobby, pid)

    def chat_message(self, msg, addr):
        pid = str(addr)
        lid = self.waiting_players.get(pid)
        if not lid: return
        lobby = self.lobbies[lid]
        text = msg.get('text', '')[:100].strip()
        if not text: return
        chat = {'player': self.players[pid]['username'], 'text': text, 'timestamp': time.time()}
        lobby.chat_history.append(chat)
        self.broadcast(lobby, {'type': 'chat_message', **chat})

    def toggle_ready(self, msg, addr):
        pid = str(addr)
        lid = self.waiting_players.get(pid)
        if not lid: return
        lobby = self.lobbies[lid]
        p = lobby.players[pid]
        p['ready'] = not p['ready']
        self.players[pid]['ready'] = p['ready']
        self.broadcast_lobby_update(lobby)

    def start_game(self, msg, addr):
        pid = str(addr)
        lid = self.waiting_players.get(pid)
        if not lid: return
        lobby = self.lobbies[lid]
        if pid == lobby.host and all(p['ready'] for p in lobby.players.values()):
            lobby.state = LobbyState.COUNTDOWN
            threading.Thread(target=self.countdown_and_start, args=(lobby,), daemon=True).start()

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
        spawn_pos = [[271, 385], [716, 321]]
        self.game_states[lobby.id] = {'players': {}}
        for i, pid in enumerate(lobby.players):
            self.game_states[lobby.id]['players'][pid] = {
                'position': spawn_pos[i],
                'velocity': [0, 0],
                'anim_state': 'idle',
                'direction': 'right'
            }
        threading.Thread(target=self.game_loop, args=(lobby,), daemon=True).start()

    def game_loop(self, lobby):
        while self.running and lobby.id in self.game_states:
            with self.lock:
                state = self.game_states[lobby.id]['players']
                for pid, pdata in state.items():
                    for p in lobby.players.values():
                        self.send_json({
                            'type': 'player_position',
                            'id': pid,
                            **pdata
                        }, p['addr'])
            time.sleep(0.01)

    def player_input(self, msg, addr):
        pid = str(addr)
        lid = self.waiting_players.get(pid)
        if not lid or lid not in self.game_states: return
        player_state = self.game_states[lid]['players'].get(pid)
        if player_state:
            player_state.update({
                'position': msg.get('position', player_state['position']),
                'velocity': msg.get('velocity', player_state['velocity']),
                'anim_state': msg.get('anim_state', player_state['anim_state']),
                'direction': msg.get('direction', player_state['direction']),
            })

    def player_ready(self, msg, addr):
        pid = str(addr)
        lid = self.waiting_players.get(pid)
        if not lid: return
        lobby = self.lobbies[lid]
        lobby.ready_players = getattr(lobby, 'ready_players', set())
        lobby.ready_players.add(pid)
        for other_pid, other_p in lobby.players.items():
            self.send_json({
                'type': 'spawn_player',
                'id': other_pid,
                'position': self.game_states.get(lid, {}).get('players', {}).get(other_pid, {}).get('position', [0,0]),
                'is_local': (pid == other_pid),
                'username': self.players[other_pid]['username'],
                'character': self.players[other_pid].get('character', 'warrior')
            }, lobby.players[pid]['addr'])

    def character_select(self, msg, addr):
        pid = str(addr)
        char = msg.get('character', 'warrior')
        if pid in self.players:
            self.players[pid]['character'] = char
        lid = self.waiting_players.get(pid)
        if not lid: return
        lobby = self.lobbies[lid]
        for p in lobby.players.values():
            self.send_json({'type': 'character_changed', 'id': pid, 'character': char}, p['addr'])

    def broadcast_lobby_update(self, lobby):
        data = {
            'type': 'lobby_update',
            'countdown': lobby.countdown,
            'players': [{'username': p['username'], 'ready': p['ready'], 'character': p.get('character')} for p in lobby.players.values()]
        }
        self.broadcast(lobby, data)

    def send_lobby_data(self, lobby, pid):
        data = {
            'type': 'lobby_joined',
            'lobby_id': lobby.id,
            'host': lobby.host == pid,
            'players': [{'username': p['username'], 'ready': p['ready'], 'character': p.get('character', '')} for p in lobby.players.values()],
            'chat_history': lobby.chat_history[-10:]
        }
        self.send_json(data, self.players[pid]['addr'])

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

    def unknown_command(self, msg, addr):
        self.send_error(addr, "Unknown command")

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
