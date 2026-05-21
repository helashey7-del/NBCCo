"""
Database Module - SQLite database for ratings, operators, and jobs.
Provides abstraction layer for data persistence.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager(ABC):
    """Abstract base class for database operations."""
    
    @abstractmethod
    def record_job_completion(self, job_id: str, operator_id: str, **kwargs) -> None:
        """Record job completion."""
        pass
    
    @abstractmethod
    def create_rating_request(self, job_id: str, user_phone: str, operator_id: str, status: str) -> str:
        """Create a rating request."""
        pass
    
    @abstractmethod
    def record_rating(self, request_id: str, operator_id: str, rating: int, timestamp: datetime) -> None:
        """Record a rating."""
        pass
    
    @abstractmethod
    def get_operator(self, operator_id: str) -> Optional[Dict]:
        """Get operator details."""
        pass
    
    @abstractmethod
    def update_operator_status(self, operator_id: str, status: str) -> None:
        """Update operator status."""
        pass
    
    @abstractmethod
    def get_operator_ratings(self, operator_id: str) -> List[int]:
        """Get all ratings for an operator."""
        pass


class SQLiteDatabaseManager(DatabaseManager):
    """SQLite implementation of database manager."""
    
    def __init__(self, db_path: str = "nbcco_ratings.db"):
        """
        Initialize SQLite database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self) -> None:
        """Initialize database schema."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.cursor()
            
            # Operators table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operators (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone_number TEXT UNIQUE NOT NULL,
                    email TEXT,
                    status TEXT DEFAULT 'Active',
                    average_rating REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    blocked_from_queue BOOLEAN DEFAULT 0
                )
            """)
            
            # Jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    operator_id TEXT NOT NULL,
                    user_phone TEXT NOT NULL,
                    operator_phone TEXT NOT NULL,
                    status TEXT DEFAULT 'Pending',
                    completion_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (operator_id) REFERENCES operators(id)
                )
            """)
            
            # Rating requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rating_requests (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    user_phone TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id),
                    FOREIGN KEY (operator_id) REFERENCES operators(id)
                )
            """)
            
            # Ratings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                    feedback TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES rating_requests(id),
                    FOREIGN KEY (operator_id) REFERENCES operators(id)
                )
            """)
            
            # Create indices for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_operator_status ON operators(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_operator ON jobs(operator_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_operator ON ratings(operator_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_request_status ON rating_requests(status)")
            
            self.conn.commit()
            logger.info(f"Database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}", exc_info=True)
            raise
    
    def record_job_completion(
        self,
        job_id: str,
        operator_id: str,
        user_phone: str,
        operator_phone: str,
        completion_time: datetime,
        **kwargs
    ) -> None:
        """Record job completion."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO jobs 
                (id, operator_id, user_phone, operator_phone, status, completion_time)
                VALUES (?, ?, ?, ?, 'Completed', ?)
            """, (job_id, operator_id, user_phone, operator_phone, completion_time))
            self.conn.commit()
            logger.debug(f"Job completion recorded: {job_id}")
        except Exception as e:
            logger.error(f"Error recording job completion: {str(e)}", exc_info=True)
            raise
    
    def create_rating_request(
        self,
        job_id: str,
        user_phone: str,
        operator_id: str,
        status: str = "pending"
    ) -> str:
        """Create a rating request and return request ID."""
        try:
            request_id = f"REQ-{job_id}-{int(datetime.now().timestamp())}"
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO rating_requests 
                (id, job_id, operator_id, user_phone, status)
                VALUES (?, ?, ?, ?, ?)
            """, (request_id, job_id, operator_id, user_phone, status))
            self.conn.commit()
            logger.debug(f"Rating request created: {request_id}")
            return request_id
        except Exception as e:
            logger.error(f"Error creating rating request: {str(e)}", exc_info=True)
            raise
    
    def record_rating(
        self,
        request_id: str,
        operator_id: str,
        rating: int,
        timestamp: datetime,
        feedback: Optional[str] = None
    ) -> None:
        """Record a rating."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO ratings 
                (request_id, operator_id, rating, feedback, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (request_id, operator_id, rating, feedback, timestamp))
            self.conn.commit()
            logger.debug(f"Rating recorded: {operator_id} = {rating} stars")
        except Exception as e:
            logger.error(f"Error recording rating: {str(e)}", exc_info=True)
            raise
    
    def update_rating_request_status(self, request_id: str, status: str) -> None:
        """Update rating request status."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE rating_requests 
                SET status = ?, completed_at = ?
                WHERE id = ?
            """, (status, datetime.now() if status == "completed" else None, request_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error updating rating request status: {str(e)}", exc_info=True)
            raise
    
    def get_operator(self, operator_id: str) -> Optional[Dict]:
        """Get operator details."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM operators WHERE id = ?", (operator_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting operator: {str(e)}", exc_info=True)
            return None
    
    def update_operator_status(self, operator_id: str, status: str) -> None:
        """Update operator status."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE operators 
                SET status = ?, updated_at = ?
                WHERE id = ?
            """, (status, datetime.now(), operator_id))
            self.conn.commit()
            logger.info(f"Operator {operator_id} status updated to: {status}")
        except Exception as e:
            logger.error(f"Error updating operator status: {str(e)}", exc_info=True)
            raise
    
    def update_operator_average_rating(self, operator_id: str, average: float) -> None:
        """Update operator's average rating."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE operators 
                SET average_rating = ?, updated_at = ?
                WHERE id = ?
            """, (average, datetime.now(), operator_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error updating average rating: {str(e)}", exc_info=True)
            raise
    
    def get_operator_ratings(self, operator_id: str) -> List[int]:
        """Get all ratings for an operator."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT rating FROM ratings 
                WHERE operator_id = ?
                ORDER BY timestamp DESC
            """, (operator_id,))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting operator ratings: {str(e)}", exc_info=True)
            return []
    
    def get_operator_transaction_count(self, operator_id: str) -> int:
        """Get total completed transactions for an operator."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM jobs 
                WHERE operator_id = ? AND status = 'Completed'
            """, (operator_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting transaction count: {str(e)}", exc_info=True)
            return 0
    
    def block_from_queue(self, operator_id: str) -> None:
        """Block operator from matching queue."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE operators 
                SET blocked_from_queue = 1
                WHERE id = ?
            """, (operator_id,))
            self.conn.commit()
            logger.info(f"Operator {operator_id} blocked from queue")
        except Exception as e:
            logger.error(f"Error blocking operator: {str(e)}", exc_info=True)
            raise
    
    def get_all_active_operators(self) -> List[Dict]:
        """Get all active (non-banned) operators."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM operators 
                WHERE status = 'Active'
                ORDER BY average_rating DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting active operators: {str(e)}", exc_info=True)
            return []
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    print("Database module - for use in your application")
