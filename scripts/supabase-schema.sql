-- SupaChat Blog Analytics Schema
-- Run this in your Supabase SQL editor to set up the database

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Authors ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS authors (
    id          UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    bio         TEXT,
    avatar_url  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Topics ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS topics (
    id          UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Articles ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS articles (
    id                  UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    title               TEXT NOT NULL,
    slug                TEXT UNIQUE NOT NULL,
    topic               TEXT NOT NULL,
    topic_id            UUID REFERENCES topics(id),
    author_id           UUID REFERENCES authors(id),
    published_at        TIMESTAMPTZ DEFAULT NOW(),
    read_time_minutes   INTEGER DEFAULT 5,
    word_count          INTEGER DEFAULT 1000,
    is_published        BOOLEAN DEFAULT true,
    tags                TEXT[],
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_articles_topic ON articles(topic);
CREATE INDEX idx_articles_author_id ON articles(author_id);
CREATE INDEX idx_articles_published_at ON articles(published_at);

-- ── Article Metrics (daily) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS article_metrics (
    id                  UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    article_id          UUID REFERENCES articles(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    views               INTEGER DEFAULT 0,
    unique_visitors     INTEGER DEFAULT 0,
    avg_time_on_page    FLOAT DEFAULT 0,
    bounce_rate         FLOAT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(article_id, date)
);

CREATE INDEX idx_metrics_article_date ON article_metrics(article_id, date);
CREATE INDEX idx_metrics_date ON article_metrics(date);

-- ── Comments ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comments (
    id          UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    article_id  UUID REFERENCES articles(id) ON DELETE CASCADE,
    author_name TEXT NOT NULL,
    content     TEXT,
    sentiment   TEXT CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_comments_article ON comments(article_id);

-- ── Social Shares ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS social_shares (
    id          UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    article_id  UUID REFERENCES articles(id) ON DELETE CASCADE,
    platform    TEXT CHECK (platform IN ('twitter', 'linkedin', 'reddit', 'facebook', 'hackernews')),
    shared_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Likes ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS likes (
    id          UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    article_id  UUID REFERENCES articles(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── RPC: Execute raw SQL (needed for MCP integration) ─────────────────────────
CREATE OR REPLACE FUNCTION execute_query(query_text TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    -- Safety: block dangerous operations
    IF query_text ~* '^\s*(drop|truncate|delete|insert|update|alter|create)\s' THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed';
    END IF;
    EXECUTE 'SELECT jsonb_agg(row_to_json(t)) FROM (' || query_text || ') t' INTO result;
    RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

-- Grant execute to anon role
GRANT EXECUTE ON FUNCTION execute_query TO anon;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- ── Seed Demo Data ────────────────────────────────────────────────────────────
INSERT INTO topics (name, slug) VALUES
    ('Artificial Intelligence', 'ai'),
    ('Machine Learning', 'ml'),
    ('DevOps', 'devops'),
    ('Cloud Computing', 'cloud'),
    ('Cybersecurity', 'security'),
    ('Web3 & Blockchain', 'web3'),
    ('Data Engineering', 'data-engineering'),
    ('Open Source', 'open-source')
ON CONFLICT DO NOTHING;

INSERT INTO authors (name, email, bio) VALUES
    ('Sarah Chen', 'sarah@example.com', 'AI researcher and technical writer'),
    ('Marcus Rivera', 'marcus@example.com', 'DevOps engineer and cloud architect'),
    ('Priya Patel', 'priya@example.com', 'Full-stack developer and OSS contributor'),
    ('Alex Thompson', 'alex@example.com', 'Cybersecurity expert'),
    ('Jin-woo Park', 'jinwoo@example.com', 'Data engineer and ML practitioner')
ON CONFLICT DO NOTHING;

-- Generate sample articles (last 90 days)
DO $$
DECLARE
    v_author_ids UUID[];
    v_topic_names TEXT[] := ARRAY['Artificial Intelligence','Machine Learning','DevOps','Cloud Computing','Cybersecurity'];
    v_titles TEXT[] := ARRAY[
        'Getting Started with %s in 2024',
        'Advanced %s Patterns You Should Know',
        'Why %s is Changing Everything',
        'The Future of %s',
        'Building Production-Ready %s Systems'
    ];
    i INT;
    v_topic TEXT;
    v_title TEXT;
BEGIN
    SELECT ARRAY_AGG(id) INTO v_author_ids FROM authors;

    FOR i IN 1..50 LOOP
        v_topic := v_topic_names[1 + (i % array_length(v_topic_names, 1))];
        v_title := format(v_titles[1 + (i % array_length(v_titles, 1))], v_topic);

        INSERT INTO articles (title, slug, topic, author_id, published_at, read_time_minutes, word_count)
        VALUES (
            v_title,
            'article-' || i,
            v_topic,
            v_author_ids[1 + (i % array_length(v_author_ids, 1))],
            NOW() - (random() * 90)::INT * INTERVAL '1 day',
            (3 + random() * 12)::INT,
            (500 + random() * 3000)::INT
        );
    END LOOP;
END $$;

-- Generate daily metrics for all articles
INSERT INTO article_metrics (article_id, date, views, unique_visitors, avg_time_on_page)
SELECT
    a.id,
    generate_series(
        (a.published_at::date),
        CURRENT_DATE,
        '1 day'::INTERVAL
    )::DATE as date,
    (50 + random() * 2000)::INT as views,
    (30 + random() * 1200)::INT as unique_visitors,
    (60 + random() * 420)::FLOAT as avg_time_on_page
FROM articles a
ON CONFLICT (article_id, date) DO NOTHING;

-- Generate comments and social shares
INSERT INTO comments (article_id, author_name, sentiment)
SELECT
    id,
    'User ' || (random() * 1000)::INT,
    (ARRAY['positive', 'negative', 'neutral'])[1 + (random() * 2)::INT]
FROM articles
CROSS JOIN generate_series(1, (random() * 10)::INT + 1);

INSERT INTO social_shares (article_id, platform, shared_at)
SELECT
    id,
    (ARRAY['twitter', 'linkedin', 'reddit', 'hackernews'])[1 + (random() * 3)::INT],
    published_at + (random() * 30)::INT * INTERVAL '1 day'
FROM articles
CROSS JOIN generate_series(1, (random() * 5)::INT + 1);
