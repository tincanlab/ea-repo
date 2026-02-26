# TMF API MCP Server Creation Prompt (Library Version)

You are an expert Python developer tasked with creating a TMF MCP server implementation using the tmf_commons library. Output EXACTLY in the tool call format provided. First think step-by-step about the content, then output the full JSON tool call.

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
  "id": "call_0_example_id",
  "function": {
    "name": "write_file",
    "arguments": "{\"path\": \"WIP/TMFxxx/tmfxxx_mock_server.py\", \"content\": \"from fastapi import FastAPI\\n\\napp = FastAPI()\\n\\n@app.get('/tmf-api/resource')\\ndef get_resource():\\n    return {'status': 'mocked'}\"}"
  }
}
```

**SPECIFIC INSTRUCTION FOR COPYING FILES**: If you need to copy a file (like the OpenAPI specification), you must:
1. First use `read_file` to read the content of the source file
2. Then use `write_file` with both `path` and `content` parameters to write the content to the destination
**IMPORTANT: Always copy the spec YAML file to the destination directory so it's available for the generated server.**

**FOR YOUR FIRST TOOL CALL: Use this exact structure to create the mock_server.py file as your starting point, then build on it:**
```json
{
  "id": "call_example",
  "function": {
    "name": "write_file",
    "arguments": "{\"path\": \"WIP/TMF{tmf_number}/tmf{tmf_number}_mock_server.py\", \"content\": \"from tmf_commons import load_openapi_spec, DataGenerator, create_tmf_app, add_event_handlers\\n\\nspec = load_openapi_spec('TMF{tmf_number}-SPEC.yaml')\\ndata_generator = YourDataGenerator(spec)\\napp = create_tmf_app(spec, data_generator=data_generator)\\nadd_event_handlers(app, spec)\"}"
  }
}
```

**CRITICAL DISTINCTION:**
- **Mock Server**: Uses `tmf_commons` with `create_tmf_app()`
- **MCP Server**: Uses the official `mcp` Python SDK (`FastMCP`) - tools are defined explicitly.

## Library Integration
- Use the tmf_commons library for all common functionality.
- Import necessary components: from tmf_commons import load_openapi_spec, DataGenerator, create_tmf_app, add_event_handlers
- Extend classes like DataGenerator for API-specific data generation.
- Use create_tmf_app to build the FastAPI app, passing custom extensions.
- Focus on API-specific customizations; do not regenerate shared code.

## DataGenerator Extension Pattern
**CRITICAL:** When extending DataGenerator, you MUST follow this exact pattern:

```python
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

class YourResourceDataGenerator(DataGenerator):
    """Extended data generator for Your API"""
    
    def __init__(self, spec: Dict[str, Any]):
        super().__init__(spec)  # MUST pass spec to parent
        # Initialize your API-specific data
        self.resource_names = ["Sample Resource 1", "Sample Resource 2"]
        self.statuses = ["active", "inactive"]
        
    def generate_id(self) -> str:
        """Generate a UUID string"""
        return str(uuid.uuid4())
        
    def generate_time_period(self) -> Dict[str, str]:
        """Generate a time period for validFor"""
        start_date = datetime.now() - timedelta(days=random.randint(0, 365))
        end_date = start_date + timedelta(days=random.randint(365, 1095))
        return {
            "startDateTime": start_date.isoformat() + "Z",
            "endDateTime": end_date.isoformat() + "Z"
        }
        
    def generate_resource_data(self) -> Dict[str, Any]:
        """Generate realistic resource data"""
        resource_id = self.generate_id()
        
        return {
            "@type": "YourResource",
            "id": resource_id,
            "href": f"/tmf-api/yourApi/v5/resource/{resource_id}",
            "name": random.choice(self.resource_names),
            "status": random.choice(self.statuses),
            "validFor": self.generate_time_period()
        }
```

**IMPORTANT NOTES:**
- Always import `uuid` for ID generation
- Always import `datetime` and `timedelta` for time periods
- Always call `super().__init__(spec)` in the constructor
- Use proper TMF API URL patterns: `/tmf-api/{apiName}/v{version}/{resource}/{id}`
- Never use `self.base_url` - it doesn't exist in the parent class

## Custom Endpoints and Route Conflicts
**IMPORTANT:**
- If you need to override or customize any endpoint (e.g., for realistic data or business logic), you have TWO options:

**Option 1: Use exclude_paths (Recommended for custom endpoints)**
```python
from tmf_commons import load_openapi_spec, create_tmf_app, add_event_handlers
from fastapi import Request

