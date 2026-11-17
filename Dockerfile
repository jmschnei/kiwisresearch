# Kiwis Research API (FastAPI). The dashboard is built from ui/Dockerfile.
FROM python:3.12-slim

# LaTeX is needed to compile the generated paper to PDF (~600 MB). Build with
# `--build-arg WITH_LATEX=0` for a slim image; papers are then delivered as .tex only.
ARG WITH_LATEX=1
RUN if [ "$WITH_LATEX" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
        texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended texlive-science latexmk \
      && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api,pgvector]"
COPY kiwis_config.yaml ./kiwis_config.yaml

# Runtime state (research jobs in output/, embedded vector memory in chroma_kiwis/) lives in /data
RUN useradd --create-home --uid 1000 kiwis && mkdir /data && chown kiwis /data
USER kiwis
WORKDIR /data
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["kiwis", "serve", "-c", "/app/kiwis_config.yaml", "--host", "0.0.0.0", "--port", "8000"]
