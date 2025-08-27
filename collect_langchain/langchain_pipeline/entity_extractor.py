from langchain_community.llms import Ollama

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from .prompts import ENTITES_PROMPT

llm = Ollama(model="mistral:7b", base_url="http://178.32.42.24:11434/api/generate")

def extract_entities(text_chunk):
    prompt = PromptTemplate(input_variables=["text"], template=ENTITES_PROMPT)
    chain = LLMChain(llm=llm, prompt=prompt)
    result = chain.run(text=text_chunk)
    return result
