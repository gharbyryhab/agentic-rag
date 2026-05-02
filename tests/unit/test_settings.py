from src.config import get_settings


def test_settings_load():
    s = get_settings()
    assert s.embeddings.model_name == "BAAI/bge-small-en-v1.5"
    assert s.vector_store.provider == "chroma"
    assert s.llm.provider == "gemini"
    assert s.retrieval.top_k > 0
