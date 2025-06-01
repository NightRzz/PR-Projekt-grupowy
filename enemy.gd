extends CharacterBody2D

@export var patrol_distance := 120.0
@export var patrol_speed := 50.0
@export var chase_speed := 150.0
@export var is_owner := false
@export var enemy_id := ""
var current_health = 3
var is_dead = false
var left_bound : float
var right_bound : float
var patrol_direction := 1
var state = State.PATROL
var player : Node2D = null
var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")
@onready var anim = get_node("AnimationTree")
@onready var eye = $Eye
@onready var sword = $AnimatedSprite2D/Swing/SwingCol
@onready var CloseDistance = $CloseDistance
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

func update_enemy_state(new_health: int, new_anim_state: String) -> void:
	current_health = new_health
	if current_health <= 0:
		is_dead = true
	else:
		is_dead = false
	anim.get("parameters/playback").travel(new_anim_state)


func _physics_process(delta):
	if is_owner and not is_dead:
		if not ($RayCast2D.is_colliding() or $RayCast2D2.is_colliding()):
			velocity.y += gravity * delta
		else:
			velocity.y = 0
		if velocity.x < 0:
			anim.set("parameters/run/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/walk/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/idle/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/attack/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/hurt/BlendSpace2D/blend_position", Vector2(-1, 0))
			anim.set("parameters/dead/blend_position", Vector2(-1, 0))
		elif velocity.x > 0:
			anim.set("parameters/run/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/idle/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/walk/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/attack/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/hurt/BlendSpace2D/blend_position", Vector2(1, 0))
			anim.set("parameters/dead/BlendSpace2D/blend_position", Vector2(1, 0))
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
					if _see_player(CloseDistance):
						_attack_player()
						
				else:
					state = State.RETURN
					anim.get("parameters/playback").travel("run")
					anim_state = "run"
					if _see_player(CloseDistance):
						_attack_player()
					player = null
			State.RETURN:
				_return_to_start(delta)
		if velocity.x > 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = 37
			$AnimatedSprite2D/Swing/SwingCol.rotation = 41
			$Eye.target_position.x = 155
			$CloseDistance.target_position.x = 19
		elif velocity.x < 0:
			$AnimatedSprite2D/Swing/SwingCol.position.x = -37
			$AnimatedSprite2D/Swing/SwingCol.rotation = -41
			$CloseDistance.target_position.x = -21
			$Eye.target_position.x = -155
		last_dir = direction
		direction = "right" if velocity.x > 0 else ("left" if velocity.x < 0 else last_dir)

		var data = {
			"type": "enemy_status",
			"enemy_id": enemy_id,
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
		
		var collider = col.get_collider()
		if collider and collider.is_in_group("Player"):
			
			player = collider
			return true
	return false
func _attack_player():
	anim.get("parameters/playback").travel("attack")
	anim_state = "attack"

	
func _chase_player(delta):
	if player and player.is_inside_tree():
		var dir = sign(player.global_position.x - global_position.x)
		velocity.x = dir * chase_speed
		anim.get("parameters/playback").travel("run")
		anim_state = "run"
		move_and_slide()
	else:
		state = State.PATROL
		anim.get("parameters/playback").travel("walk")
		anim_state = "walk"
		player = null
		
func update_remote_transform(pos_x: float, pos_y: float, vel_x: float = 0, vel_y: float = 0, anim_state: String = "idle", direction: String = "right", current_health: int = 3):
	position = Vector2(pos_x, pos_y)
	velocity = Vector2(vel_x, vel_y)
	self.anim_state = anim_state
	self.current_health = current_health
	anim.get("parameters/playback").travel(anim_state)
	var blend = Vector2(1, 0) if direction == "right" else Vector2(-1, 0)
	anim.set("parameters/walk/BlendSpace2D/blend_position", blend)
	anim.set("parameters/run/BlendSpace2D/blend_position", blend)
	anim.set("parameters/idle/BlendSpace2D/blend_position", blend)
	anim.set("parameters/attack/BlendSpace2D/blend_position", blend)
	anim.set("parameters/hurt/BlendSpace2D/blend_position", blend)
	anim.set("parameters/dead/BlendSpace2D/blend_position", blend)
	if velocity.x > 0:
		$AnimatedSprite2D/Swing/SwingCol.position.x = 37
		$AnimatedSprite2D/Swing/SwingCol.rotation = 41
		$Eye.target_position.x = 155
		$CloseDistance.target_position.x = 19
	elif velocity.x < 0:
		$AnimatedSprite2D/Swing/SwingCol.position.x = -37
		$AnimatedSprite2D/Swing/SwingCol.rotation = -41
		$CloseDistance.target_position.x = -21
		$Eye.target_position.x = -155

func enemy_take_damage():
	if is_owner:
		current_health -= 1
		print("HURTTTTTTTTTTTTTTT")
		if current_health > 0:
			anim.get("parameters/playback").travel("hurt")
			anim_state = "hurt"
		else:
			print("Enemy died")
			current_health = 0
			$CollisionShape2D.set_deferred("disabled", true)
			anim.get("parameters/playback").travel("dead")
			anim_state = "dead"
			is_dead = true
		send_enemy_health_to_server()

func send_enemy_health_to_server():
	var data = {
		"type": "update_enemy_health",
		"enemy_id": enemy_id,
		"health": current_health
	}

	Global.udp.put_packet(JSON.stringify(data).to_utf8_buffer())

func _on_swing_body_entered(body: Node2D) -> void:
	if body is CharacterBody2D and body.has_method("take_damage"):
		body.isAttacked = true 
