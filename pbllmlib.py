"""
PuzzleBoss LLM Library - Natural language query support via Google Gemini

This module provides LLM-powered natural language querying of hunt data.
It uses Google Gemini with function calling to interpret queries and
fetch relevant data. Also includes RAG support for wiki content.
"""

import threading
import fcntl
import os
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

# Optional ChromaDB support for wiki RAG
CHROMADB_AVAILABLE = False
chromadb = None
try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
    debug_log(3, "ChromaDB available for wiki RAG")
except ImportError:
    debug_log(3, "chromadb not installed - wiki search unavailable")

# Global ChromaDB client (lazy initialized)
_chroma_client = None
_wiki_collection = None

# Wiki indexer for RAG (optional)
WIKI_INDEXER_AVAILABLE = False
try:
    from scripts.wiki_indexer import index_wiki, load_config as load_wiki_config

    WIKI_INDEXER_AVAILABLE = True
except ImportError:
    debug_log(3, "wiki_indexer not available - wiki RAG disabled")


def get_gemini_tools():
    """Define tools for Gemini function calling."""
    if not GEMINI_AVAILABLE:
        return []

    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_hunt_summary",
                    description="Get overall hunt status including total puzzles, solved count, open count, metas solved, breakdown by status, AND per-round summary with open/solved counts for each round. Use this to compare rounds.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT, properties={}, required=[]
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_round_status",
                    description="Get the status of all puzzles in a specific round. Returns puzzle names, statuses, answers, current solvers, lastact (last activity of any type), and lastsheetact (last sheet edit).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "round_name": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the round to query",
                            )
                        },
                        required=["round_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_open_puzzles_in_round",
                    description="Get only the open (unsolved) puzzles in a specific round.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "round_name": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the round to query",
                            )
                        },
                        required=["round_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_puzzles_by_tag",
                    description="Get all puzzles that have a specific tag (like 'conundrum', 'logic', 'wordplay', etc).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "tag_name": types.Schema(
                                type=types.Type.STRING,
                                description="The tag to search for",
                            )
                        },
                        required=["tag_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_solver_activity",
                    description="Get solver info by username. Returns: id, name, fullname, chat_uid, chat_name, currently_assigned_puzzle (the ONE puzzle they are working on right now), and puzzle_history (list of ALL puzzles they have ever worked on).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "solver_name": types.Schema(
                                type=types.Type.STRING,
                                description="The username of the solver",
                            )
                        },
                        required=["solver_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_solver_by_id",
                    description="Get solver info by ID number. Returns: id, name, fullname, chat_uid, chat_name, currently_assigned_puzzle, and puzzle_history. Use this when you have a solver_id (e.g., from activity records) and need to find out who that solver is.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "solver_id": types.Schema(
                                type=types.Type.INTEGER,
                                description="The numeric ID of the solver",
                            )
                        },
                        required=["solver_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="search_puzzles",
                    description="Search for puzzles by name pattern.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING,
                                description="The search query (partial name match)",
                            )
                        },
                        required=["query"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_puzzle_activity",
                    description="Get activity information for a specific puzzle. Returns lastact (last activity of any type including status changes, comments, assignments), lastsheetact (last sheet edit specifically), and xyzloc (physical location where puzzle is being worked on). Use this to check when a puzzle was last worked on or edited.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "puzzle_name": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the puzzle",
                            )
                        },
                        required=["puzzle_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_all_data",
                    description="FALLBACK: Get complete hunt data including all rounds and all puzzles with full details. Puzzle fields include: name, status, answer, roundname, sheetcount (number of sheets in spreadsheet), cursolvers, xyzloc (physical location where puzzle is being worked on, e.g. room name or table), comments, ismeta, tags, drive_uri, drive_id, chat_channel_name, lastact (last activity of any type with solver_id, type, and time), lastsheetact (last sheet edit specifically with solver_id, type='revise', and time). Use this when other tools don't have the data needed.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT, properties={}, required=[]
                    ),
                ),
                types.FunctionDeclaration(
                    name="search_wiki",
                    description="Search the team wiki for information about puzzle-solving techniques, team resources, policies, historical knowledge, and general reference material. Use this for questions about 'how to solve X type puzzles', 'what tools do we have for Y', 'team policies', or any general knowledge questions.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING,
                                description="The search query - describe what information you're looking for",
                            )
                        },
                        required=["query"],
                    ),
                ),
            ]
        )
    ]


