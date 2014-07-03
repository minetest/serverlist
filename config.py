
# Enables detailed tracebacks and an interactive Python console on errors.
# Never use in production!
#DEBUG = True

# Makes the server more performant at sending static files when the
# server is being proxied by a server that supports X-Sendfile.
#USE_X_SENDFILE = True

# Address to listen for clients on
HOST = "0.0.0.0"

# Port to listen on
PORT = 8000

# File to store the JSON server list data in.
FILENAME = "list.json"

# Ammount of time, is seconds, after which servers are removed from the list
# if they haven't updated their listings.  Note: By default Minetest servers
# only announce once every 5 minutes, so this should be more than 300.
PURGE_TIME = 350

# List of banned IP addresses.
BANLIST = []

# Creates server entries if a server sends an 'update' and there is no entry yet
# This should only be used to populate the server list after list.json was deleted.
# This WILL cause problems such as mapgen, mods and privilege information missing from the list
ALLOW_UPDATE_WITHOUT_OLD = False
