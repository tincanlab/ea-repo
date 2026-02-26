# TMF API MCP Server Creation Prompt

You are an expert Python developer tasked with creating a complete TMF MCP server implementation. Output EXACTLY in the tool call format provided. First think step-by-step about the content, then output the full JSON tool call.

## CRITICAL TOOL USAGE REQUIREMENTS (READ THIS FIRST - FAILURE TO FOLLOW WILL CAUSE ERRORS)

**ALWAYS PLAN YOUR TOOL CALLS BEFORE MAKING THEM. FOLLOW THIS CHECKLIST FOR EVERY write_file CALL:**
1. Am I creating a new file with generated content (e.g., code)? If yes, generate the FULL content in your reasoning and include it in the `content` parameter.
2. Am I copying an existing file (e.g., the spec)? If yes, FIRST call `read_file` to get the content, THEN call `write_file` with both `path` and `content`.
3. Do I have BOTH `path` AND `content` parameters? If not, STOP and fix it - path-only calls will fail.
4. Is the `content` complete and valid? Double-check for syntax errors in code.

**NEVER ATTEMPT TO CREATE EMPTY FILES OR USE write_file FOR ANYTHING BUT WRITING COMPLETE CONTENT.**

When using the `write_file` tool, you **MUST** provide BOTH parameters:
- `path`: The file path where to create the file
- `content`: The **COMPLETE** file content to write (generate it fully in your response if needed)

**Example of CORRECT usage (creating a new file with generated content):**
```json
{
  "id": "call_0_d6fcbbe1-0d05-405d-b2c5-85aa4bf82590",
  "function": {
    "name": "write_file",
    "arguments": "{\"path\": \"WIP/TMF629/tmf629_mock_server.py\", \"content\": \"from fastapi import FastAPI\\n\\napp = FastAPI()\\n\\n@app.get('/tmf-api/resource')\\ndef get_resource():\\n    return {'status': 'mocked'}\"}"
  }
}
```

**Example of INCORRECT usage (will fail and loop):**
```json
{
  "path": "WIP/TMF629/tmf629_mock_server.py"
}
```

**IMPORTANT**: Never call `write_file` with only the path parameter. You must always include the complete file content in the `content` parameter. If you forget, the system will error and remind you - but plan ahead to avoid this.

**SPECIFIC INSTRUCTION FOR COPYING FILES**: If you need to copy a file (like the OpenAPI specification), you must:
1. First use `read_file` to read the content of the source file
2. Then use `write_file` with both `path` and `content` parameters to write the content to the destination
**Do NOT copy the spec file if the directory already exists - assume it's there and focus on creating implementation files.**

**FOR YOUR FIRST TOOL CALL: Use this exact structure to create the mock_server.py file as your starting point, then build on it:**
```json
{
  "id": "call_example",
  "function": {
    "name": "write_file",
    "arguments": "{\"path\": \"WIP/TMF{tmf_number}/tmf{tmf_number}_mock_server.py\", \"content\": \"from fastapi import FastAPI\\n\\napp = FastAPI()\\n\\n@app.get('/tmf-api/resource')\\ndef get_resource():\\n    return {'status': 'mocked'}\"}"
  }
}
```
Modify the content inside as needed for the specific TMF API.

## Your Task

Create a complete TMF MCP server implementation with the following files:

1. **tmf###_mock_server.py** - FastAPI mock server that implements the API (prefix with tmf###_)
2. **tmf###_client.py** - HTTP client for communicating with the mock server (prefix with tmf###_)
3. **tmf###_mcp_server.py** - MCP server that wraps the API for LLM access (prefix with tmf###_)
4. **run_mock_server.py** - Script to run the mock server
5. **run_mcp_server.py** - Script to run the MCP server
6. **requirements.txt** - Python dependencies
7. **README.md** - Documentation

## Step 1: Analyze the TMF OpenAPI Specification

### Input Requirements
- TMF OpenAPI specification file (e.g., `TMF###-ApiName-v#.#.#.oas.yaml`)
- The specification should contain:
  - API paths and operations
  - Component schemas with complex inheritance (`allOf`, discriminators)
  - Request/response models
  - Event notification endpoints

