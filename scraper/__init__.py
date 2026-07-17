"""Scraper package for lead discovery."""

from .models import LeadItem
from .runner import scrape_url

__all__ = ["LeadItem", "scrape_url"]