# ============================================================================
# Tool Implementation Functions
# ============================================================================


def get_all_data(get_all_data_fn):
    """Get complete hunt data - use as fallback when specific tools aren't sufficient."""
    return get_all_data_fn()


def _init_wiki_search(chromadb_path, api_key):
    """Initialize ChromaDB client and collection for wiki search."""
    global _chroma_client, _wiki_collection

    if not CHROMADB_AVAILABLE:
        return None

    if _wiki_collection is not None:
        return _wiki_collection

    try:
        if not chromadb_path:
            debug_log(3, "WIKI_CHROMADB_PATH not configured")
            return None

        if not os.path.exists(chromadb_path):
            debug_log(
                3,
                f"ChromaDB path does not exist: {chromadb_path} - run wiki_indexer.py --full first",
            )
            return None

        # Check if ChromaDB has been initialized (look for chroma.sqlite3)
        chroma_db_file = os.path.join(chromadb_path, "chroma.sqlite3")
        if not os.path.exists(chroma_db_file):
            debug_log(
                3,
                f"ChromaDB not initialized at {chromadb_path} - run wiki_indexer.py --full first",
            )
            return None

        _chroma_client = chromadb.PersistentClient(
            path=chromadb_path, settings=Settings(anonymized_telemetry=False)
        )

        # Try to get existing collection
        try:
            _wiki_collection = _chroma_client.get_collection("wiki_pages")
            debug_log(
                3, f"Wiki collection loaded with {_wiki_collection.count()} documents"
            )
        except Exception:
            debug_log(
                3,
                "Wiki collection 'wiki_pages' not found - run wiki_indexer.py --full first",
            )
            return None

        return _wiki_collection

    except Exception as e:
        debug_log(2, f"Error initializing wiki search: {e}")
        return None


def search_wiki(query, chromadb_path, api_key, n_results=5):
    """Search the wiki for relevant content using semantic search.

    Results are boosted by:
    - Priority pages (marked in WIKI_PRIORITY_PAGES config)
    - Recency (more recently modified pages rank higher)
    """
    if not CHROMADB_AVAILABLE:
        return {"status": "error", "error": "Wiki search not available - chromadb not installed"}

    if not GEMINI_AVAILABLE:
        return {"status": "error", "error": "Wiki search not available - google-genai not installed"}

    collection = _init_wiki_search(chromadb_path, api_key)
    if collection is None:
        return {
            "status": "error",
            "error": "Wiki search not available - wiki has not been indexed yet",
            "results": [],
        }

    try:
        # Create embedding for query using Gemini
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(model="models/gemini-embedding-001", contents=query)
        query_embedding = result.embeddings[0].values

        # Search ChromaDB - fetch more than needed for re-ranking
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results * 3,  # Fetch extra for re-ranking
            include=["documents", "metadatas", "distances"],
        )

        # Format and score results
        wiki_results = []
        if results and results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0

                # Base relevance score (1 - distance, so higher is better)
                base_score = 1 - distance

                # Boost priority pages
                is_priority = metadata.get("is_priority", False)
                priority_boost = 0.15 if is_priority else 0

                # Boost recent pages, penalize old pages
                # Pages older than 3 years are heavily penalized (essentially ignored)
                recency_boost = 0
                last_modified = metadata.get("last_modified", "")
                if last_modified:
                    try:
                        from datetime import datetime

                        mod_date = datetime.fromisoformat(
                            last_modified.replace("Z", "+00:00")
                        )
                        now = datetime.now(mod_date.tzinfo)
                        days_old = (now - mod_date).days
                        if days_old < 30:
                            recency_boost = 0.1
                        elif days_old < 365:
                            recency_boost = 0.05
                        elif days_old < 730:  # 1-2 years old
                            recency_boost = -0.1
                        elif days_old < 1095:  # 2-3 years old
                            recency_boost = -0.3
                        else:  # 3+ years old - heavily penalize
                            recency_boost = -0.8
                    except Exception:
                        pass

                final_score = base_score + priority_boost + recency_boost

                # Skip pages with very low scores (heavily penalized old pages)
                if final_score < 0.1:
                    continue

                wiki_results.append(
                    {
                        "title": metadata.get("title", "Unknown"),
                        "content": doc,
                        "relevance": round(final_score, 3),
                        "is_priority": is_priority,
                        "last_modified": last_modified,
                    }
                )

        # Sort by final score and take top n_results
        wiki_results.sort(key=lambda x: x["relevance"], reverse=True)
        wiki_results = wiki_results[:n_results]

        debug_log(4, f"Wiki search for '{query}' returned {len(wiki_results)} results")

        return {"query": query, "count": len(wiki_results), "results": wiki_results}

    except Exception as e:
        debug_log(2, f"Wiki search error: {e}")
        return {"status": "error", "error": str(e), "results": []}


