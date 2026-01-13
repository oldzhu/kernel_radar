#!/usr/bin/env bash
set -euo pipefail

# Create a modified syzkaller repro file for issue #3 that avoids unrelated subsystems.
# We keep the original syzbot bundle intact: the input is repro/<extid>/repro.syz
# and we generate repro/<extid>/repro.local.syz.

EXTID=${EXTID:-a9528028ab4ca83e8bac}
ROOT_DIR=${ROOT_DIR:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}
BUNDLE_DIR=${BUNDLE_DIR:-"$ROOT_DIR/repro/$EXTID"}

IN="$BUNDLE_DIR/repro.syz"
OUT="$BUNDLE_DIR/repro.local.syz"

if [[ ! -f "$IN" ]]; then
  echo "ERROR: missing $IN" >&2
  exit 2
fi

cp -a "$IN" "$OUT"

# Minimal transform: turn off wifi + ieee802154 setup to avoid cfg80211/mac80211/ieee802154 crashes.
# This only touches the JSON options line.
sed -i \
  -e 's/"wifi":true/"wifi":false/g' \
  -e 's/"ieee802154":true/"ieee802154":false/g' \
  "$OUT"

echo "[ok] wrote $OUT"