### Key Analysis Points
1. **Identify main resource entities** from the schema components
2. **Map API operations** (GET, POST, PUT, PATCH, DELETE) to endpoints
3. **Handle schema inheritance** - TMF specs use `allOf` and discriminators extensively
4. **Extract event notification patterns** for hub/listener endpoints
5. **Understand the API's business domain** (e.g., Product Inventory, Customer Management)

## Step 2: Create the Mock API Server

### File Structure
Create these files following the TMF637 pattern with EXACT naming:
```
TMF###/
├── TMF###-ApiName-v#.#.#.oas.yaml
├── tmf###_mock_server.py      # CRITICAL: Use tmf### prefix (lowercase)
├── tmf###_mcp_server.py       # CRITICAL: Use tmf### prefix (lowercase)  
├── tmf###_client.py           # CRITICAL: Use tmf### prefix (lowercase)
├── run_mock_server.py         # Import from tmf###_mock_server
├── run_mcp_server.py          # Import from tmf###_mcp_server
├── requirements.txt
└── README.md
```

**CRITICAL**: All core files MUST use the `tmf###_` prefix (lowercase) where ### is the TMF number. The run scripts import from these prefixed modules.

**CRITICAL**: When creating each file using the `write_file` tool, you MUST provide the complete file content in the `content` parameter. Do not call `write_file` with only the path.

### Mock Server Implementation (`tmf###_mock_server.py`)

**CRITICAL**: The mock server file MUST have this exact structure because run_mock_server.py imports from it:

```python
#!/usr/bin/env python3
"""TMF### Mock Server Implementation"""

import yaml
from fastapi import FastAPI, HTTPException, Query, Body, Path, status, Response
from fastapi.responses import JSONResponse
# ... other imports

def load_openapi_spec(yaml_path: str) -> Dict[str, Any]:
    """Load and parse the OpenAPI specification from a YAML file"""
    # Implementation here

def create_mock_api(openapi_spec: Dict[str, Any], delay: float = 0) -> FastAPI:
    """Create FastAPI application from OpenAPI specification"""
    # Implementation here
    return app

# Optional: if running directly
if __name__ == "__main__":
    import uvicorn
    spec = load_openapi_spec("TMF###-spec.yaml")
    app = create_mock_api(spec)
    uvicorn.run(app, host="0.0.0.0", port=8###)
```

#### Core Functions Required

1. **OpenAPI Spec Loader**
```python
def load_openapi_spec(yaml_path: str) -> Dict[str, Any]:
    """Load and parse the OpenAPI specification from a YAML file"""
    # Handle multiple encodings (utf-8, latin-1, cp1252)
    # Use yaml.safe_load() to parse the specification
```

2. **Enhanced Sample Data Generator**
```python
def generate_sample_data(schema: Dict[str, Any], path: str = "", property_name: str = "", openapi_spec: Dict[str, Any] = None) -> Any:
    """Generate realistic sample data based on OpenAPI schema"""
    # CRITICAL: Handle '$ref' references by resolving them to actual schemas
    # CRITICAL: Handle 'allOf' schema composition (TMF specs use this extensively)
    # CRITICAL: Process schemas that have both 'type' and 'allOf' (common in TMF)
    # Generate context-aware realistic data based on property names
    # Support all OpenAPI data types: object, array, string, number, integer, boolean
    # Handle date-time, date, uri, email formats
    # Generate realistic business data (names, descriptions, IDs, etc.)
    
    # Handle $ref references by resolving them
    if '$ref' in schema:
        if openapi_spec:
            ref_path = schema['$ref']
            if ref_path.startswith('#/'):
                # Parse the reference path (e.g., "#/components/schemas/PartyRole")
                parts = ref_path[2:].split('/')  # Remove '#/' and split
                ref_schema = openapi_spec
                for part in parts:
                    if part in ref_schema:
                        ref_schema = ref_schema[part]
                    else:
                        ref_schema = {}
                        break
                
                if ref_schema and ref_schema != openapi_spec:
                    return generate_sample_data(ref_schema, path, property_name, openapi_spec)
        
        # Fallback: generate contextual data based on the reference name
        # (implement specific fallbacks for common TMF references like PartyRole, etc.)
        return generate_contextual_fallback_data(schema['$ref'])
    
    # Handle allOf schema composition (even if type is also present)
    if 'allOf' in schema:
        result = {}
        # If there's a base type, start with that
        if 'type' in schema and schema['type'] == 'object':
            # Process any direct properties first
            for prop_name, prop_schema in schema.get('properties', {}).items():
                prop_path = f"{path}.{prop_name}" if path else prop_name
                result[prop_name] = generate_sample_data(prop_schema, prop_path, prop_name, openapi_spec)
        
        # Then process each schema in allOf
        for sub_schema in schema['allOf']:
            sub_data = generate_sample_data(sub_schema, path, property_name, openapi_spec)
            if isinstance(sub_data, dict):
                result.update(sub_data)
        return result
    
    # Continue with regular type processing...
```

