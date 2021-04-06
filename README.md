# Valheim Log Parser and State Management

## Introduction
This is a python log parser designed for Valheim server logs, which tracks the server state and includes notifications (currently via Discord webhooks)

## Outcomes
- Produces a `state.json` file in the directory the parser is called (or at the `STATE_FILE` env-var)
- Produces a `parser_{date}.log` file in the directory the parser is called
- Submits the following messages to discord (if `DISCORD` webhook URL is provided):
    - `Server has been shutdown.`
    - `The parser has been forced to exit`
    - `{name} has disconnected. Their total play time has been {hours}hr {min}m!`
    - `{name} attempted to join with a bad password!`
    - `A new player attempted to join with a bad password! Their steam ID is {id}`
    - `{name} has joined!`
    - `A new player has joined! Welcome, {name}!`
    - `{name} has died! This is death number {deaths}`
    - `Server is live! Visit {ip}:{port}`

## Usage
### Windows
- Prerequisites: Python 3.8 installed (this can be done through the Microsoft Store), and the `requests` python library must be installed via `pip install requests` through a terminal
1. Add the `parser.py` and `sample_bat.bat` files to your valheim server directory
2. The existing `start_headless_server.bat` will need to be updated with `sample_bat.bat`, so update the `sample_bat.bat` with the appropriate:
    - `SERVER_PORT`: The port that the server will be exposed on
    - `DISCORD`: The discord webhook URL to submit notifications to
    - `-name "..."`: The name of the server
    - `-world "..."`: The name of the world
    - `-password "..."`: The password used to connect
3. Replace `start_headless_server.bat` with the newly updated `sample_bat.bat` (you can save a copy of it just in case)
    - **NOTE**: This new BAT will contact opendns for your external IP which others can use to connect to your server on the specified port.
4. Run the server as usual!
