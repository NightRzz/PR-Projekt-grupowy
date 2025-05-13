extends Node

var peer = ENetMultiplayerPeer.new()
var udp := PacketPeerUDP.new()
var server_ip := "127.0.0.1"
var server_port := 9999
var lobby_id := ""
var username := ""
var is_host := false
var players := []

func create_server(port: int):
	peer.create_server(port)
	multiplayer.multiplayer_peer = peer
	peer.host.compress(ENetConnection.COMPRESS_RANGE_CODER)  # Kompresja
	print("Server created on port ", port)

func join_server(ip: String, port: int):
	peer.create_client(ip, port)
	multiplayer.multiplayer_peer = peer
	peer.host.compress(ENetConnection.COMPRESS_RANGE_CODER)
	print("Connecting to ", ip, ":", port)
