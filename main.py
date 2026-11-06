
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("NOTION_PAGE_ID")

API_URL = "https://api.notion.com/v1"
LONDON = ZoneInfo("Europe/London")

# Exact paragraph IDs from your dashboard
BLOCKS = {
    "subtitles": {
        "text": "8947eaa8-8b64-4ca4-b3d9-48cbc6d633cc"
    },
    "philosophers": {
        "text": "4ef01803-dd52-4c79-b892-4533cf0fe1c5",
        "attribution": "26f7c9db-5d3d-4128-932e-8ffa38c6a0f6"
    },
    "anime": {
        "text": "884995d5-7b96-4817-a999-606cab50e100",
        "attribution": "d400a478-6073-4f6c-ba38-a7fff8e53a3f"
    },
    "music": {
        "text": "a39a4641-f918-440f-b8f0-ceec6070594d",
        "attribution": "61212896-63d0-4c09-b04f-dc061cecd016"
    }
}


def get_headers():
    if not TOKEN or not PAGE_ID:
        raise ValueError(
            "Missing NOTION_TOKEN or NOTION_PAGE_ID in environment"
        )

    return {
        "Authorization": f"Bearer {TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }


def notion_request(method, endpoint, headers, payload=None):
    response = requests.request(
        method,
        f"{API_URL}{endpoint}",
        headers=headers,
        json=payload,
        timeout=20
    )

    response.raise_for_status()
    return response.json()


def load_quotes():
    path = Path(__file__).with_name("quotes.json")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    for category in BLOCKS:
        entries = data.get(category)

        if not isinstance(entries, list) or not entries:
            raise ValueError(
                f"Category '{category}' needs at least one quote"
            )

        for entry in entries:
            if not isinstance(entry.get("text"), str):
                raise ValueError(
                    f"Invalid quote in category '{category}'"
                )

            if "attribution" in BLOCKS[category]:
                if not isinstance(entry.get("attribution"), str):
                    raise ValueError(
                        f"Missing attribution in '{category}'"
                    )

    return data


def choose_quote(entries, today):
    # Date-based rotation, no persistent state required.
    # Each category cycles through its own list.
    index = today.toordinal() % len(entries)
    return entries[index]


def update_paragraph(block_id, new_text, headers, dry_run=False):
    block = notion_request(
        "GET",
        f"/blocks/{block_id}",
        headers
    )

    if block["type"] != "paragraph":
        raise ValueError(f"Block {block_id} is not a paragraph")

    rich_text = block["paragraph"]["rich_text"]

    if len(rich_text) != 1 or rich_text[0]["type"] != "text":
        raise ValueError(
            f"Unexpected text structure in block {block_id}. "
            "Skipping to protect formatting."
        )

    original = rich_text[0]
    old_text = original["text"]["content"]

    if old_text == new_text:
        print(f"Unchanged: {old_text}")
        return

    # Copy the existing text object and formatting.
    new_item = {
        "type": "text",
        "text": {
            "content": new_text
        },
        "annotations": original["annotations"]
    }

    # Preserve an existing text link if one exists.
    if original["text"].get("link"):
        new_item["text"]["link"] = original["text"]["link"]

    payload = {
        "paragraph": {
            "rich_text": [new_item]
        }
    }

    if dry_run:
        print(f"[PREVIEW] {old_text} -> {new_text}")
        return

    notion_request(
        "PATCH",
        f"/blocks/{block_id}",
        headers,
        payload
    )

    print(f"Updated: {new_text}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating Notion"
    )
    args = parser.parse_args()

    headers = get_headers()
    quotes = load_quotes()
    today = datetime.now(LONDON).date()

    # Confirm the integration can access the dashboard.
    notion_request(
        "GET",
        f"/pages/{PAGE_ID}",
        headers
    )

    print(f"Connected to Notion | UK date: {today}")

    if args.dry_run:
        print("DRY RUN: No changes will be made.")

    for category, block_ids in BLOCKS.items():
        selected = choose_quote(quotes[category], today)

        print(f"\n--- {category.upper()} ---")

        update_paragraph(
            block_ids["text"],
            selected["text"],
            headers,
            args.dry_run
        )

        if "attribution" in block_ids:
            update_paragraph(
                block_ids["attribution"],
                selected["attribution"],
                headers,
                args.dry_run
            )

    print("\nFinished!")


if __name__ == "__main__":
    main()
