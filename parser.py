import json
import time
from datetime import datetime
import sys
import re
import os
import logging
import requests

logging.basicConfig(
    format="%(asctime)s;%(levelname)s;%(funcName)s; %(message)s",
    filename='parser_{:%Y-%m-%d}.log'.format(datetime.now()),
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S'
)

SERVER_IP = os.environ.get("SERVER_IP", "NONE")
PORT = os.environ.get("SERVER_PORT", "2456")
DISCORD = os.environ.get("DISCORD")
STATE_FILE = os.environ.get("STATE_FILE", "./state.json")

#=====================
#  STATE UTILITIES
#=====================

# Loose player definition. These represent the steam users that connected to the server
DEFAULT_PLAYER = {
    "last_character": "",
    "last_joined_epoch": 0,
    "last_joined": "",
    "last_disconnect": "",
    "last_disconnect_epoch": 0,
    "time_played": 0,
    "status": "",
}

# Loose character definition. These represent the Valheim characters that have connected to the
# server
DEFAULT_CHARACTER = {
    "owner_steam_id": "",
    "last_zdoid": "",
    "last_joined_epoch": 0,
    "last_joined": "",
    "last_disconnect": "",
    "last_disconnect_epoch": 0,
    "time_played": 0,
    "status": "",
    "deaths": 0,
}

# Loose server definition. Stores details on the server
DEFAULT_SERVER = {
    "last_parsed_log": "",
    "last_turned_on_epoch": 0,
    "last_shutdown_epoch": 0,
    "last_turned_on": "",
    "last_shutdown": "",
}

# The top level state structure
DEFAULT_STATE = {
    "players": {},
    "characters": {},
    "server": {},
}

def read_state_file():
    """ Reads the JSON state file located at STATE_FILE, appends any new feilds found in
    DEFAULT_STATE, and returns the state dictionary.

    :return Dict[str, Any]: The state of the server.
    """
    f = open(STATE_FILE, "a+")
    f = open(STATE_FILE, "r+")
    try:
        state = json.loads(f.read())
    except json.JSONDecodeError:
        # if we cannot decode, reset the state
        state = DEFAULT_STATE
    logging.debug(f"start state: {json.dumps(state, indent=2)}")
    f.close()

    if state.keys() != DEFAULT_STATE.keys():
        # add any new fields to the state
        state.update({
            key: value
            for key, value in DEFAULT_STATE.items()
            if key not in state
        })
    logging.debug(f"return state: {json.dumps(state, indent=2)}")
    return state

def write_state_file(state):
    """ Writes the given state to the STATE_FILE in JSON format.
    :param state: A dictionary state to write

    :return None:
    """
    f = open(STATE_FILE, "w+")
    logging.debug(f"write state: {json.dumps(state, indent=2)}")
    f.write(json.dumps(state, indent=2))
    f.close()

def update_player(
    state,
    steam_id,
    **kwargs,
):
    """ Updates the given key-values for a player by their steam_id.

    :param state: A dictionary state to update
    :param steam_id: the steam ID of the player to update
    :param **kwargs: Any key value pairs to add to the player's state. Only keys found in
        DEFAULT_PLAYER can be used as key-word args.

    :return None:
    """
    players = state["players"]
    if steam_id not in players:
        # first time seeing steam user, so add them
        players[steam_id] = dict(**DEFAULT_PLAYER)

    # update user with new values
    players[steam_id].update({
        key: value
        for key, value in kwargs.items()
        if key in DEFAULT_PLAYER
    })
    logging.debug(f"players[{steam_id}]: {json.dumps(kwargs, indent=2)}")

def update_character(
    state,
    name,
    **kwargs,
):
    """ Updates the given key-values for a character by their name.

    :param state: A dictionary state to update
    :param name: the name of the character to update
    :param **kwargs: Any key value pairs to add to the character's state. Only keys found in
        DEFAULT_CHARACTER can be used as key-word args.

    :return None:
    """
    characters = state["characters"]
    if name not in characters:
        # first time seeing character, so add them
        characters[name] = dict(**DEFAULT_CHARACTER)

    # update user with new values
    characters[name].update({
        key: value
        for key, value in kwargs.items()
        if key in DEFAULT_CHARACTER
    })
    logging.debug(f"characters[{name}]: {json.dumps(kwargs, indent=2)}")

