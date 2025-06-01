extends Node2D

var players = {}
var local_player_id = 0
var character_scenes = {
	"magician": preload("res://player.tscn"),
	"warrior": preload("res://player2.tscn")
}
var selected_character = "warrior" 

var enemies = {}
			
var enemy_scene = preload("res://enemy.tscn") 

func _ready():
	# Setup timer to receive UDP packets
	await get_tree().create_timer(0.1).timeout
	var timer = Timer.new()
	add_child(timer)
	timer.wait_time = 0.006  # 100 times per second
	timer.timeout.connect(_process_packets)
	timer.start()
	
	# Tell server we're ready for game start
	var data = {"type": "player_ready"}
	Global.udp.put_packet(JSON.stringify(data).to_utf8_buffer())

func _input(event):
	if event.is_action_pressed("select_character_1"):
		selected_character = "magician"
		_send_character_selection()
	elif event.is_action_pressed("select_character_2"):
		selected_character = "warrior"
		_send_character_selection()
		
func _send_character_selection():
	var data = {"type": "character_select", "character": selected_character}
	Global.udp.put_packet(JSON.stringify(data).to_utf8_buffer())

func _process_packets():
	while Global.udp.get_available_packet_count() > 0:
		var packet = Global.udp.get_packet().get_string_from_utf8()
		var data = JSON.parse_string(packet)
		_handle_server_message(data)

func _handle_server_message(data):
	match data.type:
		"game_update":
			_update_game_state(data.state)
		"spawn_player":
			_spawn_player(data.id, data.position, data.is_local, data.username, data.character)
		"player_position":
			_update_player_position(data.id, data.position, data.velocity, data.anim_state, data.direction)
		"character_changed":
			_update_player_character(data.id, data.character)
		"spawn_enemy":
			_spawn_enemy(data.enemy_id, data.is_host ,data.position, data.character)
		"enemy_sync":
			_sync_enemies(data.enemies)
		"player_health":
			_update_player_health(data.id, data.health)

func _update_player_health(id: String, health: int) -> void:
	if has_node("Players/" + id):
		var other_player = get_node("Players/" + id)
		other_player.current_health = health
		if health <= 0:
			other_player.die()

			
func _spawn_enemy(eid: String,is_host: bool, pos: Array, character: String):
	if character == "Skeleton":
		var enemy_scene = preload("res://enemy.tscn") 
	var enemy = enemy_scene.instantiate()
	enemy.position.x = pos[0]
	enemy.position.y = pos[1]
	enemy.enemy_id = eid
	enemy.is_owner = is_host
	
	$Enemies.add_child(enemy)
	enemy.get_node("AnimatedSprite2D").animation = "walk"
	enemy.anim_state = "walk"
	enemy.anim.get("parameters/playback").travel("walk")
	enemies[eid] = enemy
		
func _sync_enemies(enemy_states):
	for eid in enemy_states:
		var e = enemy_states[eid]
		if enemies.has(eid) and not enemies[eid].is_owner:
			
			enemies[eid].update_remote_transform(
				e.position[0], e.position[1],
				e.velocity[0], e.velocity[1],
				e.anim_state, e.direction
			)
func _update_player_character(id: String, character: String):
	if not players.has(id):
		return
	var old_player = players[id]
	var pos = old_player.position
	1
	var is_local = old_player.is_local_player
	var nickname = ""
	if old_player.has_node("Nickname"):
		nickname = old_player.get_node("Nickname").text
	old_player.queue_free()
	players.erase(id)
	# Instantiate new character scene
	var scene = character_scenes.get(character, character_scenes["warrior"])
	var player = scene.instantiate()
	player.position = pos
	player.player_id = id
	player.is_local_player = is_local
	if !is_local and player.has_node("Nickname"):
		player.get_node("Nickname").text = nickname
	if is_local:
		local_player_id = id
	$Players.add_child(player)
	players[id] = player

func _update_game_state(state):
	# Update general game state here
	pass

func _spawn_player(id: String, position: Array, is_local: bool, nickname: String, character: String = "magician"):
	if players.has(id):
		return
	var scene = character_scenes.get(character, character_scenes["warrior"])
	var player = scene.instantiate()
	
	player.position = Vector2(position[0], position[1])
	player.player_id = id  # Now string
	player.is_local_player = is_local
	if !is_local:
		player.get_node("Nickname").text = nickname
	if is_local:
		local_player_id = id
	$Players.add_child(player)
	players[id] = player

func _update_player_position(id, position, velocity, anim_state, direction):
	if players.has(id) and id != local_player_id:
		players[id].update_remote_transform(
			position[0], position[1], 
			velocity[0], velocity[1],
			anim_state, direction
		)
