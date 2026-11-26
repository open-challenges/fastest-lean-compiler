# Where untrusted code runs: building an entry's toolchain, and that toolchain building the workload.
# scripts/verify.py runs it with no network, no capabilities and a read-only root.
FROM ubuntu:24.04
RUN apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
      ca-certificates git cmake make clang libgmp-dev libuv1-dev libssl-dev pkgconf python3 time \
    && rm -rf /var/lib/apt/lists/*
