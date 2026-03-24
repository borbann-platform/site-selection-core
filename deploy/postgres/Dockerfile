FROM postgis/postgis:16-3.4

ARG PGVECTOR_VERSION=0.8.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
        postgresql-server-dev-16 \
    && mkdir -p /usr/lib/llvm-13/bin \
    && ln -s /usr/lib/llvm-16/bin/llvm-lto /usr/lib/llvm-13/bin/llvm-lto \
    && git clone --branch "v${PGVECTOR_VERSION}" --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make CLANG=clang-16 \
    && make CLANG=clang-16 install \
    && rm -rf /tmp/pgvector /usr/lib/llvm-13 \
    && apt-get purge -y --auto-remove \
        build-essential \
        git \
        postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*
