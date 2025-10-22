from sentence_transformers import CrossEncoder
import os

# ============ GLOBAL RERANKER MODEL ============
class LocalReranker:
    """Local cross-encoder reranker using sentence-transformers"""
    
    def __init__(self, model_name='cross-encoder/ms-marco-MiniLM-L-6-v2'):
        local_path = "./models/reranker"
        if os.path.exists(local_path):
            print(f"📦 Found local reranker at {local_path}")
            self.model = CrossEncoder(local_path, trust_remote_code=True)
        else:
            print(f"🌐 Downloading model from Hugging Face: {model_name}")
            self.model = CrossEncoder(model_name, trust_remote_code=True)
            self.model.save(local_path)
            print("💾 Model saved locally for future runs.")
    
    def rerank(self, query: str, documents: list, top_k: int = 5):
        """
        Rerank documents using cross-encoder
        Returns top_k most relevant documents with scores
        """
        if not documents:
            return []
        
        try:
            # Prepare query-document pairs
            pairs = []
            for doc in documents:
                title = doc.properties.get('title', '')
                content = doc.properties.get('content', '')
                summary = doc.properties.get('summary', '')
                # Combine fields (limit length for performance)
                text = f"{title}. {summary} {content}"[:1000]
                pairs.append([query, text])
            
            # Score all pairs
            scores = self.model.predict(pairs)
            
            # Combine documents with scores
            doc_scores = list(zip(documents, scores))
            
            # Sort by score (descending)
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Return top_k
            reranked = doc_scores[:top_k]
            
            print(f"✅ Reranked {len(documents)} → {len(reranked)} documents")
            for i, (doc, score) in enumerate(reranked):
                title = doc.properties.get('title', 'Untitled')
                print(f"   {i+1}. {title} (score: {score:.4f})")
            
            return [
                {'document': doc, 'relevance_score': float(score)}
                for doc, score in reranked
            ]
            
        except Exception as e:
            print(f"⚠️ Reranking failed: {e}")
            # Fallback: return original documents
            return [{'document': doc, 'relevance_score': None} for doc in documents[:top_k]]