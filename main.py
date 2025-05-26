import requests
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional
from dataclasses import dataclass
from abc import ABC

# === Configuration ===
load_dotenv()

@dataclass
class Config:
    HUBSPOT_ACCESS_TOKEN: str = os.getenv("HUBSPOT_ACCESS_TOKEN")
    HUBSPOT_LIST_ID: str = os.getenv("HUBSPOT_LIST_ID")
    HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME: str = os.getenv("HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME")
    HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME: str = os.getenv("HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    HUBSPOT_API_BASE_URL: str = "https://api.hubapi.com"
    OPENAI_API_BASE_URL: str = "https://api.openai.com/v1"
    
    # OpenAI message templates
    OPENAI_SYSTEM_MESSAGE: str = os.getenv("OPENAI_SYSTEM_MESSAGE", "")
    OPENAI_USER_MESSAGE_TEMPLATE: str = os.getenv("OPENAI_USER_MESSAGE_TEMPLATE", "")
    OPENAI_WEB_SEARCH_QUERY_TEMPLATE: str = os.getenv("OPENAI_WEB_SEARCH_QUERY_TEMPLATE", "")
    
    @property
    def HUBSPOT_CATEGORY_FIELD_NAMES(self) -> List[str]:
        names_str = os.getenv("HUBSPOT_CATEGORY_FIELD_NAMES")
        if not names_str:
            return []
        return [category.strip() for category in names_str.split(',') if category.strip()]

# === Base API Client (Refactored) ===
class APIClient(ABC):
    def __init__(self, client_name: str, base_url: str, api_key: Optional[str]):
        self.client_name = client_name
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {} 
        if self.api_key:
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Makes a request to the configured API."""
        if not self.api_key:
            print(f"Error: {self.client_name} API Key/Token not available for request.")
            return None
            
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"{self.client_name} API request error to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"{self.client_name} API JSON decode error for {url}: {e}")
            if 'response' in locals() and response is not None:
                 print(f"Response text: {response.text}")
            return None

# === HubSpot Client (Simplified) ===
class HubSpotClient(APIClient):
    def __init__(self, access_token: Optional[str], base_url: str):
        super().__init__("HubSpot", base_url, access_token)
        if not access_token:
            print("Error: HubSpot Access Token is not configured.")
    
    # The _make_request method is now inherited from APIClient.

    def get_contacts_from_list(self, list_id: str) -> List[str]:
        """Retrieves all contact IDs from a specific HubSpot list, handling pagination."""
        contact_ids: List[str] = []
        endpoint = f"/crm/v3/lists/{list_id}/memberships?limit=100"
        
        page_count = 0
        MAX_PAGES_TO_FETCH = 20 # Safety break, adjust as needed

        while endpoint and page_count < MAX_PAGES_TO_FETCH:
            page_count += 1
            data = self._make_request("GET", endpoint)

            if not data:
                print(f"No data returned or error on page {page_count} for list {list_id}.")
                break 

            for member in data.get("results", []):
                if "recordId" in member:
                    contact_ids.append(str(member["recordId"]))
            
            paging_info = data.get("paging")
            if paging_info and paging_info.get("next") and paging_info["next"].get("link"):
                full_next_link = paging_info["next"]["link"]
                if self.base_url in full_next_link:
                    endpoint = full_next_link.split(self.base_url, 1)[-1]
                    if "limit=" not in endpoint:
                        separator = "&" if "?" in endpoint else "?"
                        endpoint += f"{separator}limit=100"
                else:
                    print(f"Warning: Next page link {full_next_link} does not match base URL.")
                    endpoint = None
            else:
                endpoint = None

        hubspot_reported_total = data.get('total', 'N/A') if data else 'N/A'
        print(f"Found {len(contact_ids)} contact IDs in total from list {list_id} after processing {page_count} page(s). (HubSpot reported total: {hubspot_reported_total})")
        return contact_ids

    def get_contact_details(self, contact_id: str, properties: List[str]) -> Optional[Dict]:
        """Retrieves details for a specific HubSpot contact."""
        endpoint = f"/crm/v3/objects/contacts/{contact_id}"
        params = {"properties": ",".join(properties)}
        
        data = self._make_request("GET", endpoint, params=params)
        if data:
            print(f"Retrieved details for contact ID {contact_id}")
            return data.get("properties", {})
        else:
            print(f"Failed to retrieve details for contact ID {contact_id}")
            return None

    def update_contact(self, contact_id: str, property_name: str, value: str) -> bool:
        """Updates a HubSpot contact with the specified property value."""
        endpoint = f"/crm/v3/objects/contacts/{contact_id}"
        payload = {"properties": {property_name: value}}
        
        response_data = self._make_request("PATCH", endpoint, data=json.dumps(payload))
        
        if response_data:
            print(f"Successfully updated contact {contact_id} with '{value}' in property '{property_name}'.")
            return True
        else:
            print(f"Failed to update contact {contact_id} with property '{property_name}'.")
            return False

# === OpenAI Client (Simplified) ===
class OpenAIClient(APIClient):
    def __init__(self, api_key: str, config: Config):
        super().__init__("OpenAI", config.OPENAI_API_BASE_URL, api_key)
        self.config = config

    # The _make_request method is now inherited from APIClient.

    def get_web_search_response(self, search_query: str, model: str = "gpt-4o") -> Optional[str]:
        """Performs a web search using OpenAI's API."""
        url = f"{self.base_url}/responses"
        data = {
            "model": model,
            "input": search_query,
            "tools": [{"type": "web_search"}]
        }

        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            
            message_output = next((item for item in result.get("output", []) 
                                 if item.get("type") == "message"), None)
            if message_output and "content" in message_output:
                text_block_item = next((block for block in message_output["content"] 
                                      if block.get("type") == "output_text"), None)
                if text_block_item and "text" in text_block_item:
                    return text_block_item["text"]
            return None
        except Exception as e:
            print(f"Error in OpenAI web search: {e}")
            return None

    def get_company_category(self, company_info: str, web_context: str, 
                           categories_list: List[str]) -> str:
        """Determines a company's category using OpenAI's API."""
        url = f"{self.base_url}/chat/completions"
        
        system_message = self.config.OPENAI_SYSTEM_MESSAGE.format(
            categories=", ".join(categories_list)
        )
        
        user_message = self.config.OPENAI_USER_MESSAGE_TEMPLATE.format(
            company_info=company_info,
            web_context=web_context,
            categories=", ".join(categories_list)
        )

        data = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.1,
            "max_tokens": 50
        }

        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            
            if result.get("choices") and len(result["choices"]) > 0:
                determined_category = result["choices"][0]["message"].get("content", "").strip()
                if determined_category in categories_list:
                    return determined_category
                for valid_cat in categories_list:
                    if valid_cat in determined_category:
                        return valid_cat
            return "Other"
        except Exception as e:
            print(f"Error getting category from OpenAI: {e}")
            return "Other"

