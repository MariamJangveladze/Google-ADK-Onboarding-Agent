"""Cached Google Drive semantic retrieval using Vertex AI embeddings."""

import asyncio
import io
import logging
import math
import time
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from ..config import Settings

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeChunk:
    source: str
    text: str
    embedding: list[float]


class GoogleDriveKnowledgeBase:
    """Refreshes authorized Drive content on a bounded cache interval, not every query."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._chunks: list[KnowledgeChunk] = []
        self._refreshed_at = 0.0
        self._lock = asyncio.Lock()

    @staticmethod
    def _chunk(text: str, size: int = 800, overlap: int = 150) -> list[str]:
        step = size - overlap
        return [text[index : index + size] for index in range(0, len(text), step)]

    @staticmethod
    def _docx_text(content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", namespace):
            value = "".join(
                node.text or "" for node in paragraph.findall(".//w:t", namespace)
            ).strip()
            if value:
                paragraphs.append(value)
        return "\n\n".join(paragraphs)

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def _clients(self):
        try:
            import vertexai
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from vertexai.language_models import TextEmbeddingModel
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install integrations with: uv sync --extra integrations") from exc

        drive_credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_application_credentials,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        vertex_credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_application_credentials,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        vertexai.init(
            project=self.settings.google_cloud_project,
            location=self.settings.google_cloud_location,
            credentials=vertex_credentials,
        )
        return (
            build("drive", "v3", credentials=drive_credentials),
            TextEmbeddingModel.from_pretrained("gemini-embedding-001"),
        )

    @staticmethod
    def _read_file(drive, metadata: dict) -> str:
        mime = metadata["mimeType"]
        file_id = metadata["id"]
        if mime == "application/vnd.google-apps.document":
            content = drive.files().export(fileId=file_id, mimeType="text/plain").execute()
            return content.decode("utf-8", errors="ignore")
        if mime == "text/plain":
            content = drive.files().get_media(fileId=file_id).execute()
            return content.decode("utf-8", errors="ignore")
        if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return GoogleDriveKnowledgeBase._docx_text(
                drive.files().get_media(fileId=file_id).execute()
            )
        return ""

    def _refresh_sync(self) -> None:
        drive, model = self._clients()
        query = f"'{self.settings.drive_folder_id}' in parents and trashed = false"
        response = (
            drive.files()
            .list(
                q=query,
                fields="files(id,name,mimeType)",
                pageSize=100,
            )
            .execute()
        )
        raw_chunks: list[tuple[str, str]] = []
        for metadata in response.get("files", []):
            try:
                for chunk in self._chunk(self._read_file(drive, metadata)):
                    if chunk.strip():
                        raw_chunks.append((metadata["name"], chunk))
            except Exception:
                logger.exception("Failed to ingest Drive file %s", metadata["name"])
        embeddings: list[list[float]] = []
        for index in range(0, len(raw_chunks), 50):
            batch = [text for _, text in raw_chunks[index : index + 50]]
            embeddings.extend(item.values for item in model.get_embeddings(batch))
        self._chunks = [
            KnowledgeChunk(source=source, text=text, embedding=embedding)
            for (source, text), embedding in zip(raw_chunks, embeddings, strict=True)
        ]
        self._refreshed_at = time.monotonic()

    async def _ensure_cache(self) -> None:
        age = time.monotonic() - self._refreshed_at
        if self._chunks and age < self.settings.knowledge_cache_seconds:
            return
        async with self._lock:
            age = time.monotonic() - self._refreshed_at
            if not self._chunks or age >= self.settings.knowledge_cache_seconds:
                await asyncio.to_thread(self._refresh_sync)

    def _search_sync(self, query: str) -> tuple[str, list[str]]:
        _, model = self._clients()
        query_vector = model.get_embeddings([query])[0].values
        ranked = sorted(
            self._chunks,
            key=lambda chunk: self._cosine(query_vector, chunk.embedding),
            reverse=True,
        )[:3]
        context = "\n\n---\n\n".join(
            f"UNTRUSTED_RETRIEVED_DATA [{chunk.source}]\n{chunk.text}" for chunk in ranked
        )
        return context, list(dict.fromkeys(chunk.source for chunk in ranked))

    async def search(self, query: str) -> tuple[str, list[str]]:
        await self._ensure_cache()
        return await asyncio.to_thread(self._search_sync, query)
