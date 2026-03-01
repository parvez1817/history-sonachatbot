from pymongo import MongoClient
from datetime import datetime
import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from crewai.flow import Flow

# Suppress unnecessary logging
os.environ["LITELLM_LOG"] = "CRITICAL"
os.environ["OTEL_SDK_DISABLED"] = "true"

# Import the crew
from sonachatbot.crews.poem_crew.poem_crew import CutoffCrew


# =========================
# SETTINGS
# =========================
class Settings(BaseSettings):
    """Application settings."""
    api_title: str = "Sona ChatBot API"
    api_version: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

# =========================
# MONGODB CONNECTION
# =========================
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("MONGO_URI not found in .env file")

mongo_client = MongoClient(MONGO_URI)

db = mongo_client["sonachatbot"]
chats_collection = db["chats"]
chats_collection.create_index("timestamp")

# =========================
# FASTAPI APP
# =========================
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API for Sona College Assistant ChatBot powered by CrewAI"
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# REQUEST/RESPONSE MODELS
# =========================
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


# =========================
# CHAT FLOW CLASS (Reusable)
# =========================
class ChatFlowAPI(Flow):
    """
    API-friendly version of ChatFlow that processes queries and returns results.
    Can be used as a reusable script in any application.
    """
    
    def __init__(self):
        super().__init__()
        self.crew_factory = CutoffCrew()
        self.user_query = ""
        self.route = ""
        self.answer = ""

    def process_query(self, user_query: str) -> str:
        """
        Process a user query through the CrewAI flow and return the answer.
        
        Args:
            user_query: The user's question/query
            
        Returns:
            The AI-generated response
        """
        self.user_query = user_query
        self.route = ""
        self.answer = ""
        
        try:
            # Step 1: Route the query
            route = self._route_query()
            
            # Step 2: Execute the selected crew
            if route == "error":
                return "I encountered an error while processing your request. Please try again."
            
            # Step 3: Get the answer based on route
            if route == "convo":
                result = self._safe_kickoff(self.crew_factory.crew_b_convo())
            else:
                result = self._safe_kickoff(self.crew_factory.crew_c_cutoff())
            
            if result:
                self.answer = result.raw
            else:
                self.answer = "I encountered an error while processing your request. Please try again."
                
            return self.answer
            
        except Exception as e:
            return f"I encountered an error: {str(e)}"

    def _route_query(self) -> str:
        """Route the query using Crew A (Router)."""
        try:
            result = self._safe_kickoff(self.crew_factory.crew_a_router())
            
            if not result:
                return "error"
            
            decision = result.raw.upper()
            if "CONVERSATION" in decision:
                return "convo"
            else:
                return "cutoff"
                
        except Exception as e:
            print(f"Routing error: {e}")
            return "error"

    def _safe_kickoff(self, crew, retry_count=0):
        """Handles Rate Limits and Daily Token Limits gracefully."""
        MAX_RETRIES = 3
        try:
            return crew.kickoff(inputs={"user_query": self.user_query})
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for Daily Token Limit
            if "tokens per day" in error_msg or "tpd" in error_msg:
                print("\n🛑 DAILY TOKEN LIMIT REACHED on Groq!")
                print("Switch to Llama-3.1-8b-instant or wait for the reset.")
                return None 

            # Check for Rate Limit (429)
            if "429" in error_msg and retry_count < MAX_RETRIES:
                wait_time = 7 * (retry_count + 1)
                print(f"⚠️  Rate limit hit! Cooling down for {wait_time}s... (Attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self._safe_kickoff(crew, retry_count + 1)
            
            # Rethrow other errors
            print(f"\n❌ Execution Error: {e}")
            raise e


# =========================
# GLOBAL INSTANCE (Reusable)
# =========================
# Create a singleton instance that can be reused across requests
chat_flow = ChatFlowAPI()


# =========================
# API ENDPOINTS
# =========================
@app.get("/")
def root():
    """Root endpoint returning API info."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "status": "running",
        "endpoints": {
            "chat": "/api/chat (POST)",
            "health": "/health (GET)"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        # 🔥 Process query
        response = chat_flow.process_query(request.message)

        # 🔥 Store in MongoDB
        chat_document = {
            "user_query": request.message,
            "bot_response": response,
            "timestamp": datetime.utcnow()
        }

        try:
            chats_collection.insert_one(chat_document)
        except Exception as db_error:
            print(f"Database error: {db_error}")    
            

        return ChatResponse(
            response=response,
            status="success"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

# =========================
# RUN FUNCTION (for Uvicorn)
# =========================
def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Run the FastAPI server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload
    """
    import uvicorn
    uvicorn.run(
        "sonachatbot.api:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    run_server()

