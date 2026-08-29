#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
bin_dir="$HOME/.local/bin"

mkdir -p "$bin_dir"
cat > "$bin_dir/omagames" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$project_root\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m omagames "\$@"
EOF
chmod +x "$bin_dir/omagames"

mkdir -p "$applications_dir"
cp "$project_root/data/omagames.desktop" "$applications_dir/omagames.desktop"
update-desktop-database "$applications_dir" >/dev/null 2>&1 || true

echo "Installed. Launch with 'omagames' (make sure $bin_dir is on PATH) or from your app launcher as 'Games'."