3. **Mock API Factory**
```python
def create_mock_api(openapi_spec: Dict[str, Any], delay: float = 0) -> FastAPI:
    """Create FastAPI application from OpenAPI specification"""
    # Pre-populate with realistic sample data
    # Register dynamic routes from OpenAPI paths
    # Implement full CRUD operations with in-memory storage
    # Add debug endpoints (/debug/storage, /debug/routes, /debug/reset)
    # Handle filtering, pagination, field selection
    # Proper HTTP status codes and error handling
```

#### Critical Implementation Details

1. **Schema Reference Resolution**
   - TMF specs extensively use `$ref` to reference other schemas
   - Must resolve `$ref` references to actual schema definitions
   - Handle nested references and circular dependencies
   - Implement fallback data generation for unresolvable references

2. **Schema Inheritance Handling**
   - TMF specs heavily use `allOf` for schema composition
   - Must handle schemas that have both `type` and `allOf` (common pattern)
   - Must properly merge schemas from `allOf` arrays
   - Handle discriminator mappings correctly
   - Process `allOf` even when `type` is present in the schema

3. **Realistic Data Generation**
   - Generate business-appropriate data based on property names
   - Use realistic values for TMF entities (products, customers, services)
   - Implement proper date/time generation with realistic ranges
   - Generate UUIDs for ID fields
   - Create contextual fallback data for common TMF references (PartyRole, etc.)

3. **Storage Management**
   - Use correct storage keys that match API paths
   - Implement proper collection vs. single item handling
   - Support filtering with query parameters
   - Handle nested property filtering (e.g., `status.value`)

4. **Debug Capabilities**
   - `/debug/storage` - View current in-memory data
   - `/debug/routes` - List all registered API routes
   - `/debug/reset` - Reset to initial sample data
   - `/debug/error/{status_code}` - Simulate error responses

### Run Script (`run_mock_server.py`)
```python
#!/usr/bin/env python3
"""Run script for the TMF### Mock Server"""
# Command-line argument parsing
# Support for --spec, --host, --port, --delay, --debug, --persistence
# Integration with main mock server
```

## Step 3: Create the MCP Server

### MCP Server Implementation (`tmf###_mcp_server.py`)

#### Required Components

1. **TMF API Client** (`tmf###_client.py`)
```python
class TMF###Client:
    """HTTP client for communicating with the TMF### mock API server"""
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        # Handle HTTP requests to mock server
        # Proper error handling and status code management
        
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    # Implement specific API methods based on TMF spec:
    # CRITICAL: Use SINGULAR form for all method names to match MCP server
    async def list_customer(self, fields=None, offset=None, limit=None):  # SINGULAR
    async def get_customer(self, customer_id: str, fields=None):  # SINGULAR
    async def create_customer(self, customer_data: Dict[str, Any]):  # SINGULAR
    async def update_customer(self, customer_id: str, customer_data: Dict[str, Any]):  # SINGULAR
    async def patch_customer(self, customer_id: str, patch_data: Dict[str, Any]):  # SINGULAR
    async def delete_customer(self, customer_id: str):  # SINGULAR
    async def create_hub(self, callback: str, query=None):
    async def delete_hub(self, hub_id: str):
    async def health_check(self):
```

