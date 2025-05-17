extends Control

@onready var create_button = $CanvasLayer/Panel/VBoxContainer/CreateLobbyButton
@onready var join_button = $CanvasLayer/Panel/VBoxContainer/JoinLobbyButton
@onready var lobby_label = $CanvasLayer/Panel/VBoxContainer/LobbyLabel
var notalobby = false
var waiting = false
func _ready():
	create_button.pressed.connect(_on_create_lobby)
	join_button.pressed.connect(_on_join_lobby)

	var timer = Timer.new()
	add_child(timer)
	timer.wait_time = 0.1
	timer.timeout.connect(_process_packets)
	timer.start()
	Global.udp.connect_to_host(Global.server_ip, Global.server_port)
func _process_packets():
	while Global.udp.get_available_packet_count() > 0:
		var packet = Global.udp.get_packet().get_string_from_utf8()
		var data = JSON.parse_string(packet)
		if data.status == "found":
			notalobby = false
			if waiting:
				waiting = false
				var message = {
					"type": "join_lobby",
					"lobby_id": Global.lobby_id,
					"username": Global.username
				}
				get_tree().change_scene_to_file("res://lobby.tscn")
				Global.udp.put_packet(JSON.stringify(message).to_utf8_buffer())
				
		elif data.status == "not found":
			notalobby = true
			if waiting:
				waiting = false
				lobby_label.text = "There is no lobby with provided id or it is full"

func _on_create_lobby():
	Global.username = $CanvasLayer/Panel/VBoxContainer/UsernameInput.text.strip_edges()
	if !_validate_username(Global.username):
		return
	
	Global.udp.connect_to_host(Global.server_ip, Global.server_port)
	var message = {
		"type": "create_lobby",
		"username": Global.username
	}
	Global.udp.put_packet(JSON.stringify(message).to_utf8_buffer())
	
	get_tree().change_scene_to_file("res://lobby.tscn")

func _on_join_lobby():
	Global.lobby_id = $CanvasLayer/Panel/VBoxContainer/LobbyCodeInput.text.strip_edges().to_upper()
	Global.username = $CanvasLayer/Panel/VBoxContainer/UsernameInput.text.strip_edges()
	
	if !_validate_username(Global.username) || Global.lobby_id.length() != 4:
		return
	
	Global.udp.connect_to_host(Global.server_ip, Global.server_port)
	var message = {
		"type": "find_lobby",
		"lobby_id": Global.lobby_id,
	}
	Global.udp.put_packet(JSON.stringify(message).to_utf8_buffer())
	waiting = true




func _validate_username(name: String) -> bool:
	return name.length() >= 3 && name.length() <= 16
