"""Environment-driven configuration for SIEGE."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    round_seconds: int = int(_env("ROUND_SECONDS", "90") or 90)
    auto_defend: bool = _env("AUTO_DEFEND", "true").lower() != "false"
    benign_floor: float = float(_env("BENIGN_FLOOR", "0.9") or 0.9)
    max_attempts: int = int(_env("MAX_ATTEMPTS", "3") or 3)
    variants_per_breach: int = int(_env("VARIANTS_PER_BREACH", "4") or 4)

    def to_dict(self) -> dict:
        return {
            "round_seconds": self.round_seconds,
            "auto_defend": self.auto_defend,
            "benign_floor": self.benign_floor,
            "max_attempts": self.max_attempts,
            "variants_per_breach": self.variants_per_breach,
        }


@dataclass
class Config:
    anthropic_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    typesafe_key: str = field(default_factory=lambda: _env("TYPESAFE_API_KEY"))
    wandb_key: str = field(default_factory=lambda: _env("WANDB_API_KEY"))
    weave_project: str = field(default_factory=lambda: _env("WEAVE_PROJECT", "siege") or "siege")
    agent_model: str = field(default_factory=lambda: _env("AGENT_MODEL", "claude-sonnet-5") or "claude-sonnet-5")
    defender_model: str = field(default_factory=lambda: _env("DEFENDER_MODEL", "claude-fable-5-1") or "claude-fable-5-1")
    redteam_model: str = field(default_factory=lambda: _env("REDTEAM_MODEL", "gpt-6-astra") or "gpt-6-astra")
    typesafe_model: str = field(default_factory=lambda: _env("TYPESAFE_MODEL", "") or None)
    wandb_entity: str = field(default_factory=lambda: _env("WANDB_ENTITY"))
    wandb_agent_model: str = field(default_factory=lambda: _env("WANDB_AGENT_MODEL", "openai/gpt-oss-20b") or "openai/gpt-oss-20b")
    wandb_defender_model: str = field(default_factory=lambda: _env("WANDB_DEFENDER_MODEL", "deepseek-ai/DeepSeek-V4-Pro") or "deepseek-ai/DeepSeek-V4-Pro")
    wandb_redteam_model: str = field(default_factory=lambda: _env("WANDB_REDTEAM_MODEL", "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B") or "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B")
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://localhost:8000") or "http://localhost:8000")
    db_path: Path = field(default_factory=lambda: Path(_env("SIEGE_DB", str(ROOT / "backend" / "data" / "siege.db"))))
    mode_override: str = field(default_factory=lambda: _env("SIEGE_MODE"))
    settings: Settings = field(default_factory=Settings)

    @property
    def mode(self) -> str:
        if self.mode_override in ("live", "mock"):
            return self.mode_override
        return "live" if (self.anthropic_key or self.wandb_key) else "mock"


CONFIG = Config()
