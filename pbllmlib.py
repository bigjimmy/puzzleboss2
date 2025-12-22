"""
PuzzleBoss LLM Library - Natural language query support via Google Gemini

This module provides LLM-powered natural language querying of hunt data.
It uses Google Gemini with function calling to interpret queries and
fetch relevant data.
"""

from pblib import debug_log

# Optional Google Gemini support for LLM queries
GEMINI_AVAILABLE = False
genai = None
types = None
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
    debug_log(3, "google-genai SDK available for LLM queries")
except ImportError:
    debug_log(3, "google-genai not installed - /v1/query endpoint unavailable")


def get_gemini_tools():
    """Define tools for Gemini function calling."""
    if not GEMINI_AVAILABLE:
        return []
    
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_hunt_summary",
                    description="Get overall hunt status including total puzzles, solved count, open count, metas solved, and breakdown by status.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={},
                        required=[]
                    )
                ),
                types.FunctionDeclaration(
                    name="get_round_status",
                    description="Get the status of all puzzles in a specific round. Returns puzzle names, statuses, answers, and current solvers.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "round_name": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the round to query"
                            )
                        },
                        required=["round_name"]
                    )
                ),
                types.FunctionDeclaration(
                    name="get_open_puzzles_in_round",
                    description="Get only the open (unsolved) puzzles in a specific round.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "round_name": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the round to query"
                            )
                        },
                        required=["round_name"]
                    )
                ),
                types.FunctionDeclaration(
                    name="get_puzzles_by_tag",
                    description="Get all puzzles that have a specific tag (like 'conundrum', 'logic', 'wordplay', etc).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "tag_name": types.Schema(
                                type=types.Type.STRING,
                                description="The tag to search for"
                            )
                        },
                        required=["tag_name"]
                    )
                ),
                types.FunctionDeclaration(
                    name="get_solver_activity",
                    description="Get information about what puzzles a specific solver/user has worked on.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "solver_name": types.Schema(
                                type=types.Type.STRING,
                                description="The username of the solver"
                            )
                        },
                        required=["solver_name"]
                    )
                ),
                types.FunctionDeclaration(
                    name="search_puzzles",
                    description="Search for puzzles by name pattern.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING,
                                description="The search query (partial name match)"
                            )
                        },
                        required=["query"]
                    )
                ),
            ]
        )
    ]


# ============================================================================
# Tool Implementation Functions
# ============================================================================

def get_hunt_summary(get_all_data_fn):
    """Get overall hunt status summary."""
    data = get_all_data_fn()
    rounds = data.get("rounds", [])
    
    total_puzzles = 0
    solved_puzzles = 0
    open_puzzles = 0
    metas_solved = 0
    metas_total = 0
    puzzles_by_status = {}
    
    for round in rounds:
        for puzzle in round.get("puzzles", []):
            total_puzzles += 1
            status = puzzle.get("status", "Unknown")
            puzzles_by_status[status] = puzzles_by_status.get(status, 0) + 1
            
            if status == "Solved":
                solved_puzzles += 1
            elif status != "[hidden]" and status != "Unnecessary":
                open_puzzles += 1
            
            if puzzle.get("ismeta"):
                metas_total += 1
                if status == "Solved":
                    metas_solved += 1
    
    return {
        "total_rounds": len(rounds),
        "total_puzzles": total_puzzles,
        "solved_puzzles": solved_puzzles,
        "open_puzzles": open_puzzles,
        "metas_solved": metas_solved,
        "metas_total": metas_total,
        "puzzles_by_status": puzzles_by_status
    }


def get_round_status(round_name, get_all_data_fn):
    """Get status of puzzles in a specific round."""
    data = get_all_data_fn()
    
    for round in data.get("rounds", []):
        if round.get("name", "").lower() == round_name.lower():
            puzzles = []
            for puzzle in round.get("puzzles", []):
                puzzles.append({
                    "name": puzzle.get("name"),
                    "status": puzzle.get("status"),
                    "answer": puzzle.get("answer"),
                    "ismeta": puzzle.get("ismeta"),
                    "cursolvers": puzzle.get("cursolvers"),
                    "tags": puzzle.get("tags")
                })
            return {
                "round_name": round.get("name"),
                "round_status": round.get("status"),
                "puzzle_count": len(puzzles),
                "puzzles": puzzles
            }
    
    return {"error": f"Round '{round_name}' not found"}


def get_open_puzzles_in_round(round_name, get_all_data_fn):
    """Get open (unsolved) puzzles in a specific round."""
    round_data = get_round_status(round_name, get_all_data_fn)
    if "error" in round_data:
        return round_data
    
    open_puzzles = [p for p in round_data["puzzles"] 
                    if p["status"] not in ["Solved", "[hidden]", "Unnecessary"]]
    
    return {
        "round_name": round_data["round_name"],
        "open_count": len(open_puzzles),
        "open_puzzles": open_puzzles
    }


