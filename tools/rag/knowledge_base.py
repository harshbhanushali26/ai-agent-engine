"""
Knowledge Base System

- KnowledgeBase class: Query ChromaDB
- query_preferences tool: Agent integration
"""

import chromadb
from sentence_transformers import SentenceTransformer
from tools.responses import tool_response
from tools.schemas import RAGQueryInput

# Configuration
DB_PATH = "runtime/rag_db"
COLLECTION_NAME = "preferences"
MODEL_NAME = "all-MiniLM-L6-v2"


class KnowledgeBase:
    """RAG-based knowledge retrieval."""
    
    _instance = None
    _model = None
    _collection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            self._initialize()
    
    def _initialize(self):
        """Load model and connect to database."""
        self._model = SentenceTransformer(MODEL_NAME)
        client = chromadb.PersistentClient(path=DB_PATH)
        
        try:
            self._collection = client.get_collection(COLLECTION_NAME)
        except:
            raise RuntimeError(
                f"Knowledge base not found! Run: python -m tools.rag.loader"
            )
    
    def query(self, query_text: str, top_k: int = 3) -> str:
        """Query knowledge base."""
        query_embedding = self._model.encode([query_text]).tolist()
        
        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )
        
        if results['documents'] and results['documents'][0]:
            return "\n\n".join(results['documents'][0])
        
        return ""


# Singleton instance
_kb = None

def get_knowledge_base() -> KnowledgeBase:
    """Get or create knowledge base instance."""
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


# ═══════════════════════════════════════════════════════════
# TOOL FUNCTION (Agent Integration)
# ═══════════════════════════════════════════════════════════

def query_preferences(data: RAGQueryInput):
    """
    Query user preferences from knowledge base.
    
    Agent tool for retrieving user context.
    """
    try:
        kb = get_knowledge_base()
        context = kb.query(data.query, data.top_k)
        
        if not context:
            return tool_response(
                tool="query_preferences",
                success=True,
                data="No relevant preferences found."
            )
        
        return tool_response(
            tool="query_preferences",
            success=True,
            data=context
        )
        
    except Exception as e:
        return tool_response(
            tool="query_preferences",
            success=False,
            error=str(e)
        )
