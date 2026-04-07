import os
import re
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from termcolor import colored
from config import get_embeddings, DATA_FOLDER, DB_FOLDER, FILES


def clean_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def build_vector_dbs():
    embeddings = get_embeddings()

    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        print(colored(f"[WARN] {DATA_FOLDER} directory was empty. Creating it...", "yellow"))

    # Only build DBs for files defined in config, skip dynamic discovery
    # to avoid duplicated indices
    for key, filename in FILES.items():
        persist_dir = os.path.join(DB_FOLDER, key)
        file_path = os.path.join(DATA_FOLDER, filename)

        if os.path.exists(persist_dir):
            print(colored(f"[OK] DB for '{key}' already exists at {persist_dir}. Skipping.", "yellow"))
            continue

        if not os.path.exists(file_path):
            print(colored(f"[ERROR] Missing source file: {filename}", "red"))
            continue

        print(colored(f"[INFO] Building Vector Index for {key}...", "cyan"))

        loader = PyMuPDFLoader(file_path)
        docs = loader.load()
        print(f"  - Loaded {len(docs)} pages.")

        for doc in docs:
            doc.page_content = clean_text(doc.page_content)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""],
        )

        splits = splitter.split_documents(docs)
        print(f"  - Split into {len(splits)} chunks.")

        print("  - Embedding and storing...")
        Chroma.from_documents(splits, embeddings, persist_directory=persist_dir)
        print(colored(f"[OK] Successfully built DB for {key}!", "green"))


if __name__ == "__main__":
    build_vector_dbs()
