"""
Machinery Rental Matching Engine
Matches farmers with equipment operators based on ward location and ratings
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class MachineryMatchingEngine:
    """Handles matching farmers with machinery operators"""
    
    def __init__(self, db_path='crop_waste.db'):
        """
        Initialize matching engine.
        
        Args:
            db_path (str): Path to SQLite database
        """
        self.db_path = db_path
    
    def initialize_machinery_tables(self):
        """Create machinery-related tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create machinery_registry table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS machinery_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_phone_hash TEXT NOT NULL UNIQUE,
                    operator_name TEXT NOT NULL,
                    ward_location TEXT NOT NULL,
                    machinery_type TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    ratings REAL DEFAULT 0.0,
                    total_jobs INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_machinery_ward 
                ON machinery_registry(ward_location, is_active)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_machinery_ratings 
                ON machinery_registry(ratings DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_machinery_type 
                ON machinery_registry(machinery_type)
            ''')
            
            # Create rental_requests table to track matches
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rental_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farmer_phone_hash TEXT NOT NULL,
                    machinery_type TEXT NOT NULL,
                    ward_location TEXT NOT NULL,
                    operator_id INTEGER,
                    status TEXT DEFAULT 'Pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    matched_at TIMESTAMP,
                    FOREIGN KEY(operator_id) REFERENCES machinery_registry(id)
                )
            ''')
            
            # Create sms_log table for tracking communications
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sms_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_request_id INTEGER,
                    recipient_phone_hash TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    message_body TEXT NOT NULL,
                    status TEXT DEFAULT 'Pending',
                    sent_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(rental_request_id) REFERENCES rental_requests(id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sms_log_status 
                ON sms_log(status)
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Machinery tables initialized successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing machinery tables: {str(e)}")
            return False
    
    def register_operator(self, operator_phone_hash: str, operator_name: str, 
                         ward_location: str, machinery_type: str) -> Optional[int]:
        """
        Register a machinery operator.
        
        Args:
            operator_phone_hash (str): Hashed phone number
            operator_name (str): Operator's name
            ward_location (str): Ward location
            machinery_type (str): Type of machinery (tractor, harvester, etc.)
            
        Returns:
            int: Operator ID or None if failed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO machinery_registry 
                (operator_phone_hash, operator_name, ward_location, machinery_type, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (operator_phone_hash, operator_name, ward_location.lower(), 
                  machinery_type.lower()))
            
            conn.commit()
            operator_id = cursor.lastrowid
            conn.close()
            
            logger.info(f"Operator {operator_id} registered for {machinery_type} in {ward_location}")
            return operator_id
        
        except sqlite3.IntegrityError:
            logger.warning(f"Operator already registered: {operator_phone_hash}")
            return None
        except Exception as e:
            logger.error(f"Error registering operator: {str(e)}")
            return None
    
    def find_matching_operators(self, machinery_type: str, ward_location: str) -> List[Dict]:
        """
        Find all active operators matching machinery type and ward location.
        Returns sorted by highest rating first.
        
        Args:
            machinery_type (str): Type of machinery needed
            ward_location (str): Ward location
            
        Returns:
            list: List of operators sorted by rating (highest first)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM machinery_registry
                WHERE machinery_type = ? 
                AND ward_location = ?
                AND is_active = 1
                ORDER BY ratings DESC, total_jobs DESC
                LIMIT 10
            ''', (machinery_type.lower(), ward_location.lower()))
            
            operators = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            logger.info(f"Found {len(operators)} operators for {machinery_type} in {ward_location}")
            return operators
        
        except Exception as e:
            logger.error(f"Error finding operators: {str(e)}")
            return []
    
    def get_top_rated_operator(self, machinery_type: str, ward_location: str) -> Optional[Dict]:
        """
        Get the single highest-rated operator for a given machinery type and ward.
        
        Args:
            machinery_type (str): Type of machinery needed
            ward_location (str): Ward location
            
        Returns:
            dict: Operator details or None if no match found
        """
        operators = self.find_matching_operators(machinery_type, ward_location)
        
        if operators:
            return operators[0]  # Already sorted by rating DESC
        
        logger.warning(f"No operators found for {machinery_type} in {ward_location}")
        return None
    
    def create_rental_request(self, farmer_phone_hash: str, machinery_type: str, 
                             ward_location: str) -> Optional[int]:
        """
        Create a rental request record.
        
        Args:
            farmer_phone_hash (str): Hashed farmer phone
            machinery_type (str): Machinery type requested
            ward_location (str): Ward location
            
        Returns:
            int: Rental request ID or None if failed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO rental_requests 
                (farmer_phone_hash, machinery_type, ward_location, status)
                VALUES (?, ?, ?, 'Pending')
            ''', (farmer_phone_hash, machinery_type.lower(), ward_location.lower()))
            
            conn.commit()
            request_id = cursor.lastrowid
            conn.close()
            
            logger.info(f"Rental request {request_id} created")
            return request_id
        
        except Exception as e:
            logger.error(f"Error creating rental request: {str(e)}")
            return None
    
    def match_farmer_to_operator(self, farmer_phone_hash: str, machinery_type: str, 
                                ward_location: str) -> Optional[Dict]:
        """
        Main matching function: Find best operator for farmer and create match record.
        
        Args:
            farmer_phone_hash (str): Hashed farmer phone
            machinery_type (str): Machinery type needed
            ward_location (str): Ward location
            
        Returns:
            dict: Match details including operator info or None if no match
        """
        try:
            # Step 1: Create rental request
            request_id = self.create_rental_request(farmer_phone_hash, machinery_type, ward_location)
            
            if not request_id:
                logger.error("Failed to create rental request")
                return None
            
            # Step 2: Find best operator by rating
            operator = self.get_top_rated_operator(machinery_type, ward_location)
            
            if not operator:
                logger.info(f"No operators available for request {request_id}")
                self._update_request_status(request_id, 'No_Match')
                return None
            
            # Step 3: Update rental request with matched operator
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE rental_requests 
                SET operator_id = ?, status = 'Matched', matched_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (operator['id'], request_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Matched request {request_id} with operator {operator['id']}")
            
            # Return comprehensive match data
            return {
                'request_id': request_id,
                'farmer_phone_hash': farmer_phone_hash,
                'operator_id': operator['id'],
                'operator_name': operator['operator_name'],
                'operator_phone_hash': operator['operator_phone_hash'],
                'machinery_type': machinery_type,
                'ward_location': ward_location,
                'operator_rating': operator['ratings'],
                'operator_jobs_completed': operator['total_jobs'],
                'match_timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error in match_farmer_to_operator: {str(e)}")
            return None
    
    def _update_request_status(self, request_id: int, status: str) -> bool:
        """Update rental request status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE rental_requests SET status = ? WHERE id = ?
            ''', (status, request_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating request status: {str(e)}")
            return False
    
    def log_sms(self, request_id: int, recipient_phone_hash: str, 
               message_type: str, message_body: str, status: str = 'Pending') -> bool:
        """
        Log SMS message for tracking and resend capability.
        
        Args:
            request_id (int): Rental request ID
            recipient_phone_hash (str): SMS recipient phone hash
            message_type (str): 'to_farmer' or 'to_operator'
            message_body (str): SMS message content
            status (str): SMS delivery status
            
        Returns:
            bool: Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sms_log 
                (rental_request_id, recipient_phone_hash, message_type, message_body, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (request_id, recipient_phone_hash, message_type, message_body, status))
            
            conn.commit()
            conn.close()
            
            logger.info(f"SMS logged for request {request_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error logging SMS: {str(e)}")
            return False
    
    def mark_sms_sent(self, sms_log_id: int) -> bool:
        """Mark SMS as sent in log"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE sms_log SET status = 'Sent', sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (sms_log_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error marking SMS sent: {str(e)}")
            return False
    
    def update_operator_rating(self, operator_id: int, new_rating: float, 
                              increment_jobs: bool = False) -> bool:
        """
        Update operator rating and job count.
        
        Args:
            operator_id (int): Operator ID
            new_rating (float): New rating (0-5)
            increment_jobs (bool): Increment job count
            
        Returns:
            bool: Success status
        """
        try:
            if not (0 <= new_rating <= 5):
                logger.error(f"Invalid rating: {new_rating}")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if increment_jobs:
                cursor.execute('''
                    UPDATE machinery_registry 
                    SET ratings = ?, total_jobs = total_jobs + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_rating, operator_id))
            else:
                cursor.execute('''
                    UPDATE machinery_registry 
                    SET ratings = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_rating, operator_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated operator {operator_id} rating to {new_rating}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating operator rating: {str(e)}")
            return False
    
    def deactivate_operator(self, operator_id: int) -> bool:
        """Deactivate an operator"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE machinery_registry SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (operator_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Operator {operator_id} deactivated")
            return True
        except Exception as e:
            logger.error(f"Error deactivating operator: {str(e)}")
            return False
    
    def get_operator_details(self, operator_id: int) -> Optional[Dict]:
        """Get operator details"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM machinery_registry WHERE id = ?
            ''', (operator_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error retrieving operator details: {str(e)}")
            return None
    
    def get_pending_requests(self, limit: int = 50) -> List[Dict]:
        """Get all pending rental requests"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM rental_requests 
                WHERE status = 'Pending'
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            
            requests = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return requests
        except Exception as e:
            logger.error(f"Error retrieving pending requests: {str(e)}")
            return []
    
    def get_request_details(self, request_id: int) -> Optional[Dict]:
        """Get rental request details with operator info"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT r.*, 
                       m.operator_name, m.operator_phone_hash, m.ratings, 
                       m.machinery_type as operator_machinery
                FROM rental_requests r
                LEFT JOIN machinery_registry m ON r.operator_id = m.id
                WHERE r.id = ?
            ''', (request_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error retrieving request details: {str(e)}")
            return None
    
    def get_statistics(self) -> Dict:
        """Get machinery matching statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Total operators
            cursor.execute('SELECT COUNT(*) as count FROM machinery_registry WHERE is_active = 1')
            total_operators = cursor.fetchone()['count']
            
            # Total requests
            cursor.execute('SELECT COUNT(*) as count FROM rental_requests')
            total_requests = cursor.fetchone()['count']
            
            # Matched requests
            cursor.execute('SELECT COUNT(*) as count FROM rental_requests WHERE status = "Matched"')
            matched_requests = cursor.fetchone()['count']
            
            # By machinery type
            cursor.execute('''
                SELECT machinery_type, COUNT(*) as count 
                FROM machinery_registry 
                WHERE is_active = 1
                GROUP BY machinery_type
            ''')
            by_machinery = {row['machinery_type']: row['count'] for row in cursor.fetchall()}
            
            # Average operator rating
            cursor.execute('SELECT AVG(ratings) as avg_rating FROM machinery_registry WHERE is_active = 1')
            avg_rating = cursor.fetchone()['avg_rating'] or 0
            
            # Top operators
            cursor.execute('''
                SELECT operator_name, ratings, total_jobs, ward_location 
                FROM machinery_registry 
                WHERE is_active = 1
                ORDER BY ratings DESC 
                LIMIT 5
            ''')
            top_operators = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'total_active_operators': total_operators,
                'total_requests': total_requests,
                'matched_requests': matched_requests,
                'match_success_rate': (matched_requests / total_requests * 100) if total_requests > 0 else 0,
                'by_machinery_type': by_machinery,
                'average_operator_rating': round(avg_rating, 2),
                'top_operators': top_operators,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error retrieving statistics: {str(e)}")
            return {}
