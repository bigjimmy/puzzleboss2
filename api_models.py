from flask_restx import Namespace, fields

# Namespaces
puzzle_ns = Namespace('puzzles', description='Puzzle operations')
round_ns = Namespace('rounds', description='Round operations')
solver_ns = Namespace('solvers', description='Solver operations')
rbac_ns = Namespace('rbac', description='RBAC operations')
account_ns = Namespace('account', description='Account operations')
config_ns = Namespace('config', description='Configuration operations')

# Sub-models
solver_info_model = puzzle_ns.model('SolverInfo', {
    'solver_id': fields.Integer(description='ID of the solver')
})

solvers_list_model = puzzle_ns.model('SolversList', {
    'solvers': fields.List(fields.Nested(solver_info_model))
})

activity_model = puzzle_ns.model('Activity', {
    'id': fields.Integer(description='Activity ID'),
    'time': fields.DateTime(description='Timestamp of activity'),
    'solver_id': fields.Integer(description='ID of solver who performed activity'),
    'puzzle_id': fields.Integer(description='ID of puzzle activity was performed on'),
    'source': fields.String(description='Source of activity', 
        enum=['google', 'pb_auto', 'pb_manual', 'bigjimmy', 'twiki', 'squid', 'apache', 'xmpp']),
    'type': fields.String(description='Type of activity',
        enum=['create', 'open', 'revise', 'comment', 'interact']),
    'uri': fields.String(description='URI associated with activity'),
    'source_version': fields.Integer(description='Version of source')
})

# Models
puzzle_model = puzzle_ns.model('Puzzle', {
    'id': fields.Integer(description='Puzzle ID'),
    'name': fields.String(description='Puzzle name'),
    'status': fields.String(description='Status category of puzzle', 
        enum=['New', 'Being worked', 'Needs eyes', 'Solved', 'Critical', 'WTF', 'Unnecessary', '[hidden]']),
    'answer': fields.String(description='Answer of puzzle (if solved)'),
    'roundname': fields.String(description='Name of round that puzzle is in'),
    'round_id': fields.Integer(description='ID of round that puzzle is in'),
    'comments': fields.String(description='Free-form comments field'),
    'drive_uri': fields.String(description='URI of google sheet for puzzle'),
    'chat_channel_name': fields.String(description='Name of puzzle\'s chat channel'),
    'chat_channel_id': fields.String(description='ID number of puzzle\'s chat channel'),
    'chat_channel_link': fields.String(description='HTML A tag for linking to puzzle\'s chat channel'),
    'drive_id': fields.String(description='Google drive id string for puzzle\'s google sheet'),
    'puzzle_uri': fields.String(description='URI pointing to the original puzzle page'),
    'cursolvers': fields.String(description='Comma-separated list of all solvers currently working on puzzle'),
    'solvers': fields.String(description='Comma-separated list of all solvers ever working on puzzle'),
    'xyzloc': fields.String(description='Location where puzzle is being worked on'),
    'current_solvers': fields.Nested(solvers_list_model, description='JSON structure of current solvers'),
    'solver_history': fields.Nested(solvers_list_model, description='JSON structure of solver history'),
    'ismeta': fields.Boolean(description='Whether this puzzle is a meta puzzle'),
    'lastact': fields.Nested(activity_model, description='Last activity performed on this puzzle')
})

# Model for POST operations (excludes read-only fields)
puzzle_post_model = puzzle_ns.model('PuzzlePost', {
    'name': fields.String(required=True, description='Puzzle name'),
    'status': fields.String(description='Status category of puzzle', 
        enum=['New', 'Being worked', 'Needs eyes', 'Solved', 'Critical', 'WTF', 'Unnecessary', '[hidden]']),
    'answer': fields.String(description='Answer of puzzle (if solved)'),
    'round_id': fields.Integer(required=True, description='ID of round that puzzle is in'),
    'comments': fields.String(description='Free-form comments field'),
    'puzzle_uri': fields.String(required=True, description='URI pointing to the original puzzle page'),
    'xyzloc': fields.String(description='Location where puzzle is being worked on'),
    'ismeta': fields.Boolean(description='Whether this puzzle is a meta puzzle')
})

puzzle_list_model = puzzle_ns.model('PuzzleList', {
    'puzzles': fields.List(fields.Nested(puzzle_model))
})

round_model = round_ns.model('Round', {
    'id': fields.Integer(description='Round ID'),
    'name': fields.String(description='Round name'),
    'drive_uri': fields.String(description='URI of google folder for round'),
    'drive_id': fields.String(description='Google drive id string for round\'s folder'),
    'meta_id': fields.Integer(description='ID of puzzle that is this round\'s meta'),
    'round_uri': fields.String(description='URI of page where this round is'),
    'comments': fields.String(description='Free-form comments field'),
    'status': fields.String(description='Status of the round', 
        enum=['New', 'Being worked', 'Needs eyes', 'Solved', 'Critical', 'WTF', 'Unnecessary', '[hidden]']),
    'puzzles': fields.List(fields.Nested(puzzle_model))
})

round_list_model = round_ns.model('RoundList', {
    'rounds': fields.List(fields.Nested(round_model))
})

solver_model = solver_ns.model('Solver', {
    'id': fields.Integer(description='Solver ID'),
    'name': fields.String(description='Solver short name'),
    'fullname': fields.String(description='Solver long name'),
    'puzz': fields.String(description='Name of puzzle solver is currently working on'),
    'puzzles': fields.String(description='Comma separated list of puzzle names for all puzzles solver has worked on'),
    'chat_uid': fields.String(description='ID number for solver\'s chat presence'),
    'chat_name': fields.String(description='Name of solver\'s chat presence'),
    'lastact': fields.Nested(activity_model, description='Last activity performed by this solver')
})

solver_list_model = solver_ns.model('SolverList', {
    'solvers': fields.List(fields.Nested(solver_model))
})

new_account_model = account_ns.model('NewAccount', {
    'username': fields.String(required=True, description='Username'),
    'fullname': fields.String(required=True, description='Full name'),
    'email': fields.String(required=True, description='Email address'),
    'password': fields.String(required=True, description='Password'),
    'reset': fields.String(description='Set to "reset" for password reset')
})

rbac_model = rbac_ns.model('RBAC', {
    'allowed': fields.String(required=True, enum=['YES', 'NO'], description='YES to allow, NO to disallow')
})

config_model = config_ns.model('Config', {
    'cfgkey': fields.String(required=True, description='Configuration key'),
    'cfgval': fields.String(required=True, description='Configuration value')
}) 