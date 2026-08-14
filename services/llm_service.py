"""
services/llm_service.py
-------------------------
LLM-based resume evaluation using a locally running Ollama server with the
Gemma 3 4B model (Section 9 of spec), plus the Career-AI chat feature
(Section 25).

If Ollama is not running or the model is not pulled, every function here
fails gracefully and returns a structured "unavailable" result instead of
raising - the calling route always has something safe to render.
"""

import json
import re
import requests
from flask import current_app

RESUME_EVAL_PROMPT = """You are an expert technical recruiter. Evaluate the following resume text
for a candidate applying to the role of: {role}

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

Respond with ONLY valid JSON in exactly this shape, no extra commentary:
{{
  "score": <integer 0-100>,
  "summary": "<2-3 sentence summary>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "concerns": ["<concern 1>", "<concern 2>"]
}}
"""

CHAT_SYSTEM_PROMPT = """You are Career-AI, a helpful and honest career assistant inside the
TalentLens AI recruitment platform. You help candidates understand their skill gaps,
resume evaluation, and match scores. Be concise, encouraging, and specific.
Do not make hiring decisions - only the recruiter decides. Use the context provided."""


def _ollama_available():
    try:
        resp = requests.get(f"{current_app.config['OLLAMA_HOST']}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _extract_json(text):
    """Pull the first JSON object out of an LLM response, tolerating extra text."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def evaluate_resume(resume_text, applied_role="the applied position"):
    """
    Send the resume text to Gemma 3 4B (via Ollama) for evaluation.

    Returns a dict:
        {
          "available": bool,
          "score": int | None,
          "summary": str,
          "strengths": list[str],
          "concerns": list[str],
          "error": str | None
        }
    """
    if not resume_text or not resume_text.strip():
        return {
            "available": False, "score": None, "summary": "",
            "strengths": [], "concerns": [],
            "error": "No resume text available to evaluate.",
        }

    if not _ollama_available():
        return {
            "available": False, "score": None, "summary": "",
            "strengths": [], "concerns": [],
            "error": (
                "The LLM evaluation service (Ollama + Gemma 3 4B) is not currently "
                "running. Start Ollama and pull the model to enable AI resume evaluation."
            ),
        }

    prompt = RESUME_EVAL_PROMPT.format(role=applied_role, resume_text=resume_text[:6000])

    try:
        resp = requests.post(
            f"{current_app.config['OLLAMA_HOST']}/api/generate",
            json={
                "model": current_app.config["OLLAMA_MODEL"],
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=current_app.config["OLLAMA_TIMEOUT_SECONDS"],
        )
        resp.raise_for_status()
        raw_text = resp.json().get("response", "")
        parsed = _extract_json(raw_text)

        if not parsed or "score" not in parsed:
            return {
                "available": False, "score": None, "summary": "",
                "strengths": [], "concerns": [],
                "error": "The LLM returned an unexpected response format.",
            }

        score = max(0, min(100, int(parsed.get("score", 0))))
        return {
            "available": True,
            "score": score,
            "summary": str(parsed.get("summary", ""))[:1000],
            "strengths": list(parsed.get("strengths", []))[:10],
            "concerns": list(parsed.get("concerns", []))[:10],
            "error": None,
        }

    except requests.exceptions.RequestException as exc:
        return {
            "available": False, "score": None, "summary": "",
            "strengths": [], "concerns": [],
            "error": f"Could not reach Ollama: {exc}",
        }
    except (ValueError, KeyError) as exc:
        return {
            "available": False, "score": None, "summary": "",
            "strengths": [], "concerns": [],
            "error": f"Unexpected LLM response: {exc}",
        }


def career_chat(user_message, context_text):
    """
    Career-AI chat used on the candidate dashboard (Section 25).

    Returns dict: {"available": bool, "reply": str}
    """
    if not _ollama_available():
        return {
            "available": False,
            "reply": (
                "Career-AI is currently unavailable because Ollama is not running. "
                "Start Ollama and pull the gemma3:4b model to chat with Career-AI. "
                "In the meantime, check your Skill Gap Analysis section on the dashboard."
            ),
        }

    full_prompt = f"{CHAT_SYSTEM_PROMPT}\n\nContext about the candidate:\n{context_text}\n\nCandidate question: {user_message}\n\nAnswer:"

    try:
        resp = requests.post(
            f"{current_app.config['OLLAMA_HOST']}/api/generate",
            json={
                "model": current_app.config["OLLAMA_MODEL"],
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": 0.4},
            },
            timeout=current_app.config["OLLAMA_TIMEOUT_SECONDS"],
        )
        resp.raise_for_status()
        reply = resp.json().get("response", "").strip()
        if not reply:
            return {"available": False, "reply": "Career-AI did not return a response. Please try again."}
        return {"available": True, "reply": reply}
    except requests.exceptions.RequestException as exc:
        return {"available": False, "reply": f"Career-AI is unavailable right now ({exc})."}
