# Recipe Google Cloud Build follows to package TexDex for Cloud Run.
# app/deploy/cloud_run.py copies this file to the top of a temporary folder,
# next to the code and the species tables, and uploads that folder.

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/srv/texdex/.hf-cache
WORKDIR /srv/texdex

# CPU-only torch: Cloud Run has no GPU, and the default download adds ~2 GB
# of GPU code we would never use.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
# gunicorn: a sturdier web server than Flask's built-in one (Linux only).
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Download BioCLIP 2 and work out the species text embeddings NOW, while
# building, so they are baked into the image. Otherwise every cold start
# would download about 1.5 GB before the first catch could be identified.
RUN USE_FAKE_ID=0 TEXDEX_IMAGE_SCORER=bioclip python -m app.deploy.warm_cache

ENV USE_FAKE_ID=0

# One process (-w 1) on purpose: unconfirmed catches are kept in that
# process's memory (see supabase_store.py). Threads let it answer several
# people at once. Cloud Run tells us the port in $PORT.
CMD exec gunicorn -w 1 --threads 8 --timeout 120 -b 0.0.0.0:${PORT:-8080} "app.server:create_app()"
