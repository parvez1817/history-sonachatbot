import os
from typing import List
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

# ⭐ IMPORT YOUR TOOL
from sonachatbot.tools.college_search_tool import college_search_tool

load_dotenv()

@CrewBase
class CutoffCrew:
    # 1. High-Reasoning Model (For Routing & Search)
    llm_strong = LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=os.getenv("ULTER_API_KEY"),
        temperature=0.2
    )

    # 2. Fast Model (For Small Talk & Formatting)
    llm_fast = LLM(
        model="groq/llama-3.1-8b-instant",
        api_key=os.getenv("ULTER_API_KEY"),
        temperature=0.1,
        max_tokens=500
    )
    
    ollama_llm = LLM(
        model="ollama/llama3.2:1b",
        base_url="http://localhost:11434",
        api_key="ollama",
        temperature=0.3
    )

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # --- AGENT DEFINITIONS ---

    @agent
    def manager_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["manager_agent"],
            llm=self.llm_strong,
            verbose=True,
            allow_delegation=False # Usually False for a simple router
        )

    @agent
    def convo_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["convo_agent"],
            llm=self.llm_fast,
            verbose=False
        )

    @agent
    def cutoff_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["cutoff_agent"], 
            llm=self.llm_strong,
            tools=[college_search_tool], 
            verbose=True,
            # Groq has tight rate limits; let's limit requests per minute
            max_iter=3 
        )

    @agent
    def response_formatter_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["response_formatter_agent"], 
            llm=self.llm_fast, 
            verbose=False
        )

    # --- TASK DEFINITIONS ---

    @task
    def routing_task(self) -> Task:
        return Task(
            config=self.tasks_config["routing_task"],
            agent=self.manager_agent()
        )

    @task
    def conversation_task(self) -> Task:
        return Task(
            config=self.tasks_config["conversation_task"],
            agent=self.convo_agent()
        )

    @task
    def search_task(self) -> Task:
        return Task(
            config=self.tasks_config["search_task"],
            agent=self.cutoff_agent()
        )

    @task
    def format_task(self) -> Task:
        return Task(
            config=self.tasks_config["format_task"],
            agent=self.response_formatter_agent(),
            context=[self.search_task()] 
        )

    # --- CREW DEFINITIONS ---

    @crew
    def crew_a_router(self) -> Crew:
        return Crew(
            agents=[self.manager_agent()], 
            tasks=[self.routing_task()], 
            verbose=True
        )

    @crew
    def crew_b_convo(self) -> Crew:
        return Crew(
            agents=[self.convo_agent()], 
            tasks=[self.conversation_task()], 
            verbose=True
        )

    @crew
    def crew_c_cutoff(self) -> Crew:
        return Crew(
            agents=[self.cutoff_agent(), self.response_formatter_agent()],
            tasks=[self.search_task(), self.format_task()],
            process=Process.sequential,
            max_rpm=20,
            verbose=True
        )