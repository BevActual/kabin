#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
bin_dir="$HOME/.local/bin"

"$project_root/scripts/build-media-helper.sh" >/dev/null

mkdir -p "$bin_dir"
cat > "$bin_dir/kabin" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$project_root\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m kabin "\$@"
EOF
chmod +x "$bin_dir/kabin"
ln -sf "$project_root/build/kabin-media-helper" "$bin_dir/kabin-media-helper"

mkdir -p "$applications_dir"
cp "$project_root/data/kabin.desktop" "$applications_dir/kabin.desktop"
mkdir -p "$icons_dir"
cp "$project_root/data/com.andrewbevington.Kabin.svg" "$icons_dir/com.andrewbevington.Kabin.svg"
rm -f "$applications_dir/omagames.desktop" "$bin_dir/omagames"
update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
gtk-update-icon-cache "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo "Installed. Launch with 'kabin' (make sure $bin_dir is on PATH) or from your app launcher as 'Kabin'."
