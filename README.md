# Company Categorization Tool

This tool automatically categorizes companies in HubSpot based on custom-defined categories. It uses OpenAI's API to analyze company information and web context to determine the most appropriate category for each company.

## Features

- Fetches contacts from a specified HubSpot list
- Performs web searches to gather company information
- Uses OpenAI to analyze and categorize companies
- Updates HubSpot contacts with determined categories
- Stores web search context in HubSpot
- Supports test mode for safe testing

## Prerequisites

- Python 3.8 or higher
- HubSpot account with API access
- OpenAI API key
- Required HubSpot custom properties set up

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file:
```bash
cp .env.example .env
```

5. Configure your `.env` file with the following variables:
```env
# HubSpot Configuration
HUBSPOT_ACCESS_TOKEN=your_hubspot_access_token_here
HUBSPOT_LIST_ID=your_hubspot_list_id_here
HUBSPOT_CATEGORY_PROPERTY_INTERNAL_NAME=your_category_property_name_here
HUBSPOT_COMPANY_CONTEXT_PROPERTY_INTERNAL_NAME=your_context_property_name_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Category Configuration
HUBSPOT_CATEGORY_FIELD_NAMES=[category fields as set up in HubSpot]

# OpenAI Message Templates
OPENAI_SYSTEM_MESSAGE="..."
OPENAI_USER_MESSAGE_TEMPLATE="..."
```

## HubSpot Setup

1. Create a custom property in HubSpot for storing the category
2. Create a custom property in HubSpot for storing the web search context
3. Create a list in HubSpot containing the contacts you want to categorize
4. Note down the internal names of these properties and the list ID

## Usage

1. Run the script in test mode (processes one contact):
```bash
python main.py
```

2. For production use, modify the last line in `main.py`:
```python
categorizer.run(test_mode=False)
```


## Error Handling

The script includes comprehensive error handling for:
- API connection issues
- Invalid responses
- Missing or invalid data
- Configuration problems

