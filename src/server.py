import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse

import aioftp


creds = {'host': '86.81.98.192', 'user': 'UZG', 'password': '4862KpZ2'}


app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')

templates = Jinja2Templates(directory='templates')


class File:
    year: int
    month: int


@app.get('/', response_class=HTMLResponse)
async def ftp_listing(request: Request):
    async with aioftp.Client.context(**creds) as client:
        files = dict(await client.list())

    files = sorted(files.items(), key=lambda item: item[1]['modify'], reverse=True)
    files = [x for x in files if x[0].name.endswith('.mp3')]

    # Latest mp3 might not be there just yet.
    if files and files[0][0].name[11:13] == str(datetime.datetime.now().hour):
        files = files[1:]

    entries = []
    for entry in files:
        filename = entry[0].name
        entries.append(
            {
                'filename': filename,
                'date': '-'.join(reversed(filename[:10].split('-'))),
                'time': filename[11:16].replace('-', ':'),
            }
        )

    return templates.TemplateResponse('index.html', {'request': request, 'entries': entries})


@app.get('/fetch/{filename}', name='fetch')
async def ftp_fetch(request: Request, filename: str):
    async with aioftp.Client.context(**creds) as client:
        files = [x.name for x in dict(await client.list()).keys()]

    if filename not in files:
        raise HTTPException(404, 'File not found!')

    return StreamingResponse(
        stream_file(filename),
        media_type='audio/mpeg',
        headers={'content-disposition': 'attachment; filename="{}"'.format(filename)},
    )


async def stream_file(filename):
    async with aioftp.Client.context(**creds) as client:
        async with client.download_stream(filename) as stream:
            async for block in stream.iter_by_block():
                yield block
