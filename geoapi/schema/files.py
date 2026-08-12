from typing import Literal

from pydantic import BaseModel, Field


class FileInspectRequest(BaseModel):
    """A Tapis path to inspect -- a single file OR a directory (inspected recursively).

    POST (not GET) because ``path`` contains slashes/special chars that are awkward
    as query params, and inspect does real work (partial read + GDAL) that should
    not be triggered by a cache/prefetcher hitting a cacheable GET.
    """

    system_id: str
    path: str
    recursive: bool = Field(
        default=True, description="descend into sub-directories (default true)"
    )


class FileListRequest(BaseModel):
    """A Tapis path to list -- a single file OR a directory."""

    system_id: str
    path: str
    recursive: bool = Field(
        default=True,
        description="descend into sub-directories (default true). If false, list only "
        "the immediate children (files and folders).",
    )


class FileInspectResponse(BaseModel):
    """Deterministic geospatial verdict for a single file.

    The verdict is decided by GDAL/OGR/PDAL, never by an LLM. A raster with no CRS
    reports ``is_geospatial=False`` (likely a plain image) and says so in ``detail``.
    The inspect endpoint returns a LIST of these (see module docstring).
    """

    system: str = Field(default="", description="the Tapis system id")
    path: str = Field(default="", description="the inspected file's path")
    is_geospatial: bool
    kind: str | None = Field(
        default=None, description="raster | vector | pointcloud | image | null"
    )
    driver: str | None = None
    crs: str | None = None
    bounds: list[float] | None = Field(
        default=None, description="[minx, miny, maxx, maxy] in the file's own CRS"
    )
    size: list[int] | None = Field(
        default=None, description="[width, height] for rasters; null otherwise"
    )
    bands: int | None = None
    detail: str = Field(description="human-readable one-liner for the agent to relay")


class JobSubmitResponse(BaseModel):
    """The 202 body when a file job (inspect/list) is submitted: its id and status."""

    task_id: int
    status: str = Field(description="task status, e.g. QUEUED")


_JOB_STATUS_DESC = "QUEUED | RUNNING | COMPLETED | FAILED | ERROR | EXPIRED"


class FileInspectJobResponse(BaseModel):
    """An inspect job's status, plus the per-file verdicts once COMPLETED."""

    task_id: int
    status: str = Field(description=_JOB_STATUS_DESC)
    result: list[FileInspectResponse] | None = Field(
        default=None, description="per-file verdicts; present once status is COMPLETED"
    )
    error: str | None = Field(
        default=None, description="failure message when status is FAILED/ERROR/EXPIRED"
    )


class FileListJobResponse(BaseModel):
    """A list job's status, plus the per-file/dir entries once COMPLETED."""

    task_id: int
    status: str = Field(description=_JOB_STATUS_DESC)
    result: list["FileListEntry"] | None = Field(
        default=None, description="listing entries; present once status is COMPLETED"
    )
    error: str | None = Field(
        default=None, description="failure message when status is FAILED/ERROR/EXPIRED"
    )


class FileListEntry(BaseModel):
    """A cheap, extension-only listing entry -- no fetch, no GDAL.

    For a ``dir`` entry, ``extension``/``size``/``geospatial`` are null. For a ``file``,
    ``geospatial`` is guessed from the extension alone; for a real verdict use
    ``/files/inspect``.
    """

    system: str
    path: str
    type: Literal["file", "dir"]
    size: int | None = None
    extension: str | None = None  # e.g. ".tif", "" for extensionless
    geospatial: Literal["yes", "no", "maybe"] | None = Field(
        default=None,
        description="cheap extension-only guess for files (null for dirs) -- not a "
        "verdict, use /files/inspect for that",
    )


# FileListJobResponse forward-references FileListEntry (defined above now); resolve it.
FileListJobResponse.model_rebuild()
