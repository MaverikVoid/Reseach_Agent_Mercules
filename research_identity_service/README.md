# Research Identity Service

A production-quality Python microservice built using FastAPI, Pydantic, PyMuPDF, and the NVIDIA/OpenRouter APIs. This service forms part of the AI Research Chief of Staff system, analyzing researcher profiles from multiple inputs (PDF resumes, research paper PDFs, portfolios, GitHub, and Google Scholar) and consolidating them into a unified, machine-readable JSON schema (`research_profile.json`).

---

## 🛠️ Tech Stack
- **Python 3.12** (Backward compatible to 3.10)
- **FastAPI**
- **Pydantic V2** (Self-correcting validation schema)
- **PyMuPDF** (High-fidelity PDF text extraction)
- **OpenAI SDK** (Connecting to NVIDIA NIM / OpenRouter APIs)
- **SQLite** (Logs execution history and caches web crawls to bypass rate limits)

---

## 📁 Directory Structure
```
research_identity_service/
├── app/
│   ├── api/
│   │   └── endpoints.py      # POST /api/generate-profile
│   ├── core/
│   │   ├── config.py         # BaseSettings loader
│   │   └── database.py       # SQLite execution logs & web cache
│   ├── extractors/
│   │   ├── pdf_extractor.py  # fitz-based PDF text parser
│   │   └── web_extractor.py  # httpx, BeautifulSoup & GitHub API client
│   ├── models/
│   │   └── profile.py        # Pydantic ResearchProfile Schema
│   ├── prompts/
│   │   └── templates.py      # LLM Prompt definitions
│   ├── services/
│   │   ├── llm_service.py    # OpenAI client with self-correcting validation loop
│   │   └── profile_service.py # Core orchestrator
│   └── main.py               # Fast API App instantiation
├── tests/
│   └── test_api.py           # Unit tests
├── requirements.txt          # Python dependencies
└── .env.example              # Configuration template
```

---

## ⚙️ Configuration & Setup

1. **Install dependencies**:
   ```bash
   pip install -r research_identity_service/requirements.txt
   ```

2. **Set up Environment Variables**:
   Create a `.env` file inside the `research_identity_service/` directory (or workspace root) based on `.env.example`:
   ```env
   NVIDIA_API_KEY=nvapi-xxxx... # Default if present
   OPENROUTER_API_KEY=sk-or-v1-xxxx... # Backup/Alternative
   PORT=8001
   HOST=0.0.0.0
   DATABASE_URL=sqlite:///data/cache/app.db
   OUTPUT_DIR=data/output
   ```

---

## 🚀 Running the Microservice

To run the FastAPI server locally:
```bash
python -m uvicorn app.main:app --port 8001 --reload
```
Once started, the documentation is interactive at:
* Swagger UI: `http://localhost:8001/docs`
* ReDoc: `http://localhost:8001/redoc`

---

## 🧪 Testing the API

To run the unit test suite:
```bash
pytest research_identity_service/tests
```

### Manual Request Example (cURL)
You can trigger profile generation by uploading the researcher's PDF resume, optional research paper PDFs, and providing their online profile URLs:

```bash
curl -X 'POST' \
  'http://localhost:8001/api/generate-profile' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'resume=@Meet_Dabgar_resume.pdf;type=application/pdf' \
  -F 'papers=@tnnls.pdf;type=application/pdf' \
  -F 'portfolio_url=https://meetdabgar.github.io' \
  -F 'github_url=https://github.com/MaverikVoid' \
  -F 'scholar_url=https://scholar.google.com/citations?user=xxxx'
```

---

## 🛡️ Robustness Features
1. **SQLite Web Cache**: All fetched URL HTML pages are cached in a SQLite database to prevent redundant network scraping and avoid getting rate limited or CAPTCHA-blocked during active development.
2. **Self-Correcting LLM Loop**: If the LLM generates a JSON that fails the Pydantic schema validation, the service automatically initiates a correction conversation loop by feeding the validation error back to the LLM to fix the formatting (up to 3 retries).
