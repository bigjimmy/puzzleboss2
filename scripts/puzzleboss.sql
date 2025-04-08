-- mysql puzzleboss schema 2025

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
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
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `activity` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `solver_id` int(11) NOT NULL,
  `puzzle_id` int(11) DEFAULT NULL,
  `source` enum('google','pb_auto','pb_manual','bigjimmy','twiki','squid','apache','xmpp') DEFAULT NULL,
  `type` enum('create','open','revise','comment','interact') DEFAULT NULL,
  `uri` text,
  `source_version` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_google_activity_solver1_idx` (`solver_id`),
  KEY `fk_google_activity_puzzle1_idx` (`puzzle_id`),
  KEY `time` (`time`),
  KEY `puzzle_id` (`puzzle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `newuser`
--

DROP TABLE IF EXISTS `newuser`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `newuser` (
  `username` varchar(100) NOT NULL,
  `fullname` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(100) NOT NULL,
  `code` varchar(8) NOT NULL,
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clientindex`
--

DROP TABLE IF EXISTS `clientindex`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `clientindex` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `config`
--

DROP TABLE IF EXISTS `config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `config` (
  `key` varchar(100) NOT NULL,
  `val` varchar(2000) DEFAULT NULL,
  PRIMARY KEY (`key`),
  UNIQUE KEY `key_UNIQUE` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `config` WRITE;
/*!40000 ALTER TABLE `config` DISABLE KEYS */;
INSERT INTO `config` VALUES ('ACCT_URI', 'https://yourdomain.org/account'), ('BIN_URI', 'https://yourdomain.org/pb'), ('bookmarklet_js', 'insert complicated bookmarklet javascript here'), ('LOGLEVEL','3'), ('MAILRELAY', 'mail-server.yourdomain.org'), ('REGEMAIL', 'admin@yourdomain.org'), ('TEAMNAME', 'Default Team Name'), ('LDAP_ADMINDN', 'cn=name,dc=example,dc=org'), ('LDAP_ADMINPW', 'hunter2'), ('LDAP_DOMAIN', 'ou=people,dc=example,dc=org'),('LDAP_HOST', 'ldapserver.example.org'), ('LDAP_LDAP0', 'ldap domain name'), ('DOMAINNAME', 'example.org'), ('HUNT_FOLDER_NAME', 'Hunt 2999'), ('SKIP_GOOGLE_API', 'true'), ('SHEETS_TEMPLATE_ID', 'xxxxxxxxxxxxxxxxxxxxxxi'), ('PUZZCORD_HOST', 'puzzcord-server.example.org'), ('PUZZCORD_PORT', '3141'), ('SKIP_PUZZCORD', 'true'), ('BIGJIMMY_AUTOASSIGN', 'false'), ('BIGJIMMY_PUZZLEPAUSETIME', '1'), ('BIGJIMMY_THREADCOUNT', '2'); 
/*!40000 ALTER TABLE `config` ENABLE KEYS */;
UNLOCK TABLES;


--
-- Table structure for table `log`
--

DROP TABLE IF EXISTS `log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `log` (
  `version` int(11) NOT NULL AUTO_INCREMENT,
  `time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `user` varchar(500) DEFAULT NULL,
  `module` enum('puzzles','rounds','solvers','locations') NOT NULL,
  `name` varchar(500) DEFAULT NULL,
  `id` int(11) DEFAULT NULL,
  `part` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`version`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `privs`
--

DROP TABLE IF EXISTS `privs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `privs` (
  `uid` int(11) NOT NULL,
  `puzztech` enum('NO','YES') NOT NULL DEFAULT 'NO',
  `puzzleboss` enum('NO','YES') NOT NULL DEFAULT 'NO',
  PRIMARY KEY (`uid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `puzzle`
--

DROP TABLE IF EXISTS `puzzle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `puzzle` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `puzzle_uri` text,
  `drive_uri` varchar(255) DEFAULT NULL,
  `chat_channel_id` varchar(500) DEFAULT NULL,
  `chat_channel_link` varchar(255) DEFAULT NULL,
  `comments` text,
  `status` enum('New','Being worked','Needs eyes','Solved','Critical','Unnecessary','WTF','[hidden]') NOT NULL,
  `answer` varchar(500) DEFAULT NULL,
  `round_id` int(11) NOT NULL,
  `drive_id` varchar(100) DEFAULT NULL,
  `xyzloc` varchar(500) DEFAULT NULL,
  `chat_channel_name` varchar(300) DEFAULT NULL,
  `ismeta` tinyint(1) NOT NULL DEFAULT 0,
  `current_solvers` JSON DEFAULT NULL,
  `solver_history` JSON DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_UNIQUE` (`name`),
  KEY `fk_puzzles_rounds1_idx` (`round_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Remove legacy tables and views
--

DROP TABLE IF EXISTS `puzzle_cursolver_distinct`;
DROP TABLE IF EXISTS `puzzle_cursolvers`;
DROP TABLE IF EXISTS `puzzle_solver_distinct`;
DROP TABLE IF EXISTS `puzzle_solvers`;

DROP TABLE IF EXISTS `puzzle_view`;
/*!50001 DROP VIEW IF EXISTS `puzzle_view`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `puzzle_view` (
  `id` tinyint NOT NULL,
  `name` tinyint NOT NULL,
  `status` tinyint NOT NULL,
  `answer` tinyint NOT NULL,
  `roundname` tinyint NOT NULL,
  `round_id` tinyint NOT NULL,
  `comments` tinyint NOT NULL,
  `locations` tinyint NOT NULL,
  `drive_uri` tinyint NOT NULL,
  `chat_channel_name` tinyint NOT NULL,
  `drive_id` tinyint NOT NULL,
  `linkid` tinyint NOT NULL,
  `puzzle_uri` tinyint NOT NULL,
  `activity` tinyint NOT NULL,
  `solvers` tinyint NOT NULL,
  `cursolvers` tinyint NOT NULL,
  `xyzloc` tinyint NOT NULL
) ENGINE=INNODB */;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `round_view`
--

DROP TABLE IF EXISTS `round_view`;
/*!50001 DROP VIEW IF EXISTS `round_view`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `round_view` (
  `id` tinyint NOT NULL,
  `name` tinyint NOT NULL,
  `round_uri` tinyint NOT NULL,
  `drive_uri` tinyint NOT NULL,
  `drive_id` tinyint NOT NULL,
  `puzzles` tinyint NOT NULL
) ENGINE=INNODB */;
SET character_set_client = @saved_cs_client;


--
-- Table structure for table `round`
--

DROP TABLE IF EXISTS `round`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `round` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `round_uri` text,
  `drive_uri` varchar(255) DEFAULT NULL,
  `drive_id` varchar(100) DEFAULT NULL,
  `status` enum('New','Being worked','Needs eyes','Solved','Critical','Unnecessary','WTF','[hidden]') NOT NULL DEFAULT 'New',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_UNIQUE` (`name`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8;

--
-- Table structure for table `solver`
--

DROP TABLE IF EXISTS `solver`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `solver` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `fullname` varchar(255) DEFAULT NULL,
  `chat_uid` varchar(255) DEFAULT NULL,
  `chat_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uid_UNIQUE` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Temporary table structure for view `solver_view`
--

DROP TABLE IF EXISTS `solver_view`;
/*!50001 DROP VIEW IF EXISTS `solver_view`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `solver_view` (
  `id` tinyint NOT NULL,
  `name` tinyint NOT NULL,
  `puzzles` tinyint NOT NULL,
  `puzz` tinyint NOT NULL,
  `chat_uid` tinyint NOT NULL,
  `chat_name` tinyint NOT NULL,
  `fullname` tinyint NOT NULL
) ENGINE=INNODB */;
SET character_set_client = @saved_cs_client;

--
-- Final view structure for view `puzzle_view`
--

/*!50001 DROP TABLE IF EXISTS `puzzle_view`*/;
/*!50001 DROP VIEW IF EXISTS `puzzle_view`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8 */;
/*!50001 SET character_set_results     = utf8 */;
/*!50001 SET collation_connection      = utf8_unicode_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50001 VIEW `puzzle_view` AS select `puzzle`.`id` AS `id`,`puzzle`.`name` AS `name`,`puzzle`.`status` AS `status`,`puzzle`.`answer` AS `answer`,`round`.`name` AS `roundname`, `round`.`id` AS `round_id`, `puzzle`.`comments` AS `comments`, `puzzle`.`drive_uri` AS `drive_uri`,`puzzle`.`chat_channel_name` AS `chat_channel_name`,`puzzle`.`chat_channel_id` AS `chat_channel_id`,`puzzle`.`chat_channel_link` AS `chat_channel_link`,`puzzle`.`drive_id` AS `drive_id`,`puzzle`.`puzzle_uri` AS `puzzle_uri`, get_all_solvers(puzzle.id) AS `solvers`, get_current_solvers(puzzle.id) AS `cursolvers`,`puzzle`.`xyzloc` AS `xyzloc`, `puzzle`.`ismeta` AS `ismeta` from (`puzzle` join `round` on((`round`.`id` = `puzzle`.`round_id`))) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `round_view`
--

/*!50001 DROP TABLE IF EXISTS `round_view`*/;
/*!50001 DROP VIEW IF EXISTS `round_view`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8 */;
/*!50001 SET character_set_results     = utf8 */;
/*!50001 SET collation_connection      = utf8_unicode_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50001 VIEW `round_view` AS select `round`.`id` AS `id`,`round`.`name` AS `name`,`round`.`round_uri` AS `round_uri`, `round`.`drive_uri` AS `drive_uri`, `round`.`drive_id` AS `drive_id`, GROUP_CONCAT(`puzzle`.`id` SEPARATOR ',') AS puzzles FROM `round` LEFT JOIN `puzzle` ON (`puzzle`.`round_id` = `round`.`id`) GROUP BY `round`.`id` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `solver_view`
--

/*!50001 DROP TABLE IF EXISTS `solver_view`*/;
/*!50001 DROP VIEW IF EXISTS `solver_view`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8 */;
/*!50001 SET character_set_results     = utf8 */;
/*!50001 SET collation_connection      = utf8_unicode_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50001 VIEW `solver_view` AS select `solver`.`id` AS `id`,`solver`.`name` AS `name`, get_all_puzzles(solver.id) AS `puzzles`, get_current_puzzle(solver.id) AS `puzz`,`solver`.`fullname` AS `fullname`,`solver`.`chat_uid` AS `chat_uid`, `solver`.`chat_name` as `chat_name` from `solver` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

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
RETURNS TEXT
DETERMINISTIC
BEGIN
    DECLARE result TEXT;
    SELECT p.name INTO result
    FROM puzzle p
    WHERE JSON_SEARCH(p.current_solvers, 'one', solver_id, NULL, '$.solvers[*].solver_id') IS NOT NULL
    LIMIT 1;
    RETURN IFNULL(result, '');
END //

CREATE FUNCTION get_all_puzzles(solver_id INT) 
RETURNS TEXT
DETERMINISTIC
BEGIN
    DECLARE result TEXT;
    SELECT GROUP_CONCAT(DISTINCT p.name) INTO result
    FROM puzzle p
    WHERE JSON_SEARCH(p.solver_history, 'one', solver_id, NULL, '$.solvers[*].solver_id') IS NOT NULL;
    RETURN IFNULL(result, '');
END //

DELIMITER ;