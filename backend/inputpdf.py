import os
import sys
import glob
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for config imports
sys.path.append(str(Path(__file__).resolve().parent))
from config import EMBEDDING_MODEL, CHROMA_PERSIST_DIR, GEMINI_API_KEY, DOCS_DIR

load_dotenv()


def get_embedding_model(model_name=EMBEDDING_MODEL):
    """
    Returns GoogleGenerativeAIEmbeddings if API key is provided,
    otherwise falls back to local ONNX embeddings (all-MiniLM-L6-v2)
    so the RAG pipeline works out of the box offline or online.
    """
    key = os.getenv("gemini_api_key") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    if key and not key.startswith("your_") and not key.startswith("PASTE_") and len(key.strip()) > 15:
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            print(f"[RAG] Using Google Generative AI Embeddings ({model_name}).")
            return GoogleGenerativeAIEmbeddings(
                model=model_name,
                google_api_key=key
            )
        except Exception as e:
            print(f"[RAG] Warning initializing GoogleGenerativeAIEmbeddings: {e}")


    # Fallback to local embedded ONNX model (offline capable, no API key required)
    print("[RAG] Using local high-performance embeddings (all-MiniLM-L6-v2).")
    from langchain_core.embeddings import Embeddings
    from chromadb.utils import embedding_functions

    class LocalFallbackEmbeddings(Embeddings):
        def __init__(self):
            self.ef = embedding_functions.DefaultEmbeddingFunction()
        def embed_documents(self, texts):
            return self.ef(list(texts))
        def embed_query(self, text):
            return self.ef([text])[0]

    return LocalFallbackEmbeddings()


def load_documents(docs_path=None):
    """
    Loads all .txt documents from the configured docs directory.
    """
    if docs_path is None:
        docs_path = str(DOCS_DIR)

    docs_path = Path(docs_path)
    print(f"[RAG] Loading text documents from '{docs_path}'...")

    if not docs_path.exists():
        docs_path.mkdir(parents=True, exist_ok=True)
        print(f"[RAG] Created documents directory at '{docs_path}'.")
        return []

    documents = []
    from langchain_core.documents import Document

    # Load text documents (.txt primary, .md fallback)
    text_files = sorted(list(docs_path.glob("**/*.txt")) + list(docs_path.glob("**/*.md")))
    for file_path in text_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
            if content:
                doc = Document(
                    page_content=content,
                    metadata={"source": file_path.name, "page": 1}
                )
                documents.append(doc)
                print(f"[RAG] Loaded document: {file_path.name}")
        except Exception as e:
            print(f"[RAG] Warning loading text file '{file_path}': {e}")

    # Fallback to PDF if any exist
    pdf_files = list(docs_path.glob("**/*.pdf"))
    if pdf_files:
        try:
            from pypdf import PdfReader
            for pdf_path in pdf_files:
                reader = PdfReader(str(pdf_path))
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        documents.append(Document(
                            page_content=text.strip(),
                            metadata={"source": pdf_path.name, "page": page_num + 1}
                        ))
            print(f"[RAG] Loaded {len(pdf_files)} PDF file(s).")
        except Exception as e:
            print(f"[RAG] Warning loading PDFs: {e}")

    print(f"[RAG] Total documents/pages loaded: {len(documents)}")
    return documents


def split_documents(documents, chunk_size=500, chunk_overlap=50):
    """
    Splits documents into overlapping chunks using RecursiveCharacterTextSplitter.
    """
    if not documents:
        print("[RAG] No documents to split.")
        return []

    print(f"[RAG] Splitting {len(documents)} document(s) into chunks (size={chunk_size}, overlap={chunk_overlap})...")
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"[RAG] Generated {len(chunks)} text chunk(s).")
    return chunks


