"""Small deterministic language and command router."""

import re

from .models import Language

GEORGIAN = re.compile(r"[\u10A0-\u10FF]")
CYRILLIC = re.compile(r"[\u0400-\u04FF]")


def detect_language(text: str, fallback: Language = "ka") -> Language:
    normalized = text.casefold()
    if GEORGIAN.search(text):
        return "ka"
    if CYRILLIC.search(text):
        return "ru"
    if any(word in normalized for word in ("english", "please", "ready", "policy")):
        return "en"
    if any(word in normalized for word in ("gamarjoba", "madloba", "davaleba", "qartulad")):
        return "ka"
    return fallback


def is_ready(text: str) -> bool:
    value = text.casefold().strip()
    return value in {
        "ready",
        "start",
        "let's start",
        "lets start",
        "კი",
        "დიახ",
        "დავიწყოთ",
        "готов",
        "начать",
    }


def is_done(text: str) -> bool:
    return text.casefold().strip() in {
        "done",
        "completed",
        "დავასრულე",
        "მოვრჩი",
        "готово",
        "завершено",
    }


def is_help(text: str) -> bool:
    value = text.casefold()
    return any(word in value for word in ("help", "stuck", "დახმარ", "ვერ", "помощ", "застрял"))


def is_policy_query(text: str) -> bool:
    value = text.casefold()
    return any(
        word in value
        for word in (
            "policy",
            "procedure",
            "leave",
            "benefit",
            "პოლიტიკ",
            "შვებულ",
            "процедур",
            "политик",
            "отпуск",
        )
    )
