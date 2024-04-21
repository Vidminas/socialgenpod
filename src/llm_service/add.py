import glob
import os
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

from tqdm import tqdm
from langchain.document_loaders.csv_loader import CSVLoader
from langchain.document_loaders.pdf import PDFMinerLoader
from langchain.document_loaders.text import TextLoader
from langchain.document_loaders.email import UnstructuredEmailLoader
from langchain.document_loaders.epub import UnstructuredEPubLoader
from langchain.document_loaders.html import UnstructuredHTMLLoader
from langchain.document_loaders.markdown import UnstructuredMarkdownLoader
from langchain.document_loaders.odt import UnstructuredODTLoader
from langchain.document_loaders.powerpoint import UnstructuredPowerPointLoader
from langchain.document_loaders.word_document import UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

from .solid_utils import webid_to_filepath, discover_document_uris, download_resource
from .embeddings import (
    does_vectorstore_exist,
    get_vectorstore,
    get_vectorstore_from_documents,
)


# Custom document loaders
class MyElmLoader(UnstructuredEmailLoader):
    """Wrapper to fallback to text/plain when default does not work"""

    def load(self) -> List[Document]:
        """Wrapper adding fallback for elm without html"""
        try:
            try:
                doc = UnstructuredEmailLoader.load(self)
            except ValueError as e:
                if "text/html content not found in email" in str(e):
                    # Try plain text
                    self.unstructured_kwargs["content_source"] = "text/plain"
                    doc = UnstructuredEmailLoader.load(self)
                else:
                    raise
        except Exception as e:
            # Add file_path to exception message
            raise type(e)(f"{self.file_path}: {e}") from e

        return doc


# Map file extensions to document loaders and their arguments
LOADER_MAPPING = {
    ".csv": (CSVLoader, {"encoding": "utf8"}),
    ".doc": (UnstructuredWordDocumentLoader, {}),
    ".docx": (UnstructuredWordDocumentLoader, {}),
    ".eml": (MyElmLoader, {}),
    ".epub": (UnstructuredEPubLoader, {}),
    ".html": (UnstructuredHTMLLoader, {}),
    ".md": (UnstructuredMarkdownLoader, {}),
    ".odt": (UnstructuredODTLoader, {}),
    ".pdf": (PDFMinerLoader, {}),
    ".ppt": (UnstructuredPowerPointLoader, {}),
    ".pptx": (UnstructuredPowerPointLoader, {}),
    ".txt": (TextLoader, {"encoding": "utf8"}),
    ".ttl": (TextLoader, {"encoding": "utf8"}),
    # Add more mappings for other file extensions and loaders as needed
}


def download_documents(uris: list[str], save_dir: str):
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_uri = {
            executor.submit(download_resource, uri, save_dir): uri for uri in uris
        }
        for future in as_completed(future_to_uri):
            if future.done():
                try:
                    future.result()
                except Exception as e:
                    print(f"Failed to download {future_to_uri[future]}: {e}")
                else:
                    print(f"Downloaded {future_to_uri[future]}")
            else:
                print(f"Cancelled downloading {future_to_uri[future]}")


def load_single_document(file_path: str) -> List[Document]:
    ext = "." + file_path.rsplit(".", 1)[-1]
    if ext in LOADER_MAPPING:
        loader_class, loader_args = LOADER_MAPPING[ext]
        loader = loader_class(file_path, **loader_args)
        return loader.load()

    raise ValueError(f"Unsupported file extension '{ext}'")


def load_documents(source_dir: str, ignored_files: List[str] = []) -> List[Document]:
    """
    Loads all documents from the source documents directory, ignoring specified files
    """
    all_files = glob.glob(os.path.join(source_dir, f"**/*"), recursive=True)
    filtered_files = [
        file_path for file_path in all_files if file_path not in ignored_files
    ]

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = []
        with tqdm(
            total=len(filtered_files),
            desc="Loading new documents",
            ncols=80,
            position=0,
            leave=True,
        ) as pbar:
            futures = {
                executor.submit(load_single_document, file): file
                for file in filtered_files
            }
            for future in as_completed(futures):
                docs = future.result()
                results.extend(docs)
                pbar.update()

    return results


def process_documents(
    source_directory: str, ignored_files: List[str] = []
) -> List[Document]:
    """
    Load documents and split in chunks
    """
    print(f"Loading documents from {source_directory}")
    documents = load_documents(source_directory, ignored_files)
    if not documents:
        print("No new documents to load")
        return
    print(f"Loaded {len(documents)} new documents from {source_directory}")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)
    return texts


def add(config: Dict[str, Any], docs_location: str, webid: str) -> None:
    persist_directory = os.path.join(
        config["chroma"]["persist_directory"], webid_to_filepath(webid)
    )
    docs_directory = os.path.join(persist_directory, "docs")
    os.makedirs(docs_directory, exist_ok=True)

    docs_uris = discover_document_uris(docs_location)
    download_documents(docs_uris, docs_directory)
    db = None

    if does_vectorstore_exist(persist_directory):
        # Update local vectorstore
        print(f"Appending to existing vectorstore at {persist_directory}")
        db = get_vectorstore(config, persist_directory)
        collection = db.get()
        texts = process_documents(
            docs_directory,
            [metadata["source"] for metadata in collection["metadatas"]],
        )
        if texts is not None:
            print(f"Creating embeddings. May take a few minutes...")
            db.add_documents(texts)
    else:
        # Create and store a local vectorstore
        print("Creating new vectorstore")
        texts = process_documents(docs_directory)
        if texts is not None:
            print(f"Creating embeddings. May take a few minutes...")
            db = get_vectorstore_from_documents(config, persist_directory, texts)

    if db is not None:
        db.persist()
        db = None