2. **MCP Server with FastMCP (official mcp SDK)**
```python
#!/usr/bin/env python3
"""TMF### MCP Server (FastMCP)

Expose TMF### API operations as MCP tools.
This MCP server should call the TMF###Client (which talks to the mock server or a real TMF endpoint).
"""

import os
import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from tmf###_client import TMF###Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmf###_mcp")

mcp = FastMCP("tmf###_mcp")

tmf_client = TMF###Client(os.getenv("TMF###_API_URL", "http://localhost:8###"))

@mcp.tool(name="tmf###_health_check", annotations={"readOnlyHint": True})
async def tmf###_health_check() -> Dict[str, Any]:
    return await tmf_client.health_check()

# Define tools explicitly (do not rely on auto-conversion):
# - tmf###_list_{resource}
# - tmf###_get_{resource}
# - tmf###_create_{resource}
# - tmf###_patch_{resource}
# - tmf###_delete_{resource}

if __name__ == "__main__":
    mcp.run()
```

3. **API Endpoint Definitions**
Define MCP tools with `@mcp.tool` and keep tool names aligned with your `operation_id` conventions:

```python
# Main resource operations
@app.get("/api/{resource}", tags=["{resource}"], operation_id="tmf###_list_{resource}")
async def api_list_{resource}(
    fields: Optional[str] = Query(None, description="Fields to include in the response"),
    offset: Optional[int] = Query(None, description="Pagination offset"),
    limit: Optional[int] = Query(None, description="Pagination limit")
):
    """List {Resource} objects with optional filtering and pagination"""
    try:
        result = await tmf_client.list_{resource}(
            fields=fields,
            offset=offset,
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list {resource}: {e}")
        raise

@app.post("/api/{resource}", tags=["{resource}"], operation_id="tmf###_create_{resource}")
async def api_create_{resource}(
    {resource}: Dict[str, Any] = Body(..., description="{Resource} data")
):
    """Create a new {Resource}"""
    try:
        result = await tmf_client.create_{resource}({resource})
        return result
    except Exception as e:
        logger.error(f"Failed to create {resource}: {e}")
        raise

@app.get("/api/{resource}/{{resource_id}}", tags=["{resource}"], operation_id="tmf###_get_{resource}")
async def api_get_{resource}(
    {resource}_id: str = Path(..., description="{Resource} ID"),
    fields: Optional[str] = Query(None, description="Fields to include in the response")
):
    """Retrieve a {Resource} by ID"""
    try:
        result = await tmf_client.get_{resource}({resource}_id, fields=fields)
        return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"{Resource} with id {{resource}_id} not found")
        else:
            logger.error(f"HTTP error getting {resource}: {e}")
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get {resource}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.put("/api/{resource}/{{resource_id}}", tags=["{resource}"], operation_id="tmf###_update_{resource}")
async def api_update_{resource}(
    {resource}_id: str = Path(..., description="{Resource} ID"),
    {resource}: Dict[str, Any] = Body(..., description="Updated {resource} data")
):
    """Update a {Resource}"""
    try:
        result = await tmf_client.update_{resource}({resource}_id, {resource})
        return result
    except Exception as e:
        logger.error(f"Failed to update {resource}: {e}")
        raise

@app.patch("/api/{resource}/{{resource_id}}", tags=["{resource}"], operation_id="tmf###_patch_{resource}")
async def api_patch_{resource}(
    {resource}_id: str = Path(..., description="{Resource} ID"),
    patch: Dict[str, Any] = Body(..., description="Patch data")
):
    """Patch a {Resource}"""
    try:
        result = await tmf_client.patch_{resource}({resource}_id, patch)
        return result
    except Exception as e:
        logger.error(f"Failed to patch {resource}: {e}")
        raise

@app.delete("/api/{resource}/{{resource_id}}", tags=["{resource}"], operation_id="tmf###_delete_{resource}")
async def api_delete_{resource}(
    {resource}_id: str = Path(..., description="{Resource} ID")
):
    """Delete a {Resource}"""
    try:
        result = await tmf_client.delete_{resource}({resource}_id)
        return result
    except Exception as e:
        logger.error(f"Failed to delete {resource}: {e}")
        raise

# Hub/Event subscription endpoints
@app.post("/api/hub", tags=["hub"], operation_id="tmf###_create_hub")
async def api_create_hub(
    callback: str = Body(..., description="Callback URL"),
    query: Optional[str] = Body(None, description="Query string")
):
    """Create an event subscription hub to receive notifications"""
    try:
        result = await tmf_client.create_hub(callback, query=query)
        return result
    except Exception as e:
        logger.error(f"Failed to create hub: {e}")
        raise

@app.delete("/api/hub/{hub_id}", tags=["hub"], operation_id="tmf###_delete_hub")
async def api_delete_hub(
    hub_id: str = Path(..., description="Hub ID")
):
    """Delete an event subscription hub"""
    try:
        result = await tmf_client.delete_hub(hub_id)
        return result
    except Exception as e:
        logger.error(f"Failed to delete hub: {e}")
        raise

# System endpoints
@app.get("/api/health", tags=["system"], operation_id="tmf###_health_check")
async def api_health_check():
    """Check the health status of the TMF### API server"""
    try:
        result = await tmf_client.health_check()
        return result
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise

# Standard endpoints
@app.get("/health")
async def health_check():
    """Health check for the MCP HTTP server"""
    try:
        tmf_health = await tmf_client.health_check()
        return {
            "status": "healthy",
            "service": "TMF### MCP HTTP Server",
            "tmf###_api": tmf_health
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "TMF### MCP HTTP Server",
            "error": str(e)
        }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "TMF### API MCP Server",
        "version": "1.0.0",
        "description": "MCP server for TMF### API",
        "endpoints": {
            "mcp": "/mcp",
            "api": "/api",
            "health": "/health",
            "docs": "/docs"
        }
    }

# MCP server: use the official mcp Python SDK (FastMCP); define tools explicitly (see FastMCP example above).

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8###"))  # Use appropriate port number
    
    print(f"Starting TMF### API MCP Server...")
    print(f"Server: http://{host}:{port}")
    print(f"TMF### API: {tmf_client.base_url}")
    print(f"Documentation: http://{host}:{port}/docs")
    print(f"MCP Endpoint: http://{host}:{port}/mcp")
    print(f"API Endpoints: http://{host}:{port}/api")
    
    uvicorn.run(app, host=host, port=port)
```