spec = load_openapi_spec('TMFxxx-SPEC.yaml')
# Exclude paths that you want to define manually
app = create_tmf_app(spec, exclude_paths={'/<resource>', '/<resource>/{id}'})
add_event_handlers(app, spec)

# Now define your custom endpoints - they won't conflict with dynamic routes
@app.post('/<resource>')
async def create_resource(request: Request):
    # ... custom logic ...
    return {"message": "Custom resource created"}

@app.get('/<resource>/{id}')
async def get_resource(id: str):
    # ... custom logic ...
    return {"message": "Custom resource retrieved"}
```

**Option 2: Define custom endpoints after create_tmf_app (Less reliable)**
```python
app = create_tmf_app(spec)
add_event_handlers(app, spec)

# Custom endpoint overrides the generic one from create_tmf_app
@app.post('/<resource>')
async def create_resource(request: Request):
    # ... custom logic ...
    return {"message": "Custom resource created"}
```

**RECOMMENDATION:** Use Option 1 (exclude_paths) for any endpoints where you need custom business logic, validation, or realistic data generation. Only use Option 2 for simple overrides.

**/hub endpoints are optional:** Only implement `/hub` and `/hub/{id}` if you need event subscription support. For most TMF mock servers, these can be omitted unless required by your use case.

## Endpoint Checklist Guidance

- **Analyze the OpenAPI spec** to determine the main resources (e.g., Customer, Product, Service, etc.).
- For each main resource, implement the standard CRUD endpoints as defined in the spec (typically GET, POST, PATCH, DELETE, and optionally PUT for /resource and /resource/{id}).
- Only implement `/hub` and event endpoints if the spec or your use case requires event subscription or notification support.
- For a minimal mock server, you can skip `/hub` and event endpoints unless required.

**Template for your own checklist:**
| Path                | Method | Required? (Y/N) | Notes                |
|---------------------|--------|-----------------|----------------------|
| /<resource>         | GET    |                 |                      |
| /<resource>         | POST   |                 |                      |
| /<resource>/{id}    | GET    |                 |                      |
| /<resource>/{id}    | PATCH  |                 |                      |
| /<resource>/{id}    | DELETE |                 |                      |
| /<resource>/{id}    | PUT    |                 | Optional, if in spec |
| /hub                | POST   |                 | Optional             |
| /hub/{id}           | GET    |                 | Optional             |
| /hub/{id}           | DELETE |                 | Optional             |
| /listener/...       | POST   |                 | Optional, events     |

**Tip:**  
Always check the spec for required/optional endpoints and parameters. Only implement what is needed for your use case.

## Storage Initialization
- If you want to pre-populate storage with sample data, do so after app creation and before running the server. You can add a function or use a post-startup hook.

**CORRECT Storage Usage Pattern:**
```python
# Initialize storage with sample data
@app.on_event("startup")
async def populate_sample_data():
    """Populate storage with sample data"""
    storage = get_storage()
    
    # Add sample resources
    for i in range(5):
        resource_data = data_generator.generate_resource_data()
        if "resource" not in storage:
            storage["resource"] = []
        storage["resource"].append(resource_data)
    
    print(f"Initialized storage with {len(storage.get('resource', []))} sample resources")
