import litellm
from litellm import acompletion
import os
import json
import logging
import openai
from openai import OpenAIError
import asyncio

# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

## Models
# Anthropic models: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
# OpenAI models: gpt-4o, gpt-4-turbo-preview, gpt-4-vision-preview, gpt-4, gpt-3.5-turbo

async def make_llm_api_call(messages, model_name, json_mode=False, temperature=0, max_tokens=None, tools=None, tool_choice="auto"):
    # litellm.set_verbose = True

    async def attempt_api_call(api_call_func, max_attempts=3):
        for attempt in range(max_attempts):
            try:
                response = await api_call_func()
                response_content = response.choices[0].message['content'] if json_mode else response
                if json_mode:
                    if not json.loads(response_content):
                        logger.info(f"Invalid JSON received, retrying attempt {attempt + 1}")
                        continue
                    else:
                        return response
                else:
                    return response
            except OpenAIError as e:
                logger.info(f"API call failed, retrying attempt {attempt + 1}. Error: {e}")
                await asyncio.sleep(5)
            except json.JSONDecodeError:
                logger.error(f"JSON decoding failed, retrying attempt {attempt + 1}")
                await asyncio.sleep(5)
        raise Exception("Failed to make API call after multiple attempts.")

    async def api_call():
        api_call_params = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"} if json_mode else None,
            **({"max_tokens": max_tokens} if max_tokens is not None else {})
        }
        if tools:
            api_call_params["tools"] = tools
            api_call_params["tool_choice"] = tool_choice

        # Log the API request
        logger.info(f"Sending API request: {json.dumps(api_call_params, indent=2)}")

        response = await acompletion(**api_call_params)

        # Log the API response
        logger.info(f"Received API response: {response}")

        return response

    return await attempt_api_call(api_call)
