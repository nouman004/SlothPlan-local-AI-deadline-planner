import json
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st
from scheduler import plan, SPRINT
from llm import breakdown, rest_ideas, LLMError

HIST = Path(__file__).parent / "history.json"   # local file, never leaves your machine


def load_hist():
    try:
        return json.loads(HIST.read_text())
    except (OSError, ValueError):
        return []


def correction_factor():
    ratios = [h["actual"] / h["estimated"] for h in load_hist()[-10:] if h.get("estimated", 0) > 0]
    return round(min(3.0, max(0.5, sum(ratios) / len(ratios))), 2) if ratios else 1.0


def fmt(d):
    return d.strftime("%I:%M %p").lstrip("0")


st.set_page_config(page_title="SlothPlan", page_icon="🦥")
st.title("🦥 SlothPlan")
st.caption("Tell me the task and the deadline. I'll tell you how long you can rest.")

task = st.text_area("What do you have to do?", placeholder="DBMS assignment: 5 SQL queries + ER diagram")

# deadline: 12-hour clock with AM/PM
default = datetime.now() + timedelta(hours=3)
st.write("Deadline (today)")
c1, c2, c3 = st.columns([1, 1, 1])
hour = c1.selectbox("Hour", list(range(1, 13)), index=(default.hour % 12 or 12) - 1)
minute = c2.number_input("Minute", 0, 59, default.minute, format="%02d")
ampm = c3.radio("AM / PM", ["AM", "PM"], index=int(default.hour >= 12), horizontal=True)

energy = st.slider("Energy / motivation", 1, 5, 3)
s, b = SPRINT[energy]
st.caption(f"Low energy = shorter sprints ({s} min work, {b} min break) and slower work. Tired costs you rest.")
model = st.text_input("Ollama model", "qwen2.5:7b")
corr = correction_factor()
st.caption(f"Personal correction factor: ×{corr} (learned from the times you log). Applied to all minutes below.")

if st.button("1. Break it down") and task.strip():
    try:
        with st.spinner("Sloth is thinking (slowly, locally)..."):
            st.session_state["subs"] = breakdown(task, model)
        st.session_state.pop("res", None)
    except LLMError as e:
        st.error(str(e))

if "subs" in st.session_state:
    st.write("Edit the steps. You know your pace better than the model. Tick **done** for finished steps.")
    rows = [dict(r, done=r.get("done", False)) for r in st.session_state["subs"]]
    edited = st.data_editor(rows, num_rows="dynamic", key="editor",
                            column_config={"title": "Step", "minutes": st.column_config.NumberColumn("Minutes", min_value=5, max_value=240),
                                           "done": st.column_config.CheckboxColumn("Done")})
    if st.button("2. Plan my laziness (also re-plans from now)", type="primary"):
        todo = [{"title": r["title"], "minutes": int(r["minutes"])} for r in edited
                if not r.get("done") and r.get("title") and r.get("minutes")]
        now = datetime.now().replace(second=0, microsecond=0)
        deadline = now.replace(hour=(hour % 12) + (12 if ampm == "PM" else 0), minute=int(minute))
        if deadline <= now:
            deadline += timedelta(days=1)
            st.caption("That time already passed today, so I'm using tomorrow.")
        if not todo:
            st.success("Everything is done. Go rest for real. 🦥")
            st.session_state.pop("res", None)
        else:
            st.session_state["raw_total"] = sum(t["minutes"] for t in todo)
            st.session_state["res"] = plan(todo, now, deadline, energy=energy, correction=corr)

res = st.session_state.get("res")
if res:
    if not res["feasible"]:
        st.error(f"No rest. You need {res['needed_min']} min but have {res['available_min']}. "
                 "Do the minimum viable version: cut steps in the table and re-plan.")
    else:
        st.success(f"You can rest until **{fmt(res['start_by'])}** ({res['slack_min']} min guilt-free).")
        st.write(f"Work {res['work_min']} min + breaks {res['break_min']} + buffer {res['buffer_min']}")
        icons = {"work": "🔨", "rest": "😴", "buffer": "🛟"}
        for blk in res["blocks"]:
            extra = ""
            if blk.kind == "work":
                extra = f" · {blk.work_min} min work" + (f" + {blk.breaks} short break{'s' * (blk.breaks > 1)}" if blk.breaks else "")
            else:
                extra = f" · {blk.minutes} min"
            st.write(f"{icons[blk.kind]} {fmt(blk.start)} – {fmt(blk.end)} · **{blk.label}**{extra}")
        if res["slack_min"] >= 15 and st.button("What do I do while resting?"):
            try:
                st.info(rest_ideas(res["slack_min"], model))
            except LLMError as e:
                st.error(str(e))

    with st.expander("Finished? Log how long it really took"):
        actual = st.number_input("Actual minutes (total)", 1, 1000, 60)
        if st.button("Save to my history"):
            h = load_hist()
            h.append({"estimated": st.session_state.get("raw_total", 0), "actual": int(actual),
                      "when": datetime.now().isoformat(timespec="minutes")})
            HIST.write_text(json.dumps(h, indent=1))
            st.success("Saved locally. Your next plan will use it.")