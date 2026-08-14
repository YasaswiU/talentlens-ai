"""
services/scoring.py
---------------------
Transparent scoring calculations (Sections 16-18, 30).

All functions return plain floats (0-100) and are deliberately simple so
that every number can be explained during a project viva.
"""

from config import Config


def compute_skills_score(candidate_skills, required_skills):
    """
    Skills Score = (number of required skills the candidate has) / (number of
    required skills) x 100.

    Example: required = 5, candidate has 4 -> 80.0
    """
    required = set(s.lower() for s in required_skills)
    if not required:
        return 0.0
    candidate = set(s.lower() for s in candidate_skills)
    matched = required & candidate
    return round((len(matched) / len(required)) * 100, 2)


def compute_experience_score(candidate_experience, required_experience):
    """
    Experience Score:
      - If required_experience <= 0: candidate automatically gets 100
        (job has no explicit experience requirement).
      - If candidate_experience >= required_experience: 100
      - Otherwise: proportional score, capped between 0 and 100.
    """
    if required_experience is None or required_experience <= 0:
        return 100.0
    if candidate_experience is None:
        candidate_experience = 0
    if candidate_experience >= required_experience:
        return 100.0
    score = (candidate_experience / required_experience) * 100
    return round(max(0.0, min(100.0, score)), 2)


def compute_final_score(resume_match, quiz_score, skills_score, experience_score):
    """
    Final Score = 0.40*ResumeMatch + 0.30*Quiz + 0.20*Skills + 0.10*Experience

    Returns:
        (final_score: float, breakdown: dict) - breakdown is used to render
        the transparent "why this score" explanation on candidate/recruiter
        detail pages (Section 30).
    """
    resume_match = resume_match or 0
    quiz_score = quiz_score or 0
    skills_score = skills_score or 0
    experience_score = experience_score or 0

    weighted = {
        "resume_match": {"value": resume_match, "weight": Config.WEIGHT_RESUME_MATCH,
                          "contribution": round(resume_match * Config.WEIGHT_RESUME_MATCH, 2)},
        "quiz_score": {"value": quiz_score, "weight": Config.WEIGHT_QUIZ,
                        "contribution": round(quiz_score * Config.WEIGHT_QUIZ, 2)},
        "skills_score": {"value": skills_score, "weight": Config.WEIGHT_SKILLS,
                          "contribution": round(skills_score * Config.WEIGHT_SKILLS, 2)},
        "experience_score": {"value": experience_score, "weight": Config.WEIGHT_EXPERIENCE,
                              "contribution": round(experience_score * Config.WEIGHT_EXPERIENCE, 2)},
    }
    final_score = round(sum(v["contribution"] for v in weighted.values()), 2)
    return final_score, weighted


def compute_missing_skills(candidate_skills, required_skills):
    """Skill Gap = Required Skills - Candidate Skills (Section 11)."""
    candidate = set(s.lower() for s in candidate_skills)
    required = set(s.lower() for s in required_skills)
    return sorted(required - candidate)
