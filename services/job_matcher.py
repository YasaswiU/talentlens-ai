"""
services/job_matcher.py
--------------------------
Job matching using TF-IDF vectorization + cosine similarity (Section 10).

similarity(R, J) = (R . J) / (||R|| * ||J||)

We rely on scikit-learn's TfidfVectorizer (English stop-word removal) and
sklearn.metrics.pairwise.cosine_similarity, which implements exactly the
formula above.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def compute_match_percentage(resume_text, job_description):
    """
    Compute the cosine-similarity match percentage between a candidate's
    resume text and a single job description.

    Returns:
        float match percentage in [0, 100]
    """
    if not resume_text or not job_description:
        return 0.0

    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf_matrix = vectorizer.fit_transform([resume_text, job_description])
    except ValueError:
        # Happens if both documents are empty after stop-word removal.
        return 0.0

    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(float(similarity) * 100, 2)


def best_matching_job(resume_text, jobs):
    """
    Given a resume text and a list of job rows (each with 'id', 'description'),
    return (best_job, match_percentage) for the highest scoring job.
    """
    best_job = None
    best_score = -1.0
    for job in jobs:
        score = compute_match_percentage(resume_text, job["description"])
        if score > best_score:
            best_score = score
            best_job = job
    return best_job, (best_score if best_score >= 0 else 0.0)
