📄 Tech Resume Analyzer

Gemini 2.5 Flash + LangChain + LangGraph + Google Sheets

An AI-powered system that evaluates technical resumes, scores them, identifies skill gaps, and logs structured feedback into Google Sheets.

🚀 Overview

This project uses Google Gemini 2.5 Flash to analyze resume PDFs and generate structured, ATS-aware feedback.

It extracts resume content, optionally compares it with a job description, assigns a score (0–100), and returns improvement suggestions in JSON format.

Each analysis is automatically logged into a Google Sheet for tracking.

🛠️ Tech Stack

Google Gemini 2.5 Flash

LangChain

LangGraph

Google Sheets API

pypdf

Python

⚙️ How It Works

Upload resume (PDF)

Extract text using pypdf

Send structured prompt to Gemini

Receive JSON output (score, strengths, gaps, keywords, improvements)

Log results to Google Sheets

📊 Example Output
{
  "resume_score": 82,
  "strengths": ["Strong Python projects"],
  "gaps": ["No quantified results"],
  "missing_keywords": ["Docker", "AWS"]
}
⚙️ Setup

Clone repo

Install dependencies

pip install -r requirements.txt

Add .env:

GOOGLE_API_KEY=your_key
GSHEET_NAME=Resume_Analyzer_Logs

Add service_account.json

Run:

python main.py

or

streamlit run app.py
📌 Notes

Requires active Gemini API quota

Does not support scanned image PDFs
