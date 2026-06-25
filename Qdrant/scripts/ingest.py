"""
Ingestion pipeline — scans data/raw/, loads, chunks, embeds, and uploads.

Usage
-----
  # Ingest all files in data/raw/ (dense mode, default)
  python scripts/ingest.py

  # Specific file
  python scripts/ingest.py --file docs/manual.pdf

  # Hybrid mode (creates/uses the hybrid collection)
  python scripts/ingest.py --mode hybrid

  # Dry-run: show what would be ingested without uploading
  python scripts/ingest.py --dry-run

  # Force re-ingest even if already ingested
  python scripts/ingest.py --force

  # Custom chunk size
  python scripts/ingest.py --chunk-size 768 --overlap 96
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running as  python scripts/ingest.py  from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from src.config import BATCH_SIZE, CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR, SUPPORTED_EXTENSIONS
from src.chunker import chunk_pages
from src.embeddings import DenseEmbedder, HybridEmbedder
from src.loaders import load_document
from src.qdrant_manager import QdrantManager

console = Console()


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _discover_files(folder: Path, recursive: bool = True) -> list[Path]:
    """Return all supported files under *folder*."""
    files: list[Path] = []
    glob = folder.rglob("*") if recursive else folder.glob("*")
    for p in sorted(glob):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(p)
    return files


def _get_already_ingested(manager: QdrantManager) -> set[str]:
    """Scroll the collection and collect all unique source_file values."""
    seen: set[str] = set()
    offset = None
    while True:
        records, offset = manager.scroll(limit=256, offset=offset)
        for r in records:
            sf = r["payload"].get("source_file")
            if sf:
                seen.add(sf)
        if offset is None:
            break
    return seen


def _process_file(
    path: Path,
    loader_key: str,
    embedder,
    manager: QdrantManager,
    chunk_size: int,
    overlap: int,
    dry_run: bool,
    mode: str,
) -> dict:
    """Load → chunk → embed → upload one file. Returns stats dict."""
    t0 = time.perf_counter()

    # 1. Load
    pages = load_document(path, loader_key)

    # 2. Chunk
    chunks = chunk_pages(pages, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return {"file": path.name, "status": "skipped (no chunks)", "chunks": 0}

    # 3. Embed (in batches to manage memory)
    all_embeddings = []
    texts = [c.text for c in chunks]
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start: start + BATCH_SIZE]
        all_embeddings.extend(embedder.embed(batch))

    # 4. Upload
    if not dry_run:
        uploaded = manager.upsert_chunks(chunks, all_embeddings)
    else:
        uploaded = len(chunks)

    elapsed = time.perf_counter() - t0
    return {
        "file":    path.name,
        "status":  "dry-run" if dry_run else "ok",
        "pages":   len(pages),
        "chunks":  len(chunks),
        "vectors": uploaded,
        "elapsed": round(elapsed, 2),
    }


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

@click.command()
@click.option("--file", "single_file", default=None, help="Ingest a single file instead of the whole folder.")
@click.option("--folder", default=str(DATA_DIR), show_default=True, help="Folder to scan for documents.")
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]), show_default=True, help="Embedding and collection mode.")
@click.option("--chunk-size", default=CHUNK_SIZE, show_default=True, help="Max characters per chunk.")
@click.option("--overlap", default=CHUNK_OVERLAP, show_default=True, help="Overlap characters between chunks.")
@click.option("--dry-run", is_flag=True, default=False, help="Parse and chunk without uploading.")
@click.option("--force", is_flag=True, default=False, help="Re-ingest files already in the collection.")
@click.option("--recreate", is_flag=True, default=False, help="Delete and recreate the collection before ingesting.")
def main(single_file, folder, mode, chunk_size, overlap, dry_run, force, recreate):
    """RAG Ingestion Pipeline — load → chunk → embed → upload to Qdrant."""

    console.print(Panel.fit(
        f"[bold cyan]RAG Ingestion Pipeline[/bold cyan]\n"
        f"mode={mode}  chunk_size={chunk_size}  overlap={overlap}  "
        f"dry_run={dry_run}  force={force}",
        border_style="cyan",
    ))

    # ── Setup ──────────────────────────────────────────────────────────────
    manager = QdrantManager(mode=mode)

    if not dry_run:
        manager.create_collection(recreate=recreate)

    embedder = HybridEmbedder() if mode == "hybrid" else DenseEmbedder()
    console.print(f"[dim]Embedder: {'HybridEmbedder' if mode == 'hybrid' else 'DenseEmbedder'}[/dim]")

    # ── File discovery ─────────────────────────────────────────────────────
    if single_file:
        target = Path(single_file)
        if not target.exists():
            console.print(f"[red]File not found: {target}[/red]")
            sys.exit(1)
        files = [target]
    else:
        scan_dir = Path(folder)
        if not scan_dir.exists():
            console.print(f"[red]Folder not found: {scan_dir}[/red]")
            sys.exit(1)
        files = _discover_files(scan_dir)

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        sys.exit(0)

    console.print(f"[green]Found {len(files)} file(s)[/green]")

    # ── Skip already-ingested files ────────────────────────────────────────
    if not force and not dry_run and manager.collection_exists():
        already = _get_already_ingested(manager)
        before = len(files)
        files = [f for f in files if f.name not in already]
        skipped = before - len(files)
        if skipped:
            console.print(f"[dim]Skipping {skipped} file(s) already in collection (use --force to re-ingest)[/dim]")

    if not files:
        console.print("[yellow]All files already ingested. Nothing to do.[/yellow]")
        sys.exit(0)

    # ── Ingest ────────────────────────────────────────────────────────────
    results = []
    total_chunks = 0
    total_errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting files...", total=len(files))

        for path in files:
            loader_key = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
            if not loader_key:
                progress.advance(task)
                continue

            progress.update(task, description=f"[cyan]{path.name}[/cyan]")
            try:
                stats = _process_file(
                    path=path,
                    loader_key=loader_key,
                    embedder=embedder,
                    manager=manager,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    dry_run=dry_run,
                    mode=mode,
                )
                results.append(stats)
                total_chunks += stats.get("chunks", 0)
            except Exception as exc:
                console.print(f"\n[red]ERROR processing {path.name}: {exc}[/red]")
                results.append({"file": path.name, "status": "error", "error": str(exc)})
                total_errors += 1

            progress.advance(task)

    # ── Summary table ──────────────────────────────────────────────────────
    table = Table(title="Ingestion Summary", show_lines=True)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Pages", justify="right")
    table.add_column("Chunks", justify="right")
    table.add_column("Elapsed(s)", justify="right")

    for r in results:
        status_style = "red" if r.get("status") == "error" else "green"
        table.add_row(
            r.get("file", "?"),
            f"[{status_style}]{r.get('status', '?')}[/{status_style}]",
            str(r.get("pages", "-")),
            str(r.get("chunks", "-")),
            str(r.get("elapsed", "-")),
        )

    console.print(table)
    console.print(
        f"\n[bold]Total:[/bold] {len(results)} file(s) | "
        f"[bold]{total_chunks}[/bold] chunks | "
        f"[bold red]{total_errors}[/bold red] errors"
    )


if __name__ == "__main__":
    main()
