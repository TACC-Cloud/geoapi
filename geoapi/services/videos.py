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
        :param fileObj: IO
        :return: str filepath to transcoded file
        """
        asset_uuid = uuid.uuid4()
        outPath = os.path.join("/tmp", str(asset_uuid)+'.mp4')
        ffmpeg.input(filePath).output(outPath).run()
        fd = open(outPath, 'rb')
        return fd
