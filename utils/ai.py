import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger("S.T.E.V.E")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_nicknames(theme: str, count: int):
    prompt = (
        f"Create a list of {count} unique and funny Discord nicknames based on the theme: '{theme}'. "
        "Each nickname should be short, clever, and suitable for use as a humorous online nickname. "
        "Do not include numbers or rankings. Return ONLY the nicknames in a comma-separated list."
    )

    try:
        response = client.chat.completions.create(model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=150)

        raw_output = response.choices[0].message.content
        nicknames = [
            name.strip().lstrip("0123456789.- ") for name in raw_output.split(",")
            if name.strip()
        ]

        logger.info(f"Generated {len(nicknames)} nicknames with theme '{theme}'")
        return nicknames[:count]

    except Exception as e:
        logger.error(f"AI nickname generation failed: {e}")
        fallback = [f"{theme.title()}Clown_{i+1}" for i in range(count)]
        return fallback