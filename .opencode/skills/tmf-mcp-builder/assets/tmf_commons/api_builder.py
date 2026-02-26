from fastapi import FastAPI, HTTPException, Request, Query, Body, Path, status, Response
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from fastapi.responses import JSONResponse
import asyncio

logger = logging.getLogger("tmf_commons.api_builder")

# Global storage
data_storage = {}

def create_tmf_app(
    spec: Dict[str, Any],
    delay: float = 0,
    extensions=None,
    exclude_paths: Optional[Set[str]] = None,
    exclude_methods: Optional[Set[Tuple[str, str]]] = None,
    data_generator=None
) -> FastAPI:
    """
    Create FastAPI app with dynamic routes, storage, debug (enhanced from TMF637)
    
    Args:
        spec: OpenAPI spec dict
        delay: Optional artificial delay for all endpoints
        extensions: Optional extension object for custom handlers
        exclude_paths: Set of path strings to exclude from dynamic route generation
        exclude_methods: Set of (method, path) tuples to exclude from dynamic route generation
        data_generator: Optional DataGenerator instance for realistic sample data
    
    Note:
        IMPORTANT: If you need custom business logic for specific endpoints, use exclude_paths
        to prevent dynamic generation of those routes, then define your custom endpoints.
        This prevents conflicts between dynamic routes and custom implementations.
        
        Example:
            app = create_tmf_app(spec, exclude_paths={'/customer', '/customer/{id}'})
            # Now define your custom @app.post('/customer') and @app.get('/customer/{id}')
    """
    app = FastAPI(title=spec['info']['title'], version=spec['info']['version'])
    
    def initialize_storage():
        global data_storage
        data_storage = {}
        
        # Pre-populate with sample data if data_generator is provided
        if data_generator:
            # Extract main resources from paths
            resources = set()
            for path in spec.get('paths', {}):
                resource = path.strip('/').split('/')[0]
                if resource and not resource.startswith('{') and resource not in ['hub', 'listener']:
                    resources.add(resource)
            
            # Generate sample data for each resource
            for resource in resources:
                method_name = f'generate_{resource}_data'
                if hasattr(data_generator, method_name):
                    sample_count = 5  # Default sample count
                    data_storage[resource] = []
                    for _ in range(sample_count):
                        sample_data = getattr(data_generator, method_name)()
                        data_storage[resource].append(sample_data)
                    logger.info(f"Pre-populated {resource} with {sample_count} sample items")
                else:
                    logger.warning(f"No method {method_name} found in data generator")
    
    initialize_storage()
    
    # Log excluded paths for debugging
    if exclude_paths:
        logger.info(f"Excluding paths from dynamic generation: {exclude_paths}")
    if exclude_methods:
        logger.info(f"Excluding methods from dynamic generation: {exclude_methods}")
    
    routes_created = 0
    for path, path_item in spec['paths'].items():
        if exclude_paths and path in exclude_paths:
            logger.debug(f"Skipping excluded path: {path}")
            continue
        for method, operation in path_item.items():
            if exclude_methods and (method, path) in exclude_methods:
                logger.debug(f"Skipping excluded method: {method} {path}")
                continue
            async def handler(request: Request, method=method, path=path, operation=operation):
                await asyncio.sleep(delay) if delay > 0 else None
                resource = path.strip('/').split('/')[0]
                if extensions and hasattr(extensions, f'handle_{method}_{resource}'):
                    return getattr(extensions, f'handle_{method}_{resource}')(request)
                
                # Handle GET requests
                if method == 'get':
                    if '{' not in path:
                        # List resources: GET /resource
                        return data_storage.get(resource, [])
                    else:
                        # Get individual resource: GET /resource/{id}
                        path_params = request.path_params
                        if path_params:
                            item_id = next(iter(path_params.values()))
                            items = data_storage.get(resource, [])
                            for item in items:
                                if item.get('id') == item_id:
                                    return item
                            raise HTTPException(status_code=404, detail=f"{resource.title()} with id {item_id} not found")
                        return {"message": f"No ID provided for {resource}"}
                
                # Handle POST requests
                elif method == 'post':
                    body = await request.json()
                    item_id = str(uuid.uuid4())
                    body['id'] = item_id
                    
                    # Add href if not provided
                    if 'href' not in body:
                        body['href'] = f"/tmf-api/{resource}/v5/{resource}/{item_id}"
                    
                    # Use data generator to enhance the data if available
                    if data_generator and hasattr(data_generator, f'generate_{resource}_data'):
                        # Merge generated data with provided data, giving priority to provided data
                        generated_data = getattr(data_generator, f'generate_{resource}_data')()
                        for key, value in generated_data.items():
                            if key not in body:
                                body[key] = value
                    
                    if resource not in data_storage:
                        data_storage[resource] = []
                    data_storage[resource].append(body)
                    return JSONResponse(status_code=201, content=body)
                
                # Handle PATCH requests
                elif method == 'patch':
                    path_params = request.path_params
                    if path_params:
                        item_id = next(iter(path_params.values()))
                        items = data_storage.get(resource, [])
                        for i, item in enumerate(items):
                            if item.get('id') == item_id:
                                body = await request.json()
                                # Update the item with patch data
                                data_storage[resource][i].update(body)
                                return data_storage[resource][i]
                        raise HTTPException(status_code=404, detail=f"{resource.title()} with id {item_id} not found")
                    return {"message": f"No ID provided for {resource}"}
                
                # Handle DELETE requests
                elif method == 'delete':
                    path_params = request.path_params
                    if path_params:
                        item_id = next(iter(path_params.values()))
                        items = data_storage.get(resource, [])
                        for i, item in enumerate(items):
                            if item.get('id') == item_id:
                                del data_storage[resource][i]
                                return Response(status_code=204)
                        raise HTTPException(status_code=404, detail=f"{resource.title()} with id {item_id} not found")
                    return {"message": f"No ID provided for {resource}"}
                
                return {"message": f"Generic {method.upper()} response for {path}"}
            app.add_api_route(path, handler, methods=[method.upper()])
            routes_created += 1
            logger.debug(f"Created dynamic route: {method.upper()} {path}")
    
    logger.info(f"Created {routes_created} dynamic routes from OpenAPI spec")
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    @app.get("/debug/storage")
    async def debug_storage():
        return data_storage
    
    @app.get("/debug/routes")
    async def debug_routes():
        routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": getattr(route, 'name', ''),
                    "tags": getattr(route, 'tags', [])
                })
        return {"routes": routes}
    
    @app.post("/debug/reset")
    async def debug_reset():
        initialize_storage()
        return {"message": "Storage reset to initial sample data"}
    
    @app.get("/debug/error/{status_code}")
    async def debug_error(status_code: int = Path(...)):
        raise HTTPException(status_code=status_code, detail=f"Simulated error {status_code}")
    
    return app 