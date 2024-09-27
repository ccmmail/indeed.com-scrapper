Programmatically scrape job search engines (currently indeed.com only) and outputs search results into a formatted gsheet

Features
- Runs multiple searchs (e.g., SWE internship, data analytics in New York by specifying the target URLs to search (and depth for each URL) in gsheet
- Scrapes results and appends them to gsheet for easy manipulation

Usage notes
- Requires ez-sheets library, which requires you to place your google secrets (tokens and pickle files) into the same directory as main program

Potential features enhancements
- move google secrets into a separate directory
- expand to other job search engines

