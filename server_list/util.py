import re
import socket
import time

from datetime import datetime, timedelta

from .app import app

try:
	import maxminddb
	MAXMIND_DB = app.config.get("MAXMIND_DB", None)
	if MAXMIND_DB is not None:
		geoip_reader = maxminddb.open_database(MAXMIND_DB, maxminddb.MODE_AUTO)
	else:
		app.logger.warning(
			"For working GeoIP download the database from "
			"https://db-ip.com/db/download/ip-to-country-lite and point "
			"the MAXMIND_DB setting to the .mmdb file."
		)
		geoip_reader = None
except ImportError:
	app.logger.warning("maxminddb not available, GeoIP will not work.")


UUID_RE = re.compile('^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def check_ban(announce_ip, address, port):
	if "%s/%d" % (announce_ip, port) in app.config["BANNED_SERVERS"]:
		return True

	if address != announce_ip:
		# Normalize address for ban checks
		address = address.lower().rstrip(".")
		if f"{address}/{port}" in app.config["BANNED_SERVERS"] or \
				address in app.config["BANNED_SERVERS"]:
			return True

	return False


def get_addr_info(address, port):
	try:
		return socket.getaddrinfo(
			address,
			port,
			type=socket.SOCK_DGRAM,
			proto=socket.SOL_UDP)
	except socket.gaierror:
		app.logger.warning("Unable to get address info for [%s]:%d.",
			address, port)
		return None


def verify_announce(addr_info, address, announce_ip):
	if address == announce_ip:
		return True

	addresses = set(data[4][0] for data in addr_info)
	if not announce_ip in addresses:
		app.logger.warning(
			"Server address %r does not resolve to announce IP %r (address valid for %r).",
			address, announce_ip, addresses)
		return False

	return True


def get_geo_continent(ip):
	if ip.startswith("::ffff:"):
		ip = ip[7:]

	if reader is None:
		return

	try:
		geo = geoip_reader.get(ip)
	except ValueError:
		return

	if geo and "continent" in geo:
		return geo["continent"]["code"]
	else:
		app.logger.warning("Unable to get GeoIP Continent data for %s.", ip)
		return None


# fieldName: (Required, Type, SubType)
fields = {
	"action": (True, "str"),

	"world_uuid": (False, "str"),

	"address": (False, "str"),
	"port": (False, "int"),

	"clients_max": (True, "int"),
	"uptime": (True, "int"),
	"game_time": (True, "int"),
	"lag": (False, "float"),

	"clients_list": (True, "list", "str"),
	"mods": (False, "list", "str"),

	"version": (True, "str"),
	"proto_min": (True, "int"),
	"proto_max": (True, "int"),

	"gameid": (True, "str"),
	"mapgen": (False, "str"),
	"url": (False, "str"),
	"privs": (False, "str"),
	"name": (True, "str"),
	"description": (True, "str"),

	# Flags
	"creative": (False, "bool"),
	"dedicated": (False, "bool"),
	"damage": (False, "bool"),
	"pvp": (False, "bool"),
	"password": (False, "bool"),
	"rollback": (False, "bool"),
	"can_see_far_names": (False, "bool"),
}

def check_request_json(obj):
	"""Checks the types and values of fields in the request.

	Returns error string or None.
	"""
	for name, data in fields.items():
		# Delete optional string fields sent as empty strings
		if not data[0] and data[1] == "str" and obj.get(name) == "":
			del obj[name]

		if not name in obj:
			if data[0]:
				return f"Required field '{name}' is missing."
			continue

		type_str = type(obj[name]).__name__
		if type_str != data[1]:
			return f"Field '{name}'' has incorrect type (expected {data[1]} found {type_str})."


		if len(data) >= 3:
			for item in obj[name]:
				subtype_str = type(item).__name__
				if subtype_str != data[2]:
					return f"Entry in field '{name}' has incorrect type (expected {data[2]} found {subtype_str})."

	if "url" in obj:
		url = obj["url"]
		if not any(url.startswith(p) for p in ["http://", "https://", "//"]):
			return "Field 'url' does not match expected format."

	if "world_uuid" in obj and not UUID_RE.match(obj["world_uuid"]):
		return "Field 'world_uuid' does not match expected format."

	return None


def server_ranking(server):
	now = datetime.utcnow()
	points = 0

	clients = server.clients.split('\n')

	# 1 per client, capped to CLIENT_LIMIT or clients_max * 0.9
	cap = min(server.clients_max * 0.9, app.config["CLIENT_LIMIT"])
	points += min(len(clients), cap)

	# 1/2 per week of age, limited to 8
	points += min(8, (now - server.first_seen) / timedelta(weeks=2))

	# 1/2 per average client, limited to 4
	points += min(4, server.popularity / 2)

	# -8 per second of ping over 0.3s
	if server.ping > 0.3:
		points -= (server.ping - 0.3) * 8

	# Up to -4 for less than an hour of uptime (penalty linearly decreasing)
	ONE_HOUR = timedelta(hours=1)
	uptime = now - server.start_time
	if uptime < ONE_HOUR:
		# Only apply penalty if the server was down for more than an hour
		down_too_long = True
		if server.down_time is not None:
			down_too_long = (server.start_time - server.down_time) > ONE_HOUR

		if down_too_long:
			points -= ((ONE_HOUR - uptime) / ONE_HOUR) * 4

	# Reduction to 40% for servers that support both legacy (v4) and v5 clients
	if server.proto_min <= 32 and server.proto_max > 36:
		points *= 0.4

	return points
