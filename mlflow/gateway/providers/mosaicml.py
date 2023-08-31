from typing import Any, Dict, List

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from mlflow.exceptions import MlflowException
from mlflow.gateway.config import MosaicMLConfig, RouteConfig
from mlflow.gateway.providers.base import BaseProvider
from mlflow.gateway.providers.utils import rename_payload_keys, send_request
from mlflow.gateway.schemas import chat, completions, embeddings


class MosaicMLProvider(BaseProvider):
    def __init__(self, config: RouteConfig) -> None:
        super().__init__(config)
        if config.model.config is None or not isinstance(config.model.config, MosaicMLConfig):
            raise TypeError(f"Unexpected config type {config.model.config}")
        self.mosaicml_config: MosaicMLConfig = config.model.config

    async def _request(self, model: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Authorization": f"{self.mosaicml_config.mosaicml_api_key}"}
        return await send_request(
            headers=headers,
            base_url=self.mosaicml_config.mosaicml_api_base
            or "https://models.hosted-on.mosaicml.hosting",
            path=model + "/v1/predict",
            payload=payload,
        )

    # NB: as this parser performs no blocking operations, we are intentionally not defining it
    # as async due to the overhead of spawning an additional thread if we did.
    @staticmethod
    def _parse_chat_messages_to_prompt(messages: List[chat.RequestMessage]) -> str:
        """
        This parser is based on the format described in
        https://huggingface.co/blog/llama2#how-to-prompt-llama-2 .
        The expected format is:
            "<s>[INST] <<SYS>>
            {{ system_prompt }}
            <</SYS>>

            {{ user_msg_1 }} [/INST] {{ model_answer_1 }} </s>
            <s>[INST] {{ user_msg_2 }} [/INST]"
        """
        if any(m1.role == m2.role for m1, m2 in zip(messages, messages[1:])):
            raise MlflowException.invalid_parameter_value(
                "Consecutive messages cannot have the same 'role'.",
            )
        prompt = ""
        for m in messages:
            role = m.role
            content = m.content
            if role == "system":
                prompt += f"<s>[INST] <<SYS>> {content} <</SYS>>"
            elif role == "user":
                inst = f" {content} [/INST]"
                if not prompt.endswith("<</SYS>>"):
                    inst = f"<s>[INST]{inst}"
                prompt += inst
            elif role == "assistant":
                if not prompt.endswith("[/INST]"):
                    raise MlflowException.invalid_parameter_value(
                        "Messages with role 'assistant' must be preceded by a message "
                        "with role 'user'."
                    )
                prompt += f" {content} </s>"
            else:
                raise MlflowException.invalid_parameter_value(
                    f"Invalid role {role} inputted. Must be one of 'system', "
                    "'user', or 'assistant'.",
                )
        if not prompt.endswith("[/INST]"):
            raise MlflowException.invalid_parameter_value(
                "Messages must end with 'user' role for final prompt."
            )
        return prompt

    async def chat(self, payload: chat.RequestPayload) -> chat.ResponsePayload:
        # Extract the List[RequestMessage] from the RequestPayload
        messages = payload.messages
        payload = jsonable_encoder(payload, exclude_none=True)
        # remove the messages from the remaining configuration items
        payload.pop("messages", None)
        self.check_for_model_field(payload)
        key_mapping = {
            "max_tokens": "max_new_tokens",
        }
        for k1, k2 in key_mapping.items():
            if k2 in payload:
                raise HTTPException(
                    status_code=422, detail=f"Invalid parameter {k2}. Use {k1} instead."
                )
        payload = rename_payload_keys(payload, key_mapping)

        # Handle 'prompt' field in payload
        try:
            prompt = [self._parse_chat_messages_to_prompt(messages)]
        except MlflowException as e:
            raise HTTPException(
                status_code=422, detail=f"An invalid request structure was submitted. {e.message}"
            )
        # Construct final payload structure
        final_payload = {"inputs": prompt, "parameters": payload}

        # Input data structure for Mosaic Text Completion endpoint
        #
        # {"inputs": [prompt],
        #  {
        #    "parameters": {
        #      "temperature": 0.2
        #    }
        #   }
        # }

        resp = await self._request(
            self.config.model.name,
            final_payload,
        )
        # Response example
        # (https://docs.mosaicml.com/en/latest/inference.html#text-completion-models)
        # ```
        # {
        #   "outputs": [
        #     "string",
        #   ],
        # }
        # ```
        return chat.ResponsePayload(
            **{
                "candidates": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": c,
                        },
                        "metadata": {},
                    }
                    for c in resp["outputs"]
                ],
                "metadata": {
                    "model": self.config.model.name,
                    "route_type": self.config.route_type,
                },
            }
        )

    async def completions(self, payload: completions.RequestPayload) -> completions.ResponsePayload:
        payload = jsonable_encoder(payload, exclude_none=True)
        self.check_for_model_field(payload)
        key_mapping = {
            "max_tokens": "max_new_tokens",
        }
        for k1, k2 in key_mapping.items():
            if k2 in payload:
                raise HTTPException(
                    status_code=400, detail=f"Invalid parameter {k2}. Use {k1} instead."
                )
        payload = rename_payload_keys(payload, key_mapping)

        # Handle 'prompt' field in payload
        prompt = payload.pop("prompt")
        if isinstance(prompt, str):
            prompt = [prompt]

        # Construct final payload structure
        final_payload = {"inputs": prompt, "parameters": payload}

        # Input data structure for Mosaic Text Completion endpoint
        #
        # {"inputs": [prompt],
        #  {
        #    "parameters": {
        #      "temperature": 0.2
        #    }
        #   }
        # }

        resp = await self._request(
            self.config.model.name,
            final_payload,
        )
        # Response example
        # (https://docs.mosaicml.com/en/latest/inference.html#text-completion-models)
        # ```
        # {
        #   "outputs": [
        #     "string",
        #   ],
        # }
        # ```
        return completions.ResponsePayload(
            **{
                "candidates": [
                    {
                        "text": c,
                        "metadata": {},
                    }
                    for c in resp["outputs"]
                ],
                "metadata": {
                    "model": self.config.model.name,
                    "route_type": self.config.route_type,
                },
            }
        )

    async def embeddings(self, payload: embeddings.RequestPayload) -> embeddings.ResponsePayload:
        payload = jsonable_encoder(payload, exclude_none=True)
        self.check_for_model_field(payload)
        key_mapping = {"text": "inputs"}
        for k1, k2 in key_mapping.items():
            if k2 in payload:
                raise HTTPException(
                    status_code=400, detail=f"Invalid parameter {k2}. Use {k1} instead."
                )
        payload = rename_payload_keys(payload, key_mapping)

        # Ensure 'inputs' is a list of strings
        if isinstance(payload["inputs"], str):
            payload["inputs"] = [payload["inputs"]]

        resp = await self._request(
            self.config.model.name,
            payload,
        )
        # Response example
        # (https://docs.mosaicml.com/en/latest/inference.html#text-embedding-models):
        # ```
        # {
        #   "outputs": [
        #     [
        #       3.25,
        #       0.7685547,
        #       2.65625,
        #       ...
        #       -0.30126953,
        #       -2.3554688,
        #       1.2597656
        #     ]
        #   ]
        # }
        # ```
        return embeddings.ResponsePayload(
            **{
                "embeddings": resp["outputs"],
                "metadata": {
                    "model": self.config.model.name,
                    "route_type": self.config.route_type,
                },
            }
        )
