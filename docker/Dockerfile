# ============================================================================
# STAGE 1: Minimum (python:3.15-alpine)
# Purpose: Minimal environment - base for other stages, contains only
# essential OS and pip packages
# ============================================================================
FROM python:3.15-alpine AS minimum

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /workspace

# Install minimal OS dependencies: git (for privacy_guard), ca-certificates (for HTTPS)
RUN apk add --no-cache \
    git \
    ca-certificates \
    openblas \
    libstdc++ \
    libgfortran && \
    python -m pip install --upgrade pip

# ============================================================================
# STAGE 2: Builder (minimum)
# Purpose: Full CI environment - compile deps, run all tests/checks
# ============================================================================
FROM minimum AS builder
# Install build dependencies
# For scikit-learn with Meson build: use build-base (includes gcc, g++, make, libc-dev)
# plus python3-dev, gfortran, openblas-dev for scientific packages
RUN apk add --no-cache \
    build-base \
    linux-headers \
    python3-dev \
    gfortran \
    openblas-dev \
    && \
    python -m pip install --upgrade setuptools wheel

# Diagnostic: Verify C++ compiler (key for scikit-learn Meson builds)
RUN echo "=== Compiler Verification ===" && \
    echo "gcc:" && which gcc && gcc --version && \
    echo "g++:" && which g++ && g++ --version && \
    echo "c++:" && which c++ && c++ --version && \
    echo "=== Done ==="

# Copy requirement files
COPY pyrolysis_lignocellulosic_ai_training/requirements.txt requirements-dev.txt ./

# Install runtime dependencies to /runtime-deps
RUN SITE_PACKAGES="$(python -c 'import site; print(site.getsitepackages()[0])')" && \
    mkdir -p /runtime-deps /dev-deps "$SITE_PACKAGES" && \
    python -m pip install --root-user-action ignore --target /runtime-deps -r requirements.txt && \
    python -m pip install --root-user-action ignore --target /dev-deps -r requirements-dev.txt && \
    printf '/runtime-deps\n/dev-deps\n' > "$SITE_PACKAGES/local-deps.pth"

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
RUN python run_local_ci.py --tests --security --deps-audit --format --lint --mypy

# Runtime gate for mounted workspace (when target=builder in Compose)
CMD ["python", "run_local_ci.py", "--privacy"]

# ============================================================================
# STAGE 3: Runtime (minimum)
# Purpose: Minimal image with only requirements.txt (no dev tools)
# Alpine base gives ~50% smaller image and fewer OS-level vulnerabilities
# ============================================================================
FROM minimum AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
RUN addgroup -S app && adduser -S -G app app

# Copy ONLY runtime packages (not dev tools like black, ruff, bandit, mypy)
COPY --from=builder /runtime-deps /usr/local/lib/python3.15/site-packages

# Copy the entire workspace from builder (all source code already there)
COPY --from=builder /workspace /workspace

# Switch to non-root user for runtime
USER app
# Runtime CMD (minimal - just runs the app)
CMD ["python", "run_local_ci.py"]
