extends CanvasLayer


func _ready():
	$Panel.visible = true
	$Panel/VBoxContainer/ChatInput.max_length = 100
	
	$Panel/VBoxContainer/SendButton.pressed.connect(_send_chat_message)
	$Panel/VBoxContainer/ChatInput.text_submitted.connect(func(_t): _send_chat_message())
	$Panel/VBoxContainer/HBoxContainer/VBoxContainer/ReadyButton.pressed.connect(_toggle_ready)
	$Panel/VBoxContainer/HBoxContainer/VBoxContainer/StartGameButton.pressed.connect(_start_game)
	
	_update_lobby_ui()
	
	# Timer do odbierania pakietów
	var timer = Timer.new()
	add_child(timer)
	timer.wait_time = 0.1
	timer.timeout.connect(_process_packets)
	timer.start()

func _process_packets():
	while Global.udp.get_available_packet_count() > 0:
		var packet = Global.udp.get_packet().get_string_from_utf8()
		var data = JSON.parse_string(packet)
		_handle_server_message(data)

func _handle_server_message(data: Dictionary):
	match data.type:
		"lobby_joined":
			Global.lobby_id = data.lobby_id
			Global.is_host = data.host
			Global.players = data.players
			_update_lobby_ui()
		
		"lobby_update":
			Global.players = data.players
			_update_lobby_ui()
			
			if data.get("countdown", 0) > 0:
				$Panel/VBoxContainer/LobbyIDLabel.text += " | Start za: %d" % data.countdown
		
		"chat_message":
			_add_chat_message(data.player, data.text)
		
		"error":
			print("Error: ", data.message)
				

func _update_lobby_ui():
	$Panel/VBoxContainer/LobbyIDLabel.text = "Lobby ID: %s" % Global.lobby_id
	$Panel/VBoxContainer/HBoxContainer/PlayerList.clear()
	
	for player in Global.players:
		var text = "%s [%s]" % [player["username"], "READY" if player["ready"] else "NOT READY"]
		$Panel/VBoxContainer/HBoxContainer/PlayerList.add_item(text)
	
	$Panel/VBoxContainer/HBoxContainer/VBoxContainer/StartGameButton.visible = Global.is_host

func _add_chat_message(player: String, text: String):
	var time = Time.get_time_string_from_system()
	$Panel/VBoxContainer/ChatLog.append_text("[%s] %s: %s\n" % [time, player, text])

func _send_chat_message():
	var text = $Panel/VBoxContainer/ChatInput.text.strip_edges()
	if text == "":
		return
	
	var message = {
		"type": "chat_message",
		"text": text
	}
	Global.udp.put_packet(JSON.stringify(message).to_utf8_buffer())
	$Panel/VBoxContainer/ChatInput.clear()

func _toggle_ready():
	var message = {
		"type": "toggle_ready"
	}
	Global.udp.put_packet(JSON.stringify(message).to_utf8_buffer())

func _start_game():
	var message = {
		"type": "start_game"
	}
	Global.udp.put_packet(JSON.stringify(message).to_utf8_buffer())
