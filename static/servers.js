(function() {
	function total_fill(it, div) {
		div.className = "total";
		div.innerHTML =
			"Players: " + it.total.clients + "/" + it.total_max.clients + "&nbsp" +
			"Servers: " + it.total.servers + "/" + it.total_max.servers;
	}
	function table_head_fill(thead) {
		thead.innerHTML =
			"<tr>" +
			"<th>Address[:Port]</th>" +
			"<th>Players / Max<br/>Average / Top</th>" +
			"<th>Version, Subgame[, Mapgen]</th>" +
			"<th>Name</th>" +
			"<th>Description</th>" +
			"<th>Flags</th>" +
			"<th>Uptime, Age</th>" +
			"<th>Ping, Lag</th>" +
			"</tr>";
	}
	function table_row_fill(server, tr) {
		var td = document.createElement("td");
		td.className = "address";
		td.innerHTML = addressString(server);
		tr.appendChild(td);

		var td = document.createElement("td");
		td.className = "clients" + (server.clients_list && server.clients_list.length > 0 ? " mts_hover_list_text" : "");
		td.innerHTML =
			constantWidth(server.clients + "/" + server.clients_max, 3.4) +
			constantWidth(Math.floor(server.pop_v) + "/" + server.clients_top, 3.4) +
			hoverList("Clients", server.clients_list);
		tr.appendChild(td);

		var td = document.createElement("td");
		td.className = "version" + (server.mods && server.mods.length > 0 ? " mts_hover_list_text" : "");
		td.innerHTML =
			escapeHTML(server.version) + ", " +
			escapeHTML(server.gameid) + ", " +
			escapeHTML(server.mapgen) +
			hoverList("Mods", server.mods);
		tr.appendChild(td);

		var td = document.createElement("td");
		td.className = "name";
		var url = document.createElement("a");
		url.href = (server.url ? escapeHTML(server.url) : "");
		url.textContent = tooltipString(server.name, 25);
		td.appendChild(url);
		tr.appendChild(td);

		var td = document.createElement("td");
		td.className = "description";
		td.innerHTML = tooltipString(server.description, 50);
		tr.appendChild(td);

		var td = document.createElement("td");
		td.className = "flags";
		td.innerHTML =
			hoverString("Privs", server.privs) +
			(server.creative ? "Cre " : "") +
			(server.damage   ? "Dmg " : "") +
			(server.pvp      ? "Pvp " : "") +
			(server.password ? "Pwd " : "") +
			(server.rollback ? "Rol " : "") +
			(server.can_see_far_names ? "Far " : "");
		tr.appendChild(td);

		var td = document.createElement("td");
		td.className = "uptime";
		td.innerHTML = constantWidth(humanTime(server.uptime), 3.2) + "/" + constantWidth(humanTime(server.game_time), 3.2)
		tr.appendChild(td);

		var td = document.createElement("td");
		td.className = "ping";
		td.innerHTML = constantWidth(Math.floor(server.ping * 1000), 1.8) + "/" + constantWidth(Math.floor(server.lag * 1000), 1.8);
		tr.appendChild(td);
	}
	function servers(it, node) {
		var total = document.createElement("div");
		var table = document.createElement("table");
		var thead = document.createElement("thead");
		var tbody = document.createElement("tbody");

		node.innerHTML = '';  // clear all children
		node.appendChild(total);
		node.appendChild(table);
		table.appendChild(thead);
		table.appendChild(tbody);

		total_fill(it, total);
		table_head_fill(thead);

		for (var i = 0; i < it.list.length; i++) {
			var server = it.list[i];

			if (master.limit && index > master.limit) break;
			if (master.min_clients && server.clients < master.min_clients) continue;

			var tr = document.createElement("tr");
			table_row_fill(server, tr);
			tbody.appendChild(tr);
		}
	}
	window.render = window.render || {};
	window.render['servers'] = servers;
}());
