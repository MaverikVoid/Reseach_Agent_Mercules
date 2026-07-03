from app.extractors.pdf_extractor import extract_text_from_pdf
from app.extractors.web_extractor import fetch_portfolio, fetch_github, fetch_scholar
from app.services.llm_service import synthesize_profile
from app.core.database import log_run
from app.core.config import settings
from app.prompts.templates import USER_PROMPT_TEMPLATE
import jinja2
import json
import logging
from pathlib import Path
from typing import List, BinaryIO

logger = logging.getLogger(__name__)

def generate_research_profile(
    resume_file: BinaryIO,
    resume_filename: str,
    paper_files: List[tuple[BinaryIO, str]],
    portfolio_url: str,
    github_url: str,
    scholar_url: str = None
) -> dict:
    """
    Orchestrate extraction of profile data, compile prompts, synthesize via LLM,
    and save output. Returns status and file paths.
    """
    status = "started"
    papers_names = ", ".join([name for _, name in paper_files])
    
    # 1. Extract resume text
    logger.info("Extracting resume text...")
    try:
        resume_text = extract_text_from_pdf(resume_file)
    except Exception as e:
        logger.error(f"Failed to extract resume text: {e}")
        resume_text = "[Error extracting resume]"
        
    # 2. Extract papers text
    papers_text_list = []
    for paper_file, filename in paper_files:
        logger.info(f"Extracting paper text from: {filename}...")
        try:
            p_text = extract_text_from_pdf(paper_file)
            papers_text_list.append(f"=== File: {filename} ===\n{p_text}")
        except Exception as e:
            logger.error(f"Failed to extract paper text from {filename}: {e}")
            papers_text_list.append(f"=== File: {filename} ===\n[Error extracting paper text: {e}]")
            
    papers_text = "\n\n".join(papers_text_list)
    
    # 3. Extract web data
    portfolio_text = fetch_portfolio(portfolio_url) if portfolio_url else ""
    github_text = fetch_github(github_url) if github_url else ""
    scholar_text = fetch_scholar(scholar_url) if scholar_url else ""
    
    # 4. Compile prompt
    try:
        template = jinja2.Template(USER_PROMPT_TEMPLATE)
        prompt = template.render(
            resume_text=resume_text,
            papers_text=papers_text,
            portfolio_text=portfolio_text,
            github_text=github_text,
            scholar_text=scholar_text
        )
    except Exception as e:
        logger.error(f"Error compiling template: {e}")
        status = "failed"
        log_run(status, resume_filename, papers_names, portfolio_url, github_url, scholar_url, error_message=f"Template compile error: {e}")
        raise e
        
    # 5. Call LLM
    try:
        logger.info("Calling LLM to synthesize research profile...")
        profile = synthesize_profile(prompt)
        
        # 6. Save output JSON
        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        profile_path = output_dir / "research_profile.json"
        
        profile_json = profile.model_dump_json(indent=2)
        profile_path.write_text(profile_json, encoding="utf-8")
        logger.info(f"Research profile saved to {profile_path}")
        
        status = "completed"
        log_run(status, resume_filename, papers_names, portfolio_url, github_url, scholar_url, profile_path=str(profile_path))
        
        return {
            "success": True,
            "profile_path": str(profile_path),
            "profile": profile.model_dump()
        }
    except Exception as e:
        logger.error(f"Error synthesizing or saving profile: {e}")
        status = "failed"
        log_run(status, resume_filename, papers_names, portfolio_url, github_url, scholar_url, error_message=str(e))
        return {
            "success": False,
            "error": str(e)
        }
