"""
Create user_properties table for storing user-submitted properties and valuations.

Run this script to create the table:
    uv run python -m scripts.create_user_properties_table
"""

from sqlalchemy import text
from src.config.database import SessionLocal


def create_user_properties_table():
    """Create the user_properties table if it doesn't exist."""
    db = SessionLocal()

    try:
        # Check if table exists
        result = db.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user_properties'
                )
            """)
        ).scalar()

        if result:
            print("Table 'user_properties' already exists.")
            return

        # Create table
        db.execute(
            text("""
                CREATE TABLE user_properties (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR,
                    
                    -- Property details
                    building_style VARCHAR,
                    building_area FLOAT,
                    land_area FLOAT,
                    no_of_floor INTEGER,
                    building_age FLOAT,
                    
                    -- Location
                    amphur VARCHAR,
                    tumbon VARCHAR,
                    village VARCHAR,
                    address TEXT,
                    
                    -- User-provided price
                    asking_price FLOAT,
                    
                    -- AI Valuation results
                    estimated_price FLOAT,
                    confidence VARCHAR,
                    confidence_score FLOAT,
                    model_type VARCHAR,
                    h3_index VARCHAR,
                    is_cold_start BOOLEAN,
                    
                    -- Metadata (JSON)
                    valuation_factors JSONB,
                    market_insights JSONB,
                    
                    -- Timestamps
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    
                    -- Geometry
                    geometry GEOMETRY(POINT, 4326)
                )
            """)
        )

        # Create indexes
        db.execute(
            text("CREATE INDEX idx_user_properties_user_id ON user_properties(user_id)")
        )
        db.execute(
            text("CREATE INDEX idx_user_properties_amphur ON user_properties(amphur)")
        )
        db.execute(
            text(
                "CREATE INDEX idx_user_properties_h3_index ON user_properties(h3_index)"
            )
        )
        db.execute(
            text(
                "CREATE INDEX idx_user_properties_geometry ON user_properties USING GIST(geometry)"
            )
        )
        db.execute(
            text(
                "CREATE INDEX idx_user_properties_created_at ON user_properties(created_at DESC)"
            )
        )

        db.commit()
        print("Successfully created 'user_properties' table with indexes.")

    except Exception as e:
        db.rollback()
        print(f"Error creating table: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_user_properties_table()
