-- Copy and paste this script in your XAMPP phpMyAdmin (SQL tab)

-- 1. Create the database
CREATE DATABASE IF NOT EXISTS armobot_db;
USE armobot_db;

-- 2. Create the users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Insert a default user
-- NOTE: In production, passwords should ALWAYS be hashed using bcrypt or similar.
-- For local testing, we insert a plain text password 'admin123', 
-- and the app.py will check against this. 
-- (If you upgrade to hashed passwords, adjust app.py accordingly).
INSERT INTO users (username, password) VALUES ('admin', 'admin123');
