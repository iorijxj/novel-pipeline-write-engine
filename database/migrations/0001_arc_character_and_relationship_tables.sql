CREATE TABLE IF NOT EXISTS arc_character_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id),
    character_id INTEGER NOT NULL REFERENCES characters(id),
    chapter_no INTEGER NOT NULL,
    physical_state TEXT DEFAULT '',
    emotional_state TEXT DEFAULT '',
    arc_progress TEXT DEFAULT '',
    key_decisions TEXT DEFAULT '[]',
    active_relationships TEXT DEFAULT '[]',
    UNIQUE(novel_id, character_id, chapter_no)
);

CREATE TABLE IF NOT EXISTS character_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id),
    char_a TEXT NOT NULL,
    char_b TEXT NOT NULL,
    relation_type TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, char_a, char_b)
);