def get_hunt_summary(get_all_data_fn):
    """Get overall hunt status summary including per-round breakdown."""
    data = get_all_data_fn()
    rounds = data.get("rounds", [])

    total_puzzles = 0
    solved_puzzles = 0
    open_puzzles = 0
    metas_solved = 0
    metas_total = 0
    puzzles_by_status = {}
    rounds_summary = []

    for rnd in rounds:
        round_total = 0
        round_solved = 0
        round_open = 0

        for puzzle in rnd.get("puzzles", []):
            total_puzzles += 1
            round_total += 1
            status = puzzle.get("status", "Unknown")
            puzzles_by_status[status] = puzzles_by_status.get(status, 0) + 1

            if status == "Solved":
                solved_puzzles += 1
                round_solved += 1
            elif status != "[hidden]" and status != "Unnecessary":
                open_puzzles += 1
                round_open += 1

            if puzzle.get("ismeta"):
                metas_total += 1
                if status == "Solved":
                    metas_solved += 1

        rounds_summary.append(
            {
                "name": rnd.get("name"),
                "total_puzzles": round_total,
                "solved_puzzles": round_solved,
                "open_puzzles": round_open,
            }
        )

    return {
        "total_rounds": len(rounds),
        "total_puzzles": total_puzzles,
        "solved_puzzles": solved_puzzles,
        "open_puzzles": open_puzzles,
        "metas_solved": metas_solved,
        "metas_total": metas_total,
        "puzzles_by_status": puzzles_by_status,
        "rounds": rounds_summary,
    }


def get_round_status(round_name, get_all_data_fn):
    """Get status of puzzles in a specific round."""
    data = get_all_data_fn()

    for rnd in data.get("rounds", []):
        if rnd.get("name", "").lower() == round_name.lower():
            puzzles = []
            for puzzle in rnd.get("puzzles", []):
                puzzles.append(
                    {
                        "name": puzzle.get("name"),
                        "status": puzzle.get("status"),
                        "answer": puzzle.get("answer"),
                        "ismeta": puzzle.get("ismeta"),
                        "cursolvers": puzzle.get("cursolvers"),
                        "tags": puzzle.get("tags"),
                        "lastact": puzzle.get("lastact"),  # Last activity of any type
                        "lastsheetact": puzzle.get(
                            "lastsheetact"
                        ),  # Last sheet edit specifically
                    }
                )
            return {
                "round_name": rnd.get("name"),
                "round_status": rnd.get("status"),
                "puzzle_count": len(puzzles),
                "puzzles": puzzles,
            }

    return {"status": "error", "error": f"Round '{round_name}' not found"}


