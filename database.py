"""
database.py
------------
Handles all SQLite connection management and schema creation for SkillPalavar.

We use plain sqlite3 (no ORM) so the schema and queries stay easy to read
and explain during a project viva.
"""

import sqlite3
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('candidate', 'recruiter')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    experience REAL DEFAULT 0,
    resume_filename TEXT,
    resume_text TEXT,
    extracted_skills TEXT,            -- JSON list
    resume_score REAL,                -- LLM score 0-100
    llm_summary TEXT,
    llm_strengths TEXT,               -- JSON list
    llm_concerns TEXT,                -- JSON list
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    required_skills TEXT NOT NULL,    -- JSON list
    minimum_experience REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'open',       -- open / closed
    is_demo INTEGER DEFAULT 0,
    FOREIGN KEY (recruiter_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    match_score REAL,                 -- TF-IDF cosine similarity (%)
    quiz_score REAL,                  -- 0-100
    skills_score REAL,                -- 0-100
    experience_score REAL,            -- 0-100
    final_score REAL,                 -- weighted composite
    prediction TEXT,                  -- 'Selected' / 'Not Selected'
    prediction_probability REAL,
    missing_skills TEXT,              -- JSON list
    status TEXT DEFAULT 'pending',    -- pending / approved / rejected
    is_demo INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    UNIQUE(candidate_id, job_id)
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_answer TEXT NOT NULL,     -- 'A' / 'B' / 'C' / 'D'
    skill TEXT,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quiz_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL UNIQUE,
    score REAL NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);
"""


def get_db():
    """Return a SQLite connection bound to the current Flask app context."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Create tables if they don't already exist and register teardown."""
    with app.app_context():
        conn = sqlite3.connect(app.config["DATABASE_PATH"])
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()
    app.teardown_appcontext(close_db)
