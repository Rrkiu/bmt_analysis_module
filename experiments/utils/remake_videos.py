import os
import re
import shutil
import subprocess
from pathlib import Path

# =========================
# ✅ 여기에 폴더 경로 박아넣기
# =========================
INPUT_DIR = r"/mnt/b/cd_p/bmt_demo/_adutils/rebulid"
OUTPUT_DIR = r"/mnt/b/cd_p/bmt_demo/_adutils/rebuilt"
WORK_DIR = r"/mnt/b/cd_p/bmt_demo/_adutils/_work_frames"  # 임시 프레임 폴더 (용량 큼)

# 기본 FPS (ffprobe 실패 시 사용)
DEFAULT_FPS = 30.0

# 오디오 처리: True면 오디오 버림(가장 안정적). False면 오디오도 붙이려고 시도(실패 시 자동으로 비디오만)
DROP_AUDIO = True


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run subprocess and raise with helpful output."""
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"{' '.join(cmd)}\n\n"
            f"STDOUT:\n{p.stdout}\n\n"
            f"STDERR:\n{p.stderr}\n"
        )
    return p


def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def get_fps_ffprobe(video_path: Path) -> float:
    """
    Try to get FPS via ffprobe.
    Uses avg_frame_rate; if '0/0' or parse fails, returns DEFAULT_FPS.
    """
    try:
        p = run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(video_path)
        ])
        s = p.stdout.strip()
        if not s or s == "0/0":
            return DEFAULT_FPS
        if "/" in s:
            num, den = s.split("/", 1)
            num_f, den_f = float(num), float(den)
            if den_f == 0:
                return DEFAULT_FPS
            fps = num_f / den_f
        else:
            fps = float(s)

        # sanity clamp
        if fps <= 0 or fps > 240:
            return DEFAULT_FPS
        return fps
    except Exception:
        return DEFAULT_FPS


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def clear_dir(p: Path):
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def rebuild_one(video_path: Path, out_dir: Path, work_root: Path):
    base = sanitize_name(video_path.stem)
    frames_dir = work_root / f"{base}_frames"
    ensure_dir(out_dir)

    print(f"\n=== Processing: {video_path.name} ===")

    fps = get_fps_ffprobe(video_path)
    print(f"-> FPS (estimated): {fps:.3f}")

    # 1) Extract frames
    clear_dir(frames_dir)
    frame_pattern = str(frames_dir / "frame_%06d.png")

    # -vsync 0 : 가능하면 원본 타임스탬프 기반으로 프레임을 그대로 뽑기
    # decode 오류가 있는 경우에도 최대한 뽑히는 만큼 뽑게 됨
    try:
        run([
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "warning",
            "-i", str(video_path),
            "-vsync", "0",
            frame_pattern
        ])
    except Exception as e:
        # 정말 심하게 깨진 파일은 디코더가 중간에 죽을 수 있음
        # 그런 경우 에러 로그를 보여주고 중단
        raise

    # 프레임이 하나도 없으면 실패 처리
    extracted = sorted(frames_dir.glob("frame_*.png"))
    if not extracted:
        raise RuntimeError(f"No frames extracted from {video_path}")

    print(f"-> Extracted frames: {len(extracted)}")

    # 2) Rebuild mp4 from frames
    out_path = out_dir / f"{base}_rbd.mp4"

    # 이미지 시퀀스 -> mp4
    # -framerate : 입력 프레임레이트
    # -r        : 출력 프레임레이트(CFR로 맞춤)
    # -pix_fmt yuv420p : 호환성 최우선
    # -movflags +faststart : 스트리밍/웹 재생 친화
    common_encode = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "warning",
        "-framerate", f"{fps}",
        "-i", frame_pattern,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-r", f"{fps}",
    ]

    if DROP_AUDIO:
        cmd = common_encode + [str(out_path)]
        run(cmd)
    else:
        # 오디오까지 붙이려면: 원본 오디오를 다시 매핑해보되,
        # 깨진 파일에서 오디오도 문제일 수 있으므로 실패 시 비디오만 생성
        try:
            cmd = common_encode + [
                "-i", str(video_path),
                "-map", "0:v:0",
                "-map", "1:a:0?",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(out_path)
            ]
            run(cmd)
        except Exception:
            print("-> Audio mux failed; retrying without audio...")
            cmd = common_encode + [str(out_path)]
            run(cmd)

    print(f"-> Output: {out_path}")


def main():
    in_dir = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR)
    work_root = Path(WORK_DIR)

    ensure_dir(out_dir)
    ensure_dir(work_root)

    mp4s = sorted(in_dir.glob("*.mp4"))
    if not mp4s:
        print(f"No mp4 files in: {in_dir}")
        return

    print(f"Found {len(mp4s)} mp4 files in: {in_dir}")
    print(f"Output dir: {out_dir}")
    print(f"Work dir:   {work_root}")
    print(f"DROP_AUDIO: {DROP_AUDIO}")

    ok, fail = 0, 0
    for v in mp4s:
        try:
            rebuild_one(v, out_dir, work_root)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"!! FAILED: {v.name}")
            print(e)

    print("\n=== Done ===")
    print(f"Success: {ok}, Failed: {fail}")
    print(f"Outputs in: {out_dir}")


if __name__ == "__main__":
    main()
