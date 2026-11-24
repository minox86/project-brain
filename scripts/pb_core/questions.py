"""Open questions on Teams: each one posted once as a card through a Teams workflow webhook, answered by replying
to it. The toolkit posts and remembers what it posted; the routine reads the replies through its connector. Each
run ends with one more card: the list of the questions still waiting for an answer, each linked to its own card.

The brain is written in English; the cards are posted in the team's language (`team_language` of brain.md). The
toolkit does not translate: for another language the routine passes the translated texts of each card to `publish`.

The webhook URL carries a secret: it is never read from the brain nor printed. It comes from the environment
(`webhook_env`, default PB_QUESTIONS_WEBHOOK) or from the clone's own git config (`pb.questionsWebhook`).
"""
import datetime
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from . import links, sources, state
from .brain import SCHEMA, _without_heading
from .errors import UsageError
from .repo import git

SOURCE = "questions"
WEBHOOK_ENV = "PB_QUESTIONS_WEBHOOK"
GIT_KEY = "pb.questionsWebhook"
MAX_PER_RUN = 5
AREAS = ("functional", "ux", "technical")
KEYS = {"team", "team_id", "channel", "channel_id", "tenant_id", "max_per_run", "areas", "webhook_env", "people"}
# Who can answer a question, by its area; a question with no area asks everyone.
ROLES = {"tech": "Tech", "product": "Product", "analyst": "Analyst", "ux": "UX"}
ROLES_OF = {"technical": ("tech",), "functional": ("product", "analyst"), "ux": ("ux",)}
SECTION_CHARS = 700
TIMEOUT = 20
CITATION = re.compile(r"\s*\^\[[^\]]*\]")
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
LANGUAGE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
# The fixed words of a card, in English; a translation may replace any of them.
LABELS = {"open_question": "OPEN QUESTION", "affects": "Affects", "for": "For",
          "functional": "FUNCTIONAL", "technical": "TECHNICAL", "ux": "UX", "still_open": "STILL OPEN"}
MESSAGE_LINK = "https://teams.microsoft.com/l/message/"


def language(brain):
    """The team's main language, as a code (`en`, `it`, `pt-BR`): the one the cards are posted in."""
    value = brain.config.get("team_language")
    return value.strip() if isinstance(value, str) and value.strip() else "en"


def language_problem(value):
    """Why `team_language` is unusable, or None."""
    if value is None:
        return None
    if not isinstance(value, str) or not LANGUAGE.match(value.strip()):
        return f"'{value}' is not a language code: use one like en, it, de, pt-BR"
    return None


def _english(brain):
    return language(brain).lower().split("-")[0] == "en"


