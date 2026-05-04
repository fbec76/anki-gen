from pathlib import Path

from anki_builder import build_deck
from extractors import extract_text
from generator import Flashcard
import course_manager



def test_end_to_end_multi_lecture_txt_pipeline(tmp_path):
    # Simulate two lecture uploads and generate X cards per lecture.
    lecture_1 = tmp_path / "lecture1.txt"
    lecture_2 = tmp_path / "lecture2.txt"
    lecture_1.write_text("Topic A\nConcept 1\nConcept 2", encoding="utf-8")
    lecture_2.write_text("Topic B\nConcept 3\nConcept 4", encoding="utf-8")

    cards_per_lecture = 2
    all_cards = []

    for lecture in [lecture_1, lecture_2]:
        text = extract_text(lecture)
        assert text.strip()

        # Deterministic stand-in for LLM output during e2e pipeline test.
        generated = [
            Flashcard(question=f"{lecture.stem} Q{i}", answer=f"{lecture.stem} A{i}")
            for i in range(1, cards_per_lecture + 1)
        ]
        all_cards.extend(generated)

    out_path = tmp_path / "course_combined.apkg"
    built = build_deck("My Course", all_cards, out_path)

    assert built == out_path
    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert len(all_cards) == 4


def test_delete_course(tmp_path, monkeypatch):
    # Mock COURSES_FILE to use a temp file
    courses_file = tmp_path / "courses.json"
    monkeypatch.setattr("course_manager.COURSES_FILE", courses_file)

    # Create a course
    course_manager.create_course("Test Course")
    assert "Test Course" in course_manager.list_courses()

    # Delete the course
    course_manager.delete_course("Test Course")
    assert "Test Course" not in course_manager.list_courses()


def test_delete_nonexistent_course(tmp_path, monkeypatch):
    # Mock COURSES_FILE to use a temp file
    courses_file = tmp_path / "courses.json"
    monkeypatch.setattr("course_manager.COURSES_FILE", courses_file)

    # Try to delete a non-existent course
    try:
        course_manager.delete_course("Nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not found" in str(e)


def test_api_key_storage(tmp_path, monkeypatch):
    # Mock API_KEY_FILE to use a temp file
    api_key_file = tmp_path / "api_key.json"
    monkeypatch.setattr("course_manager.API_KEY_FILE", api_key_file)

    # Initially empty
    assert course_manager.get_api_key() == ""

    # Store an API key
    test_key = "sk-test-key-12345"
    course_manager.set_api_key(test_key)

    # Retrieve it
    assert course_manager.get_api_key() == test_key

    # Update with a new key
    new_key = "sk-new-key-67890"
    course_manager.set_api_key(new_key)
    assert course_manager.get_api_key() == new_key


def test_openai_settings_storage(tmp_path, monkeypatch):
    settings_file = tmp_path / "openai_settings.json"
    monkeypatch.setattr("course_manager.OPENAI_SETTINGS_FILE", settings_file)

    defaults = course_manager.get_openai_settings()
    assert defaults == {"api_key": "", "base_url": "", "model": ""}

    course_manager.set_openai_settings(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )

    assert course_manager.get_openai_settings() == {
        "api_key": "sk-test",
        "base_url": "https://example.com/v1",
        "model": "gpt-test",
    }

