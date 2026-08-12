import os
import pytest
from transformers import AutoTokenizer, AutoModelForTokenClassification

def test_offline_loading():
    # Force offline mode
    os.environ["HF_HUB_OFFLINE"] = "1"
    
    tokenizer = AutoTokenizer.from_pretrained("/app/.model_cache/biobert-ner-bc5cdr", local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained("/app/.model_cache/biobert-ner-bc5cdr", local_files_only=True)
    
    assert tokenizer is not None
    assert model is not None
