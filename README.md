Minetest Server List
====================

Webpage Setup
---

You will have to install node.js, doT.js and their dependencies to compile the server list webpage template.

First install node.js, e.g.:

```sh
sudo pacman -S nodejs
# OR:
sudo apt-get install nodejs
```

Then install doT.js and its dependencies:

```sh
npm install
```

And finally compile the template:

```sh
cd server_list/static
../../node_modules/dot/bin/dot-packer -s .
```

You can now serve the webpage by copying the files in `server_list/static/` to your web root, or by [starting the server list](#server-setup).

Embedding in a Webpage
---

```html
<head>
	...
	<script>
		var master = {
			root: 'https://servers.minetest.net/',
			limit: 10,
			clients_min: 1,
			no_flags: 1,
			no_ping: 1,
			no_uptime: 1
		};
	</script>
	...
</head>
<body>
	...
	<div id="server_list"></div>
	...
</body>
<script src="list.js"></script>
```

Server Setup
---

 1. Install Python 3 and Pipenv:

    ```sh
    sudo pacman -S python python-pipenv
    # OR:
    sudo apt-get install python3 python3-pip && pip install pipenv
    ```

 2. Install required Python packages:

    ```sh
    pipenv sync
    ```

 3. Set up Celery message broker.  Pick a Celery backend (Redis or RabbitMQ are recommended), and install and enable the required packages.  For example:

    ```sh
    # Redis support requires an additional package
    pipenv run pip install redis
    sudo pacman -S redis # or sudo apt-get install redis
    sudo systemctl enable --now redis
    ```

 4. Configure the server by adding options to `config.py`.
    See `server_list/config.py` for defaults.

 5. Start the server for development:

    ```sh
    pipenv run flask run
    ```

 6. Start the celery background worker:

    ```sh
    pipenv run celery --app server_list:celery worker --beat
    ```

Running in Production
---

When running in production you should set up a proxy server that calls the server list through WSGI.

These examples assume that the server list is installed to `/srv/http/serverlist`.

### Nginx

First [set up uWSGI](#uwsgi), then update the Nginx configuration to proxy to uWSGI.  You should make the server load static files directly from the static directory.  Also, `/list` should be aliased to `list.json`.

Here's an example configuration:

```nginx
root /srv/http/serverlist/server_list/static;
rewrite ^/list$ /list.json;
try_files $uri @uwsgi;
location @uwsgi {
	uwsgi_pass unix:/run/uwsgi/server_list.sock;
}
```

Also see [the Flask uwsgi documentation](https://flask.palletsprojects.com/en/2.0.x/deploying/uwsgi/).

### Apache

There are two options for Apache, you can use either `mod_wsgi` or `mod_proxy_uwsgi`.

Note: both of these example configurations serve static through WSGI, instead of bypassing WSGI for performance.

#### mod_wsgi

First install/enable `mod_wsgi`.

Then create `wsgi.py` in the directory containing `server_list` with the following contents:

```py
import os, sys
sys.path.append(os.path.dirname(__file__))
from server_list import app
```

Then configure the Apache VirtualHost like the following:

```apache
WSGIDaemonProcess server_list python-home=<output of pipenv --venv>

WSGIProcessGroup server_list
WSGIApplicationGroup %{GLOBAL}

WSGIScriptAlias / /srv/http/serverlist/wsgi.py
WSGICallableObject app

<Directory /srv/http/serverlist>
	<Files wsgi.py>
		Require all granted
	</Files>
</Directory>
```

#### mod_proxy_uwsgi

First [set up uWSGI](#uwsgi), then install/enable `mod_proxy` and `mod_proxy_uwsgi` and add the following to your VirtualHost:

```apache
ProxyPass / unix:/run/uwsgi/server_list.sock|uwsgi://localhost/
```

Note: this requires at least Apache 2.4.7 for the unix socket syntax.  If you have an older version of Apache you'll have to use IP sockets.

### uWSGI

First, install uWSGI and its python plugin.

```sh
pacman -S uwsgi uwsgi-plugin-python
# OR:
apt-get install uwsgi uwsgi-plugin-python
# OR:
pip install uwsgi
```

Then create a uWSGI config file.  For example:

```ini
[uwsgi]
socket = /run/uwsgi/server_list.sock
plugin = python
virtualenv = <output of pipenv --venv>
python-path = /srv/http/serverlist
module = server_list
callable = app
```

You can put the config file in `/etc/uwsgi/server_list.ini`.  Make sure that uWSGI is configured to start as the appropriate user and group for your distro (e.g. http:http) and then start and enable uWSGI.

```sh
systemctl enable --now uwsgi@server_list.service
```

License
---

The Minetest server list code is licensed under the GNU Lesser General Public
License version 2.1 or later (LGPLv2.1+).  A LICENSE.txt file should have been
supplied with your copy of this software containing a copy of the license.
