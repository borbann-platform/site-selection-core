"""
Seed the knowledge base with documentation for RAG.
Chunks markdown files and embeds them into pgvector.

Usage:
    python -m scripts.seed_knowledge_base
    python -m scripts.seed_knowledge_base --clear  # Clear and re-seed
"""

import argparse
import logging
import re
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.documents import Document
from src.config.agent_settings import agent_settings
from src.services.rag_service import chunk_text, rag_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Documentation files to index
DOCS_DIR = Path(__file__).parent.parent / "docs"
DOCS_TO_INDEX = [
    "data_dictionary.md",
    "api.md",
    "hgt_usage_guide.md",
    "data_processing.md",
]


def parse_markdown_sections(content: str, filename: str) -> list[Document]:
    """
    Parse markdown into sections based on headers.

    Args:
        content: Markdown content
        filename: Source filename for metadata

    Returns:
        List of Document objects with section metadata

    """
    documents = []

    # Split by headers (## or ###)
    sections = re.split(r"\n(#{2,3}\s+[^\n]+)\n", content)

    current_section = ""
    current_content = []

    for i, part in enumerate(sections):
        if re.match(r"^#{2,3}\s+", part):
            # This is a header
            if current_content:
                # Save previous section
                text = "\n".join(current_content).strip()
                if text:
                    # Chunk the section if it's too long
                    chunks = chunk_text(text)
                    for j, chunk in enumerate(chunks):
                        documents.append(
                            Document(
                                page_content=chunk,
                                metadata={
                                    "source": filename,
                                    "section": current_section,
                                    "chunk_index": j,
                                },
                            )
                        )

            current_section = part.strip().lstrip("#").strip()
            current_content = [part]  # Include header in content
        else:
            current_content.append(part)

    # Don't forget the last section
    if current_content:
        text = "\n".join(current_content).strip()
        if text:
            chunks = chunk_text(text)
            for j, chunk in enumerate(chunks):
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "source": filename,
                            "section": current_section or "Introduction",
                            "chunk_index": j,
                        },
                    )
                )

    return documents


def load_documents() -> list[Document]:
    """
    Load and parse all documentation files.

    Returns:
        List of Document objects ready for embedding

    """
    all_documents = []

    for doc_file in DOCS_TO_INDEX:
        doc_path = DOCS_DIR / doc_file

        if not doc_path.exists():
            logger.warning(f"Document not found: {doc_path}")
            continue

        logger.info(f"Loading {doc_file}...")
        content = doc_path.read_text(encoding="utf-8")

        if doc_file.endswith(".md"):
            documents = parse_markdown_sections(content, doc_file)
        else:
            # For non-markdown, just chunk the whole thing
            chunks = chunk_text(content)
            documents = [
                Document(
                    page_content=chunk, metadata={"source": doc_file, "chunk_index": i}
                )
                for i, chunk in enumerate(chunks)
            ]

        all_documents.extend(documents)
        logger.info(f"  → {len(documents)} chunks from {doc_file}")

    # Add system information document
    system_doc = Document(
        page_content="""
# Real Estate Platform Overview

This platform provides real estate analysis for Bangkok, Thailand.

## Key Features
- **Price Prediction**: ML-based property valuation with SHAP explanations
- **Location Intelligence**: Scores for transit, walkability, schools, flood risk
- **Site Analysis**: Business potential evaluation with competitor/magnet counts
- **Catchment Analysis**: Isochrone-based population reach calculation
- **Market Statistics**: District-level pricing data

## Data Coverage
- Bangkok metropolitan area
- 50,000+ appraised property prices from Treasury Department
- Transit data (BTS, MRT, ARL, buses, ferries)
- POIs: schools, hospitals, malls, restaurants, etc.

## Currency
All prices are in Thai Baht (THB).
1 USD ≈ 35 THB (approximate)
1 square wah (ตารางวา) = 4 square meters

## Building Types (Thai)
- บ้านเดี่ยว = Detached house
- ทาวน์เฮ้าส์ = Townhouse
- บ้านแฝด = Semi-detached house
- อาคารพาณิชย์ = Commercial building
- ตึกแถว = Shophouse
        """.strip(),
        metadata={"source": "system_info", "section": "Overview", "chunk_index": 0},
    )
    all_documents.append(system_doc)

    return all_documents


def seed_knowledge_base(clear: bool = False):
    """
    Seed the knowledge base with documentation.

    Args:
        clear: If True, clear existing documents first

    """
    if not agent_settings.is_configured:
        logger.error("Agent not configured. Set GOOGLE_API_KEY in .env file.")
        sys.exit(1)

    # Check current document count
    try:
        current_count = rag_service.get_document_count()
        logger.info(f"Current knowledge base size: {current_count} documents")
    except Exception as e:
        logger.warning(f"Could not get document count: {e}")
        current_count = 0

    if clear and current_count > 0:
        logger.info("Clearing existing knowledge base...")
        rag_service.clear_collection()

    # Load and process documents
    documents = load_documents()
    logger.info(f"Total documents to index: {len(documents)}")

    if not documents:
        logger.warning("No documents to index!")
        return

    # Add to vector store in batches
    batch_size = 50
    total_added = 0

    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        try:
            ids = rag_service.add_documents(batch)
            total_added += len(ids)
            logger.info(f"  Added batch {i // batch_size + 1}: {len(ids)} documents")
        except Exception as e:
            logger.error(f"  Failed to add batch: {e}")

    logger.info(f"✓ Knowledge base seeded with {total_added} documents")

    # Verify
    try:
        final_count = rag_service.get_document_count()
        logger.info(f"Final knowledge base size: {final_count} documents")
    except Exception as e:
        logger.warning(f"Could not verify final count: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Seed the knowledge base with documentation for RAG"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing documents before seeding",
    )
    args = parser.parse_args()

    seed_knowledge_base(clear=args.clear)


if __name__ == "__main__":
    main()
