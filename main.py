from pathlib import Path
import typer
from rich import print
from rich.prompt import Prompt, IntPrompt

import course_manager
from extractors import extract_text
from generator import generate_cards
from anki_builder import build_deck

app = typer.Typer(help="Generate Anki decks from lecture slides.")


@app.command()
def create_course(name: str):
    """Create a new course."""
    course_manager.create_course(name)
    print(f"[green]✓ Course '{name}' created.[/green]")


@app.command()
def list_courses():
    """List all courses."""
    for c in course_manager.list_courses():
        print(f"• {c}")


@app.command()
def generate(
    course: str = typer.Option(..., "--course", "-c"),
    file: Path = typer.Option(..., "--file", "-f", exists=True),
    num_cards: int = typer.Option(20, "--num", "-n"),
    output_dir: Path = typer.Option(..., "--out", "-o"),
):
    """Generate an Anki deck from a slide file."""
    print(f"[cyan]→ Extracting text from {file.name}...[/cyan]")
    text = extract_text(file)
    print(f"[cyan]→ Generating {num_cards} flashcards via LLM...[/cyan]")
    cards = generate_cards(text, num_cards)
    out_path = output_dir / f"{course}_{file.stem}.apkg"
    build_deck(course, cards, out_path)
    course_manager.add_deck(course, str(out_path), len(cards))
    print(f"[green]✓ Saved {len(cards)} cards to {out_path}[/green]")


@app.command()
def wizard():
    """Interactive mode."""
    courses = course_manager.list_courses()
    if courses:
        print("Existing courses:", ", ".join(courses))
    course = Prompt.ask("Course name (new or existing)")
    if course not in courses:
        course_manager.create_course(course)

    file = Path(Prompt.ask("Path to slide file (PDF/PPTX)"))
    num = IntPrompt.ask("Number of cards", default=20)
    out = Path(Prompt.ask("Output directory", default=str(Path.cwd())))

    text = extract_text(file)
    cards = generate_cards(text, num)
    out_path = out / f"{course}_{file.stem}.apkg"
    build_deck(course, cards, out_path)
    course_manager.add_deck(course, str(out_path), len(cards))
    print(f"[green]✓ Done — {len(cards)} cards → {out_path}[/green]")


if __name__ == "__main__":
    app()