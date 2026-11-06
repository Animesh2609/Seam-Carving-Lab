"""User-owned image history in Supabase Storage and PostgREST.

No service-role key is used: all operations use the signed-in user's JWT.
PostgreSQL and Storage RLS policies in supabase_history_setup.sql enforce isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote
from uuid import UUID, uuid4

import requests


class HistoryError(Exception):
    pass


@dataclass(frozen=True)
class HistoryConfig:
    url: str
    public_key: str
    bucket: str = "seam-images"


class ImageHistory:
    def __init__(self, config: HistoryConfig, transport=None):
        self.config = config
        self.transport = transport or requests

    def _call(self, method, path, session, *, body=None, json_data=None, extra_headers=None, timeout=35):
        if not self.config.url or not self.config.public_key:
            raise HistoryError("Supabase settings are missing.")
        if not session or not session.get("id") or not session.get("access_token"):
            raise HistoryError("Sign in to save or view your image history.")
        headers = {"apikey": self.config.public_key,
                   "Authorization": "Bearer " + session["access_token"]}
        headers.update(extra_headers or {})
        try:
            response = self.transport.request(method,
                self.config.url.rstrip("/") + path, headers=headers,
                data=body, json=json_data, timeout=timeout)
        except requests.RequestException as exc:
            raise HistoryError("Could not reach Supabase image storage.") from exc
        if response.status_code >= 400:
            try:
                error = response.json()
                msg = error.get("message") or error.get("error") or error.get("msg") or ""
            except (ValueError, AttributeError):
                msg = ""
            raise HistoryError(f"Supabase returned HTTP {response.status_code}: {str(msg)[:220]}. "
                               "Check the database table, private bucket and RLS policies.")
        return response

    def _object_path(self, session, file_path):
        # Defensive input validation in addition to Supabase RLS.
        account_id = str(UUID(session["id"]))
        if not file_path.startswith(account_id + "/") or ".." in file_path:
            raise HistoryError("Image path does not belong to this account.")
        return f"/storage/v1/object/{self.config.bucket}/{quote(file_path, safe='/')}"

    def upload(self, session, file_path, png_bytes):
        if not isinstance(png_bytes, bytes) or len(png_bytes) > 8 * 1024 * 1024:
            raise HistoryError("Only PNG images up to 8 MB may be saved to the dashboard.")
        return self._call("POST", self._object_path(session, file_path), session,
                          body=png_bytes,
                          extra_headers={"Content-Type": "image/png", "x-upsert": "false"})

    def download(self, session, file_path):
        return self._call("GET", self._object_path(session, file_path).replace(
            "/storage/v1/object/", "/storage/v1/object/authenticated/", 1), session).content

    def delete_image(self, session, file_path):
        self._call("DELETE", self._object_path(session, file_path), session)

    def save(self, session, source_png, output_png, operation, source_name,
             original_dimensions, output_dimensions, details=None):
        if operation not in ("Seam carving", "Object removal", "Multi-size variant"):
            raise HistoryError("Unsupported processing operation.")
        run_id = uuid4().hex
        prefix = f"{session['id']}/{run_id}"
        source_path = prefix + "_source.png"
        output_path = prefix + "_output.png"
        uploaded = []
        try:
            self.upload(session, source_path, source_png)
            uploaded.append(source_path)
            self.upload(session, output_path, output_png)
            uploaded.append(output_path)
            row = {"user_id": session["id"], "operation": operation,
                   "input_path": source_path, "output_path": output_path,
                   "source_name": str(source_name or "image")[:150],
                   "input_width": int(original_dimensions[0]), "input_height": int(original_dimensions[1]),
                   "output_width": int(output_dimensions[0]), "output_height": int(output_dimensions[1]),
                   "details": details or {}}
            reply = self._call("POST", "/rest/v1/image_history", session,
                               json_data=row,
                               extra_headers={"Content-Type": "application/json",
                                              "Prefer": "return=representation"})
            result = reply.json()
            return result[0] if result else row
        except Exception:
            for path in uploaded:
                try:
                    self.delete_image(session, path)
                except HistoryError:
                    pass
            raise

    def list(self, session, limit=40):
        limit = min(max(1, int(limit)), 100)
        reply = self._call("GET", "/rest/v1/image_history"
                           f"?select=*&user_id=eq.{quote(session['id'])}"
                           f"&order=created_at.desc&limit={limit}", session)
        return reply.json()

    def delete(self, session, row):
        # RLS verifies the owner independently of these checks.
        uid = str(UUID(session["id"]))
        if row.get("user_id") != uid:
            raise HistoryError("Cannot delete another user's image history.")
        row_id = str(UUID(row["id"]))
        self._call("DELETE", "/rest/v1/image_history?id=eq." + quote(row_id), session)
        # On temporary storage failure the record is deleted but orphans may remain;
        # notify the operator through logging rather than showing somebody's images.
        for path in (row["input_path"], row["output_path"]):
            self.delete_image(session, path)
