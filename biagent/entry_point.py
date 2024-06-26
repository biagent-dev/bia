import argparse
import json

import pandas as pd

from biagent.tools import GeoCountMatrixReader, PipelineExtractor
from biagent.utils import geo_helpers
from biagent.utils.metadata_helpers import metadata_task, metadata_task_soft_file_list


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

    pipeline_extractor_subparser = subparsers.add_parser(
        "pipeline_extractor", help="Extract the pipeline from a given paper"
    )
    pipeline_extractor_subparser.add_argument(
        "--parsed_paper",
        type=str,
        help="path to the paper in `md` format",
        required=True,
    )
    pipeline_extractor_subparser.add_argument(
        "--output",
        type=str,
        help="path to the output pipeline file, html or json",
        required=True,
    )

    args = parser.parse_args()

    if args.subparser_name == "metadata":
        if args.gsm_id:
            metadatas = [metadata_task(args.gsm_id, args.model)]
        elif args.soft_file_list:
            assert args.output is not None, "Please provide output file path"
            metadatas = metadata_task_soft_file_list(
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
        results = geo_helpers.search_geo_records(args.query)
        print(json.dumps(results, indent=2))
    elif args.subparser_name == "count_matrix":
        count_matrix_reader = GeoCountMatrixReader(llm=args.model)
        adata = count_matrix_reader.process_gsm(args.gsm_id)
        adata.write_h5ad(args.output)
    elif args.subparser_name == "pipeline_extractor":
        pipeline_extractor = PipelineExtractor(llm=args.model)

        pipeline_extractor.extract_pipeline(args.parsed_paper, args.output)
    else:
        raise NotImplementedError
