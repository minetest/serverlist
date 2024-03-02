#!/usr/bin/env python3
import os, sys, json, time, socket
from threading import Thread, RLock
from glob import glob

import maxminddb
from flask import Flask, request, send_from_directory, make_response


app = Flask(__name__, static_url_path = "")

# Load configuration
app.config.from_pyfile("config-example.py")  # Use example for defaults
if os.path.isfile(os.path.join(app.root_path, "config.py")):
        app.config.from_pyfile("config.py")

tmp = glob(os.path.join(app.root_path, "dbip-country-lite-*.mmdb"))
if tmp:
	reader = maxminddb.open_database(tmp[0], maxminddb.MODE_AUTO)
else:
	app.logger.warning(
		"For working GeoIP download the database from "+
		"https://db-ip.com/db/download/ip-to-country-lite and place the "+
		".mmdb file in the app root folder."
	)
	reader = None

# Helpers

def geoip_lookup_continent(ip):
	if ip.startswith("::ffff:"):
		ip = ip[7:]

	if not reader:
		return
	geo = reader.get(ip)

	if geo and "continent" in geo:
		return geo["continent"]["code"]
	else:
		app.logger.warning("Unable to get GeoIP continent data for %s.", ip)

# Views

@app.route("/")
def index():
	return app.send_static_file("index.html")


@app.route("/list")
def list():
	# We have to make sure that the list isn't cached,
	# since the list isn't really static.
	return send_from_directory(app.static_folder, "list.json", max_age=0)


@app.route("/geoip")
def geoip():
	continent = geoip_lookup_continent(request.remote_addr)

	resp = make_response({
		"continent": continent, # null on error
	})
	resp.cache_control.max_age = 7 * 86400
	resp.cache_control.private = True

	return resp


@app.route("/announce", methods=["GET", "POST"])
def announce():
	ip = request.remote_addr
	if ip.startswith("::ffff:"):
		ip = ip[7:]

	if ip in app.config["BANNED_IPS"]:
		return "Banned (IP).", 403

	data = request.values["json"]

	if len(data) > 8192:
		return "JSON data is too big.", 413

	try:
		server = json.loads(data)
	except:
		return "Unable to process JSON data.", 400

	if type(server) != dict:
		return "JSON data is not an object.", 400

	if not "action" in server:
		return "Missing action field.", 400

	action = server["action"]
	if action not in ("start", "update", "delete"):
		return "Invalid action field.", 400

	if action == "start":
		server["uptime"] = 0

	server["ip"] = ip

	if not "port" in server:
		server["port"] = 30000
	#### Compatability code ####
	# port was sent as a string instead of an integer
	elif type(server["port"]) == str:
		server["port"] = int(server["port"])
	#### End compatability code ####

	if "%s/%d" % (server["ip"], server["port"]) in app.config["BANNED_SERVERS"]:
		return "Banned (Server).", 403
	elif "address" in server and "%s/%d" % (server["address"].lower(), server["port"]) in app.config["BANNED_SERVERS"]:
		return "Banned (Server).", 403
	elif "address" in server and server["address"].lower() in app.config["BANNED_SERVERS"]:
		return "Banned (Server).", 403

	old = serverList.get(ip, server["port"])

	if action == "delete":
		if not old:
			return "Server not found."
		serverList.remove(old)
		serverList.save()
		return "Removed from server list."
	elif not checkRequest(server):
		return "Invalid JSON data.", 400

	if action == "update" and not old:
		if app.config["ALLOW_UPDATE_WITHOUT_OLD"]:
			action = "start"
		else:
			return "Server to update not found."

	server["update_time"] = int(time.time())

	if action == "start":
		server["start"] = int(time.time())
		tracker.push("%s:%d" % (server["ip"], server["port"]), server["start"])
	else:
		server["start"] = old["start"]

	if "clients_list" in server:
		server["clients"] = len(server["clients_list"])

	server["clients_top"] = max(server["clients"], old["clients_top"]) if old else server["clients"]

	if "url" in server:
		url = server["url"]
		if not any(url.startswith(p) for p in ["http://", "https://", "//"]):
			del server["url"]

	# Make sure that startup options are saved
	if action == "update":
		for field in ("dedicated", "rollback", "mapgen", "privs",
				"can_see_far_names", "mods"):
			if field in old:
				server[field] = old[field]

	# Popularity
	if old:
		server["updates"] = old["updates"] + 1
		# This is actually a count of all the client numbers we've received,
		# it includes clients that were on in the previous update.
		server["total_clients"] = old["total_clients"] + server["clients"]
	else:
		server["updates"] = 1
		server["total_clients"] = server["clients"]
	server["pop_v"] = server["total_clients"] / server["updates"]

	finishRequestAsync(server)

	return "Request has been filed.", 202

