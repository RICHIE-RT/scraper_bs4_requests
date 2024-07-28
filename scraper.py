import re
import os
import time
import requests
from urllib import parse
from utils import utility
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils.bk_event import Website
from utils.log_init import info_logger, error_logger
load_dotenv()

DEVELOPER_TESTING = os.getenv("DEVELOPER_TESTING")


class WebsiteScraper:

    # NOTE: Not implementing the session(requests) because maybe you can switch on proxies or AWS lambda.
    def __init__(self, type_short_name: str, identifier: int) -> None:
        self.name = "example"
        self.id = "123"
        self.identifier = identifier
        self.type_short_name = type_short_name
        self.home_link = "https://www.example.com"
        self.event_api = f"https://www.example.com/Competitions/{self.identifier}?displayType=default"
        self.headers = {
            "referer": "https://www.example.com",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        
        self.match_data = dict()
        self.meta_data = dict()
        self.all_details = list()

        self.start_time = time.time().__trunc__()
        self.end_time = 0
        self.meta_data["start_time"] = self.start_time

    def start_scraper(self):
        self.get_event_url()
        self.end_scraper()
        info_logger.info("------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")

    def get_event_url(self):
        response = requests.request("GET", self.event_api, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")
        url = soup.find("a", href=re.compile(self.identifier))
        if url and url.attrs.get("href"):
            self.event_url = parse.urljoin(self.home_link, url.attrs.get("href"))
            self.get_match_details()
        else:
            error_logger.error(f"Failed to get match id for event: {self.type_short_name} | identifier: {self.identifier}, status_code: {response.status_code}")
    
    def get_match_details(self):
        response = requests.request("GET", self.event_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")
        if response.status_code == 200:
            try:
                matches = soup.select(".staticContent .staticContent")
                for match in matches:
                    event_name = match.find_all(class_="eventName")

                    kickoff = match.find(class_="start_time").get_text(strip=True).replace(",", "").replace("  ", " ")
                    self.match_data["start_time"] = kickoff
                    self.match_data["event_name"] = event_name

                    match_columns = list(match.select_one(".matchTable thead tr").stripped_strings)
                    match_columns = match_columns[2 if len(match_columns) == 5 else 1:]
                    match_columns.insert(0, "team")
                    sub_groups = list()
                    match_trs = match.select(".groupTable tbody tr")
                    for match_tr in match_trs:
                        sub_groups.append((dict(zip(match_columns, list(match_tr.stripped_strings)))))
                    structured_groups = utility.restructured_addtional_sub_details(sub_groups)
                    [self.all_details.append({structured_group_name: structured_group_value}) for structured_group_name, structured_group_value in structured_groups.items()]

                    check_additional_details = list()
                    group_details = match.find(class_="groupDetails")
                    if group_details: # Some of does not have the addtional detaiks
                        addtional_details = group_details.select("dd[data-dynload]")
                        for addtional_detail in addtional_details:
                            addtional_detail_name = addtional_detail.previous_element.previous_element.text
                            detail_url_suffix = addtional_detail.attrs["data-dynload"]
                            addtional_detail_url = f"https://www.example.com/dyn{detail_url_suffix}"
                            if addtional_detail_url in check_additional_details:
                                continue
                            check_additional_details.append(addtional_detail_url)
                            self.get_additional_details(addtional_detail_name, addtional_detail_url)
                        
                    self.insert_details_into_db()
            except Exception as e:
                error_logger.error(f"Failed to extract the details in get match details for event: {self.type_short_name} | event_identifier: {self.type_short_name} | event url: {self.event_url}, status_code: {response.status_code} | {e}")
                return None
        else:
            error_logger.error(f"Failed to get match details for event: {self.type_short_name} | event_identifier: {self.type_short_name} | event {self.identifier} | event url: {self.event_url}, status_code: {response.status_code}")
            return None
        
    def get_additional_details(self, addtional_detail_name: str, additional_detail_url: str):
        response = requests.request("GET", additional_detail_url, headers=self.headers)
        if response.status_code == 200:
            try:
                soup = BeautifulSoup(response.text, "html.parser")
                sub_details, sub_selections = dict(), list()
                sub_details_groups = soup.find_all("tr")
                for sub_details_group in sub_details_groups:
                    team_name, price = list(sub_details_group.stripped_strings)
                    sub_selections.append({
                        "team_name": team_name,
                        "price": price
                    })
                sub_details.update({addtional_detail_name: sub_selections})
                self.all_details.append(sub_details)
            except Exception as e:
                error_logger.error(f"Failed to convert into soup in get additional details for event: {self.type_short_name} | event_identifier: {self.identifier} | event url: {self.event_url} | additional_detail_url: {additional_detail_url}, status_code: {response.status_code} | {e}")
                return None
        else:
            error_logger.error(f"Failed to get additional details for event: {self.type_short_name} | event_identifier: {self.identifier} | event_url: {self.event_url} | additional_detail_url: {additional_detail_url}, status_code: {response.status_code}")
            return None
        
    def insert_details_into_db(self):
        self.match_data.update({
            "details": self.all_details,
        })
        if DEVELOPER_TESTING:
            utility.write_json(file_name=f"{self.name.lower()}_{self.type_short_name}_match", data=self.match_data)
        else:
            if self.type_short_name == "mlb":
                "INSERT DATA INTO DATABASE"
            else:
                "INSERT DATA INTO DATABASE 2"

        info_logger.info(f"Finished scraping for event name: {self.type_short_name} | event_id: {self.identifier} | evnt_url: {self.event_url} | details found: {len(self.all_details)}")
        self.top_details = dict()
        self.all_details = list()

    def end_scraper(self):
        self.end_time = time.time().__trunc__()
        self.meta_data["stop_time"] = self.end_time
        self.meta_data["duration"] = self.end_time - self.start_time
        if DEVELOPER_TESTING:
            utility.write_json(file_name=f"{self.name.lower()}_{self.type_short_name}_metadata", data=self.meta_data)
        else:
            "INSERT DATA INTO DATABASE"


class WebsiteScraperEndpoint(WebsiteScraper):

    def __init__(self, type_short_name: str, identifier: int) -> None:
        super().__init__(type_short_name, identifier)
        self.home_link = f"https://www.example.com/<ENDPOINT>"

    def get_event_url(self):
        response = requests.request("GET", self.home_link, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")
        match_rounds_section = soup.select_one(".staticContent .framePanel")
        event_url_elements = match_rounds_section.find_all("a", href=lambda link: link.endswith(self.identifier))
        if event_url_elements:
            for event_url_element in event_url_elements:
                if event_url_element and event_url_element.attrs.get("href"):
                    event_url = event_url_element.attrs.get("href")
                    self.event_url = parse.urljoin(self.home_link, event_url)
                    self.get_match_details()
        else:
            error_logger.error(f"Event URL not found for event: {self.type_short_name} | event identifier: {self.identifier}")


Website_scraper_instance = WebsiteScraper(short_name=Website.TYPE, id=Website.TYPE_ID)
Website_scraper_instance.start_scraper()

Website_scraper_instance2 = WebsiteScraperEndpoint(short_name=Website.TYPE, id=Website.TYPE)
Website_scraper_instance2.start_scraper()
