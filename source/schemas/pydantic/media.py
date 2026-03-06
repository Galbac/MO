from pydantic import BaseModel


class MediaFile(BaseModel):
    id: int
    filename: str
    content_type: str
    url: str
    size: int | None = None
