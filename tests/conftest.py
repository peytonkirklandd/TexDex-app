"""Settings shared by every test."""
import os

# The normal test run must not need the BioCLIP model (a large download) or
# real photo files, so tests use the placeholder photo scorer unless you ask
# for the real one, e.g.  TEXDEX_IMAGE_SCORER=bioclip python -m pytest
os.environ.setdefault("TEXDEX_IMAGE_SCORER", "placeholder")

# Tests always run on the small made-up demo tables, never on whatever real
# GBIF tables happen to be in data/ on this machine.
os.environ["TEXDEX_USE_DEMO"] = "1"
