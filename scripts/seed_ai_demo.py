"""Seed AI demo data: knowledge, prompts, memory, a mock daily run and evals."""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
os.environ.setdefault("AI_PROVIDER_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.ai.evals.runner import run_eval_suite  # noqa: E402
from app.ai.knowledge.ingestion import ingest_document  # noqa: E402
from app.ai.memory.business import list_memories  # noqa: E402
from app.ai.orchestrator.runner import start_run  # noqa: E402
from app.ai.prompts.registry import sync_prompts  # noqa: E402
from app.ai.tools.build_registry import build_registry  # noqa: E402
from app.ai.tools.memory import write_business_memory  # noqa: E402
from app.core.database import Base  # noqa: E402

KNOWLEDGE = [
    ("BRAND", "Brand Overview", "We sell a vintage cassette player for music discovery. Brand voice: nostalgic, tactile, anti-streaming."),
    ("PRODUCT", "Product Specs", "Cassette Player C-100: battery 12h, USB-C, supports aux, wood-accent shell, $89 retail, break-even CPA 30."),
    ("RULES", "Growth Rule Glossary", "NO_PURCHASE_BURN: spend >= 2x target CPA with zero purchases. CREATIVE_FATIGUE: CTR drop + frequency rise."),
    ("CREATIVE", "Creative Taxonomy", "Labels: CASSETTE_INSERT, LID_CLOSE, PLAY_BUTTON, TAPE_ROTATION, HEADPHONE_LISTENING, BEDROOM_NOSTALGIA, GIFT_UNBOXING."),
    ("SITE", "Site Funnel Documentation", "Funnel: landing -> product view -> add to cart -> checkout -> purchase. Checkout uses Shopify standard checkout."),
    ("OFFER", "Offer / Price Policy", "Current offer: 10% first order. Free shipping over $75. 30-day returns."),
]


async def main() -> int:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        build_registry()
        prompt_count = await sync_prompts(db)
        print(f"prompts synced: {prompt_count} new")
        for doc_type, title, content in KNOWLEDGE:
            result = await ingest_document(db, document_type=doc_type, title=title, content=content, source_uri=f"seed://{title.lower().replace(' ', '-')}")
            print(f"knowledge: {title} ({result['chunks']} chunks)")
        await write_business_memory(
            db,
            statement="Tactile cassette-loading hooks historically outperform static product shots (mock evidence).",
            memory_type="CREATIVE",
            evidence_refs=["rule://META_WINNER_CREATIVE", "creative://demo"],
            confidence=0.6,
            run_id="seed-ai",
        )
        memories = await list_memories(db)
        print(f"business memory proposed: {len(memories)}")
        run = await start_run(
            db,
            task_type="DAILY_GROWTH_REVIEW",
            user_request="Daily growth review from rule findings",
            scope={"platforms": ["META", "GOOGLE"]},
        )
        print(f"mock daily review run: {run['run_id']} status={run['status']}")
        eval_result = await run_eval_suite(db, "all")
        print(f"evals: passed={eval_result['passed']} failed={eval_result['failed']} scores={eval_result['aggregate_scores']}")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
