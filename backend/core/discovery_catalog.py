from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class SystemProfile:
    canonical_name: str
    aliases: List[str]
    category: str
    auth_method: str
    criticality: str
    key_entities: List[str]
    business_processes: List[str]


KNOWN_SYSTEMS: List[SystemProfile] = [
    SystemProfile(
        canonical_name="Salesforce",
        aliases=["salesforce", "salesforce crm", "sales cloud"],
        category="CRM",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["Account", "Contact", "Lead", "Opportunity"],
        business_processes=["Lead Management", "Opportunity Management", "Customer Success"],
    ),
    SystemProfile(
        canonical_name="NetSuite",
        aliases=["netsuite", "oracle netsuite"],
        category="ERP",
        auth_method="Token Based",
        criticality="High",
        key_entities=["Customer", "Invoice", "PurchaseOrder", "Vendor"],
        business_processes=["Order to Cash", "Billing", "Procurement"],
    ),
    SystemProfile(
        canonical_name="Jira",
        aliases=["jira", "jira service management", "atlassian jira"],
        category="Issue Tracker",
        auth_method="API Token",
        criticality="Medium",
        key_entities=["Issue", "Project", "Ticket", "Sprint"],
        business_processes=["Incident Management", "Service Desk", "Project Tracking"],
    ),
    SystemProfile(
        canonical_name="Workday",
        aliases=["workday"],
        category="HRIS",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["Employee", "Job", "OnboardingTask", "Payroll"],
        business_processes=["Hiring", "Onboarding", "HR Operations"],
    ),
    SystemProfile(
        canonical_name="Slack",
        aliases=["slack"],
        category="Other",
        auth_method="OAuth2",
        criticality="Medium",
        key_entities=["Channel", "Message", "User"],
        business_processes=["Notifications", "Collaboration"],
    ),
    SystemProfile(
        canonical_name="HubSpot",
        aliases=["hubspot"],
        category="CRM",
        auth_method="API Key",
        criticality="Medium",
        key_entities=["Company", "Contact", "Deal"],
        business_processes=["Marketing Automation", "Lead Nurture"],
    ),
    SystemProfile(
        canonical_name="Okta",
        aliases=["okta", "okta identity cloud"],
        category="Other",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["User", "Group", "Application"],
        business_processes=["Identity Management", "SSO"],
    ),
    SystemProfile(
        canonical_name="Stripe",
        aliases=["stripe", "stripe payments"],
        category="Finance",
        auth_method="API Key",
        criticality="High",
        key_entities=["Customer", "Invoice", "PaymentIntent"],
        business_processes=["Payments", "Billing"],
    ),
    SystemProfile(
        canonical_name="SAP",
        aliases=["sap", "sap erp"],
        category="ERP",
        auth_method="SAML/OAuth2",
        criticality="High",
        key_entities=["Order", "Material", "Invoice"],
        business_processes=["Finance", "Supply Chain"],
    ),
    SystemProfile(
        canonical_name="ServiceNow",
        aliases=["servicenow"],
        category="Issue Tracker",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["Incident", "Request", "CMDB CI"],
        business_processes=["ITSM", "Change Management"],
    ),
    SystemProfile(
        canonical_name="Snowflake",
        aliases=["snowflake", "snowflake data cloud"],
        category="Database",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["Database", "Schema", "Table", "Warehouse"],
        business_processes=["Data Warehousing", "Analytics"],
    ),
    SystemProfile(
        canonical_name="Zendesk",
        aliases=["zendesk", "zendesk support"],
        category="Issue Tracker",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["Ticket", "User", "Organization"],
        business_processes=["Customer Support", "Ticketing"],
    ),
    SystemProfile(
        canonical_name="Coupa",
        aliases=["coupa"],
        category="Finance",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["Invoice", "PurchaseOrder", "Supplier"],
        business_processes=["Procurement", "Expense Management"],
    ),
    SystemProfile(
        canonical_name="AWS",
        aliases=["aws", "amazon web services"],
        category="Infrastructure",
        auth_method="IAM",
        criticality="High",
        key_entities=["EC2", "S3", "RDS", "Lambda"],
        business_processes=["Cloud Computing", "Infrastructure Management"],
    ),
    SystemProfile(
        canonical_name="Greenhouse",
        aliases=["greenhouse"],
        category="HRIS",
        auth_method="API Key",
        criticality="Medium",
        key_entities=["Candidate", "Job", "Application"],
        business_processes=["Recruiting", "Hiring"],
    ),
    SystemProfile(
        canonical_name="Gainsight",
        aliases=["gainsight"],
        category="CRM",
        auth_method="OAuth2",
        criticality="Medium",
        key_entities=["Customer", "SuccessPlan", "Survey"],
        business_processes=["Customer Success"],
    ),
    SystemProfile(
        canonical_name="Looker",
        aliases=["looker"],
        category="Database",
        auth_method="OAuth2",
        criticality="Medium",
        key_entities=["Dashboard", "Look", "Explore"],
        business_processes=["Business Intelligence", "Reporting"],
    ),
    SystemProfile(
        canonical_name="Workato",
        aliases=["workato"],
        category="Other",
        auth_method="OAuth2",
        criticality="High",
        key_entities=["Recipe", "Connection", "Job"],
        business_processes=["Automation", "Integration"],
    ),
]


PROFILE_BY_ALIAS: Dict[str, SystemProfile] = {
    alias.lower(): profile
    for profile in KNOWN_SYSTEMS
    for alias in profile.aliases
}


GOAL_KEYWORDS = {
    "invoice": ["NetSuite", "Stripe", "SAP"],
    "invoices": ["NetSuite", "Stripe", "SAP"],
    "opportunity": ["Salesforce"],
    "opportunities": ["Salesforce"],
    "lead": ["Salesforce", "HubSpot"],
    "leads": ["Salesforce", "HubSpot"],
    "employee": ["Workday"],
    "employees": ["Workday"],
    "onboarding": ["Workday", "Jira", "Slack", "Okta"],
    "ticket": ["Jira", "ServiceNow"],
    "tickets": ["Jira", "ServiceNow"],
    "payment": ["Stripe"],
    "payments": ["Stripe"],
}


def iter_profiles() -> Iterable[SystemProfile]:
    return KNOWN_SYSTEMS