# Utilities

# Returns ping time in seconds (up), False (down), or None (error).
def serverUp(info):
	try:
		sock = socket.socket(info[0], info[1], info[2])
		sock.settimeout(3)
		sock.connect(info[4])
		# send packet of type ORIGINAL, with no data
		#     this should prompt the server to assign us a peer id
		# [0] u32       protocol_id (PROTOCOL_ID)
		# [4] session_t sender_peer_id (PEER_ID_INEXISTENT)
		# [6] u8        channel
		# [7] u8        type (PACKET_TYPE_ORIGINAL)
		buf = b"\x4f\x45\x74\x03\x00\x00\x00\x01"
		sock.send(buf)
		start = time.time()
		# receive reliable packet of type CONTROL, subtype SET_PEER_ID,
		#     with our assigned peer id as data
		# [0] u32        protocol_id (PROTOCOL_ID)
		# [4] session_t  sender_peer_id
		# [6] u8         channel
		# [7] u8         type (PACKET_TYPE_RELIABLE)
		# [8] u16        seqnum
		# [10] u8        type (PACKET_TYPE_CONTROL)
		# [11] u8        controltype (CONTROLTYPE_SET_PEER_ID)
		# [12] session_t peer_id_new
		data = sock.recv(1024)
		end = time.time()
		if not data:
			return False
		peer_id = data[12:14]
		# send packet of type CONTROL, subtype DISCO,
		#     to cleanly close our server connection
		# [0] u32       protocol_id (PROTOCOL_ID)
		# [4] session_t sender_peer_id
		# [6] u8        channel
		# [7] u8        type (PACKET_TYPE_CONTROL)
		# [8] u8        controltype (CONTROLTYPE_DISCO)
		buf = b"\x4f\x45\x74\x03" + peer_id + b"\x00\x00\x03"
		sock.send(buf)
		sock.close()
		return end - start
	except socket.timeout:
		return False
	except:
		return None


# fieldName: (Required, Type, SubType)
fields = {
	"action": (True, "str"),

	"address": (False, "str"),
	"port": (False, "int"),

	"clients": (True, "int"),
	"clients_max": (True, "int"),
	"uptime": (True, "int"),
	"game_time": (True, "int"),
	"lag": (False, "float"),

	"clients_list": (False, "list", "str"),
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
	"liquid_finite": (False, "bool"),
	"pvp": (False, "bool"),
	"password": (False, "bool"),
	"rollback": (False, "bool"),
	"can_see_far_names": (False, "bool"),
}

def checkRequest(server):
	for name, data in fields.items():
		if not name in server:
			if data[0]: return False
			else: continue
		#### Compatibility code ####
		# Accept strings in boolean fields but convert it to a
		# boolean, because old servers sent some booleans as strings.
		if data[1] == "bool" and type(server[name]).__name__ == "str":
			server[name] = True if server[name].lower() in ("true", "1") else False
			continue
		# Accept strings in integer fields but convert it to an
		# integer, for interoperability with e.g. minetest.write_json.
		if data[1] == "int" and type(server[name]).__name__ == "str":
			server[name] = int(server[name])
			continue
		#### End compatibility code ####
		if type(server[name]).__name__ != data[1]:
			return False
		if len(data) >= 3:
			for item in server[name]:
				if type(item).__name__ != data[2]:
					return False
	return True


def finishRequestAsync(server):
	th = Thread(name = "ServerListThread",
		target = asyncFinishThread,
		args = (server,))
	th.start()


def asyncFinishThread(server):
	checkAddress = False
	if not "address" in server or not server["address"]:
		server["address"] = server["ip"]
	else:
		checkAddress = True

	try:
		info = socket.getaddrinfo(server["address"],
			server["port"],
			type=socket.SOCK_DGRAM,
			proto=socket.SOL_UDP)
	except socket.gaierror:
		app.logger.warning("Unable to get address info for %s." % (server["address"],))
		return

	if checkAddress:
		addresses = set(data[4][0] for data in info)
		if not server["ip"] in addresses:
			app.logger.warning("Invalid IP %s for address %s (address valid for %s)."
					% (server["ip"], server["address"], addresses))
			return

	geo = geoip_lookup_continent(info[-1][4][0])
	if geo:
		server["geo_continent"] = geo

	server["ping"] = serverUp(info[0])
	if not server["ping"]:
		app.logger.warning("Server %s:%d has no ping."
				% (server["address"], server["port"]))
		return

	del server["action"]

	serverList.update(server)


