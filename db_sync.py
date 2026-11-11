import logging
import psycopg
from typing import Dict, List
from config import DB_CONFIG
from parser import DesktopEntry

logger = logging.getLogger(__name__)

class DatabaseSynchronizer:
    def __init__(self):
        self.config = DB_CONFIG

    def _get_connection(self):
        return psycopg.connect(
            host=self.config["host"],
            port=self.config["port"],
            dbname=self.config["dbname"],
            user=self.config["user"],
            password=self.config["password"]
        )

    def init_db(self):
        """Create tables if they don't exist"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Table for applications
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS applications (
                            filename TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            category TEXT,
                            comment TEXT,
                            exec_cmd TEXT,
                            icon TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Table for usage statistics
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS usage_stats (
                            filename TEXT PRIMARY KEY REFERENCES applications(filename) ON DELETE CASCADE,
                            launch_count INTEGER DEFAULT 0,
                            last_used TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Table for categories (for semester project metadata)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS categories (
                            name TEXT PRIMARY KEY,
                            description TEXT
                        )
                    """)
                    
                    conn.commit()
            logger.info("Database tables initialized")
            return True
        except Exception as e:
            # If database 'catwalker' doesn't exist, we might need to create it
            if "does not exist" in str(e).lower():
                logger.error(f"Database '{self.config['dbname']}' does not exist. Please create it first: 'createdb {self.config['dbname']}'")
            else:
                logger.error(f"Failed to initialize database: {e}")
            return False

    def sync(self, entries: Dict[str, DesktopEntry], usage_data: Dict[str, Dict], categorized: Dict[str, str]):
        """Sync all data to PostgreSQL"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Sync Categories
                    all_categories = set(categorized.values())
                    for cat_name in all_categories:
                        cur.execute("""
                            INSERT INTO categories (name) 
                            VALUES (%s) 
                            ON CONFLICT (name) DO NOTHING
                        """, (cat_name,))

                    # 2. Sync Applications and Usage
                    for filename, entry in entries.items():
                        category = categorized.get(filename)
                        
                        # Upsert application
                        cur.execute("""
                            INSERT INTO applications (filename, name, category, comment, exec_cmd, icon, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                            ON CONFLICT (filename) DO UPDATE SET
                                name = EXCLUDED.name,
                                category = EXCLUDED.category,
                                comment = EXCLUDED.comment,
                                exec_cmd = EXCLUDED.exec_cmd,
                                icon = EXCLUDED.icon,
                                updated_at = CURRENT_TIMESTAMP
                        """, (filename, entry.name, category, entry.comment, entry.exec_cmd, entry.icon))

                        # Upsert usage (if we have usage data)
                        app_usage = usage_data.get(filename, {})
                        count = app_usage.get("count", 0)
                        last_used = app_usage.get("last_used")
                        
                        if count > 0:
                            cur.execute("""
                                INSERT INTO usage_stats (filename, launch_count, last_used, updated_at)
                                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                                ON CONFLICT (filename) DO UPDATE SET
                                    launch_count = EXCLUDED.launch_count,
                                    last_used = EXCLUDED.last_used,
                                    updated_at = CURRENT_TIMESTAMP
                            """, (filename, count, last_used))

                conn.commit()
            logger.info(f"Successfully synchronized {len(entries)} applications to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Failed to sync to database: {e}")
            return False
