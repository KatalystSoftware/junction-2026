"""A person's profile, filled in from one thing they hand over themselves: their LinkedIn, a portfolio page, or their CV.

Handing it over is the consent, and the person is shown what was read before anything is kept. Nothing
here is stored, cached or logged: the material is fetched, a model turns it into short lines the person
can agree with or strike, and the answer goes back to their browser. Every line carries the words it was
read from, and those words must be in the material word for word, or the line is dropped. This is the
same rule the company side follows.

Schools and studies are left out, with photo, age, gender and nationality: the form promises they are never
read into a profile. Only the skill part of a profile can be filled in this way. What a person wants to do next and what
would suit them are not in a CV; the form asks for those.

  linkedin    Context.dev POST /v1/people/enrich with the profile address (20 credits a match). It reads
              Context.dev's own record of the profile, which can be weeks old: one more reason the person
              checks every line.
  portfolio   Context.dev POST /v1/web/scrape of the page (1 credit).
  cv          the text of the CV, as pasted.

  sops exec-env ../../secrets/secrets.yaml 'python3 person.py linkedin https://www.linkedin.com/in/<you>'
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

import signals

MOST = 20_000  # characters of material read
SURE = 90  # Context.dev's match score, out of 100, below which a profile is not taken as the person's
SYSTEM = """A job seeker has handed over material about themselves (their LinkedIn profile, a portfolio page or their CV) so that a sign-up form for a recruitment event can be filled in for them. They will read every line you write and agree with it or strike it.

Write only what the material states about their work and studies. Do not guess. Leave out anything about age, gender, nationality, origin, health, family, religion, politics or appearance, and anything about other people.

Every item has a field `from`: a run of 3 to 15 words copied exactly, character for character, from the material, that the item rests on. An item you cannot back with such words is left out.

name: the person's own name as the material gives it, or an empty string when it does not.
headline: who they are at work, at most 10 words, no adjectives of praise.
field: the one field of work that fits best.
level: by years and titles in the material.
can_do: up to 6 things they can do, each a plain line of at most 14 words that starts with a verb and names the work, not a quality ("Builds data pipelines in Python", never "Strong communicator").
skills: up to 10 tools, methods or technologies named in the material, each as the material writes it.
experience: up to 6 roles, newest first. years as "2023–2025" or "2025–now"; empty when the material gives none. Leave out studies and schools.
languages: spoken languages the material names, with the level if given."""
QUOTE = {"type": "string", "description": "3 to 15 words copied exactly from the material"}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["name", "headline", "field", "level", "can_do", "skills", "experience", "languages"],
    "properties": {
        "name": {"type": "string"},
        "headline": {"type": "string"},
        "field": {"type": "string", "enum": signals.FAMILIES},
        "level": {"type": "string", "enum": signals.SENIORITY},
        "can_do": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["line", "from"],
                                              "properties": {"line": {"type": "string"}, "from": QUOTE}}},
        "skills": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["skill", "from"],
                                              "properties": {"skill": {"type": "string"}, "from": QUOTE}}},
        "experience": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title", "organisation", "years", "from"],
                                                  "properties": {"title": {"type": "string"}, "organisation": {"type": "string"},
                                                                 "years": {"type": "string"}, "from": QUOTE}}},
        "languages": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["language", "from"],
                                                 "properties": {"language": {"type": "string"}, "from": QUOTE}}},
    },
}


class Unreadable(Exception):
    """The material could not be read; the message is one the person can be shown."""


def call(url, body, headers):
    """One request that leaves no trace here: no cache, no log of what was sent or what came back."""
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"content-type": "application/json", "user-agent": "kutsu", **headers})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise Unreadable("We could not read that just now. Try again in a minute, or paste your CV instead.") from error


def context(path, body):
    return call(f"{signals.CONTEXT}/{path}", body, {"authorization": f"Bearer {os.environ['CONTEXT_DEV_API_KEY']}"})


def years(role):
    start, end = (role.get("start_date") or {}).get("year"), (role.get("end_date") or {}).get("year")
    return f"{start}–{'now' if role.get('is_current') or not end else end}" if start else ""


def linkedin(url):
    """(name, material) from a LinkedIn profile address, through Context.dev's record of that profile."""
    if "linkedin.com/in/" not in url:
        raise Unreadable("That does not look like a LinkedIn profile address. It should contain linkedin.com/in/.")
    match = context("people/enrich", {"social_urls": [url]})["match"]
    person = match.get("person")
    if match.get("status") != "candidate" or (match.get("score") or 0) < SURE or not person:
        raise Unreadable("We could not find that LinkedIn profile. Paste your CV or a portfolio page instead.")
    lines = [person.get("bio") or ""]
    for role in person.get("experience") or []:
        lines.append(". ".join(x for x in (f"{role.get('title')}, {(role.get('organization') or {}).get('name')}, {years(role)}",
                                            role.get("description") or "") if x))
    for study in person.get("education") or []:
        lines.append(", ".join(x for x in (study.get("degree"), study.get("field_of_study"), (study.get("institution") or {}).get("name"),
                                           study.get("description")) if x))
    if person.get("skills"):
        lines.append("Skills: " + ", ".join(person["skills"]))
    return (person.get("name") or {}).get("full"), "\n".join(line for line in lines if line)


