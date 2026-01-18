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

    # Add Bangkok districts knowledge
    bangkok_districts_doc = Document(
        page_content="""
# Bangkok District Guide for Real Estate

## Premium Districts (High-end residential, expat-friendly)
- **วัฒนา (Watthana)**: Home to Sukhumvit Soi 1-63. International schools, embassies. Avg price: 15-40M THB.
- **ปทุมวัน (Pathum Wan)**: Central Bangkok, Siam area. Commercial hub. Avg price: 20-50M THB.
- **คลองเตย (Khlong Toei)**: Lower Sukhumvit, near port. Mixed development. Avg price: 8-25M THB.

## Mid-Range Districts (Growing, good value)
- **พระโขนง (Phra Khanong)**: On Nut area, BTS accessible. Popular with young professionals. Avg: 4-12M THB.
- **ลาดพร้าว (Lat Phrao)**: Large district, MRT access. Family-friendly. Avg: 3-10M THB.
- **จตุจักร (Chatuchak)**: Near famous market, MRT hub. Avg: 5-15M THB.
- **ห้วยขวาง (Huai Khwang)**: MRT Blue Line, affordable condos. Avg: 3-8M THB.

## Affordable Districts (Suburbs, emerging)
- **บางกะปิ (Bang Kapi)**: East Bangkok, affordable houses. Avg: 2-6M THB.
- **บางนา (Bang Na)**: Near BITEC, improving transit. Avg: 2-7M THB.
- **มีนบุรี (Min Buri)**: Pink Line access, suburban feel. Avg: 1.5-5M THB.

## Price Factors by District
1. BTS/MRT proximity: +15-30% within 500m
2. International school access: +10-25%
3. Shopping mall proximity: +5-15%
4. Flood history: -10-20% in risk zones
        """.strip(),
        metadata={
            "source": "bangkok_knowledge",
            "section": "Districts",
            "chunk_index": 0,
        },
    )
    all_documents.append(bangkok_districts_doc)

    # Add transit knowledge
    transit_doc = Document(
        page_content="""
# Bangkok Public Transit Guide

## BTS Skytrain (Green Lines)
- **Sukhumvit Line**: Mo Chit to Kheha, passes through prime areas
- **Silom Line**: National Stadium to Bang Wa
- Properties within 500m of BTS command 15-30% premium

## MRT Metro
- **Blue Line**: Circular line covering central Bangkok
- **Purple Line**: Bang Yai to Tao Poon (northwest)
- **Yellow Line**: Lat Phrao to Samrong
- **Pink Line**: Khae Rai to Min Buri (newest)
- **Orange Line**: Under construction, will connect east-west

## Airport Links
- **ARL (Airport Rail Link)**: Suvarnabhumi to Phaya Thai
- Properties near ARL stations: +10-20% for commuter convenience

## Impact on Property Values
- Within 200m of station: +25-35% premium
- 200-500m: +15-25% premium
- 500-1000m: +5-15% premium
- Beyond 1km: minimal transit premium
        """.strip(),
        metadata={
            "source": "bangkok_knowledge",
            "section": "Transit",
            "chunk_index": 0,
        },
    )
    all_documents.append(transit_doc)

    # Add market trends knowledge
    market_doc = Document(
        page_content="""
# Bangkok Real Estate Market Trends

## 2023-2024 Market Conditions
- Post-COVID recovery continuing
- Average price growth: 3-5% annually
- Condo oversupply in some areas
- Houses/townhouses in higher demand

## Hot Areas for Investment
1. **On Nut-Bearing**: Affordable with improving infrastructure
2. **Rama 9**: New CBD development
3. **Bang Na-Trad corridor**: Industrial growth
4. **Minburi**: Pink Line opened

## Price Trends by Property Type
- Detached houses (บ้านเดี่ยว): +4-6% YoY
- Townhouses (ทาวน์เฮ้าส์): +3-5% YoY  
- Condos: 0-3% YoY (oversupply in some areas)

## Buyer Demographics
- Thai nationals: 85% of transactions
- Foreigners: 15% (limited to condos)
- First-time buyers prefer: townhouses, 3-6M THB range
- Expats prefer: Sukhumvit, near international schools

## Rental Yields
- Prime areas: 3-5% gross yield
- Suburban: 5-7% gross yield
- Near universities: 6-8% gross yield
        """.strip(),
        metadata={
            "source": "bangkok_knowledge",
            "section": "Market Trends",
            "chunk_index": 0,
        },
    )
    all_documents.append(market_doc)

    # Add flood risk knowledge
    flood_doc = Document(
        page_content="""
# Bangkok Flood Risk Guide

## High Risk Areas
- Areas along Chao Phraya River
- Parts of Don Mueang, Bang Khen
- Low-lying areas in east Bangkok
- Near canals (khlongs) without proper drainage

## Moderate Risk Areas
- Parts of Lat Phrao
- Some areas in Bang Kapi
- Older neighborhoods with poor drainage

## Low Risk Areas
- Central business district (elevated)
- Most of Sukhumvit
- Sathorn-Silom corridor
- Areas with modern drainage

## Impact on Property Values
- High flood risk: -15-25% discount
- Moderate risk: -5-10% discount
- Properties on raised foundations: reduced impact
- Ground floor units most affected

## Mitigation
- Properties with flood walls
- Raised construction
- Good building management
- Location on higher ground
        """.strip(),
        metadata={
            "source": "bangkok_knowledge",
            "section": "Flood Risk",
            "chunk_index": 0,
        },
    )
    all_documents.append(flood_doc)

    # Add property valuation knowledge
    valuation_doc = Document(
        page_content="""
# Property Valuation Factors in Bangkok

## Primary Price Drivers
1. **Location (40-50% of value)**
   - District prestige
   - Transit accessibility
   - Amenities nearby

2. **Building Characteristics (30-40%)**
   - Total area (land + building)
   - Building age and condition
   - Number of floors/rooms
   - Construction quality

3. **External Factors (10-20%)**
   - Market conditions
   - Infrastructure projects
   - Economic outlook

## Price per Square Meter by Area Type
- Prime CBD: 150,000-300,000 THB/sqm
- Inner suburbs: 80,000-150,000 THB/sqm
- Outer suburbs: 40,000-80,000 THB/sqm
- Peripheral areas: 20,000-40,000 THB/sqm

## Depreciation
- New construction: Full value
- 5 years: -5-10%
- 10 years: -10-20%
- 20+ years: -20-35%
- Well-maintained properties depreciate less

## Premium Features
- Corner lot: +5-10%
- Swimming pool: +3-5%
- Modern kitchen: +2-4%
- Garden/yard: +5-10%
- Parking for 2+ cars: +3-5%
        """.strip(),
        metadata={
            "source": "bangkok_knowledge",
            "section": "Valuation",
            "chunk_index": 0,
        },
    )
    all_documents.append(valuation_doc)

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
