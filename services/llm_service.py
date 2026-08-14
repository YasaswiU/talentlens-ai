"""
services/llm_service.py
-----------------------
LLM-based resume evaluation and Career-AI chat using the Groq API.

The rest of the application continues to use:
    evaluate_resume()
    career_chat()

The API key is read from the GROQ_API_KEY environment variable.
"""

import json
import re
from flask import current_app
from groq import Groq


RESUME_EVAL_PROMPT = """You are an expert technical recruiter.

Evaluate the following resume for a candidate applying to the role of: {role}

Consider:
- relevance to the applied role
- technical skills present
- experience level
- project relevance
- resume completeness

Resume text:
\"\"\"
{resume_text}
\"\"\"

Respond with ONLY valid JSON in exactly this shape:

{{
  "score": <integer 0-100>,
  "summary": "<2-3 sentence summary>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "concerns": ["<concern 1>", "<concern 2>"]
}}
"""


CHAT_SYSTEM_PROMPT = """You are Career-AI, a helpful and honest career assistant
inside the TalentLens AI recruitment platform.

You help candidates understand:
- their skill gaps
- resume evaluation
- match scores
- quiz performance
- areas for improvement

Be concise, encouraging, and specific.

Do not make hiring decisions. Only the recruiter decides.
Use the candidate context provided.
"""


def _get_client():
    """Create a Groq client using the environment API key."""

    api_key = current_app.config.get("GROQ_API_KEY")

    if not api_key:
        return None

    return Groq(api_key=api_key)


def _extract_json(text):
    """Extract the first JSON object from an LLM response."""

    if not text:
        return None

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def evaluate_resume(resume_text, applied_role="the applied position"):
    """
    Evaluate a resume using the Groq LLM.

    Returns:

    {
        "available": bool,
        "score": int | None,
        "summary": str,
        "strengths": list,
        "concerns": list,
        "error": str | None
    }
    """

    if not resume_text or not resume_text.strip():
        return {
            "available": False,
            "score": None,
            "summary": "",
            "strengths": [],
            "concerns": [],
            "error": "No resume text available to evaluate.",
        }

    client = _get_client()

    if client is None:
        return {
            "available": False,
            "score": None,
            "summary": "",
            "strengths": [],
            "concerns": [],
            "error": (
                "The AI evaluation service is not configured. "
                "Please configure the GROQ_API_KEY environment variable."
            ),
        }

    prompt = RESUME_EVAL_PROMPT.format(
        role=applied_role,
        resume_text=resume_text[:6000],
    )

    try:
        response = client.chat.completions.create(
            model=current_app.config["GROQ_MODEL"],
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.2,
            max_tokens=500,
        )

        raw_text = response.choices[0].message.content or ""

        parsed = _extract_json(raw_text)

        if not parsed or "score" not in parsed:
            return {
                "available": False,
                "score": None,
                "summary": "",
                "strengths": [],
                "concerns": [],
                "error": "The AI returned an unexpected response format.",
            }

        try:
            score = int(parsed.get("score", 0))
        except (ValueError, TypeError):
            score = 0

        score = max(0, min(100, score))

        strengths = parsed.get("strengths", [])
        concerns = parsed.get("concerns", [])

        if not isinstance(strengths, list):
            strengths = []

        if not isinstance(concerns, list):
            concerns = []

        return {
            "available": True,
            "score": score,
            "summary": str(parsed.get("summary", ""))[:1000],
            "strengths": [str(x) for x in strengths[:10]],
            "concerns": [str(x) for x in concerns[:10]],
            "error": None,
        }

    except Exception as exc:
        return {
            "available": False,
            "score": None,
            "summary": "",
            "strengths": [],
            "concerns": [],
            "error": f"AI resume evaluation failed: {exc}",
        }


def career_chat(user_message, context_text):
    """
    Career-AI chat used on the candidate dashboard.

    Returns:

    {
        "available": bool,
        "reply": str
    }
    """

    if not user_message or not user_message.strip():
        return {
            "available": False,
            "reply": "Please enter a question.",
        }

    client = _get_client()

    if client is None:
        return {
            "available": False,
            "reply": (
                "Career-AI is currently unavailable because the "
                "GROQ_API_KEY is not configured."
            ),
        }

    full_prompt = f"""
{CHAT_SYSTEM_PROMPT}

Context about the candidate:
{context_text}

Candidate question:
{user_message}

Answer:
"""

    try:
        response = client.chat.completions.create(
            model=current_app.config["GROQ_MODEL"],
            messages=[
                {
                    "role": "system",
                    "content": CHAT_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        f"Candidate context:\n{context_text}\n\n"
                        f"Candidate question:\n{user_message}"
                    ),
                },
            ],
            temperature=0.4,
            max_tokens=500,
        )

        reply = response.choices[0].message.content or ""
        reply = reply.strip()

        if not reply:
            return {
                "available": False,
                "reply": "Career-AI did not return a response. Please try again.",
            }

        return {
            "available": True,
            "reply": reply,
        }

    except Exception as exc:
        return {
            "available": False,
            "reply": f"Career-AI is unavailable right now ({exc}).",
        }