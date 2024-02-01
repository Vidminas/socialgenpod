from typing import Any, Dict

from langchain.embeddings.base import Embeddings
from langchain_community.embeddings import HuggingFaceInstructEmbeddings, HuggingFaceEmbeddings


def get_embeddings(config: Dict[str, Any]) -> Embeddings:
    config = {**config["embeddings"]}
    config["model_name"] = config.pop("model")
    if config["model_name"].startswith("hkunlp/"):
        Provider = HuggingFaceInstructEmbeddings
    else:
        Provider = HuggingFaceEmbeddings
    return Provider(**config)
