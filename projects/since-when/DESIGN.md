---
name: Since When
description: The Wikipedia skin, on one screen per topic
colors:
  text: "#202122"
  text-emphasized: "#101418"
  text-subtle: "#54595d"
  link: "#3366cc"
  surface: "#ffffff"
  surface-quote: "#f8f9fa"
  rule: "#c8ccd1"
  rule-strong: "#a2a9b1"
  mark-fill: "#ffe49c"
  mark-line: "#ab7f2a"
  lane-past: "#72777d"
typography:
  title:
    fontFamily: "'Linux Libertine', Georgia, Times, 'Source Serif 4', serif"
    fontSize: "1.75rem"
    fontWeight: 400
    lineHeight: "2.375rem"
  heading:
    fontFamily: "'Linux Libertine', Georgia, Times, 'Source Serif 4', serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: "1.875rem"
  quote:
    fontFamily: "'Linux Libertine', Georgia, Times, 'Source Serif 4', serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: "1.875rem"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Inter, Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: "1.625rem"
  small:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Inter, Helvetica, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: "1.375rem"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Inter, Helvetica, Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: "1.25rem"
rounded:
  base: "2px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  section: "48px"
components:
  button-run:
    backgroundColor: "{colors.link}"
    textColor: "{colors.surface}"
    rounded: "{rounded.base}"
  button-quiet:
    textColor: "{colors.link}"
    rounded: "{rounded.base}"
  quote:
    backgroundColor: "{colors.surface-quote}"
    textColor: "{colors.text}"
    typography: "{typography.quote}"
    padding: "8px 12px 12px"
  mark:
    backgroundColor: "{colors.mark-fill}"
    textColor: "{colors.text}"
  chip:
    backgroundColor: "#eaecf0"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: "0 6px"
---

# Design System: Since When

## Overview

Since When wears the Wikipedia skin. Every value is a Wikimedia Codex design token and every
control is a Codex CSS-only component on a native element, so a Wikipedia reader meets a page they
already know how to read: serif headings, sans text, blue links, hairline rules, no cards and no
decoration.

The page is one column, 62rem wide. What is drawn is the product's subject: three editions, and
time. An edition always sits in the same order (Finnish, Swedish, English), as a column of quotes
and as a lane of the time strip.

**The Skin Rule.** A colour, size or space that is not a Codex token does not go on the page. A new
kind of control is the Codex component documented as "CSS-only", or a native element.

**The Say-Less Rule.** A sentence that explains the page waits behind a native disclosure (a
popover, `<details>` or `title`). Structure, position and marks carry what it said.

## Colors

One accent, used for one thing each.

### Primary

- **Link blue** (`link`): links and the quiet buttons that act like links, the Run button, focus
  rings. Nothing that cannot be clicked is blue.

### Secondary

- **Mark amber** (`mark-fill` behind the words, `mark-line` under them): the words a difference is
  about, inside a quote. The time strip's bars are drawn in `mark-line`, so the bar reads as the
  life of the marked words.

### Neutral

- **Text** (`text`, `text-emphasized` for headings, `text-subtle` for labels and dates).
- **Surface** (`surface` for the page, `surface-quote` behind quoted article text and code).
- **Rules** (`rule` for hairlines and the strip's empty lanes, `rule-strong` on top of a quote).
- **Lane past** (`lane-past`): a period that has ended, on the time strip.

**The Quote Surface Rule.** The grey surface means "these are the article's words, or the
database's". Nothing the app wrote sits on it.

## Typography

**Display font:** Linux Libertine, Georgia (Codex serif)
**Body font:** the system sans (Codex system sans)

**Character:** Wikipedia's own pairing. Serif is for titles and for article text; sans is for
everything the app says.

### Hierarchy

- **Title** (regular, 1.75rem, 2.375rem): the topic, and the headline of the open difference.
- **Heading** (regular, 1.25rem): section headings, the SQL panel's title.
- **Quote** (regular serif, 1.25rem, 1.875rem): article text, word for word.
- **Body** (regular, 1rem, 1.625rem): row headlines, controls.
- **Small** (regular, 0.875rem): captions, dates, links under a quote.
- **Label** (regular, 0.75rem, tabular figures): the strip's lane names and year labels.

**The Two Voices Rule.** Article text is serif on the quote surface. The app's own words are sans.
A reader can tell who is speaking without a label.

## Layout

One column, 62rem at most, 24px side padding (16px under 640px). The top bar is 3rem tall with the
name, the topic picker and the SQL button.

A difference is a row: its headline on the left, its time strip on the right, on one scale down the
whole list. Opened, the row shows the editions' quotes in equal columns (three or two) with 16px
between them. The first difference is open on arrival and has the first screen to itself.

Under 640px the strip moves under the headline and the quote columns stack.

Space comes from the Codex scale (4, 8, 12, 16, 24, 48px): 12–16px inside a row, 48px between
sections.

## Elevation & Depth

Flat. Hairline rules separate rows. Two things float, with Codex's shadows: the dialogs (the SQL
panel and the topic list, `box-shadow-drop-xx-large` over a light backdrop) and the small popover
behind a mark (`box-shadow-medium`).

## Shapes

Square, with Codex's 2px radius on controls and popovers. The only round things are the info chip
(a pill) and the dot that starts a bar on the time strip.

## Components

### Buttons

Codex Button. Default (grey, bordered) for "SQL" and "Show all"; progressive quiet (blue text, no
border) for actions that read as links ("Topics", "Close", "Check in MariaDB"); progressive primary
(blue fill) for Run alone.

### Chips

Codex InfoChip, as a button: a compact mark for what the reader should know and need not read
every time ("Machine-suggested", "Unchecked"). Clicking it opens a native popover with the full
sentence.

### Cards / Containers

- **Quote.** Article text on the quote surface with a 3px `rule-strong` line on top, the edition's
  name above it as a link to the revision the quote was taken from.
- **Row.** A Codex Accordion (`<details>`): headline in the summary, quotes and actions inside.
- **Dialog.** A native `<dialog>` sheet on the right edge for the SQL panel and the topic list.

### Inputs / Fields

Codex Select, TextInput, SearchInput, Field and Label, in the SQL panel and the topic list.

### Time strip

The page's signature. One lane for each edition quoted, on a shared scale from 2001 to today. A
lane is a hairline; a bar on it is the period that edition has said what the difference is about,
drawn in `mark-line`, starting at a dot. A period that ended is drawn in `lane-past`. The lane's
name is at its left and the date the current period began at its right, as a link to the edit that
began it. The scale is labelled once, above the list.

### Marked words

The words a difference is about, inside a quote: `mark-fill` behind them, a 2px `mark-line` under
them, semi-bold.

## Do's and Don'ts

### Do:

- **Do** keep an edition in its place: Finnish, Swedish, English, left to right and top to bottom.
- **Do** put article text on the quote surface, in serif, word for word.
- **Do** draw a date on the time scale and keep the exact date next to it.
- **Do** put an explanation behind a chip, `<details>` or `title`.
- **Do** use tabular figures for dates, counts and timings.

### Don't:

- **Don't** add a font, a colour or a shadow that is not a Codex token.
- **Don't** print a sentence that explains the page where it is always visible.
- **Don't** use blue for anything that cannot be clicked, or amber for anything but the words a
  difference is about and their bars.
- **Don't** restate a quote in the app's words next to the quote.
- **Don't** say what an article should say.
