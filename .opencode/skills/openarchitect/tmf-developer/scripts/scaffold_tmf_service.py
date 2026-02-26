#!/usr/bin/env python3
"""Generate a FastAPI + SQLite TMF service scaffold from OpenAPI."""

from __future__ import annotations

import argparse
import json
import pprint
import re
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Tuple

import yaml

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
CRUD_KEYS = ("list", "create", "get", "patch", "put", "delete")


def _tmf_number_from_text(*parts: str) -> str | None:
    for part in parts:
        match = re.search(r"TMF(\d+)", part or "", flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _sanitize_module_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip())
    cleaned = cleaned.strip("_").lower()
    return cleaned or "tmf_service"


def _collect_resources(paths: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str], bool]:
    resource_map: Dict[str, Dict[str, Any]] = {}
    skipped_paths: List[str] = []
    has_hub = False

    for raw_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        if raw_path.startswith("/hub"):
            has_hub = True
            continue
        if not raw_path.startswith("/"):
            skipped_paths.append(raw_path)
            continue

        parts = [p for p in raw_path.split("/") if p]
        if not parts or parts[0].startswith("{"):
            skipped_paths.append(raw_path)
            continue

        methods = [m for m in HTTP_METHODS if isinstance(path_item.get(m), dict)]
        if not methods:
            continue

        resource_name = parts[0]
        entry = resource_map.setdefault(
            resource_name,
            {
                "name": resource_name,
                "collection_methods": set(),
                "item_methods": set(),
            },
        )

        if len(parts) == 1:
            entry["collection_methods"].update(methods)
        elif len(parts) >= 2 and parts[1].startswith("{"):
            entry["item_methods"].update(methods)
        else:
            skipped_paths.append(raw_path)

    resources: List[Dict[str, Any]] = []
    for _, value in sorted(resource_map.items(), key=lambda kv: kv[0]):
        collection_methods = sorted(value["collection_methods"])
        item_methods = sorted(value["item_methods"])
        supports = {
            "list": "get" in collection_methods,
            "create": "post" in collection_methods,
            "get": "get" in item_methods,
            "patch": "patch" in item_methods,
            "put": "put" in item_methods,
            "delete": "delete" in item_methods,
        }
        resources.append(
            {
                "name": value["name"],
                "collection_methods": collection_methods,
                "item_methods": item_methods,
                "supports": supports,
            }
        )

    return resources, sorted(set(skipped_paths)), has_hub


