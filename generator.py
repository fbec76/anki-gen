import json
from typing import List
from pydantic import BaseModel, Field
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL, MAX_CHUNK_CHARS


class Flashcard(BaseModel):
    question: str = Field(..., description="Concise question on the front")
    answer: str = Field(..., description="Clear, complete answer on the back")


class FlashcardSet(BaseModel):
    cards: List[Flashcard]


SYSTEM_PROMPT = """You are an expert tutor creating Anki flashcards from lecture material.
Rules:
- Each card tests ONE atomic concept (minimum information principle).
- Questions must be self-contained (no "according to the slide...").
- Prefer "why/how" over pure recall when the material allows.
- Answers are concise but complete; include formulas in LaTeX where helpful.
- Output strictly valid JSON matching the requested schema."""


def _chunk(text: str, size: int) -> List[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def generate_cards(
    text: str,
    num_cards: int,
    prompt_appendix: str = "",
    previous_exams_text: str = "",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> List[Flashcard]:
    client = OpenAI(
        api_key=api_key or OPENAI_API_KEY,
        base_url=base_url or OPENAI_BASE_URL or None,
    )
    model_name = model or MODEL
    chunks = _chunk(text, MAX_CHUNK_CHARS)
    per_chunk = max(1, num_cards // len(chunks))
    all_cards: List[Flashcard] = []

    for idx, chunk in enumerate(chunks):
        remaining = num_cards - len(all_cards)
        if remaining <= 0:
            break
        target = min(per_chunk, remaining) if idx < len(chunks) - 1 else remaining

        appendix = (prompt_appendix or "").strip()
        appendix_block = f"\n\n=== ADDITIONAL INSTRUCTIONS ===\n{appendix}" if appendix else ""
        exam_context = (previous_exams_text or "").strip()
        exams_block = (
            "\n\n=== PREVIOUS EXAMS (STYLE REFERENCE) ===\n"
            "Use the questions below to match likely exam style, phrasing, and topic emphasis. "
            "Do not copy wording verbatim; instead, imitate the level of specificity and the kinds of concepts tested.\n"
            f"{exam_context[:6000]}"
        ) if exam_context else ""

        user_msg = (
            f"Create exactly {target} high-quality flashcards from the material below.\n\n"
            f"=== MATERIAL ===\n{chunk}"
            f"{appendix_block}"
            f"{exams_block}"
        )

        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = resp.choices[0].message.content

        def _ensure_list(obj):
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict):
                # single card dict or container with card lists
                if "cards" in obj and isinstance(obj["cards"], list):
                    return obj["cards"]
                if "flashcards" in obj and isinstance(obj["flashcards"], list):
                    return obj["flashcards"]
                return [obj]
            # try to parse JSON string
            if isinstance(obj, str):
                try:
                    parsed = json.loads(obj)
                except Exception:
                    # return raw string as-is so downstream can attempt to coerce
                    return [obj]
                return _ensure_list(parsed)
            raise ValueError("Unsupported response format from LLM")

        try:
            parsed = json.loads(content)
        except Exception:
            # content might already be a Python structure or a plain string
            parsed = content

        raw_items = _ensure_list(parsed)

        def _normalize_card_dict(item: dict) -> dict:
            # Handle occasional alternate key names from model output.
            question = item.get("question") or item.get("front") or item.get("q")
            answer = item.get("answer") or item.get("back") or item.get("a")
            if question is not None and answer is not None:
                return {"question": str(question).strip(), "answer": str(answer).strip()}
            return item

        for item in raw_items:
            if isinstance(item, dict):
                normalized = _normalize_card_dict(item)
                # If this dict is another wrapper, expand it and continue.
                if "cards" in normalized or "flashcards" in normalized:
                    for sub in _ensure_list(normalized):
                        if isinstance(sub, dict):
                            all_cards.append(Flashcard(**_normalize_card_dict(sub)))
                    continue
                all_cards.append(Flashcard(**normalized))
            elif isinstance(item, str):
                # try parsing a JSON-encoded card inside the string
                try:
                    inner = json.loads(item)
                except Exception:
                    # best-effort: split into Q/A on first blank line or newline
                    if "\n\n" in item:
                        q, a = item.split("\n\n", 1)
                    elif "\n" in item:
                        q, a = item.split("\n", 1)
                    else:
                        raise ValueError(
                            "Received a plain string from the model that couldn't be parsed into a card. "
                            f"Content: {item!r}"
                        )
                    all_cards.append(Flashcard(question=q.strip(), answer=a.strip()))
                else:
                    # recursively handle parsed inner object
                    if isinstance(inner, dict):
                        normalized = _normalize_card_dict(inner)
                        if "cards" in normalized or "flashcards" in normalized:
                            for sub in _ensure_list(normalized):
                                if isinstance(sub, dict):
                                    all_cards.append(Flashcard(**_normalize_card_dict(sub)))
                            continue
                        all_cards.append(Flashcard(**normalized))
                    elif isinstance(inner, list):
                        for sub in inner:
                            if isinstance(sub, dict):
                                all_cards.append(Flashcard(**_normalize_card_dict(sub)))
                            else:
                                raise ValueError("Unexpected card format inside list")
                    else:
                        raise ValueError("Unexpected parsed content from model")

    return all_cards[:num_cards]