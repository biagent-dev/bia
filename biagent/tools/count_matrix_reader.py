from jinja2 import Template
from modelscope_agent.llm import get_chat_model
from modelscope_agent.llm.base import BaseChatModel
from modelscope_agent.tools.base import BaseTool, register_tool
from scanpy import AnnData

from biagent import prompts
from biagent.types import FileType
from biagent.utils import geo_helpers
from biagent.utils.code_runner import safe_exec_func
from biagent.utils.llm_helpers import get_chat_model
from biagent.utils.output_parser import parse_python_markdown


@register_tool("geo_count_matrix_reader")
class GeoCountMatrixReader(BaseTool):
    description = "Read the count matrix from a given GEO sample ID as Anndata object"
    name = "geo-count-matrix-reader"
    parameters: list = [
        {
            "name": "id",
            "type": "string",
            "description": "a valid GEO sample ID, e.g., GSM2856250",
            "required": True,
        }
    ]

    prompt_templates: dict[FileType, Template] = {
        FileType.MTX: prompts.mtx_reader,
        FileType.TABLE: prompts.table_reader,
    }

    def __init__(
        self,
        llm: str | dict | BaseChatModel,
        cfg: dict | None = {},
    ):
        super().__init__(cfg)
        self.llm = get_chat_model(llm)

    def _construct_context(self, file_content: dict) -> str:
        final_str = "### SUPP FILES\n"
        for j, gsm_file in enumerate(file_content["files"]):
            final_str += f"\nFile {j+1}: `{gsm_file}`\n"
            final_str += f'\n```\n{file_content["content"][j]}\n```'
        return final_str

    def process_gsm(self, gsm_id: str) -> AnnData:
        # step 1: determine whether using supp files or process fastq files
        file_content = geo_helpers.get_supp_data(gsm_id)
        if len(file_content["files"]) == 0:
            raise ValueError("No supplementary file found")
        # step 2: Anndata reading
        file_type = geo_helpers.check_file_type(file_content)

        if file_type == FileType.UNKNOWN:
            raise ValueError("Unknown file type")
        context = self._construct_context(file_content)

        template = self.prompt_templates[file_type]
        prompt = template.render(files=context, folder_path=file_content["dir"])

        reply = self.llm.chat(prompt)
        if "Error" in reply:
            raise ValueError(f"Error reading count matrix: {reply}")

        code = parse_python_markdown(reply)
        final_result = safe_exec_func(code, param_space={})
        if "adata" not in final_result or not isinstance(
            final_result["adata"], AnnData
        ):
            raise ValueError(f"Error reading count matrix: {reply}")
        adata = final_result["adata"]
        return adata

    def call(self, params: str, **kwargs) -> str:
        params = self._verify_args(params)
        gsm_id = params.get("id")
        if not gsm_id.startswith("GSM"):
            raise ValueError("Invalid GSM ID")

        try:
            count_matrix = self.process_gsm(gsm_id)
        except ValueError as e:
            return str(e)
        return str(count_matrix)
