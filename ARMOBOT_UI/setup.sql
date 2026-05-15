-- 1. SQLite does NOT use CREATE DATABASE
-- Database is just a file, e.g., armobot_db.db

-- 2. Create users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Insert default user
INSERT INTO users (username, password)
VALUES ('admin', 'admin123');