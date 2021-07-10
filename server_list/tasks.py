import asyncio
import json
import os
from datetime import datetime

from .app import app, celery, db
from .models import Server, Stats
from .ping import ping_servers_async, ping_server_addresses
from .util import get_geo_continent, server_ranking


@celery.task
def update_server(obj):
	geo_continent = get_geo_continent(obj["addr_info"][-1][4][0])
	if geo_continent is not None:
		obj["geo_continent"] = geo_continent

	# Ensure that a Minetest server is actually reachable on all addresses
	pings = ping_server_addresses(obj["address"], obj["port"])

	if pings is None:
		return

	# Use average ping
	obj["ping"] = sum(pings) / len(pings)

	Server.create_or_update(obj)

	db.session.commit()


def update_list_json():
	online_servers = Server.query.filter_by(online=True).all()
	online_servers.sort(key=server_ranking, reverse=True)
	server_list = [s.as_json() for s in online_servers]

	num_clients = 0
	for server in server_list:
		num_clients += len(server["clients_list"])

	stats = Stats.get()
	stats.max_servers = max(len(server_list), stats.max_servers)
	stats.max_clients = max(num_clients, stats.max_clients)

	list_path = os.path.join(app.static_folder, "list.json")
	# Write to temporary file, then do an atomic replace so that clients don't
	# see a truncated file if they load the list just as it's being updated.
	with open(list_path + "~", "w") as fd:
		debug = app.config["DEBUG"]
		json.dump({
				"total": {"servers": len(server_list), "clients": num_clients},
				"total_max": {"servers": stats.max_servers, "clients": stats.max_clients},
				"list": server_list,
			},
			fd,
			indent="\t" if debug else None,
			separators=(',', ': ') if debug else (',', ':')
		)
	os.replace(list_path + "~", list_path)


@celery.task
def update_list():
	cutoff = datetime.utcnow() - app.config["PURGE_TIME"]
	expired_servers = Server.query.filter(
			Server.online == True,
			Server.last_update < cutoff
		)

	for server in expired_servers:
		server.set_offline()

	update_list_json()

	db.session.commit()


@celery.task
def update_ping():
	servers = Server.query.filter_by(online=True).all()

	addresses = [(s.address, s.port) for s in servers]
	pings = []

	async def do_ping():
		pings.extend(await ping_servers_async(addresses))
	asyncio.run(do_ping())

	for i, server in enumerate(servers):
		if pings[i] is None:
			server.set_offline()
		else:
			server.ping = pings[i]

	db.session.commit()


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
	sender.add_periodic_task(60, update_list.s(), name='Update server list')
	sender.add_periodic_task(5*60, update_ping.s(), name='Update server ping')
