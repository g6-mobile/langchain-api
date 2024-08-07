from fastapi import FastAPI, APIRouter, HTTPException, Query
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_objectbox.vectorstores import ObjectBox
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain import hub
from openai import OpenAI
import os
from dotenv import load_dotenv,find_dotenv
load_dotenv(find_dotenv())

app = FastAPI()
router = APIRouter()

OpenAI_key = os.environ.get("OPENAI_API_KEY")

# Initialize once on startup
loader = TextLoader("./data/data.txt")
data = loader.load()
text_splitter = RecursiveCharacterTextSplitter()
documents = text_splitter.split_documents(data)
vector = ObjectBox.from_documents(documents, OpenAIEmbeddings(openai_api_key=OpenAI_key), embedding_dimensions=768)

llm = ChatOpenAI(model="gpt-3.5-turbo", openai_api_key=OpenAI_key)
prompt = hub.pull("rlm/rag-prompt")
qa_chain = RetrievalQA.from_chain_type(
    llm,
    retriever=vector.as_retriever(),
    chain_type_kwargs={"prompt": prompt}
)

class QueryModel(BaseModel):
    query: str

@router.post("/query")
async def handle_query(query_model: QueryModel, from_context: bool = Query(False)):
    if from_context:
        # Handle the query using the first logic
        try:
            result = qa_chain({"query": query_model.query})
            return {"query": query_model.query, "answer": result["result"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Handle the query using the second logic
        client = OpenAI()
        allowed_responses = ["moneyReceived", "moneyGiven", "moneyBalance", "invalidQuery"]
        
        # Make the request to OpenAI
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You must interpret the user's request and respond with only one of these four words (moneyReceived, moneyGiven, moneyBalance, invalidQuery). You cannot respond with any other word. Ensure that the response pertains only to the user's query and does not address questions about any other person. If the user's query is unclear or does not match any of the categories, respond with 'invalidQuery'."},
                {"role": "user", "content": query_model.query},
            ],
            max_tokens=10  # Limit response to one word
        )

        # Validate and process the response
        response = completion.choices[0].message.content.strip()

        if response in allowed_responses:
            return {"query": query_model.query, "answer": response}
        else:
            raise HTTPException(status_code=400, detail=f"Invalid response: {response}")

app.include_router(router)
