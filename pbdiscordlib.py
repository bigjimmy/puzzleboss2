from pblib import *


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

    # TODO: parse retval here to pull out channelid / link for return tuple

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

    # TODO: Implement piping the command to server and port for puzzcord

    debug_log(4, "TODO: send to puzzcord here: %s" % command)

    # TODO: implement actual shell call to puzzcord and return the output
    return 0
