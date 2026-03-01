import time
import os
from pydantic import BaseModel
from crewai.flow import Flow, listen, start

# Suppress unnecessary logging
os.environ["LITELLM_LOG"] = "CRITICAL"
os.environ["OTEL_SDK_DISABLED"] = "true"

# ✅ Ensure this matches your project structure
from sonachatbot.crews.poem_crew.poem_crew import CutoffCrew

# =========================
# STATE (Chat Input/Output)
# =========================
class ChatState(BaseModel):
    user_query: str = ""
    route: str = ""      # Tracks decision: "convo" or "cutoff"
    answer: str = ""

# =========================
# FLOW DEFINITION
# =========================
class ChatFlow(Flow[ChatState]):

    def __init__(self):
        super().__init__()
        # Initialize the crew factory once for efficiency
        self.crew_factory = CutoffCrew()

    @start()
    def get_user_query(self):
        """Step 1: Capture user input from the terminal."""
        self.state.user_query = input("\nAsk Sona College Assistant: ")

    @listen(get_user_query)
    def run_router(self):
        """Step 2: Use Crew A (The Router) to decide the logic path."""
        print(f"\n--- [CREW A] Manager is analyzing the query... ---")
        
        # ✅ Added safe_kickoff here to prevent router crashes
        result = self._safe_kickoff(self.crew_factory.crew_a_router())
        
        if not result:
            self.state.route = "error"
            return self.state.route

        # Determine path based on manager output
        decision = result.raw.upper()
        if "CONVERSATION" in decision:
            self.state.route = "convo"
        else:
            self.state.route = "cutoff"
            
        return self.state.route

    @listen(run_router)
    def execute_selected_crew(self):
        """Step 3: Execute the specific crew based on the route."""
        if self.state.route == "error":
            self.state.answer = "I encountered an error while processing your request. Please try again."
            return

        if self.state.route == "convo":
            print(f"--- [CREW B] Routing to Conversational Assistant ---")
            result = self._safe_kickoff(self.crew_factory.crew_b_convo())
        else:
            print(f"--- [CREW C] Routing to Cutoff Search Specialists ---")
            result = self._safe_kickoff(self.crew_factory.crew_c_cutoff())

        if result:
            self.state.answer = result.raw

    @listen(execute_selected_crew)
    def show_answer(self):
        """Step 4: Display the final result to the user."""
        print("\n🎓 ANSWER:\n")
        print(self.state.answer)
        print("-" * 50)

    # ⭐ HELPER FUNCTION (Now properly placed inside the Class)
    def _safe_kickoff(self, crew, retry_count=0):
        """Handles Rate Limits and Daily Token Limits gracefully."""
        MAX_RETRIES = 3
        try:
            return crew.kickoff(inputs={"user_query": self.state.user_query})
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
# EXECUTION LOOP
# =========================
def kickoff():
    """Initializes and runs the chatbot loop."""
    flow = ChatFlow()
    print("🚀 Sona College AI is ready.")
    
    try:
        while True:
            flow.kickoff()
    except KeyboardInterrupt:
        print("\n\nShutting down Sona College Assistant. Goodbye!")
    except Exception as e:
        print(f"\n[Flow Error]: {e}")
        print("Restarting in 3s...")
        time.sleep(3)
        kickoff() # Restart the loop

if __name__ == "__main__":
    kickoff()