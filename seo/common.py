"""Общие утилиты SEO-инструментов: чтение .env.seo, подключение к sqlite."""
import os
import sqlite3

SEO_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SEO_DIR)
ENV_PATH = os.path.join(REPO_ROOT, ".env.seo")
DB_PATH = os.path.join(SEO_DIR, "keywords.sqlite")


def load_env(path=ENV_PATH):
    """Читает .env.seo (KEY=VALUE) в dict. Не печатает значения."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def get_db(path=DB_PATH):
    """Подключение к sqlite с созданием схемы."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS keywords (
            query       TEXT PRIMARY KEY,   -- нормализованный запрос (lower, strip)
            cluster     TEXT,
            pillar      TEXT,
            intent      TEXT,
            geo_level   TEXT,
            target_url  TEXT,
            page_needed INTEGER DEFAULT 0,  -- 1 = страницы нет (NEW)
            priority    TEXT,
            status      TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS webmaster_queries (
            query       TEXT,
            date_from   TEXT,
            date_to     TEXT,
            shows       INTEGER DEFAULT 0,
            clicks      INTEGER DEFAULT 0,
            ctr         REAL DEFAULT 0,
            position    REAL,
            fetched_at  TEXT,
            PRIMARY KEY (query, date_from, date_to)
        );

        CREATE TABLE IF NOT EXISTS wordstat (
            query       TEXT,
            region      TEXT,
            freq_base   INTEGER,            -- базовая частотность (фраза целиком)
            freq_exact  INTEGER,            -- точная ("!фраза")
            fetched_at  TEXT,
            PRIMARY KEY (query, region)
        );
        """
    )
    conn.commit()