def get_puzzles_by_tag(tag_name, cursor):
    """Get all puzzles with a specific tag."""
    # Find tag ID
    cursor.execute("SELECT id FROM tag WHERE LOWER(name) = LOWER(%s)", (tag_name,))
    tag_row = cursor.fetchone()
    if not tag_row:
        return {"error": f"Tag '{tag_name}' not found", "puzzles": []}
    
    tag_id = tag_row["id"]
    
    # Find puzzles with this tag
    cursor.execute(
        "SELECT * FROM puzzle_view WHERE %s MEMBER OF(tags)",
        (tag_id,)
    )
    puzzles = cursor.fetchall()
    
    return {
        "tag": tag_name,
        "count": len(puzzles),
        "puzzles": [{"name": p["name"], "status": p["status"], "answer": p["answer"], 
                     "roundname": p["roundname"], "tags": p["tags"]} for p in puzzles]
    }


def get_solver_activity(solver_name, cursor):
    """Get puzzles a solver has worked on."""
    # Find solver
    cursor.execute("SELECT * FROM solver_view WHERE LOWER(name) = LOWER(%s)", (solver_name,))
    solver = cursor.fetchone()
    if not solver:
        return {"error": f"Solver '{solver_name}' not found"}
    
    # Get their puzzle history
    puzzles_worked = solver.get("puzzles", "") or ""
    current_puzzle = solver.get("puzz", "")
    
    result = {
        "solver_name": solver.get("name"),
        "fullname": solver.get("fullname"),
        "current_puzzle": current_puzzle if current_puzzle else None,
        "puzzles_worked_on": [p.strip() for p in puzzles_worked.split(",") if p.strip()],
        "total_puzzles_worked": len([p for p in puzzles_worked.split(",") if p.strip()])
    }
    
    return result


def search_puzzles(query, cursor):
    """Search puzzles by name pattern."""
    cursor.execute(
        "SELECT name, status, answer, roundname, tags, cursolvers FROM puzzle_view WHERE LOWER(name) LIKE LOWER(%s)",
        (f"%{query}%",)
    )
    puzzles = cursor.fetchall()
    
    return {
        "query": query,
        "count": len(puzzles),
        "puzzles": list(puzzles)
    }


def execute_tool(tool_name, tool_args, get_all_data_fn, cursor):
    """Execute an LLM tool and return the result."""
    if tool_name == "get_hunt_summary":
        return get_hunt_summary(get_all_data_fn)
    elif tool_name == "get_round_status":
        return get_round_status(tool_args.get("round_name", ""), get_all_data_fn)
    elif tool_name == "get_open_puzzles_in_round":
        return get_open_puzzles_in_round(tool_args.get("round_name", ""), get_all_data_fn)
    elif tool_name == "get_puzzles_by_tag":
        return get_puzzles_by_tag(tool_args.get("tag_name", ""), cursor)
    elif tool_name == "get_solver_activity":
        return get_solver_activity(tool_args.get("solver_name", ""), cursor)
    elif tool_name == "search_puzzles":
        return search_puzzles(tool_args.get("query", ""), cursor)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ============================================================================
# Main Query Processing
# ============================================================================

def process_query(query_text, api_key, system_instruction, get_all_data_fn, cursor, user_id="unknown"):
    """
    Process a natural language query using Google Gemini.
    
    Args:
        query_text: The natural language query
        api_key: Google Gemini API key
        system_instruction: System prompt for the LLM (required)
        get_all_data_fn: Function that returns all hunt data (rounds/puzzles)
        cursor: Database cursor for direct queries
        user_id: ID of the user making the query (for logging)
    
    Returns:
        dict with 'status', 'response', and 'user_id'
    """
    if not GEMINI_AVAILABLE:
        return {"status": "error", "error": "Google Generative AI SDK not installed"}
    
    if not api_key:
        return {"status": "error", "error": "GEMINI_API_KEY not configured"}
    
    if not system_instruction:
        return {"status": "error", "error": "GEMINI_SYSTEM_INSTRUCTION not configured"}
    
    debug_log(3, f"LLM query from user {user_id}: {query_text[:100]}")
    
    try:
        # Prepend user context to query so LLM knows who is asking
        contextualized_query = f"[The user asking this question is: {user_id}]\n\n{query_text}"
        
        # Create Gemini client
        client = genai.Client(api_key=api_key)
        
        # Create config with tools
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=get_gemini_tools()
        )
        
        # Start chat
        chat = client.chats.create(
            model="gemini-2.0-flash-exp",
            config=config
        )
        
        response = chat.send_message(contextualized_query)
        
        # Handle function calling loop
        max_iterations = 10
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            # Check if there are function calls to handle
            function_calls = []
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                        function_calls.append(part)
            
            if not function_calls:
                break
            
            # Execute function calls and collect results
            function_responses = []
            for part in function_calls:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                
                debug_log(4, f"LLM calling tool: {tool_name} with {tool_args}")
                result = execute_tool(tool_name, tool_args, get_all_data_fn, cursor)
                
                function_responses.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": result}
                    )
                )
            
            # Send function results back to model
            response = chat.send_message(function_responses)
        
        # Extract final text response
        final_response = ""
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    final_response += part.text
        
        debug_log(4, f"LLM response: {final_response[:200]}")
        
        return {
            "status": "ok",
            "response": final_response,
            "user_id": user_id
        }
        
    except Exception as e:
        debug_log(1, f"LLM query error: {str(e)}")
        return {"status": "error", "error": str(e)}
