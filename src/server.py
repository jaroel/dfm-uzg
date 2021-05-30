import datetime
import dataclasses
import functools
import pathlib
from typing import List

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

month_names = {
    1: 'Januari',
    2: 'Februari',
    3: 'Maart',
    4: 'April',
    5: 'Mei',
    6: 'Juni',
    7: 'Juli',
    8: 'Augustus',
    9: 'September',
    10: 'Oktober',
    11: 'November',
    12: 'December'
}

day_names = {
    0: 'maandag',
    1: 'dinsdag',
    2: 'woensdag',
    3: 'donderdag',
    4: 'vrijdag',
    5: 'zaterdag',
    6: 'zondag'
}

day_names_short = {
    0: 'ma',
    1: 'di',
    2: 'wo',
    3: 'do',
    4: 'vr',
    5: 'za',
    6: 'zo'
}


@dataclasses.dataclass
@functools.total_ordering
class File:
    datetime: datetime.datetime
    name: str
    size: int

    def __lt__(self, other):
        return self.datetime < other.datetime

    def title(self):
        day = day_names[self.datetime.weekday() % 7].lower()
        month = month_names[self.datetime.month]
        year = self.datetime.year
        return f'Uitzending van {day} {self.datetime.day} {month} {year}'

    def size_display(self):
        size = int(self.size / 1024 / 1024)
        return f'{size} MB'


@app.get('/', response_class=HTMLResponse)
async def ftp_listing(request: Request):
    async with aioftp.Client.context(**creds) as client:
        ftp_files = dict(await client.list())

    now = datetime.datetime.now()

    files: List[File] = []

    for path, metadata in ftp_files.items():
        path = pathlib.Path(path)
        if path.suffix != '.mp3':
            continue
        try:
            day, month, year = path.stem[:10].split('-')
            hour, minute = path.stem[11:].split('-')
            date = datetime.datetime(
                int(year), int(month), int(day), int(hour), int(minute)
            )
        except:
            continue
        files.append(
            File(name=path.name, size=int(metadata['size']), datetime=date)
        )

    files.sort()

    # Latest mp3 might not be there just yet.
    if files and files[-1].datetime == now.replace(second=0, microsecond=0):
        files = files[:-1]

    years = {}
    for f in files:
        months: dict = years.setdefault(f.datetime.year, {})
        days: dict = months.setdefault(f.datetime.month, {})
        items: List = days.setdefault(f.datetime.day, [])
        items.append(f)

    return templates.TemplateResponse(
        'index.html', {'request': request, 'years': years, 'month_names': month_names, 'day_names': day_names, 'day_names_short': day_names_short}
    )


@app.get('/fetch/{filename}', name='fetch')
async def ftp_fetch(request: Request, filename: str):
    async with aioftp.Client.context(**creds) as client:
        files = [x.name for x in dict(await client.list()).keys()]

    if filename not in files:
        raise HTTPException(404, 'File not found!')

    return StreamingResponse(
        stream_file(filename),
        media_type='audio/mpeg',
        headers={
            'content-disposition': 'attachment; filename="{}"'.format(filename)
        },
    )


async def stream_file(filename):
    async with aioftp.Client.context(**creds) as client:
        async with client.download_stream(filename) as stream:
            async for block in stream.iter_by_block():
                yield block
