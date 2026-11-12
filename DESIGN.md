---
name: TexDex
description: A Texas wildlife field journal you fill by photographing animals.
colors:
  paper: "#efe6d0"
  card: "#f8f2e2"
  ink: "#2b2620"
  ink-soft: "#6c6253"
  pine: "#2f4a3a"
  rust: "#a3432a"
  moss: "#55683a"
  slate: "#3f6480"
  ochre: "#b0822a"
  leather: "#33271e"
  cream: "#eadfc4"
  desk: "#221a14"
  darkroom: "#14110d"
  tier-common: "#6b665c"
typography:
  display:
    fontFamily: "Caveat, Segoe Print, Bradley Hand, cursive"
    fontSize: "44px"
    fontWeight: 700
    lineHeight: 0.9
  headline:
    fontFamily: "Caveat, Segoe Print, Bradley Hand, cursive"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1
  title:
    fontFamily: "Caveat, Segoe Print, Bradley Hand, cursive"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1
  body:
    fontFamily: "Lora, Georgia, serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Special Elite, Courier New, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    letterSpacing: "0.1em"
  wordmark:
    fontFamily: "Special Elite, Courier New, monospace"
    fontSize: "44px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.04em"
rounded:
  none: "0px"
  stamp: "2px"
  sm: "3px"
  full: "50%"
spacing:
  xs: "4px"
  sm: "10px"
  md: "14px"
  lg: "20px"
  margin: "26px"
components:
  button:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "11px 16px 9px"
  button-primary:
    backgroundColor: "{colors.pine}"
    textColor: "{colors.card}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "11px 16px 9px"
  button-danger:
    backgroundColor: "{colors.card}"
    textColor: "{colors.rust}"
    rounded: "{rounded.sm}"
    padding: "11px 16px 9px"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "2px 2px 0"
  index-tab:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 10px 6px"
  index-tab-on:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.card}"
  tier-stamp:
    backgroundColor: "transparent"
    rounded: "{rounded.stamp}"
    padding: "3px 5px 1px"
  tabbar:
    backgroundColor: "{colors.leather}"
    textColor: "{colors.cream}"
    height: "62px"
  sheet:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    padding: "22px 20px"
---

# Design System: TexDex

## Overview

**Creative North Star: "The Scrapbook Expedition"**

TexDex looks like the notebook a family brings home from a trip outdoors: grainy paper, faint ruled lines, a red margin line, photos taped in, animal names written by hand, and rarity marked with a coloured ink stamp. Every screen is a page in that journal. The tab bar is the leather spine, the Dex region tabs are index dividers sticking out of the edge, a bottom sheet is a loose page laid on top, and a new catch is a fresh entry that gets stamped.

The mood is warm, curious, and a bit handmade. Three voices do all the work: **handwriting** for names and the user's own words, a **typewriter** for labels, numbers, and system facts, and a **book serif** for reading text. Colour comes from inks and natural pigments (pine, rust, moss, slate, ochre) on paper. The code states its anti-references directly: no glows and no gradients on the paper surfaces.

Layout is one phone-width page (max 480px) with dense content and generous margins. Imperfection is deliberate but controlled: decorations tilt, controls don't.

**Key Characteristics:**
- Paper surfaces with procedural grain, ruled lines, and a red margin line
- Three-font system: Caveat handwriting, Special Elite typewriter, Lora serif
- Ink-and-pigment palette; rarity shown as coloured ink stamps
- Physical scrapbook metaphors: tape, photo corners, stamps, index tabs, loose pages
- Slight hand-placed tilt on decorative pieces only
- Layered loose pages for depth

## Colors

An ink-on-paper palette: warm parchment neutrals, near-black brown ink, and a handful of natural pigment accents, each with one job.

### Primary
- **Field Pine** (`pine`): The primary action colour (filled primary buttons) and the tone for good news such as XP gained and tip notes. It's also the colour of the journal cover behind sign-in.
- **Margin Rust** (`rust`): The red-pen colour. Used for the page margin line, the focused input underline, warnings, errors, the user's own map pins, earned badges, and the "new entry" stamp. It's also the very-rare tier ink.

### Secondary
- **Lichen Moss** (`moss`): The uncommon tier ink and the tip-note rule.
- **Creek Slate** (`slate`): The rare tier ink, the ruled-line tint, and protected-species "shield" notes.
- **Prairie Ochre** (`ochre`): A sparing highlight. Marks the active tab-bar underline, a pressed shutter, and selected list rows (at 16% tint).

