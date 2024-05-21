import json

from modelscope_agent.tools.base import BaseTool, register_tool

from biagent.utils.geo_helper import search_geo_records


@register_tool("geo_search")
class GeoSearch(BaseTool):
    description = "Search for GEO samples based on the given query"
    name = "geo-search"
    parameters: list = [
        {
            "name": "query",
            "type": "string",
            "description": "a query string to search for GEO samples",
            "required": True,
        }
    ]

    def call(self, params: str, **kwargs) -> str:
        params = self._verify_args(params)
        query = params.get("query")
        res = search_geo_records(query)
        return json.dumps(res)
