import json

from GEOparse.GEOTypes import GSE, GSM, NoMetadataException
from modelscope_agent.llm import get_chat_model
from modelscope_agent.llm.base import BaseChatModel
from modelscope_agent.tools.base import BaseTool, register_tool
from modelscope_agent.utils.tokenization_utils import count_tokens

from biagent import prompts
from biagent.configs.metadata import DEFAULT_META_FIELD_GROUP
from biagent.types import MetaFieldList
from biagent.utils import geo_helper
from biagent.utils.logger import biagent_logger as logger
from biagent.utils.output_parser import parse_json_markdown


@register_tool("geo_metadata_extraction")
class GeoMetadataExtraction(BaseTool):
    description = "Extract metadata from GEO based on sample ID"
    name = "geo-metadata-extraction"
    parameters: list = [
        {
            "name": "id",
            "type": "string",
            "description": "a valid GEO sample ID, e.g., GSM2856250",
            "required": True,
        }
    ]

    def __init__(
        self,
        llm: dict | BaseChatModel | None,
        meta_field_groups: list[MetaFieldList] | None = None,
        cfg: dict | None = {},
    ):
        super().__init__(cfg)
        if isinstance(llm, dict):
            self.llm_config = llm
            self.llm = get_chat_model(**self.llm_config)
        else:
            self.llm = llm
        if meta_field_groups:
            self.meta_field_groups = meta_field_groups
        else:
            # copy_from_ref field should be in its own group
            meta_field_groups = [[]]
            for meta_field in DEFAULT_META_FIELD_GROUP.root:
                if meta_field.copy_from_ref:
                    meta_field_groups.append([meta_field])
                else:
                    meta_field_groups[0].append(meta_field)
            self.meta_field_groups = [MetaFieldList(root=g) for g in meta_field_groups]

        self.umls_mapper = geo_helper.UMLSMapper(threshold=0.5)

    def _get_metadata_as_string(self, gsm: GSM, max_tokens: int = 1000):
        """Get the metadata as SOFT formatted string."""
        metalist = []
        for metaname, meta in gsm.metadata.items():
            assert isinstance(
                meta, list
            ), "Single value in metadata dictionary should be a list!"
            for data in meta:
                if data:
                    meta_str = "!%s_%s = %s" % (
                        gsm.geotype.capitalize(),
                        metaname,
                        data,
                    )
                    if count_tokens(meta_str) < max_tokens:
                        metalist.append(meta_str)
                    else:
                        logger.error(
                            f"Metadata `{metaname}` is too long. Likely a unhelpful field. Skip it."
                        )
        return "\n".join(metalist)

    def _construct_context(
        self, gsm: GSM, gse: GSE, refs: list[str] | None = None
    ) -> str:
        metadata_field_content = []
        metadata_str = ""
        if refs is None:
            refs = []
        for ref_field in refs:
            if ref_field.startswith("Sample_"):
                for field in gsm.metadata:
                    if ref_field.replace("Sample_", "") in field:
                        metadata_field_content.append(gsm.get_metadata_attribute(field))
                        metadata_str += (
                            f"{ref_field} = {gsm.get_metadata_attribute(field)}\n"
                        )
            elif gse is not None and ref_field.startswith("Series_"):
                for field in gse.metadata:
                    if ref_field.replace("Series_", "") in field:
                        metadata_field_content.append(gse.get_metadata_attribute(field))
                        metadata_str += (
                            f"{ref_field} = {gse.get_metadata_attribute(field)}\n"
                        )
        if metadata_str == "":
            metadata_str = self._get_metadata_as_string(gsm)
            # adding some necessary GSE metadata
            for field in ["title", "overall_design", "supplementary_file"]:
                try:
                    metadata_str += (
                        f"!Series_{field} = {gse.get_metadata_attribute(field)}\n"
                    )
                except NoMetadataException:
                    continue
        return metadata_str

    def _construct_response_format(self, meta_field_group: MetaFieldList) -> str:
        response_fields_str = ""
        for i, meta_field in enumerate(meta_field_group.root):
            note_str = ""
            note_str += meta_field.description
            if meta_field.options is not None and len(meta_field.options) > 0:
                note_str += " Choose from: " + ", ".join(
                    [f"`{x}`" for x in meta_field.options]
                )
            if i + 1 == len(meta_field_group.root):
                response_fields_str += (
                    f'  "{meta_field.name}": {meta_field.type} \\ {note_str}'
                )
            else:
                response_fields_str += (
                    f'  "{meta_field.name}": {meta_field.type}, \\ {note_str}\n'
                )
        return "```json\n{\n" + response_fields_str + "\n}\n```\n"

    def parse_gsm(self, gsm: GSM, gse: GSE) -> dict:
        """
        Parse the metadata of a GSM and return a dictionary.

        Args:
            gsm: GSM object
            gse: GSE object
        Returns:
            dict: dictionary of metadata
        """
        final = {"gsm": gsm.get_accession()}

        for meta_field_group in self.meta_field_groups:
            if (
                len(meta_field_group.root) == 1
                and meta_field_group.root[0].copy_from_ref
                and len(meta_field_group.root[0].ref) == 1
            ):
                meta_field = meta_field_group.root[0]
                # just copy the value from the metadata field!
                try:
                    if meta_field.ref[0].startswith("Series_"):
                        final[meta_field.name] = gse.get_metadata_attribute(
                            meta_field.ref[0].replace("Series_", "")
                        )
                    else:
                        final[meta_field.name] = gsm.get_metadata_attribute(
                            meta_field.ref[0].replace("Sample_", "")
                        )
                except NoMetadataException:
                    final[meta_field.name] = None
                if isinstance(final[meta_field.name], list):
                    final[meta_field.name] = ";".join(final[meta_field.name])
            else:
                if all(field.ref is not None for field in meta_field_group.root):
                    refs = set(
                        [r for field in meta_field_group.root for r in field.ref]
                    )
                else:
                    refs = None
                context_str = self._construct_context(gsm, gse, refs)
                response_fields_str = self._construct_response_format(meta_field_group)
                prompt = prompts.metadata.render(
                    metadata=context_str, response_fields=response_fields_str
                )
                try:
                    logger.info(f"Input tokens: {count_tokens(prompt)}")

                    step_reply = self.llm.chat(prompt)
                    if "Error" in step_reply:
                        raise ValueError(f"Error parsing metadata: {step_reply}")
                    parsed_meta_with_ref = parse_json_markdown(step_reply)
                    for meta_field in meta_field_group.root:
                        if meta_field.name in parsed_meta_with_ref:
                            final[meta_field.name] = parsed_meta_with_ref[
                                meta_field.name
                            ]
                            if meta_field.map_to_umls:
                                final[meta_field.name + "_umls"] = self.umls_mapper(
                                    parsed_meta_with_ref[meta_field.name]
                                )
                        else:
                            final[meta_field.name] = None

                except KeyboardInterrupt as exce:
                    raise KeyboardInterrupt from exce
                except Exception as e:
                    logger.error(f"Error parsing metadata: {e}")
                    for meta_field in meta_field_group.root:
                        final[meta_field.name] = None

        final["raw_metadata"] = self._get_metadata_as_string(gsm)
        return final

    def call(self, params: str, **kwargs) -> str:
        params = self._verify_args(params)
        gsm_id = params.get("id")
        if not gsm_id.startswith("GSM"):
            raise ValueError("Invalid GSM ID")
        gsm, gse = geo_helper.get_geo(gsm_id, return_gse=True)
        extracted_metadata = self.parse_gsm(gsm, gse)
        return json.dumps(extracted_metadata, ensure_ascii=False, indent=4)
