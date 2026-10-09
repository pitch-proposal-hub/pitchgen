"""PitchGen Services Package.

Contains decoupled, single-responsibility services:
- DeckTransformationService: Headless Google Slides copy polishing & in-place
transformation (Checkpoint 2)
- DeckGenerationService: Phase 1 (Outline) & Phase 2 (Slide Synthesis & Deck
Creation)
- DeckTranslationService: Headless multilingual presentation translation
"""

from services.deck_generation_service import DeckGenerationService
from services.deck_transformation_service import DeckTransformationService
from services.deck_translation_service import DeckTranslationService

__all__ = [
    "DeckTransformationService",
    "DeckGenerationService",
    "DeckTranslationService",
]
