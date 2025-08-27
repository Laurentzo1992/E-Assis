from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from .prompts import SOMMAIRE_PROMPT

llm = Ollama(model="mistral:7b", base_url="http://178.32.42.24:11434/api/generate")

def extract_sommaire_structure(text):
    prompt = PromptTemplate(input_variables=["text"], template=SOMMAIRE_PROMPT)
    chain = LLMChain(llm=llm, prompt=prompt)
    result = chain.run(text=text)
    return result
