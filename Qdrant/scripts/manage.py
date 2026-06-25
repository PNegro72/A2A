"""
Database management CLI — inspect, maintain, and control Qdrant collections.

Commands
--------
  info       Show collection metadata and config
  list       List all collections in the Qdrant instance
  stats      Chunk / document counts and payload statistics
  scroll     Page through stored points
  delete     Delete a whole collection (requires --confirm)
  delete-doc Delete all chunks belonging to a specific source file
  recreate   Drop and recreate the collection (data WILL BE LOST)
  export     Export all payloads to a JSON file
  cache      Show embedding cache stats or clear it

Usage
-----
  python scripts/manage.py info
  python scripts/manage.py info --mode hybrid
  python scripts/manage.py list
  python scripts/manage.py stats
  python scripts/manage.py scroll --limit 5
  python scripts/manage.py delete --confirm
  python scripts/manage.py delete-doc --source "report.pdf"
  python scripts/manage.py recreate --mode hybrid
  python scripts/manage.py export --output dump.json
  python scripts/manage.py cache
  python scripts/manage.py cache --clear
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cache_manager import get_cache
from src.qdrant_manager import QdrantManager

console = Console()


def _make_manager(mode: str, collection: str | None) -> QdrantManager:
    return QdrantManager(mode=mode, collection=collection or None)


# ─────────────────────────────────────────────
#  CLI group
# ─────────────────────────────────────────────

@click.group()
def cli():
    """Qdrant RAG — database management tool."""


# ── info ──────────────────────────────────────

@cli.command()
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
@click.option("--collection", default=None, help="Override collection name.")
def info(mode, collection):
    """Show collection metadata and vector configuration."""
    manager = _make_manager(mode, collection)
    if not manager.collection_exists():
        console.print(f"[red]Collection '{manager.collection}' does not exist.[/red]")
        return

    data = manager.get_info()
    table = Table(title=f"Collection: {data['name']}", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    for k, v in data.items():
        table.add_row(k, str(v))
    console.print(table)


# ── list ──────────────────────────────────────

@cli.command("list")
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
def list_collections(mode):
    """List all collections in the Qdrant instance."""
    manager = _make_manager(mode, None)
    cols = manager.list_collections()
    if not cols:
        console.print("[yellow]No collections found.[/yellow]")
        return
    table = Table(title="Collections")
    table.add_column("#", justify="right")
    table.add_column("Name", style="cyan")
    for i, name in enumerate(cols, 1):
        table.add_row(str(i), name)
    console.print(table)


# ── stats ─────────────────────────────────────

@cli.command()
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
@click.option("--collection", default=None)
def stats(mode, collection):
    """Show chunk / document breakdown and payload statistics."""
    manager = _make_manager(mode, collection)
    if not manager.collection_exists():
        console.print(f"[red]Collection '{manager.collection}' does not exist.[/red]")
        return

    info_data = manager.get_info()
    console.print(Panel.fit(
        f"[bold]{info_data['name']}[/bold]  —  "
        f"{info_data['points_count']} points  |  status: {info_data['status']}",
        border_style="green",
    ))

    # Scroll to gather per-file stats
    file_stats: dict[str, int] = {}
    section_stats: dict[str, int] = {}
    offset = None

    with console.status("[dim]Scanning points...[/dim]"):
        while True:
            records, offset = manager.scroll(limit=500, offset=offset)
            for r in records:
                p = r["payload"]
                sf = p.get("source_file", "unknown")
                sec = p.get("section", "") or "(no section)"
                file_stats[sf] = file_stats.get(sf, 0) + 1
                section_stats[sec] = section_stats.get(sec, 0) + 1
            if offset is None:
                break

    # Per-file table
    table = Table(title="Chunks per Source File", show_lines=True)
    table.add_column("Source File", style="cyan")
    table.add_column("Chunk Count", justify="right", style="green")
    for fname, count in sorted(file_stats.items(), key=lambda x: -x[1]):
        table.add_row(fname, str(count))
    console.print(table)

    # Top sections
    top_sections = sorted(section_stats.items(), key=lambda x: -x[1])[:15]
    table2 = Table(title="Top 15 Sections")
    table2.add_column("Section", style="cyan")
    table2.add_column("Count", justify="right")
    for sec, cnt in top_sections:
        table2.add_row(sec[:80], str(cnt))
    console.print(table2)


# ── scroll ────────────────────────────────────

@cli.command()
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
@click.option("--collection", default=None)
@click.option("--limit", default=10, show_default=True)
@click.option("--offset", default=None, help="Page offset (UUID of last seen point).")
def scroll(mode, collection, limit, offset):
    """Page through stored points."""
    manager = _make_manager(mode, collection)
    if not manager.collection_exists():
        console.print(f"[red]Collection '{manager.collection}' does not exist.[/red]")
        return

    records, next_offset = manager.scroll(limit=limit, offset=offset)
    if not records:
        console.print("[yellow]No records found.[/yellow]")
        return

    table = Table(title=f"Points (limit={limit})", show_lines=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Source", style="cyan")
    table.add_column("Section")
    table.add_column("Pg", justify="right")
    table.add_column("Chars", justify="right")
    table.add_column("Text preview")

    for r in records:
        p = r["payload"]
        preview = (p.get("text") or "")[:80].replace("\n", " ")
        table.add_row(
            str(r["id"])[:8] + "…",
            p.get("source_file", "?"),
            (p.get("section") or "")[:40],
            str(p.get("page", "-")),
            str(p.get("char_count", "-")),
            preview,
        )

    console.print(table)
    if next_offset:
        console.print(f"[dim]Next offset: {next_offset}[/dim]")
    else:
        console.print("[dim]End of collection.[/dim]")


# ── delete ────────────────────────────────────

@cli.command()
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
@click.option("--collection", default=None)
@click.option("--confirm", is_flag=True, default=False, help="Required safety flag.")
def delete(mode, collection, confirm):
    """Delete the entire collection. Requires --confirm."""
    if not confirm:
        console.print("[red]Safety flag missing. Add --confirm to delete the collection.[/red]")
        return
    manager = _make_manager(mode, collection)
    deleted = manager.delete_collection()
    if deleted:
        console.print(f"[green]Collection '{manager.collection}' deleted.[/green]")
    else:
        console.print(f"[yellow]Collection '{manager.collection}' not found.[/yellow]")


# ── delete-doc ────────────────────────────────

@cli.command("delete-doc")
@click.option("--source", required=True, help="Source filename to remove (e.g. 'report.pdf').")
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
@click.option("--collection", default=None)
def delete_doc(source, mode, collection):
    """Delete all chunks belonging to a specific source file."""
    manager = _make_manager(mode, collection)
    if not manager.collection_exists():
        console.print(f"[red]Collection '{manager.collection}' does not exist.[/red]")
        return
    count = manager.delete_by_source(source)
    console.print(f"[green]Deleted chunks for source_file='{source}' (count={count})[/green]")


# ── recreate ──────────────────────────────────

@cli.command()
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
@click.option("--collection", default=None)
def recreate(mode, collection):
    """Drop and recreate the collection (all data will be lost)."""
    manager = _make_manager(mode, collection)
    console.print(f"[yellow]Recreating collection '{manager.collection}'…[/yellow]")
    manager.create_collection(recreate=True)
    console.print(f"[green]Done. Empty collection '{manager.collection}' ready.[/green]")


# ── export ────────────────────────────────────

@cli.command()
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]))
@click.option("--collection", default=None)
@click.option("--output", default="export.json", show_default=True)
def export(mode, collection, output):
    """Export all payloads to a JSON file."""
    manager = _make_manager(mode, collection)
    if not manager.collection_exists():
        console.print(f"[red]Collection '{manager.collection}' does not exist.[/red]")
        return

    all_records = []
    offset = None
    total = 0

    with console.status("[dim]Exporting...[/dim]"):
        while True:
            records, offset = manager.scroll(limit=500, offset=offset)
            all_records.extend(records)
            total += len(records)
            if offset is None:
                break

    out_path = Path(output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False, default=str)

    console.print(f"[green]Exported {total} records to '{out_path}'[/green]")


# ── cache ─────────────────────────────────────

@cli.command()
@click.option("--clear", is_flag=True, default=False, help="Clear the embedding cache.")
def cache(clear):
    """Show embedding cache stats or clear it."""
    c = get_cache()
    s = c.stats()
    if clear:
        c.clear()
        console.print("[green]Cache cleared.[/green]")
        return
    table = Table(title="Embedding Cache", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    for k, v in s.items():
        table.add_row(k, str(v))
    console.print(table)


if __name__ == "__main__":
    cli()
