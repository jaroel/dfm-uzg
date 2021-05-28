Run dev:

cd src
uvicorn server:app --reload


todo:
list ftp files
fetch single file
    - store in static/files
serve static/files with nginx

In nginx use try_files to serve existing downloaded files.
For a missing file trigger download via fastapi.
