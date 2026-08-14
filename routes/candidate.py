"""
routes/candidate.py
---------------------
All candidate-facing Flask routes.
"""

import json
import os

from flask import render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename

import database
from routes.utils import login_required, allowed_file
from services import resume_parser, skill_extractor, llm_service, job_matcher
from services import quiz_generator, scoring, prediction


def register_candidate_routes(app):

    def get_candidate_row(db, user_id):
        return db.execute("SELECT * FROM candidates WHERE user_id = ?", (user_id,)).fetchone()

    # ---------------- Dashboard ----------------

    @app.route("/candidate/dashboard")
    @login_required(role="candidate")
    def candidate_dashboard():
        db = database.get_db()
        candidate = get_candidate_row(db, session["user_id"])

        applications = db.execute(
            """SELECT applications.*, jobs.title AS job_title, jobs.required_skills,
                      jobs.minimum_experience
               FROM applications
               JOIN jobs ON jobs.id = applications.job_id
               WHERE applications.candidate_id = ?
               ORDER BY applications.created_at DESC""",
            (candidate["id"],),
        ).fetchall()

        skills = json.loads(candidate["extracted_skills"]) if candidate and candidate["extracted_skills"] else []
        strengths = json.loads(candidate["llm_strengths"]) if candidate and candidate["llm_strengths"] else []
        concerns = json.loads(candidate["llm_concerns"]) if candidate and candidate["llm_concerns"] else []

        apps_view = []
        for a in applications:
            required = json.loads(a["required_skills"]) if a["required_skills"] else []
            missing = json.loads(a["missing_skills"]) if a["missing_skills"] else []
            apps_view.append({**dict(a), "required_skills_list": required, "missing_skills_list": missing})

        return render_template(
            "candidate/dashboard.html",
            candidate=candidate,
            skills=skills,
            strengths=strengths,
            concerns=concerns,
            applications=apps_view,
        )

    # ---------------- Profile ----------------

    @app.route("/candidate/profile", methods=["GET", "POST"])
    @login_required(role="candidate")
    def candidate_profile():
        db = database.get_db()
        candidate = get_candidate_row(db, session["user_id"])

        if request.method == "POST":
            name = request.form.get("name", "").strip() or candidate["name"]
            try:
                experience = float(request.form.get("experience", 0) or 0)
            except ValueError:
                experience = candidate["experience"]
            db.execute(
                "UPDATE candidates SET name = ?, experience = ? WHERE id = ?",
                (name, experience, candidate["id"]),
            )
            db.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("candidate_profile"))

        return render_template("candidate/profile.html", candidate=candidate)

    # ---------------- Resume upload ----------------

    @app.route("/candidate/upload-resume", methods=["GET", "POST"])
    @login_required(role="candidate")
    def upload_resume():
        db = database.get_db()
        candidate = get_candidate_row(db, session["user_id"])

        if request.method == "POST":
            file = request.files.get("resume")
            if not file or file.filename == "":
                flash("Please choose a PDF file to upload.", "error")
                return redirect(url_for("upload_resume"))

            if not allowed_file(file.filename):
                flash("Only PDF files are accepted.", "error")
                return redirect(url_for("upload_resume"))

            safe_name = secure_filename(f"candidate_{candidate['id']}_{file.filename}")
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)

            try:
                file.save(save_path)
            except Exception:
                flash("Could not save the uploaded file. Please try again.", "error")
                return redirect(url_for("upload_resume"))

            # Step 1: PDF text extraction (pdfplumber)
            resume_text, error = resume_parser.extract_text_from_pdf(save_path)
            if error:
                flash(error, "error")
                return redirect(url_for("upload_resume"))

            # Step 2: NLP skill extraction (spaCy / fallback)
            extracted_skills = skill_extractor.extract_skills(resume_text)

            # Step 3: LLM resume evaluation (Ollama + Gemma 3 4B)
            llm_result = llm_service.evaluate_resume(resume_text, applied_role="a technical role")

            db.execute(
                """UPDATE candidates
                   SET resume_filename = ?, resume_text = ?, extracted_skills = ?,
                       resume_score = ?, llm_summary = ?, llm_strengths = ?, llm_concerns = ?
                   WHERE id = ?""",
                (
                    safe_name, resume_text, json.dumps(extracted_skills),
                    llm_result["score"], llm_result["summary"],
                    json.dumps(llm_result["strengths"]), json.dumps(llm_result["concerns"]),
                    candidate["id"],
                ),
            )
            db.commit()

            if llm_result["available"]:
                flash("Resume uploaded and evaluated successfully.", "success")
            else:
                flash(f"Resume uploaded and skills extracted, but AI evaluation is unavailable: {llm_result['error']}", "warning")

            return redirect(url_for("candidate_dashboard"))

        return render_template("candidate/upload.html", candidate=candidate)

    # ---------------- Apply for jobs ----------------

    @app.route("/candidate/jobs")
    @login_required(role="candidate")
    def browse_jobs():
        db = database.get_db()
        candidate = get_candidate_row(db, session["user_id"])
        jobs = db.execute("SELECT * FROM jobs WHERE status = 'open' ORDER BY created_at DESC").fetchall()

        applied_job_ids = {
            row["job_id"] for row in db.execute(
                "SELECT job_id FROM applications WHERE candidate_id = ?", (candidate["id"],)
            ).fetchall()
        }

        jobs_view = []
        for j in jobs:
            jobs_view.append({**dict(j), "required_skills_list": json.loads(j["required_skills"]),
                               "already_applied": j["id"] in applied_job_ids})

        return render_template("candidate/jobs.html", jobs=jobs_view, candidate=candidate)

    @app.route("/candidate/apply/<int:job_id>", methods=["POST"])
    @login_required(role="candidate")
    def apply_job(job_id):
        db = database.get_db()
        candidate = get_candidate_row(db, session["user_id"])
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

        if not job:
            flash("This job posting no longer exists.", "error")
            return redirect(url_for("browse_jobs"))

        if not candidate["resume_text"]:
            flash("Please upload your resume before applying.", "error")
            return redirect(url_for("upload_resume"))

        existing = db.execute(
            "SELECT id FROM applications WHERE candidate_id = ? AND job_id = ?",
            (candidate["id"], job_id),
        ).fetchone()
        if existing:
            flash("You have already applied to this job.", "warning")
            return redirect(url_for("browse_jobs"))

        # Step: TF-IDF + cosine similarity job matching
        match_score = job_matcher.compute_match_percentage(candidate["resume_text"], job["description"])

        candidate_skills = json.loads(candidate["extracted_skills"]) if candidate["extracted_skills"] else []
        required_skills = json.loads(job["required_skills"])

        # Step: skill gap analysis
        missing_skills = scoring.compute_missing_skills(candidate_skills, required_skills)

        # Step: skills score + experience score
        skills_score = scoring.compute_skills_score(candidate_skills, required_skills)
        experience_score = scoring.compute_experience_score(candidate["experience"], job["minimum_experience"])

        db.execute(
            """INSERT INTO applications
               (candidate_id, job_id, match_score, skills_score, experience_score, missing_skills, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (candidate["id"], job_id, match_score, skills_score, experience_score, json.dumps(missing_skills)),
        )
        db.commit()

        flash(f"Application submitted. Resume match score: {match_score}%. Next, take the skill quiz.", "success")
        return redirect(url_for("candidate_dashboard"))

    # ---------------- Adaptive quiz ----------------

    @app.route("/candidate/quiz/<int:application_id>", methods=["GET", "POST"])
    @login_required(role="candidate")
    def take_quiz(application_id):
        db = database.get_db()
        candidate = get_candidate_row(db, session["user_id"])

        application = db.execute(
            "SELECT * FROM applications WHERE id = ? AND candidate_id = ?",
            (application_id, candidate["id"]),
        ).fetchone()
        if not application:
            flash("Application not found.", "error")
            return redirect(url_for("candidate_dashboard"))

        already_done = db.execute(
            "SELECT * FROM quiz_results WHERE application_id = ?", (application_id,)
        ).fetchone()
        if already_done:
            flash("You have already completed the quiz for this application.", "warning")
            return redirect(url_for("candidate_dashboard"))

        if request.method == "POST":
            questions = db.execute(
                "SELECT * FROM quiz_questions WHERE application_id = ? ORDER BY id", (application_id,)
            ).fetchall()
            if not questions:
                flash("Quiz questions could not be found. Please restart the quiz.", "error")
                return redirect(url_for("take_quiz", application_id=application_id))

            submitted = {str(q["id"]): request.form.get(f"q_{q['id']}") for q in questions}
            score, correct_count, total = quiz_generator.score_quiz(
                [dict(q) for q in questions], submitted
            )

            db.execute(
                "INSERT INTO quiz_results (application_id, score, total_questions, correct_count) VALUES (?, ?, ?, ?)",
                (application_id, score, total, correct_count),
            )

            # Recompute prediction + final score now that quiz is done
            candidate_skills = json.loads(candidate["extracted_skills"]) if candidate["extracted_skills"] else []
            pred = prediction.predict_outcome(
                app.config["MODEL_PATH"],
                candidate["experience"],
                len(candidate_skills),
                score,
            )
            final_score, _ = scoring.compute_final_score(
                application["match_score"], score, application["skills_score"], application["experience_score"]
            )

            db.execute(
                """UPDATE applications
                   SET quiz_score = ?, final_score = ?, prediction = ?, prediction_probability = ?
                   WHERE id = ?""",
                (score, final_score, pred.get("prediction"), pred.get("probability"), application_id),
            )
            db.commit()

            flash(f"Quiz submitted. You scored {correct_count}/{total} ({score}%).", "success")
            return redirect(url_for("candidate_dashboard"))

        # GET: generate questions if not already generated
        existing_questions = db.execute(
            "SELECT * FROM quiz_questions WHERE application_id = ? ORDER BY id", (application_id,)
        ).fetchall()

        if not existing_questions:
            candidate_skills = json.loads(candidate["extracted_skills"]) if candidate["extracted_skills"] else []
            generated = quiz_generator.generate_quiz_questions(candidate_skills, app.config["QUIZ_QUESTION_COUNT"])
            for q in generated:
                db.execute(
                    """INSERT INTO quiz_questions
                       (application_id, question, option_a, option_b, option_c, option_d, correct_answer, skill)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (application_id, q["question"], q["option_a"], q["option_b"], q["option_c"], q["option_d"],
                     q["correct_answer"], q["skill"]),
                )
            db.commit()
            existing_questions = db.execute(
                "SELECT * FROM quiz_questions WHERE application_id = ? ORDER BY id", (application_id,)
            ).fetchall()

        return render_template("candidate/quiz.html", questions=existing_questions, application=application)

    # ---------------- Career-AI chat ----------------

    @app.route("/candidate/chat", methods=["POST"])
    @login_required(role="candidate")
    def candidate_chat():
        db = database.get_db()
        candidate = get_candidate_row(db, session["user_id"])
        message = request.json.get("message", "").strip() if request.is_json else request.form.get("message", "").strip()

        if not message:
            return jsonify({"reply": "Please type a question.", "available": False})

        applications = db.execute(
            """SELECT applications.*, jobs.title AS job_title, jobs.required_skills
               FROM applications JOIN jobs ON jobs.id = applications.job_id
               WHERE applications.candidate_id = ?""",
            (candidate["id"],),
        ).fetchall()

        context_parts = [
            f"Candidate skills: {candidate['extracted_skills'] or '[]'}",
            f"Resume AI score: {candidate['resume_score']}",
        ]
        for a in applications:
            context_parts.append(
                f"Applied to '{a['job_title']}' - match: {a['match_score']}%, "
                f"quiz: {a['quiz_score']}%, missing skills: {a['missing_skills']}"
            )
        context_text = "\n".join(context_parts)

        result = llm_service.career_chat(message, context_text)
        return jsonify(result)