def _translations(path):
    """The translated texts the routine wrote for this run: {"labels": {...}, "questions": {title: {...}}}."""
    if path is None:
        return {}, {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise UsageError(f"--translations {path}: {exc}")
    found = data.get("questions", {}) if isinstance(data, dict) else None
    labels = data.get("labels") if isinstance(data, dict) else None
    if not isinstance(found, dict) or any(not _usable(entry) for entry in found.values()):
        raise UsageError(f'--translations {path}: expected {{"labels": {{…}}, "questions": {{"<title>": {{"title": "…", '
                         '"question": "…", "sections": [{"heading": "…", "text": "…"}]}}}}')
    return found, {k: v for k, v in (labels if isinstance(labels, dict) else {}).items()
                   if k in LABELS and isinstance(v, str) and v.strip()}


def _usable(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("title"), str) or not entry["title"].strip():
        return False
    parts = entry.get("sections", [])
    return isinstance(entry.get("question", ""), str) and isinstance(parts, list) and all(
        isinstance(part, dict) and isinstance(part.get("heading"), str) and isinstance(part.get("text"), str)
        for part in parts)


def texts(page, translated=None):
    """What a card says: (title, question, [(heading, text)]) of the page, or of its translation."""
    if translated:
        return (translated["title"].strip(), (translated.get("question") or "").strip(),
                [(part["heading"].strip(), part["text"].strip()) for part in translated.get("sections", [])
                 if part["text"].strip()])
    question, parts = sections(page)
    return page.title, question, parts


def config(brain):
    """The `questions` settings of sources.md, or None when the feature is off."""
    value = (brain.sources or {}).get(SOURCE)
    return value if isinstance(value, dict) and value else None


def switched_off(brain):
    """True when `questions` is listed in `disabled` of sources.md: configured, but nothing is posted or read."""
    return SOURCE in sources.status(brain)["off"]


def problems(brain):
    """Why the `questions` settings are unusable, one message each."""
    value = (brain.sources or {}).get(SOURCE)
    if value in (None, {}, []):
        return []
    if not isinstance(value, dict):
        return ["questions must be a map: {team, team_id, channel, channel_id} of the channel the workflow posts to"]
    out = [f"questions: unknown key '{key}', use {sorted(KEYS)}" for key in sorted(set(value) - KEYS)]
    if any(isinstance(v, str) and re.match(r"\s*https?://", v) for v in value.values()):
        out.append("questions holds a URL: the webhook is a secret and never goes in the repo; set it in "
                   f"${WEBHOOK_ENV} or with `git config --local {GIT_KEY} <url>`")
    for key in ("team_id", "channel_id"):
        if not value.get(key):
            out.append(f"questions.{key} is missing: the routine reads the replies from that channel")
    limit = value.get("max_per_run", MAX_PER_RUN)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        out.append("questions.max_per_run must be a number, 1 or more")
    areas = value.get("areas")
    if areas is not None and (not isinstance(areas, list) or any(a not in AREAS for a in areas)):
        out.append(f"questions.areas must be a list of {list(AREAS)}")
    people = value.get("people")
    if people is not None and not isinstance(people, dict):
        out.append(f"questions.people must map the roles {list(ROLES)} to lists of people")
    for role, members in (people.items() if isinstance(people, dict) else []):
        if role not in ROLES:
            out.append(f"questions.people: unknown role '{role}', use {list(ROLES)}")
        if not isinstance(members, list) or any(_person(m) is None for m in members):
            out.append(f"questions.people.{role} must be a list of Teams sign-in addresses (name@company.com), "
                       "or of {name, email}")
    name = value.get("webhook_env")
    if name is not None and not (isinstance(name, str) and ENV_NAME.match(name)):
        out.append("questions.webhook_env must be the name of an environment variable")
    return out


def webhook(brain):
    """(url | None, where it was found | None). The URL is a secret: callers never print it."""
    settings = config(brain) or {}
    name = settings.get("webhook_env") if isinstance(settings.get("webhook_env"), str) else WEBHOOK_ENV
    url = (os.environ.get(name) or "").strip()
    if url:
        return url, f"${name}"
    proc = git(brain.repo_root, "config", "--get", GIT_KEY, check=False)
    url = proc.stdout.strip() if proc.returncode == 0 else ""
    return (url, f"git config {GIT_KEY}") if url else (None, None)


def _open(brain, settings):
    """Open questions of the configured areas, oldest first."""
    areas = settings.get("areas") if isinstance(settings.get("areas"), list) else None
    found = [p for p in brain.pages()
             if p.type == "open-question" and p.get("status", "open") in (None, "open") and p.get("archived") is not True
             and (areas is None or p.get("area") in areas)]
    return sorted(found, key=lambda p: (str(p.get("created") or p.get("updated") or "9999"), p.title.lower()))


def _posted(brain):
    value = state.get(brain, SOURCE, "posted")
    return dict(value) if isinstance(value, dict) else {}


def _prune(brain, posted):
    """Forget the cards of questions that are no longer open (answered, dropped, renamed)."""
    titles = {p.title for p in brain.pages()
              if p.type == "open-question" and p.get("status", "open") in (None, "open")}
    kept = {title: entry for title, entry in posted.items() if title in titles}
    return kept, sorted(set(posted) - set(kept))


def status(brain):
    """What the routine needs to read the answers: the channel and the cards still waiting for one."""
    settings = config(brain)
    if settings is None:
        return {"configured": False, "posted": [], "unpublished": 0}
    url, where = webhook(brain)
    posted, _ = _prune(brain, _posted(brain))
    pages = {p.title: p for p in _open(brain, settings)}
    return {
        "configured": True,
        "off": switched_off(brain),
        "webhook": where,
        "language": language(brain),
        "channel": {key: settings.get(key) for key in ("team", "team_id", "channel", "channel_id")},
        "posted": [{"title": title, "path": pages[title].rel if title in pages else None,
                    "shown": entry.get("shown") or title,
                    "at": entry.get("at"), "message_id": entry.get("message_id"), "seen": entry.get("seen"),
                    "url": link(settings, entry)}
                   for title, entry in sorted(posted.items(), key=lambda item: str(item[1].get("at")))],
        "unpublished": len([title for title in pages if title not in posted]),
    }


def publish(brain, now=None, check=False, translations=None):
    """Post a card for each open question not posted yet, at most `max_per_run`, oldest first, in the team's
    language: when it is not English, only the questions `translations` (a JSON file) carries are posted."""
    settings = config(brain)
    if settings is None:
        return {"configured": False, "published": [], "failed": [], "left": 0}, 0
    if switched_off(brain):
        # The switch wins over the configuration: no card leaves, and the record of the posted ones is not touched.
        return {"configured": True, "off": True, "published": [], "failed": [], "left": 0,
                "skipped": "questions is switched off (`disabled` in sources.md): `pb sources on questions`"}, 0
    found = problems(brain)
    if found:
        raise UsageError(f"{SCHEMA}/sources.md: " + "; ".join(found))
    posted, forgotten = _prune(brain, _posted(brain))
    new = [p for p in _open(brain, settings) if p.title not in posted]
    batch = new[:settings.get("max_per_run", MAX_PER_RUN)]
    url, where = webhook(brain)
    out = {"configured": True, "off": False, "webhook": where, "language": language(brain), "published": [],
           "failed": [],
           "left": len(new) - len(batch), "forgotten": forgotten}
    if check:
        out["would_publish"] = [p.title for p in batch]
        out["left"] = len(new)
        if not _english(brain):
            # What the routine translates before posting: the texts of each card and its fixed words.
            out["translate"] = {"labels": dict(LABELS), "questions": {
                p.title: {"title": p.title, "question": texts(p)[1],
                          "sections": [{"heading": name, "text": text} for name, text in texts(p)[2]]}
                for p in batch}}
        return out, 0
    translated, labels = _translations(translations)
    if not _english(brain):
        out["untranslated"] = [p.title for p in batch if p.title not in translated]
        batch = [p for p in batch if p.title in translated]
        out["left"] += len(out["untranslated"])
    if url is None:
        if forgotten:
            state.set_(brain, SOURCE, "posted", posted)
        out["left"] = len(new)
        out["skipped"] = (f"no webhook: set ${settings.get('webhook_env') or WEBHOOK_ENV} in the environment of the "
                          f"run, or `git config --local {GIT_KEY} <url>` in this clone")
        return out, 0
    now = now or datetime.datetime.now(datetime.timezone.utc)
    for page in batch:
        error = post(url, card(brain, page, settings, translated.get(page.title), labels))
        if error:
            out["failed"].append({"title": page.title, "error": error})
            continue
        posted[page.title] = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "message_id": None}
        shown = texts(page, translated.get(page.title))[0]
        if shown != page.title:
            posted[page.title]["shown"] = shown  # the title the card shows, to find it in the channel
        out["published"].append(page.title)
    out["left"] += len(out["failed"])
    if out["published"] or forgotten:
        state.set_(brain, SOURCE, "posted", posted)
    return out, 1 if out["failed"] else 0


