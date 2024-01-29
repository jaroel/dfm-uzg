FROM python:3.12-slim-bookworm
WORKDIR /app
COPY src .
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD ["uvicorn", "server:app"]
