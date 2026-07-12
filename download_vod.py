import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHANNEL = "sektorlagg"
KICK_API_URL = f"https://kick.com/api/v2/channels/{CHANNEL}/videos"
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/mnt/workspace"))

GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_ENV = Path(os.environ["GITHUB_ENV"])


def write_env(name, value):
    """Guarda una variable para los siguientes pasos del workflow."""
    with GITHUB_ENV.open("a", encoding="utf-8") as env_file:
        env_file.write(f"{name}={value}\n")


def release_exists(tag_name):
    """Comprueba si ya existe una release para este VOD."""
    encoded_tag = urllib.parse.quote(tag_name, safe="")

    request = urllib.request.Request(
        (
            f"https://api.github.com/repos/"
            f"{GITHUB_REPOSITORY}/releases/tags/{encoded_tag}"
        ),
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "vod-release-workflow",
        },
    )

    try:
        with urllib.request.urlopen(request):
            return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


request = urllib.request.Request(
    KICK_API_URL,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) "
            "Gecko/20100101 Firefox/152.0"
        ),
        "Accept": "application/json",
    },
)

with urllib.request.urlopen(request) as response:
    videos = json.load(response)

WORKSPACE.mkdir(parents=True, exist_ok=True)

(WORKSPACE / "videos.json").write_text(
    json.dumps(videos, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

videos = sorted(
    (
        video
        for video in videos
        if video.get("is_live") is not True and video.get("source")
    ),
    key=lambda video: (
        video.get("created_at", ""),
        str(video.get("id", "")),
    ),
)

selected_video = None

for video in videos:
    tag_name = f"vod-{video['id']}"

    if not release_exists(tag_name):
        selected_video = video
        break

if selected_video is None:
    write_env("HAS_VOD", "false")
    print("No hay VODs pendientes para publicar.")
    raise SystemExit(0)

video_id = selected_video["id"]
created_at = str(selected_video.get("created_at", "unknown"))
video_date = created_at.split("T")[0].split(" ")[0]

tag_name = f"vod-{video_id}"
file_name = f"{CHANNEL}_{video_date}_{video_id}.ts"

video_directory = WORKSPACE / f"{video_date}_{video_id}"
video_directory.mkdir(parents=True, exist_ok=True)

(video_directory / "video.json").write_text(
    json.dumps(selected_video, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

output_path = video_directory / file_name

subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-i",
        selected_video["source"],
        "-c",
        "copy",
        str(output_path),
    ],
    check=True,
)

write_env("HAS_VOD", "true")
write_env("VOD_ID", video_id)
write_env("VOD_DATE", video_date)
write_env("VOD_CREATED_AT", created_at)
write_env("VOD_DIR", video_directory)
write_env("FILE_NAME", file_name)
write_env("RELEASE_TAG", tag_name)
write_env(
    "RELEASE_NAME",
    f"{CHANNEL} VOD - {video_date} - {video_id}",
)

print(f"VOD seleccionado: {video_id} ({created_at})")
