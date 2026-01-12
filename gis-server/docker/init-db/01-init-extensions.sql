-- Enable required PostgreSQL extensions for the GIS server
-- This script runs automatically on first container startup

-- PostGIS for geospatial features
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- pgvector for vector embeddings (RAG agent)
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extensions
DO $$ BEGIN RAISE NOTICE 'Extensions enabled: postgis, postgis_topology, vector';

END $$;