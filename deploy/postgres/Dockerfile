FROM postgis/postgis:16-3.4

ARG PGVECTOR_VERSION=0.8.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
        postgresql-server-dev-16 \
    && git clone --branch "v${PGVECTOR_VERSION}" --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make CLANG=clang-16 LLVM_CONFIG=/usr/bin/llvm-config-16 \
    && make CLANG=clang-16 LLVM_CONFIG=/usr/bin/llvm-config-16 install \
    && rm -rf /tmp/pgvector \
    && apt-get purge -y --auto-remove \
        build-essential \
        git \
        postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*
