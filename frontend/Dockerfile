FROM python:3.11-slim

WORKDIR /app

COPY frontend/ ./frontend/
RUN pip install --no-cache-dir streamlit requests

EXPOSE 8501

CMD ["streamlit", "run", "frontend/streamlit_app.py", "--server.address=0.0.0.0"]
