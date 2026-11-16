# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Casual Texans outdoors: hikers, families, and students who spot a wild animal on a walk, take a photo with their phone, and enjoy filling up a collection. They are standing outside, often one-handed, in bright sun or shade, with patchy signal and little patience for setup. They are curious, not experts: they want to know what they saw and whether it was special.

The class demo, the Dec 1, 2026 submission, and the Dec 10/12 interview are how the project is evaluated, but they are not the design target. Design for the person on the trail.

## Product Purpose

TexDex identifies Texas wildlife from a live photo and saves each new species to the user's personal Dex and a shared map. Success means a user can go from seeing an animal to a confirmed, saved entry in a few taps, learns something true about the animal (what it is, how rare it is here), and wants to go out and find the next one.

## Positioning

The data engine makes TexDex different. Rarity tiers and a "what lives here this month" location boost come from real GBIF sightings in Texas, and a published accuracy report states how well the identification works. A generic species-ID app can't honestly claim Texas-specific rarity, seasonal likelihood by ecoregion, or a self-reported accuracy record.

## Operating Context

- Phone browser, served over https (needed for the camera). The planned deployment is a free Hugging Face Space. It is not deployed yet.
- Four tabs: **Catch** (live rear camera only; no camera-roll uploads), **Dex** (12 EPA Level III ecoregions plus Gulf waters, filtered by animal group), **Map** (Texas by ecoregion, with one pin per located catch), **Profile** (level, XP, stamps, progress per group, latest entries).
- Catch flow: take a photo, run a quality check (blurry, too dark, or too far away, explained in plain words), see the top 3 guesses from BioCLIP 2, then confirm one and save it.
- Two-person team: Person A owns `data_engine/` (data and AI) and Person B owns `app/` (app and backend). `contract/` and `docs/interface.md` change only when both agree.

## Capabilities and Constraints

- Texas only. Animal groups: birds, mammals, reptiles, amphibians, fish, sharks and rays. Fish and water sightings are in scope.
- Identification is BioCLIP 2 combined with the regional and monthly boost. The app only calls `identify()` and never changes the model logic.
- Protected-species locations must never be shown unblurred anywhere: map, API, logs, or exports. They are pinned to a rough 25 km area only.
- Stack: Flask (`app/server.py`) with a plain HTML/CSS/JS front end in `app/static/`. Storage is SQLite for now; the Supabase schema is written but not applied.
- Venomous species get a warning.
- Out of scope (do not design for these): weekly forecasts, zoo or aquarium detection, iNaturalist export, leaderboards or social features, native mobile apps, training our own model.
- Code must stay simple enough for both teammates to explain without AI in the interview.

## Brand Commitments

- Name: **TexDex**. Entries are numbered from No. 001.
- The app is presented as a naturalist's field journal. This framing is already part of the product identity in the README and the current UI.
- Voice: a warm field-guide naturalist. Plain and friendly, like a park ranger's notebook. Game terms (catch, XP, levels, stamps) exist, but the writing stays light on game slang. Error and quality-check messages explain the problem in plain words.

## Evidence on Hand

- Species, region, rarity, and protected flags in `app/demo_data/` are **demo data**: real Texas species with illustrative values. They will be replaced by Person A's GBIF tables. Never present demo values as real statistics.
- Ecoregion shapes (EPA) and the Texas outline (U.S. Census Bureau) are real and downloaded to `data/`, not committed.
- The accuracy report is not published yet. Do not invent accuracy numbers, user counts, testimonials, or press.

## Product Principles

1. **Trail first.** Every screen should work for one hand, in sunlight, in a few seconds. Speed from sighting to saved entry comes before extras.
2. **Show the data, honestly.** Rarity, seasonal likelihood, and accuracy are the product's edge. Surface them clearly, and never overstate what the model or the data knows.
3. **Protect the animals.** Protected-species privacy is never traded for a nicer map or a richer feature.
4. **Curiosity over competition.** The rewards are personal discovery and collection, not ranking against other people.
5. **Simple enough to explain.** Prefer the plain solution both teammates can defend in the interview.

## Accessibility & Inclusion

No course-mandated standard. Aim for the basics: WCAG AA-level contrast (including for outdoor readability), large touch targets, one-handed use, and plain-language messages.
