from flask_restx import Namespace, fields

# Namespaces
puzzle_ns = Namespace('puzzles', description='Puzzle operations')
round_ns = Namespace('rounds', description='Round operations')
solver_ns = Namespace('solvers', description='Solver operations')
rbac_ns = Namespace('rbac', description='RBAC operations')
account_ns = Namespace('account', description='Account operations')
config_ns = Namespace('config', description='Configuration operations')

# Models
puzzle_model = puzzle_ns.model('Puzzle', {
    'id': fields.Integer(description='Puzzle ID'),
    'name': fields.String(description='Puzzle name'),
    'status': fields.String(description='Status category of puzzle', 
        enum=['New', 'Being worked', 'Needs eyes', 'Solved', 'Critical', 'WTF', 'Unnecessary']),
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
    'xyzloc': fields.String(description='Location where puzzle is being worked on')
})

puzzle_list_model = puzzle_ns.model('PuzzleList', {
    'puzzles': fields.List(fields.Nested(puzzle_model))
})

round_model = round_ns.model('Round', {
    'id': fields.Integer(description='Round ID'),
    'name': fields.String(description='Round name'),
    'drive_uri': fields.String(description='URI of google folder for round'),
    'meta_id': fields.Integer(description='ID of puzzle that is this round\'s meta'),
    'round_uri': fields.String(description='URI of page where this round is'),
    'puzzles': fields.List(fields.Nested(puzzle_model))
})

round_list_model = round_ns.model('RoundList', {
    'rounds': fields.List(fields.Nested(round_model))
})

solver_model = solver_ns.model('Solver', {
    'id': fields.Integer(description='Solver ID'),
    'name': fields.String(description='Solver short name'),
    'fullname': fields.String(description='Solver long name'),
    'puzz': fields.Integer(description='ID number of puzzle solver is currently working on'),
    'puzzles': fields.String(description='Comma separated list of puzzle ids for all puzzles solver has worked on'),
    'chat_uid': fields.String(description='ID number for solver\'s chat presence'),
    'chat_name': fields.String(description='Name of solver\'s chat presence')
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