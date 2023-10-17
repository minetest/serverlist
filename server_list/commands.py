import json

import click

from .app import app, db
from .models import Server, Stats


@app.cli.command("load-json")
@click.argument("filename")
@click.option("--update")
def load_json(filename, update):
	"""Load the SQL database with servers from a JSON server list.
	"""
	with open(filename, "r") as fd:
		data = json.load(fd)
		assert data

	for obj in data["list"]:
		if update:
			obj.setdefault("address", obj["ip"])
			Server.create_or_update(obj)
		else:
			server = Server()
			server.update(obj, True)
			db.session.add(server)

	stats = Stats.get()
	stats.max_servers = data["total_max"]["servers"]
	stats.max_clients = data["total_max"]["clients"]
	db.session.add(stats)

	db.session.commit()

	click.echo(click.style(f'Loaded {len(data["list"])} servers', fg="green"))
