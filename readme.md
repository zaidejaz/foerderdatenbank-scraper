# Funding Program Scraper

This project is a web scraper designed to extract funding program information from the German Funding Database (https://www.foerderdatenbank.de). It uses Python 3.10.2 and Poetry for dependency management.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Database](#database)
6. [Scheduling](#scheduling)
7. [Logging](#logging)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.10.2
- Poetry
- MySQL database

## Installation


1. Install Poetry if you haven't already:
   ```
   pip install poetry
   ```

2. Set up the project using Poetry:
   ```
   poetry install
   ```

   This will create a virtual environment with Python 3.10.2 and install all required dependencies.

## Configuration

1. Create a `.env` file in the project root directory with the following content:
   ```
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_HOST=your_database_host
   DB_NAME=your_database_name
   ```

   Replace the placeholders with your actual MySQL database credentials.

2. Ensure you have the necessary permissions to create tables in the specified database.

## Usage

Activate the Poetry environment:
```
poetry shell
```

The scraper supports several command-line arguments:

- To run the scraper once:
  ```
  python scraper.py
  ```

- To reset the database (clear all data and reset flags):
  ```
  python scraper.py --reset
  ```

- To verify the database contents:
  ```
  python scraper.py --verify
  ```

- To run the scraper on a weekly schedule:
  ```
  python scraper.py --schedule
  ```

## Database

The scraper uses two main tables:

1. `funding_programs`: Stores basic information about each funding program.
2. `program_details`: Stores detailed information about each program.

The database schema is automatically created when you run the scraper for the first time.

## Scheduling

The scraper can be scheduled to run automatically every Monday at 01:00 AM. Use the `--schedule` flag to start the scheduler.

## Logging

The scraper logs its activities to both a file (`scraper.log`) and the console. Check these logs for detailed information about the scraping process and any errors that occur.

## Troubleshooting

1. If you encounter database connection issues, double-check your `.env` file and ensure your MySQL server is running.

2. If the scraper fails to extract information from certain pages, it might be due to changes in the website's structure. Check the logs for specific errors and update the scraping logic if necessary.

3. If you're experiencing issues with Pyppeteer (the library used for JavaScript rendering), ensure you have the latest version and that your system meets its requirements.

4. For any other issues, check the `scraper.log` file for detailed error messages.

## Notes

- This scraper is designed to be polite to the server by introducing delays between requests. Please use it responsibly.
- The scraper uses both requests and Pyppeteer. Requests is used for static pages, while Pyppeteer is used for pages that require JavaScript rendering.
- Ensure you comply with the website's terms of service and robots.txt file when using this scraper.
