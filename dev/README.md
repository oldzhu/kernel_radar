# Containerized kernel-dev environment (Ubuntu 24.04)

This folder provides an **opt-in** container environment for building/testing the Linux kernel and running contribution tooling (`checkpatch.pl`, `get_maintainer.pl`, `b4`, etc.).

Principle: **build + tooling in container, email sending on host**.

## Quick start

1) Build/run an interactive shell:
- `./dev/run-container.sh --build`

2) In the container, run tools against your upstream linux checkout:
- `cd ~/linux`
- `./scripts/checkpatch.pl -g HEAD`
- `./scripts/get_maintainer.pl -f path/to/file.c`

3) Create patch files (in your linux repo):
- `git format-patch -1`

4) Send email from the host (simplest):
- `git send-email 0001-*.patch --to ... --cc ...`

## Out-of-tree build (recommended)

Kernel builds are I/O heavy; keep your source tree clean:
- `mkdir -p ~/linux-out`
- `make -C ~/linux O=~/linux-out defconfig`
- `make -C ~/linux O=~/linux-out -j"$(nproc)" W=1`

## Notes

- This container does **not** configure SMTP.
- If `b4` isn’t available via apt in the image, install it in a venv inside the container:
  - `python3 -m venv ~/.venv-b4 && ~/.venv-b4/bin/pip install b4 && ~/.venv-b4/bin/b4 --help`
