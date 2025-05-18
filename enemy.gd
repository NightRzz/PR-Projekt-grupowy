extends CharacterBody2D

@export var patrol_distance := 120.0
@export var patrol_speed := 50.0
@export var chase_speed := 150.0
@export var is_owner := false
var left_bound : float
var right_bound : float
var patrol_direction := 1
var state = State.PATROL
var player : Node2D = null
var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")
@onready var anim = get_node("AnimationTree")
@onready var eye = $Eye
@onready var sword = $AnimatedSprite2D/Swing/SwingCol
var anim_state = "walk"
var direction = ""
var last_dir = ""
var current_state = State.PATROL
var initial_position: Vector2

enum State {
	PATROL,
	CHASE,
	RETURN
}

func _ready():
	initial_position = position 
	left_bound = position.x - patrol_distance
	right_bound = position.x + patrol_distance
	patrol_direction = 1
	state = State.PATROL
	anim.get("parameters/playback").travel("walk")
	anim_state = "walk"

func _physics_process(delta):
	if is_owner:
		if not ($RayCast2D.is_colliding() or $RayCast2D2.is_colliding()):
			velocity.y += gravity * delta
		else:
			velocity.y = 0
		if velocity.x < 0:
			anim.set("parameters/run/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/walk/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/idle/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/attack/BlendSpace2D/blend_position", Vector2(-1, 0))
		elif velocity.x > 0:
			anim.set("parameters/run/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/idle/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/walk/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/attack/BlendSpace2D/blend_position", Vector2(1, 0))
		match state:
			State.PATROL:
				anim.get("parameters/playback").travel("walk")
				anim_state = "walk"
				_patrol(delta)
				if _see_player(eye):
					state = State.CHASE
					anim.get("parameters/playback").travel("run")
					anim_state = "run"
			State.CHASE:
				if _see_player(eye):
					_chase_player(delta)
				else:
					state = State.RETURN
					anim.get("parameters/playback").travel("run")
					anim_state = "run"
					player = null
			State.RETURN:
				_return_to_start(delta)
		if velocity.x > 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = 37
			$AnimatedSprite2D/Swing/SwingCol.rotation = 41
			$Eye.target_position.x = 155
		elif velocity.x < 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = -37
			$AnimatedSprite2D/Swing/SwingCol.rotation = -41
			$Eye.target_position.x = -155
		last_dir = direction
		direction = "right" if velocity.x > 0 else ("left" if velocity.x < 0 else last_dir)
		# Send enemy state to clients
		var data = {
			"type": "enemy_status",
			"position": [position.x, position.y],
			"velocity": [velocity.x, velocity.y],
			"anim_state": anim_state,
			"direction": direction
		}
		Global.udp.put_packet(JSON.stringify(data).to_utf8_buffer())

func _return_to_start(delta):
	var return_speed = patrol_speed * 1.5  # Faster return speed
	var direction = sign(initial_position.x - position.x)
	velocity.x = direction * return_speed
	move_and_slide()
	
	# When close to initial position, resume patrol
	if abs(position.x - initial_position.x) < 5:
		position.x = initial_position.x  # Snap to exact position
		patrol_direction = 1 if randf() > 0.5 else -1  # Randomize new patrol direction
		state = State.PATROL

func _patrol(delta):
	velocity.x = patrol_direction * patrol_speed
	
	position.x += velocity.x * delta
	if position.x < left_bound:
		position.x = left_bound
		patrol_direction = 1
	elif position.x > right_bound:
		position.x = right_bound
		patrol_direction = -1
	move_and_slide()

func _see_player(col) -> bool:
	if col.is_colliding():
		print("collide")
		var collider = col.get_collider()
		if collider and collider.is_in_group("Player"):
			print("group")
			player = collider
			return true
	return false

func _chase_player(delta):
	if player and player.is_inside_tree():
		var dir = sign(player.global_position.x - global_position.x)
		velocity.x = dir * chase_speed
		
		move_and_slide()
	else:
		state = State.PATROL
		anim.get("parameters/playback").travel("walk")
		player = null
		
func update_remote_transform(pos_x: float, pos_y: float, vel_x: float = 0, vel_y: float = 0, anim_state: String = "idle", direction: String = "right"):
	position = Vector2(pos_x, pos_y)
	velocity = Vector2(vel_x, vel_y)
	self.anim_state = anim_state
	anim.get("parameters/playback").travel(anim_state)
	var blend = Vector2(1, 0) if direction == "right" else Vector2(-1, 0)
	anim.set("parameters/walk/BlendSpace2D/blend_position", blend)
	anim.set("parameters/run/BlendSpace2D/blend_position", blend)
	anim.set("parameters/idle/BlendSpace2D/blend_position", blend)
	anim.set("parameters/attack/BlendSpace2D/blend_position", blend)