# === Company Categorizer ===
class CompanyCategorizer:
    def __init__(self, config: Config):
        self.config = config
        if not config.HUBSPOT_ACCESS_TOKEN:
            raise ValueError("HubSpot Access Token is not configured.")
        if not config.OPENAI_API_KEY:
            raise ValueError("OpenAI API Key is not configured.")
            
        self.hubspot_client = HubSpotClient(config.HUBSPOT_ACCESS_TOKEN, config.HUBSPOT_API_BASE_URL)
        self.openai_client = OpenAIClient(config.OPENAI_API_KEY, config)

    def get_email_domain(self, email: str) -> Optional[str]:
        """Extracts the domain from an email address."""
        if email and "@" in email:
            return email.split("@")[-1]
        return None

    def process_contact(self, contact_id: str) -> bool:
        """Processes a single contact for categorization. Returns True if all steps involving updates succeed."""
        print(f"Fetching details for contact ID: {contact_id}")
        contact_props = self.hubspot_client.get_contact_details(
            contact_id, 
            ["email", "company"]
        )
        if not contact_props:
            print(f"Skipping contact {contact_id}: Failed to fetch details.")
            return False

        contact_email = contact_props.get("email")
        company_name = contact_props.get("company") # This is HubSpot's default 'Company name' field
        
        company_identifier = company_name
        email_domain = None
        if contact_email:
            email_domain = self.get_email_domain(contact_email)
            if not company_identifier and email_domain:
                company_identifier = email_domain
        
        if not company_identifier:
            print(f"Skipping contact {contact_id}: Could not determine company name or email domain.")
            return False
        print(f"Company Identifier for contact {contact_id}: {company_identifier}")

        # Get web context
        company_query_base = f"company {company_identifier}"
        if email_domain and company_identifier != email_domain and company_name == company_identifier:
            company_query_base += f" (domain: {email_domain})"
        
        web_search_query = self.config.OPENAI_WEB_SEARCH_QUERY_TEMPLATE.format(
            company_query=company_query_base
        )
        print(f"Performing OpenAI web search for: \"{web_search_query[:100]}...\"")
        company_context = self.openai_client.get_web_search_response(web_search_query)
        if not company_context:
            print(f"No web context found for {company_identifier}. Using fallback.")
            company_context = "No additional web context available."
        else:
            print(f"Web context retrieved for {company_identifier}.")

        # Store web context
        if self.config.HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME:
            print(f"Attempting to store web search context for contact {contact_id}...")
            context_stored_successfully = self.hubspot_client.update_contact(
                contact_id,
                self.config.HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME,
                company_context
            )
            if not context_stored_successfully:
                 print(f"Warning: Failed to store web context for contact {contact_id}. Proceeding with categorization.")
        else:
            print("Warning: HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME not configured. Skipping context storage.")

        # Determine category
        print(f"Determining category for: {company_identifier}")
        determined_category = self.openai_client.get_company_category(
            company_identifier,
            company_context,
            self.config.HUBSPOT_CATEGORY_FIELD_NAMES
        )
        print(f"Category determined for {company_identifier}: {determined_category}")

        # Store category
        if self.config.HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME:
            print(f"Attempting to store category '{determined_category}' for contact {contact_id}...")
            category_stored_successfully = self.hubspot_client.update_contact(
                contact_id,
                self.config.HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME,
                determined_category
            )
            if not category_stored_successfully:
                print(f"Warning: Failed to store category for contact {contact_id}.")
                return False
            return True # Successfully stored the category
        else:
            print("Warning: HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME not configured. Cannot store category.")
            return False

    def run(self, test_mode: bool = True):
        """Main execution method."""
        # Configuration check
        missing_configs = []
        if not self.config.HUBSPOT_ACCESS_TOKEN: missing_configs.append("HUBSPOT_ACCESS_TOKEN")
        if not self.config.HUBSPOT_LIST_ID: missing_configs.append("HUBSPOT_LIST_ID")
        if not self.config.HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME: missing_configs.append("HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME")
        if not self.config.HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME: 
            print("Warning: HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME is not set. Web context will not be stored.")
        if not self.config.OPENAI_API_KEY: missing_configs.append("OPENAI_API_KEY")
        if not self.config.HUBSPOT_CATEGORY_FIELD_NAMES: missing_configs.append("HUBSPOT_CATEGORY_FIELD_NAMES (resulted in empty list)")
        
        if missing_configs:
            print(f"Error: Critical configuration(s) missing: {', '.join(missing_configs)}. Please check your .env file.")
            return

        print("--- Initial Configuration ---")
        print(f"HubSpot List ID: {self.config.HUBSPOT_LIST_ID}")
        print(f"HubSpot Category Property: {self.config.HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME}")
        print(f"HubSpot Context Property: {self.config.HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME}")
        print(f"Category Names: {self.config.HUBSPOT_CATEGORY_FIELD_NAMES}")
        print(f"Test Mode: {test_mode}")
        print("-----------------------------")

        contact_ids = self.hubspot_client.get_contacts_from_list(self.config.HUBSPOT_LIST_ID)
        if not contact_ids:
            print("No contacts found in the list or an error occurred fetching them. Exiting.")
            return
        
        print(f"--- NOTE: Found {len(contact_ids)} contacts in the list. ---")

        processed_successfully_count = 0
        for i, contact_id in enumerate(contact_ids):
            print(f"\n--- Processing Contact {i+1}/{len(contact_ids)} (ID: {contact_id}) ---")
            if self.process_contact(contact_id):
                processed_successfully_count += 1
            
            if test_mode and i == 0:
                print("--- TESTING MODE: Processed 1 contact. Halting loop now. ---")
                break
        
        print("\n--- Script execution finished. ---")
        print(f"Successfully processed and updated {processed_successfully_count} contact(s).")
        if test_mode and len(contact_ids) > 0:
            print("Ran in TEST MODE, processed only the first contact found.")

# === Main Execution ===
if __name__ == "__main__":
    try:
        config_instance = Config()
        categorizer = CompanyCategorizer(config_instance)
        # Set test_mode to True for testing with one contact, False for full run.
        categorizer.run(test_mode=True) 
    except ValueError as e:
        print(f"Initialization Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during script execution: {e}")