import dataclasses
from datetime import datetime
import functools
from operator import attrgetter
import pathlib
from typing import List, TypedDict

import aioftp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import computed_field

creds = {"host": "dinxperfm.freeddns.org", "user": "UZG", "password": "4862KpZ2"}
templates = Jinja2Templates(directory="templates")
month_names = {
    1: "Januari",
    2: "Februari",
    3: "Maart",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Augustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "December",
}
day_names = {
    0: "maandag",
    1: "dinsdag",
    2: "woensdag",
    3: "donderdag",
    4: "vrijdag",
    5: "zaterdag",
    6: "zondag",
}
day_names_short = {
    0: "ma",
    1: "di",
    2: "wo",
    3: "do",
    4: "vr",
    5: "za",
    6: "zo",
}


@dataclasses.dataclass
@functools.total_ordering
class File:
    datetime: datetime
    name: str
    size: int

    def __lt__(self, other):
        return self.datetime < other.datetime

    def title(self):
        day = day_names[self.datetime.weekday() % 7].lower()
        month = month_names[self.datetime.month]
        year = self.datetime.year
        return f"Uitzending van {day} {self.datetime.day} {month} {year}"

    def size_display(self):
        size = int(self.size / 1024 / 1024)
        return f"{size} MB"

    @computed_field
    @property
    def key(self) -> int:
        return int(self.datetime.timestamp())


class FileMetadata(TypedDict):
    size: str


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

type FtpFiles = list[tuple[pathlib.Path, FileMetadata]]


@app.get("/", response_class=HTMLResponse)
async def ftp_listing(request: Request):
    async with aioftp.Client.context(**creds) as client:
        ftp_files: FtpFiles = await client.list()

    now = datetime.now()

    files: List[File] = []

    for path, metadata in ftp_files:
        path = pathlib.Path(path)
        if path.suffix != ".mp3":
            continue
        try:
            day, month, year = path.stem[:10].split("-")
            hour, minute = path.stem[11:].split("-")
            date = datetime(int(year), int(month), int(day), int(hour), int(minute))
        except Exception:
            continue
        files.append(File(name=path.name, size=int(metadata["size"]), datetime=date))

    files.sort()

    # Latest mp3 might not be there just yet.
    if files and files[-1].datetime == now.replace(second=0, microsecond=0):
        files = files[:-1]

    years: dict[int, dict[int, dict[int, list[File]]]] = {}
    for f in files:
        months = years.setdefault(f.datetime.year, {})
        days = months.setdefault(f.datetime.month, {})
        items = days.setdefault(f.datetime.day, [])
        items.append(f)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "years": years,
            "month_names": month_names,
            "day_names": day_names,
            "day_names_short": day_names_short,
        },
    )


async def fetch_ftp_listing() -> list[File]:
    async with aioftp.Client.context(**creds) as client:
        ftp_files: FtpFiles = await client.list()

    files = [
        File(
            name=str(file_name),
            size=int(metadata["size"]),
            datetime=datetime.strptime(str(file_name), "%d-%m-%Y-%H-%M.mp3"),
        )
        for file_name, metadata in ftp_files
        if file_name.suffix == ".mp3"
    ]

    if files == []:
        return []

    files.sort(key=attrgetter("datetime"))

    # Current hour will not be fully written to disk yet.
    latest_file = files[-1]
    current_hour = datetime.now().replace(second=0, microsecond=0)
    if latest_file.datetime == current_hour:
        files = files[:-1]

    return files


@app.get("/listing")
async def uzg_listing() -> list[File]:
    return await fetch_ftp_listing()


async def stream_file_from_ftp_server(filename):
    async with aioftp.Client.context(**creds) as client:
        async with client.download_stream(filename) as stream:
            async for block in stream.iter_by_block():
                yield block


@app.get(
    "/fetch/{filename}.mp3",
    response_class=StreamingResponse,
    responses={200: {"content": {"audio/mpeg": {}}}},
)
async def ftp_fetch(filename: str):
    filename = filename + ".mp3"

    for file in await fetch_ftp_listing():
        if file.name == filename:
            break
    else:
        raise HTTPException(404)

    return StreamingResponse(
        content=stream_file_from_ftp_server(file.name),
        media_type="audio/mpeg",
        headers={"content-length": str(file.size)},
    )
