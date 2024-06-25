from joblib import Memory
from modelscope_agent.llm.base import BaseChatModel
from modelscope_agent.tools.base import BaseTool, register_tool

from biagent import prompts
from biagent.utils.llm_helpers import get_chat_model, get_valid_json_response
from biagent.utils.logger import biagent_logger as logger
from biagent.utils.pipeline_helpers import (
    CellTypeToolMetadata,
    ParagraphRotator,
    Pipeline,
    ToolMetadata,
)


@register_tool("pipeline_extractor")
class PipelineExtractor(BaseTool):
    description = "Extract the pipeline from a given paper"
    name = "pipeline-extractor"
    parameters: list = [
        {
            "name": "parsed_paper",
            "type": "string",
            "description": "path to the paper, assuming the paper is in `md` format",
            "required": True,
        }
    ]

    def __init__(
        self,
        llm: str | dict | BaseChatModel,
        cfg: dict | None = {},
        cache: bool = False,
    ):
        super().__init__(cfg)
        self.llm = get_chat_model(llm)
        self.mem = Memory(location=".cache", verbose=0)
        if cache:
            self.get_valid_json_response = self.mem.cache(
                get_valid_json_response, ignore=["llm", "validator"]
            )
        else:
            self.get_valid_json_response = get_valid_json_response

    def _extract_tool(
        self,
        task_type: str,
        current_task_name: str,
        current_task_dependencies: list[str],
        current_task_descendants: list[str],
        content: ParagraphRotator,
        tools_extracted: list,
    ) -> ToolMetadata:
        if task_type == "cell_type_process":
            tool_type = CellTypeToolMetadata
        elif task_type == "process":
            tool_type = ToolMetadata
        else:
            raise ValueError(f"Invalid task type: {task_type}")
        while content.has_next():
            paragraph = content.get()
            prompt = prompts.pipeline_extractor.render(
                paragraph=paragraph,
                current_task_name=current_task_name,
                current_task_dependencies=current_task_dependencies,
                current_task_descendants=current_task_descendants,
                tools_extracted=tools_extracted,
                tool_fields=[
                    {
                        "name": field,
                        "type": str(content.annotation).replace(" | None", ""),
                    }
                    for field, content in tool_type.model_fields.items()
                ],
            )

            def validator(json_string: dict) -> bool:
                for field in ["task_exists", "task_name"]:
                    if field not in json_string:
                        return False
                try:
                    if json_string["task_exists"]:
                        tool_type.model_validate(json_string["tool_info"])
                    return True
                except:
                    return False

            response = self.get_valid_json_response(
                prompt, self.llm, validator=validator
            )

            if response["task_exists"] and response["task_name"] == current_task_name:
                return tool_type.model_validate(response["tool_info"])
            else:
                content.step()

    def extract_pipeline(self, path: str, output_file: str = None):
        with open(path, "r") as f:
            paper_content = f.read()

        ## we assume the above functionality has been implemented
        methods_section = ParagraphRotator(paper_content, min_word_limit=200)

        # step 2: let's load the pipeline and extract the tools and metadata
        pipeline = Pipeline()
        tools_extracted = []
        for node in pipeline.iter_nodes():
            if node.tool_required:
                last_index = methods_section.index
                current_task_name = node.name
                current_task_dependencies = pipeline.predecessor_labels(node.id)

                current_task_descendants = pipeline.successor_labels(node.id)
                tool = self._extract_tool(
                    node.type,
                    current_task_name,
                    current_task_dependencies,
                    current_task_descendants,
                    methods_section,
                    tools_extracted,
                )

                if tool is None:
                    # reset the index
                    methods_section.index = last_index
                else:
                    pipeline.set_node(node, tool)
                    logger.info(f"Extracted tool for {node.id}: {tool}")

                    tools_extracted.append(
                        {"task_name": node.name, **tool.model_dump()}
                    )

        if output_file is not None:
            logger.info(f"Saving pipeline to {output_file}")
            pipeline.save(filename=output_file, save_as=output_file.split(".")[-1])

    def call(self, params: str, **kwargs) -> str:
        params = self._verify_args(params)
        path = params.get("parsed_paper")
        return self.extract_pipeline(path)
