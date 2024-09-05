import bs4
import ezsheets
from datetime import datetime
import time
from selenium import webdriver


GSHEET_NAME = 'intern search'
TAB_NAME_URLS = 'target_URL'  # gsheet tab for search URLs to scrape
URL_COLUMN = 'A'  # search URLs in 'target_URL' tab
PAGES_COLUMN = 'B'  # number of pages to paginate in 'target_URL' tab
TAB_NAME_LISTINGS = 'superset'  # gsheet tab for listings
COMPANY_COLUMN = 'B'  # company name in 'superset' tab
APPLICATION_DUE_COLUMN = 'L'  # app due date in 'superset' tab
APPLIED_COLUMN = 'N'  # applied status in 'superset' tab
CONNECTIONS_LOOKUP = 'connections!$A:$A,connections!$C:$C'
CATEGORIZATION_LOOKUP = 'companies!A:A,companies!K:K,"N/A",0,1'
JOB_ID_COLUMN = 3  # column with connections in "connections" tab
TODAY_DATE = datetime.today().strftime("%Y-%m-%d")
API_WAIT_DELAY = 30  # seconds to wait after each URL update


def get_payload(url):
    driver = webdriver.Chrome()
    driver.get(url)
    payload = driver.page_source
    return payload


def scrape_serp_indeed(url):
    # get list of job listings from webpage
    payload = get_payload(url)
    payload_soup = bs4.BeautifulSoup(payload, 'html.parser')
    serp_soup = payload_soup.select('.slider_container')
    return serp_soup


def extract_job_elements_indeed(listing_soup):
    # for indeed.com
    # takes in a beautiful soup serp html and returns a dictionary of
    # job_elements = {job_ID, title, company, location, description,
    # posted_date, site_URL, google_URL}

    job_elements = {}

    # Extract the job_ID from data-jk value
    job_header = listing_soup.find('a', class_='jcs-JobTitle')
    job_elements['job_ID'] = job_header.get('data-jk')

    # Extract the title value
    job_title_span = job_header.find('span')
    job_elements['title'] = job_title_span.get('title')

    # Extract the company name
    job_elements['company'] = listing_soup.find('span',
                                                {'data-testid': 'company-name'}
                                                ).text

    # Extract the location
    job_elements['location'] = listing_soup.find('div',
                                                {'data-testid': 'text-location'}
                                                ).text

    # Extract application due date - not available in Indeed
    job_elements['application_due_date'] = ""

    # Extract the posted date
    date_element = listing_soup.find('span',
                                    {'data-testid': 'myJobsStateDate'}
                                    )
    if date_element is not None:
        job_elements['posted_date'] = date_element.text.strip()
    else:
        job_elements['posted_date'] = ""

    # Extract job description from text
    ul_element = listing_soup.find('ul',
                                   style="list-style-type:circle;margin-top: "
                                         "0px;margin-bottom: 0px;padding-left:20px;")
    if ul_element is not None:
        job_elements['description'] = ' '.join([li.text
                                                for li in ul_element.find_all('li')
                                                ])
    else:
        job_elements['description'] = ""

    # Create direct URL
    job_elements['site_URL'] = ("https://www.indeed.com/viewjob?jk=" +
                                str(job_elements['job_ID'])
                                )

    # Create google URL
    job_elements['google_URL'] = ("https://www.google.com/search?q=" +
                                  str(job_elements['company'].replace(' ', '+')) +
                                  "+" +
                                  str(job_elements['title'].replace(' ', '+'))
                                  )
    return job_elements


##
## MAIN PROGRAM
##
print("STARTING PROGRAM...")
print(f"Accessing gsheet ({time.ctime()})...")

# create ezsheet objects
gsheet = (ezsheets.Spreadsheet(GSHEET_NAME))
tab_listings = gsheet[TAB_NAME_LISTINGS]
tab_urls = gsheet[TAB_NAME_URLS]

