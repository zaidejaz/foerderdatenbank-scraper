import asyncio
import datetime
import json
import logging
import argparse
from urllib.parse import urljoin, quote_plus

import time
import schedule
import os
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup
from pyppeteer import launch
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import mysql.connector

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(filename='scraper.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add console handler to see logs in real-time
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Get database credentials
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

# URL-encode the password
encoded_password = quote_plus(DB_PASSWORD)

# Construct the database URL
DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{encoded_password}@{DB_HOST}/{DB_NAME}"

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class FundingProgram(Base):
    __tablename__ = 'funding_programs'

    id = Column(Integer, primary_key=True)
    program_url = Column(String(255), unique=True)
    program_name = Column(LONGTEXT)
    is_scraped = Column(Boolean, default=False)
    details = relationship("ProgramDetails", back_populates="program", uselist=False, cascade="all, delete-orphan")

class ProgramDetails(Base):
    __tablename__ = 'program_details'

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey('funding_programs.id'))
    program = relationship("FundingProgram", back_populates="details")
    funding_type = Column(Text)
    support_area = Column(Text)
    funding_area = Column(Text)
    eligible = Column(Text)
    funding_provider = Column(LONGTEXT)
    provider_name = Column(Text)
    provider_address = Column(Text)
    provider_phone = Column(Text)
    provider_fax = Column(Text)
    provider_email = Column(Text)
    provider_website = Column(Text)
    further_links = Column(JSON)
    short_summary = Column(LONGTEXT)
    additional_information = Column(LONGTEXT)
    legal_basis = Column(LONGTEXT)

Base.metadata.create_all(engine)

BASE_URL = "https://www.foerderdatenbank.de"
START_URL = f"{BASE_URL}/SiteGlobals/FDB/Forms/Suche/Foederprogrammsuche_Formular.html?submit=Suchen&filterCategories=FundingProgram&sortOrder=dateOfIssue_dt+asc"

async def get_browser():
    return await launch(headless=True)

