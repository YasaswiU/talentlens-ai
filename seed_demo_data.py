"""
seed_demo_data.py
--------------------
Populates the database with demo/sample data so the recruiter dashboard
looks populated for a project review (Section 36).

Run:
    python seed_demo_data.py

All demo rows are clearly marked (is_demo = 1) and demo users use the
@demo.skillpalavar email domain so they are easy to identify.

This script is idempotent-ish: it checks for the demo recruiter account
before re-inserting jobs, but re-running will add duplicate demo
candidates if you run it twice. Delete skillpalavar.db and re-run
init to start fresh if needed.
"""

import json
import random

from werkzeug.security import generate_password_hash

from app import create_app
import database
from services import scoring, quiz_generator, prediction

DEMO_PASSWORD = "demo1234"

DEMO_JOBS = [
    {
        "title": "Python Developer",
        "description": (
            "We are looking for a Python Developer to build and maintain backend "
            "services using Flask and PostgreSQL. Experience with Docker, Git, and "
            "REST API design is required. You'll work closely with the data team on "
            "scalable, well-tested services."
        ),
        "required_skills": ["python", "flask", "sql", "postgresql", "docker", "git"],
        "minimum_experience": 2,
    },
    {
        "title": "Data Analyst",
        "description": (
            "Seeking a Data Analyst comfortable with SQL, Python, and building "
            "dashboards. You will analyze large datasets, build reports using pandas, "
            "and communicate insights to stakeholders. Machine learning exposure is a plus."
        ),
        "required_skills": ["sql", "python", "machine learning", "mysql"],
        "minimum_experience": 1,
    },
    {
        "title": "ML Engineer",
        "description": (
            "ML Engineer role focused on building and deploying models using "
            "TensorFlow or PyTorch. Strong Python skills, experience with scikit-learn, "
            "and familiarity with cloud platforms (AWS/GCP) required. NLP experience is a bonus."
        ),
        "required_skills": ["python", "machine learning", "tensorflow", "pytorch", "scikit-learn", "aws"],
        "minimum_experience": 3,
    },
    {
        "title": "Frontend Developer",
        "description": (
            "Frontend Developer needed to build responsive web interfaces using React, "
            "HTML, and CSS. Experience with JavaScript/TypeScript and Git workflows required. "
            "You'll collaborate with designers to ship polished, accessible UI."
        ),
        "required_skills": ["react", "html", "css", "javascript", "git"],
        "minimum_experience": 1,
    },
]

DEMO_CANDIDATES = [
    {"name": "Aditi Sharma", "experience": 3.5, "skills": ["python", "flask", "sql", "postgresql", "git", "docker"], "resume_score": 85},
    {"name": "Rahul Verma", "experience": 1.0, "skills": ["python", "sql", "html", "css"], "resume_score": 58},
    {"name": "Priya Nair", "experience": 4.0, "skills": ["python", "machine learning", "tensorflow", "scikit-learn", "aws", "sql"], "resume_score": 91},
    {"name": "Karan Mehta", "experience": 2.0, "skills": ["react", "javascript", "html", "css", "git"], "resume_score": 74},
    {"name": "Sneha Iyer", "experience": 0.5, "skills": ["python", "sql"], "resume_score": 45},
    {"name": "Vikram Rao", "experience": 5.0, "skills": ["python", "django", "flask", "sql", "docker", "kubernetes", "aws", "git"], "resume_score": 93},
    {"name": "Ananya Gupta", "experience": 2.5, "skills": ["javascript", "react", "node.js", "css", "html", "git"], "resume_score": 79},
    {"name": "Rohan Das", "experience": 1.5, "skills": ["sql", "mysql", "python", "machine learning"], "resume_score": 62},
    {"name": "Meera Pillai", "experience": 3.0, "skills": ["python", "pytorch", "machine learning", "nlp", "aws"], "resume_score": 88},
    {"name": "Arjun Kapoor", "experience": 0.8, "skills": ["html", "css", "javascript"], "resume_score": 40},
]

DEMO_RESUME_TEXT_TEMPLATE = (
    "{name} - Software professional with {experience} years of experience.\n"
    "Skills: {skills}.\n"
    "Demo resume text generated for TalentLens AI sample data.\n"
)


