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

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None


def _auth_headers() -> dict:
    if st.session_state.access_token:
        return {"Authorization": f"Bearer {st.session_state.access_token}"}
    return {}


# --- Sidebar: login / register / logout ---
with st.sidebar:
    st.header("Account")
    if st.session_state.access_token:
        st.success(f"Logged in as {st.session_state.user_email}")
        if st.button("Log out"):
            st.session_state.access_token = None
            st.session_state.user_email = None
            st.rerun()
    else:
        st.caption("Log in to save your analysis history. Not required to use the analyzer.")
        tab_login, tab_register = st.tabs(["Log in", "Sign up"])

        with tab_login:
            with st.form("login_form"):
                login_email = st.text_input("Email", key="login_email")
                login_password = st.text_input("Password", type="password", key="login_password")
                if st.form_submit_button("Log in"):
                    try:
                        r = requests.post(
                            f"{BACKEND_URL}/api/v1/auth/login",
                            data={"username": login_email, "password": login_password},
                            timeout=15,
                        )
                        if r.status_code == 200:
                            st.session_state.access_token = r.json()["access_token"]
                            st.session_state.user_email = login_email
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "Login failed."))
                    except requests.exceptions.RequestException:
                        st.error("Could not reach the backend service.")

        with tab_register:
            with st.form("register_form"):
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input(
                    "Password (min 8 characters)", type="password", key="reg_password"
                )
                if st.form_submit_button("Sign up"):
                    try:
                        r = requests.post(
                            f"{BACKEND_URL}/api/v1/auth/register",
                            json={"email": reg_email, "password": reg_password},
                            timeout=15,
                        )
                        if r.status_code == 201:
                            st.success("Account created! Please log in from the Log in tab.")
                        else:
                            st.error(r.json().get("detail", "Registration failed."))
                    except requests.exceptions.RequestException:
                        st.error("Could not reach the backend service.")

st.title("📄 AI Resume Analyzer")
st.caption("Upload your resume and a job description to get an instant match score and feedback.")

tab_analyze, tab_history = st.tabs(["Analyze", "History"])

with tab_analyze:
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
                        f"{BACKEND_URL}/api/v1/analyze",
                        files=files,
                        data=data,
                        headers=_auth_headers(),
                        timeout=30,
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

            if st.session_state.access_token:
                st.caption("Saved to your history.")
            else:
                st.caption("Log in (sidebar) to save results like this to your history.")

with tab_history:
    if not st.session_state.access_token:
        st.info("Log in from the sidebar to see your past analysis history.")
    else:
        try:
            r = requests.get(
                f"{BACKEND_URL}/api/v1/history", headers=_auth_headers(), timeout=15
            )
            if r.status_code == 200:
                history = r.json()
                if not history:
                    st.write("No analyses yet — run one from the Analyze tab.")
                else:
                    for item in history:
                        st.write(f"**{item['created_at'][:16].replace('T', ' ')}** — Match score: {item['match_score']}/100")
            else:
                st.error("Could not load history.")
        except requests.exceptions.RequestException:
            st.error("Could not reach the backend service.")

st.divider()
st.caption(
    "Your resume text is never stored. If logged in, only your match score and "
    "timestamp are saved to your history — never the resume content itself."
)
