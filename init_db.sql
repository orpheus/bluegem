-- Create tables for the agentic framework

-- Create projects table
CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    project_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    CONSTRAINT check_project_status CHECK (status IN ('draft', 'active', 'review', 'completed', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_project_created ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_project_status ON projects(status);

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    image_url TEXT,
    type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    model_no VARCHAR(200),
    qty INTEGER NOT NULL DEFAULT 1,
    key VARCHAR(100),
    confidence_score FLOAT NOT NULL DEFAULT 0.0,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    extraction_metadata JSONB DEFAULT '{}',
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 1),
    CONSTRAINT check_qty_positive CHECK (qty > 0)
);

CREATE INDEX IF NOT EXISTS idx_product_confidence ON products(confidence_score);
CREATE INDEX IF NOT EXISTS idx_product_project ON products(project_id);
CREATE INDEX IF NOT EXISTS idx_product_type ON products(type);
CREATE INDEX IF NOT EXISTS idx_product_url ON products(url);
CREATE INDEX IF NOT EXISTS idx_product_verified ON products(verified);

-- Create verification_requests table
CREATE TABLE IF NOT EXISTS verification_requests (
    id VARCHAR PRIMARY KEY,
    product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    reviewed_at TIMESTAMP,
    reviewer VARCHAR(100),
    corrections JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_priority_range CHECK (priority >= 1 AND priority <= 10),
    CONSTRAINT check_verification_status CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_verification_created ON verification_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_verification_priority ON verification_requests(priority);
CREATE INDEX IF NOT EXISTS idx_verification_status ON verification_requests(status);

-- Create change_history table
CREATE TABLE IF NOT EXISTS change_history (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    field VARCHAR(100) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    change_type VARCHAR(20) NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_change_type CHECK (change_type IN ('added', 'removed', 'modified'))
);

CREATE INDEX IF NOT EXISTS idx_change_detected ON change_history(detected_at);
CREATE INDEX IF NOT EXISTS idx_change_product ON change_history(product_id);

-- Create task_queue table
CREATE TABLE IF NOT EXISTS task_queue (
    id VARCHAR PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    task_data JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    result JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT check_task_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_task_created ON task_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_task_status ON task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_type ON task_queue(task_type);

-- Create alembic version table
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL
);

-- Insert the migration version
INSERT INTO alembic_version (version_num) VALUES ('45fdf300c4aa') ON CONFLICT DO NOTHING;