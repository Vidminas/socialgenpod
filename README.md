# Solid RAG
Converse with an LLM provider of your choice. Store your documents and chat history in a Solid pod.

This project builds on the work from [ChatDocs-Streamlit](https://github.com/Vidminas/chatdocs-streamlit).

## Setup

Based on <https://stackoverflow.com/questions/76722680/what-is-the-best-way-to-combine-conda-with-standard-python-packaging-tools-e-g>

### Installation with pip

```bash
# local installation of the package:
pip install .

# editable install:
pip install -e .

# editable install with optional dependencies:
pip install -e .[llm]
```

### Installation with conda

When creating an environment from scratch:
```bash
conda create -n ENVNAME "python>=3.11" --file requirements.txt
```

If adding to an established environment, use update:
```bash
conda update --name ENVNAME --file requirements.txt
```

For optional dependencies:
```bash
conda update --name ENVNAME --freeze-installed --file requirements-llm.txt
```

Then install this package using:
```bash
pip install --no-build-isolation --no-deps .
```

## Usage

Open chat interface by running `solidrag-chat`. 

Run the LLM service provider using `solidrag-llm`.