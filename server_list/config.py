from datetime import timedelta
from glob import glob

# Enables detailed tracebacks and an interactive Python console on errors.
# Never use in production!
DEBUG = False

# Amount of time, in seconds, after which servers are removed from the list
# if they haven't updated their listings.  Note: By default Minetest servers
# only announce once every 5 minutes, so this should be more than 300.
PURGE_TIME = timedelta(minutes=6)

# List of banned IP addresses for announce
# e.g. ['2620:101::44']
BANNED_IPS = []

# List of banned servers as host/port pairs
# e.g. ['1.2.3.4/30000', 'lowercase.hostname', 'lowercase.hostname/30001']
BANNED_SERVERS = []

# Creates server entries if a server sends an 'update' and there is no entry yet.
# This should only be used to populate the server list after list.json was deleted.
# This WILL cause problems such as mapgen, mods and privilege information missing from the list
ALLOW_UPDATE_WITHOUT_OLD = False

# Database to use to store persistent server information
SQLALCHEMY_DATABASE_URI = "sqlite:///server_list.sqlite"

# How strongly past player counts are weighted into the popularity
# over the current player count.
POPULARITY_FACTOR = 0.9

# Message broker to forward messages from web server to worker threads
# Redis and RabbitMQ are good options.
#CELERY_BROKER_URL = "redis://localhost/0"

# Maximum number of clients before a server will be considered heavily loaded
# and down-weighted to improve player distribution.
CLIENT_LIMIT = 32

# MaxMind GeoIP database.
# You can download a copy from https://db-ip.com/db/download/ip-to-country-lite
mmdbs = glob("dbip-country-lite-*.mmdb")
if mmdbs:
	MAXMIND_DB = mmdbs[0]
