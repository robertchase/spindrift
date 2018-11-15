DROP DATABASE IF EXISTS spindrift;
CREATE DATABASE spindrift;
GRANT ALL ON spindrift.* to 'test'@'%';
USE spindrift;

CREATE TABLE IF NOT EXISTS `parent` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `create_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `update_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `foo` INT NOT NULL,
    `bar` INT,
    `chunk` BLOB NULL,
    PRIMARY KEY(`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `child` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `create_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `update_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `parent_id` INT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    PRIMARY KEY(`id`),
	FOREIGN KEY(`parent_id`) REFERENCES `parent`(`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `odd_keys_root` (
    `my_key` INT NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(100) NOT NULL,
    PRIMARY KEY(`my_key`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `odd_keys_node` (
    `and_my_key` INT NOT NULL AUTO_INCREMENT,
    `odd_keys_root_id` INT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    PRIMARY KEY(`and_my_key`),
	FOREIGN KEY(`odd_keys_root_id`) REFERENCES `odd_keys_root`(`my_key`)
) ENGINE=InnoDB;
