"""Send per-language FCM. Default is dry-run; pass --apply to send."""

import argparse
import json
import re
import sys

import firebase_admin
from firebase_admin import credentials, db, messaging
from deep_translator import GoogleTranslator

import constants

language_map = {
    "English": "en",
    "Slovak": "sk",
    "Czech": "cs",
    "German": "de",
    "French": "fr",
    "Hungarian": "hu",
    "Polish": "pl",
    "Romanian": "ro",
    "Russian": "ru",
    "Japanese": "ja",
    "Danish": "da",
    "Dutch": "nl",
    "Swedish": "sv",
    "Italian": "it",
    "Finnish": "fi",
    "Norwegian": "no",
    "Ukrainian": "uk",
    "Spanish (Spain)": "es",
    "Portuguese (Brazil)": "pt",
    "Chinese (Traditional)": "zh-TW",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_LIST_TITLE = "New plants"
DEFAULT_LIST_BODY_ONE = "1 species was added. Tap to browse it."
DEFAULT_LIST_BODY_MANY = "{count} species were added. Tap to browse them."
DEFAULT_PLANT_TITLE = "New video available for {label}"
DEFAULT_PLANT_BODY = "Click here to see the video."
DEFAULT_BROWSE_TITLE = "New website"
DEFAULT_BROWSE_BODY = "whatsthatflower.com has been rebuilt. Tap to take a look."
URL_RE = re.compile(r"^https?://", re.I)

# Official launcher / store names from android/app/src/main/res/values*/strings.xml
APP_NAMES = {
    "en": "What's that flower?",
    "sk": "Čo to tu kvitne?",
    "cs": "Co to tu kvete?",
    "de": "Welche Blume ist das?",
    "fr": "Quelle est cette fleur?",
    "hu": "Miféle virág is ez?",
    "pl": "Co to za kwiat?",
    "ro": "Ce este acea floare?",
    "ru": "Что это за цветок?",
    "ja": "あの花は何ですか？",
    "da": "Hvad er denne blomst?",
    "nl": "Welke bloem is dit?",
    "sv": "Vad är den där blomman?",
    "it": "E questo che fiore è?",
    "fi": "Mikä on kukka?",
    "no": "Hva er den blomsten?",
    "uk": "Що це за квітка?",
    "es": "¿Qué flor es?",
    "pt": "Que flor é esta?",
    "zh-TW": "那朵花是什麼？",
}


def list_path(date):
    return "lists_custom/new/%s/list" % date


def count_ids(value):
    if value is None:
        return 0
    if isinstance(value, list):
        return sum(1 for item in value if item is not None)
    if isinstance(value, dict):
        return len(value)
    return 0


def app_name(code):
    return APP_NAMES.get(code) or APP_NAMES["en"]


def title_with_app_name(heading, code):
    name = app_name(code)
    if heading.endswith(name):
        return heading
    return "%s — %s" % (heading, name)


def list_copy(count, title=None, body=None):
    heading = title or DEFAULT_LIST_TITLE
    if body:
        return heading, body.format(count=count)
    if count == 1:
        return heading, DEFAULT_LIST_BODY_ONE
    return heading, DEFAULT_LIST_BODY_MANY.format(count=count)


def plant_copy(label, title=None, body=None):
    return (title or DEFAULT_PLANT_TITLE).format(label=label), body or DEFAULT_PLANT_BODY


def plant_data(name):
    return {
        "click_action": "FLUTTER_NOTIFICATION_CLICK",
        "action": "plant",
        "name": name,
    }


def list_data(path):
    return {
        "click_action": "FLUTTER_NOTIFICATION_CLICK",
        "action": "list",
        "path": path,
    }


def browse_data(uri):
    return {
        "click_action": "FLUTTER_NOTIFICATION_CLICK",
        "action": "browse",
        "uri": uri,
    }


def web_lang(code):
    if code == "zh-TW":
        return "zh"
    if code == "nb":
        return "no"
    return code.split("-", 1)[0]


def browse_uri(base, code):
    if "lang=" in base:
        return base
    joiner = "&" if "?" in base else "?"
    return "%s%slang=%s" % (base, joiner, web_lang(code))


def load_copy(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise ValueError("cannot read %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise ValueError("%s is not JSON: %s" % (path, exc))
    if not isinstance(data, dict) or not data:
        raise ValueError("%s is not a language copy map" % path)
    out = {}
    for code, item in data.items():
        if not isinstance(item, dict):
            raise ValueError("%s: %s must be {title, body}" % (path, code))
        title = item.get("title")
        body = item.get("body")
        if not title or not body:
            raise ValueError("%s: %s needs title and body" % (path, code))
        out[code] = (title, body)
    return out


def missing_copy(copy, languages):
    return [code for code in languages.values() if code not in copy]


# App topic is notifications-{Locale.languageCode}. nb_NO -> nb, zh_TW -> zh.
TOPIC_ALIASES = {
    "no": ("no", "nb"),
    "zh-TW": ("zh-TW", "zh"),
}


def topics_for(code):
    return TOPIC_ALIASES.get(code, (code,))


def selected_languages(codes):
    if not codes:
        return dict(language_map)
    wanted = set(codes)
    known = set(language_map.values())
    unknown = wanted - known
    if unknown:
        raise ValueError("unknown language codes: %s" % ", ".join(sorted(unknown)))
    return {name: code for name, code in language_map.items() if code in wanted}


def get_translated_label(language_code, plant_name):
    try:
        label = db.reference("translations/%s/%s/label" % (language_code, plant_name)).get()
        return label if label else plant_name
    except Exception as exc:
        print("Failed to fetch translation for %s: %s" % (language_code, exc))
        return plant_name


def load_new_list_count(date):
    snapshot = db.reference("lists_custom/new/%s" % date).get()
    if not snapshot:
        raise ValueError("no lists_custom/new/%s" % date)
    items = snapshot.get("list") if isinstance(snapshot, dict) else None
    count = count_ids(items)
    if count == 0:
        raise ValueError("empty list at lists_custom/new/%s" % date)
    return count


def load_user_token(uid):
    token = db.reference("users/%s/token" % uid).get()
    if not isinstance(token, str) or not token:
        raise ValueError("no FCM token at users/%s/token" % uid)
    return token


def mask_token(token):
    if not token or len(token) < 12:
        return "(token)"
    return "%s…%s" % (token[:8], token[-4:])


def translate_copy(title, body, code):
    if code == "en":
        return title, body
    translator = GoogleTranslator(source="en", target=code)
    return translator.translate(title), translator.translate(body)


def init_firebase():
    if firebase_admin._apps:
        return
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Send per-language FCM. Default is dry-run; pass --apply to send."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list",
        dest="list_date",
        metavar="DATE",
        help="List-drop for lists_custom/new/DATE (YYYY-MM-DD)",
    )
    group.add_argument(
        "--plant",
        metavar="NAME",
        help="Open one species page (Latin name)",
    )
    group.add_argument(
        "--browse",
        metavar="URL",
        help="Open this URL (https://whatsthatflower.com/)",
    )
    parser.add_argument("--title", help="English title. Plant: {label}.")
    parser.add_argument("--body", help="English body. List: {count} is replaced.")
    parser.add_argument(
        "--copy",
        metavar="FILE",
        help="JSON map of lang code -> {title, body}. Skips Google Translate.",
    )
    parser.add_argument(
        "--lang",
        action="append",
        dest="langs",
        metavar="CODE",
        help="Limit to this language code (repeatable). Default: all mapped languages.",
    )
    parser.add_argument(
        "--uid",
        metavar="UID",
        help="Send only to users/UID/token (not the language topic)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually send FCM (explicit; default is dry-run)",
    )
    args = parser.parse_args(argv)
    if args.list_date and not DATE_RE.match(args.list_date):
        parser.error("--list must be YYYY-MM-DD")
    if args.browse and not URL_RE.match(args.browse):
        parser.error("--browse must be an http(s) URL")
    return args


def english_from_copy(copy, title, body):
    if copy and "en" in copy:
        copied_title, copied_body = copy["en"]
        return title or copied_title, body or copied_body
    return title, body


def copy_for_language(job, code):
    copies = job.get("copy")
    if copies and code in copies:
        title, body = copies[code]
    elif job["kind"] == "plant":
        label = get_translated_label(code, job["plant"])
        title, body = translate_copy(job["title_template"].format(label=label), job["body"], code)
    else:
        title, body = translate_copy(job["title"], job["body"], code)
    if job["kind"] in ("list-drop", "browse"):
        title = title_with_app_name(title, code)
    return title, body


def payload_for_language(job, code):
    if job["kind"] == "browse":
        return browse_data(browse_uri(job["uri"], code))
    return job["data"]


def prepare_job(args):
    languages = selected_languages(args.langs)
    copy = load_copy(args.copy) if args.copy else None
    if args.list_date:
        count = load_new_list_count(args.list_date)
        path = list_path(args.list_date)
        title, body = list_copy(count, args.title, args.body)
        job = {
            "kind": "list-drop",
            "label": "%s count=%s path=%s" % (args.list_date, count, path),
            "title": title,
            "body": body,
            "data": list_data(path),
            "languages": languages,
        }
    elif args.plant:
        title_template, body = plant_copy("{label}", args.title, args.body)
        job = {
            "kind": "plant",
            "label": args.plant,
            "title_template": title_template,
            "body": body,
            "data": plant_data(args.plant),
            "languages": languages,
            "plant": args.plant,
        }
    else:
        title, body = english_from_copy(copy, args.title, args.body)
        title = title or DEFAULT_BROWSE_TITLE
        body = body or DEFAULT_BROWSE_BODY
        job = {
            "kind": "browse",
            "label": args.browse,
            "uri": args.browse,
            "title": title,
            "body": body,
            "data": browse_data(args.browse),
            "languages": languages,
        }
    if copy:
        job["copy"] = copy
    if args.uid:
        job["token"] = load_user_token(args.uid)
        job["uid"] = args.uid
    return job


def send_language(job, language, code, apply):
    try:
        title, body = copy_for_language(job, code)
        data = payload_for_language(job, code)
    except Exception as exc:
        print("Translation failed for %s: %s" % (language, exc))
        return False

    token = job.get("token")
    topics = topics_for(code)
    target = "token %s" % mask_token(token) if token else ", ".join("notifications-%s" % topic for topic in topics)
    print("%s  %s" % (code, target))
    print("  title: %s" % title)
    print("  body: %s" % body)
    if job["kind"] == "browse":
        print("  uri: %s" % data["uri"])
    if not apply:
        return True

    payload = dict(data)
    payload["title"] = title
    payload["body"] = body
    ok = True
    targets = [{"token": token}] if token else [{"topic": "notifications-%s" % topic} for topic in topics]
    for kwargs in targets:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=payload,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    title=title,
                    body=body,
                    sound="default",
                    click_action="FLUTTER_NOTIFICATION_CLICK",
                ),
            ),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10", "apns-push-type": "alert"},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(title=title, body=body),
                        sound="default",
                    )
                ),
            ),
            **kwargs,
        )
        try:
            response = messaging.send(message)
            print("  sent %s-%s: %s" % (job["kind"], language, response))
        except Exception as exc:
            print("  failed %s: %s" % (language, exc))
            ok = False
    return ok


def needs_firebase(args):
    return bool(args.apply or args.uid or args.list_date or args.plant)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        languages = selected_languages(args.langs)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if needs_firebase(args):
        init_firebase()
    try:
        job = prepare_job(args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.copy:
        missing = missing_copy(job.get("copy") or {}, languages)
        if missing:
            print("copy missing languages: %s" % ",".join(missing), file=sys.stderr)
            return 2

    print("%s  %s" % (job["kind"], job["label"]))
    print("data: %s" % job["data"])
    if job.get("uid"):
        print("target: users/%s/token %s" % (job["uid"], mask_token(job["token"])))
    else:
        print("target: language topics")
    if not args.apply:
        print("dry-run (FCM not sent). Pass --apply to send.")
    print("languages: %s" % ",".join(languages.values()))

    ok = True
    for language, code in languages.items():
        if not send_language(job, language, code, args.apply):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
