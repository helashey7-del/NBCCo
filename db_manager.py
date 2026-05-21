"""
Database Manager for Crop Waste Listings
Handles SQLite operations with Base64 phone number hashing
"""

import sqlite3
import base64
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for crop waste listings"""
    
    def __init__(self, db_path='crop_waste.db'):
        """
        Initialize database manager.
        
        Args:
            db_path (str): Path to SQLite database file
        """
        self.db_path = db_path
        self.connection = None
    
    def initialize_database(self):
        """Create database and tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create crop_waste_listings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crop_waste_listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number_hash TEXT NOT NULL,
                    crop_type TEXT NOT NULL,
                    quantity_bags INTEGER NOT NULL,
                    ward_location TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Available',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(phone_number_hash, crop_type, ward_location, created_at)
                )
            ''')
            
            # Create indexes for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_crop_type 
                ON crop_waste_listings(crop_type)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ward_location 
                ON crop_waste_listings(ward_location)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status 
                ON crop_waste_listings(status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_phone_hash 
                ON crop_waste_listings(phone_number_hash)
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database initialized at {self.db_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            return False
    
    def get_connection(self):
        """Get database connection"""
        if not self.connection:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
        return self.connection
    
    def close_connection(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    @staticmethod
    def hash_phone_number(phone_number):
        """
        Hash phone number using Base64 encoding.
        
        Args:
            phone_number (str): Raw phone number
            
        Returns:
            str: Base64 encoded phone number hash
        """
        try:
            phone_bytes = phone_number.encode('utf-8')
            hash_bytes = base64.b64encode(phone_bytes)
            return hash_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Error hashing phone number: {str(e)}")
            return None
    
    @staticmethod
    def unhash_phone_number(phone_hash):
        """
        Decode Base64 phone number hash back to original.
        
        Args:
            phone_hash (str): Base64 encoded phone number
            
        Returns:
            str: Decoded phone number
        """
        try:
            hash_bytes = phone_hash.encode('utf-8')
            phone_bytes = base64.b64decode(hash_bytes)
            return phone_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Error unhashing phone number: {str(e)}")
            return None
    
    def insert_listing(self, phone_number, crop_type, quantity_bags, ward_location):
        """
        Insert a new crop waste listing.
        
        Args:
            phone_number (str): Farmer's phone number
            crop_type (str): Type of crop
            quantity_bags (int): Number of bags
            ward_location (str): Ward location
            
        Returns:
            int: Listing ID or None if failed
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Hash the phone number for storage
            phone_hash = self.hash_phone_number(phone_number)
            
            if not phone_hash:
                return None
            
            cursor.execute('''
                INSERT INTO crop_waste_listings 
                (phone_number_hash, crop_type, quantity_bags, ward_location, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (phone_hash, crop_type.lower(), quantity_bags, 
                  ward_location.lower(), 'Available'))
            
            conn.commit()
            
            listing_id = cursor.lastrowid
            logger.info(f"Inserted listing ID: {listing_id}")
            
            return listing_id
        
        except sqlite3.IntegrityError as e:
            logger.warning(f"Duplicate listing detected: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error inserting listing: {str(e)}")
            return None
    
    def get_listing_by_id(self, listing_id):
        """
        Retrieve listing by ID.
        
        Args:
            listing_id (int): Listing ID
            
        Returns:
            dict: Listing data or None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM crop_waste_listings WHERE id = ?
            ''', (listing_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return dict(row)
        
        except Exception as e:
            logger.error(f"Error retrieving listing: {str(e)}")
            return None
    
    def get_listings(self, crop_type=None, ward_location=None, 
                    status='Available', limit=50):
        """
        Retrieve listings with optional filters.
        
        Args:
            crop_type (str): Filter by crop type
            ward_location (str): Filter by ward
            status (str): Filter by status (default: Available)
            limit (int): Maximum number of results
            
        Returns:
            list: List of listings
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = 'SELECT * FROM crop_waste_listings WHERE 1=1'
            params = []
            
            if status:
                query += ' AND status = ?'
                params.append(status)
            
            if crop_type:
                query += ' AND crop_type LIKE ?'
                params.append(f'%{crop_type.lower()}%')
            
            if ward_location:
                query += ' AND ward_location LIKE ?'
                params.append(f'%{ward_location.lower()}%')
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Error retrieving listings: {str(e)}")
            return []
    
    def update_listing_status(self, listing_id, new_status):
        """
        Update listing status.
        
        Args:
            listing_id (int): Listing ID
            new_status (str): New status (Available, Sold, Removed)
            
        Returns:
            bool: Success status
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            valid_statuses = ['Available', 'Sold', 'Removed', 'Pending']
            
            if new_status not in valid_statuses:
                logger.error(f"Invalid status: {new_status}")
                return False
            
            cursor.execute('''
                UPDATE crop_waste_listings 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_status, listing_id))
            
            conn.commit()
            
            logger.info(f"Updated listing {listing_id} status to {new_status}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating listing status: {str(e)}")
            return False
    
    def delete_listing(self, listing_id):
        """
        Delete a listing (soft delete via status).
        
        Args:
            listing_id (int): Listing ID
            
        Returns:
            bool: Success status
        """
        return self.update_listing_status(listing_id, 'Removed')
    
    def get_listings_by_phone_hash(self, phone_hash, status='Available'):
        """
        Retrieve all listings for a specific phone number hash.
        
        Args:
            phone_hash (str): Phone number hash
            status (str): Filter by status
            
        Returns:
            list: List of listings
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM crop_waste_listings 
                WHERE phone_number_hash = ? AND status = ?
                ORDER BY created_at DESC
            ''', (phone_hash, status))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Error retrieving listings by phone: {str(e)}")
            return []
    
    def get_statistics(self):
        """
        Get database statistics.
        
        Returns:
            dict: Statistics
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Total listings
            cursor.execute('SELECT COUNT(*) as total FROM crop_waste_listings')
            total = cursor.fetchone()['total']
            
            # Available listings
            cursor.execute('SELECT COUNT(*) as count FROM crop_waste_listings WHERE status = ?', ('Available',))
            available = cursor.fetchone()['count']
            
            # Sold listings
            cursor.execute('SELECT COUNT(*) as count FROM crop_waste_listings WHERE status = ?', ('Sold',))
            sold = cursor.fetchone()['count']
            
            # Crop type breakdown
            cursor.execute('''
                SELECT crop_type, COUNT(*) as count 
                FROM crop_waste_listings 
                WHERE status = 'Available'
                GROUP BY crop_type 
                ORDER BY count DESC
            ''')
            crops = {row['crop_type']: row['count'] for row in cursor.fetchall()}
            
            # Ward breakdown
            cursor.execute('''
                SELECT ward_location, COUNT(*) as count 
                FROM crop_waste_listings 
                WHERE status = 'Available'
                GROUP BY ward_location 
                ORDER BY count DESC
            ''')
            wards = {row['ward_location']: row['count'] for row in cursor.fetchall()}
            
            # Total quantity
            cursor.execute('SELECT SUM(quantity_bags) as total FROM crop_waste_listings WHERE status = ?', ('Available',))
            total_quantity = cursor.fetchone()['total'] or 0
            
            return {
                'total_listings': total,
                'available': available,
                'sold': sold,
                'removed': total - available - sold,
                'total_bags_available': total_quantity,
                'crops': crops,
                'wards': wards
            }
        
        except Exception as e:
            logger.error(f"Error retrieving statistics: {str(e)}")
            return {}
    
    def search_listings(self, query, limit=50):
        """
        Search listings by keyword across crop type and ward.
        
        Args:
            query (str): Search query
            limit (int): Maximum results
            
        Returns:
            list: Matching listings
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_pattern = f'%{query.lower()}%'
            
            cursor.execute('''
                SELECT * FROM crop_waste_listings 
                WHERE status = 'Available' 
                AND (crop_type LIKE ? OR ward_location LIKE ?)
                ORDER BY created_at DESC
                LIMIT ?
            ''', (query_pattern, query_pattern, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Error searching listings: {str(e)}")
            return []
    
    def cleanup_old_listings(self, days=90):
        """
        Remove old 'Removed' listings to keep database lean.
        
        Args:
            days (int): Days to keep
            
        Returns:
            int: Number of listings deleted
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM crop_waste_listings 
                WHERE status = 'Removed' 
                AND created_at < datetime('now', '-' || ? || ' days')
            ''', (days,))
            
            conn.commit()
            
            deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} old listings")
            
            return deleted
        
        except Exception as e:
            logger.error(f"Error cleaning up listings: {str(e)}")
            return 0
