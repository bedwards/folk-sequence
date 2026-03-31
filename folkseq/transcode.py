"""Transcode source .mov to YouTube-optimized .mp4 with fades."""

import re
import subprocess
from pathlib import Path

SOURCE_DIR = Path("/Volumes/Lacie/videos/folk-sequence")
OUTPUT_DIR = Path("output")

EPISODE_RE = re.compile(r"Folk Sequence (\d{3})")


def _probe_duration(input_path):
    """Get video duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(input_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ffprobe failed: {result.stderr.strip()}")
        raise SystemExit(1)

    try:
        return float(result.stdout.strip())
    except ValueError:
        print(f"Could not parse duration from ffprobe output: {result.stdout.strip()!r}")
        raise SystemExit(1)


def _extract_episode(input_path):
    """Extract zero-padded episode number from filename."""
    match = EPISODE_RE.search(input_path.stem)
    if not match:
        print(f"Could not extract episode number from: {input_path.name}")
        print("Expected filename like: Folk Sequence 001.mov")
        raise SystemExit(1)
    return match.group(1)


def transcode(input_path, output=None, dry_run=False):
    """Transcode a source .mov to YouTube-optimized .mp4."""
    input_path = Path(input_path)

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        raise SystemExit(1)

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        episode = _extract_episode(input_path)
        output_path = OUTPUT_DIR / f"folk-sequence-{episode}.mp4"

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Probe duration for fade-out calculation
    print(f"Probing duration: {input_path}")
    duration = _probe_duration(input_path)
    fade_out_start = duration - 3.0
    print(f"Duration: {duration:.1f}s — fade out at {fade_out_start:.1f}s")

    # Build ffmpeg command
    vf = (
        f"crop=4096:2304:0:12,"
        f"scale=3840:2160:flags=lanczos,"
        f"fade=t=in:st=0:d=0.5,"
        f"fade=t=out:st={fade_out_start}:d=3"
    )
    af = (
        f"loudnorm=I=-14:TP=-1:LRA=11,"
        f"afade=t=in:st=0:d=0.5,"
        f"afade=t=out:st={fade_out_start}:d=3"
    )

    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-profile:v", "high", "-level", "5.1", "-preset", "slow",
        "-b:v", "35M", "-maxrate", "40M", "-bufsize", "80M",
        "-r", "60", "-g", "30", "-bf", "2", "-flags", "+cgop",
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-af", af,
        "-c:a", "aac", "-b:a", "384k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-y", str(output_path),
    ]

    if dry_run:
        print("Dry run — ffmpeg command:")
        print(" ".join(cmd))
        return

    # Run ffmpeg (inherit stdio for progress output)
    print(f"Transcoding: {input_path.name} -> {output_path}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"ffmpeg exited with code {result.returncode}")
        raise SystemExit(1)

    # Summary
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Done.")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path}")
    print(f"  Size:   {size_mb:.1f} MB")
