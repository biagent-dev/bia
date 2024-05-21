from enum import Enum

from .pydantic_models import MetaField, MetaFieldList


class FileType(Enum):
    RDATA = 1
    MTX = 2
    TABLE = 3
    H5 = 4
    H5AD = 5
    UNKNOWN = 6
