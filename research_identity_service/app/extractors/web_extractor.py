import httpx
from bs4 import BeautifulSoup
import re
import logging
from app.core.database import get_cache, set_cache

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

def fetch_portfolio(url: str) -> str:
    """
    Fetch portfolio website text. Cleans HTML tags, script, and style elements.
    """
    if not url:
        return ""
    
    # Standardize URL
    url_clean = url.strip()
    if not url_clean.startswith(("http://", "https://")):
        url_clean = "https://" + url_clean

    cached = get_cache(url_clean)
    if cached is not None:
        logger.info(f"Loaded portfolio text from cache: {url_clean}")
        return cached

    try:
        logger.info(f"Fetching portfolio: {url_clean}")
        response = httpx.get(url_clean, headers=HEADERS, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header", "form"]):
            element.decompose()
            
        text = soup.get_text(separator="\n")
        cleaned_text = re.sub(r'\n+', '\n', text).strip()
        
        set_cache(url_clean, cleaned_text)
        return cleaned_text
    except Exception as e:
        logger.error(f"Error fetching portfolio {url_clean}: {e}")
        return f"[Error fetching portfolio: {e}]"

def fetch_github(url: str) -> str:
    """
    Fetch GitHub profile info and public repo details.
    """
    if not url:
        return ""

    url_clean = url.strip()
    cached = get_cache(url_clean)
    if cached is not None:
        logger.info(f"Loaded GitHub profile from cache: {url_clean}")
        return cached

    match = re.search(r"github\.com/([^/]+)", url_clean)
    if not match:
        logger.warning(f"Could not parse GitHub username from {url_clean}")
        return f"[Invalid GitHub URL: {url_clean}]"
        
    username = match.group(1).strip()
    
    import os
    github_token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {"User-Agent": "Research-Identity-Service"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
        
    try:
        logger.info(f"Fetching GitHub profile for user: {username}")
        user_url = f"https://api.github.com/users/{username}"
        user_response = httpx.get(user_url, headers=headers, timeout=10.0)
        user_response.raise_for_status()
        user_data = user_response.json()
        
        repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10"
        repos_response = httpx.get(repos_url, headers=headers, timeout=10.0)
        repos_response.raise_for_status()
        repos_data = repos_response.json()
        
        summary = []
        summary.append(f"GitHub Username: {user_data.get('login')}")
        summary.append(f"Name: {user_data.get('name')}")
        summary.append(f"Bio: {user_data.get('bio')}")
        summary.append(f"Public Repos: {user_data.get('public_repos')}")
        summary.append(f"Followers: {user_data.get('followers')}")
        summary.append(f"Following: {user_data.get('following')}")
        
        summary.append("\nPublic Repositories (Recent / Highlighted):")
        for repo in repos_data:
            if not repo.get("fork"):
                summary.append(
                    f"- {repo.get('name')}: {repo.get('description')} "
                    f"(Stars: {repo.get('stargazers_count')}, Language: {repo.get('language')})"
                )
                
        cleaned_text = "\n".join(summary)
        set_cache(url_clean, cleaned_text)
        return cleaned_text
    except Exception as e:
        logger.error(f"Error fetching GitHub data for {username}: {e}")
        return f"[Error fetching GitHub data: {e}]"

def fetch_scholar(url: str) -> str:
    """
    Fetch Google Scholar profile text.
    Extracts citations, h-index, i10-index, and list of papers.
    """
    if not url:
        return ""

    url_clean = url.strip()
    if not url_clean.startswith(("http://", "https://")):
        url_clean = "https://" + url_clean

    cached = get_cache(url_clean)
    if cached is not None:
        logger.info(f"Loaded Google Scholar profile from cache: {url_clean}")
        return cached
        
    try:
        logger.info(f"Fetching Google Scholar profile: {url_clean}")
        response = httpx.get(url_clean, headers=HEADERS, follow_redirects=True, timeout=15.0)
        
        if response.status_code == 429 or "captcha" in response.text.lower():
            logger.warning("Google Scholar blocked request (Rate limit or CAPTCHA)")
            return "[Google Scholar rate limited or CAPTCHA block, skipped parsing]"
            
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        summary = []
        
        name_div = soup.find("div", id="gsc_prf_in")
        if name_div:
            summary.append(f"Scholar Name: {name_div.text.strip()}")
            
        aff_div = soup.find("div", class_="gsc_prf_il")
        if aff_div:
            summary.append(f"Affiliation/Title: {aff_div.text.strip()}")
            
        stats_table = soup.find("table", id="gsc_rsb_st")
        if stats_table:
            summary.append("\nCitation Metrics:")
            rows = stats_table.find_all("tr")[1:]
            for row in rows:
                cols = [td.text.strip() for td in row.find_all("td")]
                if len(cols) >= 3:
                    summary.append(f"- {cols[0]}: All = {cols[1]}, Since 2021 = {cols[2]}")
                    
        summary.append("\nPublications (First page):")
        pub_rows = soup.find_all("tr", class_="gsc_a_tr")
        for idx, row in enumerate(pub_rows):
            title_a = row.find("a", class_="gsc_a_at")
            details = row.find_all("div", class_="gs_gray")
            cit_td = row.find("td", class_="gsc_a_c")
            year_td = row.find("td", class_="gsc_a_y")
            
            title = title_a.text.strip() if title_a else "Unknown"
            authors = details[0].text.strip() if len(details) > 0 else "Unknown"
            venue = details[1].text.strip() if len(details) > 1 else "Unknown"
            citations = cit_td.text.strip() if cit_td else "0"
            year = year_td.text.strip() if year_td else "Unknown"
            
            summary.append(f"{idx+1}. {title}")
            summary.append(f"   Authors: {authors}")
            summary.append(f"   Venue: {venue} | Year: {year}")
            summary.append(f"   Citations: {citations}")
            summary.append("")
            
        cleaned_text = "\n".join(summary).strip()
        if not cleaned_text:
            cleaned_text = "[Empty or unparseable Google Scholar profile]"
            
        set_cache(url_clean, cleaned_text)
        return cleaned_text
    except Exception as e:
        logger.error(f"Error fetching Google Scholar profile {url_clean}: {e}")
        return f"[Error fetching Google Scholar profile: {e}]"
