-- Create unified product vectors table
-- Combines all fields from product_vectors and product_vector_storage tables
-- For RAG filtering and vector storage in a single table
-- Created: 2025-01-27

-- Enable pgvector extension (if available)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create unified product vectors table
CREATE TABLE IF NOT EXISTS product_vectors (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT UNIQUE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    description TEXT,
    image_gif VARCHAR(1000),
    category_id BIGINT,
    brand VARCHAR(255),
    price DECIMAL(10, 2),
    is_recommended SMALLINT DEFAULT 0,
    product_status SMALLINT DEFAULT 0,
    
    -- Tag fields for RAG coarse-grained filtering
    scene VARCHAR(50),   -- scene: casual/sports
    color VARCHAR(50),   -- color
    style VARCHAR(50),   -- style
    fit VARCHAR(50),     -- fit
    material VARCHAR(50), -- material
    season VARCHAR(50),  -- season
    pattern VARCHAR(50), -- pattern
    
    -- Vector fields for RAG fine-grained filtering
    text_vector TEXT,                 -- Text vector, 1024 dimensions (JSON format)
    image_vector TEXT,                -- Image vector, 1024 dimensions (JSON format)
    
    -- Original data for reference
    original_data JSONB,              -- Original data JSON with image_url and text_content
    
    -- Status and timestamps
    vector_status SMALLINT DEFAULT 0, -- Vector status: 0-unprocessed, 1-text generated, 2-image generated, 3-completed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Note: Indexes will be created by RAG team based on query patterns
-- This table provides the data structure for both coarse-grained (tag) and fine-grained (vector) filtering

-- Create update timestamp trigger
CREATE OR REPLACE FUNCTION update_product_vectors_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_product_vectors_updated_at
    BEFORE UPDATE ON product_vectors
    FOR EACH ROW
    EXECUTE FUNCTION update_product_vectors_updated_at();

-- Add comments
COMMENT ON TABLE product_vectors IS 'Unified product vectors table with tag fields for RAG filtering and vector fields for similarity search';
COMMENT ON COLUMN product_vectors.id IS 'Primary key ID';
COMMENT ON COLUMN product_vectors.product_id IS 'Product ID';
COMMENT ON COLUMN product_vectors.product_name IS 'Product name';
COMMENT ON COLUMN product_vectors.description IS 'Product description';
COMMENT ON COLUMN product_vectors.image_gif IS 'Product image URL';
COMMENT ON COLUMN product_vectors.category_id IS 'Category ID';
COMMENT ON COLUMN product_vectors.brand IS 'Brand';
COMMENT ON COLUMN product_vectors.price IS 'Price';
COMMENT ON COLUMN product_vectors.scene IS 'Scene: casual/sports/formal/party';
COMMENT ON COLUMN product_vectors.color IS 'Color';
COMMENT ON COLUMN product_vectors.style IS 'Style';
COMMENT ON COLUMN product_vectors.fit IS 'Fit';
COMMENT ON COLUMN product_vectors.material IS 'Material';
COMMENT ON COLUMN product_vectors.season IS 'Season';
COMMENT ON COLUMN product_vectors.pattern IS 'Pattern';
COMMENT ON COLUMN product_vectors.text_vector IS 'Text vector, 1024 dimensions (JSON format)';
COMMENT ON COLUMN product_vectors.image_vector IS 'Image vector, 1024 dimensions (JSON format)';
COMMENT ON COLUMN product_vectors.original_data IS 'Original data JSON with image_url and text_content';
COMMENT ON COLUMN product_vectors.vector_status IS 'Vector status: 0-unprocessed, 1-text generated, 2-image generated, 3-completed';
