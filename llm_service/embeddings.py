import glob
import os
from typing import Any, Dict, List

from chromadb.config import Settings
from langchain.docstore.document import Document
from langchain.vectorstores.chroma import Chroma
from langchain.embeddings.base import Embeddings
from langchain_community.embeddings import (
    HuggingFaceInstructEmbeddings,
    HuggingFaceEmbeddings,
)

from .solid_utils import webid_to_filepath


def get_embeddings(config: Dict[str, Any]) -> Embeddings:
    config = {**config["embeddings"]}
    config["model_name"] = config.pop("model")
    if config["model_name"].startswith("hkunlp/"):
        Provider = HuggingFaceInstructEmbeddings
    else:
        Provider = HuggingFaceEmbeddings
    return Provider(**config)


def does_vectorstore_exist(persist_directory: str) -> bool:
    """
    Checks if vectorstore exists
    """
    if os.path.exists(os.path.join(persist_directory, "index")):
        if os.path.exists(
            os.path.join(persist_directory, "chroma-collections.parquet")
        ) and os.path.exists(
            os.path.join(persist_directory, "chroma-embeddings.parquet")
        ):
            list_index_files = glob.glob(os.path.join(persist_directory, "index/*.bin"))
            list_index_files += glob.glob(
                os.path.join(persist_directory, "index/*.pkl")
            )
            # At least 3 documents are needed in a working vectorstore
            if len(list_index_files) > 3:
                return True
    return False


def get_vectorstore(config: Dict[str, Any], persist_directory: str) -> Chroma:
    embeddings = get_embeddings(config)
    config = {**config["chroma"], "persist_directory": persist_directory}
    return Chroma(
        embedding_function=embeddings,
        client_settings=Settings(**config),
    )


def get_vectorstore_from_documents(
    config: Dict[str, Any],
    persist_directory: str,
    documents: List[Document],
) -> Chroma:
    embeddings = get_embeddings(config)
    config = {**config["chroma"], "persist_directory": persist_directory}
    return Chroma.from_documents(
        documents,
        embeddings,
        client_settings=Settings(**config),
    )


def get_retriever_for_webid(config: Dict[str, Any], webid: str):
    persist_directory = os.path.join(
        config["chroma"]["persist_directory"], webid_to_filepath(webid)
    )
    db = get_vectorstore(config, persist_directory)
    return db.as_retriever(**config["retriever"])
