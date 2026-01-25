# --------------------------------------------------------------------
# Dockerfile for SolarEdgeController
# --------------------------------------------------------------------

    # Builder stage
FROM python:3.13-slim AS builder
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Final runtime stage
FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src
COPY run.sh ./
COPY healthcheck.py /app/healthcheck.py
RUN chmod +x /app/healthcheck.py
ENV PATH="/opt/venv/bin:${PATH}"
ENV DOCKER=True
CMD ["python", "-m", "solar_controller.main"]

HEALTHCHECK --interval=10s --timeout=3s CMD python /app/healthcheck.py
