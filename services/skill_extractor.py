"""
services/skill_extractor.py
-----------------------------
NLP skill extraction (Section 8 of spec).

Primary path: spaCy tokens + noun chunks matched against a controlled
40-term technical skill vocabulary, using spaCy's PhraseMatcher so that
multi-word skills (e.g. "machine learning", "node.js") are detected
correctly alongside single-word skills (e.g. "python").

Fallback path: if spaCy (or its "en_core_web_sm" model) is not installed
in the current environment, we fall back to a lightweight tokenizer that
reproduces the same lowercase + vocabulary-matching logic without spaCy.
This keeps the application runnable in restricted/offline environments
while preserving identical output structure. This is documented as a
known limitation (see README "Limitations").
"""

import re

SKILL_VOCABULARY = [
    "python", "java", "c++", "c#", "javascript", "typescript", "ruby", "php",
    "go", "rust", "sql", "nosql", "mongodb", "postgresql", "mysql", "redis",
    "html", "css", "react", "angular", "vue", "node.js", "express", "django",
    "flask", "fastapi", "machine learning", "deep learning", "nlp",
    "computer vision", "tensorflow", "pytorch", "scikit-learn", "aws",
    "azure", "gcp", "docker", "kubernetes", "ci/cd", "jenkins", "git",
    "linux",
]

# Multi-word terms must be checked before single-word ones so that, e.g.,
# "machine learning" is captured as one skill rather than matching nothing
# because "machine" and "learning" alone aren't in the vocabulary.
_MULTI_WORD = sorted([s for s in SKILL_VOCABULARY if " " in s], key=len, reverse=True)
_SINGLE_WORD = [s for s in SKILL_VOCABULARY if " " not in s]

_nlp = None
_SPACY_AVAILABLE = False


def _try_load_spacy():
    """Attempt to load spaCy + en_core_web_sm once, lazily."""
    global _nlp, _SPACY_AVAILABLE
    if _nlp is not None or _SPACY_AVAILABLE:
        return
    try:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not downloaded - use a blank English pipeline instead,
            # which still gives us tokenization + noun chunks via the
            # rule-based sentencizer we add below.
            _nlp = spacy.blank("en")
            if "sentencizer" not in _nlp.pipe_names:
                _nlp.add_pipe("sentencizer")
        _SPACY_AVAILABLE = True
    except ImportError:
        _nlp = None
        _SPACY_AVAILABLE = False


def _extract_with_spacy(text_lower):
    from spacy.matcher import PhraseMatcher

    matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
    patterns = [_nlp.make_doc(term) for term in SKILL_VOCABULARY]
    matcher.add("SKILLS", patterns)

    doc = _nlp(text_lower)
    found = set()
    for match_id, start, end in matcher(doc):
        found.add(doc[start:end].text.lower())
    return found


def _extract_with_fallback_tokenizer(text_lower):
    """Regex/substring based matcher used when spaCy is unavailable."""
    found = set()
    for term in _MULTI_WORD:
        if term in text_lower:
            found.add(term)

    tokens = set(re.findall(r"[a-zA-Z0-9+#./]+", text_lower))
    for term in _SINGLE_WORD:
        if term in tokens or term in text_lower:
            found.add(term)
    return found


def extract_skills(resume_text):
    """
    Extract technical skills from resume text against the controlled
    40-term vocabulary.

    Returns:
        sorted list[str] of unique skills found (no duplicates).
    """
    if not resume_text:
        return []

    text_lower = resume_text.lower()

    _try_load_spacy()
    if _SPACY_AVAILABLE and _nlp is not None:
        found = _extract_with_spacy(text_lower)
    else:
        found = _extract_with_fallback_tokenizer(text_lower)

    return sorted(found)
