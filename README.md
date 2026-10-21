# SlothPlan 🦥
Give it a task and a deadline. It tells you how long you can rest and still finish.

A local LLM (Ollama) breaks the task into steps and guesses the minutes.
Plain Python does all the time math. Nothing leaves your machine.

## Run
```
ollama pull qwen2.5:7b        # or llama3.2:3b for less RAM
pip3 install streamlit requests
python3 -m streamlit run app.py
```

## Test
```
python3 test_slothplan.py
```
Your logged times live in `history.json` next to the app.