def link(settings, entry):
    """The address that opens a posted card in Teams: the one the routine recorded for it (the message's `webUrl`),
    or the one built from the channel and the message id. None until the card's message is found."""
    if entry.get("url"):
        return entry["url"]
    message, channel = entry.get("message_id"), settings.get("channel_id")
    if not message or not channel:
        return None
    query = {"groupId": settings.get("team_id"), "tenantId": settings.get("tenant_id"),
             "parentMessageId": message, "createdTime": message}
    return (f"{MESSAGE_LINK}{urllib.parse.quote(str(channel), safe='')}/{urllib.parse.quote(str(message), safe='')}?"
            + urllib.parse.urlencode({key: value for key, value in query.items() if value}))


def summary(brain, check=False, translations=None):
    """Post one card listing the questions already posted and still open, oldest first, each title a link to its
    card. Posted after the new cards of the run, so it is the last message of the channel."""
    settings = config(brain)
    if settings is None:
        return {"configured": False, "posted": False, "listed": []}, 0
    if switched_off(brain):
        return {"configured": True, "off": True, "posted": False, "listed": [],
                "skipped": "questions is switched off (`disabled` in sources.md): `pb sources on questions`"}, 0
    found = problems(brain)
    if found:
        raise UsageError(f"{SCHEMA}/sources.md: " + "; ".join(found))
    waiting, _ = _prune(brain, _posted(brain))
    # Oldest card first; the cards of one run share their time, and go in the order they were posted: oldest question.
    age = {p.title: str(p.get("created") or p.get("updated") or "9999") for p in brain.pages()
           if p.type == "open-question"}
    items = [(title, entry.get("shown") or title, link(settings, entry)) for title, entry in sorted(
        waiting.items(), key=lambda item: (str(item[1].get("at")), age.get(item[0], "9999"), item[0].lower()))]
    url, where = webhook(brain)
    out = {"configured": True, "off": False, "webhook": where, "language": language(brain), "posted": False,
           "listed": [title for title, _, _ in items],
           "unlinked": [title for title, _, target in items if target is None]}
    if not items:
        out["skipped"] = "no posted question is waiting for an answer"
    elif url is None:
        out["skipped"] = (f"no webhook: set ${settings.get('webhook_env') or WEBHOOK_ENV} in the environment of the "
                          f"run, or `git config --local {GIT_KEY} <url>` in this clone")
    if check or "skipped" in out:
        return out, 0
    _, labels = _translations(translations)
    error = post(url, summary_card([(shown, target) for _, shown, target in items], labels))
    if error:
        out["error"] = error
        return out, 1
    out["posted"] = True
    return out, 0


