import tqdm
from GEOparse.GEOTypes import GSE, GSM
from joblib import Memory, Parallel, delayed

from biagent.tools import GeoMetadataExtraction
from biagent.utils import geo_helpers
from biagent.utils.llm_helpers import get_llm_config
from biagent.utils.logger import biagent_logger as logger


def metadata_task(
    gsm_id: str = None,
    model: str = "qwen1.5-72b-chat",
    gsm: GSM = None,
    gse: GSE = None,
    tool: GeoMetadataExtraction = None,
) -> dict:
    assert gsm_id is not None or gsm is not None
    if gsm is None:
        gsm, gse = geo_helpers.get_geo(gsm_id, return_gse=True)

    if tool is None:
        llm_config = get_llm_config(model)
        tool = GeoMetadataExtraction(llm=llm_config)
    extracted_metadata = tool.parse_gsm(gsm, gse)
    return extracted_metadata


def metadata_task_soft_file_list(
    soft_file_list: str,
    max_gsms_per_gse: int,
    model: str,
    parallel: int,
    progress: bool = True,
    cache_dir: str = None,
) -> list[dict]:
    with open(soft_file_list, "r") as f:
        soft_files = [l.strip() for l in f.readlines()]

    logger.info(f"Reading content from {len(soft_files)} soft files")
    llm_config = {
        "model": model,
        "model_server": "dashscope",
    }
    tool = GeoMetadataExtraction(llm=llm_config)

    gsms = [
        t
        for tup in Parallel(n_jobs=parallel)(
            delayed(geo_helpers.process_soft_files)(
                f, max_gsms_per_gse=max_gsms_per_gse
            )
            for f in tqdm.tqdm(soft_files, disable=not progress)
        )
        for t in tup
    ]
    if cache_dir is not None:
        logger.info(f"Caching GSM and GSE objects to {cache_dir}")
        _metadata_task_cached = Memory(location=cache_dir, verbose=0).cache(
            metadata_task, ignore=["tool"]
        )
    else:
        _metadata_task_cached = metadata_task

    if parallel == 1:
        extracted_metadatas = [
            _metadata_task_cached(gsm=gsm, gse=gse, model=model, tool=tool)
            for gsm, gse in tqdm.tqdm(gsms, disable=not progress)
        ]
    else:
        extracted_metadatas = Parallel(n_jobs=parallel, backend="threading")(
            delayed(_metadata_task_cached)(gsm=gsm, gse=gse, model=model, tool=tool)
            for gsm, gse in tqdm.tqdm(gsms, disable=not progress)
        )
    return extracted_metadatas
