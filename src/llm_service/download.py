from typing import Any, Dict
from multiprocessing import Process

from .embeddings import get_embeddings
from .llms import get_llm


def download(config: Dict[str, Any]) -> None:
    config = {**config, "download": True}
    get_embeddings(config)

    for idx in range(len(config["llms"])):
        # run each model loading in a child process so that allocated memory gets released in between
        # https://stackoverflow.com/questions/15455048/releasing-memory-in-python
        p = Process(target=get_llm, args=(config,), kwargs={"selected_llm_index": idx})
        p.start()
        p.join()
        p.close()
