import io
from typing import Callable

# https://stackoverflow.com/questions/56260336/how-to-escape-from-the-standard-output-redirection-in-python
class CaptureOutput(io.TextIOBase):
    def __init__(self, callback: Callable, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback

    def write(self, s):
        super().write(s)
        self.callback(s)
