"""Pagination helpers matching the API contract in spec 04."""

from typing import Any

from fastapi import Query
from pydantic import BaseModel, Field


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


def page_params(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


def page_of(items: list[Any], *, total: int, params: PageParams) -> dict[str, Any]:
    return {
        "items": items,
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
    }
