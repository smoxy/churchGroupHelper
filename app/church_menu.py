"""
Church Menu Module

This module contains functions for managing church-related operations
in the bot, including settings management and address geocoding.
"""

import logging
from geopy.geocoders import Nominatim
from database import Database

# Enable logging
logConf = logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Nominatim geocoder
geolocator = Nominatim(user_agent="churchLocatorBot")


async def settings(update, context):
    """
    Display and manage settings for a group or church.
    
    If sent in a private chat, asks for a group to manage.
    If sent in a group, shows the settings of the group in private.
    """
    # TODO: Implement settings management
    pass


async def set_address(update, context, church_id: int, latitude: float, longitude: float):
    """
    Use reverse geocoding to update the address, city, and country of the church.
    
    Nominatim and GeoPy are used for geocoding.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        church_id: ID of the church to update
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    """
    db = Database.get_instance()
    
    # Get church language or default to 'en'
    lang = db.get_church_language(church_id) or 'en'
    
    try:
        # Get addresses from coordinates
        locations = geolocator.reverse(
            (latitude, longitude), 
            exactly_one=False, 
            timeout=5, 
            language=lang
        )
        
        if not locations:
            logger.warning(f"No addresses found for coordinates ({latitude}, {longitude})")
            return False
        
        addresses = [loc[0] for loc in locations]
        
        # Limit to 5 addresses
        if len(addresses) > 5:
            addresses = addresses[:5]
        
        # TODO: Send the addresses to the user to choose the correct one
        # TODO: Format as telegram inline keyboard buttons
        # await update.message.reply_text(
        #     "Select the correct address:",
        #     reply_markup=InlineKeyboardMarkup(buttons)
        # )
        
        return addresses
        
    except Exception as e:
        logger.error(f"Error in reverse geocoding: {e}", exc_info=True)
        return False