### Neutral
- **Parchment** (`paper`): The page background for every journal screen.
- **Bond Card** (`card`): Raised paper: buttons, tabs, sheets, map sheet, slips. Also the text colour on dark ink fills.
- **Walnut Ink** (`ink`): All main text, borders, and outlines. Also the selected fill for tabs and segmented controls.
- **Faded Ink** (`ink-soft`): Secondary text, captions, typewriter metadata.
- **Pencil** (`ink` at 22% alpha): Hairline dividers, blank-card frames, unearned badge rings.
- **Saddle Leather** (`leather`): The tab bar (the journal's spine) and the browser theme colour.
- **Cream Thread** (`cream`): Text and stitching on leather and on the camera view.
- **Desk** (`desk`) and **Darkroom** (`darkroom`): What's behind the journal. The page sits on the desk; the camera view is the darkroom.
- **Worn Graphite** (`tier-common`): The common tier ink.

### Named Rules
**The Tier Ink Rule.** Rarity always uses the same four inks, in order: Worn Graphite (common) → Lichen Moss (uncommon) → Creek Slate (rare) → Margin Rust (very rare). Tier colour comes from `data-tier` setting `--t`. Never pick a tier colour by hand.

**The Red Pen Rule.** Rust means "look here": attention, errors, the user's own marks, and the very-rare tier. Don't use it for decoration.

## Typography

**Display Font:** Caveat (with Segoe Print, Bradley Hand, cursive)
**Body Font:** Lora (with Georgia, serif)
**Label Font:** Special Elite (with Courier New, monospace)

**Character:** Handwriting is the person, the typewriter is the record, and the serif is the book. Caveat carries names and feelings, Special Elite carries facts and numbers, and Lora carries reading text, often in italic for captions.

### Hierarchy
- **Display** (Caveat 700, 44px, line-height 0.9): Page titles like "Dex" and "Map", and the species name on a new entry (42px).
- **Headline** (Caveat 700, 30–38px, line-height ~1): Sheet titles, the top guess, the profile owner name.
- **Title** (Caveat 700, 18–24px, line-height 1): Specimen card names, list entries, guesses, and handwritten notes and errors.
- **Body** (Lora 400, 13–14.5px, line-height 1.35–1.5): Reading text. Captions and sub-lines use Lora italic in Faded Ink.
- **Label** (Special Elite 400, 12–15px, letter-spacing 0.02–0.22em): Buttons, tabs, entry numbers, dates, map labels, tier stamps. Section headings and the tab bar are uppercase.

**The 12px Floor Rule.** Functional text (labels, numbers, stamps, tab names, map keys) is never smaller than 12px. The cover's "vol. 1" plate (11px) is the only decorative exception.
- **Wordmark** (Special Elite 400, 44px, letter-spacing 0.04em): "TexDex" on the cover plate.

### Named Rules
**The Three Voices Rule.** Every piece of text picks one voice by what it is. Names and the user's notes are handwriting, facts, numbers and controls are typewriter, sentences are serif. Don't put a sentence in Caveat or a number in Lora.

**The No Thin Hand Rule.** Caveat is used at 18px or larger. Below that, switch to Special Elite.

## Layout

A single phone column, centred, max 480px wide, the full dynamic viewport height. A fixed 62px tab bar (plus the safe-area inset) sits at the bottom, and screens fill the space above it.

Scrolling pages use asymmetric padding (20px top, 16px right, 30px bottom, 26px left). The extra left space clears the red margin line drawn 15px from the edge. Horizontal strips (region tabs, recent entries) break out to the screen edges with negative margins, then re-pad, so they scroll past the margin.

Spacing is tight and handmade rather than strictly scaled. Common steps are 4, 10, 14, 20 and 26px. Section headings sit 24px above their content. The Dex is a 3-column grid with 14px rows and 10px columns. Badges use a 4-column grid, and avatars a 6-column grid. Ruled lines repeat every 30px and scroll with the page.

## Elevation & Depth

Depth is **layered loose pages**: paper on paper on a desk. Lighter Bond Card lifts off the Parchment page, ink borders define each sheet, and overlays dim the desk behind them. Shadows stay small and warm (ink-tinted, never black). Tape and photo corners show what is stuck down.

### Shadow Vocabulary
- **Taped print** (`box-shadow: 1px 2px 3px rgba(43, 38, 32, .18)`): Photos in specimen cards and entries.
- **Page dim** (`background: rgba(34, 26, 20, .55)`): The backdrop behind a bottom sheet.
- **Camera text lift** (`text-shadow: 0 1px 6px rgba(0, 0, 0, .8)`): Handwritten hints over the live camera only.

### Named Rules
**The Paper Stack Rule.** New layers are new sheets of paper: Bond Card fill, a 1–2px ink edge, and at most a small warm shadow like the taped print. Don't use floating glass, blur, glows, or large soft drop shadows.

## Shapes

Edges are almost square, like cut paper and ink boxes. Buttons, tabs and segmented controls use a 3px radius. Stamps and slips use 2px. Sheets, cards, the map sheet and inputs have none. Index tabs are rounded only on top (3px 3px 0 0) with a heavier 2px bottom edge. Circles are kept for the shutter, round camera buttons, pins, the profile seal, badges and avatars.

Borders do the work: 1–1.5px solid ink for objects, dashed pencil for empty or not-yet states (blank specimen frames, unearned badges, unchosen avatars), and doubled rules (outline plus offset) for official marks (the cover plate, the seal, earned badges, the 3px-double "new entry" stamp).

**The Decor Tilts Rule.** Decorative paper tilts by small amounts (−9° to +7°, usually under 2°): taped photos, stamps, slips, the map sheet, specimen cards, badges and recent entries. Controls never tilt: buttons, inputs, index tabs, the tab bar, list rows, and running text.

## Components

### Buttons
Typewriter keys on card stock: square-ish and outlined, with a 1px press.
- **Shape:** gently squared corners (3px), a 1.5px ink border.
- **Default:** Bond Card fill, ink text, Special Elite 15px, padding 11px 16px 9px.
- **Primary:** Field Pine fill and border, Bond Card text.
- **Big:** full width, 16px text, padding 14px 16px 12px.
- **Plain:** no border or fill, underlined (3px offset).
- **Danger:** Rust text and border on card.
- **Press:** `translateY(1px)`. There are no hover-only effects, because this is a touch-first app.

### Segmented control
A two-part ink box (1.5px border, 3px radius). The selected half is filled with ink and has Bond Card text. Used on the cover to switch between sign up and log in.

### Inputs / Fields
**A line to write on, not a box.** The text is Caveat 24px over a 1.5px ink underline, with no fill and no radius. The label sits above in Special Elite 12px Faded Ink. **Focus:** the underline turns Margin Rust. **Error:** a handwritten message in Caveat 20px Rust below the form.

### Navigation
- **Tab bar (the spine):** Saddle Leather with grain and a dashed Cream stitch line 5px from the top. There are four equal columns, each a 24px line icon (1.5 stroke) over an uppercase Special Elite 12px label. Inactive tabs are Cream at 75% (about 6.5:1 on leather). The active tab is solid Cream with an Ochre underline under its label.
- **Index tabs (Dex regions, groups):** Card-stock dividers in a horizontal scrolling strip, each with a 10px colour swatch. The selected tab is inverted to an ink fill.

### Tier Stamp (signature)
The rarity mark: uppercase Special Elite 12px, letter-spacing 0.06em, in the tier ink with a matching 1.5px border, a 2px radius, and a −1.5° tilt.

### Specimen Card (signature)
A Dex entry in the 3-column grid. The top line shows the number and tier in Special Elite 12px (wrapping to two lines when needed), with the name below in Caveat 18.5px.
- **Not found:** a dashed pencil frame with a faint sepia sketch (30% opacity) and a handwritten "?".
- **Found:** the user's photo in a white print border (4px), with the taped-print shadow and a tape strip across the top.
- Every third card tilts −0.7° or +0.6°.

### Bottom Sheet (loose page)
Bond Card with grain, a 2px ink top edge, max 88% height, rising in over 0.28s. It opens with a Caveat 34px title and a Lora italic sub-line. Guesses are rows separated by pencil rules, and the top guess is boxed in ink on Parchment.

### Notes
Handwritten callouts in Caveat 21px with a 3px left rule. Variants: **warn** (Rust), **shield** (Slate, for protected species), **tip** (Moss rule, Pine text).

### New Entry Reveal
A full-page entry after a catch: a typewriter date, the photo tilted −2°, and a "new" stamp in a Rust 3px double border that thumps in (scaling from 2.4×, overshoot easing, 0.35s after a 0.45s delay). A repeat catch gets the same stamp in Faded Ink.

### Map Sheet
The Texas map on Bond Card, tilted −0.4°, held by two tape strips. Ecoregions have ink strokes. Pins are card circles; the user's own pins are Rust. Protected species get a dashed Rust halo for their rough 25 km area. The key underneath is set in typewriter text.

## Do's and Don'ts

### Do:
- **Do** use the tokens on `:root` in `app/static/app.css` (`--paper`, `--ink`, `--rust`, …). Never hard-code a new hex for something an existing ink already covers.
- **Do** pick fonts by the Three Voices Rule: Caveat for names and notes, Special Elite for labels and numbers, Lora for sentences.
- **Do** mark rarity only with the tier stamp and the four tier inks, set through `data-tier`.
- **Do** build new surfaces as paper: Parchment or Bond Card, the grain image, and ink borders.
- **Do** use dashed pencil borders for empty or not-yet states, and solid or doubled ink once something is earned.
- **Do** keep tilts small and only on decorative paper. Keep controls straight.
- **Do** honour `prefers-reduced-motion`; the global rule already cuts animations to near zero.
- **Do** give every control a visible keyboard focus ring: 2px Margin Rust, offset 2px (Prairie Ochre on leather and over the camera).

### Don't:
- **Don't** add glows or gradients to paper surfaces. The only gradients are the grain, the ruled lines and margin, and the shades over the camera view.
- **Don't** use large, soft, or black drop shadows, or blur and glass effects. Depth is stacked paper.
- **Don't** tilt buttons, inputs, tabs, list rows, or running text.
- **Don't** set Caveat below 18px.
- **Don't** use Rust for decoration. It means attention, the user's own marks, or very rare.
- **Don't** show a protected species' pin without its blurred rough-area halo.
