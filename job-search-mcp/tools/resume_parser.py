import json
import re
import logging
from pathlib import Path
from typing import Any

from config import GEMINI_API_KEY, RESUME_TEXT

try:
    from google import genai
except ImportError:
    genai = None

try:
    from pypdf import PdfReader  # type: ignore[import-not-found]
except ImportError:
    PdfReader = None

try:
    from docx import Document  # type: ignore[import-not-found]
except ImportError:
    Document = None

try:
    import pytesseract  # type: ignore[import-not-found]
    from pdf2image import convert_from_path  # type: ignore[import-not-found]
except ImportError:
    pytesseract = None
    convert_from_path = None

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

COMMON_SKILLS = [
    "python", "fastapi", "gcp", "google cloud", "vertex ai", "gemini", "bigquery",
    "firestore", "redis", "cloud run", "pubsub", "docker", "terraform", "sql",
    "ai", "ml", "rag", "mcp", "distributed systems", "asyncio", "system design"
]
SKILL_LABELS = {skill: skill.title() for skill in COMMON_SKILLS}
SKILL_LABELS.update({
    "google cloud": "Google Cloud", "vertex ai": "Vertex AI",
    "pubsub": "Pub/Sub"
})

def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def extract_text_from_file(file_path: str | Path) -> str:
    """
    Extract text from resume file (txt, md, pdf, docx).
    Falls back to OCR for scanned PDFs.
    """
    path = Path(file_path)
    extension = path.suffix.lower()
    text = ""
    if extension in {".txt", ".md", ".rst"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
    elif extension == ".pdf" and PdfReader:
        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
        except Exception as e:
            logger.warning(f"pypdf failed on {file_path}: {e}")
        # If no text was extracted, attempt OCR
        if not text and pytesseract and convert_from_path:
            try:
                images = convert_from_path(str(path))
                ocr_text = []
                for img in images:
                    ocr_text.append(pytesseract.image_to_string(img))
                text = "\n".join(ocr_text)
            except Exception as e:
                logger.error(f"OCR failed on {file_path}: {e}")
    elif extension == ".docx" and Document:
        try:
            doc = Document(str(path))
            text = "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            logger.error(f"python-docx failed on {file_path}: {e}")
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Unable to read {file_path}: {e}")

    return text or ""

def _extract_with_gemini(resume_text: str) -> dict[str, Any]:
    """
    Use Gemini (via Google genai) to extract structured profile.
    """
    if not GEMINI_API_KEY or genai is None:
        return {}
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        "You are extracting a structured candidate profile from a resume. "
        "Return ONLY valid JSON with keys: name, summary, skills, experience_years, projects, education.\n"
        f"Resume text:\n{resume_text}\n"
        "Expected JSON format:\n"
        "{\n"
        '  "name": null,\n'
        '  "summary": "2-sentence summary",\n'
        '  "skills": ["skill1", "skill2"],\n'
        '  "experience_years": 0,\n'
        '  "projects": ["project descriptions"],\n'
        '  "education": ["education details"]\n'
        "}"
    )
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = (response.text or "").strip()
        # Remove markdown fences if present
        cleaned = text.replace("```json", "").replace("```", "")
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Gemini parsing error: {e}")
        return {}

def extract_resume_profile(file_path: str | None = None, resume_text: str | None = None) -> dict[str, Any]:
    """
    Parse resume and return structured profile.
    """
    source_text = ""
    if file_path:
        source_text = extract_text_from_file(file_path)
    if not source_text and resume_text:
        source_text = resume_text
    if not source_text:
        source_text = RESUME_TEXT  # fallback test content

    cleaned = _clean_text(source_text)
    gemini_result = _extract_with_gemini(cleaned)

    # Extract name (prefer Gemini, else first non-empty line)
    name = gemini_result.get("name")
    if not name:
        first_line = cleaned.splitlines()[0].strip()
        name = first_line if first_line and len(first_line.split()) <= 3 else None

    # Extract email and phone via regex
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cleaned)
    phone_match = re.search(r"(\+?\d[\d\s-]{7,}\d)", cleaned)
    email = email_match.group(0) if email_match else None
    phone = phone_match.group(0) if phone_match else None

    # Skills: combine Gemini skills with keyword scanning
    skills = gemini_result.get("skills", []) or []
    lowered = cleaned.lower()
    for skill, label in SKILL_LABELS.items():
        if skill in lowered and label not in skills:
            skills.append(label)
    skills = list(dict.fromkeys(skills))

    # Projects from Gemini or simple parsing of bullet points
    projects = gemini_result.get("projects", []) or []
    if not projects:
        projects = [m.strip(" -") for m in re.findall(r"-\s(.+)", source_text)][:5]

    summary = gemini_result.get("summary") or (cleaned[:200] + "...")
    experience_years = gemini_result.get("experience_years") or 0
    if not experience_years:
        match = re.search(r"(\d+)\s+years", cleaned, re.IGNORECASE)
        experience_years = int(match.group(1)) if match else 0

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "summary": summary,
        "skills": skills,
        "experience_years": experience_years,
        "projects": projects,
        "education": gemini_result.get("education", []),
        "raw_text": cleaned
    }
