#!/bin/bash
set -eu
cd "$(dirname "$0")"
mkdir -p segments

still() {
  local img=$1 dur=$2 out=$3 zoom=${4:-0.00035}
  ffmpeg -y -loglevel error -loop 1 -t "$dur" -i "$img" \
    -vf "scale=1920:1080,zoompan=z='min(zoom+${zoom},1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=24,fade=t=in:st=0:d=0.4,fade=t=out:st=$(echo "$dur-0.5" | bc):d=0.5,format=yuv420p" \
    -r 24 -c:v libx264 -crf 18 -pix_fmt yuv420p "$out"
}

card() {
  local img=$1 dur=$2 out=$3
  ffmpeg -y -loglevel error -loop 1 -t "$dur" -i "$img" \
    -vf "scale=1920:1080,fade=t=in:st=0:d=0.5,fade=t=out:st=$(echo "$dur-0.5" | bc):d=0.5,format=yuv420p" \
    -r 24 -c:v libx264 -crf 18 -pix_fmt yuv420p "$out"
}

card card_intro.png 10 segments/00_intro.mp4
card card_archive.png 13.5 segments/01_archive.mp4
ffmpeg -y -loglevel error -i ../blender/graph_hero_glow.mp4 \
  -vf "setpts=2*PTS,fps=24,fade=t=in:st=0:d=0.4,fade=t=out:st=9.6:d=0.4,format=yuv420p" \
  -t 10 -r 24 -c:v libx264 -crf 18 -pix_fmt yuv420p segments/02_hero.mp4
still overlay_graph.png 6 segments/03_graph.mp4
still overlay_build.png 20 segments/04_build.mp4 0.00025
card card_build.png 15 segments/05_cardbuild.mp4
still overlay_kcore.png 12 segments/06_kcore.mp4 0.0004
still overlay_critical.png 12.2 segments/07_critical.mp4 0.0003
still overlay_cost.png 18 segments/08_cost.mp4 0.0003
still overlay_ricci.png 27 segments/09_ricci.mp4 0.0002
still overlay_debt.png 21 segments/10_debt.mp4 0.0003
card card_verify.png 21.1 segments/11_verify.mp4
card card_credits.png 14.2 segments/12_credits.mp4

printf "file '%s'\n" segments/*.mp4 > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -t 200 -c copy cut210.mp4

ffmpeg -y -loglevel error -f lavfi -i "sine=frequency=55:sample_rate=48000:duration=200" \
  -f lavfi -i "sine=frequency=82.41:sample_rate=48000:duration=200" \
  -f lavfi -i "sine=frequency=110:sample_rate=48000:duration=200" \
  -filter_complex "[0][1][2]amix=inputs=3:duration=longest,volume=0.055,lowpass=f=900,afade=t=in:st=0:d=4,afade=t=out:st=196:d=4[a]" \
  -map "[a]" -c:a aac -b:a 160k bed.m4a
ffmpeg -y -loglevel error -i cut210.mp4 -i narration.mp3 -i bed.m4a \
  -filter_complex "[1:a]adelay=500|500,volume=1.0[voice];[2:a]volume=0.8[music];[music][voice]amix=inputs=2:duration=first:normalize=0[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k -shortest cut210_narrated.mp4
ffprobe -v error -show_entries format=duration -of default=nw=1 cut210_narrated.mp4
ls -lh cut210_narrated.mp4
