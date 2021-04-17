# Enables detailed tracebacks and an interactive Python console on errors.
# Never use in production!
DEBUG = False

# Address for development server to listen on
HOST = "127.0.0.1"
# Port for development server to listen on
PORT = 5000

# Amount of time, in seconds, after which servers are removed from the list
# if they haven't updated their listings.  Note: By default Minetest servers
# only announce once every 5 minutes, so this should be more than 300.
PURGE_TIME = 350

# List of banned IP addresses for announce
# e.g. ['2620:101::44']
BANNED_IPS = []

# List of banned servers as host/port pairs, domains must be lowercase
# e.g. ['1.2.3.4/30000', 'server.example.net', 'server.example.net/30001']
BANNED_SERVERS = []

# List of banned domain suffixes, must be lowercase
# e.g. ['.example.net', 'server.example.com']
BANNED_DOMAINS = []

# List of domain suffixes that should not get a point bonus (e.g. free domains), must be lowercase
IRREPUTABLE_DOMAINS = ['.cf', '.ga', '.gq', '.ml', '.tk']

# Creates server entries if a server sends an 'update' and there is no entry yet.
# This should only be used to populate the server list after list.json was deleted.
# This WILL cause problems such as mapgen, mods and privilege information missing from the list
ALLOW_UPDATE_WITHOUT_OLD = False
