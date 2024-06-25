import ast
import json
import re
from typing import Union

import pandas as pd

from biagent.types.type_alias import MarkdownTypes
from biagent.utils.logger import biagent_logger as logger


def json_indent_limit(json_string, indent="  ", limit=3):
    regexPattern = re.compile(f"\n({indent}){{{limit}}}(({indent})+|(?=(}}|])))")
    return regexPattern.sub("", json_string)


def _replace_new_line(match: re.Match[str]) -> str:
    value = match.group(2)
    value = re.sub(r"\n", r"\\n", value)
    value = re.sub(r"\r", r"\\r", value)
    value = re.sub(r"\t", r"\\t", value)
    value = re.sub(r'(?<!\\)"', r"\"", value)

    return match.group(1) + value + match.group(3)


def _custom_parser(multiline_string: str) -> str:
    """
    The LLM response for `action_input` may be a multiline
    string containing unescaped newlines, tabs or quotes. This function
    replaces those characters with their escaped counterparts.
    (newlines in JSON must be double-escaped: `\\n`)
    """
    if isinstance(multiline_string, (bytes, bytearray)):
        multiline_string = multiline_string.decode()

    multiline_string = re.sub(
        r'("action_input"\:\s*")(.*)(")',
        _replace_new_line,
        multiline_string,
        flags=re.DOTALL,
    )

    return multiline_string


def parse_markdown(code_string: str, mtype: MarkdownTypes) -> Union[str, dict]:
    """
    Parse markdown string
    """
    match = re.search(
        r"```({})(.*?)```".format(mtype.lower()),
        code_string,
        re.DOTALL | re.IGNORECASE,
    )

    if match is not None:
        # If match found, use the content within the backticks
        code_string = match.group(2)

    code_string = code_string.strip()

    return code_string


def parse_python_markdown(code_string: str) -> str:
    return parse_markdown(code_string, "python")


def parse_r_markdown(code_string: str) -> str:
    return parse_markdown(code_string, "r")


def parse_sql_markdown(code_string: str) -> str:
    return parse_markdown(code_string, "sql")


def parse_json_markdown(code_string: str) -> dict:
    json_str = parse_markdown(code_string, "json")
    # handle errors
    json_str = json_str.replace("True", "true").replace("False", "false")
    # Remove comments (anything after // in a line)
    lines = json_str.split("\n")
    cleaned_lines = [line.split("//")[0].rstrip() for line in lines]
    json_str = "\n".join(cleaned_lines)
    json_str = _custom_parser(json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(
            f"Error parsing json: {e}. Please check the json string: {json_str}"
        )
        raise


def parse_json(code_string: str, parser=json.loads):
    try:
        res = parser(code_string)
        return res
    except json.decoder.JSONDecodeError as e:
        if "Expecting property name enclosed in double quotes" in str(e):
            # If the error is due to the fact that the json is not properly quoted, try to fix it
            return parse_json(code_string, ast.literal_eval)
    except Exception as e:
        print(f"Error parsing json: {e}")
        return None


def flatten_nested_json_df(df: pd.DataFrame):
    if df.empty:
        return df

    df = df.reset_index()

    print(f"original shape: {df.shape}")
    print(f"original columns: {df.columns}")

    # search for columns to explode/flatten
    s = (df.applymap(type) == list).all()
    list_columns = s[s].index.tolist()

    s = (df.applymap(type) == dict).all()
    dict_columns = s[s].index.tolist()

    print(f"lists: {list_columns}, dicts: {dict_columns}")
    while len(list_columns) > 0 or len(dict_columns) > 0:
        new_columns = []

        for col in dict_columns:
            print(f"flattening: {col}")
            # explode dictionaries horizontally, adding new columns
            horiz_exploded = pd.json_normalize(df[col]).add_prefix(f"{col}.")
            horiz_exploded.index = df.index
            df = pd.concat([df, horiz_exploded], axis=1).drop(columns=[col])
            new_columns.extend(horiz_exploded.columns)  # inplace

        for col in list_columns:
            print(f"exploding: {col}")
            # explode lists vertically, adding new columns
            df = df.drop(columns=[col]).join(df[col].explode().to_frame())
            # Prevent combinatorial explosion when multiple
            # cols have lists or lists of lists
            df = df.reset_index(drop=True)
            new_columns.append(col)

        # check if there are still dict o list fields to flatten
        s = (df[new_columns].applymap(type) == list).all()
        list_columns = s[s].index.tolist()

        s = (df[new_columns].applymap(type) == dict).all()
        dict_columns = s[s].index.tolist()

        print(f"lists: {list_columns}, dicts: {dict_columns}")

    print(f"final shape: {df.shape}")
    print(f"final columns: {df.columns}")
    return df