def summary_card(items, labels=None):
    """The Teams message listing the open questions: `items` are (title shown, link to its card | None)."""
    words = dict(LABELS, **(labels or {}))
    lines = [f"- [{_label(shown)}]({target})" if target else f"- {shown}" for shown, target in items]
    return _message([_text(f"{words['still_open']} · {len(items)}", size="Small", weight="Bolder", color="Accent",
                           spacing="None"),
                     _text("\n".join(lines), spacing="Small")])


def _label(text):
    """A title as the label of a Markdown link."""
    return re.sub(r"([\[\]\\])", r"\\\1", text)


def mark(brain, title, message_id=None, seen=None, url=None):
    """Record the Teams message of a posted question, its address and how far its replies were read."""
    posted = _posted(brain)
    if title not in posted:
        raise UsageError(f"'{title}' was not posted: `pb questions` lists the posted questions")
    if url:
        if not re.match(r"https://\S+$", url):
            raise UsageError("--url must be the https address of the card's message in Teams")
        posted[title]["url"] = url
    if message_id:
        posted[title]["message_id"] = message_id
    if seen:
        posted[title]["seen"] = seen
    state.set_(brain, SOURCE, "posted", posted)
    return dict(posted[title], title=title)


def test(brain):
    """Post a sample card, to check the webhook and see where the workflow posts."""
    found = problems(brain)
    if found:
        raise UsageError(f"{SCHEMA}/sources.md: " + "; ".join(found))
    url, where = webhook(brain)
    if url is None:
        raise UsageError(f"no webhook: set ${(config(brain) or {}).get('webhook_env') or WEBHOOK_ENV}, or "
                         f"`git config --local {GIT_KEY} <url>` in this clone")
    product = brain.config.get("product") or "Product"
    body = [_text("TEST · PROJECT BRAIN", size="Small", weight="Bolder", color="Accent", spacing="None"),
            _text(f"The {product} brain can post here", size="Large", weight="Bolder"),
            _text("Open questions of the brain will arrive in this channel, one message each. "
                  "Answering is replying to the message."),
            _text("Reply to this message to check that replies are allowed here; this one is ignored.",
                  isSubtle=True)]
    error = post(url, _message(body))
    return {"webhook": where, "posted": error is None, "error": error}, 1 if error else 0


def post(url, payload):
    """POST the payload to the webhook. Returns None, or why it failed (never the URL)."""
    if not re.match(r"https?://", url):
        return "the webhook is not an http(s) URL"
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            code = response.getcode()
    except urllib.error.HTTPError as exc:
        return f"the webhook answered {exc.code} {exc.reason}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        host = urllib.parse.urlsplit(url).hostname or "the webhook's host"
        return f"could not reach {host}: {str(reason).replace(url, '<webhook>')}"
    return None if 200 <= code < 300 else f"the webhook answered {code}"


