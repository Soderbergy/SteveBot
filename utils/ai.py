import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger("S.T.E.V.E")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