# create list of URLs to extract from gsheet input
search_urls = tab_urls.getColumn(URL_COLUMN)
page_depth = tab_urls.getColumn(PAGES_COLUMN)
target_urls = []  # initialize list of urls
for i in range(1, len(search_urls)):  # start 1 to skip header row
    if search_urls[i].startswith("http"):
        for j in range(int(page_depth[i])):
            start_count = j * 10
            if start_count > 0:
                modified_url = search_urls[i].replace("&vjk=",
                                                       f"&start={start_count}&vjk=")
            else:
                modified_url = search_urls[i]
            target_urls.append(modified_url)
    else:
        break

print("Number of pages to scrape: " + str(len(target_urls)))
print()

# extract list of listings and their elements from created URLs
for url in target_urls:
    print(f"Scrapping webpage {url} ({time.ctime()})...")
    # initialize list of dictionary of job elements
    job_listings = []
    # get list of job listing SOUPs from SRP
    listings_soup = scrape_serp_indeed(url)
    # extract job elements into a dictionary
    for listing in listings_soup:
        listing_elements = extract_job_elements_indeed(listing)
        listing_elements['scraped_date'] = TODAY_DATE  # stamp dict entry
        # add dictionary of job elements into job_listing
        job_listings.append(listing_elements)

    # tag scraped listings as new vs. duplicate to prior jobs
    print(f"Identifying unique listings vs. previous listings "
          f"({time.ctime()})...")
    job_IDs_prior = tab_listings.getColumn(JOB_ID_COLUMN)
    for i in range(len(job_listings)):
        if job_listings[i]['job_ID'] in job_IDs_prior:
            job_listings[i]['new_listing'] = "duplicate"
        else:
            job_listings[i]['new_listing'] = "new"

    # find next_empty_row for insertion in gsheet
    next_empty_row = 0  # initialize next_empty_row variable
    rows = tab_listings.getRows()  # Get list of rows
    for i, row in enumerate(rows):
        if not any(row):  # Check if the row is completely empty
            next_empty_row = i + 1  # current row + 1, as ezsheet is 1-indexed
            break

    # append job listings into gsheet
    print(f"Entering listings into gsheet ({time.ctime()}...")
    for i in range(len(job_listings)):
        categorization_formula = (f'=XLOOKUP('
                                  f'{COMPANY_COLUMN}{next_empty_row},'
                                  f'{CATEGORIZATION_LOOKUP})'
                                  )
        connections_formula = (f"=XLOOKUP("
                               f"{COMPANY_COLUMN}{next_empty_row},"
                               f"{CONNECTIONS_LOOKUP})"
                               )
        deadline_formula = (f'=if(isblank({APPLIED_COLUMN}{next_empty_row}),if(isblank('
                            f'{APPLICATION_DUE_COLUMN}{next_empty_row}),"unknown",'
                            f'if({APPLICATION_DUE_COLUMN}{next_empty_row}<today(),"past deadline",'
                            f'"not due")),if({APPLIED_COLUMN}{next_empty_row}'
                            f'="pass","pass","submitted"))'
                            )
        tab_listings.updateRow(next_empty_row,
                              [job_listings[i]['title'],
                              job_listings[i]['company'],
                              job_listings[i]['job_ID'],
                              job_listings[i]['new_listing'],
                              job_listings[i]['location'],
                              job_listings[i]['description'],
                              job_listings[i]['site_URL'],
                              job_listings[i]['google_URL'],
                              job_listings[i]['scraped_date'],
                              job_listings[i]['posted_date'],
                              categorization_formula,
                              job_listings[i]['application_due_date'],
                              deadline_formula,
                              "",
                              connections_formula]
                             )
        print(f"Entering item {i} at row: {next_empty_row} -"
              f" {job_listings[i]['title']}"
              )
        next_empty_row += 1

    # [hack] ensure that Google API writes are finished before next loop
    print()
    print(f"waiting {API_WAIT_DELAY} seconds before processing next URL"
          f"in case GSheet is still finishing API writes")
    time.sleep(API_WAIT_DELAY)
    print()

    # refresh the gsheet with the appended listings before next loop
    tab_listings.refresh()

print(f"ALL DONE! ({time.ctime()})")
