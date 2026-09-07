import logging
from typing import List, Dict, Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class NotionService:
    """Service to fetch and parse pages and databases from Notion API."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.NOTION_API_KEY
        self.default_database_ids = settings.NOTION_DATABASE_IDS
        self._client = None

    def _get_client(self):
        """Lazy load Notion client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Kredensial Notion API Key belum diset. Silakan konfigurasi NOTION_API_KEY di .env")
            try:
                from notion_client import Client
                self._client = Client(auth=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Notion client: {e}")
                raise e
        return self._client

    def _extract_plain_text(self, rich_text_array: List[Dict[str, Any]]) -> str:
        """Extract concatenated plain text from Notion rich text objects."""
        if not rich_text_array:
            return ""
        return "".join([t.get("plain_text", "") for t in rich_text_array])

    def _parse_blocks(self, block_id: str) -> str:
        """Recursively fetch and parse child blocks of a Notion page/block into Markdown."""
        client = self._get_client()
        content_lines = []

        has_more = True
        start_cursor = None

        while has_more:
            response = client.blocks.children.list(
                block_id=block_id,
                start_cursor=start_cursor,
                page_size=100
            )
            results = response.get("results", [])

            for block in results:
                block_type = block.get("type", "")
                block_data = block.get(block_type, {})
                rich_text = block_data.get("rich_text", [])
                text = self._extract_plain_text(rich_text)

                if block_type == "paragraph":
                    content_lines.append(text)
                elif block_type == "heading_1":
                    content_lines.append(f"# {text}")
                elif block_type == "heading_2":
                    content_lines.append(f"## {text}")
                elif block_type == "heading_3":
                    content_lines.append(f"### {text}")
                elif block_type in ("bulleted_list_item", "numbered_list_item"):
                    content_lines.append(f"- {text}")
                elif block_type == "to_do":
                    checked = block_data.get("checked", False)
                    checkbox = "[x]" if checked else "[ ]"
                    content_lines.append(f"- {checkbox} {text}")
                elif block_type == "code":
                    language = block_data.get("language", "")
                    content_lines.append(f"```{language}\n{text}\n```")
                elif block_type == "quote":
                    content_lines.append(f"> {text}")
                elif block_type == "callout":
                    content_lines.append(f"> 💡 {text}")
                elif text:
                    content_lines.append(text)

                # Recursively parse nested blocks
                if block.get("has_children", False):
                    child_text = self._parse_blocks(block.get("id"))
                    if child_text:
                        content_lines.append(child_text)

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        return "\n\n".join([line for line in content_lines if line])

    def fetch_page_by_id(self, page_id: str, space: str = "GENERAL") -> Dict[str, Any]:
        """Fetch and extract a single Notion page."""
        client = self._get_client()
        page = client.pages.retrieve(page_id=page_id)
        
        # Extract title from properties
        title = "Untitled"
        properties = page.get("properties", {})
        for prop in properties.values():
            if prop.get("type") == "title":
                title = self._extract_plain_text(prop.get("title", [])) or "Untitled"
                break

        body_content = self._parse_blocks(page_id)
        page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

        return {
            "id": f"notion_{page_id}",
            "title": title,
            "content": body_content,
            "source": "notion",
            "space": space,
            "url": page_url,
            "metadata": {
                "page_id": page_id,
                "space": space,
                "created_time": page.get("created_time"),
                "last_edited_time": page.get("last_edited_time"),
                "type": "notion_page"
            }
        }

    def fetch_database_pages(self, database_id: str, space: str = "GENERAL", limit: int = 50) -> List[Dict[str, Any]]:
        """Query a Notion database and fetch text for all pages."""
        client = self._get_client()
        logger.info(f"Querying Notion database '{database_id}' with limit {limit}...")

        response = client.databases.query(
            database_id=database_id,
            page_size=min(limit, 100)
        )

        pages = response.get("results", [])
        documents = []

        # Auto determine space based on db name/id if applicable
        db_space = "OPS" if "sop" in database_id.lower() else ("ENG" if "tech" in database_id.lower() else space)

        for page in pages:
            page_id = page.get("id")
            try:
                doc = self.fetch_page_by_id(page_id, space=db_space)
                if doc["content"]:
                    documents.append(doc)
            except Exception as e:
                logger.warning(f"Failed to fetch Notion page {page_id}: {e}")

        logger.info(f"Successfully processed {len(documents)} pages from Notion database '{database_id}'.")
        return documents

    def fetch_all_default_databases(self, limit_per_db: int = 50) -> List[Dict[str, Any]]:
        """Fetch all pages across configured default Notion databases."""
        all_docs = []
        for db_id in self.default_database_ids:
            try:
                docs = self.fetch_database_pages(db_id, limit=limit_per_db)
                all_docs.extend(docs)
            except Exception as e:
                logger.warning(f"Error syncing Notion database '{db_id}': {e}")
        return all_docs


def get_notion_service() -> NotionService:
    """Dependency injector for NotionService."""
    return NotionService()
