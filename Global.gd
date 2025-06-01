extends Node
var udp := PacketPeerUDP.new()
var server_ip := "127.0.0.1"
var server_port := 9999
var lobby_id := ""
var username := ""
var is_host := false
var players := []

func join_server():
	udp.connect_to_host(server_ip, server_port)

func _exit_tree():
	udp.close()