def get_open_puzzles_in_round(round_name, get_all_data_fn):
    """Get open (unsolved) puzzles in a specific round."""
    round_data = get_round_status(round_name, get_all_data_fn)
    if "error" in round_data:
        return round_data

    open_puzzles = [
        p
        for p in round_data["puzzles"]
        if p["status"] not in ["Solved", "[hidden]", "Unnecessary"]
    ]

    return {
        "round_name": round_data["round_name"],
        "open_count": len(open_puzzles),
        "open_puzzles": open_puzzles,
    }


def get_puzzles_by_tag(tag_name, get_tag_id_by_name_fn, get_puzzles_by_tag_id_fn):
    """Get all puzzles with a specific tag using injected functions from pbrest.py."""
    # Find tag ID
    tag_id = get_tag_id_by_name_fn(tag_name)
    if tag_id is None:
        return {"status": "error", "error": f"Tag '{tag_name}' not found", "puzzles": []}

    # Get puzzles with this tag
    puzzles = get_puzzles_by_tag_id_fn(tag_id)

    return {
        "tag": tag_name,
        "count": len(puzzles),
        "puzzles": [
            {
                "name": p["name"],
                "status": p["status"],
                "answer": p["answer"],
                "roundname": p["roundname"],
                "tags": p["tags"],
            }
            for p in puzzles
        ],
    }


def _format_solver_result(solver):
    """Helper to format solver data consistently."""
    puzzles_worked = solver.get("puzzles", "") or ""
    current_puzzle = solver.get("puzz", "")

    return {
        "id": solver.get("id"),
        "name": solver.get("name"),
        "fullname": solver.get("fullname"),
        "chat_uid": solver.get("chat_uid"),
        "chat_name": solver.get("chat_name"),
        # The ONE puzzle they are actively assigned to right now (or null if none)
        "currently_assigned_puzzle": current_puzzle if current_puzzle else None,
        # Historical list of ALL puzzles they have ever worked on
        "puzzle_history": [p.strip() for p in puzzles_worked.split(",") if p.strip()],
        "total_puzzles_in_history": len(
            [p for p in puzzles_worked.split(",") if p.strip()]
        ),
    }


def get_solver_activity(solver_name, cursor):
    """Get solver's info and puzzle history by username."""
    cursor.execute(
        "SELECT * FROM solver_view WHERE LOWER(name) = LOWER(%s)", (solver_name,)
    )
    solver = cursor.fetchone()
    if not solver:
        return {"status": "error", "error": f"Solver '{solver_name}' not found"}

    return _format_solver_result(solver)


def get_solver_by_id(solver_id, get_one_solver_fn):
    """Get solver's info and puzzle history by ID using pbrest function."""
    try:
        result = get_one_solver_fn(solver_id)
        solver = result.get("solver")
        if not solver:
            return {"status": "error", "error": f"Solver with ID {solver_id} not found"}
        return _format_solver_result(solver)
    except Exception:
        return {"status": "error", "error": f"Solver with ID {solver_id} not found"}


def search_puzzles(query, cursor):
    """Search puzzles by name pattern."""
    cursor.execute(
        "SELECT name, status, answer, roundname, tags, cursolvers FROM puzzle_view WHERE LOWER(name) LIKE LOWER(%s)",
        (f"%{query}%",),
    )
    puzzles = cursor.fetchall()

    return {"query": query, "count": len(puzzles), "puzzles": list(puzzles)}


def get_puzzle_activity(
    puzzle_name, get_puzzle_id_by_name_fn, get_one_puzzle_fn, get_last_sheet_activity_fn
):
    """Get activity information for a specific puzzle using injected functions from pbrest.py."""
    # Find puzzle ID by name
    puzzle_id = get_puzzle_id_by_name_fn(puzzle_name)
    if not puzzle_id:
        return {"status": "error", "error": f"Puzzle '{puzzle_name}' not found"}

    # Get full puzzle info (includes lastact)
    puzzle_data = get_one_puzzle_fn(puzzle_id)
    puzzle = puzzle_data["puzzle"]
    lastact = puzzle_data.get("lastact")

    # Get lastsheetact separately (not included in get_one_puzzle)
    lastsheetact = get_last_sheet_activity_fn(puzzle_id)

    return {
        "puzzle_name": puzzle["name"],
        "round_name": puzzle["roundname"],
        "status": puzzle["status"],
        "lastact": lastact,  # Last activity of any type (status change, comment, assignment, etc.)
        "lastsheetact": lastsheetact,  # Last sheet edit (revise type activity)
        "cursolvers": puzzle["cursolvers"],
        "xyzloc": puzzle["xyzloc"],  # Physical location where puzzle is being worked on
    }


