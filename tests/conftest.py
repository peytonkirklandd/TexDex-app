"""Settings shared by every test."""
import os

# The normal test run must not need the BioCLIP model (a large download) or
# real photo files, so tests use the placeholder photo scorer unless you ask
# for the real one, e.g.  TEXDEX_IMAGE_SCORER=bioclip python -m pytest
os.environ.setdefault("TEXDEX_IMAGE_SCORER", "placeholder")
