from .schema_utils import load_openapi_spec
from .data_generator import DataGenerator
from .api_builder import create_tmf_app
from .event_utils import add_event_handlers
import uuid

def get_storage():
    """Get the global data storage"""
    from .api_builder import data_storage
    return data_storage

def generate_uuid():
    """Generate a UUID string"""
    return str(uuid.uuid4())

__all__ = [
    'load_openapi_spec',
    'DataGenerator',
    'create_tmf_app',
    'add_event_handlers',
    'get_storage',
    'generate_uuid'
] 