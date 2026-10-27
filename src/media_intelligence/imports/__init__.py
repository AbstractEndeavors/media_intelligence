"""Shared constants and external imports."""

from importlib import import_module as _import_module
from . import init_imports as _lazy

from .constants import (
    _IMAGE_EXTS,
    _VIDEO_EXTS,
    _AUDIO_EXTS,
    _DOC_EXTS,
    _REACT,
    _NGINX,
    _EXTRA_FOR_PACKAGE,
    _LAZY_SUBMODULES,
    _LAYER_PACKAGES,
    _NOT_WIRED,
    TEXT_EXT,
    PROMPT,
    SCHEMA_VERSION,
    ENGINE_VERSION,
)

_EXTERNAL_NAMES = frozenset(_lazy.__all__)
__all__ = ['_IMAGE_EXTS', '_VIDEO_EXTS', '_AUDIO_EXTS', '_DOC_EXTS', '_REACT', '_NGINX', '_EXTRA_FOR_PACKAGE', '_LAZY_SUBMODULES', '_LAYER_PACKAGES', '_NOT_WIRED', 'TEXT_EXT', 'PROMPT', 'SCHEMA_VERSION', 'ENGINE_VERSION', 'Any', 'Blueprint', 'Callable', 'Counter', 'ET', 'Flask', 'ModuleType', 'Optional', 'Path', 'Protocol', 'TYPE_CHECKING', 'Table', 'asdict', 'base64', 'contextmanager', 'csv', 'dataclass', 'docx', 'enum', 'fcntl', 'field', 'flask', 'functools', 'hashlib', 'importlib', 'io', 'json', 'jsonify', 'math', 'mimetypes', 'openpyxl', 'os', 'pdfium', 'pdfplumber', 'posixpath', 're', 'request', 'resource', 'runtime_checkable', 'safe_dump_to_json', 'safe_load_from_json', 'subprocess', 'sys', 'tempfile', 'threading', 'time', 'urllib', 'zipfile']


def __getattr__(name):
    if name not in _EXTERNAL_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_lazy, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
