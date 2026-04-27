"""
RAG-powered task suggestion for PawPal+.

Pipeline:
  1. Load .txt files from knowledge_base/ and chunk them into paragraphs.
  2. Embed chunks with ChromaDB's default (sentence-transformers) embedder.
  3. At query time, embed a pet-info description and retrieve the top-k chunks.
  4. Pass retrieved chunks + pet info to Gemini to generate Task suggestions.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from groq import Groq
import chromadb
from chromadb.utils import embedding_functions

from pawpal_system import Task
from validators import sanitize_for_prompt, validate_llm_task, ValidationError
from dotenv import load_dotenv

load_dotenv()


_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge_base"
_COLLECTION_NAME = "pawpal_care"
_TOP_K = 6


def _chunk_text(text: str, min_chars: int = 80) -> list[str]:
    """Split on blank lines; drop tiny fragments."""
    raw = re.split(r"\n{2,}", text.strip())
    return [c.strip() for c in raw if len(c.strip()) >= min_chars]


class PetCareAdvisor:
    """Retrieves relevant pet-care guidelines and asks Claude to suggest Tasks."""

    def __init__(self, knowledge_dir: Path = _KNOWLEDGE_DIR):
        ef = embedding_functions.DefaultEmbeddingFunction()
        self._db = chromadb.Client()
        self._col = self._db.get_or_create_collection(_COLLECTION_NAME, embedding_function=ef)
        self._groq = Groq(api_key=os.environ["GROQ_API_KEY"])
        self._load_knowledge(knowledge_dir)

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _load_knowledge(self, directory: Path) -> None:
        """Chunk and upsert every .txt file in the knowledge directory."""
        if not directory.exists():
            return

        docs, ids, metas = [], [], []
        for txt_file in sorted(directory.glob("*.txt")):
            source = txt_file.stem
            chunks = _chunk_text(txt_file.read_text(encoding="utf-8"))
            for i, chunk in enumerate(chunks):
                chunk_id = f"{source}_{i}"
                docs.append(chunk)
                ids.append(chunk_id)
                metas.append({"source": source})

        if docs:
            self._col.upsert(documents=docs, ids=ids, metadatas=metas)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def _build_query(self, name: str, species: str, age: Optional[int],
                     energy_level: Optional[str], needs_medication: bool,
                     breed: Optional[str]) -> str:
        parts = [f"{species} care"]
        if breed:
            parts.append(f"{breed} breed")
        if age is not None:
            if species == "dog":
                category = "puppy" if age < 1 else ("senior" if age >= 7 else "adult")
            else:
                category = "kitten" if age < 1 else ("senior" if age >= 10 else "adult")
            parts.append(f"{category} age {age}")
        if energy_level:
            parts.append(f"{energy_level} energy")
        if needs_medication:
            parts.append("medication administration health condition")
        return " ".join(parts)

    def _retrieve(self, query: str) -> list[str]:
        results = self._col.query(query_texts=[query], n_results=_TOP_K)
        return results["documents"][0] if results["documents"] else []

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _build_prompt(self, pet_info: dict, chunks: list[str]) -> str:
        context = "\n\n---\n\n".join(chunks)
        safe_name = sanitize_for_prompt(str(pet_info["name"]))
        safe_breed = sanitize_for_prompt(str(pet_info.get("breed") or "unknown"))
        return f"""You are a helpful pet care assistant for the PawPal+ app.

Using ONLY the care guidelines below, suggest a realistic daily task list for this pet.
Return ONLY a JSON array of task objects with these exact keys:
  title (string), duration_minutes (int), priority ("low"|"medium"|"high"),
  category ("walk"|"feed"|"meds"|"enrichment"|"grooming"|"general"),
  required (bool)

Do not include tasks that have no basis in the provided guidelines.
Aim for 4-7 tasks that fit a typical owner's day.

PET INFO:
- Name: {safe_name}
- Species: {pet_info['species']}
- Age: {pet_info.get('age', 'unknown')} years
- Breed: {safe_breed}
- Energy level: {pet_info.get('energy_level') or 'unknown'}
- Needs medication: {pet_info.get('needs_medication', False)}

RELEVANT CARE GUIDELINES:
{context}

Respond with ONLY the JSON array, no explanation."""

    def suggest_tasks(
        self,
        name: str,
        species: str,
        age: Optional[int] = None,
        energy_level: Optional[str] = None,
        needs_medication: bool = False,
        breed: Optional[str] = None,
    ) -> list[Task]:
        """Return a list of suggested Task objects for the given pet."""
        pet_info = {
            "name": name, "species": species, "age": age,
            "energy_level": energy_level, "needs_medication": needs_medication,
            "breed": breed,
        }

        query = self._build_query(name, species, age, energy_level, needs_medication, breed)
        chunks = self._retrieve(query)
        if not chunks:
            return []

        prompt = self._build_prompt(pet_info, chunks)

        response = self._groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        import json
        task_dicts = json.loads(raw)

        tasks = []
        for td in task_dicts:
            try:
                clean = validate_llm_task(td)
                tasks.append(Task(**clean))
            except (ValidationError, ValueError):
                continue

        return tasks
