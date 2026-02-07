"""Web and digital footprint signal processors"""

from .app_store_ratings import AppStoreRatingsProcessor
from .google_trends import GoogleTrendsProcessor

__all__ = ["AppStoreRatingsProcessor", "GoogleTrendsProcessor"]
