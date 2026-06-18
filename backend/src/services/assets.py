from sqlite3 import Row

from backend.src.db.sqlite import SQLiteStore, encode_json
from backend.src.schemas.assets import ImageRequest, ImageResponse


class ImageService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def request_image(self, request: ImageRequest) -> ImageResponse:
        prompt = f"Create a {request.kind} image: {request.description}"
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO generated_assets (
                    kind, subject_id, prompt, status, result_uri, metadata_json
                )
                VALUES (
                    :kind, :subject_id, :prompt, :status, :result_uri, :metadata_json
                )
                """,
                {
                    "kind": request.kind,
                    "subject_id": request.subject_id,
                    "prompt": prompt,
                    "status": "not_connected",
                    "result_uri": None,
                    "metadata_json": encode_json({}),
                },
            )
            row = conn.execute("SELECT * FROM generated_assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_row(row)

    def _map_row(self, row: Row) -> ImageResponse:
        return ImageResponse(
            id=row["id"],
            kind=row["kind"],
            subject_id=row["subject_id"],
            prompt=row["prompt"],
            status=row["status"],
            result_uri=row["result_uri"],
        )
