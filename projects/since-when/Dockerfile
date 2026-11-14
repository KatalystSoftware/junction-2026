# The Since When API and pages. Build context: projects/since-when/.
FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libmariadb-dev \
 && rm -rf /var/lib/apt/lists/*
# CPU torch only: the API embeds one search question at a time.
RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir transformers==5.23.0 mariadb==1.1.15 mwparserfromhell==0.7.2

WORKDIR /app
COPY gapfinder gapfinder
COPY differences differences
COPY ui ui
ENV HF_HOME=/models PYTHONUNBUFFERED=1