### MCP Configuration

Create `.kiro/settings/mcp.json`:
```json
{
  "mcpServers": {
    "tmf###": {
      "command": "python",
      "args": ["tmf###_mcp_server.py"],
      "env": {
        "PYTHONPATH": ".",
        "TMF###_API_URL": "http://localhost:8###"
      },
      "disabled": false,
      "autoApprove": [
        "tmf###_health_check",
        "tmf###_list_{resource}",
        "tmf###_get_{resource}"
      ]
    }
  }
}
```

### Additional Files Required

1. **TMF### Client** (`tmf###_client.py`)
```python
#!/usr/bin/env python3
"""
TMF### API Client
HTTP client for communicating with TMF### API server
"""

import httpx
import logging
from typing import Dict, Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger("tmf###-client")

class TMF###Client:
    """HTTP client for TMF### API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to TMF### API"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            
            if response.status_code == 204:
                return {"status": "success", "message": "Operation completed successfully"}
            
            return response.json()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise
    
    # Implement specific methods based on your TMF API:
    # CRITICAL: Use PLURAL for list methods, SINGULAR for others
    
    async def list_{resource}s(self, fields: Optional[str] = None, 
                             offset: Optional[int] = None, 
                             limit: Optional[int] = None) -> Dict[str, Any]:
        """List {resource} objects - NOTE: Method name is PLURAL"""
        params = {}
        if fields:
            params['fields'] = fields
        if offset is not None:
            params['offset'] = offset
        if limit is not None:
            params['limit'] = limit
            
        return await self._make_request('GET', '/{resource}', params=params)
    
    async def get_{resource}(self, {resource}_id: str, fields: Optional[str] = None) -> Dict[str, Any]:
        """Get a specific {resource} by ID - NOTE: Method name is SINGULAR"""
        params = {}
        if fields:
            params['fields'] = fields
            
        return await self._make_request('GET', f'/{resource}/{{{resource}_id}}', params=params)
    
    async def create_{resource}(self, {resource}_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new {resource} - NOTE: Method name is SINGULAR"""
        return await self._make_request('POST', '/{resource}', json={resource}_data)
    
    async def update_{resource}(self, {resource}_id: str, {resource}_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a {resource} - NOTE: Method name is SINGULAR"""
        return await self._make_request('PUT', f'/{resource}/{{{resource}_id}}', json={resource}_data)
    
    async def patch_{resource}(self, {resource}_id: str, patch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Patch a {resource} - NOTE: Method name is SINGULAR"""
        return await self._make_request('PATCH', f'/{resource}/{{{resource}_id}}', json=patch_data)
    
    async def delete_{resource}(self, {resource}_id: str) -> Dict[str, Any]:
        """Delete a {resource} - NOTE: Method name is SINGULAR"""
        return await self._make_request('DELETE', f'/{resource}/{{{resource}_id}}')
    
    async def create_hub(self, callback: str, query: Optional[str] = None) -> Dict[str, Any]:
        """Create an event subscription hub"""
        hub_data = {"callback": callback}
        if query:
            hub_data["query"] = query
        return await self._make_request('POST', '/hub', json=hub_data)
    
    async def delete_hub(self, hub_id: str) -> Dict[str, Any]:
        """Delete an event subscription hub"""
        return await self._make_request('DELETE', f'/hub/{hub_id}')
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        return await self._make_request('GET', '/health')
```