def _load_design_package(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Design package not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Design package must be a JSON object: {path}")
    apis = data.get("apis")
    if not isinstance(apis, list) or not apis:
        raise SystemExit(f"Design package missing non-empty 'apis' list: {path}")
    return data


def _pick_design_api_entry(
    design: Dict[str, Any], spec_path: Path, tmf_number: str, design_api: str | None
) -> Dict[str, Any]:
    apis = design.get("apis")
    if not isinstance(apis, list):
        raise SystemExit("Invalid design package: 'apis' must be a list")

    matches: List[Dict[str, Any]] = []
    if design_api:
        needle = design_api.strip().lower()
        for api in apis:
            if not isinstance(api, dict):
                continue
            if str(api.get("api_id", "")).lower() == needle:
                matches.append(api)
                continue
            if str(api.get("tmf_number", "")).lower() == needle.replace("tmf", ""):
                matches.append(api)
                continue
            if str(api.get("title", "")).lower() == needle:
                matches.append(api)
        if not matches:
            raise SystemExit(f"No API match in design package for --design-api '{design_api}'")
    else:
        spec_name = spec_path.name.lower()
        for api in apis:
            if not isinstance(api, dict):
                continue
            api_spec = str(api.get("spec_path", "")).lower()
            api_tmf = str(api.get("tmf_number", ""))
            if api_spec.endswith(spec_name) or (tmf_number and api_tmf == tmf_number):
                matches.append(api)

    if not matches:
        raise SystemExit(
            "Could not auto-select API from design package. Provide --design-api <api_id>."
        )
    if len(matches) > 1:
        ids = ", ".join(sorted(str(item.get("api_id", "?")) for item in matches))
        raise SystemExit(f"Multiple API matches in design package ({ids}); specify --design-api explicitly.")
    return matches[0]


def _apply_design_resource_metadata(
    resources: List[Dict[str, Any]],
    design_api_entry: Dict[str, Any],
    shared_entities: List[Dict[str, Any]],
) -> None:
    design_resources = design_api_entry.get("resources")
    if not isinstance(design_resources, list):
        design_resources = []
    design_by_name = {
        str(item.get("name")): item for item in design_resources if isinstance(item, dict) and item.get("name")
    }
    shared_by_resource: Dict[str, str] = {}
    for item in shared_entities:
        if not isinstance(item, dict):
            continue
        canonical_entity = item.get("canonical_entity")
        resources_list = item.get("resources")
        if not canonical_entity or not isinstance(resources_list, list):
            continue
        for resource_name in resources_list:
            shared_by_resource[str(resource_name)] = str(canonical_entity)

    for resource in resources:
        name = resource.get("name")
        if not isinstance(name, str):
            continue
        match = design_by_name.get(name)
        if isinstance(match, dict):
            supports = match.get("supports")
            if isinstance(supports, dict):
                resource["supports"] = {key: bool(supports.get(key)) for key in CRUD_KEYS}
            canonical = match.get("canonical_entity")
            if canonical:
                resource["canonical_entity"] = str(canonical)
        if name in shared_by_resource and "canonical_entity" not in resource:
            resource["canonical_entity"] = shared_by_resource[name]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_database_py(default_database_url: str) -> str:
    return Template(
        '''"""Database configuration for generated TMF service."""

from __future__ import annotations

import os
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL = os.getenv("DATABASE_URL", "$DATABASE_URL")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
'''
    ).substitute(DATABASE_URL=default_database_url)


def _build_models_py() -> str:
    return '''"""Data models for generated TMF service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class ResourceItem(SQLModel, table=True):
    __tablename__ = "resource_items"
    __table_args__ = (UniqueConstraint("resource_type", "external_id", name="uq_resource_external_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    resource_type: str = Field(index=True, nullable=False)
    external_id: str = Field(index=True, nullable=False)
    payload: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class HubSubscription(SQLModel, table=True):
    __tablename__ = "hub_subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    callback: str = Field(index=True, nullable=False)
    query: Optional[str] = Field(default=None)
    event_type: Optional[str] = Field(default=None)
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
'''


def _build_crud_py() -> str:
    return '''"""CRUD operations for generated TMF service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlmodel import Session, select

from .models import HubSubscription, ResourceItem


def list_items(session: Session, resource_type: str, limit: int, offset: int) -> List[ResourceItem]:
    stmt = (
        select(ResourceItem)
        .where(ResourceItem.resource_type == resource_type)
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(stmt))


def get_item(session: Session, resource_type: str, external_id: str) -> Optional[ResourceItem]:
    stmt = select(ResourceItem).where(
        ResourceItem.resource_type == resource_type,
        ResourceItem.external_id == external_id,
    )
    return session.exec(stmt).first()


def create_item(session: Session, resource_type: str, payload: Dict[str, Any]) -> ResourceItem:
    body = dict(payload or {})
    external_id = str(body.get("id") or uuid4())
    body["id"] = external_id
    existing = get_item(session, resource_type, external_id)
    if existing is not None:
        raise ValueError(f"{resource_type} with id '{external_id}' already exists")

    item = ResourceItem(resource_type=resource_type, external_id=external_id, payload=body)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update_item(
    session: Session,
    resource_type: str,
    external_id: str,
    payload: Dict[str, Any],
    *,
    replace: bool = False,
) -> ResourceItem:
    item = get_item(session, resource_type, external_id)
    if item is None:
        raise KeyError(f"{resource_type} with id '{external_id}' not found")

    body = dict(payload or {})
    if replace:
        merged = body
    else:
        current = dict(item.payload or {})
        merged = {**current, **body}
    merged["id"] = external_id
    item.payload = merged
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_item(session: Session, resource_type: str, external_id: str) -> bool:
    item = get_item(session, resource_type, external_id)
    if item is None:
        return False
    session.delete(item)
    session.commit()
    return True


def list_subscriptions(session: Session) -> List[HubSubscription]:
    return list(session.exec(select(HubSubscription)))


def create_subscription(
    session: Session, callback: str, query: Optional[str], event_type: Optional[str], payload: Dict[str, Any]
) -> HubSubscription:
    item = HubSubscription(callback=callback, query=query, event_type=event_type, payload=dict(payload or {}))
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_subscription(session: Session, subscription_id: int) -> bool:
    item = session.get(HubSubscription, subscription_id)
    if item is None:
        return False
    session.delete(item)
    session.commit()
    return True
'''


def _build_schemas_py() -> str:
    return '''"""Request and response schemas for generated TMF service."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ResourceBody(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class DeleteResponse(BaseModel):
    status: str
    id: str


class HubSubscriptionIn(BaseModel):
    callback: str
    query: Optional[str] = None
    eventType: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
'''


def _build_main_py(
    title: str,
    version: str,
    tmf_number: str,
    resources: List[Dict[str, Any]],
    skipped_paths: List[str],
    has_hub: bool,
) -> str:
    resource_config_literal = pprint.pformat(resources, width=100, sort_dicts=True)
    skipped_paths_literal = pprint.pformat(skipped_paths, width=100, sort_dicts=True)

    template = Template(
        '''"""Generated FastAPI application for TMF service."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from .crud import (
    create_item,
    create_subscription,
    delete_item,
    delete_subscription,
    get_item,
    list_items,
    list_subscriptions,
    update_item,
)
from .database import get_session, init_db
from .schemas import HubSubscriptionIn, ResourceBody


APP_TITLE = "$APP_TITLE"
APP_VERSION = "$APP_VERSION"
TMF_NUMBER = "$TMF_NUMBER"
RESOURCE_CONFIG = $RESOURCE_CONFIG
SKIPPED_PATHS = $SKIPPED_PATHS
HAS_HUB = $HAS_HUB

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="Generated TMF service backed by SQLite",
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": APP_TITLE,
        "tmf_number": TMF_NUMBER,
        "resource_count": len(RESOURCE_CONFIG),
    }


@app.get("/_meta")
def metadata() -> Dict[str, Any]:
    return {
        "title": APP_TITLE,
        "version": APP_VERSION,
        "tmf_number": TMF_NUMBER,
        "resources": RESOURCE_CONFIG,
        "skipped_paths": SKIPPED_PATHS,
        "has_hub": HAS_HUB,
    }


def register_resource_router(resource_name: str, supports: Dict[str, bool]) -> None:
    router = APIRouter(prefix=f"/{resource_name}", tags=[resource_name])

    if supports.get("list"):
        @router.get("")
        def _list_items(
            limit: int = Query(default=100, ge=1, le=1000),
            offset: int = Query(default=0, ge=0),
            session: Session = Depends(get_session),
        ) -> List[Dict[str, Any]]:
            return [item.payload for item in list_items(session, resource_name, limit, offset)]

    if supports.get("create"):
        @router.post("")
        def _create_item(
            body: ResourceBody,
            session: Session = Depends(get_session),
        ) -> Dict[str, Any]:
            try:
                item = create_item(session, resource_name, body.payload)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            return item.payload

    if supports.get("get"):
        @router.get("/{item_id}")
        def _get_item(item_id: str, session: Session = Depends(get_session)) -> Dict[str, Any]:
            item = get_item(session, resource_name, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail=f"{resource_name} '{item_id}' not found")
            return item.payload

    if supports.get("patch"):
        @router.patch("/{item_id}")
        def _patch_item(
            item_id: str,
            body: ResourceBody,
            session: Session = Depends(get_session),
        ) -> Dict[str, Any]:
            try:
                item = update_item(session, resource_name, item_id, body.payload, replace=False)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return item.payload

    if supports.get("put"):
        @router.put("/{item_id}")
        def _put_item(
            item_id: str,
            body: ResourceBody,
            session: Session = Depends(get_session),
        ) -> Dict[str, Any]:
            try:
                item = update_item(session, resource_name, item_id, body.payload, replace=True)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return item.payload

    if supports.get("delete"):
        @router.delete("/{item_id}")
        def _delete_item(item_id: str, session: Session = Depends(get_session)) -> Dict[str, Any]:
            deleted = delete_item(session, resource_name, item_id)
            if not deleted:
                raise HTTPException(status_code=404, detail=f"{resource_name} '{item_id}' not found")
            return {"status": "deleted", "id": item_id}

    app.include_router(router)


for config in RESOURCE_CONFIG:
    register_resource_router(config["name"], config["supports"])


if HAS_HUB:
    hub_router = APIRouter(prefix="/hub", tags=["hub"])

    @hub_router.get("")
    def _list_subscriptions(session: Session = Depends(get_session)) -> List[Dict[str, Any]]:
        return [
            {
                "id": item.id,
                "callback": item.callback,
                "query": item.query,
                "eventType": item.event_type,
                "payload": item.payload,
            }
            for item in list_subscriptions(session)
        ]

    @hub_router.post("")
    def _create_subscription(
        body: HubSubscriptionIn,
        session: Session = Depends(get_session),
    ) -> Dict[str, Any]:
        item = create_subscription(
            session=session,
            callback=body.callback,
            query=body.query,
            event_type=body.eventType,
            payload=body.payload,
        )
        return {
            "id": item.id,
            "callback": item.callback,
            "query": item.query,
            "eventType": item.event_type,
            "payload": item.payload,
        }

    @hub_router.delete("/{subscription_id}")
    def _delete_subscription(subscription_id: int, session: Session = Depends(get_session)) -> Dict[str, Any]:
        deleted = delete_subscription(session, subscription_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"subscription '{subscription_id}' not found")
        return {"status": "deleted", "id": str(subscription_id)}

    app.include_router(hub_router)
'''
    )
    return template.substitute(
        APP_TITLE=title,
        APP_VERSION=version,
        TMF_NUMBER=tmf_number,
        RESOURCE_CONFIG=resource_config_literal,
        SKIPPED_PATHS=skipped_paths_literal,
        HAS_HUB="True" if has_hub else "False",
    )


def _build_readme(
    title: str,
    version: str,
    tmf_number: str,
    resources: List[Dict[str, Any]],
    skipped_paths: List[str],
    has_hub: bool,
    design_context: Dict[str, Any] | None = None,
) -> str:
    lines: List[str] = []
    lines.append(f"# README-TMF{tmf_number}.md")
    lines.append("")
    lines.append(f"- Service: `{title}`")
    lines.append(f"- Version: `{version}`")
    lines.append(f"- TMF API: `TMF{tmf_number}`")
    if isinstance(design_context, dict) and design_context:
        component_name = design_context.get("component_name")
        api_id = design_context.get("api_id")
        design_package = design_context.get("design_package")
        if component_name:
            lines.append(f"- Component: `{component_name}`")
        if api_id:
            lines.append(f"- Design API: `{api_id}`")
        if design_package:
            lines.append(f"- Design Package: `{design_package}`")
    lines.append("")
    lines.append("## Run")
    lines.append("")
    lines.append("```bash")
    lines.append("pip install -r requirements.txt")
    lines.append("uvicorn app.main:app --reload")
    lines.append("```")
    lines.append("")
    lines.append("## Generated Endpoints")
    lines.append("")
    lines.append("- `GET /health`")
    lines.append("- `GET /_meta`")
    for resource in resources:
        name = resource["name"]
        supports = resource["supports"]
        if supports.get("list"):
            lines.append(f"- `GET /{name}`")
        if supports.get("create"):
            lines.append(f"- `POST /{name}`")
        if supports.get("get"):
            lines.append(f"- `GET /{name}/{{id}}`")
        if supports.get("patch"):
            lines.append(f"- `PATCH /{name}/{{id}}`")
        if supports.get("put"):
            lines.append(f"- `PUT /{name}/{{id}}`")
        if supports.get("delete"):
            lines.append(f"- `DELETE /{name}/{{id}}`")
    if has_hub:
        lines.append("- `GET /hub`")
        lines.append("- `POST /hub`")
        lines.append("- `DELETE /hub/{subscription_id}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Payloads are stored as JSON in SQLite (`resource_items.payload`).")
    lines.append("- Item identity uses TMF `id` when present; otherwise UUID is generated.")
    lines.append("- Harden authentication, authorization, and validation before production exposure.")
    if skipped_paths:
        lines.append("")
        lines.append("## Skipped Paths")
        lines.append("")
        for path in skipped_paths:
            lines.append(f"- `{path}`")
    lines.append("")
    return "\n".join(lines)


def scaffold(
    spec: Dict[str, Any],
    spec_path: Path,
    output_dir: Path,
    service_name: str | None,
    database_url: str,
    *,
    strict_methods: bool,
    include_hub: bool | None,
    design_context: Dict[str, Any] | None,
) -> None:
    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
    resources, skipped_paths, has_hub = _collect_resources(paths)
    if not resources:
        raise SystemExit("No top-level TMF resources could be derived from the OpenAPI paths")
    if not strict_methods:
        for resource in resources:
            resource["supports"] = {
                "list": True,
                "create": True,
                "get": True,
                "patch": True,
                "put": True,
                "delete": True,
            }
    if include_hub is not None:
        has_hub = bool(include_hub)
    if isinstance(design_context, dict):
        _apply_design_resource_metadata(
            resources=resources,
            design_api_entry=design_context.get("api", {}),
            shared_entities=design_context.get("shared_entities", []),
        )

    title = service_name or info.get("title") or spec_path.stem
    version = str(info.get("version") or "0.0.0")
    tmf_number = _tmf_number_from_text(spec_path.name, str(info.get("title", ""))) or "unknown"
    package_name = _sanitize_module_name(title)

    app_dir = output_dir / "app"
    _write(output_dir / "requirements.txt", "fastapi\nuvicorn\nsqlmodel\npyyaml\n")
    _write(output_dir / "app" / "__init__.py", "")
    _write(app_dir / "database.py", _build_database_py(database_url))
    _write(app_dir / "models.py", _build_models_py())
    _write(app_dir / "crud.py", _build_crud_py())
    _write(app_dir / "schemas.py", _build_schemas_py())
    _write(
        app_dir / "main.py",
        _build_main_py(
            title=title,
            version=version,
            tmf_number=tmf_number,
            resources=resources,
            skipped_paths=skipped_paths,
            has_hub=has_hub,
        ),
    )

    inventory = {
        "title": title,
        "version": version,
        "tmf_number": tmf_number,
        "package_name": package_name,
        "database_url_default": database_url,
        "resources": resources,
        "skipped_paths": skipped_paths,
        "has_hub": has_hub,
        "strict_methods": bool(strict_methods),
    }
    if isinstance(design_context, dict) and design_context:
        inventory["design_context"] = {
            "component_name": design_context.get("component_name"),
            "api_id": design_context.get("api_id"),
            "design_package": design_context.get("design_package"),
            "shared_entity_count": len(design_context.get("shared_entities", [])),
        }
    _write(output_dir / "inventory.json", json.dumps(inventory, indent=2) + "\n")
    _write(
        output_dir / f"README-TMF{tmf_number}.md",
        _build_readme(title, version, tmf_number, resources, skipped_paths, has_hub, design_context),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="Path to OpenAPI YAML/JSON file")
    parser.add_argument("--out", required=True, help="Output folder for generated service")
    parser.add_argument("--service-name", help="Override service name")
    parser.add_argument("--database-url", default="sqlite:///./tmf_service.db", help="Default DATABASE_URL value")
    parser.add_argument("--implementation-catalog", help="Optional tmf-domain-architect implementation-catalog.json")
    parser.add_argument("--design-api", help="API selector for design package (api_id, tmf number, or title)")
    parser.add_argument(
        "--strict-methods",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate only methods present in spec (default true)",
    )
    parser.add_argument(
        "--include-hub",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force-enable or force-disable /hub endpoints (default: auto from spec)",
    )
    parser.add_argument("--force", action="store_true", help="Allow writing into non-empty output folder")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        raise SystemExit(f"Spec file not found: {spec_path}")

    output_dir = Path(args.out).resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        raise SystemExit(f"Output directory is not empty: {output_dir}. Use --force to continue.")
    output_dir.mkdir(parents=True, exist_ok=True)

    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise SystemExit("Spec did not parse into an object")
    if not isinstance(spec.get("paths"), dict):
        raise SystemExit("Spec is missing top-level 'paths' object")

    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    spec_title = str(info.get("title") or spec_path.stem)
    spec_tmf_number = _tmf_number_from_text(spec_path.name, spec_title) or "unknown"

    service_name = args.service_name
    database_url = args.database_url
    include_hub = args.include_hub
    design_context: Dict[str, Any] | None = None

    if args.implementation_catalog:
        design_path = Path(args.implementation_catalog).resolve()
        design = _load_design_package(design_path)
        api_entry = _pick_design_api_entry(
            design=design,
            spec_path=spec_path,
            tmf_number=spec_tmf_number,
            design_api=args.design_api,
        )
        if service_name is None and api_entry.get("service_name"):
            service_name = str(api_entry.get("service_name"))
        db = design.get("database") if isinstance(design.get("database"), dict) else {}
        if (
            database_url == "sqlite:///./tmf_service.db"
            and isinstance(db, dict)
            and isinstance(db.get("url"), str)
            and db.get("url")
        ):
            database_url = str(db.get("url"))
        if include_hub is None and isinstance(api_entry.get("has_hub"), bool):
            include_hub = bool(api_entry.get("has_hub"))
        design_context = {
            "component_name": design.get("component_name"),
            "api_id": api_entry.get("api_id"),
            "design_package": str(design_path),
            "shared_entities": design.get("shared_entities", []),
            "api": api_entry,
        }

    scaffold(
        spec=spec,
        spec_path=spec_path,
        output_dir=output_dir,
        service_name=service_name,
        database_url=database_url,
        strict_methods=bool(args.strict_methods),
        include_hub=include_hub,
        design_context=design_context,
    )
    print(f"Generated TMF service scaffold at: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
