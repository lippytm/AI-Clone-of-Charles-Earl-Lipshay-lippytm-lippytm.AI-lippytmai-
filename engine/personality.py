"""
engine/personality.py
Personality profile loader and style enforcer for the AI Clone Engine.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PersonalityProfile:
    name: str = "Charles Earl Lipshay"
    handle: str = "lippytm"
    tagline: str = "lippytmai"
    traits: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    speech_style: dict[str, Any] = field(default_factory=dict)
    knowledge_domains: list[str] = field(default_factory=list)
    catchphrases: list[str] = field(default_factory=list)
    system_prompt: str = ""

    @classmethod
    def from_file(cls, path: str) -> "PersonalityProfile":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def build_system_prompt(self) -> str:
        """Compose the LLM system prompt from the personality profile."""
        if self.system_prompt:
            return self.system_prompt

        traits_str = ", ".join(self.traits) if self.traits else "thoughtful, direct, curious"
        interests_str = ", ".join(self.interests) if self.interests else "AI, technology, creativity"
        domains_str = ", ".join(self.knowledge_domains) if self.knowledge_domains else "general knowledge"
        style_notes = self.speech_style.get("notes", "conversational and authentic")
        catchphrase_str = ""
        if self.catchphrases:
            catchphrase_str = (
                f" Occasionally use one of these catchphrases naturally: "
                + "; ".join(f'"{p}"' for p in self.catchphrases)
                + "."
            )

        return (
            f"You are an AI clone of {self.name} (GitHub: @{self.handle}, AI handle: {self.tagline}). "
            f"You embody their personality exactly: {traits_str}. "
            f"Your primary interests are: {interests_str}. "
            f"Your expertise covers: {domains_str}. "
            f"Your communication style is {style_notes}.{catchphrase_str} "
            "Respond as Charles Earl Lipshay would — authentic, first-person, never breaking character. "
            "Do NOT say you are an AI unless directly and sincerely asked."
        )

    def apply_style(self, text: str) -> str:
        """Post-process a response to match speech style rules."""
        style = self.speech_style

        if style.get("lowercase_i", False):
            text = re.sub(r"\bI\b", "i", text)

        if style.get("no_em_dash", False):
            text = text.replace("—", " - ")

        replacements: dict[str, str] = style.get("replacements", {})
        for src, dst in replacements.items():
            text = text.replace(src, dst)

        return text
