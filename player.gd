extends CharacterBody2D
var game = true
var input_direction = Vector2.ZERO
var player_id: String = ""
var is_local_player := false
const SPEED = 300
@export var is_owner := false
const JUMP_VELOCITY = -400.0
var max_health := 3
var isAttacked := false
var points = 0
var current_health := max_health
var is_dead = false
var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")
@onready var anim = get_node("AnimationTree")
var anim_state = ""
var direction = ""
var last_dir = ""
var spectate_target = null


func _ready():
	$Camera2D.enabled = is_local_player
	add_to_group("Player")
	$Camera2D/GUI/EscPanel/VBoxContainer/Button.pressed.connect(on_exit)

func _process(delta):
	if is_local_player:
		var data = {
			"type": "player_input",
			"position": [position.x, position.y],
			"velocity": [velocity.x, velocity.y],
			"anim_state": anim_state,
			"direction": direction,
			"points": points
		}
		Global.udp.put_packet(JSON.stringify(data).to_utf8_buffer())
		if is_dead and is_local_player and spectate_target:
			$Camera2D.global_position = spectate_target.global_position
		get_node("Camera2D/GUI/Points").text = "Points: " + str(points)
		get_node("Camera2D/GUI/Health").text = "Life count: " + str(current_health)
		if isAttacked:
			take_damage(1)
			isAttacked = false


func _physics_process(delta):
	if is_local_player and is_dead == false and game:
		# Only get horizontal input
		var horizontal = Input.get_action_strength("right") - Input.get_action_strength("left")
		velocity.x = horizontal * SPEED

		if not ($RayCast2D.is_colliding() or $RayCast2D2.is_colliding()):
			velocity.y += gravity * delta
		else:
			velocity.y = 0
		
		if position.y>2000.0 and position.x < 9000.0:
			take_damage(1)
			
		if velocity.x < 0:
			anim.set("parameters/run/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/jump/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/idle/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/attack/BlendSpace2D/blend_position", Vector2(-1, 0))
		elif velocity.x > 0:
			anim.set("parameters/run/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/idle/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/jump/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/attack/BlendSpace2D/blend_position", Vector2(1, 0))

		if Input.is_action_just_pressed("up") and ($RayCast2D.is_colliding() or $RayCast2D2.is_colliding()):
			velocity.y = JUMP_VELOCITY
			anim.get("parameters/playback").travel("jump")
			anim_state = "jump"
		elif abs(velocity.x) > 10:
			anim.get("parameters/playback").travel("run")
			anim_state = "run"
		else:
			anim.get("parameters/playback").travel("idle")
			anim_state = "idle"
		if Input.is_action_just_pressed("attack"):
			anim.get("parameters/playback").travel("attack")
			anim_state = "attack"
		if Input.is_action_just_pressed("esc"):
			if $Camera2D/GUI/EscPanel.visible:
				$Camera2D/GUI/EscPanel.visible = false
			else:
				$Camera2D/GUI/EscPanel.visible = true
		last_dir = direction
		direction = "right" if velocity.x > 0 else ("left" if velocity.x < 0 else last_dir)
		var col_pos = 40 if process_priority == 1 else 32
		if velocity.x > 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = col_pos
		elif velocity.x < 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = -col_pos
		move_and_slide()

func update_remote_transform(pos_x: float, pos_y: float, vel_x: float = 0, vel_y: float = 0, anim_state: String = "idle", direction: String = "right"):
	if !is_local_player:
		position = Vector2(pos_x, pos_y)
		velocity = Vector2(vel_x, vel_y)
		anim.get("parameters/playback").travel(anim_state)
		var blend = Vector2(1, 0) if direction == "right" else Vector2(-1, 0)
		anim.set("parameters/%s/BlendSpace2D/blend_position" % anim_state, blend)
		var col_pos = 40 if process_priority == 1 else 32
		if velocity.x > 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = col_pos
		elif velocity.x < 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = -col_pos

	
func take_damage(amount: int):
	current_health -= amount
	if current_health > 0:
		velocity.y = 0
		position.y = -300.0
		position.x = 200.0
		if points>500:
			points -=500
		else:
			points = 0
	else:
		print("Player died")
		position.x = -100000
		var players = get_tree().get_nodes_in_group("Player")
		for p in players:
			if p != self:
				spectate_target = p
				break
		current_health = 0
		is_dead = true
		get_node("Camera2D/GUI/DeadInfo").text = "You are dead!"
		get_node("Camera2D/GUI/PointsFinal").text = "Colleted points: " + str(points)
		get_node("Camera2D/GUI/DeadGraphic").visible = true
	send_stats_to_server()

func _on_swing_body_entered(body: Node2D) -> void:
	if body is CharacterBody2D and body.has_method("enemy_take_damage") and not body.is_dead:
		points += 750
		body.enemy_take_damage() 
		send_stats_to_server()


func send_stats_to_server():
	var data = {
		"type": "update_stats",
		"health": current_health,
		"points": points
	}
	Global.udp.put_packet(JSON.stringify(data).to_utf8_buffer())


func on_exit() -> void:
	get_tree().change_scene_to_file("res://lobby.tscn")
