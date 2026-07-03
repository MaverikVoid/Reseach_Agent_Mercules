from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
from app.services.profile_service import generate_research_profile
from io import BytesIO

router = APIRouter()

@router.post("/generate-profile")
async def generate_profile(
    resume: UploadFile = File(...),
    papers: Optional[List[UploadFile]] = File(default=[]),
    portfolio_url: str = Form(...),
    github_url: str = Form(...),
    scholar_url: Optional[str] = Form(default=None),
):
    # Perform basic file type validation
    if not resume.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")
        
    valid_papers = []
    if papers:
        for paper in papers:
            # Check if it is a valid upload and is a PDF
            if paper.filename and paper.filename.strip():
                if not paper.filename.lower().endswith(".pdf"):
                    raise HTTPException(status_code=400, detail=f"Research paper '{paper.filename}' must be a PDF file.")
                valid_papers.append(paper)
            
    try:
        # Read resume file stream
        resume_content = await resume.read()
        
        # Read paper file streams
        paper_streams = []
        for p in valid_papers:
            content = await p.read()
            paper_streams.append((BytesIO(content), p.filename))
            
        result = generate_research_profile(
            resume_file=BytesIO(resume_content),
            resume_filename=resume.filename,
            paper_files=paper_streams,
            portfolio_url=portfolio_url,
            github_url=github_url,
            scholar_url=scholar_url
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
            
        return {
            "profile_generated": True,
            "profile_path": result.get("profile_path"),
            "profile": result.get("profile")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
