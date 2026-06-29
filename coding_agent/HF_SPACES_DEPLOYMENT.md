# Hugging Face Spaces Deployment Guide

This application can be deployed directly to **Hugging Face Spaces** for free hosting.

## 🚀 Quick Deployment Steps

### 1. Create a New Space on Hugging Face

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click **"Create new Space"**
3. Fill in the details:
   - **Space name**: `jarvis-coding-agent` (or your preferred name)
   - **License**: Choose appropriately (MIT recommended)
   - **Select the Space SDK**: Choose **Gradio**
4. Click **"Create Space"**

### 2. Setup the Repository

Once your Space is created, you'll see a prompt to clone the repository. In your local machine:

```bash
git clone https://huggingface.co/spaces/<your-username>/jarvis-coding-agent
cd jarvis-coding-agent
```

### 3. Copy Files

Copy these files from the `coding_agent` directory to your Space:

```
- app.py
- master_agent.py
- script_agent.py
- project_agent.py
- state.py
- tools.py
- llm_model.py
- requirements.txt
```

### 4. Update Requirements

Ensure `requirements.txt` is in the Space with all necessary dependencies:

```
gradio>=4.0.0
langchain-huggingface>=0.0.1
langgraph>=0.0.1
python-dotenv>=1.0.0
langchain>=0.1.0
requests>=2.31.0
pydantic>=2.0.0
```

### 5. Set Environment Variables

In your Space:

1. Go to **Settings** → **Repository secrets**
2. Add a new secret:
   - **Name**: `HUGGINGFACEHUB_API_TOKEN`
   - **Value**: Your Hugging Face API token (get it from [HF Settings](https://huggingface.co/settings/tokens))

⚠️ **Important**: Make sure your token has **read** permissions for accessing models.

### 6. Push to Space

```bash
git add .
git commit -m "Initial Gradio app setup"
git push
```

The Space will automatically start building and deploying. You can monitor the build in the **Logs** tab.

### 7. Access Your App

Once deployment is complete, your app will be available at:
```
https://huggingface.co/spaces/<your-username>/jarvis-coding-agent
```

---

## 📝 File Structure for Spaces

```
jarvis-coding-agent/
├── app.py                    # Main Gradio interface
├── master_agent.py           # Workflow orchestrator
├── script_agent.py           # Script generation workflow
├── project_agent.py          # Project generation workflow
├── state.py                  # State management & nodes
├── tools.py                  # Utility functions
├── llm_model.py              # LLM configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

---

## 🔧 Configuration Notes

### API Token Security

- The `HUGGINGFACEHUB_API_TOKEN` must be set as a **secret** in Space Settings
- Never commit your `.env` file to the repository
- The app will automatically load the token from Space's environment variables

### Model Configuration

The default model is **DeepSeek-V3.2**. To use a different model:

Edit `llm_model.py` and change the `repo_id`:

```python
llm = HuggingFaceEndpoint(
    repo_id="your-model/name",  # Change this
    task="chat-completion",
    huggingfacehub_api_token=huggingfacehub_api_token,
    max_new_tokens=1200,
    temperature=0.1
)
```

Popular alternatives:
- `meta-llama/Llama-2-7b-chat-hf`
- `mistralai/Mistral-7B-Instruct-v0.1`
- `NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO`

### Performance Tuning

For better performance on Spaces with resource constraints:

1. **Reduce `max_new_tokens`** in `llm_model.py` (default: 1200)
2. **Reduce `max_attempts`** in the UI (default: 3)
3. **Use a smaller model** with faster inference

---

## 🐛 Troubleshooting

### App doesn't start

Check the **Logs** tab in your Space for error messages.

### Token expired or invalid

- Go to Space **Settings** → **Repository secrets**
- Update your `HUGGINGFACEHUB_API_TOKEN` with a fresh token

### Out of memory

- Reduce model size in `llm_model.py`
- Reduce `max_new_tokens` parameter
- Use a quantized model variant

### Slow response time

- Model inference can take time depending on the model and Space tier
- Consider upgrading to a GPU Space (paid option) for faster inference

---

## 💡 Tips for Success

1. **Test locally first** before pushing to Spaces
2. **Monitor logs** during deployment
3. **Use a smaller model** initially for faster iteration
4. **Enable caching** in Gradio for faster repeated queries
5. **Consider GPU upgrade** if inference is slow

---

## 📚 Additional Resources

- [Gradio Documentation](https://www.gradio.app/)
- [Hugging Face Spaces Docs](https://huggingface.co/docs/hub/spaces-overview)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Hugging Face Hub Documentation](https://huggingface.co/docs/hub/security-tokens)

---

**Happy coding! 🚀**
