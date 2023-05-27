
# Enables detailed tracebacks and an interactive Python console on errors.
# Never use in production!
DEBUG = False

# Address for development server to listen on
HOST = "127.0.0.1"
# Port for development server to listen on
PORT = 5000

# Amount of time, is seconds, after which servers are removed from the list
# if they haven't updated their listings.  Note: By default Minetest servers
# only announce once every 5 minutes, so this should be more than 300.
PURGE_TIME = 350

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

# Rules to show to the server that has not yet agreed to them. Set to "" to disable.
RULES = """servers.minetest.net server list server operator agreement:
1   Your server must NOT do any of the following:

1.1 Manupulate data to boost server rank. This includes but is not limited to player count, 
uptime, and total server age.

1.2 Server must not contain mods that add pornographic content to the game.

1.3 Server must not advertise in the server list metadata that it contains or
allows pornographic content. This includes server title and description and URL.

"pornographic content" refers to content aimed exlusivly towards adults and not suitible
minors. This includes but is not limited to depicitons of genitals, sex, and any fetish. Even
those that may not be sexual in nature even if the implimentation of said fetish is not sexual.

2   Server operators must do their part to moderate the server. Here is the bare minimum required:

2.1 Server operators must ensure that no content contained in the server is illegal accourding to
the jurisdiction in which the serverlist service resides. [maybe put the country here or something]

2.2 Server operators must take proper security precautions to ensure their server is not easily
compromised.

3   Reporting a server:

3.1 To report a server, please email sfan5 at sfan5@live.de

3.2 Your report must contain the following:

3.2.1 The IP/hostname of the server as it appears in the list

3.2.2 An accurate description of the violation.

3.2.3 Description of where said violation occured. Such as the name, description, server mods/assets,
coordinates to location of violation in-game.

4   Voilation of these rules will result in your server being delisted and prohibited from
showing up in the list in the future. Members of our community may also attempt to take down your
server by exploiting vunerabilities in mods and flooding player slots. This action is discouraged
but not prohibited.

5   We reserve the right to delist your server for any reason or no reason at all.

"""