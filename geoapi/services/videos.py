import ffmpeg
import uuid
import os
from typing import IO


class VideoService:
    """
    Utilities for handling video uploads
    """
    @staticmethod
    def transcode(filePath: str) -> IO:
        """
        Transcode a video from whatever format to mp4 with ffmpeg
        :param filePath: str
        :return: IO file descriptor of transcoded file in /tmp directory
        """
        asset_uuid = uuid.uuid4()
        outPath = os.path.join("/tmp", str(asset_uuid)+'.mp4')
        ffmpeg.input(filePath).output(outPath).run()
        with open(outPath, 'rb') as fd:
            yield fd