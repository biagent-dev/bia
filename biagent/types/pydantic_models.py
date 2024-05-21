from typing import Optional

from pydantic import BaseModel, RootModel


class MetaField(BaseModel):
    name: str
    type: str
    description: str = ""
    # list of fields in GSM soft file that contain this information
    # e.g., `Series_title`, `Sample_description`
    ref: Optional[list[str]] = None
    # list of options for this field
    options: Optional[list[str]] = None
    # if True, copy the value from ref field
    # assert len(ref) == 1 if copy_from_ref is True
    copy_from_ref: Optional[bool] = False
    # if True, map the value to UMLS concepts
    map_to_umls: Optional[bool] = False


class MetaFieldList(RootModel):
    root: list[MetaField]
