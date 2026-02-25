from datetime import datetime
from dotenv import load_dotenv
from typing_extensions import TypedDict
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import gspread
from google.oauth2.service_account import Credentials
from pypdf import PdfReader

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langgraph.graph import StateGraph, START, END

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "service_account.json"
SHEET_NAME = os.getenv("GSHEET_NAME", "Resume_Analyzer_Logs")

GEMINI_TIMEOUT = 45
SHEETS_TIMEOUT = 20

def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()

def safe_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        return {}

def invoke_gemini_with_timeout(prompt: str) -> str:
    def _call():
        return llm.invoke(prompt).content.strip()

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_call)
        return fut.result(timeout=GEMINI_TIMEOUT)

def append_to_sheet_with_timeout(row: list):
    def _call():
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        ws = gc.open(SHEET_NAME).sheet1
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_call)
        return fut.result(timeout=SHEETS_TIMEOUT)

class AgentState(TypedDict):
    input: str
    output: str

def agent_node(state: AgentState) -> AgentState:
    user_input = (state.get("input") or "").strip()
    if not user_input:
        return {"input": "", "output": "Empty input. Use: PDF_PATH=resume.pdf || JOB=... (optional)"}

    pdf_path = ""
    job_desc = ""
    parts = [p.strip() for p in user_input.split("||")]
    for p in parts:
        if p.startswith("PDF_PATH="):
            pdf_path = p.replace("PDF_PATH=", "").strip().strip("'").strip('"')
        elif p.startswith("JOB="):
            job_desc = p.replace("JOB=", "").strip()

    if not pdf_path:
        return {"input": user_input, "output": "Missing PDF_PATH. Example: PDF_PATH=resume.pdf || JOB=Data Engineer"}

    try:
        resume_text = extract_text_from_pdf(pdf_path)
    except Exception as e:
        return {"input": user_input, "output": f"Could not read PDF: {e}"}

    if not resume_text:
        return {"input": user_input, "output": "PDF has no readable text (maybe scanned). Use a text-based PDF."}

    analysis_prompt = f"""
You are a technical resume analyzer for software/data roles.
Be direct, ATS-aware, and practical. No fluff.

RESUME TEXT:
{resume_text[:18000]}

JOB DESCRIPTION (optional):
{(job_desc or '')[:8000]}

Return ONLY valid JSON (no markdown, no extra text) with exactly these keys:
name, email, phone, resume_score, strengths, gaps, missing_keywords, improvements, role_fit_summary
"""

    # 1) Gemini call with hard timeout
    try:
        raw = invoke_gemini_with_timeout(analysis_prompt)
    except TimeoutError:
        return {"input": user_input, "output": f"❌ Gemini call timed out after {GEMINI_TIMEOUT}s."}
    except ChatGoogleGenerativeAIError as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            return {"input": user_input, "output": "❌ Gemini quota/rate limit exceeded (429 RESOURCE_EXHAUSTED). Enable billing / wait / new key."}
        return {"input": user_input, "output": f"❌ Gemini error: {e}"}
    except Exception as e:
        return {"input": user_input, "output": f"❌ Unexpected Gemini error: {e}"}

    data = safe_json(raw)
    if not data:
        return {"input": user_input, "output": "❌ Model returned invalid JSON. Try again with a cleaner resume PDF."}

    # 2) Sheets logging with hard timeout
    ts = datetime.utcnow().isoformat()
    row = [
        ts,
        data.get("name", ""),
        data.get("email", ""),
        data.get("phone", ""),
        int(data.get("resume_score", 0) or 0),
        json.dumps(data.get("strengths", []), ensure_ascii=False),
        json.dumps(data.get("gaps", []), ensure_ascii=False),
        json.dumps(data.get("missing_keywords", []), ensure_ascii=False),
        json.dumps(data.get("improvements", []), ensure_ascii=False),
        data.get("role_fit_summary", ""),
        (resume_text[:300] + "...") if len(resume_text) > 300 else resume_text
    ]

    try:
        append_to_sheet_with_timeout(row)
    except TimeoutError:
        # return analysis anyway
        return {"input": user_input, "output": json.dumps(data, indent=2, ensure_ascii=False) + f"\n\n⚠️ Sheets logging timed out after {SHEETS_TIMEOUT}s."}
    except Exception as e:
        return {"input": user_input, "output": json.dumps(data, indent=2, ensure_ascii=False) + f"\n\n⚠️ Sheets logging failed: {e}"}

    return {"input": user_input, "output": json.dumps(data, indent=2, ensure_ascii=False)}

graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_edge(START, "agent")
graph.add_edge("agent", END)
app = graph.compile()