def seed():
    app = create_app()
    with app.app_context():
        db = database.get_db()

        # --- Demo recruiter ---
        recruiter = db.execute("SELECT * FROM users WHERE email = ?", ("recruiter@demo.skillpalavar",)).fetchone()
        if not recruiter:
            cur = db.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("Demo Recruiter", "recruiter@demo.skillpalavar", generate_password_hash(DEMO_PASSWORD), "recruiter"),
            )
            recruiter_id = cur.lastrowid
        else:
            recruiter_id = recruiter["id"]

        # --- Demo jobs ---
        job_ids = []
        for job in DEMO_JOBS:
            existing = db.execute(
                "SELECT id FROM jobs WHERE title = ? AND recruiter_id = ?", (job["title"], recruiter_id)
            ).fetchone()
            if existing:
                job_ids.append(existing["id"])
                continue
            cur = db.execute(
                """INSERT INTO jobs (recruiter_id, title, description, required_skills, minimum_experience, is_demo)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (recruiter_id, job["title"], job["description"], json.dumps(job["required_skills"]), job["minimum_experience"]),
            )
            job_ids.append(cur.lastrowid)
        db.commit()

        jobs_by_id = {j["id"]: j for j in db.execute("SELECT * FROM jobs WHERE recruiter_id = ?", (recruiter_id,)).fetchall()}

        # --- Demo candidates + applications ---
        for i, c in enumerate(DEMO_CANDIDATES):
            email = f"candidate{i+1}@demo.skillpalavar"
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                cur = db.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (c["name"], email, generate_password_hash(DEMO_PASSWORD), "candidate"),
                )
                user_id = cur.lastrowid
                resume_text = DEMO_RESUME_TEXT_TEMPLATE.format(
                    name=c["name"], experience=c["experience"], skills=", ".join(c["skills"])
                )
                db.execute(
                    """INSERT INTO candidates
                       (user_id, name, experience, resume_filename, resume_text, extracted_skills, resume_score, llm_summary)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, c["name"], c["experience"], "demo_resume.pdf", resume_text,
                     json.dumps(c["skills"]), c["resume_score"],
                     "Demo AI evaluation summary (sample data, not a live LLM call)."),
                )
            db.commit()

            candidate = db.execute("SELECT * FROM candidates WHERE user_id = (SELECT id FROM users WHERE email = ?)", (email,)).fetchone()

            # Apply to a random subset of jobs (1-2 jobs per candidate)
            chosen_jobs = random.sample(list(jobs_by_id.values()), k=random.choice([1, 2]))
            for job in chosen_jobs:
                existing_app = db.execute(
                    "SELECT id FROM applications WHERE candidate_id = ? AND job_id = ?", (candidate["id"], job["id"])
                ).fetchone()
                if existing_app:
                    continue

                required_skills = json.loads(job["required_skills"])
                candidate_skills = c["skills"]

                # Simulated match score (deterministic-ish based on skill overlap)
                overlap = len(set(candidate_skills) & set(required_skills))
                match_score = round(min(95, 30 + overlap * 12 + random.uniform(-5, 5)), 2)

                skills_score = scoring.compute_skills_score(candidate_skills, required_skills)
                experience_score = scoring.compute_experience_score(c["experience"], job["minimum_experience"])
                missing_skills = scoring.compute_missing_skills(candidate_skills, required_skills)

                quiz_score = round(min(100, max(20, c["resume_score"] + random.uniform(-15, 10))), 2)

                final_score, _ = scoring.compute_final_score(match_score, quiz_score, skills_score, experience_score)

                pred = prediction.predict_outcome(
                    app.config["MODEL_PATH"], c["experience"], len(candidate_skills), quiz_score
                )

                db.execute(
                    """INSERT INTO applications
                       (candidate_id, job_id, match_score, quiz_score, skills_score, experience_score,
                        final_score, prediction, prediction_probability, missing_skills, status, is_demo)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1)""",
                    (candidate["id"], job["id"], match_score, quiz_score, skills_score, experience_score,
                     final_score, pred.get("prediction"), pred.get("probability"), json.dumps(missing_skills)),
                )
        db.commit()

    print("Demo data seeded successfully.")
    print(f"Demo recruiter login: recruiter@demo.skillpalavar / {DEMO_PASSWORD}")
    print(f"Demo candidate logins: candidate1@demo.skillpalavar ... candidate10@demo.skillpalavar / {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