def execute_tool(
    tool_name,
    tool_args,
    get_all_data_fn,
    cursor,
    get_last_sheet_activity_fn=None,
    get_puzzle_id_by_name_fn=None,
    get_one_puzzle_fn=None,
    get_one_solver_fn=None,
    get_tag_id_by_name_fn=None,
    get_puzzles_by_tag_id_fn=None,
    wiki_chromadb_path=None,
    api_key=None,
):
    """Execute an LLM tool and return the result."""
    if tool_name == "get_hunt_summary":
        return get_hunt_summary(get_all_data_fn)
    elif tool_name == "get_round_status":
        return get_round_status(tool_args.get("round_name", ""), get_all_data_fn)
    elif tool_name == "get_open_puzzles_in_round":
        return get_open_puzzles_in_round(
            tool_args.get("round_name", ""), get_all_data_fn
        )
    elif tool_name == "get_puzzles_by_tag":
        return get_puzzles_by_tag(
            tool_args.get("tag_name", ""),
            get_tag_id_by_name_fn,
            get_puzzles_by_tag_id_fn,
        )
    elif tool_name == "get_solver_activity":
        return get_solver_activity(tool_args.get("solver_name", ""), cursor)
    elif tool_name == "get_solver_by_id":
        return get_solver_by_id(tool_args.get("solver_id", 0), get_one_solver_fn)
    elif tool_name == "search_puzzles":
        return search_puzzles(tool_args.get("query", ""), cursor)
    elif tool_name == "get_puzzle_activity":
        return get_puzzle_activity(
            tool_args.get("puzzle_name", ""),
            get_puzzle_id_by_name_fn,
            get_one_puzzle_fn,
            get_last_sheet_activity_fn,
        )
    elif tool_name == "get_all_data":
        return get_all_data(get_all_data_fn)
    elif tool_name == "search_wiki":
        return search_wiki(tool_args.get("query", ""), wiki_chromadb_path, api_key)
    else:
        return {"status": "error", "error": f"Unknown tool: {tool_name}"}


# ============================================================================
# Main Query Processing
# ============================================================================