2. **Run Script** (`run_mcp_server.py`)
```python
#!/usr/bin/env python3
"""
Run the TMF### MCP server.
"""
import os
import uvicorn
from tmf###_mcp_server import app, tmf_client

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8###"))  # Use appropriate port
    tmf_api_url = os.getenv("TMF###_API_URL", "http://localhost:8###")

    # Set the TMF API URL for the client
    tmf_client.base_url = tmf_api_url
    
    print(f"Starting TMF### MCP Server...")
    print(f"Server: http://{host}:{port}")
    print(f"TMF API: {tmf_client.base_url}")
    print(f"Documentation: http://{host}:{port}/docs")
    print(f"MCP Endpoint: http://{host}:{port}/mcp")
    
    uvicorn.run(app, host=host, port=port)
```

## Step 4: Documentation and Testing

### Create Documentation
1. **README.md** - Installation, usage, API endpoints
2. **TMF_MCP_SERVER_GUIDE.md** - MCP-specific documentation
3. **API documentation** - Available via FastAPI's `/docs` endpoint

### Testing Requirements
1. **Mock server functionality** - All CRUD operations work
2. **Sample data quality** - Realistic, properly structured data
3. **MCP tool functionality** - All tools respond correctly
4. **Error handling** - Proper HTTP status codes and error messages
5. **Debug endpoints** - All debug features work as expected

## Key Success Criteria

### Mock Server Requirements
- ✅ Loads TMF OpenAPI specification correctly
- ✅ Handles `allOf` schema inheritance properly
- ✅ Generates realistic, business-appropriate sample data
- ✅ Implements full CRUD operations with proper HTTP status codes
- ✅ Supports filtering, pagination, and field selection
- ✅ Provides comprehensive debug endpoints
- ✅ Maintains data consistency across operations

### MCP Server Requirements
- ✅ Exposes TMF API functionality as MCP tools
- ✅ Handles all MCP request/response formats correctly
- ✅ Provides comprehensive error handling
- ✅ Integrates seamlessly with Kiro and other MCP clients
- ✅ Supports all major TMF API operations
- ✅ Includes proper tool documentation and examples

### Code Quality Requirements
- ✅ Follows the established patterns from TMF637 example
- ✅ Includes comprehensive logging and debugging
- ✅ Handles edge cases and error conditions gracefully
- ✅ Uses appropriate Python typing and documentation
- ✅ Follows TMF API conventions and best practices

## Example Usage

After implementation, the system should support:

```bash
# Start the mock server
python run_mock_server.py --spec TMF###-ApiName-v#.#.#.oas.yaml --port 8### --debug

# Start the MCP server
python tmf###_mcp_server.py

# Or use the run script
python run_mcp_server.py

# Test the MCP server directly
curl -X GET http://localhost:8###/

# Test MCP tools via the /mcp endpoint
curl -X POST http://localhost:8###/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/list",
    "params": {}
  }'

# Test a specific tool
curl -X POST http://localhost:8###/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "tmf###_list_{resource}",
      "arguments": {
        "limit": 10
      }
    }
  }'

# Test via regular API endpoints (which become MCP tools)
curl -X GET http://localhost:8###/api/{resource}
```

## Dependencies

Ensure these packages are included in `requirements.txt`:
```
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
pyyaml>=6.0.0
httpx>=0.25.0
mcp>=0.9.0
```

