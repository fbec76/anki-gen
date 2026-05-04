# anki-gen

Anki Flashcard Generator using an OpenAI-compatible API.

Generate Anki flashcards from lecture material (PDF/PPTX/TXT/MD) with CLI or Streamlit UI.

## Features
- Multiple slide uploads in Streamlit
- Generates X cards per uploaded lecture
- Optional previous-exams file upload to steer question style and topic emphasis
- Editable OpenAI-compatible endpoint settings in the sidebar
- Builds one combined `.apkg` deck
- Course metadata storage

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Streamlit app
```bash
streamlit run streamlit_app.py
```

## Run CLI
```bash
python main.py list-courses
python main.py create-course "My Course"
python main.py generate --course "My Course" --file ./lecture.pdf --num 20 --out .
```

## Run tests
```bash
pytest -q
```

## Test coverage added
- `tests/test_generator.py`: robust parsing of varied LLM response shapes (`cards`, `flashcards`, alt keys)
- `tests/test_pipeline_e2e.py`: end-to-end multi-lecture pipeline (text extraction -> card aggregation -> `.apkg` build)
