from datetime import datetime

from sqlalchemy.orm.exc import NoResultFound

from .app import app, db


class Server(db.Model):
	__table_args__ = (db.Index("ix_server_address_port", "address", "port", unique=True),)

	id = db.Column(db.Integer, primary_key=True)

	# World-specific UUID used to identify the server.
	# This is kept secret to prevent anyone from spoofing the server.
	world_uuid = db.Column(db.String(36), nullable=True, index=True, unique=True)

	# Whether the server is currently online
	online = db.Column(db.Boolean, index=True, nullable=False, default=True)

	# Server sent connection address
	address = db.Column(db.String, nullable=False)
	port = db.Column(db.Integer, nullable=False, default=30000)

	# IP address announcement was received from
	announce_ip = db.Column(db.String, nullable=False)

	# Name of server software.  E.g. "minetest"
	server_id = db.Column(db.String, nullable=True)

	# List of player names, one per line
	clients = db.Column(db.String, nullable=True)

	# Highest number of clients ever seen
	clients_top = db.Column(db.Integer, nullable=False)

	# Maximum number of allowed clients
	clients_max = db.Column(db.Integer, nullable=False)

	# First time that we received an announcement from this server
	first_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	# Time that server sent "start" announcement.
	# This can be used to calculate the current uptime.
	start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	# Time of most recent update request
	last_update = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	# Amount of time that we've seen the server up for, in seconds
	total_uptime = db.Column(db.Float, nullable=False)

	# Most recent time that the server went down
	down_time = db.Column(db.DateTime, nullable=True)

	# Server sent value for age of world.
	# Should nearly match uptime on a server that always announces.
	game_time = db.Column(db.Integer, nullable=False)

	# Server sent value based on sever loop timing
	lag = db.Column(db.Float, nullable=True)

	# Ping time in seconds
	ping = db.Column(db.Float, nullable=False)

	# List of enabled mods, one per line
	mods = db.Column(db.String, nullable=True)

	# Server release version
	version = db.Column(db.String, nullable=False)

	# Supported protocol versions
	proto_min = db.Column(db.Integer, nullable=False)
	proto_max = db.Column(db.Integer, nullable=False)

	game_id = db.Column(db.String, nullable=False)

	# Mapgen name
	mapgen = db.Column(db.String, nullable=True)

	# Server landing page URL
	url = db.Column(db.String, nullable=True)

	# Privileges granted to new players by default
	default_privs = db.Column(db.String, nullable=True)

	name = db.Column(db.String, nullable=False)

	description = db.Column(db.String, nullable=False)

	# Roughly the average number of players on the server
	popularity = db.Column(db.Float, nullable=False)

	# Continent determined from IP
	geo_continent = db.Column(db.String(2), nullable=True)

	# Flags
	creative = db.Column(db.Boolean, nullable=False)
	is_dedicated = db.Column(db.Boolean, nullable=False)
	damage_enabled = db.Column(db.Boolean, nullable=False)
	pvp_enabled = db.Column(db.Boolean, nullable=False)
	password_required = db.Column(db.Boolean, nullable=False)
	rollback_enabled = db.Column(db.Boolean, nullable=False)
	can_see_far_names = db.Column(db.Boolean, nullable=False)

	address_verification_required = db.Column(db.Boolean, nullable=False, default=False)

	@staticmethod
	def find_from_json(obj):
		try:
			if "world_uuid" in obj:
				return Server.query.filter_by(world_uuid=obj["world_uuid"]).one()
			return Server.query.filter_by(address=obj["address"], port=obj["port"]).one()
		except NoResultFound:
			return None

	@staticmethod
	def create_or_update(obj):
		server = Server.find_from_json(obj)
		if server is not None:
			server.update(obj)
		else:
			server = Server()
			server.update(obj, True)
			db.session.add(server)
		return server

	def update(self, obj, initial=False):
		now = datetime.now()
		action = obj.get("action", "start")

		assert action != "delete"

		if "clients_list" in obj:
			num_clients = len(obj["clients_list"])
		else:
			num_clients = obj["clients"]

		if initial:
			# Values set only when the server is first created
			assert action == "start"
			self.world_uuid = obj.get("world_uuid")
			self.clients_top = num_clients
			self.total_uptime = 0
		else:
			self.clients_top = max(self.clients_top, num_clients)

		if action == "start":
			# Fields updated only on startup
			self.start_time = now
			self.mods = "\n".join(obj.get("mods", []))
			self.mapgen = obj.get("mapgen")
			self.default_privs = obj.get("privs")
			self.is_dedicated = obj.get("dedicated", False)
			self.rollback_enabled = obj.get("rollback", False)
			self.can_see_far_names = obj.get("can_see_far_names", False)

		self.online = True

		self.address = obj["address"]
		self.port = obj.get("port", 30000)

		self.announce_ip = obj["ip"]

		self.server_id = obj.get("server_id")

		self.clients = "\n".join(obj["clients_list"])
		self.clients_max = obj["clients_max"]

		self.game_time = obj["game_time"]

		self.lag = obj.get("lag")
		self.ping = obj["ping"]

		self.version = obj["version"]
		self.proto_min = obj["proto_min"]
		self.proto_max = obj["proto_max"]

		self.game_id = obj["gameid"]
		self.url = obj.get("url")
		self.name = obj["name"]
		self.description = obj["description"]

		if initial:
			self.popularity = num_clients
		else:
			pop_factor = app.config["POPULARITY_FACTOR"]
			self.popularity = self.popularity * pop_factor + \
				num_clients * (1 - pop_factor)

		self.geo_continent = obj.get("geo_continent")

		self.creative = obj.get("creative", False)
		self.damage_enabled = obj.get("damage", False)
		self.pvp_enabled = obj.get("pvp", False)
		self.password_required = obj.get("password", False)

		self.last_update = now

		if obj["address_verified"]:
			self.address_verification_required = True

	def as_json(self):
		obj = {
			"address": self.address,
			"can_see_far_names": self.can_see_far_names,
			"clients_list": self.clients.split("\n") if self.clients else [],
			"clients_max": self.clients_max,
			"clients_top": self.clients_top,
			"creative": self.creative,
			"damage": self.damage_enabled,
			"dedicated": self.is_dedicated,
			"description": self.description,
			"game_time": self.game_time,
			"gameid": self.game_id,
			"name": self.name,
			"password": self.password_required,
			"ping": self.ping,
			"pop_v": self.popularity,
			"port": self.port,
			"proto_max": self.proto_max,
			"proto_min": self.proto_min,
			"pvp": self.pvp_enabled,
			"rollback": self.rollback_enabled,
			"uptime": int((datetime.utcnow() - self.start_time).total_seconds()),
			"version": self.version,
		}

		# Optional fields
		if self.geo_continent is not None:
			obj["geo_continent"] = self.geo_continent
		if self.lag is not None:
			obj["lag"] = self.lag
		if self.mapgen is not None:
			obj["mapgen"] = self.mapgen
		if self.mods is not None:
			obj["mods"] = self.mods.split("\n") if self.mods else []
		if self.default_privs is not None:
			obj["privs"] = self.default_privs
		if self.server_id is not None:
			obj["server_id"] = self.server_id
		if self.url is not None:
			obj["url"] = self.url

		return obj

	def set_offline(self):
		now = datetime.utcnow()
		self.online = False
		self.total_uptime += (now - self.start_time).total_seconds()
		self.down_time = now


class Stats(db.Model):
	"""
	This table has only a single row storing all of the global statistics.
	"""
	id = db.Column(db.Integer, primary_key=True)

	max_servers = db.Column(db.Integer, nullable=False, default=0)
	max_clients = db.Column(db.Integer, nullable=False, default=0)

	@staticmethod
	def get():
		try:
			return Stats.query.filter_by(id=1).one()
		except NoResultFound:
			stats = Stats()
			stats.id = 1
			db.session.add(stats)
			return stats
