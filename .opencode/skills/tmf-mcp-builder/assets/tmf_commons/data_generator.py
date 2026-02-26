import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

class DataGenerator:
    def __init__(self, spec: Dict):
        self.spec = spec

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

    def generate_contextual_fallback_data(self, ref_path: str) -> Any:
        """Generate contextual fallback data for common TMF references (from prompt)"""
        ref_name = ref_path.split('/')[-1]
        
        if 'PartyRole' in ref_name:
            return {
                "id": str(uuid.uuid4()),
                "href": f"/tmf-api/customer/v5/partyRole/{uuid.uuid4()}",
                "name": f"Party Role {random.randint(1000, 9999)}",
                "description": f"Description for {ref_name}",
                "role": "customer",
                "status": "active",
                "@type": ref_name
            }
        # ... (add more from your prompt's full function)
        else:
            return {
                "id": str(uuid.uuid4()),
                "href": f"/tmf-api/{ref_name.lower()}/{uuid.uuid4()}",
                "name": f"{ref_name} {random.randint(1000, 9999)}"
            }

    def generate_sample_data(self, schema: Dict[str, Any], path: str = "", property_name: str = "") -> Any:
        """Generate realistic sample data based on OpenAPI schema (enhanced from TMF637 reference)"""
        # Handle $ref
        if '$ref' in schema:
            ref_path = schema['$ref']
            if ref_path.startswith('#/'):
                parts = ref_path[2:].split('/')
                ref_schema = self.spec
                for part in parts:
                    ref_schema = ref_schema.get(part, {})
                if ref_schema:
                    return self.generate_sample_data(ref_schema, path, property_name)
            return self.generate_contextual_fallback_data(ref_path)
        
        # Handle allOf (from prompt)
        if 'allOf' in schema:
            result = {}
            for sub_schema in schema['allOf']:
                sub_data = self.generate_sample_data(sub_schema, path, property_name)
                if isinstance(sub_data, dict):
                    result.update(sub_data)
            return result
        
        # Handle types (enhanced with TMF637's contextual logic)
        schema_type = schema.get('type', 'object')
        if schema_type == 'object':
            result = {}
            for prop_name, prop_schema in schema.get('properties', {}).items():
                prop_path = f"{path}.{prop_name}" if path else prop_name
                result[prop_name] = self.generate_sample_data(prop_schema, prop_path, prop_name)
            return result
        elif schema_type == 'array':
            items_schema = schema.get('items', {})
            count = random.randint(1, 3)
            return [self.generate_sample_data(items_schema, f"{path}[{i}]", property_name) for i in range(count)]
        elif schema_type == 'string':
            # TMF637-style contextual generation
            if 'id' in property_name.lower():
                return str(uuid.uuid4())
            elif 'name' in property_name.lower():
                return f"Sample {property_name.title()} {random.randint(1, 100)}"
            # ... (add more from TMF637's full logic)
            else:
                return "sample-value"
        # Add handling for number, integer, boolean, etc. (from prompt/TMF637)

    def initialize_storage(self, resource: str, schema_name: str, count: int = 5) -> None:
        """Pre-populate storage with sample data (from TMF637 reference)"""
        schema = self.spec['components']['schemas'].get(schema_name, {})
        items = [self.generate_sample_data(schema) for _ in range(count)]
        for item in items:
            item['id'] = str(uuid.uuid4())
        storage[resource] = items  # Assuming global storage; adjust as needed 