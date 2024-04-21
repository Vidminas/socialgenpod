from typing import Any, Optional

from langchain import hub
from langchain.llms.base import LLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSequence
from langchain_community.llms.ctransformers import CTransformers
from langchain_community.llms.huggingface_pipeline import HuggingFacePipeline
from langchain_community.llms.openai import OpenAI
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from .utils import merge


rephrase_prompt = hub.pull("langchain-ai/chat-langchain-rephrase")
rag_prompt = hub.pull("rlm/rag-prompt")


def get_llm(
    config: dict[str, Any],
    *,
    selected_llm_index: int = 0,
) -> LLM:
    local_files_only = not config["download"]

    selection = config["llms"][selected_llm_index].copy()
    model_framework = selection.pop("model_framework")
    config = {**selection}

    if model_framework == "ctransformers":
        config = merge(config, {"config": {"local_files_only": local_files_only}})
        llm = CTransformers(**config)
    elif model_framework == "openai":
        llm = OpenAI(**config)
    elif model_framework == "huggingface":
        config = merge(config, {"model_kwargs": {"local_files_only": local_files_only}})

        tokenizer = AutoTokenizer.from_pretrained(config["model"])
        model = AutoModelForCausalLM.from_pretrained(
            config["model"], **config["model_kwargs"]
        )
        if not tokenizer.pad_token_id:
            tokenizer.pad_token_id = model.config.eos_token_id
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            **config["pipeline_kwargs"],
        )
        llm = HuggingFacePipeline(pipeline=pipe)
    else:
        raise ValueError(f"Unsupported model framework: {model_framework}")

    return llm


def llm_rephrase_question_with_history(
    llm: LLM, prompt: str, chat_history: list
) -> str:
    chain = RunnableSequence(rephrase_prompt | llm | StrOutputParser())
    return chain.invoke({"input": prompt, "chat_history": chat_history})


def llm_respond(llm: LLM, prompt: str, context: Optional[list[str]]) -> str:
    if context is not None:
        chain = RunnableSequence(rag_prompt | llm | StrOutputParser())
        return chain.invoke({"question": prompt, "context": context})
    else:
        chain = RunnableSequence(llm | StrOutputParser())
        return chain.invoke(prompt)
