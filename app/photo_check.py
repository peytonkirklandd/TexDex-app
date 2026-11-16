"""Photo quality checks that run BEFORE the ID model.

Each check that fails returns a small dict the app shows to the user:
    {"code": ..., "title": ..., "message": ..., "tip": ...}
written in plain language (what went wrong, and what to do about it).
check_photo() returns None when the photo is good enough to identify.

All the cutoffs are PLACEHOLDERS picked on made-up test images. Tune them
on real phone photos.
"""
from __future__ import annotations

from PIL import Image, ImageFilter, ImageStat

MIN_SIDE_PIXELS = 240      # smaller than this and there is nothing to look at
TOO_DARK = 30              # average brightness, 0 (black) to 255 (white)
TOO_BRIGHT = 235
BLUR_CUTOFF = 45.0         # sharpness score below this counts as blurry
CHECK_SIZE = 512           # shrink to this before measuring, so every phone gives similar numbers

# The Laplacian: for every pixel, "how different am I from my 4 neighbours?"
# A sharp photo has crisp edges, so many pixels differ a lot from their
# neighbours. A blurry photo is smooth, so almost none do.
_LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)


def sharpness(image: Image.Image) -> float:
    """Variance of the Laplacian: one number for how much crisp detail a
    photo has. High = sharp, near zero = blurry (or a blank wall)."""
    gray = image.convert("L")
    gray.thumbnail((CHECK_SIZE, CHECK_SIZE))
    edges = gray.filter(_LAPLACIAN)
    # Variance = how spread out the edge values are. All-smooth gives ~0.
    return ImageStat.Stat(edges).var[0]


def brightness(image: Image.Image) -> float:
    gray = image.convert("L")
    gray.thumbnail((CHECK_SIZE, CHECK_SIZE))
    return ImageStat.Stat(gray).mean[0]


def check_photo(image: Image.Image) -> dict | None:
    if min(image.size) < MIN_SIDE_PIXELS:
        return {
            "code": "too_small",
            "title": "That photo is too small",
            "message": "There aren't enough pixels in this picture to make out an animal.",
            "tip": "Take the photo again with the camera.",
        }
    light = brightness(image)
    if light < TOO_DARK:
        return {
            "code": "too_dark",
            "title": "It's too dark to see",
            "message": "This photo is almost black, so the animal doesn't show up.",
            "tip": "Move to better light or turn on your flash, then try again.",
        }
    if light > TOO_BRIGHT:
        return {
            "code": "too_bright",
            "title": "That photo is washed out",
            "message": "There is so much glare that the animal's details are gone.",
            "tip": "Turn so the sun is behind you, then try again.",
        }
    if sharpness(image) < BLUR_CUTOFF:
        return {
            "code": "blurry",
            "title": "That one came out blurry",
            "message": "The picture is too soft to tell one animal from another.",
            "tip": "Hold your phone still, tap the animal to focus, and take it again.",
        }
    return None


# Shown when the photo is fine but the model can't settle on a species.
TOO_FAR = {
    "code": "too_far",
    "title": "The animal is too far away",
    "message": "We can see something in the middle of the photo, but it's too small "
               "in the frame to be sure what it is.",
    "tip": "Move closer if it's safe, or zoom in until the animal fills about half the screen.",
}
NOT_CLEAR = {
    "code": "not_clear",
    "title": "We couldn't make out an animal",
    "message": "Nothing in this photo matches a Texas animal clearly enough. It may be "
               "hidden, too far away, or facing away from the camera.",
    "tip": "Try to get the whole animal in view, in good light, with nothing in front of it.",
}
NOT_A_PHOTO = {
    "code": "not_a_photo",
    "title": "That photo didn't come through",
    "message": "We couldn't open what the camera sent as a picture.",
    "tip": "Take the photo again.",
}
DUPLICATE = {
    "code": "duplicate",
    "title": "You've already logged this photo",
    "message": "This exact picture is already in your collection.",
    "tip": "Each catch needs a fresh photo. Go find another one!",
}