Note: Use the official `mcp` Python SDK (`FastMCP`) for MCP integration. Define MCP tools explicitly and keep tool names consistent with your endpoint `operation_id` values for discoverability.

## Critical Implementation Requirements

### Required Imports for Mock Server
```python
from fastapi import FastAPI, HTTPException, Query, Body, Path, status, Response
from fastapi.responses import JSONResponse
```

### Required Functions for Mock Server
Every mock server MUST include these exact functions that are imported by run_mock_server.py:

```python
def load_openapi_spec(yaml_path: str) -> Dict[str, Any]:
    """Load and parse the OpenAPI specification from a YAML file"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load OpenAPI spec: {e}")
        raise

def create_mock_api(openapi_spec: Dict[str, Any], delay: float = 0) -> FastAPI:
    """Create FastAPI application from OpenAPI specification"""
    app = FastAPI(title="TMF### Mock Server")
    # Implementation here - register routes, add storage, etc.
    return app
```

### Required Health Endpoint
Every mock server MUST include a health endpoint:
```python
@app.get("/health", 
         summary="Health check endpoint",
         tags=["system"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "TMF### Mock Server",
        "version": "1.0.0"
    }
```

### MCP Server Client Integration
The MCP server MUST use the proper client class, not raw httpx:
```python
# Import the TMF client
from tmf###_client import TMF###Client

# Initialize client
tmf_client = TMF###Client(os.getenv("TMF###_API_URL", "http://localhost:8###"))

# CRITICAL: Method names must match EXACTLY between client and MCP server
@app.get("/api/customer", operation_id="tmf###_list_customer")
async def api_list_customer():
    return await tmf_client.list_customer()  # Must match client method name exactly

@app.get("/api/customer/{id}", operation_id="tmf###_get_customer")  
async def api_get_customer(id: str):
    return await tmf_client.get_customer(id)  # Must match client method name exactly
```

**CRITICAL**: Client method naming pattern:
- `list_customers()` - PLURAL for listing multiple items
- `get_customer()` - SINGULAR for getting one item
- `create_customer()` - SINGULAR for creating one item
- `update_customer()` - SINGULAR for updating one item
- `patch_customer()` - SINGULAR for patching one item  
- `delete_customer()` - SINGULAR for deleting one item

## CRITICAL IMPLEMENTATION REQUIREMENTS

### Method Naming Consistency
**CRITICAL**: Method names MUST be consistent between client and MCP server:
- Use SINGULAR form for all resource methods: `list_customer`, `get_customer`, etc.
- Client methods and MCP server calls must match EXACTLY
- Example: If client has `list_customer()`, MCP server must call `list_customer()`

## Important Notes

1. **Schema Reference Resolution**: TMF APIs extensively use `$ref` references to other schemas. The `generate_sample_data` function must resolve these references by parsing the reference path and looking up the actual schema definition in the OpenAPI specification.

2. **Schema Complexity**: TMF APIs use complex schema inheritance with `allOf` and discriminators. The `generate_sample_data` function must handle schemas that have both `type` and `allOf` properties, which is a common pattern in TMF specifications.

3. **Data Realism**: Generate business-appropriate data that reflects the TMF domain (telecommunications, products, services, customers). Implement contextual fallback data for common TMF references like PartyRole, Individual, Organization, etc.

4. **API Compliance**: Ensure the mock server fully implements the TMF API specification, including proper HTTP status codes, error responses, and data validation.

5. **MCP Integration**: Use the official `mcp` Python SDK (`FastMCP`) and define MCP tools explicitly. Keep tool names aligned with your `operation_id` conventions for consistency.

6. **Tool Naming**: Follow the pattern `tmf###_operation_resource` for tool names (e.g., `tmf637_list_products`, `tmf629_get_customer`).

7. **Client Architecture**: Separate the HTTP client logic into a dedicated client class that handles all API communication with the mock server.

8. **Environment Configuration**: Use environment variables for configuration (API URLs, ports, etc.) to make the system flexible.

9. **Port Configuration**: Use TMF-specific port numbering:
   - Mock Server: Port 8000 + TMF number (e.g., TMF629 → port 8629)
   - MCP Server: Port 8000 + TMF number + 1 (e.g., TMF629 → port 8630)

