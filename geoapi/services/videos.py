import ffmpeg
import uuid
import os
from typing import IO


class VideoService:
    """
    Utilities for handling video uploads
    """
    @staticmethod
    def transcode(filePath: str) -> str:
        """
        Transcode a video from whatever format to mp4 with ffmpeg
        :param filePath: str
        :return: Path to transcoded file in /tmp directory
        """
        asset_uuid = uuid.uuid4()
        outPath = os.path.join("/tmp", str(asset_uuid)+'.mp4')
        ffmpeg.input(filePath).output(outPath).run()
        return outPath
