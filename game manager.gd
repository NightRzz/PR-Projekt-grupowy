extends Node2D

var players = {}
var local_player_id = 0
var player_scene = preload("res://player.tscn")

func _ready():
	# Setup timer to receive UDP packets
	await get_tree().create_timer(0.2).timeout
	var timer = Timer.new()
	add_child(timer)
	timer.wait_time = 0.009  # 100 times per second
	timer.timeout.connect(_process_packets)
	timer.start()
	
	# Tell server we're ready for game start
	var data = {"type": "player_ready"}
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
			_spawn_player(data.id, data.position, data.is_local, data.username)
		"player_position":
			_update_player_position(data.id, data.position, data.velocity, data.anim_state, data.direction)

func _update_game_state(state):
	# Update general game state here
	pass

func _spawn_player(id: String, position: Array, is_local: bool, nickname: String):
	if players.has(id):
		return
	var player = player_scene.instantiate()
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
