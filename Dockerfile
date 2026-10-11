# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
FROM ${PYTHON_IMAGE} AS wheel-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
RUN python -m pip install --no-cache-dir setuptools==80.9.0 wheel==0.45.1
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --no-build-isolation --wheel-dir /wheels .

FROM wheel-builder AS test
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels chord-evaluation-toolkit
COPY requirements-dev.txt ./
RUN python -m pip install --no-cache-dir -r requirements-dev.txt
COPY . /build
CMD ["sh", "-c", "ruff check . && python -m pytest --junitxml=/tmp/test-results.xml"]

FROM ${PYTHON_IMAGE} AS runtime
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/Dogisday01/chord-evaluation-toolkit" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.title="Chord Evaluation Toolkit"
COPY --from=wheel-builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels chord-evaluation-toolkit \
    && rm -rf /wheels \
    && groupadd --gid 10001 chord \
    && useradd --uid 10001 --gid chord --create-home chord
WORKDIR /tmp
USER 10001:10001
ENTRYPOINT ["chord-eval"]
CMD ["--help"]
