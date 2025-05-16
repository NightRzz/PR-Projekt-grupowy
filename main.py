import socket
import threading
import time
import json
import uuid
import random
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
        self.ready_players = set()
        self.state = LobbyState.WAITING
        self.countdown = 10
        self.created_at = time.time()



class GameServer:
    def __init__(self, host='192.168.0.164', port=9999):
        self.server_address = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.server_address)

        self.lobbies = {}
        self.players = {}
        self.waiting_players = {}
        self.game_states = {}

        self.running = True
        self.lock = threading.Lock()
        self.state_history = deque(maxlen=60)

    def start(self):
        print(f"Server started on {self.server_address}")
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def receive_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                self.handle_message(data, addr)
            except Exception as e:
                print(f"Receive error: {e}")

    def handle_message(self, data, addr):
        try:
            message = json.loads(data.decode('utf-8'))
            handler = {
                'create_lobby': self.handle_create_lobby,
                'join_lobby': self.handle_join_lobby,
                'chat_message': self.handle_chat_message,
                'toggle_ready': self.handle_toggle_ready,
                'start_game': self.handle_start_game,
                'player_input': self.handle_player_input,
                'attack': self.handle_attack,
                'pause': self.handle_pause,
                'player_ready': self.handle_player_ready
            }.get(message['type'], self.handle_unknown)

            with self.lock:
                handler(message, addr)

        except json.JSONDecodeError:
            print(f"Invalid JSON from {addr}")
        except Exception as e:
            print(f"Processing error: {e}")

    def handle_player_ready(self, message, addr):
        player_id = str(addr)
        lobby_id = self.waiting_players.get(player_id)
        if not lobby_id:
            return
        lobby = self.lobbies.get(lobby_id)
        if not lobby:
            return
        # Mark this player as ready for spawning
        lobby.ready_players.add(player_id)
        # Send spawn_player messages for all players, to this player only
        for other_id in lobby.players.keys():
            self._send_json({
                'type': 'spawn_player',
                'id': other_id,
                'position': self.game_states[lobby_id]['players'][other_id]['position'],
                'is_local': (player_id == other_id)
            }, lobby.players[player_id]['addr'])

    # Lobby management
    def handle_create_lobby(self, message, addr):
        player_id = str(addr)

        if player_id in self.waiting_players:
            return

        if not self.validate_username(message.get('username', '')):
            self.send_error(addr, "Invalid username (3-16 alphanumeric chars)")
            return

        lobby = GameLobby(player_id)
        print(f"player {message['username']} started lobby id: {lobby.id}")
        self.lobbies[lobby.id] = lobby
        self.waiting_players[player_id] = lobby.id

        self.players[player_id] = {
            'addr': addr,
            'username': message['username'],
            'ready': False,
            'last_active': time.time()
        }
        lobby.players[player_id] = self.players[player_id].copy()
        self.broadcast_lobby_update(lobby)
        self.send_lobby_data(lobby, player_id)

    def handle_join_lobby(self, message, addr):
        player_id = str(addr)
        lobby_id = message['lobby_id'].upper().strip()

        print(f"player {message['username']} joined lobby id: {lobby_id}")
        if player_id in self.waiting_players:
            return

        if not self.validate_username(message.get('username', '')):
            self.send_error(addr, "Invalid username")
            return

        if lobby_id not in self.lobbies:
            self.send_error(addr, "Lobby not found")
            return

        lobby = self.lobbies[lobby_id]
        if len(lobby.players) >= 2:
            self.send_error(addr, "Lobby is full")
            return

        lobby.players[player_id] = {
            'addr': addr,
            'username': message['username'],
            'ready': False,
            'last_active': time.time()
        }

        self.waiting_players[player_id] = lobby_id
        self.players[player_id] = lobby.players[player_id]
        self.broadcast_lobby_update(lobby)
        self.send_lobby_data(lobby, player_id)

    def handle_chat_message(self, message, addr):
        player_id = str(addr)
        if player_id not in self.waiting_players:
            print("not in waiting")
            return

        lobby_id = self.waiting_players[player_id]
        lobby = self.lobbies[lobby_id]
        text = message['text'][:100].strip()
        print(text)
        if not text:
            print("nottext")
            return

        chat_msg = {
            'player': self.players[player_id]['username'],
            'text': text,
            'timestamp': time.time()
        }

        lobby.chat_history.append(chat_msg)
        self.broadcast_chat_message(lobby, chat_msg)

    def handle_toggle_ready(self, message, addr):
        player_id = str(addr)
        if player_id not in self.waiting_players:
            return

        lobby_id = self.waiting_players[player_id]
        lobby = self.lobbies[lobby_id]

        lobby.players[player_id]['ready'] = not lobby.players[player_id]['ready']
        self.players[player_id]['ready'] = lobby.players[player_id]['ready']
        self.broadcast_lobby_update(lobby)

    def handle_start_game(self, message, addr):
        player_id = str(addr)
        if player_id not in self.waiting_players:
            return

        lobby_id = self.waiting_players[player_id]
        lobby = self.lobbies[lobby_id]

        if player_id == lobby.host and all(p['ready'] for p in lobby.players.values()):
            lobby.state = LobbyState.COUNTDOWN
            self.start_game_countdown(lobby)

    # Game management

    def initialize_game(self, lobby):
        lobby.state = LobbyState.IN_GAME
        self.game_states[lobby.id] = {
            'players': {},
            'level': 1
        }

        spawn_positions = [[271, 385], [716, 321]]
        player_index = 0

        # Assign spawn positions to each player by string ID
        for player_id, player in lobby.players.items():
            self.game_states[lobby.id]['players'][player_id] = {
                'position': spawn_positions[player_index],
                'velocity': [0, 0]
            }
            player_index += 1

        # Send spawn message to each player, using string IDs



        threading.Thread(target=self.game_loop, args=(lobby,), daemon=True).start()

    def game_loop(self, lobby):
        while self.running and lobby.id in self.game_states:
            with self.lock:
                # Broadcast updated positions
                for player_id, player_data in self.game_states[lobby.id]['players'].items():
                    for other_player in lobby.players.values():
                        self._send_json({
                            'type': 'player_position',
                            'id': player_id,
                            'position': player_data['position'],
                            'velocity': player_data['velocity']
                        }, other_player['addr'])

            # Loop at 20 updates per second
            time.sleep(0.01)

    def handle_player_input(self, message, addr):
        player_id = str(addr)
        if player_id not in self.players:
            return

        lobby_id = self.waiting_players.get(player_id)
        if not lobby_id or lobby_id not in self.game_states:
            return

        # Update player position and velocity
        if player_id in self.game_states[lobby_id]['players']:
            self.game_states[lobby_id]['players'][player_id]['position'] = message.get('position', [0, 0])
            self.game_states[lobby_id]['players'][player_id]['velocity'] = message.get('velocity', [0, 0])


    def handle_attack(self, message, addr):
        # Attack validation logic
        pass

    def handle_pause(self, message, addr):
        # Pause logic
        pass

    # Helper methods
    def validate_username(self, username):
        return 3 <= len(username) <= 16 and username.isalnum()

    def send_lobby_data(self, lobby, player_id):
        data = {
            'type': 'lobby_joined',
            'lobby_id': lobby.id,
            'host': lobby.host == player_id,
            'players': [{
                'username': p['username'],
                "ready": bool(p['ready']),
                "character": str(p.get('character', ''))
            } for p in lobby.players.values()],
            'chat_history': lobby.chat_history[-10:]
        }
        self._send_json(data, self.players[player_id]['addr'])

    def broadcast_lobby_update(self, lobby):
        data = {
            'type': 'lobby_update',
            'countdown': lobby.countdown,
            'players': [{
                'username': p['username'],
                'ready': p['ready'],
                'character': p.get('character')
            } for p in lobby.players.values()]
        }
        for player in lobby.players.values():
            self._send_json(data, player['addr'])

    def broadcast_chat_message(self, lobby, message):
        data = {
            'type': 'chat_message',
            'player': message['player'],
            'text': message['text'],
            'timestamp': message['timestamp']
        }
        for player in lobby.players.values():
            self._send_json(data, player['addr'])

    def handle_start_game(self, message, addr):
        player_id = str(addr)
        lobby_id = self.waiting_players.get(player_id)
        if not lobby_id: return

        lobby = self.lobbies[lobby_id]
        if player_id == lobby.host and len(lobby.players) == 2:
            if all(p['ready'] for p in lobby.players.values()):
                lobby.state = LobbyState.COUNTDOWN
                self.start_game_countdown(lobby)

    def start_game_countdown(self, lobby):
        def countdown_task():
            for i in range(2, 0, -1):
                with self.lock:
                    if lobby.state != LobbyState.COUNTDOWN:
                        return
                    lobby.countdown = i
                    self.broadcast_lobby_update(lobby)
                time.sleep(1)

            with self.lock:
                for player in lobby.players.values():
                    self._send_json({"type": "game"}, player['addr'])
                self.initialize_game(lobby)

        threading.Thread(target=countdown_task).start()







    def broadcast_game_state(self, lobby):
        game_state = self.game_states.get(lobby.id, {})
        data = {
            'type': 'game_update',
            'state': game_state
        }
        for player in lobby.players.values():
            self._send_json(data, player['addr'])

    # def cleanup_loop(self):
    #     while self.running:
    #         with self.lock:
    #             now = time.time()
    #             # Cleanup inactive lobbies
    #             for lobby_id in list(self.lobbies.keys()):
    #                 lobby = self.lobbies[lobby_id]
    #                 if now - lobby.created_at > 3600:  # 1 hour timeout
    #                     del self.lobbies[lobby_id]
    #
    #             # Cleanup inactive players
    #             for player_id in list(self.players.keys()):
    #                 last_active = self.players[player_id].get('last_active', 0)
    #                 if now - last_active > 30:  # 30s timeout
    #                     self.remove_player(player_id)
    #         time.sleep(10)

    # def remove_player(self, player_id):
    #     if player_id in self.waiting_players:
    #         lobby_id = self.waiting_players[player_id]
    #         if lobby_id in self.lobbies:
    #             lobby = self.lobbies[lobby_id]
    #             del lobby.players[player_id]
    #             if not lobby.players:
    #                 del self.lobbies[lobby_id]
    #             else:
    #                 self.broadcast_lobby_update(lobby)
    #         del self.waiting_players[player_id]
    #     if player_id in self.players:
    #         del self.players[player_id]

    def _send_json(self, data, addr):
        try:
            self.sock.sendto(json.dumps(data).encode('utf-8'), addr)
        except Exception as e:
            print(f"Send error: {e}")

    def send_error(self, addr, message):
        self._send_json({'type': 'error', 'message': message}, addr)

    def handle_unknown(self, message, addr):
        self.send_error(addr, "Unknown command")

    def stop(self):
        self.running = False
        self.sock.close()


if __name__ == "__main__":
    server = GameServer()
    try:
        server.start()
        while True: time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("Server stopped")
