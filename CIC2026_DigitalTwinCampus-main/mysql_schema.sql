CREATE DATABASE IF NOT EXISTS omnisx CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE omnisx;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL, salt VARCHAR(64) NOT NULL,
  role VARCHAR(64) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS resources (
  id VARCHAR(32) PRIMARY KEY, name VARCHAR(100) NOT NULL, domain VARCHAR(64) NOT NULL,
  students INT NOT NULL DEFAULT 0, faculty INT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'Operational', updated_at DATETIME
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS buildings (
  id INT AUTO_INCREMENT PRIMARY KEY, resource_id VARCHAR(32) UNIQUE,
  express_id VARCHAR(64), name VARCHAR(100) NOT NULL,
  FOREIGN KEY(resource_id) REFERENCES resources(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS dependencies (
  source_id VARCHAR(32), target_id VARCHAR(32), PRIMARY KEY(source_id,target_id),
  FOREIGN KEY(source_id) REFERENCES resources(id),
  FOREIGN KEY(target_id) REFERENCES resources(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS faculty (
  id VARCHAR(32) PRIMARY KEY, name VARCHAR(100), subject VARCHAR(100),
  qualification VARCHAR(100), availability VARCHAR(32), workload INT
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS students (
  id VARCHAR(32) PRIMARY KEY, cohort VARCHAR(100), count INT
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS rooms (
  id VARCHAR(32) PRIMARY KEY, name VARCHAR(100), kind VARCHAR(32),
  capacity INT, available TINYINT
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS timetables (
  id INT AUTO_INCREMENT PRIMARY KEY, faculty_id VARCHAR(32), cohort VARCHAR(100),
  subject VARCHAR(100), start_hour INT, end_hour INT, room_id VARCHAR(32),
  FOREIGN KEY(faculty_id) REFERENCES faculty(id),
  FOREIGN KEY(room_id) REFERENCES rooms(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS incidents (
  id VARCHAR(32) PRIMARY KEY, resource_id VARCHAR(32), type VARCHAR(64),
  severity VARCHAR(32), duration INT, description TEXT, status VARCHAR(32),
  created_by VARCHAR(100), created_at DATETIME,
  FOREIGN KEY(resource_id) REFERENCES resources(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS simulations (
  id VARCHAR(32) PRIMARY KEY, resource_id VARCHAR(32), type VARCHAR(64),
  severity VARCHAR(32), duration INT, affected_resources TEXT,
  students INT, faculty INT, blast_radius INT, result_json JSON, created_at DATETIME,
  FOREIGN KEY(resource_id) REFERENCES resources(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS recovery_plans (
  id VARCHAR(64) PRIMARY KEY, simulation_id VARCHAR(32), incident_id VARCHAR(32),
  name VARCHAR(100), estimated_delay INT, rooms_required INT, cost INT,
  constraint_violations INT, feasibility_score INT, recommended TINYINT,
  reason TEXT, status VARCHAR(32) DEFAULT 'Pending',
  FOREIGN KEY(simulation_id) REFERENCES simulations(id),
  FOREIGN KEY(incident_id) REFERENCES incidents(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS recovery_approvals (
  id INT AUTO_INCREMENT PRIMARY KEY, plan_id VARCHAR(64),
  decision VARCHAR(32), decided_by VARCHAR(100), decided_at DATETIME,
  FOREIGN KEY(plan_id) REFERENCES recovery_plans(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS historical_analytics (
  id INT AUTO_INCREMENT PRIMARY KEY, resource_id VARCHAR(32),
  metric VARCHAR(100), value DOUBLE, recorded_at DATETIME
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS problems (
  id VARCHAR(32) PRIMARY KEY, title VARCHAR(255) NOT NULL,
  description TEXT, category VARCHAR(64) NOT NULL, location VARCHAR(255),
  resource_id VARCHAR(32), reported_by VARCHAR(100), assigned_to VARCHAR(100),
  assigned_department VARCHAR(100), priority VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL, resolution_details TEXT,
  created_at DATETIME, resolved_at DATETIME,
  FOREIGN KEY(resource_id) REFERENCES resources(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS problem_history (
  id INT AUTO_INCREMENT PRIMARY KEY, problem_id VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL, note TEXT, changed_by VARCHAR(100),
  changed_at DATETIME,
  FOREIGN KEY(problem_id) REFERENCES problems(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notifications (
  id INT AUTO_INCREMENT PRIMARY KEY, recipient VARCHAR(100),
  problem_id VARCHAR(32), message TEXT NOT NULL, `read` TINYINT DEFAULT 0,
  created_at DATETIME
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS staff (
  id VARCHAR(32) PRIMARY KEY, name VARCHAR(100) NOT NULL,
  role VARCHAR(64) NOT NULL, department VARCHAR(100) NOT NULL,
  qualification VARCHAR(100), workload INT DEFAULT 0, available TINYINT DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS announcements (
  id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255), message TEXT,
  audience VARCHAR(64), created_at DATETIME
) ENGINE=InnoDB;
