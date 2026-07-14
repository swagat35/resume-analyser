"""
Streamlit frontend for the AI Resume Analyzer.
Pure Python — calls the FastAPI backend over HTTP.

Run locally:
    streamlit run frontend/streamlit_app.py
"""
import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄", layout="centered")
st.title("📄 AI Resume Analyzer")
st.caption("Upload your resume and a job description to get an instant match score and feedback.")

with st.form("analyze_form"):
    resume_file = st.file_uploader("Upload resume (PDF or DOCX, max 2MB)", type=["pdf", "docx"])
    job_description = st.text_area("Paste the job description", height=220)
    submitted = st.form_submit_button("Analyze")

if submitted:
    if not resume_file:
        st.error("Please upload a resume file.")
    elif not job_description or len(job_description.strip()) < 20:
        st.error("Please paste a job description (at least 20 characters).")
    else:
        with st.spinner("Analyzing your resume..."):
            try:
                files = {"resume": (resume_file.name, resume_file.getvalue(), resume_file.type)}
                data = {"job_description": job_description}
                response = requests.post(
                    f"{BACKEND_URL}/api/v1/analyze", files=files, data=data, timeout=30
                )
                response.raise_for_status()
                result = response.json()
            except requests.exceptions.Timeout:
                st.error("The analysis took too long. Please try again.")
                st.stop()
            except requests.exceptions.HTTPError:
                detail = response.json().get("detail", "Something went wrong.")
                st.error(detail)
                st.stop()
            except requests.exceptions.RequestException:
                st.error("Could not reach the backend service. Is it running?")
                st.stop()

        st.subheader(f"Match Score: {result['match_score']}/100")
        st.progress(min(int(result["match_score"]), 100) / 100)

        st.markdown("### ✅ Matching Skills")
        st.write(", ".join(result["skill_gap"]["matching_skills"]) or "None found")

        st.markdown("### ⚠️ Missing Skills")
        st.write(", ".join(result["skill_gap"]["missing_skills"]) or "None — great coverage!")

        st.markdown("### 💪 Strengths")
        for s in result["strengths"]:
            st.markdown(f"- {s}")

        st.markdown("### 🛠️ Suggestions")
        for s in result["suggestions"]:
            st.markdown(f"- {s}")

        st.markdown("### 📝 Summary")
        st.write(result["summary"])

st.divider()
st.caption("Your resume is processed in memory and never stored with identifying details.")
