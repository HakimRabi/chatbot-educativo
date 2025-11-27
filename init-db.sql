CREATE DATABASE IF NOT EXISTS `bd_chatbot` 
/*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ 
/*!80016 DEFAULT ENCRYPTION='N' */;

USE `bd_chatbot`;

-- -----------------------------------------------------
-- 1. Tabla: users
-- -----------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) DEFAULT NULL,
  `email` varchar(100) DEFAULT NULL,
  `password` varchar(100) DEFAULT NULL,
  `created_at` varchar(100) DEFAULT NULL,
  `permisos` enum('usuario','admin') NOT NULL DEFAULT 'usuario',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_email` (`email`),
  KEY `ix_users_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- 2. Tabla: chat_sessions
-- Relación: Un usuario tiene muchas sesiones.
-- -----------------------------------------------------
DROP TABLE IF EXISTS `chat_sessions`;
CREATE TABLE `chat_sessions` (
  `session_id` varchar(255) NOT NULL,
  `user_id` int NOT NULL, -- CAMBIO: de VARCHAR a INT
  `history` json NOT NULL,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `session_id`), -- Clave primaria compuesta
  CONSTRAINT `fk_sessions_user`
    FOREIGN KEY (`user_id`)
    REFERENCES `users` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- 3. Tabla: feedback
-- Relación: Vinculada a una sesión específica de un usuario.
-- -----------------------------------------------------
DROP TABLE IF EXISTS `feedback`;
CREATE TABLE `feedback` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL, -- CAMBIO: de VARCHAR a INT
  `session_id` varchar(255) NOT NULL,
  `pregunta` text NOT NULL,
  `respuesta` text NOT NULL,
  `rating` int DEFAULT NULL,
  `comentario` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `feedback_chk_1` CHECK ((`rating` between 1 and 5)),
  CONSTRAINT `fk_feedback_session`
    FOREIGN KEY (`user_id`, `session_id`) -- Relación con la sesión
    REFERENCES `chat_sessions` (`user_id`, `session_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- 4. Tabla: session_pdfs
-- Relación: Vinculada a una sesión específica de un usuario.
-- -----------------------------------------------------
DROP TABLE IF EXISTS `session_pdfs`;
CREATE TABLE `session_pdfs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL, -- CAMBIO: de VARCHAR a INT
  `session_id` varchar(255) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `file_path` varchar(255) NOT NULL,
  `page_count` int DEFAULT NULL,
  `upload_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_pdfs_session`
    FOREIGN KEY (`user_id`, `session_id`) -- Relación con la sesión
    REFERENCES `chat_sessions` (`user_id`, `session_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- 5. Tabla: chat_tasks (NUEVA)
-- Relación: Vinculada a un usuario y opcionalmente a una sesión.
-- -----------------------------------------------------
DROP TABLE IF EXISTS `chat_tasks`;
CREATE TABLE `chat_tasks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `task_id` VARCHAR(255) UNIQUE NOT NULL,
    `user_id` INT NOT NULL, -- CAMBIO: de VARCHAR a INT
    `session_id` VARCHAR(255), -- Puede ser NULL si la tarea no es de una sesión específica
    
    -- Información de la consulta
    `query` TEXT NOT NULL,
    `query_length` INT,
    `response` TEXT,
    `response_length` INT,
    
    -- Modelo y configuración
    `model` VARCHAR(50) DEFAULT 'llama3',
    `worker_name` VARCHAR(100),
    
    -- Estados y tiempos
    `status` ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED') DEFAULT 'PENDING',
    `started_at` TIMESTAMP NULL,
    `completed_at` TIMESTAMP NULL,
    `processing_time` FLOAT,  -- en segundos
    
    -- Metadata adicional
    `vector_db_used` BOOLEAN DEFAULT FALSE,
    `documents_count` INT DEFAULT 0,
    `error_message` TEXT NULL,
    
    -- Índices y Tiempos
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_task_id` (`task_id`),
    
    -- Relaciones
    CONSTRAINT `fk_tasks_user`
        FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
        
    -- Intenta vincular con la sesión si session_id no es nulo
    CONSTRAINT `fk_tasks_session`
        FOREIGN KEY (`user_id`, `session_id`)
        REFERENCES `chat_sessions` (`user_id`, `session_id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- Tabla: stress_tests
-- Almacena resultados de tests de estres del sistema
-- -----------------------------------------------------
DROP TABLE IF EXISTS `stress_tests`;
CREATE TABLE `stress_tests` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `test_id` VARCHAR(36) UNIQUE NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    
    -- Configuracion del test
    `config` JSON NOT NULL,
    
    -- Estado
    `status` ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED') DEFAULT 'PENDING',
    
    -- Tiempos
    `started_at` TIMESTAMP NULL,
    `completed_at` TIMESTAMP NULL,
    `duration_seconds` DECIMAL(10,2) NULL,
    
    -- Hardware donde se ejecuto
    `hardware_info` JSON NULL,
    
    -- Resultados
    `metrics_snapshots` JSON NULL,
    `summary` JSON NULL,
    `log_entries` JSON NULL,
    
    -- Metadata
    `error_message` TEXT NULL,
    `created_by` INT NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indices
    INDEX `idx_stress_status` (`status`),
    INDEX `idx_stress_created_at` (`created_at`),
    INDEX `idx_stress_test_id` (`test_id`),
    
    -- Relaciones
    CONSTRAINT `fk_stress_user`
        FOREIGN KEY (`created_by`)
        REFERENCES `users` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


