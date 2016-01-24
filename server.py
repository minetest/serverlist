#!/usr/bin/env python3
import os, sys, json, time, socket
from threading import Thread, RLock

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, send_from_directory


# Set up scheduler
sched = BackgroundScheduler(timezone="UTC")
sched.start()

app = Flask(__name__, static_url_path = "")

# Load configuration
app.config.from_pyfile("config-example.py")  # Use example for defaults
if os.path.isfile(os.path.join(app.root_path, "config.py")):
        app.config.from_pyfile("config.py")


# Views

@app.route("/")
def index():
	return app.send_static_file("index.html")


@app.route("/list")
def list():
	# We have to make sure that the list isn't cached,
	# since the list isn't really static.
	return send_from_directory(app.static_folder, "list.json",
			cache_timeout=0)


@app.route("/announce", methods=["GET", "POST"])
def announce():
	ip = request.remote_addr
	if ip.startswith("::ffff:"):
		ip = ip[7:]

	data = request.values["json"]

	if len(data) > 5000:
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

	old = serverList.get(ip, server["port"])

	if action == "delete":
		if not old:
			return "Server not found.", 500
		serverList.remove(old)
		serverList.save()
		return "Removed from server list."
	elif not checkRequest(server):
		return "Invalid JSON data.", 400

	if action == "update" and not old:
		if app.config["ALLOW_UPDATE_WITHOUT_OLD"]:
			old = server
			old["start"] = time.time()
			old["clients_top"] = 0
			old["updates"] = 0
			old["total_clients"] = 0
		else:
			return "Server to update not found.", 500

	server["update_time"] = time.time()

	server["start"] = time.time() if action == "start" else old["start"]

	if "clients_list" in server:
		server["clients"] = len(server["clients_list"])

	server["clients_top"] = max(server["clients"], old["clients_top"]) if old else server["clients"]

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

	return "Thanks, your request has been filed.", 202

sched.add_job(lambda: serverList.purgeOld(), "interval",
		seconds=60, coalesce=True, max_instances=1)

# Utilities

# Returns ping time in seconds (up), False (down), or None (error).
def serverUp(info):
	try:
		sock = socket.socket(info[0], info[1], info[2])
		sock.settimeout(3)
		sock.connect(info[4])
		buf = b"\x4f\x45\x74\x03\x00\x00\x00\x01"
		sock.send(buf)
		start = time.time()
		data = sock.recv(1024)
		end = time.time()
		if not data:
			return False
		peer_id = data[12:14]
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
	"proto_min": (False, "int"),
	"proto_max": (False, "int"),

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
		# clients_max was sent as a string instead of an integer
		if name == "clients_max" and type(server[name]).__name__ == "str":
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

	server["ping"] = serverUp(info[0])
	if not server["ping"]:
		app.logger.warning("Server %s:%d has no ping."
				% (server["address"], server["port"]))
		return

	del server["action"]

	serverList.update(server)


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
		def server_points(server):
			points = 0

			# 1 per client, but only 1/8 per client with a guest
			# or all-numeric name.
			if "clients_list" in server:
				for name in server["clients_list"]:
					if name.startswith("Guest") or \
							name.isdigit():
						points += 1/8
					else:
						points += 1
			else:
				# Old server
				points = server["clients"] / 4

			# Penalize highly loaded servers to improve player distribution.
			# Note: This doesn't just make more than 16 players stop
			# increasing your points, it can actually reduce your points
			# if you have guests/all-numerics.
			if server["clients"] > 16:
				points -= server["clients"] - 16

			# 1 per month of age, limited to 8
			points += min(8, server["game_time"] / (60*60*24*30))

			# 1/2 per average client, limited to 4
			points += min(4, server["pop_v"] / 2)

			# -8 for unrealistic max_clients
			if server["clients_max"] >= 128:
				points -= 8

			# -8 per second of ping over 0.4s
			if server["ping"] > 0.4:
				points -= (server["ping"] - 0.4) * 8

			# Up to -8 for less than an hour of uptime (penalty linearly decreasing)
			HOUR_SECS = 60 * 60
			uptime = server["uptime"]
			if uptime < HOUR_SECS:
				points -= ((HOUR_SECS - uptime) / HOUR_SECS) * 8

			return points

		with self.lock:
			self.list.sort(key=server_points, reverse=True)

	def purgeOld(self):
		with self.lock:
			for server in self.list:
				if server["update_time"] < time.time() - app.config["PURGE_TIME"]:
					self.list.remove(server)
		self.save()

	def load(self):
		try:
			with open(os.path.join("static", "list.json"), "r") as fd:
				data = json.load(fd)
		except FileNotFoundError:
			return

		if not data:
			return

		with self.lock:
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

			with open(os.path.join("static", "list.json"), "w") as fd:
				json.dump({
						"total": {"servers": servers, "clients": clients},
						"total_max": {"servers": self.maxServers, "clients": self.maxClients},
						"list": self.list
					},
					fd,
					indent = "\t" if app.config["DEBUG"] else None
				)

	def update(self, server):
		with self.lock:
			i, old = self.getWithIndex(server["ip"], server["port"])
			if i is not None:
				self.list[i] = server
			else:
				self.list.append(server)

			self.sort()
			self.save()

serverList = ServerList()

if __name__ == "__main__":
	app.run(host = app.config["HOST"], port = app.config["PORT"])

