"""Run once while the Cloud Run image is being built (see Dockerfile).

Identifying one blank picture makes BioCLIP 2 download its weights and
work out the text embeddings for every species on our list. Both are saved
to disk inside the image, so the live server starts without downloading
anything. The result of this identification is thrown away.
"""
import tempfile
from datetime import date
from pathlib import Path

from PIL import Image

from app.config import load_config, share_files_with_identify
from contract import identify

if __name__ == "__main__":
    config = load_config()
    share_files_with_identify(config)  # same species list as the app will use
    print("Species list:", config["species_csv"])
    with tempfile.TemporaryDirectory() as folder:
        blank = Path(folder) / "blank.jpg"
        Image.new("RGB", (224, 224), (90, 120, 80)).save(blank)
        identify(str(blank), 30.27, -97.74, date.today())
    print("BioCLIP 2 and species embeddings are cached.")
