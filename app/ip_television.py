import time
import base64
import subprocess
import shlex
import json
import os
import signal
from threading import Thread


def ffprobe(path):
    cmd = "ffprobe -v quiet -print_format json -show_streams"
    args = shlex.split(cmd)
    args.append(path)
    ffprobe_output = subprocess.check_output(args).decode("utf-8")
    ffprobe_output = json.loads(ffprobe_output)
    return ffprobe_output


def get_codecs(url):
    streams = ffprobe(url)["streams"]
    video_codec = next(
        (s.get("codec_name") for s in streams if s.get("codec_type") == "video"), None
    )
    audio_codec = next(
        (s.get("codec_name") for s in streams if s.get("codec_type") == "audio"), None
    )
    return video_codec, audio_codec


def convert(url, path):
    video_codec, audio_codec = get_codecs(url)
    return subprocess.Popen(
        " ".join(
            [
                "ffmpeg",
                "-loglevel panic",
                "-nostdin",
                f'-i "{url}"',
                "-vcodec libx264 -preset ultrafast -vf scale=640:-1"
                if video_codec != "h264"
                else "-vcodec copy",
                "-acodec aac -ab 128k -ac 2"
                if audio_codec != "aac"
                else "-acodec copy",
                "-f hls",
                "-hls_flags delete_segments",
                "-hls_time 10",
                "-hls_init_time 30",
                "-hls_list_size 5",
                f'"{path}"',
            ]
        ),
        shell=True,
        preexec_fn=os.setsid,
    )


class IPTelevision:
    def __init__(self, channel_map):
        self.channel_id = None
        self.conversion = None
        self.loading = False
        Thread(target=self._loop).start()

    def change_channel(self, channel_id):
        if channel_id != self.channel_id:
            self.channel_id = channel_id
            if self.conversion:
                self.loading = True
                try:
                    os.killpg(os.getpgid(self.conversion.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def _loop(self):
        while True:
            if self.channel_id:
                channel_id = self.channel_id
                url = base64.b64decode(channel_id.encode("ascii")).decode("ascii")
                path = f"/tmp/{channel_id}.m3u8"
                try:
                    self.loading = True
                    os.system("rm -rf /tmp/*")
                    self.conversion = convert(url, path)
                    time.sleep(2)
                    while not os.path.isfile(path):
                        if self.channel_id != channel_id:
                            break
                        time.sleep(2)
                    else:
                        self.loading = False
                        self.conversion.wait()
                except Exception as e:
                    print(e, flush=True)
            else:
                self.conversion = None
            time.sleep(2)
