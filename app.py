import streamlit as st
import tempfile
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

st.set_page_config(page_title="Tech Resume Analyzer", layout="centered")
st.title("📄 Tech Resume Analyzer (Gemini + LangGraph + Google Sheets)")

st.write("✅ UI loaded")

# Import main app (LangGraph)
from main import app as graph_app
from pdf_utils import extract_text_from_pdf  # we will create this file below

uploaded = st.file_uploader("Upload Resume PDF", type=["pdf"])
job_desc = st.text_area("Optional: Paste Job Description (JD)", height=150)

TIMEOUT_SECONDS = 60  # hard timeout so app can't freeze forever

def run_agent(user_input: str):
    return graph_app.invoke({"input": user_input, "output": ""})

if st.button("Analyze"):
    if not uploaded:
        st.error("Please upload a resume PDF.")
        st.stop()

    st.info("Step 1/4: Saving PDF...")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.read())
        pdf_path = tmp.name
    st.success(f"Saved PDF: {pdf_path}")

    st.info("Step 2/4: Extracting text from PDF...")
    try:
        resume_text = extract_text_from_pdf(pdf_path)
    except Exception as e:
        st.error(f"PDF extraction failed: {e}")
        try:
            os.remove(pdf_path)
        except:
            pass
        st.stop()

    if not resume_text.strip():
        st.error("No readable text found in PDF (likely scanned image). Use a text-based PDF.")
        try:
            os.remove(pdf_path)
        except:
            pass
        st.stop()

    st.success("PDF text extracted ✅")
    st.write("Preview (first 300 chars):")
    st.code(resume_text[:300])

    st.info("Step 3/4: Calling Gemini + generating JSON (timeout enabled)...")
    user_input = f"PDF_PATH={pdf_path} || JOB={job_desc}"

    with st.spinner("Analyzing..."):
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(run_agent, user_input)
            try:
                result = future.result(timeout=TIMEOUT_SECONDS)
            except TimeoutError:
                st.error(f"❌ Timed out after {TIMEOUT_SECONDS}s. The model or Sheets call is hanging.")
                st.info("Next: we will isolate whether Gemini or Google Sheets is causing the hang.")
                try:
                    os.remove(pdf_path)
                except:
                    pass
                st.stop()
            except Exception as e:
                st.error(f"❌ Error while invoking agent: {e}")
                try:
                    os.remove(pdf_path)
                except:
                    pass
                st.stop()

    st.info("Step 4/4: Showing result...")
    st.subheader("✅ Output")
    st.code(result.get("output", "No output key found."), language="json")

    try:
        os.remove(pdf_path)
    except:
        pass