import csv
import re
import time
from math import ceil
from pathlib import Path

from bs4 import BeautifulSoup
from httpx import Client

# Populate this with your email address.
FROM_EMAIL = None


class BPLEventScraper:
    """
    Class to scrape BPL events. Caches downloads.
    """
    BPL_URL = 'https://bpl.bibliocommons.com/v2/events'
    DELAY = 5

    def __init__(self, locations, num_pages, pages_dir, events_dir):
        self.locations = locations
        self.num_pages = num_pages
        self.pages_dir = pages_dir
        self.events_dir = events_dir
        pages_dir.mkdir(parents=True, exist_ok=True)
        events_dir.mkdir(parents=True, exist_ok=True)

        self.client = Client(headers={'user-agent': 'BPL_events/0.0.1', 'from': FROM_EMAIL})

    def get_page(self, page_num):
        params = {'locations': self.locations, 'page': page_num}
        return self.client.get(self.BPL_URL, params=params).raise_for_status().text

    @staticmethod
    def get_events(page):
        soup = BeautifulSoup(page, features='html.parser')
        return soup.find_all('div', class_="cp-events-search-item")

    def get_event_info(self, event):
        def get_tag(class_):
            return event.find_all(class_=class_)[0]
        def get_string(class_):
            return get_tag(class_).string.strip()
        def clean(string):
            return re.sub(r'\s+', ' ', string.strip())
        
        try:
            badge = get_string('cp-badge')
        except Exception:
            badge = ''
        link = get_tag('cp-link')['href']
        # date_time = ', '.join(
        #     tag.string.strip()
        #     for tag in get_tag('cp-event-date-time').find_all(class_='cp-screen-reader-message')
        # )

        event_path = self.events_dir / Path(link).name
        if not event_path.exists():
            print(f'Downloading event from {link}.')
            event_path.write_text(self.client.get(link).raise_for_status().text)
            time.sleep(self.DELAY)
        event = BeautifulSoup(event_path.read_text(), features='html.parser')

        name = get_string('visible-print')
        start_date = event.find_all(itemprop='startDate')[0]['datetime']
        end_date = event.find_all(itemprop='endDate')[0]['datetime']
        # time = clean(get_tag('event-time').contents[1].string)
        description = clean(''.join(get_tag('event-description-content').strings))
        facets = get_tag('event-facets-list')
        audience = [
            tag.string.strip()
            for tag in facets.find_all(itemprop='audience')[0].find_all(itemprop='name')
        ]
        types = [
            tag.string.strip()
            for tag in facets.find_all(class_='btn-link primary-link clear-padding clear-border text-left')
        ]
        languages = facets.find_all(itemprop='inLanguage')[0].string.strip()

        return name, start_date, end_date, description, audience, types, languages, badge

    def download_pages(self):
        for page_num in range(1, self.num_pages + 1):
            page_path = self.pages_dir / f'{page_num}.html'
            if not page_path.exists():
                print(f'Downloading page {page_num}')
                page_path.write_text(self.get_page(page_num))
                time.sleep(self.DELAY)

    def scrape_events(self):
        self.download_pages()
        rows = [
            self.get_event_info(event)
            for page_path in sorted(self.pages_dir.iterdir(), key=lambda p: int(p.stem))
            for event in self.get_events(page_path.read_text())
        ]
        with open('events.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Start Date', 'End Date', 'Description', 'Audience', 'Types', 'Languages', 'Badge'])
            writer.writerows(rows)
            

if __name__ == '__main__':
    scraper = BPLEventScraper(30, 5, Path('pages'), Path('events'))
    scraper.scrape_events()