def get_soup(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.info(f"Successfully fetched URL: {url}")
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None

async def get_soup_with_js(page, url):
    await page.goto(url, waitUntil='networkidle0')
    content = await page.content()
    return BeautifulSoup(content, 'html.parser')

def extract_program_links(soup):
    programs = []
    cards = soup.find_all('div', class_='card--fundingprogram')
    for card in cards:
        link = card.find('a', class_='')
        if link:
            program_url = urljoin(BASE_URL, link.get('href', ''))
            program_name = link.find('span', class_='link--label')
            program_name = program_name.text.strip() if program_name else ''
            if program_url and program_name:
                programs.append((program_url, program_name))
    logger.info(f"Extracted {len(programs)} program links from the page")
    return programs

def get_next_page_url(soup):
    pagination = soup.find('div', class_='pagination')
    if pagination:
        next_button = pagination.find('a', class_='forward button')
        if next_button and 'href' in next_button.attrs:
            next_url = urljoin(BASE_URL, next_button['href'])
            logger.info(f"Found next page URL: {next_url}")
            return next_url
    logger.info("No next page found")
    return None

def safe_extract(element, selector, attribute=None):
    try:
        found = element.select_one(selector)
        if found:
            if attribute:
                return found.get(attribute, '').strip()
            else:
                return found.text.strip()
    except Exception as e:
        logger.error(f"Error extracting {selector}: {e}")
    return ''

def extract_contact_info(contact_data):
    contact_info = {
        'provider_name': '',
        'provider_address': '',
        'provider_phone': '',
        'provider_fax': '',
        'provider_email': '',
        'provider_website': ''
    }

    contact_info['provider_name'] = safe_extract(contact_data, "p.card--title")
    contact_info['provider_address'] = safe_extract(contact_data, "div.address")

    phone = safe_extract(contact_data, "p.tel")
    contact_info['provider_phone'] = phone.split(':')[1].strip() if ':' in phone else phone

    fax = safe_extract(contact_data, "p.fax")
    contact_info['provider_fax'] = fax.split(':')[1].strip() if ':' in fax else fax

    contact_info['provider_email'] = safe_extract(contact_data, "p.email a", "href").replace('mailto:', '')
    contact_info['provider_website'] = safe_extract(contact_data, "p.website a", "href")

    return contact_info

def extract_links(element):
    links = []
    for a in element.find_all('a', href=True):
        links.append(a['href'])
    return links

def extract_program_details(soup):
    details = {}

    # Extract program name
    details['program_name'] = safe_extract(soup, 'h1.title')

    # Extract other details
    dl = soup.find('dl', class_='grid-modul--two-elements document-info-fundingprogram')
    if dl:
        dt_elements = dl.find_all('dt')
        dd_elements = dl.find_all('dd')
        for dt, dd in zip(dt_elements, dd_elements):
            key = dt.text.strip().lower().replace(' ', '_').replace(':', '')
            if key == 'weiterführende_links':
                details[key] = extract_links(dd)
            elif key == 'ansprechpunkt':
                contact_info = extract_contact_info(dd)
                details.update(contact_info)
            else:
                details[key] = dd.text.strip()

    # Extract HTML content for tabbed articles
    for tab_id in ['tab1', 'tab2', 'tab3']:
        article = soup.find('article', id=tab_id)
        if article:
            key = tab_id.replace('tab', '').replace('1', 'short_summary').replace('2', 'additional_information').replace('3', 'legal_basis')
            details[f"{key}"] = article.get_text(separator="\n", strip=True)

    return details

async def scrape_program_details(session, program, page):
    try:
        if program.is_scraped:
            logger.info(f"Program already scraped: {program.program_name}")
            return

        soup = await get_soup_with_js(page, program.program_url)
        if not soup:
            return

        details = extract_program_details(soup)

        # Check if program details already exist
        if program.details:
            logger.info(f"Updating existing details for program: {program.program_name}")
            program_details = program.details
        else:
            logger.info(f"Creating new details for program: {program.program_name}")
            program_details = ProgramDetails(program=program)

        # Update program details
        program_details.funding_type = details.get('förderart', '')
        program_details.support_area = details.get('förderbereich', '')
        program_details.funding_area = details.get('fördergebiet', '')
        program_details.eligible = details.get('förderberechtigte', '')
        program_details.funding_provider = details.get('fördergeber', '')
        program_details.provider_name = details.get('provider_name', '')
        program_details.provider_address = details.get('provider_address', '')
        program_details.provider_phone = details.get('provider_phone', '')
        program_details.provider_fax = details.get('provider_fax', '')
        program_details.provider_email = details.get('provider_email', '')
        program_details.provider_website = details.get('provider_website', '')
        program_details.further_links = json.dumps(details.get('weiterführende_links', []))
        program_details.short_summary = details.get('short_summary', '')
        program_details.additional_information = details.get('additional_information', '')
        program_details.legal_basis = details.get('legal_basis', '')

        session.add(program_details)
        program.is_scraped = True
        session.commit()
        logger.info(f"Successfully scraped and saved details for program: {program.program_name}")
    except Exception as e:
        logger.error(f"Error scraping program details: {e}")
async def scrape_funding_programs():
    browser = await get_browser()
    page = await browser.newPage()
    session = Session()

    try:
        current_url = START_URL
        while current_url:
            logger.info(f"Scraping page: {current_url}")
            soup = get_soup(current_url)  # Use requests for the main page
            if not soup:
                break

            programs = extract_program_links(soup)
            for program_url, program_name in programs:
                program = session.query(FundingProgram).filter_by(program_url=program_url).first()
                if not program:
                    program = FundingProgram(program_url=program_url, program_name=program_name)
                    session.add(program)
                    session.commit()
                    logger.info(f"Added new program: {program_name}")

                try:
                    await scrape_program_details(session, program, page)
                except Exception as e:
                    logger.error(f"Error scraping program {program_name}: {e}")
                    session.rollback()

            current_url = get_next_page_url(soup)
            await asyncio.sleep(1)  # Be polite to the server

    finally:
        session.close()
        await browser.close()
        logger.info("Finished scraping all funding programs")

def reset_database():
    session = Session()
    try:
        # Delete all records from program_details table
        session.query(ProgramDetails).delete()
        session.query(FundingProgram).delete()
        logger.info("Deleted all records from database.")

        session.commit()
        logger.info("Database reset completed successfully")
    except Exception as e:
        session.rollback()
        logger.error(f"Error resetting database: {e}")
    finally:
        session.close()

def verify_database():
    session = Session()
    try:
        programs = session.query(FundingProgram).all()
        logger.info(f"Total programs in database: {len(programs)}")

        programs_with_details = session.query(FundingProgram).filter(FundingProgram.details != None).count()
        logger.info(f"Programs with details: {programs_with_details}")

        sample_program = session.query(FundingProgram).filter(FundingProgram.details != None).first()
        if sample_program:
            logger.info(f"Sample program: {sample_program.program_name}")
            logger.info(f"Sample details:")
            logger.info(f"  Funding Type: {sample_program.details.funding_type}")
            logger.info(f"  Support Area: {sample_program.details.support_area}")
            logger.info(f"  Funding Area: {sample_program.details.funding_area}")
            logger.info(f"  Eligible: {sample_program.details.eligible}")
            logger.info(f"  Provider Name: {sample_program.details.provider_name}")
            logger.info(f"  Provider Website: {sample_program.details.provider_website}")
            logger.info(f"  Short Summary: {sample_program.details.short_summary[:100]}...")
    finally:
        session.close()

def run_scraper():
    asyncio.get_event_loop().run_until_complete(scrape_funding_programs())

def schedule_scraper():
    # Run the scraper immediately
    logger.info("Running scraper immediately...")
    run_scraper()

    # Get the current time
    now = datetime.datetime.now()

    # Schedule the next run for the same time next week
    next_run = now + datetime.timedelta(days=7)
    next_run_time = next_run.strftime("%H:%M")

    schedule.every().monday.at(next_run_time).do(run_scraper)

    logger.info(f"Scraper scheduled to run every Monday at {next_run_time}. Press Ctrl+C to exit.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Funding Program Scraper")
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    parser.add_argument("--verify", action="store_true", help="Verify database contents")
    parser.add_argument("--schedule", action="store_true", help="Run the scraper on a weekly schedule")
    args = parser.parse_args()

    if args.reset:
        reset_database()
    elif args.verify:
        verify_database()
    elif args.schedule:
        schedule_scraper()
    else:
        run_scraper()
