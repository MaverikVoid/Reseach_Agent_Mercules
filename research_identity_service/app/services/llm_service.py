from openai import OpenAI
from app.core.config import settings
from app.models.profile import ResearchProfile
import json
import logging

logger = logging.getLogger(__name__)

def _get_client_and_model() -> tuple[OpenAI, str]:
    """
    Returns (OpenAI client, model_slug) based on available credentials.
    Defaults to NVIDIA if key is set, else OpenRouter, else raises error.
    """
    nv_key = settings.nvidia_api_key.strip('"' + "'")
    or_key = settings.openrouter_api_key.strip('"' + "'")
    
    if nv_key:
        logger.info("Initializing NVIDIA NIM API Client")
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nv_key
        )
        model = "meta/llama-3.1-70b-instruct"
        return client, model
    elif or_key:
        logger.info("Initializing OpenRouter API Client")
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=or_key,
            default_headers={"X-Title": "Research Identity Service"}
        )
        model = "meta-llama/llama-3.1-70b-instruct"
        return client, model
    else:
        # Fallback to check if env variables exist at call time
        import os
        env_nv = os.getenv("NVIDIA_API_KEY", "").strip()
        env_or = os.getenv("OPENROUTER_API_KEY", "").strip()
        if env_nv:
            client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=env_nv)
            return client, "meta/llama-3.1-70b-instruct"
        elif env_or:
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=env_or, default_headers={"X-Title": "Research Identity Service"})
            return client, "meta-llama/llama-3.1-70b-instruct"
        raise ValueError("Neither NVIDIA_API_KEY nor OPENROUTER_API_KEY is configured in settings.")

def synthesize_profile(prompt: str, retries: int = 3) -> ResearchProfile:
    """
    Queries LLM to synthesize research profile, with a self-correction loop
    if validation fails.
    """
    from app.prompts.templates import SYSTEM_PROMPT
    client, model = _get_client_and_model()
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    for attempt in range(retries):
        try:
            logger.info(f"Synthesizing profile (attempt {attempt + 1}/{retries}) using model: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=3000,
            )
            raw_content = response.choices[0].message.content.strip()
            
            # Clean markdown code blocks if the LLM outputted them despite instructions
            if raw_content.startswith("```"):
                lines = raw_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_content = "\n".join(lines).strip()
            
            # Parse and validate JSON
            profile_data = ResearchProfile.model_validate_json(raw_content)
            logger.info("Research profile validated successfully.")
            return profile_data
            
        except Exception as e:
            logger.warning(f"Validation failed on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                # Add correction prompt as assistant-user turn
                assistant_content = response.choices[0].message.content if 'response' in locals() else ""
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user", 
                    "content": f"Your previous response failed validation with the following error: {e}.\n"
                               f"Please output ONLY valid raw JSON matching the required schema structure exactly."
                })
            else:
                logger.error("All synthesis validation attempts failed.")
                raise e
