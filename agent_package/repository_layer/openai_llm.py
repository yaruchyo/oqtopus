from typing import List
from openai import OpenAI


class OpenAiLLM:
    def __init__(self, OPENAI_API_KEY):

        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model_name = "gpt-4o-mini-2024-07-18"

    def generate_llm_answer_json(self, user_prompt: str, translation_class):
        response = self.client.beta.chat.completions.parse(
            model=self.model_name,
            temperature=1,
            messages=[
                {"role": "system", "content": "You are helpful assistant"},
                {"role": "user", "content": user_prompt},
            ],
            response_format=translation_class,
        )

        translation_response: translation_class = response.choices[0].message.parsed

        return translation_response

    def generate_llm_answer(
        self, user_prompt: str, translate_languages: List[str], translation_class
    ):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "You are helpful assistant"}],
                },
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
        )

        return response.choices[0].message
