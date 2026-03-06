from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse


def register_protected_docs(app: FastAPI) -> None:
    docs_path = Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml"

    @app.get("/docs/openapi.json", include_in_schema=False)
    async def protected_openapi() -> JSONResponse:
        with docs_path.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file)
        return JSONResponse(content=payload)
