import os
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
from typing import List, Dict, Any, Optional
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class NERService:
    def __init__(self):
        settings = get_settings()
        self.model_path = settings.resolved_ner_model  # None when custom checkpoint absent
        self._model = None
        self._tokenizer = None
        self._id2label = None
        self._initialized = False

    def _initialize(self):
        if self._initialized:
            return
        self._initialized = True
        if not self.model_path:
            logger.warning("NER model path is None (custom checkpoint not available on this host). "
                  "NER entity extraction will return empty results (graceful degradation).")
            return

        is_local = os.path.isdir(self.model_path)
        logger.info(f"Loading NER model from {self.model_path} (local={is_local})")
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, local_files_only=is_local, use_fast=True
            )
            self._model = AutoModelForTokenClassification.from_pretrained(
                self.model_path, local_files_only=is_local
            )
            self._model.eval()
            self._id2label = self._model.config.id2label
            logger.info(f"NER model loaded successfully from {self.model_path}")
        except (OSError, FileNotFoundError) as exc:
            # OSError/FileNotFoundError covers:
            # - local_files_only=True and files not present on disk
            # - HF Hub 404 / repo-not-found for a Hub path
            logger.warning(
                f"NER model could not be loaded from '{self.model_path}' "
                f"({type(exc).__name__}: {exc}). "
                "NER entity extraction will return empty results (graceful degradation)."
            )
            self._model = None
            self._tokenizer = None
        except Exception as exc:
            # Unexpected exception — log it prominently but do NOT silently eat it;
            # re-raise so it surfaces in the request error and Railway logs.
            logger.error(
                f"UNEXPECTED error loading NER model from '{self.model_path}': "
                f"{type(exc).__name__}: {exc}"
            )
            raise

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        self._initialize()
        if not self._model or not self._tokenizer:
            return []

        inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self._model(**inputs)
            
        preds = torch.argmax(outputs.logits, dim=-1)[0].cpu().numpy()
        word_ids = inputs.word_ids(batch_index=0)
        
        entities = []
        current_entity = None
        
        for i, (pred_id, word_id) in enumerate(zip(preds, word_ids)):
            if word_id is None:
                continue
                
            label = self._id2label[pred_id]
            
            if label == "O":
                if current_entity:
                    entities.append(current_entity)
                    current_entity = None
            elif label.startswith("B-"):
                ent_type = label[2:]
                # Treat a B-tag immediately following another B-tag of the same entity type, 
                # where both fall inside the same original word, as a continuation
                if current_entity and current_entity["type"] == ent_type and current_entity["last_word_id"] == word_id:
                    current_entity["end_pos"] = i + 1
                    current_entity["last_word_id"] = word_id
                else:
                    if current_entity:
                        entities.append(current_entity)
                    current_entity = {
                        "type": ent_type,
                        "start_pos": i,
                        "end_pos": i + 1,
                        "last_word_id": word_id
                    }
            elif label.startswith("I-"):
                ent_type = label[2:]
                if current_entity and current_entity["type"] == ent_type:
                    current_entity["end_pos"] = i + 1
                    current_entity["last_word_id"] = word_id
                else:
                    if current_entity:
                        entities.append(current_entity)
                    current_entity = {
                        "type": ent_type,
                        "start_pos": i,
                        "end_pos": i + 1,
                        "last_word_id": word_id
                    }
                    
        if current_entity:
            entities.append(current_entity)
            
        # Reconstruct text and format output
        results = []
        for ent in entities:
            # We can use token_to_chars to get exact string offsets if needed, but decoding tokens is robust
            token_span = inputs["input_ids"][0][ent["start_pos"]:ent["end_pos"]]
            text_span = self._tokenizer.decode(token_span).strip()
            
            results.append({
                "type": ent["type"],
                "text": text_span
            })
            
        return results

# Singleton instance
ner_service = NERService()
