# src/db/ — Multi-DB workspace management module
#
# registry.py     — Manage workspace/registry.json: active_slot, slots array
# slot_manager.py — Slot lifecycle (create / delete / trash recovery / ensure-by-outline)
# _conn.py        — Unified sqlite3.connect helper (WAL + timeout + foreign keys)
# init_db.py      — Schema initialization and migrations
