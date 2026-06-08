# Stripe Connector

Generated connector for a CRM system using OAuth2 authentication.

## Features

- authentication
- CRUD operations
- pagination
- retries
- rate limiting
- structured logging

## Usage

```python
from stripe_connector import StripeConnector

connector = StripeConnector(base_url="https://api.example.com", token="YOUR_TOKEN")
records = connector.list_records("records")
print(records)
```