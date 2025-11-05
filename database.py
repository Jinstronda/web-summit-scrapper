import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List, Any

DB_NAME = "websummit_attendees.db"

def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_database():
    """Create database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            badge TEXT,
            title TEXT,
            company TEXT,
            bio TEXT,
            location TEXT,
            industry TEXT,
            communities TEXT,
            profile_url TEXT NOT NULL,
            scraped_at TEXT NOT NULL,
            meeting_requested BOOLEAN DEFAULT 0,
            request_status TEXT DEFAULT 'pending',
            request_sent_at TEXT,
            error_message TEXT,
            last_updated TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_profile_id ON attendees(profile_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_request_status ON attendees(request_status)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_meeting_requested ON attendees(meeting_requested)
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database created: {DB_NAME}")

def attendee_exists(profile_id: str) -> bool:
    """Check if attendee already exists in database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM attendees WHERE profile_id = ?', (profile_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def insert_attendee(data: Dict[str, Any]) -> int:
    """Insert new attendee into database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    communities_json = json.dumps(data.get('communities', []))
    
    cursor.execute('''
        INSERT INTO attendees (
            profile_id, name, badge, title, company, bio,
            location, industry, communities, profile_url,
            scraped_at, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['profile_id'],
        data['name'],
        data.get('badge'),
        data.get('title'),
        data.get('company'),
        data.get('bio'),
        data.get('location'),
        data.get('industry'),
        communities_json,
        data['profile_url'],
        now,
        now
    ))
    
    attendee_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return attendee_id

def update_meeting_status(profile_id: str, status: str, error: Optional[str] = None):
    """Update meeting request status for an attendee."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    meeting_requested = 1 if status == 'sent' else 0
    
    cursor.execute('''
        UPDATE attendees 
        SET meeting_requested = ?,
            request_status = ?,
            request_sent_at = ?,
            error_message = ?,
            last_updated = ?
        WHERE profile_id = ?
    ''', (
        meeting_requested,
        status,
        now if status == 'sent' else None,
        error,
        now,
        profile_id
    ))
    
    conn.commit()
    conn.close()

def get_attendee(profile_id: str) -> Optional[Dict]:
    """Get attendee by profile ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM attendees WHERE profile_id = ?', (profile_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_pending_attendees(limit: Optional[int] = None) -> List[Dict]:
    """Get attendees who haven't had meeting requests sent."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT * FROM attendees 
        WHERE meeting_requested = 0 
        ORDER BY scraped_at ASC
    '''
    
    if limit:
        query += f' LIMIT {limit}'
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_stats() -> Dict[str, int]:
    """Get database statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM attendees')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM attendees WHERE meeting_requested = 1')
    sent = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM attendees WHERE meeting_requested = 0')
    pending = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM attendees WHERE request_status = "failed"')
    failed = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total': total,
        'meeting_sent': sent,
        'pending': pending,
        'failed': failed
    }

def mark_as_failed(profile_id: str, error_message: str):
    """Mark an attendee's meeting request as failed."""
    update_meeting_status(profile_id, 'failed', error_message)

def mark_as_sent(profile_id: str):
    """Mark an attendee's meeting request as sent."""
    update_meeting_status(profile_id, 'sent')

if __name__ == '__main__':
    create_database()
    print("Database initialized successfully!")