class UptimeTracker:
	def  __init__(self):
		self.d = {}
		self.cleanTime = 0
		self.lock = RLock()
	def push(self, id, ts):
		with self.lock:
			if time.time() >= self.cleanTime: # clear once in a while
				self.d.clear()
				self.cleanTime = time.time() + 48*60*60

			if id in self.d:
				self.d[id] = self.d[id][-1:] + [ts]
			else:
				self.d[id] = [0, ts]
	# returns the before-last start time, in bulk
	def getStartTimes(self):
		ret = {}
		with self.lock:
			for k, v in self.d.items():
				ret[k] = v[0]
		return ret

class ServerList:
	def __init__(self):
		self.list = []
		self.maxServers = 0
		self.maxClients = 0
		self.lock = RLock()
		self.load()
		self.purgeOld()

	def getWithIndex(self, ip, port):
		with self.lock:
			for i, server in enumerate(self.list):
				if server["ip"] == ip and server["port"] == port:
					return (i, server)
		return (None, None)

	def get(self, ip, port):
		i, server = self.getWithIndex(ip, port)
		return server

	def remove(self, server):
		with self.lock:
			try:
				self.list.remove(server)
			except:
				pass

	def sort(self):
		start_times = tracker.getStartTimes()

		def server_points(server):
			points = 0

			# 1 per client
			if "clients_list" in server:
				points += len(server["clients_list"])
			else:
				# Old server (1/4 per client)
				points = server["clients"] / 4

			# Penalize highly loaded servers to improve player distribution.
			# Note: This doesn't just make more than 80% of max players stop
			# increasing your points, it can actually reduce your points
			# if you have guests.
			cap = int(server["clients_max"] * 0.80)
			if server["clients"] > cap:
				points -= server["clients"] - cap

			# 1 per month of age, limited to 8
			points += min(8, server["game_time"] / (60*60*24*30))

			# 1/2 per average client, limited to 4
			points += min(4, server["pop_v"] / 2)

			# -8 for unrealistic max_clients
			if server["clients_max"] > 200:
				points -= 8

			# -8 per second of ping over 0.4s
			if server["ping"] > 0.4:
				points -= (server["ping"] - 0.4) * 8

			# Up to -8 for less than an hour of uptime (penalty linearly decreasing)
			# only if the server has restarted before within the last 2 hours
			HOUR_SECS = 60 * 60
			uptime = server["uptime"]
			if uptime < HOUR_SECS:
				start_time = start_times.get("%s:%d" % (server["ip"], server["port"]), 0)
				if start_time >= time.time() - 2 * HOUR_SECS:
					points -= ((HOUR_SECS - uptime) / HOUR_SECS) * 8

			# reduction to 40% for servers that support both legacy (v4) and v5 clients
			if server["proto_min"] <= 32 and server["proto_max"] > 36:
				points *= 0.4

			return points

		with self.lock:
			self.list.sort(key=server_points, reverse=True)

	def purgeOld(self):
		cutoff = int(time.time()) - app.config["PURGE_TIME"]
		with self.lock:
			count = len(self.list)
			self.list = [server for server in self.list if cutoff <= server["update_time"]]
			if len(self.list) < count:
				self.save()

	def load(self):
		with self.lock:
			try:
				with open(os.path.join(app.static_folder, "list.json"), "r") as fd:
					data = json.load(fd)
			except FileNotFoundError:
				return

			if not data:
				return

			self.list = data["list"]
			self.maxServers = data["total_max"]["servers"]
			self.maxClients = data["total_max"]["clients"]

	def save(self):
		with self.lock:
			servers = len(self.list)
			clients = 0
			for server in self.list:
				clients += server["clients"]

			self.maxServers = max(servers, self.maxServers)
			self.maxClients = max(clients, self.maxClients)

			list_path = os.path.join(app.static_folder, "list.json")
			with open(list_path + "~", "w") as fd:
				json.dump({
						"total": {"servers": servers, "clients": clients},
						"total_max": {"servers": self.maxServers, "clients": self.maxClients},
						"list": self.list
					},
					fd,
					indent = "\t" if app.config["DEBUG"] else None,
					separators = (', ', ': ') if app.config["DEBUG"] else (',', ':')
				)
			os.replace(list_path + "~", list_path)

	def update(self, server):
		with self.lock:
			i, old = self.getWithIndex(server["ip"], server["port"])
			if i is not None:
				self.list[i] = server
			else:
				self.list.append(server)

			self.sort()
			self.save()

class PurgeThread(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.daemon = True
	def run(self):
		while True:
			time.sleep(60)
			serverList.purgeOld()

# Globals / Startup

tracker = UptimeTracker()

serverList = ServerList()

PurgeThread().start()

if __name__ == "__main__":
	app.run(host = app.config["HOST"], port = app.config["PORT"])
