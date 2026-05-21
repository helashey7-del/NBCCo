"""
SMS-Triggered Machinery Rental Matching and Notification System
Automatically matches farmers with operators and sends 2-way SMS notifications
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Tuple
from db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class SMSMatcher:
    """Handles SMS-triggered machinery matching and notifications"""
    
    def __init__(self, db_path='crop_waste.db'):
        """
        Initialize SMS Matcher.
        
        Args:
            db_path (str): Path to SQLite database file
        """
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
    
    def initialize_sms_tables(self):
        """Create SMS tracking tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create SMS notification log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sms_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_request_id INTEGER NOT NULL,
                    recipient_type TEXT NOT NULL,
                    recipient_phone_hash TEXT NOT NULL,
                    message_body TEXT NOT NULL,
                    status TEXT DEFAULT 'Pending',
                    sent_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (rental_request_id) REFERENCES rental_requests(id)
                )
            ''')
            
            # Create index for SMS tracking
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sms_notifications_status 
                ON sms_notifications(status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sms_notifications_request 
                ON sms_notifications(rental_request_id)
            ''')
            
            # Create rental_requests table if it doesn't exist (from machinery_matching.py)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rental_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farmer_phone_hash TEXT NOT NULL,
                    machinery_type TEXT NOT NULL,
                    ward_location TEXT NOT NULL,
                    matched_operator_id INTEGER,
                    matched_operator_phone_hash TEXT,
                    status TEXT DEFAULT 'Pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    matched_at TIMESTAMP,
                    FOREIGN KEY(matched_operator_id) REFERENCES machinery_registry(id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_rental_requests_status 
                ON rental_requests(status)
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("SMS tables initialized successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing SMS tables: {str(e)}")
            return False
    
    def find_best_operator(self, machinery_type: str, ward_location: str) -> Optional[Dict]:
        """
        Query machinery_registry table to find the highest-rated active operator
        in the exact same ward location for the requested machinery type.
        
        Args:
            machinery_type (str): Type of machinery requested (e.g., 'tractor')
            ward_location (str): Ward location where the machinery is needed
            
        Returns:
            dict: Operator details with highest rating or None if no match found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query machinery_registry for active operators in same ward
            # Prioritize by highest star rating (average_rating or ratings column)
            cursor.execute('''
                SELECT 
                    id,
                    operator_id,
                    operator_phone_hash,
                    operator_name,
                    ward_location,
                    machinery_type,
                    hourly_rate,
                    COALESCE(average_rating, ratings, 0) as star_rating,
                    is_active
                FROM machinery_registry
                WHERE machinery_type = ?
                  AND ward_location = ?
                  AND is_active = 1
                ORDER BY COALESCE(average_rating, ratings, 0) DESC
                LIMIT 1
            ''', (machinery_type.lower(), ward_location.lower()))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.warning(
                    f"No active operators found for {machinery_type} in {ward_location}"
                )
                return None
            
            operator_data = dict(row)
            logger.info(
                f"Best operator match found: {operator_data['operator_name']} "
                f"(Rating: {operator_data['star_rating']}) in {ward_location}"
            )
            
            return operator_data
        
        except Exception as e:
            logger.error(f"Error finding best operator: {str(e)}")
            return None
    
    def create_rental_request(self, farmer_phone_hash: str, machinery_type: str,
                            ward_location: str) -> Optional[int]:
        """
        Create a rental request record in the database.
        
        Args:
            farmer_phone_hash (str): Hashed farmer phone number
            machinery_type (str): Type of machinery requested
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
            
            logger.info(f"Rental request {request_id} created for {machinery_type} in {ward_location}")
            return request_id
        
        except Exception as e:
            logger.error(f"Error creating rental request: {str(e)}")
            return None
    
    def update_rental_request_with_operator(self, request_id: int, operator_id: int,
                                           operator_phone_hash: str) -> bool:
        """
        Update rental request with matched operator details.
        
        Args:
            request_id (int): Rental request ID
            operator_id (int): Matched operator ID
            operator_phone_hash (str): Operator's hashed phone number
            
        Returns:
            bool: Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE rental_requests
                SET matched_operator_id = ?,
                    matched_operator_phone_hash = ?,
                    status = 'Matched',
                    matched_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (operator_id, operator_phone_hash, request_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Rental request {request_id} updated with operator {operator_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating rental request: {str(e)}")
            return False
    
    def generate_farmer_sms(self, farmer_phone_hash: str, operator_name: str,
                           operator_phone_hash: str, machinery_type: str,
                           hourly_rate: float) -> str:
        """
        Generate SMS message to farmer with operator contact details.
        
        Args:
            farmer_phone_hash (str): Farmer's hashed phone number
            operator_name (str): Operator's name
            operator_phone_hash (str): Operator's hashed phone number
            machinery_type (str): Type of machinery
            hourly_rate (float): Hourly rental rate
            
        Returns:
            str: SMS message body
        """
        # Decode phone hashes to display to farmer
        try:
            operator_phone = DatabaseManager.unhash_phone_number(operator_phone_hash)
        except:
            operator_phone = "Available on request"
        
        message = (
            f"Hello! We found a {machinery_type} operator for you. "
            f"Contact: {operator_name} ({operator_phone}). "
            f"Rate: {hourly_rate}/hour. "
            f"Reply CONFIRM to proceed or CANCEL to reject."
        )
        
        return message
    
    def generate_operator_sms(self, farmer_phone_hash: str, machinery_type: str,
                            ward_location: str, operator_name: str) -> str:
        """
        Generate SMS message to operator with job location and farmer details.
        
        Args:
            farmer_phone_hash (str): Farmer's hashed phone number
            machinery_type (str): Type of machinery needed
            ward_location (str): Ward location of the job
            operator_name (str): Operator's name
            
        Returns:
            str: SMS message body
        """
        message = (
            f"Hi {operator_name}! A farmer in {ward_location} is requesting a {machinery_type}. "
            f"Contact farmer to arrange details. Job ID: {farmer_phone_hash[:8]}... "
            f"Reply ACCEPT to confirm availability."
        )
        
        return message
    
    def log_sms_notification(self, request_id: int, recipient_type: str,
                           recipient_phone_hash: str, message_body: str) -> Optional[int]:
        """
        Log SMS notification for tracking and resend capability.
        
        Args:
            request_id (int): Rental request ID
            recipient_type (str): 'farmer' or 'operator'
            recipient_phone_hash (str): Recipient's hashed phone number
            message_body (str): SMS message content
            
        Returns:
            int: SMS notification ID or None if failed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sms_notifications 
                (rental_request_id, recipient_type, recipient_phone_hash, message_body, status)
                VALUES (?, ?, ?, ?, 'Pending')
            ''', (request_id, recipient_type.lower(), recipient_phone_hash, message_body))
            
            conn.commit()
            sms_id = cursor.lastrowid
            conn.close()
            
            logger.info(f"SMS notification {sms_id} logged for {recipient_type}")
            return sms_id
        
        except Exception as e:
            logger.error(f"Error logging SMS notification: {str(e)}")
            return None
    
    def mark_sms_sent(self, sms_id: int) -> bool:
        """
        Mark SMS notification as sent.
        
        Args:
            sms_id (int): SMS notification ID
            
        Returns:
            bool: Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE sms_notifications
                SET status = 'Sent', sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (sms_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"SMS notification {sms_id} marked as sent")
            return True
        
        except Exception as e:
            logger.error(f"Error marking SMS sent: {str(e)}")
            return False
    
    def process_machinery_request(self, farmer_phone_hash: str, machinery_type: str,
                                ward_location: str) -> Optional[Dict]:
        """
        Main function: Process machinery rental request with 2-way SMS trigger.
        
        Flow:
        1. Create rental request record
        2. Find best operator (highest rating) in same ward
        3. If match found:
           - Update rental request with operator details
           - Generate and log SMS to farmer (with operator contact)
           - Generate and log SMS to operator (with job location)
           - Send both SMS messages
        4. Return match details or None if no match
        
        Args:
            farmer_phone_hash (str): Hashed farmer phone number
            machinery_type (str): Type of machinery requested
            ward_location (str): Ward location
            
        Returns:
            dict: Match details with SMS status or None if no match found
        """
        try:
            # Step 1: Create rental request
            logger.info(
                f"Processing machinery request: {machinery_type} in {ward_location} "
                f"by farmer {farmer_phone_hash[:8]}..."
            )
            
            request_id = self.create_rental_request(farmer_phone_hash, machinery_type, ward_location)
            
            if not request_id:
                logger.error("Failed to create rental request")
                return None
            
            # Step 2: Find best operator in same ward
            operator = self.find_best_operator(machinery_type, ward_location)
            
            if not operator:
                logger.warning(
                    f"No matching operators found for {machinery_type} in {ward_location}"
                )
                return {
                    'request_id': request_id,
                    'status': 'No_Match',
                    'message': f'No {machinery_type} operators available in {ward_location}'
                }
            
            # Step 3: Update rental request with operator
            self.update_rental_request_with_operator(
                request_id,
                operator['id'],
                operator['operator_phone_hash']
            )
            
            # Step 4: Generate SMS messages
            farmer_sms = self.generate_farmer_sms(
                farmer_phone_hash,
                operator['operator_name'],
                operator['operator_phone_hash'],
                machinery_type,
                operator['hourly_rate']
            )
            
            operator_sms = self.generate_operator_sms(
                farmer_phone_hash,
                machinery_type,
                ward_location,
                operator['operator_name']
            )
            
            # Step 5: Log SMS notifications
            farmer_sms_id = self.log_sms_notification(
                request_id,
                'farmer',
                farmer_phone_hash,
                farmer_sms
            )
            
            operator_sms_id = self.log_sms_notification(
                request_id,
                'operator',
                operator['operator_phone_hash'],
                operator_sms
            )
            
            # Step 6: Send SMS messages (in production, integrate with SMS gateway)
            farmer_sent = self.send_sms(farmer_phone_hash, farmer_sms, farmer_sms_id)
            operator_sent = self.send_sms(operator['operator_phone_hash'], operator_sms, operator_sms_id)
            
            logger.info(
                f"Match successful! Request {request_id} matched with operator {operator['operator_id']} "
                f"(Rating: {operator['star_rating']})"
            )
            
            # Return comprehensive match details
            return {
                'request_id': request_id,
                'status': 'Matched',
                'operator_id': operator['id'],
                'operator_name': operator['operator_name'],
                'operator_phone_hash': operator['operator_phone_hash'],
                'star_rating': operator['star_rating'],
                'machinery_type': machinery_type,
                'hourly_rate': operator['hourly_rate'],
                'ward_location': ward_location,
                'farmer_sms': {
                    'id': farmer_sms_id,
                    'body': farmer_sms,
                    'status': 'Sent' if farmer_sent else 'Failed'
                },
                'operator_sms': {
                    'id': operator_sms_id,
                    'body': operator_sms,
                    'status': 'Sent' if operator_sent else 'Failed'
                },
                'matched_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error processing machinery request: {str(e)}")
            return None
    
    def send_sms(self, recipient_phone_hash: str, message_body: str,
                sms_id: Optional[int] = None) -> bool:
        """
        Send SMS message via gateway (placeholder for integration).
        
        Args:
            recipient_phone_hash (str): Recipient's hashed phone number
            message_body (str): SMS message content
            sms_id (int): SMS notification ID (for logging)
            
        Returns:
            bool: Success status
        """
        try:
            # TODO: Integrate with actual SMS gateway (Twilio, AWS SNS, local provider, etc.)
            # For now, this is a placeholder that logs the intent
            
            logger.info(
                f"SMS sent to {recipient_phone_hash[:8]}...: {message_body[:50]}..."
            )
            
            # Mark as sent in database
            if sms_id:
                self.mark_sms_sent(sms_id)
            
            return True
        
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return False
    
    def get_pending_sms_notifications(self, limit: int = 50) -> list:
        """
        Retrieve pending SMS notifications for retry/resend capability.
        
        Args:
            limit (int): Maximum number of records
            
        Returns:
            list: List of pending SMS notifications
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT *
                FROM sms_notifications
                WHERE status = 'Pending'
                ORDER BY created_at ASC
                LIMIT ?
            ''', (limit,))
            
            notifications = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return notifications
        
        except Exception as e:
            logger.error(f"Error retrieving pending SMS notifications: {str(e)}")
            return []
    
    def get_request_details(self, request_id: int) -> Optional[Dict]:
        """
        Get complete rental request details with operator and SMS info.
        
        Args:
            request_id (int): Rental request ID
            
        Returns:
            dict: Request details or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get rental request details
            cursor.execute('''
                SELECT *
                FROM rental_requests
                WHERE id = ?
            ''', (request_id,))
            
            request_row = cursor.fetchone()
            
            if not request_row:
                conn.close()
                return None
            
            request_data = dict(request_row)
            
            # Get associated SMS notifications
            cursor.execute('''
                SELECT *
                FROM sms_notifications
                WHERE rental_request_id = ?
                ORDER BY created_at DESC
            ''', (request_id,))
            
            sms_records = [dict(row) for row in cursor.fetchall()]
            request_data['sms_notifications'] = sms_records
            
            conn.close()
            
            return request_data
        
        except Exception as e:
            logger.error(f"Error retrieving request details: {str(e)}")
            return None
    
    def get_matching_statistics(self, ward_location: Optional[str] = None) -> Dict:
        """
        Get SMS matching statistics for reporting.
        
        Args:
            ward_location (str): Optional ward to filter by
            
        Returns:
            dict: Matching statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build query based on ward filter
            ward_clause = "WHERE ward_location = ?" if ward_location else ""
            ward_params = (ward_location.lower(),) if ward_location else ()
            
            # Total requests
            cursor.execute(
                f'SELECT COUNT(*) as count FROM rental_requests {ward_clause}',
                ward_params
            )
            total_requests = cursor.fetchone()['count']
            
            # Matched requests
            cursor.execute(
                f'SELECT COUNT(*) as count FROM rental_requests WHERE status = "Matched" {ward_clause}',
                ward_params
            )
            matched_requests = cursor.fetchone()['count']
            
            # SMS notifications sent
            cursor.execute(
                f'SELECT COUNT(*) as count FROM sms_notifications WHERE status = "Sent" {ward_clause}',
                ward_params
            )
            sms_sent = cursor.fetchone()['count']
            
            # SMS notifications pending
            cursor.execute(
                f'SELECT COUNT(*) as count FROM sms_notifications WHERE status = "Pending" {ward_clause}',
                ward_params
            )
            sms_pending = cursor.fetchone()['count']
            
            conn.close()
            
            match_rate = (matched_requests / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'ward_location': ward_location or 'All',
                'total_requests': total_requests,
                'matched_requests': matched_requests,
                'unmatched_requests': total_requests - matched_requests,
                'match_success_rate': round(match_rate, 2),
                'sms_sent': sms_sent,
                'sms_pending': sms_pending,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error retrieving matching statistics: {str(e)}")
            return {}
