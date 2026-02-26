from fastapi import FastAPI, Body, Request, Response, HTTPException
import logging
from typing import Dict

logger = logging.getLogger('tmf_commons.event_utils')

def add_event_handlers(app: FastAPI, spec: Dict) -> None:
    """Add generic TMF event handlers (enhanced from prompt)"""
    for path, path_item in spec['paths'].items():
        if 'hub' in path.lower() or 'listener' in path.lower():
            for method, operation in path_item.items():
                async def event_handler(request: Request, method=method, path=path):
                    if method == 'post':
                        body = await request.json()
                        logger.info(f'Handling event at {path}: {body}')
                        return Response(status_code=204)
                    # Add GET/DELETE for hubs, etc.
                    return {"message": "Event handled"}
                
                app.add_api_route(path, event_handler, methods=[method.upper()])
    logger.info('Added TMF event handlers') 