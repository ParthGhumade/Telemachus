import os
from langchain_text_splitters import CharacterTextSplitter
# from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
from config import EMBEDDING_MODEL, CHROMA_PERSIST_DIR, GEMINI_API_KEY, DOCS_DIR

load_dotenv()

def load_documents(docs_path=None):
    if docs_path is None:
        docs_path = str(DOCS_DIR)
    from langchain_community.document_loaders import PyPDFDirectoryLoader
    print(f"Loading documents from '{docs_path}'....")

    if not os.path.exists(docs_path):
        raise FileNotFoundError(f"The directory '{docs_path}' doesn't exist")

    loader = PyPDFDirectoryLoader(docs_path)
    documents = loader.load()

    for i,doc in enumerate(documents[:2]):
        print(f"\nDocument{i+1}")
        print(f"Source: {doc.metadata['source']}")
        print(f"Content length: {len(doc.page_content)} characters")
        print(f"Content preview: {doc.page_content[:100]}")
        print(f"metadata:{doc.metadata}")

    return documents

def split_documents(documents,chunk_size = 400, chunk_overlap = 0):
    print("Splitting documents into chunks")
    text_splitter = CharacterTextSplitter(
        chunk_size = chunk_size,
        chunk_overlap = chunk_overlap
    )
    chunks = text_splitter.split_documents(documents)

    if chunks:
        for i, chunk in enumerate(chunks[:5]):
            print(f"\n Chunk{i+1}")
            print(f"Source: {chunk.metadata['source']}")
            print(f"length:{len(chunk.page_content)}characters")
            print("Content")
            print(chunk.page_content)
            print("-"*50)

            if len(chunks)>5:
                print(f"\n......and{len(chunks)-5} more chunks")

    return chunks

def create_vector_store(chunks, persist_directory = CHROMA_PERSIST_DIR, model_name = EMBEDDING_MODEL):
    print("Creating Embeddings and storing it in ChromaDB.")

    # embedding_model = OpenAIEmbeddings(model = "text-embedding-3-small")
    embedding_model = GoogleGenerativeAIEmbeddings(
        model=model_name,
        google_api_key=GEMINI_API_KEY
    )

    print("Creating vector store")
    vectorstore = Chroma.from_documents(
        documents = chunks,
        embedding=embedding_model,
        persist_directory=persist_directory,
        collection_metadata={"hnsw:space":"cosine"}
    )
    print("Finished creating vector store")
    print(f"Vector store created and saved to {persist_directory}")

    return vectorstore
def main():
    print("=" * 50)

    # 1. Check documents
    documents = load_documents()
    print(f"\n📄 DOCUMENTS COUNT: {len(documents)}")
    if documents:
        print(f"   First doc length: {len(documents[0].page_content)} chars")
    else:
        print("   ❌ EMPTY! Loader found nothing.")
        return

    # 2. Check chunks
    chunks = split_documents(documents)
    print(f"\n🧩 CHUNKS COUNT: {len(chunks)}")
    if chunks:
        print(f"   First chunk length: {len(chunks[0].page_content)} chars")
    else:
        print("   ❌ EMPTY! Splitter produced nothing.")
        return

    # 3. Check vector store
    print("\n💾 Creating vector store...")
    vectorstore = create_vector_store(chunks)
    print("✅ Done!")



# Ingestion execution can be called manually or in a separate script
# if __name__ == "__main__":
#     main()
### Docs Agent Implementation ###

import json
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

class DocsAgent:
    """
    Docs Agent responsible for retrieving unstructured evidence
    as defined in the architecture. It does NOT generate responses.
    """
    def __init__(self, persist_directory=CHROMA_PERSIST_DIR, model_name=EMBEDDING_MODEL):
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=GEMINI_API_KEY
        )
        self.db = Chroma(
            persist_directory=persist_directory, 
            embedding_function=self.embedding_model, 
            collection_metadata={"hnsw:space":"cosine"}
        )

    def retrieve(self, query: str, k: int = 5, threshold: float = 0.3) -> dict:
        """
        Retrieves relevant document chunks and returns them in the 
        structured JSON format expected by the architecture.
        """
        try:
            # similarity_search_with_score returns (Document, distance)
            results = self.db.similarity_search_with_score(query, k=k)
        except Exception as e:
            print(f"Error querying ChromaDB: {e}")
            return {"sources": []}
            
        sources = []
        for doc, distance in results:
            # Chroma uses cosine distance, so similarity is roughly 1.0 - distance
            relevance = 1.0 - distance
            
            if relevance < threshold:
                continue
                
            metadata = doc.metadata
            sources.append({
                "text": doc.page_content,
                "source": metadata.get("source", "unknown"),
                "page": metadata.get("page", 0),
                "relevance": round(relevance, 4)
            })
            
        return {"sources": sources}

# Example Usage (Testing the Docs Agent)
if __name__ == "__main__":
    # If run directly, demonstrate the Docs Agent functionality
    agent = DocsAgent()
    query = "What are the main objectives of energy conservation?"
    print(f"Testing Docs Agent with query: '{query}'\n")
    
    evidence = agent.retrieve(query)
    
    # Output the structured evidence as JSON
    print(json.dumps(evidence, indent=2))

