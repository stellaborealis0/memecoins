#!/usr/bin/env python3
"""
Helper centralizado para llamadas a LLM vía LiteLLM Gateway (TO:8080).

Este módulo proporciona una única función para todas las llamadas a LLM,
garantizando consistencia y manejo de errores centralizado.

Uso:
    from scripts.llm_client import llm_call

    response = llm_call("Tu prompt aquí", model="im-qwen32b")
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

# Configuración por defecto
DEFAULT_ENDPOINT = os.getenv("LITELLM_ENDPOINT", "http://100.68.1.180:8080")
DEFAULT_MODEL = os.getenv("LITELLM_MODEL", "im-qwen32b")
DEFAULT_TIMEOUT = int(os.getenv("LITELLM_TIMEOUT", "60"))


def llm_call(prompt: str, model: str = None, temperature: float = 0.3) -> str:
    """
    Llama al LLM vía LiteLLM Gateway y devuelve el contenido de la respuesta.

    Args:
        prompt: El prompt a enviar al LLM
        model: El modelo a usar (por defecto: LITELLM_MODEL o im-qwen32b)
        temperature: Temperatura para la generación (por defecto: 0.3)

    Returns:
        El contenido de la respuesta del LLM

    Raises:
        requests.RequestException: Si la llamada falla
        KeyError: Si la respuesta no tiene el formato esperado
    """
    endpoint = os.getenv("LITELLM_ENDPOINT", DEFAULT_ENDPOINT)
    model = model or os.getenv("LITELLM_MODEL", DEFAULT_MODEL)

    # Construir la URL completa
    if not endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/v1"
    endpoint_url = f"{endpoint}/chat/completions"

    logger.debug(f"LLM call: model={model}, endpoint={endpoint_url}")

    try:
        response = requests.post(
            endpoint_url,
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        logger.debug(f"LLM response length: {len(content)} chars")
        return content

    except requests.exceptions.Timeout:
        logger.error(f"LLM call timeout after {DEFAULT_TIMEOUT}s")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM call failed: {e}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"LLM response parsing failed: {e}")
        raise


def llm_call_with_system(prompt: str, system_prompt: str, model: str = None, temperature: float = 0.3) -> str:
    """
    Llama al LLM con un system prompt específico.

    Args:
        prompt: El prompt del usuario
        system_prompt: El system prompt (instrucciones del LLM)
        model: El modelo a usar
        temperature: Temperatura para la generación

    Returns:
        El contenido de la respuesta del LLM
    """
    endpoint = os.getenv("LITELLM_ENDPOINT", DEFAULT_ENDPOINT)
    model = model or os.getenv("LITELLM_MODEL", DEFAULT_MODEL)

    if not endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/v1"
    endpoint_url = f"{endpoint}/chat/completions"

    try:
        response = requests.post(
            endpoint_url,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        logger.error(f"LLM call with system prompt failed: {e}")
        raise


if __name__ == "__main__":
    # Test simple
    logging.basicConfig(level=logging.INFO)

    test_prompt = "Di hola en una palabra."
    try:
        result = llm_call(test_prompt)
        print(f"Prompt: {test_prompt}")
        print(f"Response: {result}")
    except Exception as e:
        print(f"Error: {e}")