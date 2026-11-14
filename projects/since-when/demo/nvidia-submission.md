# NVIDIA: how Since When uses Nemotron

The text for the submission form, then where each number comes from. Every number is from
[`hero-verify-notes.md`](hero-verify-notes.md), measured on the three hero topics (Lapua Movement,
Finnish War, Diet of Porvoo) against hand labels ([`hero-labels.json`](hero-labels.json)).

## For the form

**Model.** NVIDIA Nemotron 3.5 Super VL (`nvidia/nemotron-3.5-super-vl-120b-a12b`), served on a
Verda container.

**What it does.** Since When shows where the Finnish, Swedish and English Wikipedia articles on a
topic say different things, and the edit each difference began with. Nemotron does both language
steps. As the classifier, it reads two passages that MariaDB's vector search paired across editions
and names what differs: a figure, a date, a conflicting account, a loaded word, or a fact one
edition leaves out, each with exact quotes. As the checker, it reads each claim against the passages
of the whole other article that one MariaDB statement returns (the article as of the comparison
date, every sentence ranked by vector distance, dates and numbers matched with REGEXP), and says
whether that article states it, contradicts it or does not mention it, quoting the passage.

**Why it matters.** A suggested difference that is wrong costs a reader's trust in every other one.
Passage pairs miss what the other edition says under another heading, so the classifier alone
reports facts as missing that are there, and figures as different that measure different things.

**How its outputs were improved.** Checking each claim against the whole other article, with the
same model as judge:

- Of 23 numbers rows the classifier wrote, 11 were false. On those labelled rows the check removes
  9 of the 11 false ones and keeps all 9 real ones. Across the full run, numbers rows went from
  9 real of 23 to 24 real of 31: the check also turns missing facts into the figures they disagree
  on.
- It set aside 165 of 688 "missing" facts because the other article states them, each with the
  passage that does; in a hand-checked sample of 20, 19 were rightly set aside and none wrongly.
  Kept missing facts went from 10 real of a sample of 24 to 16 of 24.
- Contradictions went from none confirmed of 7 to 2 of 6. A contradiction has to hold looked up
  from both sides, and arithmetic overrules the judge on figures (15 of 410 verdicts).

The page names Nemotron as classifier and checker, says how many suggestions it looked up and set
aside on each topic, and shows the passage behind every verdict.

## Where the numbers come from

| | Before: the classifier alone | After: Nemotron's check |
| --- | --- | --- |
| Labelled numbers rows (11 false, 9 real) | 11 false shown, 9 real shown | 9 false gone, 1 moved, 1 kept; 9 real kept |
| Numbers rows, hand-checked | 23: 9 real, 11 false, 3 unclear | 31: 24 real, 4 false, 3 unclear |
| Contradiction rows, hand-checked | 7: 0 real, 2 false, 5 unclear | 6: 2 real, 1 false, 3 unclear |
| Missing facts kept, sample of 24 | 10 real, 5 false, 9 unclear | 16 real, 3 false, 5 unclear |
| Missing facts set aside | none | 165 of 688; sample of 20: 19 right, 0 wrong, 1 partly |

Framing rows are not checked and are listed apart as unchecked. What the check still gets wrong is
in [`hero-verify-notes.md`](hero-verify-notes.md#what-is-still-wrong); the rows of that list that
reach the hero pages are closed by hand ([`hand-checked.json`](hand-checked.json)).
