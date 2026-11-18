#!/bin/bash
# 渋谷シーンの全フレームをレンダリングし、ノイズを減らして mp4 にする
set -e
cd "$(dirname "$0")"
mkdir -p frames
blender -b shibuya.blend -o "//frames/f_####" -F PNG -a
ffmpeg -y -loglevel error -framerate 24 -i frames/f_%04d.png \
  -vf "nlmeans=s=2.5:p=5:r=9,hqdn3d=2:2:3:3" \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart shibuya_scramble.mp4
ls -la shibuya_scramble.mp4
