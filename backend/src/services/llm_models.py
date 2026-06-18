from sqlite3 import Row
from typing import Any

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.llm import (
    LLMModelConnectionTest,
    LLMModelCreate,
    LLMModelOut,
    LLMModelRecord,
    LLMModelUpdate,
)


MODEL_COLUMNS = {
    "name",
    "provider",
    "base_url",
    "api_key",
    "model_name",
    "temperature",
    "max_context_tokens",
}


class LLMModelService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def create(self, model: LLMModelCreate) -> LLMModelOut:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO llm_models (
                    name, provider, base_url, api_key, model_name,
                    temperature, max_context_tokens, is_active
                )
                VALUES (
                    :name, :provider, :base_url, :api_key, :model_name,
                    :temperature, :max_context_tokens, 0
                )
                """,
                model.model_dump(),
            )
            row = conn.execute("SELECT * FROM llm_models WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_out(row)

    def list(self) -> list[LLMModelOut]:
        with self.store.connect() as conn:
            rows = conn.execute("SELECT * FROM llm_models ORDER BY id").fetchall()
        return [self._map_out(row) for row in rows]

    def get(self, model_id: int) -> LLMModelOut:
        return self._map_out(self._get_row(model_id))

    def get_active_record(self) -> LLMModelRecord | None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM llm_models WHERE is_active = 1 ORDER BY id LIMIT 1").fetchone()
        return self._map_record(row) if row else None

    def get_record(self, model_id: int) -> LLMModelRecord:
        return self._map_record(self._get_row(model_id))

    def build_connection_test_record(self, model: LLMModelConnectionTest) -> LLMModelRecord:
        api_key = (model.api_key or "").strip()
        if not api_key and model.existing_model_id:
            api_key = self.get_record(model.existing_model_id).api_key
        if not api_key:
            raise api_error(400, "model_api_key_required", "API key is required for connectivity test.")
        return LLMModelRecord(
            id=model.existing_model_id or 0,
            name=model.name,
            provider=model.provider,
            base_url=model.base_url,
            api_key_masked=self._mask_api_key(api_key),
            api_key=api_key,
            model_name=model.model_name,
            temperature=model.temperature,
            max_context_tokens=model.max_context_tokens,
            is_active=False,
            created_at="",
            updated_at="",
        )

    def update(self, model_id: int, update: LLMModelUpdate) -> LLMModelOut:
        self._get_row(model_id)
        values = update.model_dump(exclude_unset=True)
        for key in values:
            if key not in MODEL_COLUMNS:
                raise api_error(400, "validation_error", f"Unsupported model field: {key}.")

        if values:
            assignments = ", ".join(f"{column} = :{column}" for column in values)
            values["id"] = model_id
            with self.store.connect() as conn:
                conn.execute(
                    f"""
                    UPDATE llm_models
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """,
                    values,
                )
        return self.get(model_id)

    def activate(self, model_id: int) -> LLMModelOut:
        self._get_row(model_id)
        with self.store.connect() as conn:
            conn.execute("UPDATE llm_models SET is_active = 0")
            conn.execute(
                """
                UPDATE llm_models
                SET is_active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (model_id,),
            )
        return self.get(model_id)

    def delete(self, model_id: int) -> None:
        with self.store.connect() as conn:
            result = conn.execute("DELETE FROM llm_models WHERE id = ?", (model_id,))
        if result.rowcount == 0:
            raise api_error(404, "model_not_found", "Model configuration not found.")

    def _get_row(self, model_id: int) -> Row:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM llm_models WHERE id = ?", (model_id,)).fetchone()
        if row is None:
            raise api_error(404, "model_not_found", "Model configuration not found.")
        return row

    def _map_out(self, row: Row) -> LLMModelOut:
        return LLMModelOut(
            id=row["id"],
            name=row["name"],
            provider=row["provider"],
            base_url=row["base_url"],
            api_key_masked=self._mask_api_key(row["api_key"]),
            model_name=row["model_name"],
            temperature=row["temperature"],
            max_context_tokens=row["max_context_tokens"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _map_record(self, row: Row) -> LLMModelRecord:
        values: dict[str, Any] = self._map_out(row).model_dump()
        values["api_key"] = row["api_key"]
        return LLMModelRecord(**values)

    def _mask_api_key(self, api_key: str) -> str:
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}...{api_key[-4:]}"
