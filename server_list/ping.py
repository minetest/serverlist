import time
import socket

from .app import app
from .util import get_addr_info


# Initial packet of type ORIGINAL, with no data.
# This should prompt the server to assign us a peer id.
# [0] u32       protocol_id (PROTOCOL_ID)
# [4] session_t sender_peer_id (PEER_ID_INEXISTENT)
# [6] u8        channel
# [7] u8        type (PACKET_TYPE_ORIGINAL)
PING_PACKET = b"\x4f\x45\x74\x03\x00\x00\x00\x01"


def get_ping_reply(data):
	# [0] u32        protocol_id (PROTOCOL_ID)
	# [4] session_t  sender_peer_id
	# [6] u8         channel
	# [7] u8         type (PACKET_TYPE_RELIABLE)
	# [8] u16        sequence number
	# [10] u8        type (PACKET_TYPE_CONTROL)
	# [11] u8        controltype (CONTROLTYPE_SET_PEER_ID)
	# [12] session_t peer_id_new
	peer_id = data[12:14]

	# Send packet of type CONTROL, subtype DISCO,
	# to cleanly close our server connection.
	# [0] u32       protocol_id (PROTOCOL_ID)
	# [4] session_t sender_peer_id
	# [6] u8        channel
	# [7] u8        type (PACKET_TYPE_CONTROL)
	# [8] u8        controltype (CONTROLTYPE_DISCO)
	return b"\x4f\x45\x74\x03" + peer_id + b"\x00\x00\x03"


def ping_server_addresses(address, port):
	pings = []
	addr_info = get_addr_info(address, port)
	for record in addr_info:
		ping = server_up(record)
		if not ping:
			app.logger.warning("Could not connect to %s:%d using resolved info %r.",
					address, port, record)
			return None
		pings.append(ping)
	return pings


def ping_server(sock):
	sock.send(PING_PACKET)

	# Receive reliable packet of type CONTROL, subtype SET_PEER_ID,
	# with our assigned peer id as data.
	start = time.time()
	data = sock.recv(1024)
	end = time.time()

	if not data:
		return None

	sock.send(get_ping_reply(data))
	return end - start


# Returns ping time in seconds (up) or None (down).
def server_up(info):
	"""Pings a Minetest server to check if it is online.
	"""
	try:
		sock = socket.socket(info[0], info[1], info[2])
		sock.settimeout(2)
		sock.connect(info[4])
	except OSError:
		return None

	attempts = 0
	pings = []
	while len(pings) < 3 and attempts - len(pings) < 3:
		attempts += 1
		try:
			ping = ping_server(sock)
			if ping is not None:
				pings.append(ping)
		except socket.timeout:
			pass
		except ConnectionRefusedError:
			return None
		except OSError:
			return None

	sock.close()

	if len(pings) != 0:
		return min(pings)

	return None
