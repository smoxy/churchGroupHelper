import logging
from database import Database

# Enable logging
logConf = logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

### Set di funzioni per eseguire operazioni di backend sui gruppi e sugli utenti ###

"""


"""

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    

async def set_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Use reverse geocoding to update the address, the city and the country of the church.
    Or, if
    Nominatim and GeoPy are used for this scope.
    """
    lang = if get_church_language(church_id) else 'en'
    locations = geolocator.reverse((latitude, longitude), exactly_one=False, timeout=5, language=lang)
    addresses = [loc[0] for loc in locations]
    if len(addresses) == 0:
        return False
    elif len(addresses) > 5:
        addresses = addresses[:5]
    
    # Send the addresses to the user in order to choose the correct one
    # format telegram_buttons