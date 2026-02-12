-- Migration: Rewrite get_current_puzzle() and get_all_puzzles() from
-- JSON_SEARCH to JSON_TABLE with INT PATH.
--
-- Background:
--   JSON_SEARCH only matches string values in JSON. If solver_id is stored
--   as a JSON number (101), JSON_SEARCH('one', 101) silently returns NULL.
--   JSON_TABLE with INT PATH handles both int and string values via coercion.
--
--   This aligns these two functions with get_current_solvers(),
--   get_all_solvers(), and puzzle_view, which already use JSON_TABLE.
--
-- Safe to re-run: uses DROP FUNCTION IF EXISTS before CREATE.
--
-- Run with:
--   mysql -u puzzleboss -p puzzleboss < scripts/migrations/rewrite_json_search_to_json_table.sql
--
-- Verify with:
--   SELECT get_current_puzzle(101);   -- should return puzzle name or ''
--   SELECT get_all_puzzles(101);      -- should return comma-separated names or ''

DELIMITER //

DROP FUNCTION IF EXISTS get_current_puzzle //
CREATE FUNCTION get_current_puzzle(solver_id INT)
RETURNS TEXT CHARACTER SET utf8mb4
DETERMINISTIC
SQL SECURITY INVOKER
BEGIN
    DECLARE result TEXT CHARACTER SET utf8mb4;
    SELECT p.name INTO result
    FROM puzzle p,
    JSON_TABLE(
        p.current_solvers,
        '$.solvers[*]' COLUMNS (
            sid INT PATH '$.solver_id'
        )
    ) AS jt
    WHERE jt.sid = solver_id
    LIMIT 1;
    RETURN IFNULL(result, '');
END //

DROP FUNCTION IF EXISTS get_all_puzzles //
CREATE FUNCTION get_all_puzzles(solver_id INT)
RETURNS TEXT CHARACTER SET utf8mb4
DETERMINISTIC
SQL SECURITY INVOKER
BEGIN
    DECLARE result TEXT CHARACTER SET utf8mb4;
    SELECT GROUP_CONCAT(DISTINCT p.name) INTO result
    FROM puzzle p,
    JSON_TABLE(
        p.solver_history,
        '$.solvers[*]' COLUMNS (
            sid INT PATH '$.solver_id'
        )
    ) AS jt
    WHERE jt.sid = solver_id;
    RETURN IFNULL(result, '');
END //

DELIMITER ;
