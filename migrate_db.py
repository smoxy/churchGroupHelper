"""
Database Migration Script

This script migrates the existing SQLite database to be compatible
with the new SQLAlchemy ORM models by adding missing columns.
"""

import sqlite3
import sys
import os
from pathlib import Path

def migrate_database(db_path='/data/bot.db'):
    """
    Migrate the database by adding missing columns to existing tables.
    """
    print(f"Starting database migration for: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("No migration needed - database will be created with correct schema on first run.")
        return True
    
    # Backup the database first
    backup_path = f"{db_path}.backup"
    print(f"Creating backup at: {backup_path}")
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print("✓ Backup created successfully")
    except Exception as e:
        print(f"✗ Failed to create backup: {e}")
        return False
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("✓ Connected to database")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return False
    
    # Check and add missing columns
    migrations = [
        {
            'table': 'authorized_groups',
            'column': 'church_id',
            'type': 'INTEGER',
            'sql': 'ALTER TABLE authorized_groups ADD COLUMN church_id INTEGER'
        },
        {
            'table': 'authorized_groups',
            'column': 'last_cleanup',
            'type': 'DATETIME',
            'sql': 'ALTER TABLE authorized_groups ADD COLUMN last_cleanup DATETIME'
        }
    ]
    
    for migration in migrations:
        table = migration['table']
        column = migration['column']
        
        # Check if column exists
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        
        if column in columns:
            print(f"✓ Column {table}.{column} already exists")
        else:
            print(f"Adding column {table}.{column}...")
            try:
                cursor.execute(migration['sql'])
                conn.commit()
                print(f"✓ Added column {table}.{column}")
            except Exception as e:
                print(f"✗ Failed to add column {table}.{column}: {e}")
                conn.rollback()
                conn.close()
                return False
    
    conn.close()
    print("\n✓ Migration completed successfully!")
    print(f"Backup available at: {backup_path}")
    return True

if __name__ == "__main__":
    # Check if custom db path provided
    db_path = sys.argv[1] if len(sys.argv) > 1 else '/data/bot.db'
    
    success = migrate_database(db_path)
    sys.exit(0 if success else 1)
