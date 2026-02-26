# MCP Server Creation Guidelines

## Overview
This document provides guidelines for creating MCP servers that properly support resource creation operations, based on lessons learned from the TMF629 Customer Management API implementation.

## Key Problem Solved
The original MCP server implementation had a critical issue where the create resource function only accepted a `random_string` parameter instead of the actual resource data parameters. This prevented proper resource creation through MCP tools.

## Critical Requirements for MCP Resource Creation

### 1. Function Signature Pattern
**WRONG Pattern (Doesn't work with MCP tools):**
```python
@app.post("/api/{resource}", operation_id="tmf###_create_{resource}")
async def api_create_resource(
    resource_data: Dict[str, Any] = Body(..., description="Resource data")
):
```

**CORRECT Pattern (Works with MCP tools):**
```python
@app.post("/api/{resource}", operation_id="tmf###_create_{resource}")
async def api_create_resource(
    name: str = Body(..., description="Resource name"),
    status: str = Body("active", description="Resource status"),
    description: Optional[str] = Body(None, description="Resource description"),
    # Add other resource-specific parameters
):
```

### 2. Resource-Specific Parameter Patterns

#### For Customer Management APIs:
```python
async def api_create_customer(
    name: str = Body(..., description="Customer name"),
    customer_type: str = Body("organization", description="Customer type"),
    status: str = Body("active", description="Customer status"),
    engagement_type: str = Body("B2B", description="Engagement type"),
    phone: Optional[str] = Body(None, description="Primary phone number"),
    email: Optional[str] = Body(None, description="Primary email address"),
    address: Optional[str] = Body(None, description="Primary address"),
    city: Optional[str] = Body(None, description="City"),
    state: Optional[str] = Body(None, description="State or province"),
    postcode: Optional[str] = Body(None, description="Postal code"),
    country: Optional[str] = Body("USA", description="Country"),
    industry: Optional[str] = Body(None, description="Industry (for organizations)"),
    employee_count: Optional[int] = Body(None, description="Employee count (for organizations)")
):
```

#### For Product Management APIs:
```python
async def api_create_product(
    name: str = Body(..., description="Product name"),
    product_type: str = Body("physical", description="Product type"),
    status: str = Body("active", description="Product status"),
    category: Optional[str] = Body(None, description="Product category"),
    price: Optional[float] = Body(None, description="Product price"),
    description: Optional[str] = Body(None, description="Product description"),
    manufacturer: Optional[str] = Body(None, description="Manufacturer"),
    sku: Optional[str] = Body(None, description="SKU code")
):
```

#### For Service Management APIs:
```python
async def api_create_service(
    name: str = Body(..., description="Service name"),
    service_type: str = Body("basic", description="Service type"),
    status: str = Body("active", description="Service status"),
    service_level: Optional[str] = Body(None, description="Service level"),
    description: Optional[str] = Body(None, description="Service description"),
    provider: Optional[str] = Body(None, description="Service provider"),
    cost: Optional[float] = Body(None, description="Service cost")
):
```

### 3. Data Structure Building
Always build the proper TMF data structure from individual parameters:

```python
# Build resource data structure
resource_data = {
    "@type": "YourResource",  # Replace with actual resource type
    "name": name,
    "status": status
}

# Add optional fields if provided
if description:
    resource_data["description"] = description

# Add resource-specific logic
if customer_type:
    resource_data["customerType"] = customer_type

# Build contact mediums for customers
if phone or email or address:
    contact_mediums = []
    if phone:
        contact_mediums.append({
            "@type": "TelephoneContactMedium",
            "mediumType": "phone",
            "number": phone,
            "preferred": True
        })
    # Add email and address logic...
    
    if contact_mediums:
        resource_data["contactMedium"] = contact_mediums

# Call the client
result = await tmf###_client.create_{resource}(resource_data)
```

### 4. MCP Tool Naming Convention
Ensure consistent naming across all endpoints:
- List: `tmf###_list_{resource}`
- Create: `tmf###_create_{resource}`
- Get: `tmf###_get_{resource}`
- Update: `tmf###_patch_{resource}`
- Delete: `tmf###_delete_{resource}`
- Health: `tmf###_health_check`

### 5. Operation ID Pattern
Each endpoint must have the correct operation_id:
```python
@app.post("/api/{resource}", operation_id="tmf###_create_{resource}")
@app.get("/api/{resource}", operation_id="tmf###_list_{resource}")
@app.get("/api/{resource}/{id}", operation_id="tmf###_get_{resource}")
@app.patch("/api/{resource}/{id}", operation_id="tmf###_patch_{resource}")
@app.delete("/api/{resource}/{id}", operation_id="tmf###_delete_{resource}")
```

## Implementation Checklist

### Before Implementation:
- [ ] Analyze the OpenAPI spec to identify main resources
- [ ] Determine required and optional fields for each resource
- [ ] Plan the parameter structure for create operations
- [ ] Identify resource-specific characteristics and relationships

### During Implementation:
- [ ] Use individual Body parameters for create endpoints
- [ ] Build proper TMF data structures from parameters
- [ ] Handle resource-specific logic (contact mediums, characteristics, etc.)
- [ ] Use correct operation_id patterns
- [ ] Implement proper error handling

### After Implementation:
- [ ] Test resource creation through API endpoints
- [ ] Verify MCP tools are properly exposed
- [ ] Test resource creation through MCP tools
- [ ] Validate data structure compliance with TMF standards

## Common Pitfalls to Avoid

1. **Using JSON Body for Create Operations**: This prevents MCP tools from working properly
2. **Missing Operation IDs**: Without proper operation_id, MCP tools won't be generated
3. **Inconsistent Parameter Names**: Ensure parameter names match the expected TMF structure
4. **Missing Resource-Specific Logic**: Don't forget to handle resource-specific fields and relationships
5. **Poor Error Handling**: Always implement proper exception handling and logging

## Testing Guidelines

### API Testing:
```bash
# Test resource creation
curl -X POST "http://localhost:8###/api/{resource}" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Resource", "status": "active"}'

# Test resource listing
curl -X GET "http://localhost:8###/api/{resource}"
```

### MCP Tool Testing:
- Verify MCP tools are available in the client
- Test resource creation through MCP tools
- Validate that created resources appear in listings
- Check that resource-specific fields are properly handled

## Summary

The key to successful MCP server implementation for resource creation is:
1. **Use individual parameters** instead of JSON body for create operations
2. **Build proper data structures** from individual parameters
3. **Follow consistent naming conventions** for operation IDs
4. **Handle resource-specific logic** appropriately
5. **Test thoroughly** through both API and MCP interfaces

By following these guidelines, future MCP servers will properly support resource creation operations regardless of the specific TMF API being implemented. 