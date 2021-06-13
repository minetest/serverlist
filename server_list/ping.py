import asyncio
import time
import random
import socket

from .app import app
from .util import get_addr_info


class MinetestProtocol:
	def connection_made(self, transport):
		self.transport = transport

	def send_original(self):
		# Send packet of type ORIGINAL, with no data.
		# This should prompt the server to assign us a peer id.
		# [0] u32       protocol_id (PROTOCOL_ID)
		# [4] session_t sender_peer_id (PEER_ID_INEXISTENT)
		# [6] u8        channel
		# [7] u8        type (PACKET_TYPE_ORIGINAL)
		self.transport.sendto(b"\x4f\x45\x74\x03\x00\x00\x00\x01")

		self.start = time.time()

	def datagram_received(self, data, addr):
		end = time.time()

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
		self.transport.sendto(b"\x4f\x45\x74\x03" + peer_id + b"\x00\x00\x03", addr)

		self.future.set_result(end - self.start)
		self.transport.close()

	def connection_lost(self, exc):
		if not self.future.done():
			self.future.set_result(None)

	def error_received(self, exc):
		self.future.set_result(None)


async def ping_server_async(address, sock=None):
	loop = asyncio.get_event_loop()
	future = loop.create_future()
	transport, protocol = await loop.create_datagram_endpoint(
			MinetestProtocol,
			remote_addr=address,
			sock=sock)
	attempts = 0
	pings = []
	while len(pings) < 3 and attempts - len(pings) < 3:
		attempts += 1
		protocol.future = future
		try:
			# Sleep a bit to spread requests out
			await asyncio.sleep(random.random())
			protocol.send_original()
			ping = await asyncio.wait_for(asyncio.shield(future), 2)
			if ping is not None:
				pings.append(ping)
			future = loop.create_future()
		except asyncio.TimeoutError:
			pass

	if len(pings) != 0:
		return min(pings)

	return None


async def ping_servers_async(addresses):
	return await asyncio.gather(*[ping_server(a) for a in addresses])


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
	# Send packet of type ORIGINAL, with no data.
	# This should prompt the server to assign us a peer id.
	# [0] u32       protocol_id (PROTOCOL_ID)
	# [4] session_t sender_peer_id (PEER_ID_INEXISTENT)
	# [6] u8        channel
	# [7] u8        type (PACKET_TYPE_ORIGINAL)
	sock.send(b"\x4f\x45\x74\x03\x00\x00\x00\x01")

	# Receive reliable packet of type CONTROL, subtype SET_PEER_ID,
	# with our assigned peer id as data.
	start = time.time()
	data = sock.recv(1024)
	end = time.time()

	if not data:
		return None

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
	sock.send(b"\x4f\x45\x74\x03" + peer_id + b"\x00\x00\x03")

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
