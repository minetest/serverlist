import json

from flask import render_template, request, send_from_directory, make_response

from .app import app, db
from .models import Server
from .tasks import update_server
from .util import check_ban, check_request_json, get_addr_info, get_geo_continent, verify_announce


@app.route("/")
def index():
	return app.send_static_file("index.html")


@app.route("/list")
def server_list():
	# We have to make sure that the list isn't cached,
	# since the list isn't really static.
	return send_from_directory(app.static_folder, "list.json", max_age=0)


@app.route("/geoip")
def geoip():
	continent = get_geo_continent(request.remote_addr)

	resp = make_response({
		"continent": continent, # null on error
	})
	resp.cache_control.max_age = 7 * 86400
	resp.cache_control.private = True

	return resp


@app.route("/announce", methods=["GET", "POST"])
def announce():
	announce_ip = request.remote_addr
	if announce_ip.startswith("::ffff:"):
		announce_ip = announce_ip[7:]

	if announce_ip in app.config["BANNED_IPS"]:
		return "Banned.", 403

	data = request.values["json"]

	if len(data) > 8192:
		return "JSON data is too big.", 413

	try:
		obj = json.loads(data)
	except json.JSONDecodeError as e:
		return "Failed to decode JSON: " + e.msg, 400

	if not isinstance(obj, dict):
		return "JSON data is not an object.", 400

	action = obj.get("action")
	if action not in ("start", "update", "delete"):
		return "Action field is invalid or missing.", 400

	obj["ip"] = announce_ip
	if not obj.get("address"):
		obj["address"] = announce_ip
	obj.setdefault("port", 30000)

	if check_ban(announce_ip, obj["address"], obj["port"]):
		return "Banned", 403

	server = Server.find_from_json(obj)

	if action == "delete":
		if not server:
			return "Server not found."
		server.set_offline()
		db.session.commit()
		return "Removed from server list."

	# Delete message does not require most fields
	error_str = check_request_json(obj)
	if error_str is not None:
		return "Invalid JSON data: " + error_str, 400

	if action == "update" and not server:
		if app.config["ALLOW_UPDATE_WITHOUT_OLD"]:
			action = "start"
		else:
			return "Server to update not found.", 404

	addr_info = get_addr_info(obj["address"], obj["port"])

	if addr_info is None:
		return f"Failed to resolve server address {obj['address']!r}.", 400

	if "world_uuid" not in obj:
		valid = verify_announce(addr_info, obj["address"], obj["ip"])

		if not valid:
			return render_template("address_verification_failed.txt",
				announce_ip=announce_ip,
				valid_addresses=[data[4][0] for data in addr_info]), 400

	obj["addr_info"] = addr_info

	update_server.delay(obj)

	return "Done.", 202
