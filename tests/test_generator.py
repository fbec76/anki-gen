import json

import generator


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("No more fake responses configured")
        return _FakeResponse(self._responses.pop(0))


class _FakeChat:
    def __init__(self, responses):
        self.completions = _FakeCompletions(responses)


class _FakeClient:
    def __init__(self, responses):
        self.chat = _FakeChat(responses)


def test_generate_cards_accepts_flashcards_wrapper(monkeypatch):
    payload = json.dumps(
        {
            "flashcards": [
                {"question": "Q1", "answer": "A1"},
                {"question": "Q2", "answer": "A2"},
            ]
        }
    )

    monkeypatch.setattr(generator, "OpenAI", lambda **kwargs: _FakeClient([payload]))
    monkeypatch.setattr(generator, "MAX_CHUNK_CHARS", 10_000)

    cards = generator.generate_cards("short text", 2)

    assert len(cards) == 2
    assert cards[0].question == "Q1"
    assert cards[0].answer == "A1"



def test_generate_cards_handles_alt_front_back_keys(monkeypatch):
    payload = json.dumps({"cards": [{"front": "What is X?", "back": "X is ..."}]})

    monkeypatch.setattr(generator, "OpenAI", lambda **kwargs: _FakeClient([payload]))
    monkeypatch.setattr(generator, "MAX_CHUNK_CHARS", 10_000)

    cards = generator.generate_cards("short text", 1)

    assert len(cards) == 1
    assert cards[0].question == "What is X?"
    assert cards[0].answer == "X is ..."



def test_generate_cards_respects_requested_count_across_chunks(monkeypatch):
    payload_1 = json.dumps({"cards": [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]})
    payload_2 = json.dumps({"cards": [{"question": "Q3", "answer": "A3"}, {"question": "Q4", "answer": "A4"}]})

    monkeypatch.setattr(generator, "OpenAI", lambda **kwargs: _FakeClient([payload_1, payload_2]))
    monkeypatch.setattr(generator, "MAX_CHUNK_CHARS", 5)

    cards = generator.generate_cards("0123456789", 3)

    assert len(cards) == 3
    assert [c.question for c in cards] == ["Q1", "Q2", "Q3"]


def test_generate_cards_includes_prompt_appendix(monkeypatch):
    payload = json.dumps({"cards": [{"question": "Q1", "answer": "A1"}]})
    fake = _FakeClient([payload])

    monkeypatch.setattr(generator, "OpenAI", lambda **kwargs: fake)
    monkeypatch.setattr(generator, "MAX_CHUNK_CHARS", 10_000)

    appendix = "Prefer application-focused cards and include one formula if relevant."
    cards = generator.generate_cards("short text", 1, prompt_appendix=appendix)

    assert len(cards) == 1
    sent_user_msg = fake.chat.completions.calls[0]["messages"][1]["content"]
    assert "=== ADDITIONAL INSTRUCTIONS ===" in sent_user_msg
    assert appendix in sent_user_msg


def test_generate_cards_includes_previous_exams_context(monkeypatch):
    payload = json.dumps({"cards": [{"question": "Q1", "answer": "A1"}]})
    fake = _FakeClient([payload])

    monkeypatch.setattr(generator, "OpenAI", lambda **kwargs: fake)
    monkeypatch.setattr(generator, "MAX_CHUNK_CHARS", 10_000)

    previous_exams = (
        "Exam 1: Define the key stages of cellular respiration.\n"
        "Exam 2: Explain how insulin regulates blood glucose."
    )
    cards = generator.generate_cards(
        "short text",
        1,
        previous_exams_text=previous_exams,
    )

    assert len(cards) == 1
    sent_user_msg = fake.chat.completions.calls[0]["messages"][1]["content"]
    assert "=== PREVIOUS EXAMS (STYLE REFERENCE) ===" in sent_user_msg
    assert "Define the key stages of cellular respiration" in sent_user_msg
    assert "Do not copy wording verbatim" in sent_user_msg


def test_generate_cards_uses_custom_client_settings(monkeypatch):
    payload = json.dumps({"cards": [{"question": "Q1", "answer": "A1"}]})
    fake = _FakeClient([payload])
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(generator, "OpenAI", lambda **kwargs: fake_openai(**kwargs))
    monkeypatch.setattr(generator, "MAX_CHUNK_CHARS", 10_000)

    cards = generator.generate_cards(
        "short text",
        1,
        api_key="sk-custom",
        base_url="https://example.com/v1",
        model="gpt-test-model",
    )

    assert len(cards) == 1
    assert captured["api_key"] == "sk-custom"
    assert captured["base_url"] == "https://example.com/v1"
    assert fake.chat.completions.calls[0]["model"] == "gpt-test-model"