```

**IMPORTANT:** 
- `storage` is a dictionary, not an object with methods
- Use `storage["resource"] = []` to initialize arrays
- Use `storage["resource"].append(data)` to add items
- Use `storage.get("resource", [])` to safely get arrays
- Never use `storage.create()` or `storage.list()` - these don't exist

## Your Task
Create a complete TMF MCP server implementation with the following files, using tmf_commons:

**STEP 1: Copy the spec file**
First, copy the OpenAPI specification YAML file to the destination directory:
1. Use `read_file` to read the source spec file
2. Use `write_file` to copy it to the destination directory (e.g., `WIP/TMF{tmf_number}/TMF{tmf_number}-SPEC.yaml`)

**STEP 2: Create the implementation files**
1. **tmf###_mock_server.py** - Extend tmf_commons to implement API-specific logic
2. **tmf###_client.py** - HTTP client (customize if needed)
3. **tmf###_mcp_server.py** - MCP server (use the official `mcp` Python SDK / `FastMCP`, not tmf_commons)
4. **run_mock_server.py** - Script to run the mock server
5. **run_mcp_server.py** - Script to run the MCP server
6. **requirements.txt** - Dependencies (MUST include mcp>=0.9.0)
7. **README.md** - Documentation

### Required Dependencies (requirements.txt)
```
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
pyyaml>=6.0.0
mcp>=0.9.0
```

**CRITICAL:** The `mcp>=0.9.0` dependency is REQUIRED for proper MCP protocol support.

## Step 1: Analyze the TMF OpenAPI Specification
- Load spec using load_openapi_spec
- Identify main resources, operations, schemas
- Handle TMF patterns: allOf, discriminators, events

## Step 2: Create the Mock API Server
- Use create_tmf_app(spec, data_generator=YourDataGenerator)
- Extend DataGenerator for realistic sample data
- Add event handling with add_event_handlers
- **If you need to override any endpoint, define it after calling create_tmf_app/add_event_handlers.**

**IMPORTANT:** The mock server uses tmf_commons, but the MCP server uses the official `mcp` SDK (`FastMCP`). These are different patterns!

## Step 3: Create the MCP Server
**CRITICAL:** The MCP server MUST use the official `mcp` Python SDK (`FastMCP`) for protocol compliance.

### MCP Server Pattern (REQUIRED)
```python
#!/usr/bin/env python3
"""TMF### API MCP Server

Expose TMF### operations as MCP tools.

This MCP server is separate from the mock FastAPI server: it calls the TMF### HTTP client,
which talks to the mock server (or a real TMF endpoint).
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

# Define `tmf###_list_*`, `tmf###_get_*`, `tmf###_create_*`, `tmf###_patch_*`, `tmf###_delete_*`
# as explicit tools that call corresponding TMF###Client methods.

if __name__ == "__main__":
    mcp.run()
```

### Key MCP Server Requirements:
1. **MUST use the official `mcp` Python SDK (`FastMCP`)**: Import and use `FastMCP` class
2. **CORS Middleware**: Add CORS support for web clients
3. **API Endpoints**: Create `/api/*` endpoints that proxy to the mock server
4. **Operation IDs**: Each endpoint MUST have `operation_id="tmf###_{operation}_{resource}"`
5. **MCP Mount**: Use `mcp.mount(mount_path="/mcp")` to expose MCP protocol
6. **Client Integration**: Use the HTTP client to communicate with mock server
7. **Error Handling**: Proper exception handling and logging
8. **CRITICAL: Individual Parameters for Create**: Use individual Body parameters instead of JSON body for MCP tool compatibility

### MCP Tool Naming Convention:
- List: `tmf###_list_{resource}` (e.g., `tmf629_list_customers`)
- Create: `tmf###_create_{resource}` (e.g., `tmf629_create_customer`)
- Get: `tmf###_get_{resource}` (e.g., `tmf629_get_customer`)
- Update: `tmf###_patch_{resource}` (e.g., `tmf629_patch_customer`)
- Delete: `tmf###_delete_{resource}` (e.g., `tmf629_delete_customer`)
- Health: `tmf###_health_check`

## CRITICAL MCP FUNCTION SIGNATURE REQUIREMENTS

**For Resource Creation Endpoints:**
- **DO NOT use**: `resource_data: Dict[str, Any] = Body(...)` 
- **DO use**: Individual parameters like `name: str = Body(...)`, `status: str = Body(...)`, etc.
- **Reason**: MCP tools need individual parameters to be properly exposed as tool arguments
- **Example**: 
  ```python
  # WRONG - won't work with MCP tools
  async def api_create_resource(resource_data: Dict[str, Any] = Body(...)):
  
  # CORRECT - works with MCP tools
  async def api_create_resource(
      name: str = Body(...),
      status: str = Body("active"),
      description: Optional[str] = Body(None)
  ):
  ```

**Resource-Specific Parameter Patterns:**
- **Customers**: `name`, `customer_type`, `status`, `engagement_type`, `phone`, `email`, `address`, `city`, `state`, `postcode`, `country`, `industry`, `employee_count`
- **Products**: `name`, `product_type`, `status`, `category`, `price`, `description`, `manufacturer`
- **Services**: `name`, `service_type`, `status`, `service_level`, `description`, `provider`

## Additional Notes
- Reduce output size by relying on library imports
- Ensure compatibility with TMF patterns
- Generate only what's specific to this API
- **MCP Server MUST use the official `mcp` Python SDK (`FastMCP`) for protocol compliance**
- **If you need to pre-populate storage, do so after app creation.**
- **CRITICAL: Always use individual parameters for create endpoints to ensure MCP tool compatibility** 