def _plain(text):
    """Page text as a card shows it: links as their label, no source citations."""
    def shown(m):
        if m.group("wtarget") is not None:
            target, _, label = links._wiki_parts(m)
            return label or target
        return m.group("label")
    return CITATION.sub("", links.TOKEN.sub(shown, text or "")).strip()


def _cut(text, limit=SECTION_CHARS):
    return text if len(text) <= limit else text[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def sections(page):
    """(the question, [(heading, text)]) from an open-question body: its first paragraph, then its `##` sections."""
    intro, found, current = [], [], None
    for line in _without_heading(page.body).splitlines():
        heading = re.match(r"##\s+(.*\S)\s*$", line)
        if heading:
            current = [heading.group(1), []]
            found.append(current)
        elif current is None:
            intro.append(line)
        else:
            current[1].append(line)
    question = _plain(" ".join(l.strip() for l in intro if l.strip()))
    return question, [(name, _plain("\n".join(lines))) for name, lines in found if _plain("\n".join(lines))]


def _person(entry):
    """(name shown, Teams sign-in address) of a `people` entry: an address, or {name, email}. None when unusable."""
    if isinstance(entry, dict):
        email, name = entry.get("email"), entry.get("name")
    else:
        email, name = entry, None
    if not isinstance(email, str) or "@" not in email.strip() or " " in email.strip():
        return None
    email = email.strip()
    if not isinstance(name, str) or not name.strip():
        name = " ".join(part.capitalize() for part in re.split(r"[._-]+", email.split("@")[0]) if part)
    return name.strip(), email


def answerers(page, settings):
    """(role labels, [(name, address)]) of who can answer a question: the roles of its area, and the people the
    settings list for those roles."""
    roles = ROLES_OF.get(page.get("area"), tuple(ROLES))
    people = settings.get("people") if isinstance(settings.get("people"), dict) else {}
    found = []
    for role in roles:
        for entry in people.get(role) or []:
            person = _person(entry)
            if person and person[1].lower() not in {email.lower() for _, email in found}:
                found.append(person)
    return [ROLES[role] for role in roles], found


def _text(text, **style):
    return dict({"type": "TextBlock", "text": text, "wrap": True}, **style)


def _message(body, mentions=()):
    """A Teams message holding one Adaptive Card; `mentions` are the people its text tags as `<at>name</at>`."""
    teams = {"width": "Full"}
    if mentions:
        teams["entities"] = [{"type": "mention", "text": f"<at>{name}</at>", "mentioned": {"id": email, "name": name}}
                             for name, email in mentions]
    content = {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard",
               "version": "1.4", "msteams": teams, "body": body}
    return {"type": "message", "attachments": [
        {"contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None, "content": content}]}


def card(brain, page, settings=None, translated=None, labels=None):
    """The Teams message of one open question: an Adaptive Card that reads top-down as title, question, why it
    matters, what is known, who can answer (the roles of its area, and their people tagged when the settings list
    them). `translated` and `labels` are its texts and fixed words in the team's language."""
    settings = settings or {}
    words = dict(LABELS, **(labels or {}))
    title, question, parts = texts(page, translated)
    area = str(page.get("area") or "")
    area = words.get(area, area.upper())
    body = [_text(" · ".join([words["open_question"]] + ([area] if area else [])), size="Small", weight="Bolder",
                  color="Accent", spacing="None"),
            _text(title, size="Large", weight="Bolder", spacing="Small")]
    if question and question.rstrip("?. ").lower() != title.rstrip("?. ").lower():
        body.append(_text(_cut(question)))
    for name, text in parts:
        body += [_text(name, weight="Bolder", spacing="Medium"), _text(_cut(text), spacing="Small")]
    affects = [str(a) for a in (page.get("affects") or [])] if isinstance(page.get("affects"), list) else []
    if affects:
        body.append(_text(f"{words['affects']}: " + ", ".join(affects), isSubtle=True, spacing="Medium"))
    roles, people = answerers(page, settings)
    who = f"{words['for']}: **" + "**, **".join(roles) + "**"
    if people:
        who += " · " + " ".join(f"<at>{name}</at>" for name, _ in people)
    body.append(_text(who, spacing="Medium", separator=True))
    return _message(body, people)
