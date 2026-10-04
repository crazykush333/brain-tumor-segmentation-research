# CPU image for tests and tooling. Contains no data, no credentials, no GPU stack.
# Experiments use the nnU-Net environment pinned at EXP-001 (docs/reproducibility/ENVIRONMENT.md).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git make \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home researcher
WORKDIR /workspace
COPY --chown=researcher:researcher . /workspace
USER researcher

RUN python -m pip install --user -e ".[dev]"
ENV PATH="/home/researcher/.local/bin:${PATH}"

CMD ["make", "check-python"]
