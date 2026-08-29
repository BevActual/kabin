#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
bin_dir="$HOME/.local/bin"

mkdir -p "$bin_dir"
cat > "$bin_dir/kabin" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$project_root\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m kabin "\$@"
EOF
chmod +x "$bin_dir/kabin"

mkdir -p "$applications_dir"
cp "$project_root/data/kabin.desktop" "$applications_dir/kabin.desktop"
rm -f "$applications_dir/omagames.desktop" "$bin_dir/omagames"
update-desktop-database "$applications_dir" >/dev/null 2>&1 || true

echo "Installed. Launch with 'kabin' (make sure $bin_dir is on PATH) or from your app launcher as 'Kabin'."