def create_vector_store(chunks, persist_directory=None, model_name=EMBEDDING_MODEL):
    """
    Generates embeddings and stores them in ChromaDB.
    """
    if persist_directory is None:
        persist_directory = str(CHROMA_PERSIST_DIR)

    if not chunks:
        print("[RAG] No chunks provided to create vector store.")
        return None

    from langchain_chroma import Chroma
    embedding_model = get_embedding_model(model_name)

    print(f"[RAG] Creating embeddings and saving to '{persist_directory}'...")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=persist_directory,
        collection_metadata={"hnsw:space": "cosine"}
    )
    print(f"[RAG] Vector store created and saved successfully to: {persist_directory}")
    return vectorstore


class DocsAgent:
    """
    Docs Agent responsible for semantic retrieval of unstructured energy documents.
    It returns grounded source evidence with relevance scores and page numbers.
    """
    def __init__(self, persist_directory=None, model_name=EMBEDDING_MODEL):
        if persist_directory is None:
            persist_directory = str(CHROMA_PERSIST_DIR)

        from langchain_chroma import Chroma
        self.persist_directory = str(persist_directory)
        self.embedding_model = get_embedding_model(model_name)
        self.db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_model,
            collection_metadata={"hnsw:space": "cosine"}
        )

    def retrieve(self, query: str, k: int = 5, threshold: float = 0.25) -> dict:
        """
        Retrieves relevant document chunks and returns structured JSON evidence.
        """
        try:
            results = self.db.similarity_search_with_score(query, k=k)
        except Exception as e:
            print(f"[DocsAgent] Error querying ChromaDB: {e}")
            return {"sources": []}

        sources = []
        for doc, distance in results:
            # Cosine distance in [0, 2]; normalized relevance score between 0.0 and 1.0
            relevance = round(max(0.0, min(1.0, 1.0 - distance)), 4)

            if relevance < threshold:
                continue

            metadata = doc.metadata or {}
            sources.append({
                "text": doc.page_content,
                "source": metadata.get("source", "unknown"),
                "page": metadata.get("page", 1),
                "relevance": relevance
            })

        # Fallback: if all results were below threshold, return top 1 if available
        if not sources and results:
            doc, distance = results[0]
            sources.append({
                "text": doc.page_content,
                "source": (doc.metadata or {}).get("source", "unknown"),
                "page": (doc.metadata or {}).get("page", 1),
                "relevance": round(max(0.0, min(1.0, 1.0 - distance)), 4)
            })

        return {"sources": sources}


def ingest():
    """
    Full pipeline: load documents from DOCS_DIR, split into chunks, and index into ChromaDB.
    """
    print("=" * 60)
    print("STARTING DOCUMENT INGESTION PIPELINE")
    print("=" * 60)
    docs = load_documents()
    if not docs:
        print("[RAG] No documents found in DOCS_DIR.")
        return None

    chunks = split_documents(docs)
    if not chunks:
        print("[RAG] Splitting produced 0 chunks.")
        return None

    vectorstore = create_vector_store(chunks)
    print("[RAG] Document ingestion completed successfully!")
    return vectorstore


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Telemachus Docs Ingestion & Retrieval CLI")
    parser.add_argument("--ingest", action="store_true", help="Ingest documents from DOCS_DIR into ChromaDB")
    parser.add_argument("--query", type=str, default=None, help="Query the vector index")
    args = parser.parse_args()

    if args.ingest:
        ingest()
    elif args.query:
        agent = DocsAgent()
        evidence = agent.retrieve(args.query)
        import json
        print(json.dumps(evidence, indent=2))
    else:
        # Default behavior: ingest documents and run a test query
        ingest()
        test_query = "What are the main causes of evening peak energy consumption?"
        print(f"\n[RAG] Testing DocsAgent retrieval with query: '{test_query}'")
        try:
            agent = DocsAgent()
            res = agent.retrieve(test_query)
            import json
            print(json.dumps(res, indent=2))
        except Exception as e:
            print(f"[RAG] DocsAgent test query failed: {e}")
