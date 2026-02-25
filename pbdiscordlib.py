"""Discord (puzzcord) integration — channel creation, announcements, and messaging."""

from pblib import debug_log, configstruct
import socket
import json


def chat_create_channel_for_puzzle(puzname, roundname, puzuri, puzdocuri):
    """Create a Discord channel for a new puzzle and return (channel_id, url)."""
    debug_log(
        4,
        f"start, called with (puzname, roundname, puzuri, puzdocuri): {puzname} {roundname} {puzuri} {puzdocuri}",
    )

    topic = f"\nPuzzle: {puzname} \nRound: {roundname}\n"
    topic += f"Puzzle URL: {puzuri} \nSheet: {puzdocuri}\n"

    # Pass the full puzzle name with emojis directly to Discord
    debug_log(4, f"Creating Discord channel with name: {puzname}")
    try:
        retval = call_puzzcord(f"create_json {puzname} {topic}")
    except (socket.error, socket.timeout, OSError) as e:
        raise RuntimeError(f"Discord (puzzcord) is unreachable: {e}. Set SKIP_PUZZCORD=true in config to disable.") from e
    debug_log(4, f"retval from call_puzzcord is {retval}")

    if configstruct["SKIP_PUZZCORD"] == "true":
        debug_log(3, "SKIP_PUZZCORD true. stubbing channel id/uri")
        retval = '{"id":"0xtestchannelid", "url":"http://testdiscordurl.com"}'

    try:
        newchaninfo = json.loads(retval)
    except (json.JSONDecodeError, TypeError):
        raise RuntimeError(f"Discord (puzzcord) returned invalid response: {retval!r}. Is puzzcord running?")
    return (newchaninfo["id"], newchaninfo["url"])


def chat_announce_round(roundname):
    """Announce a new round in Discord."""
    debug_log(4, f"start, called with (roundname): {roundname}")
    return call_puzzcord(f"_round {roundname}")


def chat_announce_new(puzname):
    """Announce a new puzzle in Discord."""
    debug_log(4, f"start, called with (puzname): {puzname}")
    return call_puzzcord(f"_new {puzname}")


def chat_say_something(channel_id, message):
    """Send a message to a specific Discord channel."""
    debug_log(4, f"start, called with (channel_id, message): {channel_id}, {message}")
    return call_puzzcord(f"message {channel_id} {message}")


def chat_announce_attention(puzzlename):
    """Announce a puzzle needs attention in Discord."""
    debug_log(4, f"start, called with (puzzlename): {puzzlename}")
    return call_puzzcord(f"_attention {puzzlename}")


def chat_announce_solved(puzzlename):
    """Announce a puzzle has been solved in Discord."""
    debug_log(4, f"start, called with (puzzlename): {puzzlename}")
    return call_puzzcord(f"_solve {puzzlename}")


def chat_announce_move(puzzlename):
    """Announce a puzzle has been moved to a new round in Discord."""
    debug_log(4, f"start, called with (puzzlename): {puzzlename}")
    return call_puzzcord(f"_move {puzzlename}")


def call_puzzcord(command):
    """Send a command to the puzzcord daemon via socket and return its response."""
    debug_log(4, f"start, called with (command): {command}")
    if configstruct["SKIP_PUZZCORD"] == "true":
        return "OK"

    sock = socket.create_connection(
        (configstruct["PUZZCORD_HOST"], configstruct["PUZZCORD_PORT"]),
        timeout=2,
    )
    response = "error"
    # Send command to puzzcord
    try:
        sock.sendall(bytes(command, "utf-8"))
        sock.shutdown(socket.SHUT_WR)
    except socket.error:
        debug_log(0, "Sending command to puzzcord FAILED. Is puzzcord client down?")
        sock.close()
        return "error"
    # Await and record response from puzzcord
    try:
        response = sock.recv(1024).decode("utf-8")
        debug_log(4, f"response from puzzcord call: {response}")
    except socket.timeout:
        debug_log(4, "done waiting for puzzcord return message.")
    finally:
        sock.close()

    return response
