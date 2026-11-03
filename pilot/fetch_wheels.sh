#!/bin/sh
# Downloads the pinned wheels and extracts each into its own directory.
# Wheels are untrusted data: they are only parsed, never imported or run.
set -e
OUT="${1:-pilot_data}"
mkdir -p "$OUT/wheels" "$OUT/projA" "$OUT/projB"
pip download --no-deps -q -d "$OUT/wheels" \
  virtualenv==20.26.3 distlib==0.3.8 filelock==3.15.4 platformdirs==4.2.2 \
  GitPython==3.1.43 gitdb==4.0.11 smmap==5.0.1
extract() {
  proj="$1"; shift
  for w in "$@"; do
    n=$(basename "$OUT"/wheels/$w-*.whl .whl | cut -d- -f1,2)
    mkdir -p "$OUT/$proj/$n"
    python3 -m zipfile -e "$OUT"/wheels/$w-*.whl "$OUT/$proj/$n"
  done
}
extract projA virtualenv distlib filelock platformdirs
extract projB GitPython gitdb smmap
