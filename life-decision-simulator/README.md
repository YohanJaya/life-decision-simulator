# Life Decision Simulator

A multi-agent system for exploring life decisions and their potential outcomes.

## Project Structure

- `main.py` - Entry point that wires the layers together and runs the main loop
- `agents/` - Collection of specialized agents for different decision aspects
- `rules/` - DMN (Decision Model and Notation) engine for rule evaluation
- `core/` - Shared schemas and state management
- `data/` - Reference data for decision analysis
- `frontend/` - CLI and web interface (optional)
- `tests/` - Unit and integration tests

## Setup

1. Create a virtual environment
2. Install requirements: `pip install -r requirements.txt`
3. Configure environment variables from `.env.example`
4. Run: `python main.py`

## Agents

1. **Conversational Agent** - Dialogue management and user interaction
2. **Orchestrator Agent** - Coordinates workflow between agents
3. **Analytical Agent** - Quantifies decision outcomes
4. **DMN Engine (Agent 4)** - Evaluates business rules
5. **Research Agent** - Gathers data and insights
6. **Uncertainty Agent** - Handles probabilistic scenarios
7. **Decision Framer** - Structures decision problems
8. **Scenario Explorer** - "What if" simulations
