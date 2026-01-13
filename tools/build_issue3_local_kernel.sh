#!/usr/bin/env bash
set -euo pipefail

# Build a local kernel image from ~/mylinux/linux for syzbot issue #3 repro.
# - Uses the original syzbot kernel.config as baseline.
# - Applies a small config fragment enabling lockdep+tracing and disabling NILFS2.
# - Builds out-of-tree under repro/<extid>/localimage/build/.
# - Copies artifacts into repro/<extid>/localimage/ for A/B comparison.

EXTID=${EXTID:-a9528028ab4ca83e8bac}
REPO_ROOT=${REPO_ROOT:-"$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"}
BUNDLE_DIR=${BUNDLE_DIR:-"$REPO_ROOT/repro/$EXTID"}
LOCAL_DIR=${LOCAL_DIR:-"$BUNDLE_DIR/localimage"}
LINUX_TREE=${LINUX_TREE:-"$HOME/mylinux/linux"}

BASE_CONFIG=${BASE_CONFIG:-"$BUNDLE_DIR/kernel.config"}

# Prefer a tracked fragment in the repo (so changes get committed).
# Backward-compat: if the old per-bundle fragment exists, keep using it.
DEFAULT_FRAG_REPO="$REPO_ROOT/tools/issue3_localimage.fragment.config"
DEFAULT_FRAG_BUNDLE="$LOCAL_DIR/lockdep-trace-nonilfs.config"
if [[ -f "$DEFAULT_FRAG_BUNDLE" ]]; then
  FRAG_CONFIG=${FRAG_CONFIG:-"$DEFAULT_FRAG_BUNDLE"}
else
  FRAG_CONFIG=${FRAG_CONFIG:-"$DEFAULT_FRAG_REPO"}
fi
BUILD_DIR=${BUILD_DIR:-"$LOCAL_DIR/build"}

JOBS=${JOBS:-"$(nproc)"}

if [[ ! -d "$LINUX_TREE" || ! -f "$LINUX_TREE/Makefile" ]]; then
  echo "ERROR: LINUX_TREE does not look like a kernel tree: $LINUX_TREE" >&2
  exit 2
fi
if [[ ! -f "$BASE_CONFIG" ]]; then
  echo "ERROR: missing base config: $BASE_CONFIG" >&2
  exit 2
fi
if [[ ! -f "$FRAG_CONFIG" ]]; then
  echo "ERROR: missing fragment config: $FRAG_CONFIG" >&2
  exit 2
fi

mkdir -p "$BUILD_DIR"

echo "[build] linux_tree=$LINUX_TREE"
echo "[build] base_config=$BASE_CONFIG"
echo "[build] frag_config=$FRAG_CONFIG"
echo "[build] build_dir=$BUILD_DIR"

# Merge config into BUILD_DIR/.config
"$LINUX_TREE/scripts/kconfig/merge_config.sh" -m -r -O "$BUILD_DIR" "$BASE_CONFIG" "$FRAG_CONFIG"

# Finalize defaults
make -C "$LINUX_TREE" O="$BUILD_DIR" olddefconfig

# Build the kernel image (and vmlinux for symbols)
make -C "$LINUX_TREE" O="$BUILD_DIR" -j"$JOBS" bzImage vmlinux

# Stage artifacts for QEMU / debugging
cp -f "$BUILD_DIR/arch/x86/boot/bzImage" "$LOCAL_DIR/bzImage"
cp -f "$BUILD_DIR/System.map" "$LOCAL_DIR/System.map" || true
cp -f "$BUILD_DIR/.config" "$LOCAL_DIR/config" || true

# vmlinux can be large; keep it for addr2line. Compressing is optional.
cp -f "$BUILD_DIR/vmlinux" "$LOCAL_DIR/vmlinux"

echo "[build] done:"
ls -lh "$LOCAL_DIR/bzImage" "$LOCAL_DIR/vmlinux" | cat
