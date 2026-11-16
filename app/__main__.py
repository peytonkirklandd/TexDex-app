"""Start the app:  python -m app [--bioclip] [--port 5000] [--host 127.0.0.1]

--bioclip  use the real BioCLIP 2 model (sets USE_FAKE_ID=0 for this run).
           Without it the fake ID function is used: instant, but the guesses
           are random. Good for clicking through the app, useless for real IDs.
--host 0.0.0.0  lets a phone on the same Wi-Fi open the app. Note that phone
           browsers only allow the camera on https or localhost.
"""
import argparse
import os

parser = argparse.ArgumentParser(description="Run the TexDex web app.")
parser.add_argument("--bioclip", action="store_true", help="identify with the real BioCLIP 2 model")
parser.add_argument("--port", type=int, default=5000)
parser.add_argument("--host", default="127.0.0.1")
args = parser.parse_args()

if args.bioclip:
    # Must be set before the app is created: the config reads it at start-up
    # and contract.identify() reads it on every call.
    os.environ["USE_FAKE_ID"] = "0"

from .server import create_app  # noqa: E402  (imported after the env var is set)

create_app().run(host=args.host, port=args.port, threaded=True)
