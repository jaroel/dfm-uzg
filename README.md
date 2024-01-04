## Install:

- python3.12 -m venv .
- source bin/activate.fish
- pip install -r requirements.txt

## Run dev:

- source bin/activate.fish
- cd src
- uvicorn server:app --reload

## What does it use?

- fastapi
- aoiftp
- jinja2

## Usage:

- http://localhost:8000/docs
- JSON listing: http://localhost:8000/uzg/listing
- Stream the audio/mpeg data: http://localhost:8000/uzg/listing/fetch/[filename.mp3]
