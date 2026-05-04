import random
from pathlib import Path
from typing import List
import genanki
from generator import Flashcard


# Stable model ID so Anki recognises updates instead of duplicating
MODEL_ID = 1607392319
MODEL = genanki.Model(
    MODEL_ID,
    "Simple Q&A Model",
    fields=[{"name": "Question"}, {"name": "Answer"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Question}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}',
        }
    ],
    css=".card{font-family:Arial;font-size:18px;text-align:left;color:#222;background:#fff;}",
)


def build_deck(course_name: str, cards: List[Flashcard], output_path: Path) -> Path:
    deck_id = random.randrange(1 << 30, 1 << 31)
    deck = genanki.Deck(deck_id, course_name)
    for c in cards:
        deck.add_note(genanki.Note(model=MODEL, fields=[c.question, c.answer]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(str(output_path))
    return output_path