9. **Debug Support**: Include comprehensive debugging capabilities to help with development and troubleshooting. Add logging to show schema structure, allOf composition, and reference resolution.

10. **Error Handling**: Implement proper error handling in both the client and MCP server to provide meaningful error messages to LLMs.

11. **Async/Await**: Use async/await throughout the implementation for better performance and compatibility with FastAPI.

12. **OpenAPI Spec Parameter**: Always pass the `openapi_spec` parameter to the `generate_sample_data` function to enable proper reference resolution and schema composition handling.

## Common Issues and Solutions

### Issue: Generated data only contains ID fields
**Cause**: TMF schemas often use `$ref` references and `allOf` composition that aren't properly resolved.

**Solution**: 
1. Ensure `generate_sample_data` function handles `$ref` by resolving references to actual schemas
2. Handle schemas with both `type` and `allOf` properties
3. Pass the `openapi_spec` parameter to enable reference resolution
4. Add debug logging to understand schema structure

### Issue: Empty objects returned for complex schemas
**Cause**: Schema references (`$ref`) are not being resolved to their actual definitions.

**Solution**:
1. Implement reference resolution by parsing `$ref` paths like `#/components/schemas/PartyRole`
2. Navigate the OpenAPI spec structure to find the referenced schema
3. Recursively call `generate_sample_data` with the resolved schema
4. Implement fallback data for common TMF references

### Issue: allOf schemas not being processed
**Cause**: Logic checks for `type` before checking for `allOf`, missing schemas that have both.

**Solution**:
1. Check for `allOf` first, regardless of whether `type` is present
2. Process both direct properties and `allOf` schemas
3. Merge all generated data into a single result object

### Issue: DELETE endpoints return 500 errors
**Cause**: Missing `Response` import in mock server for 204 status codes.

**Solution**:
```python
from fastapi import FastAPI, HTTPException, Query, Body, Path, status, Response

@app.delete("/resource/{id}")
async def delete_resource(id: str):
    # Delete logic here
    return Response(status_code=204)  # Requires Response import
```

### Issue: 404 errors from mock server cause 500 errors in MCP server
**Cause**: HTTP exceptions from the client are not properly handled in MCP endpoints.

**Solution**:
1. Import `HTTPException` from FastAPI and `httpx` for HTTP status error handling
2. Catch `httpx.HTTPStatusError` exceptions specifically
3. Convert 404 errors to proper HTTPException with 404 status
4. Handle other HTTP errors appropriately
5. Wrap generic exceptions in 500 Internal Server Error responses

```python
try:
    result = await tmf_client.get_resource(resource_id)
    return result
except httpx.HTTPStatusError as e:
    if e.response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Resource with id {resource_id} not found")
    else:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
```

### Issue: MCP server makes dual API calls
**Cause**: Using raw httpx client instead of the proper TMF client class.

**Solution**:
```python
# WRONG - Don't use raw httpx
client = httpx.AsyncClient(base_url=TMF_API_URL)

# CORRECT - Use the TMF client class
from tmf###_client import TMF###Client
tmf_client = TMF###Client(TMF_API_URL)

# Use client methods in endpoints
return await tmf_client.list_customer()  # Not raw HTTP calls
```

### Issue: "Object has no attribute" errors in MCP server
**Cause**: Method name mismatch between client and MCP server (e.g., singular vs plural).

**Solution**:
```python
# In tmf###_client.py
async def list_customer(self, ...):  # SINGULAR
    # Implementation

# In tmf###_mcp_server.py
@app.get("/api/customer", operation_id="tmf###_list_customer")
async def api_list_customer(...):
    return await tmf_client.list_customer(...)  # SINGULAR - must match client
```

**CRITICAL**: Always use the exact same method names in both client and MCP server!

### Issue: 'TMF###Client' object has no attribute 'list_customer'
**Cause**: Method naming mismatch between MCP server and client class.

**Solution**: Use correct method names (PLURAL for list, SINGULAR for others):
```python
# WRONG - Singular method name for listing
return await tmf_client.list_customer()

# CORRECT - Plural method name for listing  
return await tmf_client.list_customers()

# CORRECT - Singular for individual operations
return await tmf_client.get_customer(id)
return await tmf_client.create_customer(data)
return await tmf_client.update_customer(id, data)
return await tmf_client.delete_customer(id)
```


