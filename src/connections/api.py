from fastapi import FastAPI

@app.get("/query/{query}")
def query_chatbot(query: str):
    # Query Pinecone
    pinecone_results = pinecone_conn.query_pinecone(query)

    # Query OpenAI
    openai_response = OpenAIConnection.generate_text(prompt=query, system_prompt=pinecone_results)

    return {"response": openai_response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)