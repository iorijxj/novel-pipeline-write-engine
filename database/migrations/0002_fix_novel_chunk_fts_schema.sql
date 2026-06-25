DROP TABLE IF EXISTS novel_chunk_fts;

CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
    content,
    content='chapter_chunks', content_rowid='id'
);
