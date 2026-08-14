# For installations

pip install langchain langchain-community langchain-text-splitters langchain-openai langchain-huggingface langchain-chroma pypdf python-dotenv sentence-transformers


###new cell

import os
from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyPDFDirectoryLoader
from langchain_text_splitters import CharacterTextSplitter
# from langchain_openai import OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

def load_documents(docs_path = "/content/docs"):
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

def create_vector_store(chunks, persist_directory = "db/chroma_db"):
    print("Creating Embeddings and storing it in ChromaDB.")

    # embedding_model = OpenAIEmbeddings(model = "text-embedding-3-small")
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
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
    documents = load_documents(docs_path="docs")
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



if __name__ == "__main__":
    main()

### new cell

from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import SystemMessage, HumanMessage
from transformers import pipeline

persistent_directory = "db/chroma_db"

embedding_model = HuggingFaceEmbeddings(model_name = "sentence-transformers/all-MiniLM-L6-v2")

from langchain_chroma import Chroma
db = Chroma(persist_directory=persistent_directory, embedding_function=embedding_model, collection_metadata={"hnsw:space":"cosine"})

query = "What are the main objectives of energy conservation? "

retriever = db.as_retriever(
    search_type = "similarity_score_threshold",
    search_kwargs = {"k":2,"score_threshold":0.3}
)

relevant_docs = retriever.invoke(query)
print(f"User query: {query}")
print("context")
for i,doc in enumerate(relevant_docs,1):
    print(f"Document{i} : \n {doc.page_content}\n")


#CHATGPT
combined_input = f"""Based on the following documents please answer this question: {query}
Documents:
{chr(10).join([f"-{doc.page_content[:800]}"for doc in relevant_docs])}
Please provide a clear helpful answer using only the information from these documents. If you can't find the answer in the document then just say "I don't have enough information to answer your query"
"""

# model = ChatOpenAI(model="gpt-4o")
# messages = [
#     SystemMessage(content = "You are a good assistant man"),
#     HumanMessage(content=combined_input),
# ]
# result = model.invoke(messages)

# print("\n Generated Response: ")
# print(result.content)

### new cell

#LOCAL MODEL

print("\n Generating Response: ")
model = pipeline("text-generation",model = "distilgpt2")

result = model(
    combined_input,
    max_new_tokens = 150,
    do_sample = False
)
print("\nGenerated Output: ")
print(result[0]["generated_text"])

