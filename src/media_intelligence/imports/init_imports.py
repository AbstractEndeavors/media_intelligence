"""External names used by this package, loaded on demand."""

from hugpy_resources.lazy_imports import import_registry, resolve_import

_IMPORTS = import_registry({
    'typing': 'Any Callable Optional Protocol TYPE_CHECKING runtime_checkable',
    'flask': 'Blueprint Flask flask= jsonify request',
    'collections': 'Counter',
    'xml.etree.ElementTree': 'ET=',
    'types': 'ModuleType',
    'pathlib': 'Path',
    'docx.table': 'Table',
    'dataclasses': 'asdict dataclass field',
    'base64': 'base64=',
    'contextlib': 'contextmanager',
    'csv': 'csv=',
    'docx': 'docx=',
    'enum': 'enum=',
    'fcntl': 'fcntl=',
    'functools': 'functools=',
    'hashlib': 'hashlib=',
    'importlib.util': 'importlib=',
    'io': 'io=',
    'json': 'json=',
    'math': 'math=',
    'mimetypes': 'mimetypes=',
    'openpyxl': 'openpyxl=',
    'os': 'os=',
    'pypdfium2': 'pdfium=',
    'pdfplumber': 'pdfplumber=',
    'posixpath': 'posixpath=',
    're': 're=',
    'resource': 'resource=',
    'abstract_essentials': 'safe_dump_to_json safe_load_from_json',
    'subprocess': 'subprocess=',
    'sys': 'sys=',
    'tempfile': 'tempfile=',
    'threading': 'threading=',
    'time': 'time=',
    'urllib.error': 'urllib=',
    'zipfile': 'zipfile=',
})
__all__ = list(_IMPORTS)


def __getattr__(name):
    return resolve_import(globals(), _IMPORTS, name)


def __dir__():
    return sorted(set(globals()) | set(__all__))
