#!/bin/bash
set -eu
cd "$(dirname "$0")"
mkdir -p segments

still() {
  local img=$1 dur=$2 out=$3 zoom=${4:-0.00045}
  ffmpeg -y -loglevel error -loop 1 -t "$dur" -i "$img" \
    -vf "scale=1920:1080,zoompan=z='min(zoom+${zoom},1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=24,fade=t=in:st=0:d=0.35,fade=t=out:st=$(echo "$dur-0.4" | bc):d=0.4,format=yuv420p" \
    -r 24 -c:v libx264 -crf 18 -pix_fmt yuv420p "$out"
}

card() {
  local img=$1 dur=$2 out=$3
  ffmpeg -y -loglevel error -loop 1 -t "$dur" -i "$img" \
    -vf "scale=1920:1080,fade=t=in:st=0:d=0.4,fade=t=out:st=$(echo "$dur-0.4" | bc):d=0.4,format=yuv420p" \
    -r 24 -c:v libx264 -crf 18 -pix_fmt yuv420p "$out"
}

card card_intro.png 5 segments/00_intro.mp4
ffmpeg -y -loglevel error -i ../blender/graph_hero_glow.mp4 \
  -vf "setpts=2*PTS,fps=24,fade=t=in:st=0:d=0.4,fade=t=out:st=9.6:d=0.4,format=yuv420p" \
  -t 10 -r 24 -c:v libx264 -crf 18 -pix_fmt yuv420p segments/01_hero.mp4
still overlay_graph.png 8 segments/02_graph.mp4
still overlay_build.png 10 segments/03_build.mp4 0.0003
still overlay_cost.png 8 segments/04_cost.mp4
still overlay_ricci.png 8 segments/05_ricci.mp4
still overlay_debt.png 6 segments/06_debt.mp4
card card_close.png 5 segments/07_close.mp4

printf "file '%s'\n" segments/*.mp4 > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -t 60 -c copy cut60.mp4
ffprobe -v error -show_entries format=duration -of default=nw=1 cut60.mp4
ls -lh cut60.mp4
