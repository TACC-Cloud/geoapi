from pydantic import BaseModel


class TapisFilePath(BaseModel):
    system: str
    path: str
