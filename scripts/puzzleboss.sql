-- mysql puzzleboss schema 2025

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


--
-- Table structure for table `activity`
--

DROP TABLE IF EXISTS `activity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `solver_id` int(11) NOT NULL,
  `puzzle_id` int(11) DEFAULT NULL,
  `source` enum('google','puzzleboss','bigjimmybot','discord') DEFAULT NULL,
  `type` enum('create','revise','comment','interact','solve') DEFAULT NULL,
  `uri` text,
  `source_version` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_google_activity_solver1_idx` (`solver_id`),
  KEY `fk_google_activity_puzzle1_idx` (`puzzle_id`),
  KEY `time` (`time`),
  KEY `puzzle_id` (`puzzle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `newuser`
--

DROP TABLE IF EXISTS `newuser`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `newuser` (
  `username` varchar(100) NOT NULL,
  `fullname` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(100) NOT NULL,
  `code` varchar(8) NOT NULL,
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `temp_puzzle_creation`
-- Temporary storage for puzzle creation requests during step-by-step processing
--

DROP TABLE IF EXISTS `temp_puzzle_creation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `temp_puzzle_creation` (
  `code` varchar(16) NOT NULL,
  `name` varchar(255) NOT NULL,
  `round_id` int(11) NOT NULL,
  `puzzle_uri` text NOT NULL,
  `ismeta` tinyint(1) NOT NULL DEFAULT '0',
  `is_speculative` tinyint(1) NOT NULL DEFAULT '0',
  `chat_channel_id` varchar(255) DEFAULT NULL,
  `chat_channel_link` text DEFAULT NULL,
  `drive_id` varchar(255) DEFAULT NULL,
  `drive_uri` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`code`),
  KEY `fk_temp_puzzle_round` (`round_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clientindex`
--

DROP TABLE IF EXISTS `clientindex`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `clientindex` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `botstats`
--

DROP TABLE IF EXISTS `botstats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `botstats` (
  `key` varchar(100) NOT NULL,
  `val` varchar(500) DEFAULT NULL,
  `updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tag`
--

DROP TABLE IF EXISTS `tag`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `tag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_UNIQUE` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `config`
--

DROP TABLE IF EXISTS `config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `config` (
  `key` varchar(100) NOT NULL,
  `val` varchar(8192) DEFAULT NULL,
  PRIMARY KEY (`key`),
  UNIQUE KEY `key_UNIQUE` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `config` WRITE;
/*!40000 ALTER TABLE `config` DISABLE KEYS */;
INSERT INTO `config` VALUES
  ('ACCT_URI', 'https://yourdomain.org/account'),
  ('BIN_URI', 'https://yourdomain.org/pb'),
  ('BIGJIMMY_ABANDONED_STATUS', 'Abandoned'),
  ('BIGJIMMY_ABANDONED_TIMEOUT_MINUTES', '10'),
  ('BIGJIMMY_AUTOASSIGN', 'false'),
  ('BIGJIMMY_PUZZLEPAUSETIME', '1'),
  ('BIGJIMMY_QUOTAFAIL_DELAY', '5'),
  ('BIGJIMMY_QUOTAFAIL_MAX_RETRIES', '10'),
  ('BIGJIMMY_THREADCOUNT', '2'),
  ('bookmarklet_js', 'javascript:puzzurl=location.href.split(''#'')[0];puzzid=(document.querySelector(''header h1 span'')?.innerText || document.title.replace(/ - Google Docs$/, ''''));roundname=Object.values(window.initialTeamState.rounds).find(r => Object.values(r.slots).some(p => p.slug===window.puzzleSlug))?.title?.replace(/[^A-Za-z0-9]+/g, '''');pbPath=`addpuzzle.php?puzzurl=${encodeURIComponent(puzzurl)}&puzzid=${encodeURIComponent(puzzid)}&roundname=${encodeURIComponent(roundname)}`;window.open(''<<>>''+pbPath);'),
  ('DISCORD_EMAIL_WEBHOOK', ''),
  ('DOMAINNAME', 'example.org'),
  ('GEMINI_API_KEY', ''),
  ('GEMINI_MODEL', 'gemini-3-flash-preview'),
  ('GEMINI_SYSTEM_INSTRUCTION', 'You are a helpful assistant for a puzzle hunt team. You have access to tools to query hunt status, puzzle information, and solver activity. RULES: 1. Always use your tools proactively - never say you cannot answer without trying first. 2. Use get_all_data as a fallback when unsure which tool has the data. 3. Never ask for permission to use tools - just use them. 4. Give complete answers - if you mention something exists, identify it by name. 5. When recommending puzzles, always provide the actual puzzle name(s). When answering: Be concise and direct. Format lists clearly. The hunt has rounds containing puzzles. Statuses: New, Being worked, Needs eyes, Solved, Critical, WTF, Unnecessary, Under control, Waiting for HQ, Grind, Abandoned. Puzzles can have tags like conundrum, logic, wordplay.'),
  ('HUNT_FOLDER_NAME', 'Hunt 2999'),
  ('LOGLEVEL', '3'),
  ('MAILRELAY', 'mail-server.yourdomain.org'),
  ('MEMCACHE_ENABLED', 'false'),
  ('MEMCACHE_HOST', ''),
  ('MEMCACHE_PORT', '11211'),
  ('PUZZCORD_HOST', 'puzzcord-server.example.org'),
  ('PUZZCORD_PORT', '3141'),
  ('REGEMAIL', 'admin@yourdomain.org'),
  ('SHEETS_TEMPLATE_ID', 'xxxxxxxxxxxxxxxxxxxxxxi'),
  ('SKIP_GOOGLE_API', 'true'),
  ('SKIP_PUZZCORD', 'true'),
  ('STATUS_METADATA', '[{"name":"WTF","emoji":"☢️","text":"?","order":0},{"name":"Critical","emoji":"⚠️","text":"!","order":1},{"name":"Needs eyes","emoji":"👀","text":"E","order":2},{"name":"Being worked","emoji":"🙇","text":"W","order":3},{"name":"Speculative","emoji":"🔮","text":"S","order":4},{"name":"Under control","emoji":"🤝","text":"U","order":5},{"name":"New","emoji":"🆕","text":"N","order":6},{"name":"Grind","emoji":"⛏️","text":"G","order":7},{"name":"Waiting for HQ","emoji":"⌛","text":"H","order":8},{"name":"Abandoned","emoji":"🏳️","text":"A","order":9},{"name":"Solved","emoji":"✅","text":"*","order":10},{"name":"Unnecessary","emoji":"🙃","text":"X","order":11},{"name":"[hidden]","emoji":"👻","text":"H","order":99}]'),
  ('METRICS_METADATA', '{"bigjimmy_loop_time_seconds":{"type":"gauge","description":"Total time in seconds for last full puzzle scan loop (setup + processing)","db_key":"loop_time_seconds"},"bigjimmy_loop_setup_seconds":{"type":"gauge","description":"Time in seconds for loop setup (API fetch, thread creation)","db_key":"loop_setup_seconds"},"bigjimmy_loop_processing_seconds":{"type":"gauge","description":"Time in seconds for actual puzzle processing","db_key":"loop_processing_seconds"},"bigjimmy_loop_puzzle_count":{"type":"gauge","description":"Number of puzzles processed in last loop","db_key":"loop_puzzle_count"},"bigjimmy_avg_seconds_per_puzzle":{"type":"gauge","description":"Average processing seconds per puzzle in last loop","db_key":"loop_avg_seconds_per_puzzle"},"bigjimmy_quota_failures":{"type":"counter","description":"Total Google API quota failures (429 errors) since bot start","db_key":"quota_failures"},"bigjimmy_loop_iterations_total":{"type":"counter","description":"Total number of loop iterations completed (resets on bot restart)","db_key":"loop_iterations_total"},"cache_hits_total":{"type":"counter","description":"Total cache hits for /allcached endpoint"},"cache_misses_total":{"type":"counter","description":"Total cache misses for /allcached endpoint"},"cache_invalidations_total":{"type":"counter","description":"Total cache invalidations"},"tags_assigned_total":{"type":"counter","description":"Total tags assigned to puzzles"},"puzzcord_members_total":{"type":"gauge","description":"Total number of Discord team members (with member role)"},"puzzcord_members_online":{"type":"gauge","description":"Number of Discord team members online (according to Discord)"},"puzzcord_members_active_in_voice":{"type":"gauge","description":"Number of team members currently active in voice on Discord"},"puzzcord_members_active_in_text":{"type":"gauge","description":"Number of team members active in text on Discord in the last 15 minutes"},"puzzcord_members_active_in_sheets":{"type":"gauge","description":"Number of team members active in Sheets in the last 15 minutes"},"puzzcord_members_active_in_discord":{"type":"gauge","description":"Number of team members currently active in voice OR active in text in the last 15 minutes"},"puzzcord_members_active_anywhere":{"type":"gauge","description":"Number of team members currently active in voice OR active in (text OR Sheets) in the last 15 minutes"},"puzzcord_members_active_in_person":{"type":"gauge","description":"Number of in-person team members currently active in voice OR active in (text OR Sheets) in the last 15 minutes"},"puzzcord_messages_per_minute":{"type":"gauge","description":"Discord messages per minute"},"puzzcord_tables_in_use":{"type":"gauge","description":"Discord tables (voice channels) in use"}}'),
  ('TEAMNAME', 'Default Team Name'),
  ('WIKI_CHROMADB_PATH', '/var/lib/puzzleboss/chromadb'),
  ('WIKI_EXCLUDE_PREFIXES', ''),
  ('WIKI_PRIORITY_PAGES', 'Main Page'),
  ('WIKI_URL', 'https://localhost/wiki/');
/*!40000 ALTER TABLE `config` ENABLE KEYS */;
UNLOCK TABLES;


--
-- Table structure for table `log`
--


--
-- Table structure for table `privs`
--

DROP TABLE IF EXISTS `privs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `privs` (
  `uid` int(11) NOT NULL,
  `puzztech` enum('NO','YES') NOT NULL DEFAULT 'NO',
  `puzzleboss` enum('NO','YES') NOT NULL DEFAULT 'NO',
  PRIMARY KEY (`uid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `puzzle`
--

DROP TABLE IF EXISTS `puzzle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `puzzle` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `puzzle_uri` text,
  `drive_uri` varchar(255) DEFAULT NULL,
  `chat_channel_id` varchar(500) DEFAULT NULL,
  `chat_channel_link` varchar(255) DEFAULT NULL,
  `comments` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `status` enum('New','Being worked','Needs eyes','Solved','Critical','Unnecessary','WTF','Under control','Waiting for HQ','Grind','Abandoned','Speculative','[hidden]') NOT NULL,
  `answer` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `round_id` int(11) NOT NULL,
  `drive_id` varchar(100) DEFAULT NULL,
  `xyzloc` varchar(500) DEFAULT NULL,
  `chat_channel_name` varchar(300) DEFAULT NULL,
  `ismeta` tinyint(1) NOT NULL DEFAULT 0,
  `current_solvers` JSON DEFAULT NULL,
  `solver_history` JSON DEFAULT NULL,
  `sheetcount` int(11) DEFAULT NULL,
  `sheetenabled` tinyint(1) NOT NULL DEFAULT 0,
  `tags` JSON DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_UNIQUE` (`name`),
  KEY `fk_puzzles_rounds1_idx` (`round_id`),
  KEY `idx_puzzle_tags` ((CAST(tags->'$[*]' AS UNSIGNED ARRAY)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Remove legacy tables and views
--

DROP TABLE IF EXISTS `puzzle_cursolver_distinct`;
DROP TABLE IF EXISTS `puzzle_cursolvers`;
DROP TABLE IF EXISTS `puzzle_solver_distinct`;
DROP TABLE IF EXISTS `puzzle_solvers`;
DROP TABLE IF EXISTS `log`;
DROP TABLE IF EXISTS `puzzle_view`;
DROP TABLE IF EXISTS `round_view`;
DROP TABLE IF EXISTS `solver_view`;

--
-- Table structure for table `round`
--

DROP TABLE IF EXISTS `round`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `round` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `round_uri` text,
  `drive_uri` varchar(255) DEFAULT NULL,
  `drive_id` varchar(100) DEFAULT NULL,
  `status` enum('New','Being worked','Needs eyes','Solved','Critical','Unnecessary','WTF','Under control','Waiting for HQ','Grind','Abandoned','Speculative','[hidden]') NOT NULL DEFAULT 'New',
  `comments` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_UNIQUE` (`name`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `solver`
--

DROP TABLE IF EXISTS `solver`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `solver` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `fullname` varchar(255) DEFAULT NULL,
  `chat_uid` varchar(255) DEFAULT NULL,
  `chat_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uid_UNIQUE` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Final view structure for view `round_view`
--

/*!50001 DROP TABLE IF EXISTS `round_view`*/;
/*!50001 DROP VIEW IF EXISTS `round_view`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_unicode_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50001 VIEW `round_view` AS select `round`.`id` AS `id`,`round`.`name` AS `name`,`round`.`round_uri` AS `round_uri`, `round`.`drive_uri` AS `drive_uri`, `round`.`drive_id` AS `drive_id`, `round`.`comments` AS `comments`, `round`.`status` AS `status`, GROUP_CONCAT(`puzzle`.`id` SEPARATOR ',') AS puzzles FROM `round` LEFT JOIN `puzzle` ON (`puzzle`.`round_id` = `round`.`id`) GROUP BY `round`.`id` */; 
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `solver_view`
--

/*!50001 DROP TABLE IF EXISTS `solver_view`*/;
/*!50001 DROP VIEW IF EXISTS `solver_view`*/;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

--
-- Helper functions for JSON-based solver tracking
--

DELIMITER //

DROP FUNCTION IF EXISTS get_current_solvers;
DROP FUNCTION IF EXISTS get_all_solvers;
DROP FUNCTION IF EXISTS get_current_puzzle;
DROP FUNCTION IF EXISTS get_all_puzzles;

CREATE FUNCTION get_current_solvers(puzzle_id INT)
RETURNS TEXT
DETERMINISTIC
SQL SECURITY INVOKER
BEGIN
    DECLARE result TEXT;
    SELECT GROUP_CONCAT(solver.name) INTO result
    FROM puzzle p,
    JSON_TABLE(
        p.current_solvers,
        '$.solvers[*]' COLUMNS (
            solver_id INT PATH '$.solver_id'
        )
    ) AS jt
    JOIN solver ON solver.id = jt.solver_id
    WHERE p.id = puzzle_id;
    RETURN IFNULL(result, '');
END //

CREATE FUNCTION get_all_solvers(puzzle_id INT)
RETURNS TEXT
DETERMINISTIC
SQL SECURITY INVOKER
BEGIN
    DECLARE result TEXT;
    SELECT GROUP_CONCAT(DISTINCT solver.name) INTO result
    FROM puzzle p,
    JSON_TABLE(
        p.solver_history,
        '$.solvers[*]' COLUMNS (
            solver_id INT PATH '$.solver_id'
        )
    ) AS jt
    JOIN solver ON solver.id = jt.solver_id
    WHERE p.id = puzzle_id;
    RETURN IFNULL(result, '');
END //

CREATE FUNCTION get_current_puzzle(solver_id INT)
RETURNS TEXT CHARACTER SET utf8mb4
DETERMINISTIC
SQL SECURITY INVOKER
BEGIN
    DECLARE result TEXT CHARACTER SET utf8mb4;
    SELECT p.name INTO result
    FROM puzzle p
    WHERE JSON_SEARCH(p.current_solvers, 'one', solver_id, NULL, '$.solvers[*].solver_id') IS NOT NULL
    LIMIT 1;
    RETURN IFNULL(result, '');
END //

CREATE FUNCTION get_all_puzzles(solver_id INT)
RETURNS TEXT CHARACTER SET utf8mb4
DETERMINISTIC
SQL SECURITY INVOKER
BEGIN
    DECLARE result TEXT CHARACTER SET utf8mb4;
    SELECT GROUP_CONCAT(DISTINCT p.name) INTO result
    FROM puzzle p
    WHERE JSON_SEARCH(p.solver_history, 'one', solver_id, NULL, '$.solvers[*].solver_id') IS NOT NULL;
    RETURN IFNULL(result, '');
END //

DELIMITER ;

-- Optimized puzzle_view
DROP VIEW IF EXISTS puzzle_view;
CREATE VIEW puzzle_view AS 
SELECT 
    p.id,
    p.name,
    p.status,
    p.answer,
    r.name AS roundname,
    p.round_id,
    p.comments,
    p.drive_uri,
    p.chat_channel_name,
    p.chat_channel_id,
    p.chat_channel_link,
    p.drive_id,
    p.puzzle_uri,
    p.ismeta,
    (
        SELECT GROUP_CONCAT(DISTINCT s.name)
        FROM JSON_TABLE(
            p.solver_history,
            '$.solvers[*]' COLUMNS (
                solver_id INT PATH '$.solver_id'
            )
        ) AS jt
        JOIN solver s ON s.id = jt.solver_id
    ) AS solvers,
    (
        SELECT GROUP_CONCAT(DISTINCT s.name)
        FROM JSON_TABLE(
            p.current_solvers,
            '$.solvers[*]' COLUMNS (
                solver_id INT PATH '$.solver_id'
            )
        ) AS jt
        JOIN solver s ON s.id = jt.solver_id
    ) AS cursolvers,
    p.xyzloc,
    p.sheetcount,
    p.sheetenabled,
    (
        SELECT GROUP_CONCAT(DISTINCT t.name ORDER BY t.name)
        FROM JSON_TABLE(
            p.tags,
            '$[*]' COLUMNS (
                tag_id INT PATH '$'
            )
        ) AS jt
        JOIN tag t ON t.id = jt.tag_id
    ) AS tags
FROM puzzle p
LEFT JOIN round r ON p.round_id = r.id;

-- Final view structure for view `solver_view`
DROP VIEW IF EXISTS solver_view;
CREATE VIEW solver_view AS 
SELECT 
    solver.id,
    solver.name,
    get_all_puzzles(solver.id) AS puzzles,
    get_current_puzzle(solver.id) AS puzz,
    solver.fullname,
    solver.chat_uid,
    solver.chat_name
FROM solver;