def process_query(
    query_text,
    api_key,
    system_instruction,
    model,
    get_all_data_fn,
    cursor,
    user_id="unknown",
    get_last_sheet_activity_fn=None,
    get_puzzle_id_by_name_fn=None,
    get_one_puzzle_fn=None,
    get_one_solver_fn=None,
    get_tag_id_by_name_fn=None,
    get_puzzles_by_tag_id_fn=None,
    wiki_chromadb_path=None,
):
    """
    Process a natural language query using Google Gemini.

    Args:
        query_text: The natural language query
        api_key: Google Gemini API key
        system_instruction: System prompt for the LLM (required)
        model: Gemini model name (e.g. "gemini-2.0-flash-exp")
        get_all_data_fn: Function that returns all hunt data (rounds/puzzles)
        cursor: Database cursor for direct queries
        user_id: ID of the user making the query (for logging)
        get_last_sheet_activity_fn: Function to get last sheet activity for a puzzle (from pbrest.py)
        get_puzzle_id_by_name_fn: Function to get puzzle ID by name (from pbrest.py)
        get_one_puzzle_fn: Function to get full puzzle info by ID (from pbrest.py)
        get_one_solver_fn: Function to get solver info by ID (from pbrest.py)
        get_tag_id_by_name_fn: Function to get tag ID by name (from pbrest.py)
        get_puzzles_by_tag_id_fn: Function to get puzzles by tag ID (from pbrest.py)
        wiki_chromadb_path: Path to ChromaDB storage for wiki RAG

    Returns:
        dict with 'status', 'response', and 'user_id'
    """
    if not GEMINI_AVAILABLE:
        return {"status": "error", "error": "Google Generative AI SDK not installed"}

    if not api_key:
        return {"status": "error", "error": "GEMINI_API_KEY not configured"}

    if not system_instruction:
        return {"status": "error", "error": "GEMINI_SYSTEM_INSTRUCTION not configured"}

    if not model:
        return {"status": "error", "error": "GEMINI_MODEL not configured"}

    debug_log(3, f"LLM query from user {user_id}: {query_text[:100]}")

    try:
        # Prepend user context to query so LLM knows who is asking
        contextualized_query = (
            f"[The user asking this question is: {user_id}]\n\n{query_text}"
        )

        # Create Gemini client
        client = genai.Client(api_key=api_key)

        # Create config with tools
        config = types.GenerateContentConfig(
            system_instruction=system_instruction, tools=get_gemini_tools()
        )

        # Start chat
        chat = client.chats.create(model=model, config=config)

        response = chat.send_message(contextualized_query)

        # Handle function calling loop
        max_iterations = 10
        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            # Check if there are function calls to handle
            function_calls = []
            if (
                response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
            ):
                for part in response.candidates[0].content.parts:
                    if (
                        hasattr(part, "function_call")
                        and part.function_call
                        and part.function_call.name
                    ):
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
                result = execute_tool(
                    tool_name,
                    tool_args,
                    get_all_data_fn,
                    cursor,
                    get_last_sheet_activity_fn,
                    get_puzzle_id_by_name_fn,
                    get_one_puzzle_fn,
                    get_one_solver_fn,
                    get_tag_id_by_name_fn,
                    get_puzzles_by_tag_id_fn,
                    wiki_chromadb_path,
                    api_key,
                )

                function_responses.append(
                    types.Part.from_function_response(
                        name=tool_name, response={"result": result}
                    )
                )

            # Send function results back to model
            response = chat.send_message(function_responses)

        # Extract final text response
        final_response = ""
        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    final_response += part.text

        debug_log(4, f"LLM response: {final_response[:200]}")

        return {"status": "ok", "response": final_response, "user_id": user_id}

    except Exception as e:
        debug_log(1, f"LLM query error: {str(e)}")
        return {"status": "error", "error": str(e)}


def _run_wiki_index_background():
    """Run wiki indexing in background thread at startup. Uses file lock to prevent multiple workers from indexing."""
    if not WIKI_INDEXER_AVAILABLE:
        return

    try:
        wiki_config = load_wiki_config()
        wiki_url = wiki_config.get("WIKI_URL", "")
        chromadb_path = wiki_config.get(
            "WIKI_CHROMADB_PATH", "/var/lib/puzzleboss/chromadb"
        )

        if not wiki_url:
            debug_log(3, "WIKI_URL not configured - skipping wiki index")
            return

        # Use a lock file to ensure only one worker indexes at a time
        lock_file_path = os.path.join(chromadb_path, ".wiki_index.lock")

        # Ensure directory exists
        os.makedirs(chromadb_path, exist_ok=True)

        try:
            lock_file = open(lock_file_path, "w")
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            debug_log(4, "Another worker is already indexing wiki - skipping")
            return

        try:
            debug_log(3, "Starting background wiki full reindex (acquired lock)...")
            success = index_wiki(wiki_config, full_reindex=True)
            if success:
                debug_log(3, "Background wiki index completed successfully")
            else:
                debug_log(2, "Background wiki index failed")
        finally:
            # Release lock
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    except Exception as e:
        debug_log(2, f"Background wiki index error: {e}")


# Start wiki indexing in background thread (non-blocking)
if WIKI_INDEXER_AVAILABLE:
    wiki_thread = threading.Thread(target=_run_wiki_index_background, daemon=True)
    wiki_thread.start()
