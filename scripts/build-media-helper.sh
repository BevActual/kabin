#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="$project_root/build"
mkdir -p "$output_dir"

cc -std=c17 -O2 -Wall -Wextra -DGST_USE_UNSTABLE_API \
  "$project_root/native/kabin-media-helper.c" \
  -o "$output_dir/kabin-media-helper" \
  $(pkg-config --cflags --libs \
    gstreamer-1.0 gstreamer-webrtc-1.0 gstreamer-sdp-1.0)

echo "$output_dir/kabin-media-helper"
