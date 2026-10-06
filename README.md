---
title: Research Agent Bot
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Research Agent Bot (Mercules)

An autonomous Research Idea Evaluator & Experiment Pipeline running natively on Telegram. This repository hosts the orchestrator bot, coding agents, and research identity services inside a containerized setup.

## 🚀 Overview

The **Research Agent Bot** is a multi-agent system designed to evaluate research ideas, conduct literature reviews, and execute code-based experiments autonomously. Users interact with the system seamlessly through a Telegram bot.

### Core Components

1. **Orchestrator (`orchestrator/`)**
   - The central nervous system of the bot.
   - Manages the Telegram bot interface and user state.
   - Routes tasks through a defined workflow graph (`graph.py`).
   - Uses OpenRouter for LLM inference (defaults to `meta/llama-3.1-70b-instruct` with an NVIDIA API key, or `openrouter/free` fallback).

2. **Coding Agent (`coding_agent/`)**
   - Handles the actual execution of coding, data tasks, and experiments.
   - Consists of specialized agents (Master Agent, Project Agent, Script Agent).
   - Powered by **`deepseek-ai/DeepSeek-V3.2`** via HuggingFace for robust code generation.
   - Includes its own deployment setup (Hugging Face Spaces).

3. **Research Identity Service (`research_identity_service/`)**
   - A backend service for managing context, memory, and researcher profiles to personalize evaluations.

## 🤖 Models Used

- **Code Generation (Coding Agent)**: `deepseek-ai/DeepSeek-V3.2`
- **Reasoning & Task Routing (Orchestrator)**: `meta/llama-3.1-70b-instruct` (via OpenRouter)
- **Text Embeddings**: `sentence-transformers/all-MiniLM-L6-v2`

## ⚙️ Setup & Configuration

The project relies on environment variables defined in `.env`. Key configurations include:
- `TELEGRAM_BOT_TOKEN`: To connect the orchestrator to Telegram.
- `OPENROUTER_API_KEY` & `NVIDIA_API_KEY`: For LLM access in the orchestrator.
- `HUGGINGFACEHUB_API_TOKEN`: For the coding agent's DeepSeek model and embeddings.
- `KAGGLE_USERNAME` & `KAGGLE_KEY`: For data access/experiments.

## 🐳 Deployment

This project is configured to run as a **Hugging Face Docker Space** (exposing port `7860`). See individual component directories (e.g., `coding_agent/HF_SPACES_DEPLOYMENT.md`) for specific deployment instructions.
