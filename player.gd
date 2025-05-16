extends CharacterBody2D

var input_direction = Vector2.ZERO
var player_id: String = ""
var is_local_player := false
const SPEED = 300
const JUMP_VELOCITY = -400.0
var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")

func _ready():
	$Camera2D.enabled = is_local_player

func _process(delta):
	if is_local_player:
		var data = {
			"type": "player_input",
			"position": [position.x, position.y],
			"velocity": [velocity.x, velocity.y]
		}
		Global.udp.put_packet(JSON.stringify(data).to_utf8_buffer())

func _physics_process(delta):
	if is_local_player:
		# Only get horizontal input
		var horizontal = Input.get_action_strength("ui_right") - Input.get_action_strength("ui_left")
		velocity.x = horizontal * SPEED

		# Apply gravity
		if not ($RayCast2D.is_colliding() or $RayCast2D2.is_colliding()):
			velocity.y += gravity * delta
		else:
			velocity.y = 0

		# Jump (use "jump" action, not "ui_up")
		if Input.is_action_just_pressed("ui_up") and ($RayCast2D.is_colliding() or $RayCast2D2.is_colliding()):
			velocity.y = JUMP_VELOCITY

		move_and_slide()

func update_remote_transform(pos_x: float, pos_y: float, vel_x: float = 0, vel_y: float = 0):
	if !is_local_player:
		position = Vector2(pos_x, pos_y)
		velocity = Vector2(vel_x, vel_y)
