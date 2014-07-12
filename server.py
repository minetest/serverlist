#!/usr/bin/env python3
import os, sys, json, time, socket
from threading import Thread, RLock
from operator import itemgetter

from apscheduler.scheduler import Scheduler
from flask import Flask, request, send_from_directory

serverList = []
maxServers = 0
maxClients = 0
listLock = RLock()

sched = Scheduler()
sched.start()

app = Flask(__name__, static_url_path = "")
app.config.from_pyfile("config.py")

@app.route("/")
def index():
	return app.send_static_file("index.html")


@app.route("/list")
def list():
	# We have to make sure that the list isn't cached,
	# since the list isn't really static.
	return send_from_directory(app.static_folder, app.config["FILENAME"],
			cache_timeout=0)


@app.route("/announce", methods=["GET", "POST"])
def announce():
	ip = request.remote_addr
	if ip.startswith("::ffff:"):
		ip = ip[7:]

	if ip in app.config["BANLIST"]:
		return "Banned.", 403

	if request.method == "POST":
		data = request.form["json"]
	else:
		data = request.args["json"]

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

	if server["action"] == "start":
		server["uptime"] = 0

	server["ip"] = ip

	if not "port" in server:
		server["port"] = 30000
	#### Compatability code ####
	# port was sent as a string instead of an integer
	elif type(server["port"]) == str:
		server["port"] = int(server["port"])
	#### End compatability code ####

	old = getServer(server["ip"], server["port"])

	if server["action"] == "delete":
		if not old:
			return "Server not found.", 500
		removeServer(old)
		saveList()
		return "Removed from server list."
	elif not checkRequest(server):
		return "Invalid JSON data.", 400

	if server["action"] != "start" and not old:
		if app.config["ALLOW_UPDATE_WITHOUT_OLD"]:
			old = server
			old["start"] = time.time()
			old["clients_top"] = 0
			old["updates"] = 0
			old["total_clients"] = 0
		else:
			return "Server to update not found.", 500

	server["update_time"] = time.time()

	if server["action"] == "start":
		server["start"] = time.time()
	else:
		server["start"] = old["start"]

	if "clients_list" in server:
		server["clients"] = len(server["clients_list"])

	if old:
		server["clients_top"] = max(server["clients"], old["clients_top"])
	else:
		server["clients_top"] = server["clients"]

	# Make sure that startup options are saved
	if server["action"] != "start":
		for field in ("dedicated", "rollback", "mapgen", "privs",
				"can_see_far_names", "mods"):
			if field in old:
				server[field] = old[field]

	# Popularity
	if old:
		server["updates"] = old["updates"] + 1
		# This is actally a count of all the client numbers we've received,
		# it includes clients that were on in the previous update.
		server["total_clients"] = old["total_clients"] + server["clients"]
	else:
		server["updates"] = 1
		server["total_clients"] = server["clients"]
	server["pop_v"] = server["total_clients"] / server["updates"]

	finishRequestAsync(server)

	return "Thanks, your request has been filed.", 202


# Returns ping time in seconds (up), False (down), or None (error).
def serverUp(address, port):
	try:
		start = time.time()
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(3)
		buf = b"\x4f\x45\x74\x03\x00\x00\x00\x01"
		sock.sendto(buf, (address, port))
		data, addr = sock.recvfrom(1000)
		if not data:
			return False
		peer_id = data[12:14]
		buf = b"\x4f\x45\x74\x03" + peer_id + b"\x00\x00\x03"
		sock.sendto(buf, (address, port))
		sock.close()
		end = time.time()
		return end - start
	except socket.timeout:
		return False
	except:
		return None


def getServerAndIndex(ip, port):
	with listLock:
		for i, server in enumerate(serverList):
			if server["ip"] == ip and server["port"] == port:
				return (i, server)


def getServer(ip, port):
	server = getServerAndIndex(ip, port)
	return server and server[1]


def removeServer(server):
	with listLock:
		try:
			serverList.remove(server)
		except:
			pass


def sortList():
	with listLock:
		serverList.sort(key=itemgetter("clients", "start"), reverse=True)

@sched.interval_schedule(minutes=1, coalesce=True, max_instances=1)
def purgeOld():
	with listLock:
		for server in serverList:
			if server["update_time"] < time.time() - app.config["PURGE_TIME"]:
				serverList.remove(server)
	saveList()


def loadList():
	global serverList, maxServers, maxClients
	try:
		with open(os.path.join("static", app.config["FILENAME"]), "r") as fd:
			data = json.load(fd)
	except FileNotFoundError:
		return
	if not data:
		return
	with listLock:
		serverList = data["list"]
		maxServers = data["total_max"]["servers"]
		maxClients = data["total_max"]["clients"]


def saveList():
	global maxServers, maxClients
	with listLock:
		servers = len(serverList)
		clients = 0
		for server in serverList:
			clients += server["clients"]

		maxServers = max(servers, maxServers)
		maxClients = max(clients, maxClients)

		with open(os.path.join("static", app.config["FILENAME"]), "w") as fd:
			json.dump({
					"total": {"servers": servers, "clients": clients},
					"total_max": {"servers": maxServers, "clients": maxClients},
					"list": serverList
				},
				fd,
				indent = "\t" if app.config["DEBUG"] else None)


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
			server[name] = True if server[name].lower() in ["true", "1"] else False
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
	if "address" in server and server["address"] != "":
		try:
			info = socket.getaddrinfo(server["address"], server["port"])
		except:
			app.logger.warning("Unable to get address info for %s." % (server["address"],))
			return
		addresses = set(data[4][0] for data in info)
		found = False
		for addr in addresses:
			if server["ip"] == addr:
				found = True
				break
		if not found:
			#app.logger.warning("Invalid IP %s for address %s (address valid for %s)."
			#		% (server["ip"], server["address"], addresses))
			#return
			pass
	else:
		server["address"] = server["ip"]

	server["ping"] = serverUp(server["address"], server["port"])
	if not server["ping"]:
		return

	del server["action"]

	with listLock:
		old = getServerAndIndex(server["ip"], server["port"])
		if old:
			serverList[old[0]] = server
		else:
			serverList.append(server)

	sortList()
	saveList()


loadList()
purgeOld()

if __name__ == "__main__":
	app.run(host = app.config["HOST"], port = app.config["PORT"])
