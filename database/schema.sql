-- MySQL schema for the OCR Data Scanning Tool.
-- The application runs these statements automatically on start-up
-- (CREATE ... IF NOT EXISTS), so this file is for reference / manual setup.

CREATE DATABASE IF NOT EXISTS ocr_scanner;

CREATE TABLE IF NOT EXISTS scan_sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  started_at DATETIME NOT NULL,
  ended_at DATETIME NULL,
  total_detections INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  session_id INT NULL,
  detected_text TEXT NOT NULL,
  confidence FLOAT NOT NULL,
  bbox JSON NULL,
  image_path VARCHAR(512) NULL,
  language VARCHAR(20) DEFAULT 'en',
  created_at DATETIME NOT NULL,
  INDEX idx_created (created_at),
  FULLTEXT KEY ft_text (detected_text),
  FOREIGN KEY (session_id) REFERENCES scan_sessions(id) ON DELETE SET NULL
);
