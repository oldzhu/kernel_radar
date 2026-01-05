FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Minimal, practical kernel-dev toolset for upstream contribution.
# Note: we intentionally do NOT configure SMTP inside the container.
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      git-email \
      less \
      locales \
      python3 \
      python3-venv \
      python3-pip \
      rsync \
      ripgrep \
      build-essential \
      bc \
      bison \
      flex \
      libssl-dev \
      libelf-dev \
      dwarves \
      ccache \
      clang \
      lld \
      kmod \
      cpio \
      pkg-config \
      xz-utils \
      zstd \
    && rm -rf /var/lib/apt/lists/*

# Enable UTF-8 locale to avoid tooling oddities.
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# b4 is very useful for kernel email workflow.
# Ubuntu usually has it as an apt package; if not, you can install it at runtime in a venv.
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends b4 && \
    rm -rf /var/lib/apt/lists/* \
    || true

WORKDIR /work

# Helpful defaults
ENV CCACHE_DIR=/work/.ccache
ENV PATH=/usr/lib/ccache:${PATH}
