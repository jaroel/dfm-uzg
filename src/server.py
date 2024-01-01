import pathlib
from datetime import datetime
from operator import attrgetter
from typing import TypedDict

import aioftp
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import computed_field
from pydantic.dataclasses import dataclass

creds = {"host": "dinxperfm.freeddns.org", "user": "UZG", "password": "4862KpZ2"}

type Files = list[File]


@dataclass
class File:
    datetime: datetime
    name: str
    size: int

    @computed_field
    @property
    def key(self) -> int:
        return int(self.datetime.timestamp())


class FileMetadata(TypedDict):
    size: str


type FtpFiles = list[tuple[pathlib.Path, FileMetadata]]


async def fetch_ftp_listing() -> Files:
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

    if files is []:
        return []

    files.sort(key=attrgetter("datetime"))

    # Current hour will not be fully written to disk yet.
    latest_file = files[-1]
    current_hour = datetime.now().replace(second=0, microsecond=0)
    if latest_file.datetime == current_hour:
        files = files[:-1]

    return files


app = FastAPI()


@app.get("/uzg/listing")
async def uzg_listing() -> Files:
    return await fetch_ftp_listing()


async def stream_file_from_ftp_server(filename):
    async with aioftp.Client.context(**creds) as client:
        async with client.download_stream(filename) as stream:
            async for block in stream.iter_by_block():
                yield block


@app.get(
    "/uzg/fetch/{filename}.mp3",
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
