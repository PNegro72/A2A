"""
Query interface — send a natural-language query and retrieve the top-N chunks.

Usage
-----
  # Basic dense query, top 5 results
  python scripts/query.py "What is machine learning?"

  # Hybrid mode (dense + sparse)
  python scripts/query.py "What is machine learning?" --mode hybrid

  # Retrieve top 10 results
  python scripts/query.py "Explain transformers" --top-k 10

  # Filter by source file
  python scripts/query.py "What are the KPIs?" --filter source_file=report.pdf

  # Show full chunk text (not just preview)
  python scripts/query.py "Define overfitting" --verbose

  # Export results to JSON
  python scripts/query.py "Neural networks" --output results.json

  # Minimum score threshold (0.0–1.0)
  python scripts/query.py "neural networks" --min-score 0.4
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from src.embeddings import DenseEmbedder, HybridEmbedder
from src.qdrant_manager import QdrantManager

console = Console()


def _parse_filters(filter_strs: tuple[str, ...]) -> dict:
    """Parse 'key=value' strings into a filter dict."""
    filters = {}
    for f in filter_strs:
        if "=" not in f:
            console.print(f"[yellow]Ignoring malformed filter (expected key=value): {f!r}[/yellow]")
            continue
        k, v = f.split("=", 1)
        filters[k.strip()] = v.strip()
    return filters


def _display_results(results: list[dict], verbose: bool, query: str, mode: str) -> None:
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    console.print(Rule(f"[bold cyan]Results for:[/bold cyan] {query!r}  [dim](mode={mode})[/dim]"))

    for i, r in enumerate(results, 1):
        score_colour = (
            "green" if r["score"] >= 0.7
            else "yellow" if r["score"] >= 0.4
            else "red"
        )
        header = (
            f"[bold]#{i}[/bold]  "
            f"score=[{score_colour}]{r['score']:.4f}[/{score_colour}]  "
            f"[cyan]{r['source_file']}[/cyan]"
            + (f"  p.{r['page']}" if r.get("page") else "")
            + (f"  §[dim]{r['section'][:50]}[/dim]" if r.get("section") else "")
        )
        console.print(header)

        if verbose:
            console.print(Panel(r["text"], expand=False, border_style="dim"))
        else:
            preview = r["text"].replace("\n", " ")[:200]
            console.print(f"  [dim]{preview}…[/dim]")

        console.print()


@click.command()
@click.argument("query_text")
@click.option("--mode", default="dense", type=click.Choice(["dense", "hybrid"]), show_default=True)
@click.option("--top-k", default=5, show_default=True, help="Number of results to retrieve.")
@click.option("--min-score", default=0.0, show_default=True, help="Minimum similarity score (0–1).")
@click.option("--filter", "filters", multiple=True, metavar="KEY=VALUE",
              help="Payload filter(s). Repeatable. E.g. --filter source_file=doc.pdf")
@click.option("--verbose", is_flag=True, default=False, help="Show full chunk text.")
@click.option("--output", default=None, help="Export results to a JSON file.")
@click.option("--collection", default=None, help="Override collection name.")
def main(query_text, mode, top_k, min_score, filters, verbose, output, collection):
    """Query the RAG vector database and retrieve the top-K most relevant chunks."""

    console.print(Panel.fit(
        f"[bold cyan]RAG Query[/bold cyan]\n"
        f"mode={mode}  top_k={top_k}  min_score={min_score}",
        border_style="cyan",
    ))

    # ── Setup ──────────────────────────────────────────────────────────────
    manager = QdrantManager(mode=mode, collection=collection)
    if not manager.collection_exists():
        console.print(f"[red]Collection '{manager.collection}' does not exist. Run ingest first.[/red]")
        sys.exit(1)

    filter_dict = _parse_filters(filters)

    # ── Embed the query ────────────────────────────────────────────────────
    with console.status("[dim]Embedding query...[/dim]"):
        if mode == "dense":
            embedder = DenseEmbedder()
            query_vec = embedder.embed_query(query_text)
            results = manager.search_dense(
                query_vector=query_vec,
                top_k=top_k,
                filter_payload=filter_dict or None,
            )
        else:
            embedder = HybridEmbedder()
            emb = embedder.embed_query(query_text)
            results = manager.search_hybrid(
                query_dense=emb["dense"],
                query_sparse_indices=emb["sparse_indices"],
                query_sparse_values=emb["sparse_values"],
                top_k=top_k,
                filter_payload=filter_dict or None,
            )

    # ── Filter by min score ────────────────────────────────────────────────
    if min_score > 0.0:
        before = len(results)
        results = [r for r in results if r["score"] >= min_score]
        if len(results) < before:
            console.print(f"[dim]Filtered {before - len(results)} result(s) below min_score={min_score}[/dim]")

    # ── Display ────────────────────────────────────────────────────────────
    _display_results(results, verbose=verbose, query=query_text, mode=mode)

    # Summary table
    if results:
        table = Table(title="Score Summary", show_lines=False)
        table.add_column("#", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Source")
        table.add_column("Section")
        table.add_column("Pg", justify="right")
        table.add_column("Chars", justify="right")

        for i, r in enumerate(results, 1):
            table.add_row(
                str(i),
                f"{r['score']:.4f}",
                r["source_file"],
                (r.get("section") or "")[:40],
                str(r.get("page", "-")),
                str(r.get("char_count", "-")),
            )
        console.print(table)

    # ── Export ────────────────────────────────────────────────────────────
    if output:
        out = {
            "query":   query_text,
            "mode":    mode,
            "top_k":   top_k,
            "results": results,
        }
        with open(output, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False, default=str)
        console.print(f"[green]Results exported to '{output}'[/green]")


if __name__ == "__main__":
    main()
