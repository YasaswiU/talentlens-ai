"""
routes/recruiter.py
----------------------
All recruiter-facing Flask routes.
"""

import json
import io
import os

import pandas as pd
from flask import render_template, request, redirect, url_for, session, flash, Response

import database
from routes.utils import login_required
from config import Config


def register_recruiter_routes(app):

    def _application_rows_for_recruiter(db, recruiter_id, job_id=None):
        query = """
            SELECT applications.*, candidates.name AS candidate_name, candidates.experience,
                   candidates.resume_score, candidates.extracted_skills, users.email AS candidate_email,
                   jobs.title AS job_title, jobs.required_skills, jobs.id AS job_id_ref
            FROM applications
            JOIN candidates ON candidates.id = applications.candidate_id
            JOIN users ON users.id = candidates.user_id
            JOIN jobs ON jobs.id = applications.job_id
            WHERE jobs.recruiter_id = ?
        """
        params = [recruiter_id]
        if job_id:
            query += " AND jobs.id = ?"
            params.append(job_id)
        query += " ORDER BY applications.created_at DESC"
        return db.execute(query, params).fetchall()

    # ---------------- Dashboard ----------------

    @app.route("/recruiter/dashboard")
    @login_required(role="recruiter")
    def recruiter_dashboard():
        db = database.get_db()
        recruiter_id = session["user_id"]

        applications = _application_rows_for_recruiter(db, recruiter_id)
        total_candidates = len({a["candidate_id"] for a in applications})
        resumes_processed = len([a for a in applications if a["resume_score"] is not None])
        match_scores = [a["match_score"] for a in applications if a["match_score"] is not None]
        avg_match = round(sum(match_scores) / len(match_scores), 2) if match_scores else 0
        predicted_selected = len([a for a in applications if a["prediction"] == "Selected"])

        jobs = db.execute("SELECT * FROM jobs WHERE recruiter_id = ? ORDER BY created_at DESC", (recruiter_id,)).fetchall()

        return render_template(
            "recruiter/dashboard.html",
            total_candidates=total_candidates,
            resumes_processed=resumes_processed,
            avg_match=avg_match,
            predicted_selected=predicted_selected,
            applications=applications[:10],
            jobs=jobs,
        )

    # ---------------- Job postings ----------------

    @app.route("/recruiter/jobs")
    @login_required(role="recruiter")
    def recruiter_jobs():
        db = database.get_db()
        jobs = db.execute(
            "SELECT * FROM jobs WHERE recruiter_id = ? ORDER BY created_at DESC", (session["user_id"],)
        ).fetchall()
        jobs_view = [{**dict(j), "required_skills_list": json.loads(j["required_skills"])} for j in jobs]
        return render_template("recruiter/jobs.html", jobs=jobs_view)

    @app.route("/recruiter/jobs/new", methods=["GET", "POST"])
    @login_required(role="recruiter")
    def new_job():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            skills_raw = request.form.get("required_skills", "").strip()
            try:
                min_exp = float(request.form.get("minimum_experience", 0) or 0)
            except ValueError:
                min_exp = 0

            if not title or not description or not skills_raw:
                flash("Please fill in title, description, and required skills.", "error")
                return render_template("recruiter/job_new.html")

            required_skills = [s.strip().lower() for s in skills_raw.split(",") if s.strip()]
            if not required_skills:
                flash("Please provide at least one required skill.", "error")
                return render_template("recruiter/job_new.html")

            db = database.get_db()
            db.execute(
                """INSERT INTO jobs (recruiter_id, title, description, required_skills, minimum_experience)
                   VALUES (?, ?, ?, ?, ?)""",
                (session["user_id"], title, description, json.dumps(required_skills), min_exp),
            )
            db.commit()
            flash("Job posting created.", "success")
            return redirect(url_for("recruiter_jobs"))

        return render_template("recruiter/job_new.html")

    @app.route("/recruiter/jobs/<int:job_id>/toggle", methods=["POST"])
    @login_required(role="recruiter")
    def toggle_job_status(job_id):
        db = database.get_db()
        job = db.execute("SELECT * FROM jobs WHERE id = ? AND recruiter_id = ?", (job_id, session["user_id"])).fetchone()
        if not job:
            flash("Job not found.", "error")
            return redirect(url_for("recruiter_jobs"))
        new_status = "closed" if job["status"] == "open" else "open"
        db.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
        db.commit()
        flash(f"Job marked as {new_status}.", "success")
        return redirect(url_for("recruiter_jobs"))

    # ---------------- Candidates ----------------

    @app.route("/recruiter/candidates")
    @login_required(role="recruiter")
    def recruiter_candidates():
        db = database.get_db()
        job_id = request.args.get("job_id", type=int)
        applications = _application_rows_for_recruiter(db, session["user_id"], job_id)
        jobs = db.execute("SELECT id, title FROM jobs WHERE recruiter_id = ?", (session["user_id"],)).fetchall()
        return render_template("recruiter/candidates.html", applications=applications, jobs=jobs, selected_job_id=job_id)

    @app.route("/recruiter/candidates/<int:application_id>")
    @login_required(role="recruiter")
    def candidate_detail(application_id):
        db = database.get_db()
        row = db.execute(
            """SELECT applications.*, candidates.name AS candidate_name, candidates.experience,
                      candidates.resume_score, candidates.extracted_skills, candidates.llm_summary,
                      candidates.llm_strengths, candidates.llm_concerns, candidates.resume_filename,
                      users.email AS candidate_email,
                      jobs.title AS job_title, jobs.description AS job_description,
                      jobs.required_skills, jobs.minimum_experience, jobs.recruiter_id
               FROM applications
               JOIN candidates ON candidates.id = applications.candidate_id
               JOIN users ON users.id = candidates.user_id
               JOIN jobs ON jobs.id = applications.job_id
               WHERE applications.id = ?""",
            (application_id,),
        ).fetchone()

        if not row or row["recruiter_id"] != session["user_id"]:
            flash("Candidate application not found.", "error")
            return redirect(url_for("recruiter_candidates"))

        from services import scoring
        candidate_skills = json.loads(row["extracted_skills"]) if row["extracted_skills"] else []
        required_skills = json.loads(row["required_skills"]) if row["required_skills"] else []
        missing_skills = json.loads(row["missing_skills"]) if row["missing_skills"] else []
        matched_skills = sorted(set(s.lower() for s in candidate_skills) & set(s.lower() for s in required_skills))

        final_score, breakdown = scoring.compute_final_score(
            row["match_score"], row["quiz_score"], row["skills_score"], row["experience_score"]
        )

        quiz_result = db.execute(
            "SELECT * FROM quiz_results WHERE application_id = ?", (application_id,)
        ).fetchone()

        return render_template(
            "recruiter/candidate_detail.html",
            row=row,
            candidate_skills=candidate_skills,
            required_skills=required_skills,
            missing_skills=missing_skills,
            matched_skills=matched_skills,
            breakdown=breakdown,
            final_score=final_score,
            strengths=json.loads(row["llm_strengths"]) if row["llm_strengths"] else [],
            concerns=json.loads(row["llm_concerns"]) if row["llm_concerns"] else [],
            quiz_result=quiz_result,
        )

    @app.route("/recruiter/candidates/<int:application_id>/action", methods=["POST"])
    @login_required(role="recruiter")
    def candidate_action(application_id):
        db = database.get_db()
        action = request.form.get("action")
        if action not in ("approved", "rejected", "pending"):
            flash("Invalid action.", "error")
            return redirect(url_for("candidate_detail", application_id=application_id))

        # Ensure this application belongs to this recruiter
        row = db.execute(
            """SELECT applications.id FROM applications
               JOIN jobs ON jobs.id = applications.job_id
               WHERE applications.id = ? AND jobs.recruiter_id = ?""",
            (application_id, session["user_id"]),
        ).fetchone()
        if not row:
            flash("Application not found.", "error")
            return redirect(url_for("recruiter_candidates"))

        db.execute("UPDATE applications SET status = ? WHERE id = ?", (action, application_id))
        db.commit()
        flash(f"Candidate marked as {action}.", "success")
        return redirect(url_for("candidate_detail", application_id=application_id))

    # ---------------- Ranked candidates ----------------

    @app.route("/recruiter/ranked")
    @login_required(role="recruiter")
    def ranked_candidates():
        db = database.get_db()
        job_id = request.args.get("job_id", type=int)
        applications = _application_rows_for_recruiter(db, session["user_id"], job_id)
        ranked = sorted(applications, key=lambda a: (a["final_score"] or 0), reverse=True)
        jobs = db.execute("SELECT id, title FROM jobs WHERE recruiter_id = ?", (session["user_id"],)).fetchall()
        return render_template("recruiter/ranked.html", applications=ranked, jobs=jobs, selected_job_id=job_id)

    # ---------------- CSV export ----------------

    @app.route("/recruiter/export-csv")
    @login_required(role="recruiter")
    def export_csv():
        db = database.get_db()
        job_id = request.args.get("job_id", type=int)
        applications = _application_rows_for_recruiter(db, session["user_id"], job_id)

        data = [{
            "Candidate Name": a["candidate_name"],
            "Job": a["job_title"],
            "Match Score": a["match_score"],
            "Resume Score": a["resume_score"],
            "Quiz Score": a["quiz_score"],
            "Skills Score": a["skills_score"],
            "Experience Score": a["experience_score"],
            "Final Score": a["final_score"],
            "Prediction": a["prediction"],
            "Status": a["status"],
        } for a in applications]

        df = pd.DataFrame(data)
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=talentlens_ai_candidates.csv"},
        )

    # ---------------- Analytics ----------------

    @app.route("/recruiter/analytics")
    @login_required(role="recruiter")
    def recruiter_analytics():
        metrics = None
        if os.path.exists(Config.MODEL_METRICS_PATH):
            with open(Config.MODEL_METRICS_PATH) as f:
                metrics = json.load(f)

        chart_exists = os.path.exists(Config.FEATURE_IMPORTANCE_CHART)

        limitations = [
            "Random Forest training data is synthetic and has not been validated on real hiring outcomes.",
            "TF-IDF matching is lexical and may miss synonyms or paraphrased skills.",
            "Skill extraction currently depends on a fixed 40-term vocabulary.",
            "LLM output can vary between runs.",
            "No fairness/bias audit has been performed yet.",
        ]

        return render_template(
            "recruiter/analytics.html", metrics=metrics, chart_exists=chart_exists, limitations=limitations
        )
