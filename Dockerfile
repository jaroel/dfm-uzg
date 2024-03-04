FROM python:3.12-slim-bookworm
EXPOSE 8000
WORKDIR /app
COPY src .
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD python -m uvicorn server:app --host 0.0.0.0 --port 80
