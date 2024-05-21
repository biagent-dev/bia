import argparse
import json

import pandas as pd
import tqdm
from GEOparse.GEOTypes import GSE, GSM
from joblib import Memory, Parallel, delayed

from biagent.tools import GeoCountMatrixReader, GeoMetadataExtraction
from biagent.utils import geo_helper
from biagent.utils.logger import biagent_logger as logger


def _metadata_task(
    gsm_id: str = None,
    model: str = "qwen1.5-72b-chat",
    gsm: GSM = None,
    gse: GSE = None,
    tool: GeoMetadataExtraction = None,
) -> dict:
    assert gsm_id is not None or gsm is not None
    if gsm is None:
        gsm, gse = geo_helper.get_geo(gsm_id, return_gse=True)

    if tool is None:
        llm_config = {
            "model": model,
            "model_server": "dashscope",
        }
        tool = GeoMetadataExtraction(llm=llm_config)
    extracted_metadata = tool.parse_gsm(gsm, gse)
    return extracted_metadata


def _metadata_task_soft_file_list(
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
            delayed(geo_helper.process_soft_files)(f, max_gsms_per_gse=max_gsms_per_gse)
            for f in tqdm.tqdm(soft_files, disable=not progress)
        )
        for t in tup
    ]
    if cache_dir is not None:
        logger.info(f"Caching GSM and GSE objects to {cache_dir}")
        _metadata_task_cached = Memory(location=cache_dir, verbose=0).cache(
            _metadata_task, ignore=["tool"]
        )
    else:
        _metadata_task_cached = _metadata_task

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


def cli():
    parser = argparse.ArgumentParser(
        description="A CLI tool to run biagent",
    )
    parser.add_argument("--model", type=str, default="qwen1.5-72b-chat")
    subparsers = parser.add_subparsers(dest="subparser_name")

    metadata_subparser = subparsers.add_parser(
        "metadata", help="GEO Sample metadata extraction"
    )
    metadata_subparser.add_argument(
        "--gsm_id", type=str, help="GSM ID", required=False, default=None
    )
    metadata_subparser.add_argument(
        "--soft_file_list",
        type=str,
        required=False,
        default=None,
        help="The file contains a list of soft files to be processed",
    )
    metadata_subparser.add_argument(
        "--max_gsms_per_gse",
        type=int,
        required=False,
        default=2,
        help="The maximum number of GSM to be processed per GSE",
    )
    metadata_subparser.add_argument(
        "--parallel",
        type=int,
        required=False,
        default=1,
        help="The number of parallel tasks",
    )
    metadata_subparser.add_argument(
        "--output",
        type=str,
        required=False,
        help="The output file path",
    )
    metadata_subparser.add_argument(
        "--cache_dir",
        type=str,
        required=False,
        default=None,
        help="The cache directory",
    )
    count_matrix_subparser = subparsers.add_parser(
        "count_matrix", help="Read the count matrix from a chosen GEO sample"
    )
    count_matrix_subparser.add_argument(
        "--gsm_id",
        type=str,
        help="a valid GEO sample ID",
        required=True,
    )
    count_matrix_subparser.add_argument(
        "--output",
        type=str,
        required=True,
        help="The output h5ad file path",
    )
    geo_search_subparser = subparsers.add_parser(
        "geo_search", help="Search GEO for samples"
    )

    geo_search_subparser.add_argument("query", type=str, help="The query string")

    args = parser.parse_args()

    if args.subparser_name == "metadata":
        if args.gsm_id:
            metadatas = [_metadata_task(args.gsm_id, args.model)]
        elif args.soft_file_list:
            assert args.output is not None, "Please provide output file path"
            metadatas = _metadata_task_soft_file_list(
                args.soft_file_list,
                args.max_gsms_per_gse,
                args.model,
                args.parallel,
                cache_dir=args.cache_dir,
            )
        else:
            raise ValueError("Please provide either gsm_id or soft_file_list")
        if args.output:
            df = pd.DataFrame(metadatas)
            df.to_csv(args.output, index=False, encoding="utf-8")
        else:
            print(metadatas)
    elif args.subparser_name == "geo_search":
        results = geo_helper.search_geo_records(args.query)
        print(json.dumps(results, indent=2))
    elif args.subparser_name == "count_matrix":
        count_matrix_reader = GeoCountMatrixReader(
            llm={"model": args.model, "model_server": "dashscope"}
        )
        adata = count_matrix_reader.process_gsm(args.gsm_id)
        adata.write_h5ad(args.output)
    else:
        raise NotImplementedError
