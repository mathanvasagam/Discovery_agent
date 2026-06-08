# Systems Discovery & Integration Agent

This is a developer-centric tool built to automate the tedious process of auditing enterprise documents, listing systems, finding integration gaps, and generating code for API connectors.

Instead of spent days digging through PDF manuals, spreadsheets, and meeting notes, this app processes the documents, builds a clean inventory list, works out the integration roadmap for your business goals, and writes clean Python/Node.js connector code that actually compiles and runs.

---

## How It Works Under the Hood

### 1. File Parsing & Text Extraction
The parser (`backend/core/ingestor.py`) takes plain text, Markdown, PDF, or Excel spreadsheets (`.xlsx`) and chops them into manageable chunks. For spreadsheets, it loops through the sheets, rows, and cells using `openpyxl` to extract any text data.

### 2. Finding the Systems (Level 1)
To prevent hallucinations (which LLMs are famous for), the system uses a hybrid approach:
- First, it scans the text using a local catalog of common enterprise system names (Salesforce, Jira, Slack, Coupa, HubSpot, SAP, NetSuite, etc.).
- It verifies any LLM-extracted names against the actual document text using a word-overlap lookup. If the LLM invents a system name that is not mentioned in the source file, the filter throws it out.
- Any extracted system gets a confidence score. If a system is explicitly named, it gets a high score (95%+). If it is only inferred from the context, it gets lower confidence and is flagged in the UI for review.
- Before anything goes to database, the PII filter (`backend/core/redactor.py`) cleans up sensitive data like emails, phone numbers, and IP addresses, but makes sure to leave system names intact.

### 3. Integration Gap Analysis (Level 2)
The backend maps your business goals (e.g. "Create invoices from opportunities") to the system inventory. If any required systems are missing, it flags them as integration gaps, calculates development effort, and identifies blocking dependencies.

### 4. Code Generation & Sandbox Testing (Level 3)
When you click to generate a connector (supporting Python and Node.js), the backend calls the LLM, reads the generated package (code, unit tests, and readme), and runs it inside a sandbox environment to test it.
- **Why it is robust**: If the LLM generates a syntax error or a bad mock test, the backend catches it and automatically falls back to a clean, pre-tested, and offline-mocked template. This ensures you always get a 100% valid package that compiles successfully.

---

## Setup & Running Locally

### Prerequisites
You will need **Python 3.10+** and **Node.js 18+** installed on your system.

### Option A: Running with Docker Compose (Easiest)
If you have Docker installed, you can build and run both the frontend and backend with a single command:
```bash
docker-compose up --build
```
- The frontend will be available at `http://localhost:5173`
- The backend API will run at `http://localhost:8000`

---

### Option B: Running Manually

#### 1. Configure Environment Variables
Copy the example configuration to create your `.env` file:
```bash
# In the project root
cp .env.example .env

# In the backend directory
cp backend/.env.example backend/.env
```
Open these files and paste your **Groq API Key** (or Gemini API key). Groq is the primary model used for LLM inference.

#### 2. Start the Backend API
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Start the FastAPI server
export PYTHONPATH=$PYTHONPATH:.
python3 -m backend.main
```
The server will run on `http://localhost:8000`.

#### 3. Start the React Frontend
```bash
cd frontend
npm install
npm run dev
```
The React development server will start on `http://localhost:5173`.

---

## Running the Tests

To verify that the ingestion, extraction, and code validation components are working correctly, run the test suites:

### Backend Test Suite
```bash
env -i PATH=$PATH PYTHONPATH=backend venv/bin/pytest backend/core/
```

### Frontend UI Test Suite
```bash
cd frontend
npm run test
```

---

## Codebase Layout

- `backend/main.py`: FastAPI server setup and routes.
- `backend/models.py`: Database models (SQLModel).
- `backend/core/ingestor.py`: Ingests and cleans up text from different formats (PDFs, text files, Excel).
- `backend/core/extractor.py`: Extracts system metadata, assigns confidence, and applies hallucination filters.
- `backend/core/sandbox.py`: Runs and validates generated connector files.
- `backend/core/code_gen.py`: Generates the connector packages and contains default fallback code.
- `frontend/src/App.tsx`: Main React dashboard UI.
- `frontend/src/services/api.ts`: API helper module for the frontend.
