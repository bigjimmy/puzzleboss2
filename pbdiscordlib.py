from pblib import *
import socket
import sys
import json
import re


def chat_create_channel_for_puzzle(puzname, roundname, puzuri, puzdocuri):
    debug_log(
        4,
        "start, called with (puzname, roundname, puzuri, puzdocuri): %s %s %s %s"
        % (puzname, roundname, puzuri, puzdocuri),
    )

    topic = "\nPuzzle: %s \nRound: %s\n" % (puzname, roundname)
    topic += "Puzzle URL: %s \nSheet: %s\n" % (puzuri, puzdocuri)
    
    # Pass the full puzzle name with emojis directly to Discord
    debug_log(4, "Creating Discord channel with name: %s" % puzname)
    retval = call_puzzcord("create_json %s %s" % (puzname, topic))
    debug_log(4, "retval from call_puzzcord is %s" % retval)

    if configstruct["SKIP_PUZZCORD"] == "true":
        debug_log(3, "SKIP_PUZZCORD true. stubbing channel id/uri")
        retval = '{"id":"0xtestchannelid", "url":"http://testdiscordurl.com"}'

    newchaninfo = json.loads(retval)
    return (newchaninfo["id"], newchaninfo["url"])


def chat_announce_round(roundname):
    debug_log(4, "start, called with (roundname): %s" % (roundname))
    return call_puzzcord("%s %s" % ("_round", roundname))


def chat_announce_new(puzname):
    debug_log(4, "start, called with (puzname): %s" % (puzname))
    return call_puzzcord("%s %s" % ("_new", puzname))


def chat_say_something(channel_id, message):
    debug_log(
        4, "start, called with (channel_id, message): %s, %s" % (channel_id, message)
    )
    return call_puzzcord("%s %s %s" % ("message", channel_id, message))


def chat_announce_attention(puzzlename):
    debug_log(4, "start, called with (puzzlename): %s" % puzzlename)
    return call_puzzcord("%s %s" % ("_attention", puzzlename))


def chat_announce_solved(puzzlename):
    debug_log(4, "start, called with (puzzlename): %s" % puzzlename)
    return call_puzzcord("%s %s" % ("_solve", puzzlename))


def call_puzzcord(command):
    debug_log(4, "start, called with (command): %s" % command)
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
        debug_log(4, "response from puzzcord call: %s" % response)
    except socket.timeout:
        debug_log(4, "done waiting for puzzcord return message.")
    finally:
        sock.close()

    return response
