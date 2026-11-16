# ============================================================================
# STAGE 1: Builder (python:3.15-slim)
# Purpose: Full CI environment - compile deps, run all tests/checks
# ============================================================================
FROM python:3.15-slim AS builder

WORKDIR /workspace

# Install build dependencies for packages that still need compile-time headers.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    gfortran \
    libopenblas-dev \
    libxml2-dev \
    libxslt-dev \
    pkg-config \
    python3-dev \
    git \
    ca-certificates \
    && \
    python -m pip install --no-cache-dir --prefer-binary --upgrade pip "setuptools>=78.1.1" wheel uv && \
    rm -rf /var/lib/apt/lists/*

# Diagnostic: Verify C++ compiler (key for scikit-learn Meson builds)
RUN echo "=== Compiler Verification ===" && \
    echo "gcc:" && which gcc && gcc --version && \
    echo "g++:" && which g++ && g++ --version && \
    echo "c++:" && which c++ && c++ --version && \
    echo "=== Done ==="

# Install runtime dependencies to /runtime-deps
RUN SITE_PACKAGES="$(python -c 'import site; print(site.getsitepackages()[0])')" && \
    mkdir -p /runtime-deps /dev-deps "$SITE_PACKAGES"

# Compile and install dependencies from requirement files in layers, smallest first
COPY requirements-dev.txt .
RUN uv pip install --python /usr/local/bin/python --target /dev-deps -r requirements-dev.txt

COPY pyrolysis_lignocellulosic_ai_training/requirements-base.txt .
RUN uv pip install --python /usr/local/bin/python --target /runtime-deps -r requirements-base.txt

# Layer for scientific dependencies, slowest and largest
COPY pyrolysis_lignocellulosic_ai_training/requirements-sci.txt .
RUN uv pip install --python /usr/local/bin/python --target /runtime-deps -r requirements-sci.txt

RUN printf '/runtime-deps\n/dev-deps\n' > "$SITE_PACKAGES/local-deps.pth"

# Ensure dependencies installed with --target are importable during the builder-stage CI checks.
ENV PYTHONPATH="/runtime-deps:/dev-deps"

# Copy only repo paths needed by the local CI gates
# Files
COPY pyproject.toml \
    run_local_ci.py \
    ./
# Directories
COPY pyrolysis_lignocellulosic_ai_training ./pyrolysis_lignocellulosic_ai_training
COPY scripts ./scripts
COPY tests ./tests
COPY utils ./utils

# Build-time quality gates (no bind mount required)
# Keep privacy out of build: privacy scan should run against mounted host workspace at container runtime.
RUN /usr/local/bin/python run_local_ci.py --tests --security --deps-audit --format --lint --mypy

# Runtime gate for mounted workspace (when target=builder in Compose)
CMD ["/usr/local/bin/python", "run_local_ci.py", "--privacy"]

# ============================================================================
# STAGE 2: Runtime (python:3.15-slim)
# Purpose: Keep the final deploy image small and low-attack-surface while using
# the glibc-based slim builder for the faster dependency install path.
# ============================================================================
FROM python:3.15-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends && \
    groupadd --system app && useradd --system --gid app --create-home app

# Copy ONLY runtime packages (not dev tools like black, ruff, bandit, mypy)
COPY --from=builder /runtime-deps /usr/local/lib/python3.15/site-packages

# Copy the entire workspace from builder (all source code already there)
COPY --from=builder /workspace /workspace

# Switch to non-root user for runtime
USER app
# Runtime CMD (minimal - just runs the app)
CMD ["/usr/local/bin/python", "run_local_ci.py"]