def portfolio(url):
    """(None, material) from any public page the person points at: a portfolio, a personal site, a code profile."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    answer = context("web/scrape", {"url": url, "formats": {"markdown": True}, "markdownParams": {"includeLinks": False}})
    markdown = answer.get("markdown") or {}
    if not markdown.get("success") or len(markdown.get("data") or "") < 200:
        raise Unreadable("That page could not be read. Paste your CV instead.")
    return None, markdown["data"]


def cv(text):
    if len(text.strip()) < 200:
        raise Unreadable("That is too short to be a CV. Paste the whole text.")
    return None, text


SOURCES = {"linkedin": linkedin, "portfolio": portfolio, "cv": cv}


def profile(kind, value, draft=True):
    """The skill part of a person's profile from what they handed over, each line with the words it was read from.

    Without `draft` only the text that was read comes back, for a form that fills itself in from it:
    then the material goes to Context.dev alone, and a pasted CV to nobody."""
    if kind not in SOURCES or not isinstance(value, str) or not value.strip():
        raise Unreadable("Choose your LinkedIn, a portfolio page or your CV.")
    name, material = SOURCES[kind](value.strip())
    material = material[:MOST]
    if not draft:
        return {"source": kind, "name": name, "material": material}
    answer = call(signals.ANTHROPIC, {
        "model": signals.MODEL, "max_tokens": 4000, "thinking": {"type": "disabled"},
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        "system": SYSTEM, "messages": [{"role": "user", "content": f"The material:\n\n{material}"}],
    }, {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    if answer.get("stop_reason") != "end_turn":
        raise Unreadable("We could not fill this in. Paste your CV instead, or type it in yourself.")
    lines = json.loads(next(block["text"] for block in answer["content"] if block["type"] == "text"))
    # the words each line rests on must be in the material: the same words in the same order, whatever the
    # punctuation and markup between them (a page comes as Markdown, a profile as fields joined by commas)
    words = lambda text: " ".join(re.findall(r"\w+", text.lower()))
    there = f" {words(material)} "
    dropped = 0
    for key in ("can_do", "skills", "experience", "languages"):
        kept = [item for item in lines[key] if len(words(item["from"]).split()) >= 2 and f" {words(item['from'])} " in there]
        dropped += len(lines[key]) - len(kept)
        lines[key] = kept
    # a name is kept only when it stands in the material; a profile's own record of the name comes first
    stated = lines.pop("name", "").strip()
    name = name or (stated if stated and f" {words(stated)} " in there else None)
    return {"source": kind, "name": name, "material": material, **lines, "dropped": dropped}


if __name__ == "__main__":
    print(json.dumps(profile(sys.argv[1], sys.argv[2] if sys.argv[1] != "cv" else open(sys.argv[2]).read()), indent=1, ensure_ascii=False))
