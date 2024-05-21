import sys
from typing import Literal

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


DataFrameType: TypeAlias = Literal["pandas", "polars"]

MarkdownTypes: TypeAlias = Literal[
    "python", "r", "sql", "json", "markdown", "html", "text", "none"
]
