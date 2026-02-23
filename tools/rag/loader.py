"""
RAG Data Loader

Loads markdown files from rag_data/ into ChromaDB vector database.
Run this once to index your knowledge base.

Usage:
    python -m tools.rag.loader
"""

import re
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configuration
RAG_DATA_DIR = Path("rag_data/preferences")
DB_PATH = "runtime/rag_db"
COLLECTION_NAME = "preferences"
MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def clean_text(text: str) -> str:
    """
    Clean markdown text.
    
    Removes excessive whitespace while preserving structure.
    """
    if not text:
        return ""
    
    # Preserve paragraph breaks
    text = re.sub(r'\n\n', '<<PARA>>', text)
    
    # Single newlines become spaces
    text = re.sub(r'\n', ' ', text)
    
    # Restore paragraphs
    text = re.sub(r'<<PARA>>', '\n\n', text)
    
    # Multiple spaces → single space
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()


def load_markdown_files() -> dict[str, str]:
    """
    Load all markdown files from rag_data directory.
    
    Returns:
        Dict mapping filename to content
    """
    files = {}
    
    if not RAG_DATA_DIR.exists():
        print(f"⚠️  Directory not found: {RAG_DATA_DIR}")
        return files
    
    for md_file in RAG_DATA_DIR.glob("*.md"):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            files[md_file.name] = clean_text(content)
    
    return files


def main():
    """Main loader function."""
    print("🔄 Loading RAG data...\n")
    
    # Load markdown files
    print(f"📂 Scanning {RAG_DATA_DIR}...")
    files = load_markdown_files()
    
    if not files:
        print("❌ No markdown files found!")
        print(f"   Create files in: {RAG_DATA_DIR}")
        return
    
    print(f"✓ Found {len(files)} file(s): {list(files.keys())}\n")
    
    # Initialize model and database
    print("🤖 Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)
    
    print("💾 Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=DB_PATH)
    
    # Delete existing collection to rebuild
    try:
        client.delete_collection(COLLECTION_NAME)
        print("🗑️  Cleared existing collection")
    except:
        pass
    
    collection = client.get_or_create_collection(COLLECTION_NAME)
    
    # Initialize LangChain text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    # Process each file
    all_chunks = []
    all_metadata = []
    
    for filename, content in files.items():
        print(f"\n📄 Processing {filename}...")
        
        # Chunk with LangChain
        chunks = splitter.split_text(content)
        print(f"   Created {len(chunks)} chunks")
        
        # Add to batch
        all_chunks.extend(chunks)
        all_metadata.extend([
            {"source": filename, "type": "preferences"}
            for _ in chunks
        ])
    
    # Generate embeddings and store
    print(f"\n🔢 Generating embeddings for {len(all_chunks)} chunks...")
    embeddings = model.encode(all_chunks, show_progress_bar=True).tolist()
    
    print("💾 Storing in vector database...")
    collection.upsert(
        documents=all_chunks,
        embeddings=embeddings,
        ids=[f"chunk_{i}" for i in range(len(all_chunks))],
        metadatas=all_metadata
    )
    
    print(f"\n✅ Successfully loaded {len(all_chunks)} chunks into ChromaDB")
    print(f"📍 Database location: {DB_PATH}")
    print(f"📦 Collection: {COLLECTION_NAME}\n")


if __name__ == "__main__":
    main()