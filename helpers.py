import os
import warnings

import nest_asyncio
from google.auth import default
from IPython.display import Markdown, display
from a2a.types import AgentCard
from dotenv import load_dotenv


def setup_env() -> None:
    """Initializes the environment by loading .env and applying nest_asyncio."""
    load_dotenv(override=True)
    nest_asyncio.apply()

    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)


def authenticate() -> tuple:
    """Authenticates with Google Cloud using credentials from .env.
    
    Returns:
        tuple: (credentials, project_id) for use with AnthropicVertex client.
    
    Raises:
        ValueError: If GOOGLE_APPLICATION_CREDENTIALS is not configured.
    """
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    if not credentials_path:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS not set in .env. "
            "Please set the path to your Google Cloud credentials JSON file."
        )
    
    if not project_id:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT not set in .env. "
            "Please set your Google Cloud project ID."
        )
    
    # If credentials path is set, use it
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    
    # Authenticate with Google Cloud
    credentials, _ = default()
    
    return credentials, project_id


def display_agent_card(agent_card: AgentCard) -> None:
    """Nicely formats and displays an AgentCard."""

    def esc(text: str) -> str:
        """Escapes pipe characters for Markdown table compatibility."""
        return str(text).replace("|", r"\|")

    # --- Part 1: Main Metadata Table ---
    md_parts = [
        "### Agent Card Details",
        "| Property | Value |",
        "| :--- | :--- |",
        f"| **Name** | {esc(agent_card.name)} |",
        f"| **Description** | {esc(agent_card.description)} |",
        f"| **Version** | `{esc(agent_card.version)}` |",
        f"| **URL** | [{esc(agent_card.url)}]({agent_card.url}) |",
        f"| **Protocol Version** | `{esc(agent_card.protocol_version)}` |",
    ]

    # --- Part 2: Skills Table ---
    if agent_card.skills:
        md_parts.extend(
            [
                "\n#### Skills",
                "| Name | Description | Examples |",
                "| :--- | :--- | :--- |",
            ]
        )
        for skill in agent_card.skills:
            examples_str = (
                "<br>".join(f"• {esc(ex)}" for ex in skill.examples)
                if skill.examples
                else "N/A"
            )
            md_parts.append(
                f"| **{esc(skill.name)}** | {esc(skill.description)} | {examples_str} |"
            )

    # Join all parts and display
    display(Markdown("\n".join(md_parts)))