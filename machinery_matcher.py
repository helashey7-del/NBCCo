"""
Machinery Matching Engine
Matches farmers requesting equipment with active operators in the same ward
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class MachineryMatcher:
    """Matches machinery rental requests to operators"""
    
    def __init__(self, db_path='crop_waste.db'):
        """
        Initialize machinery matcher.
        
        Args:
            db_path (str): Path to SQLite database file
        """
        self.db_path = db_path
    
    def initialize_machinery_tables(self):
        """Create machinery registry and ratings tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create machinery_registry table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS machinery_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_id TEXT NOT NULL UNIQUE,
                    operator_name TEXT NOT NULL,
                    operator_phone TEXT NOT NULL,
                    ward_location TEXT NOT NULL,
                    machinery_type TEXT NOT NULL,
                    machinery_description TEXT,
                    hourly_rate REAL NOT NULL,
                    availability_status TEXT DEFAULT 'available',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for machinery_registry
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_operator_ward 
                ON machinery_registry(ward_location, is_active)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_machinery_type 
                ON machinery_registry(machinery_type)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_operator_id 
                ON machinery_registry(operator_id)
            ''')
            
            # Create ratings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_id TEXT NOT NULL,
                    farmer_phone TEXT NOT NULL,
                    rating REAL NOT NULL CHECK(rating >= 1 AND rating <= 5),
                    review_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (operator_id) REFERENCES machinery_registry(operator_id)
                )
            ''')
            
            # Create index for operator ratings
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_operator_ratings 
                ON ratings(operator_id)
            ''')
            
            # Create rental_requests table (for tracking requests)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rental_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farmer_phone TEXT NOT NULL,
                    machinery_type TEXT NOT NULL,
                    ward_location TEXT NOT NULL,
                    matched_operator_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (matched_operator_id) REFERENCES machinery_registry(operator_id)
                )
            ''')
            
            # Create index for rental requests
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_rental_requests_status 
                ON rental_requests(status, created_at)
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Machinery tables initialized successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing machinery tables: {str(e)}")
            return False
    
    def register_operator(self, operator_id: str, operator_name: str, 
                         operator_phone: str, ward_location: str,
                         machinery_type: str, machinery_description: str,
                         hourly_rate: float) -> bool:
        """
        Register a new machinery operator.
        
        Args:
            operator_id (str): Unique operator identifier
            operator_name (str): Operator's name
            operator_phone (str): Operator's phone number
            ward_location (str): Ward where operator is based
            machinery_type (str): Type of machinery (tractor, plough, etc.)
            machinery_description (str): Details about the machinery
            hourly_rate (float): Rental rate per hour
            
        Returns:
            bool: Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO machinery_registry 
                (operator_id, operator_name, operator_phone, ward_location, 
                 machinery_type, machinery_description, hourly_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (operator_id, operator_name, operator_phone, 
                  ward_location.lower(), machinery_type.lower(),
                  machinery_description, hourly_rate))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Operator {operator_id} registered in {ward_location}")
            return True
        
        except sqlite3.IntegrityError as e:
            logger.warning(f"Operator already exists: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error registering operator: {str(e)}")
            return False
    
    def find_best_match(self, machinery_type: str, ward_location: str) -> Optional[Dict]:
        """
        Find the best operator match for a machinery rental request.
        
        Matches machinery type and ward location, then selects the operator
        with the highest average star rating.
        
        Args:
            machinery_type (str): Type of machinery requested
            ward_location (str): Ward where operator is needed
            
        Returns:
            dict: Best matching operator data or None if no match found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query to find active operators in same ward with machinery type
            # AND join with ratings to get average rating
            cursor.execute('''
                SELECT 
                    mr.id,
                    mr.operator_id,
                    mr.operator_name,
                    mr.operator_phone,
                    mr.ward_location,
                    mr.machinery_type,
                    mr.machinery_description,
                    mr.hourly_rate,
                    mr.availability_status,
                    COALESCE(AVG(r.rating), 0) as average_rating,
                    COUNT(r.id) as total_reviews
                FROM machinery_registry mr
                LEFT JOIN ratings r ON mr.operator_id = r.operator_id
                WHERE mr.ward_location = ? 
                  AND mr.machinery_type = ?
                  AND mr.is_active = 1
                  AND mr.availability_status = 'available'
                GROUP BY mr.operator_id
                ORDER BY average_rating DESC, mr.created_at ASC
                LIMIT 1
            ''', (ward_location.lower(), machinery_type.lower()))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.warning(f"No match found for {machinery_type} in {ward_location}")
                return None
            
            operator_data = dict(row)
            logger.info(f"Match found: {operator_data['operator_id']} with "
                       f"rating {operator_data['average_rating']}")
            
            return operator_data
        
        except Exception as e:
            logger.error(f"Error finding match: {str(e)}")
            return None
    
    def find_alternatives(self, machinery_type: str, ward_location: str, 
                         limit: int = 5) -> List[Dict]:
        """
        Find alternative operators if primary match not suitable.
        
        Args:
            machinery_type (str): Type of machinery requested
            ward_location (str): Ward location
            limit (int): Maximum number of alternatives
            
        Returns:
            list: List of alternative operators ranked by rating
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    mr.id,
                    mr.operator_id,
                    mr.operator_name,
                    mr.operator_phone,
                    mr.ward_location,
                    mr.machinery_type,
                    mr.machinery_description,
                    mr.hourly_rate,
                    mr.availability_status,
                    COALESCE(AVG(r.rating), 0) as average_rating,
                    COUNT(r.id) as total_reviews
                FROM machinery_registry mr
                LEFT JOIN ratings r ON mr.operator_id = r.operator_id
                WHERE mr.ward_location = ? 
                  AND mr.machinery_type = ?
                  AND mr.is_active = 1
                GROUP BY mr.operator_id
                ORDER BY average_rating DESC, mr.created_at ASC
                LIMIT ?
            ''', (ward_location.lower(), machinery_type.lower(), limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            alternatives = [dict(row) for row in rows]
            logger.info(f"Found {len(alternatives)} alternative operators")
            
            return alternatives
        
        except Exception as e:
            logger.error(f"Error finding alternatives: {str(e)}")
            return []
    
    def handle_rental_request(self, farmer_phone: str, machinery_type: str, 
                             ward_location: str) -> Optional[Dict]:
        """
        Handle a complete rental request.
        
        Creates a rental request record and matches it with the best operator.
        
        Args:
            farmer_phone (str): Farmer's phone number
            machinery_type (str): Type of machinery requested
            ward_location (str): Ward location
            
        Returns:
            dict: Matched operator data or None
        """
        try:
            # Find best match
            best_match = self.find_best_match(machinery_type, ward_location)
            
            if not best_match:
                logger.warning(f"No operator available for {machinery_type} in {ward_location}")
                # Record the request as unmatched
                self._record_rental_request(farmer_phone, machinery_type, 
                                           ward_location, None, 'no_match')
                return None
            
            # Record the rental request with matched operator
            self._record_rental_request(
                farmer_phone, 
                machinery_type, 
                ward_location,
                best_match['operator_id'],
                'matched'
            )
            
            return best_match
        
        except Exception as e:
            logger.error(f"Error handling rental request: {str(e)}")
            return None
    
    def _record_rental_request(self, farmer_phone: str, machinery_type: str,
                              ward_location: str, operator_id: Optional[str],
                              status: str) -> bool:
        """
        Record a rental request in the database.
        
        Args:
            farmer_phone (str): Farmer's phone
            machinery_type (str): Type of machinery
            ward_location (str): Ward location
            operator_id (str): Matched operator ID or None
            status (str): Request status (matched, no_match, pending)
            
        Returns:
            bool: Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO rental_requests 
                (farmer_phone, machinery_type, ward_location, matched_operator_id, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (farmer_phone, machinery_type.lower(), ward_location.lower(), 
                  operator_id, status))
            
            conn.commit()
            conn.close()
            
            return True
        
        except Exception as e:
            logger.error(f"Error recording rental request: {str(e)}")
            return False
    
    def add_rating(self, operator_id: str, farmer_phone: str, 
                  rating: float, review_text: str = None) -> bool:
        """
        Add a rating for an operator after rental completion.
        
        Args:
            operator_id (str): Operator ID
            farmer_phone (str): Farmer's phone number
            rating (float): Rating (1-5 stars)
            review_text (str): Optional review text
            
        Returns:
            bool: Success status
        """
        try:
            if not (1 <= rating <= 5):
                logger.error(f"Invalid rating: {rating}. Must be 1-5")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO ratings (operator_id, farmer_phone, rating, review_text)
                VALUES (?, ?, ?, ?)
            ''', (operator_id, farmer_phone, rating, review_text))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Rating {rating} added for operator {operator_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error adding rating: {str(e)}")
            return False
    
    def get_operator_stats(self, operator_id: str) -> Optional[Dict]:
        """
        Get statistics and ratings for an operator.
        
        Args:
            operator_id (str): Operator ID
            
        Returns:
            dict: Operator stats or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get operator info and ratings
            cursor.execute('''
                SELECT 
                    mr.operator_id,
                    mr.operator_name,
                    mr.operator_phone,
                    mr.ward_location,
                    mr.machinery_type,
                    mr.hourly_rate,
                    COALESCE(AVG(r.rating), 0) as average_rating,
                    COUNT(r.id) as total_reviews,
                    MIN(r.rating) as min_rating,
                    MAX(r.rating) as max_rating
                FROM machinery_registry mr
                LEFT JOIN ratings r ON mr.operator_id = r.operator_id
                WHERE mr.operator_id = ?
                GROUP BY mr.operator_id
            ''', (operator_id,))
            
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return None
            
            # Get recent reviews
            cursor.execute('''
                SELECT rating, review_text, created_at
                FROM ratings
                WHERE operator_id = ?
                ORDER BY created_at DESC
                LIMIT 10
            ''', (operator_id,))
            
            recent_reviews = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            stats = dict(row)
            stats['recent_reviews'] = recent_reviews
            
            return stats
        
        except Exception as e:
            logger.error(f"Error getting operator stats: {str(e)}")
            return None
    
    def update_operator_availability(self, operator_id: str, 
                                    availability_status: str) -> bool:
        """
        Update operator availability status.
        
        Args:
            operator_id (str): Operator ID
            availability_status (str): Status (available, busy, offline)
            
        Returns:
            bool: Success status
        """
        try:
            valid_statuses = ['available', 'busy', 'offline']
            
            if availability_status.lower() not in valid_statuses:
                logger.error(f"Invalid status: {availability_status}")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE machinery_registry 
                SET availability_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE operator_id = ?
            ''', (availability_status.lower(), operator_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Operator {operator_id} status updated to {availability_status}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating availability: {str(e)}")
            return False
    
    def deactivate_operator(self, operator_id: str) -> bool:
        """
        Deactivate an operator account.
        
        Args:
            operator_id (str): Operator ID
            
        Returns:
            bool: Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE machinery_registry 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE operator_id = ?
            ''', (operator_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Operator {operator_id} deactivated")
            return True
        
        except Exception as e:
            logger.error(f"Error deactivating operator: {str(e)}")
            return False
    
    def get_rental_request_history(self, farmer_phone: str, limit: int = 50) -> List[Dict]:
        """
        Get rental request history for a farmer.
        
        Args:
            farmer_phone (str): Farmer's phone number
            limit (int): Maximum number of records
            
        Returns:
            list: Rental request history
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    rr.id,
                    rr.farmer_phone,
                    rr.machinery_type,
                    rr.ward_location,
                    rr.matched_operator_id,
                    rr.status,
                    rr.created_at,
                    mr.operator_name,
                    COALESCE(AVG(r.rating), 0) as operator_rating
                FROM rental_requests rr
                LEFT JOIN machinery_registry mr ON rr.matched_operator_id = mr.operator_id
                LEFT JOIN ratings r ON mr.operator_id = r.operator_id
                WHERE rr.farmer_phone = ?
                GROUP BY rr.id
                ORDER BY rr.created_at DESC
                LIMIT ?
            ''', (farmer_phone, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Error retrieving rental history: {str(e)}")
            return []
    
    def get_matching_statistics(self, ward_location: str) -> Optional[Dict]:
        """
        Get matching statistics for a ward.
        
        Args:
            ward_location (str): Ward location
            
        Returns:
            dict: Statistics for the ward
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Operators in ward
            cursor.execute('''
                SELECT COUNT(*) as count FROM machinery_registry 
                WHERE ward_location = ? AND is_active = 1
            ''', (ward_location.lower(),))
            
            operator_count = cursor.fetchone()['count']
            
            # Machinery types available
            cursor.execute('''
                SELECT machinery_type, COUNT(*) as count
                FROM machinery_registry 
                WHERE ward_location = ? AND is_active = 1
                GROUP BY machinery_type
            ''', (ward_location.lower(),))
            
            machinery_types = {row['machinery_type']: row['count'] for row in cursor.fetchall()}
            
            # Recent requests
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM rental_requests
                WHERE ward_location = ?
                GROUP BY status
            ''', (ward_location.lower(),))
            
            requests = {row['status']: row['count'] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'ward': ward_location,
                'active_operators': operator_count,
                'machinery_types': machinery_types,
                'requests': requests
            }
        
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return None
