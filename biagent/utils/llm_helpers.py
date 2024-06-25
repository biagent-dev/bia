import json
import os
import typing

import modelscope_agent.llm
from modelscope_agent.llm.base import BaseChatModel
from modelscope_agent.utils.tokenization_utils import count_tokens

from biagent.utils.logger import biagent_logger as logger
from biagent.utils.output_parser import parse_json_markdown


def get_valid_json_response(
    prompt, llm, max_retries=3, validator: typing.Callable = None
):
    retry = 0
    while True:
        response = llm.chat(prompt)
        try:
            json_response = parse_json_markdown(response)
            if not validator(json_response):
                raise ValueError("Invalid JSON response")
            return json_response
        except (json.JSONDecodeError, ValueError) as e:  # noqa: E722
            logger.error(f"Invalid JSON response: {e}")
            retry += 1
            if retry >= max_retries:
                raise
            continue


def get_llm_config(model: str) -> dict:
    if model.startswith("qwen"):
        return {"model": model, "model_server": "dashscope"}
    elif model.startswith("gpt"):
        return {
            "model": model,
            "model_server": "openai",
            "api_base": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        }
    else:
        raise ValueError(f"Unsupported model: {model}")


def get_chat_model(model: dict | BaseChatModel, verbose=True) -> BaseChatModel:
    if isinstance(model, str):
        model = get_llm_config(model)
        model = modelscope_agent.llm.get_chat_model(**model)
    elif isinstance(model, dict):
        model = modelscope_agent.llm.get_chat_model(**model)

    def chat_wrapper(func: typing.Callable) -> typing.Callable:
        def wrapper(*args, **kwargs):
            if "prompt" in kwargs:
                prompt = kwargs.pop("prompt")
            else:
                prompt = args[0]
                args = args[1:]
            if verbose:
                logger.info(
                    f"Input tokens: {count_tokens(prompt)}\nSending prompt: {prompt}"
                )
            res = func(prompt=prompt, *args, **kwargs)
            if verbose:
                logger.info(f"Output tokens: {count_tokens(res)}\nResponse: {res}")
            return res

        return wrapper

    model.chat = chat_wrapper(model.chat)

    return model
