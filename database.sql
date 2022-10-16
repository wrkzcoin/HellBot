SET NAMES utf8;
SET time_zone = '+00:00';
SET foreign_key_checks = 0;
SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';

SET NAMES utf8mb4;

DROP TABLE IF EXISTS `exceptional_roles`;
CREATE TABLE `exceptional_roles` (
  `exceptional_roles_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `role_id` varchar(32) NOT NULL,
  `added_by` varchar(32) NOT NULL,
  `added_date` int(11) NOT NULL,
  PRIMARY KEY (`exceptional_roles_id`),
  UNIQUE KEY `guild_id_role_id` (`guild_id`,`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `exceptional_roles_deleted`;
CREATE TABLE `exceptional_roles_deleted` (
  `exceptional_roles_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `role_id` varchar(32) NOT NULL,
  `added_by` varchar(32) NOT NULL,
  `added_date` int(11) NOT NULL,
  `deleted_by` varchar(32) NOT NULL,
  `deleted_date` int(11) NOT NULL,
  PRIMARY KEY (`exceptional_roles_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `exceptional_users`;
CREATE TABLE `exceptional_users` (
  `exceptional_users_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `added_by` varchar(32) NOT NULL,
  `added_date` int(11) NOT NULL,
  PRIMARY KEY (`exceptional_users_id`),
  UNIQUE KEY `guild_id_user_id` (`guild_id`,`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `exceptional_users_deleted`;
CREATE TABLE `exceptional_users_deleted` (
  `exceptional_users_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `user_id` varchar(32) NOT NULL,
  `added_by` varchar(32) NOT NULL,
  `added_date` int(11) NOT NULL,
  `deleted_by` varchar(32) NOT NULL,
  `deleted_date` int(11) NOT NULL,
  PRIMARY KEY (`exceptional_users_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `guild_list`;
CREATE TABLE `guild_list` (
  `guild_list_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `guild_name` varchar(256) NOT NULL,
  `guild_joined_date` int(11) NOT NULL,
  `log_channel_id` varchar(32) DEFAULT NULL,
  `set_by` varchar(32) DEFAULT NULL,
  `set_date` int(11) DEFAULT NULL,
  `max_ignored_users` tinyint(4) NOT NULL DEFAULT 20,
  `max_ignored_roles` tinyint(4) NOT NULL DEFAULT 5,
  `maximum_regex` tinyint(4) NOT NULL DEFAULT 5,
  PRIMARY KEY (`guild_list_id`),
  UNIQUE KEY `guild_id` (`guild_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `guild_list_deleted`;
CREATE TABLE `guild_list_deleted` (
  `guild_list_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `guild_name` varchar(256) NOT NULL,
  `guild_joined_date` int(11) NOT NULL,
  `log_channel_id` varchar(32) DEFAULT NULL,
  `left_date` int(11) NOT NULL,
  PRIMARY KEY (`guild_list_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `name_filters`;
CREATE TABLE `name_filters` (
  `name_filters_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `regex` tinytext NOT NULL,
  `is_active` tinyint(4) NOT NULL DEFAULT 0,
  `added_by` varchar(32) NOT NULL,
  `added_date` int(11) NOT NULL,
  PRIMARY KEY (`name_filters_id`),
  UNIQUE KEY `guild_id_regex` (`guild_id`,`regex`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


DROP TABLE IF EXISTS `name_filters_deleted`;
CREATE TABLE `name_filters_deleted` (
  `name_filters_id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` varchar(32) NOT NULL,
  `regex` tinytext NOT NULL,
  `is_active` tinyint(4) NOT NULL DEFAULT 0,
  `added_by` varchar(32) NOT NULL,
  `added_date` int(11) NOT NULL,
  `deleted_by` varchar(32) NOT NULL,
  `deleted_date` int(11) NOT NULL,
  PRIMARY KEY (`name_filters_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