def update_server(
    state,
    **kwargs,
):
    """ Updates the given key-values for the server.

    :param state: A dictionary state to update
    :param **kwargs: Any key value pairs to add to the server's state. Only keys found in
        DEFAULT_SERVER can be used as key-word args.

    :return None:
    """
    # update server with new values
    state["server"].update({
        key: value
        for key, value in kwargs.items()
        if key in DEFAULT_SERVER
    })
    logging.debug(f"{json.dumps(kwargs, indent=2)}")

def disconnect_all_players(state):
    last_disconnect_epoch = int(time.time())
    last_disconnect = str(datetime.now())

    for _, player in state["players"].items():
        if player["status"] == "playing":
            player["last_disconnect"] = last_disconnect
            player["last_disconnect_epoch"] = last_disconnect_epoch
            player["time_played"] += last_disconnect_epoch - player["last_joined_epoch"]
        player["status"] = "disconnected"
    for _, character in state["characters"].items():
        if character["status"] == "playing":
            character["last_disconnect"] = last_disconnect
            character["last_disconnect_epoch"] = last_disconnect_epoch
            character["time_played"] += last_disconnect_epoch - character["last_joined_epoch"]
        character["status"] = "disconnected"


#=====================
#  LOG LINE PARSERS
#=====================

class LineParser:
    def __init__(self, regex):
        self._regex = regex
        self.discord_message = ""
        self.message_kwargs = {}
        self._datetime_regex = r"(\d+\/\d+\/\d+ \d+:\d+:\d+)(: )"
        self._datetime_format = '%m/%d/%Y %H:%M:%S'

    def match_line_and_exec(self, line, state):
        matched = re.search(self._regex, line)
        if matched:
            logging.debug(f"{type(self).__name__} was matched")
            log_datetime = re.search(self._datetime_regex, line)
            if log_datetime:
                log_datetime = datetime.strptime(log_datetime.group(1), self._datetime_format)
            self.exec_match(matched, log_datetime, state)
            update_server(state, last_parsed_log=line)
            write_state_file(state)
            self.notify_discord()
            return True

        return False

    def exec_match(self, matched, log_datetime, state):
        pass

    def notify_discord(self):
        if self.message_kwargs and self.discord_message and DISCORD:
            requests.post(
                DISCORD,
                json={
                    "content": self.discord_message.format(**self.message_kwargs)
                }
            )
            self.message_kwargs = {}

class ServerStart(LineParser):
    def __init__(self):
        super().__init__(r"DungeonDB Start")
        self.discord_message = "Server is live! Visit {ip}:{port}"

    def exec_match(self, matched, log_datetime, state):
        self.message_kwargs = {
            "ip": SERVER_IP,
            "port": PORT
        }
        update_server(
            state,
            last_turned_on_epoch=int(log_datetime.timestamp()),
            last_turned_on=str(log_datetime)
        )

class CharacterDied(LineParser):
    def __init__(self):
        super().__init__(r"(Got character ZDOID from )(.+)( : 0:0)")
        self.discord_message = "{name} has died! This is death number {deaths}"

    def exec_match(self, matched, log_datetime, state):
        name = matched.group(2)
        update_character(
            state,
            name,
            deaths=state["characters"][name]["deaths"] + 1,
            status="dead"
        )
        self.message_kwargs = {
            "name": name,
            "deaths": state["characters"][name]["deaths"]
        }


class CharacterJoined(LineParser):
    def __init__(self):
        super().__init__(r"(Got character ZDOID from )(.+)( : )([A-Za-z0-9-]{2,})(:[A-Za-z0-9-]+)")

    @staticmethod
    def get_oldest_connected_steam_id(state):
        # get all connected players
        players_connected = [
            steam_id
            for steam_id, player in state["players"].items()
            if player["status"] == "connected"
        ]
        if len(players_connected) > 1:
            # there could be more than one player joining, but let's be nieve and
            # get the oldest connected player
            steam_id, _ = sorted(players_connected.items(), key=lambda x: x[1]["last_joined_epoch"])[0]
            return steam_id
        # only one (or none) player found
        return players_connected[0] if players_connected else None

    def exec_match(self, matched, log_datetime, state):
        # check existing characters for the character
        zdoid = matched.group(4)
        name = matched.group(2)
        character = state["characters"].get(name)
        if not character:
            #new character found, find corresponding player
            steam_id = self.get_oldest_connected_steam_id(state)
            if steam_id:
                update_character(
                    state,
                    name,
                    status="playing",
                    owner_steam_id=steam_id,
                    last_zdoid=zdoid,
                    last_joined_epoch=int(log_datetime.timestamp()),
                    last_joined=str(log_datetime),
                )
                update_player(
                    state,
                    steam_id,
                    last_character=name,
                    status="playing"
                )
            self.discord_message = "A new player has joined! Welcome, {name}!"
            self.message_kwargs = {"name": name}
        elif character["status"] == "disconnected":
            # This character's session has just started
            update_character(
                state,
                name,
                status="playing",
                last_zdoid=zdoid,
                last_joined_epoch=int(log_datetime.timestamp()),
                last_joined=str(log_datetime),
            )
            update_player(
                state,
                state["characters"][name]["owner_steam_id"],
                last_character=name,
                status="playing"
            )
            self.discord_message = "{name} has joined!"
            self.message_kwargs = {"name": name}
        elif character["status"] == "dead":
            update_character(
                state,
                name,
                status="playing",
                last_zdoid=zdoid
            )

