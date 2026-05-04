import tempfile
from pathlib import Path
from datetime import datetime
import re
import streamlit as st

import course_manager
from extractors import extract_text
from generator import generate_cards
from anki_builder import build_deck
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "course"


def _persist_uploads(uploaded_files):
    temp_paths = []
    for uploaded_file in uploaded_files or []:
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getbuffer())
            temp_paths.append((uploaded_file.name, Path(tmp.name)))
    return temp_paths


# Load stored API key from app data
stored_settings = course_manager.get_openai_settings()
stored_api_key = stored_settings.get("api_key", "")
stored_base_url = stored_settings.get("base_url", "")
stored_model = stored_settings.get("model", "")


# ---------- Page config ----------
st.set_page_config(
    page_title="Anki Generator",
    page_icon="🧠",
    layout="centered",
)

st.title("🧠 Anki Flashcard Generator")
st.caption("Drag in your lecture slides → get a ready-to-import `.apkg` deck.")

# ---------- Sidebar: API key + course management ----------
with st.sidebar:
    st.header("⚙️ Settings")

    api_key = st.text_input(
        "OpenAI API key",
        value=stored_api_key or OPENAI_API_KEY or "",
        type="password",
        help="Stored in app data. You can also set the OPENAI_API_KEY env var.",
    )
    base_url = st.text_input(
        "OpenAI base URL",
        value=stored_base_url or OPENAI_BASE_URL or "",
        placeholder="https://api.openai.com/v1",
        help="Use this for OpenAI-compatible APIs such as local gateways or other providers.",
    )
    model = st.text_input(
        "Model",
        value=stored_model or MODEL or "",
        help="Model name to send to the API endpoint.",
    )
    if api_key:
        # Make it available to the generator module at runtime
        import os
        os.environ["OPENAI_API_KEY"] = api_key
    if base_url:
        import os
        os.environ["OPENAI_BASE_URL"] = base_url
    if model:
        import os
        os.environ["MODEL"] = model

    if (
        api_key != stored_api_key
        or base_url != stored_base_url
        or model != stored_model
    ):
        course_manager.set_openai_settings(api_key=api_key, base_url=base_url, model=model)

    st.divider()
    st.header("📚 Courses")

    existing = course_manager.list_courses()
    if existing:
        st.write("**Existing:**")
        for c in existing:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"• {c}")
            with col2:
                if st.button("🗑️", key=f"delete_{c}", help=f"Delete '{c}'"):
                    try:
                        course_manager.delete_course(c)
                        st.success(f"Deleted '{c}'.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
    else:
        st.info("No courses yet — create one below.")

    def _create_course_handler():
        course_name = st.session_state.get("new_course_input", "").strip()
        if not course_name:
            st.warning("Please enter a name.")
            return
        try:
            course_manager.create_course(course_name)
            st.success(f"Created '{course_name}'.")
            st.session_state["new_course_input"] = ""
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    st.text_input(
        "New course name",
        key="new_course_input",
        on_change=_create_course_handler,
        placeholder="Type and press Enter to create",
    )
    if st.button("➕ Create course", use_container_width=True):
        _create_course_handler()


# ---------- Main form ----------
courses = course_manager.list_courses()

if not courses:
    st.warning("👈 Create a course in the sidebar first.")
    st.stop()

# Course selection outside form so it triggers rerun on change
st.subheader("1 · Choose course")
course = st.selectbox("Course", options=courses, index=0, key="selected_course")
default_output_dir = Path.cwd() / "output" / _slugify(course)

with st.form("generate_form", clear_on_submit=False):
    st.subheader("2 · Drop your slides")
    uploaded = st.file_uploader(
        "Lecture files (you can upload multiple)",
        type=["pdf", "pptx", "ppt", "txt", "md"],
        accept_multiple_files=True,
        help="Upload one or more PDF / PowerPoint slide files. Each will produce the selected number of cards.",
    )

    st.subheader("3 · Previous exams (optional)")
    previous_exams = st.file_uploader(
        "Previous exams",
        type=["pdf", "pptx", "ppt", "txt", "md"],
        accept_multiple_files=True,
        help="Upload past exams if you want the flashcards to match their style, phrasing, and topic emphasis.",
    )

    st.subheader("4 · Configure")
    num_cards = st.slider("Number of cards per lecture file", 5, 100, 20, step=5)
    output_dir = st.text_input(
        "Output directory",
        value=str(default_output_dir),
        help="Where the .apkg file will be saved on disk.",
    )

    prompt_appendix = st.text_area(
        "Optional message appendix",
        value="",
        placeholder="Example: Focus on conceptual why/how cards and include one practical example per answer.",
        help="Extra instructions appended to the card-generation prompt.",
    )

    submitted = st.form_submit_button("🚀 Generate deck", use_container_width=True)


# ---------- Generation pipeline ----------
if submitted:
    if not uploaded:
        st.error("Please upload at least one file first.")
        st.stop()
    if not api_key:
        st.error("Please provide an OpenAI API key in the sidebar.")
        st.stop()

    out_dir = Path(output_dir).expanduser()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        st.error(f"Cannot create output directory: {e}")
        st.stop()

    # Persist uploads to temp files and process each lecture separately
    tmp_paths = _persist_uploads(uploaded)
    exam_tmp_paths = _persist_uploads(previous_exams)
    all_cards = []
    per_file_cards = []  # tuples of (orig_name, cards)
    previous_exams_text_parts = []

    for exam_name, exam_path in exam_tmp_paths:
        exam_text = extract_text(exam_path)
        if exam_text.strip():
            previous_exams_text_parts.append(f"--- Previous Exam: {exam_name} ---\n{exam_text}")

    progress = st.progress(0, text="Starting…")
    try:
        progress.progress(10, text="📄 Extracting text from slides…")

        previous_exams_text = "\n\n".join(previous_exams_text_parts)

        for i, (orig_name, tmp_path) in enumerate(tmp_paths, start=1):
            progress.progress(10 + int(60 * (i - 1) / max(1, len(tmp_paths))), text=f"📄 Extracting {orig_name}…")
            text = extract_text(tmp_path)
            if not text.strip():
                st.warning(f"No text could be extracted from {orig_name} (scanned PDF?). Skipping.")
                continue

            progress.progress(40 + int(40 * i / max(1, len(tmp_paths))), text=f"🤖 Generating {num_cards} flashcards for {orig_name}…")
            cards = generate_cards(
                text,
                num_cards,
                prompt_appendix=prompt_appendix,
                previous_exams_text=previous_exams_text,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            per_file_cards.append((orig_name, cards))
            all_cards.extend(cards)

        if not all_cards:
            st.error("No cards were generated from the uploaded files.")
            st.stop()

        progress.progress(85, text="📦 Building combined .apkg…")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{course}_combined_{timestamp}.apkg"
        build_deck(course, all_cards, out_path)
        course_manager.add_deck(course, str(out_path), len(all_cards))

        progress.progress(100, text="✅ Done!")
    except Exception as e:
        st.exception(e)
        st.stop()
    finally:
        for _, p in tmp_paths:
            p.unlink(missing_ok=True)
        for _, p in exam_tmp_paths:
            p.unlink(missing_ok=True)

    # ---------- Results ----------
    st.success(f"Saved **{len(all_cards)} cards** → `{out_path}`")

    # Offer in-browser download too
    with open(out_path, "rb") as f:
        st.download_button(
            "⬇️ Download .apkg",
            data=f.read(),
            file_name=out_path.name,
            mime="application/octet-stream",
            use_container_width=True,
        )

    # Preview cards
    with st.expander(f"👀 Preview all {len(all_cards)} cards"):
        idx = 1
        for fname, cards in per_file_cards:
            st.markdown(f"**Lecture: {fname} — {len(cards)} cards**")
            for c in cards:
                st.markdown(f"**Q{idx}.** {c.question}")
                st.markdown(f"**A.** {c.answer}")
                st.divider()
                idx += 1