import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from backend.core.config import get_settings
from backend.models import DatasetManifest


class FileStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
        return cleaned or "uploaded.parquet"

    async def save_upload(self, upload: UploadFile) -> tuple[str, str, Path]:
        if not upload.filename:
            raise ValueError("Missing upload filename.")
        if not upload.filename.lower().endswith(".parquet"):
            raise ValueError("Only .parquet files are supported.")

        dataset_id = uuid.uuid4().hex
        safe_name = self._safe_filename(upload.filename)
        stored_path = self.settings.upload_dir / f"{dataset_id}_{safe_name}"

        with stored_path.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                handle.write(chunk)

        return dataset_id, safe_name, stored_path

    def manifest_path(self, dataset_id: str) -> Path:
        return self.settings.dataset_store_dir / f"{dataset_id}.json"

    def save_manifest(self, manifest: DatasetManifest) -> None:
        payload = manifest.model_dump(mode="json")
        self.manifest_path(manifest.dataset_id).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def load_manifest(self, dataset_id: str) -> DatasetManifest:
        path = self.manifest_path(dataset_id)
        if not path.exists():
            raise FileNotFoundError(dataset_id)
        return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def list_manifests(self) -> list[DatasetManifest]:
        manifests: list[DatasetManifest] = []
        for path in sorted(self.settings.dataset_store_dir.glob("*.json")):
            manifests.append(DatasetManifest.model_validate_json(path.read_text(encoding="utf-8")))
        return sorted(manifests, key=lambda item: item.uploaded_at, reverse=True)

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def delete_dataset(self, dataset_id: str) -> None:
        path = self.manifest_path(dataset_id)
        if not path.exists():
            raise FileNotFoundError(dataset_id)

        manifest = DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))
        stored = Path(manifest.stored_path)
        if stored.exists():
            try:
                stored.unlink()
            except Exception:
                pass

        try:
            path.unlink()
        except Exception:
            pass