class SteamUserJoined(LineParser):
    def __init__(self):
        super().__init__(r"(Got handshake from client )(\d+)")

    def exec_match(self, matched, log_datetime, state):
        steam_id = matched.group(2)
        last_joined_epoch = int(log_datetime.timestamp())
        last_joined = str(log_datetime)
        update_player(
            state,
            steam_id,
            last_joined_epoch=last_joined_epoch,
            last_joined=last_joined,
            status="connected",
        )

class SteamUserBadPassword(LineParser):
    def __init__(self):
        super().__init__(r"(Peer )(\d+)( has wrong password)")

    def exec_match(self, matched, log_datetime, state):
        steam_id = matched.group(2)
        update_player(
            state,
            steam_id,
            status="bad_password",
        )

class SteamUserLeft(LineParser):
    def __init__(self):
        super().__init__(r"(Closing socket )([0-9]+)")

    def exec_match(self, matched, log_datetime, state):
        steam_id = matched.group(2)
        last_disconnect_epoch = int(log_datetime.timestamp())
        last_disconnect = str(log_datetime)
        name = state["players"].get(steam_id, {}).get("last_character", "")

        if state["players"].get(steam_id, {}).get("status") == "bad_password":
            name
            if not name:
                self.discord_message = "A new player attempted to join with a bad password! Their steam ID is {id}"
                self.message_kwargs = {
                    "id": steam_id
                }
            else:
                self.discord_message = "{name} attempted to join with a bad password!"
                self.message_kwargs = {
                    "name": name
                }
            update_player(
                state,
                steam_id,
                last_disconnect_epoch=last_disconnect_epoch,
                last_disconnect=last_disconnect,
                status="disconnected"
            )
            return None

        if not name:
            return None
        self.discord_message = "{name} has disconnected. Their total play time has been {hours}hr {min}m!"
        session_time = last_disconnect_epoch - state["players"].get(steam_id, {}).get(
            "last_joined_epoch", last_disconnect_epoch)
        player_time_played = session_time + state["players"].get(steam_id, {}).get("time_played", 0)
        character_time_played = session_time + state["characters"].get(name, {}).get("time_played", 0)
        update_player(
            state,
            steam_id,
            last_disconnect_epoch=last_disconnect_epoch,
            last_disconnect=last_disconnect,
            time_played=player_time_played,
            status="disconnected"
        )
        update_character(
            state,
            name,
            status="disconnected",
            time_played=character_time_played,
            last_disconnect_epoch=last_disconnect_epoch,
            last_disconnect=last_disconnect,
        )
        hours = int(character_time_played / (60*60))
        self.message_kwargs = {
            "name": name,
            "hours": hours,
            "min": int((character_time_played - (hours * (60*60))) / 60)
        }

#=====================
#  MAIN ENTRYPOINT
#=====================

if __name__ == "__main__":
    parsers = [
        ServerStart(),
        SteamUserJoined(),
        SteamUserBadPassword(),
        CharacterDied(),
        CharacterJoined(),
        SteamUserLeft(),
    ]
    end_message = "Server has been shutdown."

    state = read_state_file()
    # remediate state issues (e.g. no one should be connected, so disconnect everyone)
    disconnect_all_players(state)

    try:
        for line in sys.stdin:
            print(line, end='')
            for parser in parsers:
                if parser.match_line_and_exec(line, state):
                    break
    except KeyboardInterrupt:
        end_message = "Server has been shutdown."
    except Exception:
        end_message = "The parser has been forced to exit"
        logging.error(end_message, exc_info=True)

    if DISCORD:
        requests.post(
            DISCORD,
            json={
                "content": end_message
            }
        )

    # disconneect all players in case of forced shutdown
    disconnect_all_players(state)
    write_state_file(state)
