import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import markdownify
from app.config import get_settings

logger = logging.getLogger(__name__)


class ConfluenceService:
    """Service to fetch and parse pages from Atlassian Confluence."""

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        settings = get_settings()
        self.url = url or settings.CONFLUENCE_URL
        self.username = username or settings.CONFLUENCE_USERNAME
        self.api_token = api_token or settings.CONFLUENCE_API_TOKEN
        self.default_spaces = settings.CONFLUENCE_DEFAULT_SPACES
        self._confluence = None

    def _get_client(self):
        """Lazy load Atlassian Confluence client."""
        if self._confluence is None:
            if not self.url or not self.username or not self.api_token:
                raise ValueError(
                    "Kredensial Confluence belum lengkap. "
                    "Pastikan CONFLUENCE_URL, CONFLUENCE_USERNAME, dan CONFLUENCE_API_TOKEN telah diset di .env"
                )
            try:
                from atlassian import Confluence
                self._confluence = Confluence(
                    url=self.url,
                    username=self.username,
                    password=self.api_token,
                    cloud=True
                )
            except Exception as e:
                logger.error(f"Failed to initialize Confluence client: {e}")
                raise e
        return self._confluence

    def _clean_html_to_markdown(self, html_content: str) -> str:
        """Convert HTML storage format from Confluence to readable Markdown/text."""
        if not html_content:
            return ""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            cleaned_html = str(soup)
            markdown_text = markdownify.markdownify(cleaned_html, heading_style="ATX")
            return markdown_text.strip()
        except Exception as e:
            logger.warning(f"HTML conversion error: {e}. Falling back to text.")
            return BeautifulSoup(html_content, "html.parser").get_text(separator="\n").strip()

    def fetch_page_by_id(self, page_id: str) -> Dict[str, Any]:
        """Fetch a single Confluence page by ID."""
        client = self._get_client()
        page = client.get_page_by_id(page_id, expand="body.storage,version,space")
        
        title = page.get("title", "Untitled")
        html_body = page.get("body", {}).get("storage", {}).get("value", "")
        clean_text = self._clean_html_to_markdown(html_body)
        space_key = page.get("space", {}).get("key", "GENERAL")
        web_link = f"{self.url.rstrip('/')}/wiki/spaces/{space_key}/pages/{page_id}" if self.url else None

        return {
            "id": f"confluence_{page_id}",
            "title": title,
            "content": clean_text,
            "source": "confluence",
            "space": space_key,
            "url": web_link,
            "metadata": {
                "page_id": page_id,
                "space": space_key,
                "version": page.get("version", {}).get("number", 1),
                "type": "confluence_page"
            }
        }

    def fetch_space_pages(self, space_key: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch all pages in a given Confluence space."""
        client = self._get_client()
        logger.info(f"Fetching Confluence pages for space '{space_key}' with limit {limit}...")
        
        pages = client.get_all_pages_from_space(
            space=space_key,
            start=0,
            limit=limit,
            status="current",
            expand="body.storage,version,space"
        )

        documents = []
        for page in pages:
            page_id = str(page.get("id"))
            title = page.get("title", "Untitled")
            html_body = page.get("body", {}).get("storage", {}).get("value", "")
            clean_text = self._clean_html_to_markdown(html_body)
            web_link = f"{self.url.rstrip('/')}/wiki/spaces/{space_key}/pages/{page_id}" if self.url else None

            if clean_text:
                documents.append({
                    "id": f"confluence_{page_id}",
                    "title": title,
                    "content": clean_text,
                    "source": "confluence",
                    "space": space_key,
                    "url": web_link,
                    "metadata": {
                        "page_id": page_id,
                        "space": space_key,
                        "version": page.get("version", {}).get("number", 1),
                        "type": "confluence_page"
                    }
                })

        logger.info(f"Retrieved {len(documents)} valid pages from Confluence space '{space_key}'.")
        return documents

    def fetch_all_default_spaces(self, limit_per_space: int = 50) -> List[Dict[str, Any]]:
        """Fetch all pages across configured default spaces (e.g. ENG, HR, OPS)."""
        all_docs = []
        for space in self.default_spaces:
            try:
                docs = self.fetch_space_pages(space, limit=limit_per_space)
                all_docs.extend(docs)
            except Exception as e:
                logger.warning(f"Error syncing Confluence space '{space}': {e}")
        return all_docs


def get_confluence_service() -> ConfluenceService:
    """Dependency injector for ConfluenceService."""
    return ConfluenceService()
