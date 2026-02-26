import yaml
import logging
from typing import Dict, Any

logger = logging.getLogger("tmf_commons.schema_utils")

def load_openapi_spec(yaml_path: str) -> Dict[str, Any]:
    """Load and parse the OpenAPI specification from a YAML file (reusable from prompt)"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load OpenAPI spec: {e}")
        raise 