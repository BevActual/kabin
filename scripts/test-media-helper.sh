#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="$project_root/build"
mkdir -p "$output_dir"

cc -std=c17 -O2 -Wall -Wextra -D_GNU_SOURCE -DGST_USE_UNSTABLE_API \
  "$project_root/native/test_json_field.c" \
  -o "$output_dir/test_json_field" \
  $(pkg-config --cflags --libs \
    gstreamer-1.0 gstreamer-webrtc-1.0 gstreamer-sdp-1.0)

"$output_dir/test_json_field"
