"""Explicit source registry. No discovered URL is ever eligible for autonomous fetch."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator


class Source(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,60}$")
    family: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,60}$")
    url: str
    enabled: bool = False
    terms_reviewed: bool = False
    poll_seconds: int = Field(default=3600, ge=300)
    themes: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def check_url(self):
        u = urlsplit(self.url)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None, 443) or u.fragment:
            raise ValueError("Sources must have clean HTTPS URLs without credentials or fragments")
        return self


class Registry(BaseModel):
    sources: list[Source]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source ids")
        return self

    def get(self, source_id: str) -> Source:
        for source in self.sources:
            if source.id == source_id:
                return source
        raise KeyError(source_id)


def load_registry(path: str | Path | None = None) -> Registry:
    path = Path(path or os.getenv("NARD_SOURCES_FILE", "sources.json"))
    return Registry.model_validate(json.loads(path.read_text(encoding="utf-8")))


def approved(source: Source) -> bool:
    return source.enabled and source.terms_reviewed
