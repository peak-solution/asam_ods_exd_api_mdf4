# GitHub: ghcr.io/<repository_owner>/asam-ods-exd-api-mdf4:latest
# docker build -t ghcr.io/peak-solution/asam-ods-exd-api-mdf4:latest .
# docker run --rm -it -v "$(pwd)/data":"$(pwd)/data" -p 50051:50051 ghcr.io/peak-solution/asam-ods-exd-api-mdf4:latest

FROM python:3.14-slim
LABEL org.opencontainers.image.source=https://github.com/totonga/asam-ods-exd-api-mdf4
LABEL org.opencontainers.image.description="ASAM ODS External Data API for MDF4 files (*.mf4)"
LABEL org.opencontainers.image.licenses=MIT
WORKDIR /app

# Create a non-root user and change ownership of /app
RUN useradd -ms /bin/bash appuser && chown -R appuser /app

# Copy package metadata and source tree for a proper src-layout build
COPY pyproject.toml ./
COPY src ./src

# Install required packages
RUN pip3 install --upgrade pip && pip3 install .

USER appuser

# Start server using the installed package entry point
CMD ["asam-ods-exd-api-mdf4"]