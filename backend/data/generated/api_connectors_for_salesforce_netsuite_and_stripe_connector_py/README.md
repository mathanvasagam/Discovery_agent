# API connectors for Salesforce, NetSuite, and Stripe Connector

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
from api_connectors_for_salesforce_netsuite_and_stripe_connector import ApiConnectorsForSalesforceNetsuiteAndStripeConnector

connector = ApiConnectorsForSalesforceNetsuiteAndStripeConnector(base_url="https://api.example.com", token="YOUR_TOKEN")
records = connector.list_records("records")
print(records)
```