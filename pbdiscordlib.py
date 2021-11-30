from pblib import *
import socket
import sys


def chat_create_channel_for_puzzle(puzname, roundname, puzuri, puzdocuri):
    debug_log(
        4,
        "start, called with (puzname, roundname, puzuri, puzdocuri): %s %s %s %s"
        % (puzname, roundname, puzuri, puzdocuri),
    )

    topic = "\nPuzzle: %s \nRound: %s\n" % (puzname, roundname)
    topic += "Puzzle URL: %s \nSheet: %s\n" % (puzuri, puzdocuri)

    retval = call_puzzcord("%s %s" % (puzname, topic))
    debug_log(4, "retval from call_puzzcord is %s" % retval)

    return ("0xtestchannelid", "http://mychannelidlink")


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
    sock = socket.create_connection((config['PUZZCORD']['PUZZCORD_HOST'], config['PUZZCORD']['PUZZCORD_PORT']), timeout=2)
    response = "error"
    try:
        sock.sendall(bytes(command+'\0','ascii'))
        response = sock.recv(1024).decode('ascii')           
    finally:
        sock.close()

    return response
