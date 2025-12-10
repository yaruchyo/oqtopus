from enum import Enum

from dotenv import load_dotenv
from google import genai
from pydantic.v1 import BaseModel

load_dotenv()


class GeminiLLM:
    def __init__(self, gemini_api_key, gemini_version):

        self.model_name = gemini_version
        self.config = genai.types.GenerateContentConfig(
            temperature=1,
            system_instruction="Generate the answer within 750 characters.",
        )

        self.client = genai.Client(api_key=gemini_api_key)

    def generate_llm_answer(self, input_message):

        response = self.client.models.generate_content(
            model=self.model_name, config=self.config, contents=input_message
        )
        return response.text

    def generate_llm_answer_pydentic(
        self, input_message: str, structure_output_class: BaseModel
    ):

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=input_message,
            config=dict(
                response_mime_type="application/json",
                response_schema=structure_output_class.model_json_schema(),
            ),
        )

        # Use instantiated objects.
        structure_output: structure_output_class = response.parsed

        return structure_output

    def generate_llm_answer_json(
        self, input_message: str, translation_class: object
    ) -> BaseModel:

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=input_message,
            config={
                "response_mime_type": "application/json",
                "response_schema": translation_class,
            },
        )

        # Use instantiated objects.
        my_recipes: translation_class = response.parsed

        return my_recipes


if __name__ == "__main__":
    llm = GEMINI_LLM()
    answer = llm.generate_llm_answer()
    print(answer)
