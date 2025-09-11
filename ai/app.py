# ai_service/app.py
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from ortools.sat.python import cp_model
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import random
import time

app = FastAPI(title="EduSched AI Service (Hybrid Greedy + ORTools)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Pydantic models ----------

class Classroom(BaseModel):
    id: str
    name: Optional[str]
    capacity: int
    type: Optional[str] = "lecture"

class Batch(BaseModel):
    id: str
    name: Optional[str]
    size: int

class Subject(BaseModel):
    id: str
    name: Optional[str]
    batch_id: str
    classes_per_week: int = Field(..., gt=0)
    preferred_room_type: Optional[str] = None

class Faculty(BaseModel):
    id: str
    name: Optional[str]
    can_teach: List[str] = []
    avg_leaves_per_month: Optional[float] = 0.0
    unavailable_slots: Optional[List[int]] = []

class FixedSlot(BaseModel):
    day: int
    slot: int
    subject_id: str
    faculty_id: Optional[str] = None
    room_id: Optional[str] = None
    batch_id: Optional[str] = None

class ScheduleRequest(BaseModel):
    days: List[str] = Field(default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"])
    slots_per_day: int = 6
    max_classes_per_day: int = 4
    classrooms: List[Classroom] = []
    batches: List[Batch] = []
    subjects: List[Subject] = []
    faculties: List[Faculty] = []
    fixed_slots: List[FixedSlot] = []

# ---------- Helpers ----------

def timeslot_index(day_idx: int, slot_idx: int, slots_per_day: int) -> int:
    return day_idx * slots_per_day + slot_idx

def decode_timeslot(idx: int, slots_per_day: int):
    return idx // slots_per_day, idx % slots_per_day

# ---------- Greedy Pre-Fill ----------

def greedy_prefill(req: ScheduleRequest, sessions: List[Dict], S: int, D: int) -> Dict[int, Dict]:
    pre_assignments = {}
    rng = random.Random(time.time())  # ensure randomness each call

    # --- 1. Fixed Slots ---
    for fs in req.fixed_slots:
        t = timeslot_index(fs.day, fs.slot, S)
        pre_assignments[t] = {
            "session_id": f"{fs.subject_id}__fixed_{t}_{time.time_ns()}",
            "subject_id": fs.subject_id,
            "batch_id": fs.batch_id,
            "faculty_id": fs.faculty_id,
            "room_id": fs.room_id,
            "source": "fixed"
        }

    # --- 2. Faculties with only one subject ---
    for f in req.faculties:
        if len(f.can_teach) == 1:
            subj_id = f.can_teach[0]
            subj_sessions = [s for s in sessions if s["subject_id"] == subj_id]
            for s in subj_sessions:
                placed = False
                for t in range(D * S):
                    if t not in pre_assignments:
                        pre_assignments[t] = {
                            "session_id": s["session_id"],
                            "subject_id": subj_id,
                            "batch_id": s["batch_id"],
                            "faculty_id": f.id,
                            "room_id": rng.choice(req.classrooms).id if req.classrooms else None,
                            "source": "greedy"
                        }
                        placed = True
                        break
                if placed:
                    break
    return pre_assignments

# ---------- Hybrid Scheduler ----------

@app.post("/generate_timetable")
def generate_timetable(req: ScheduleRequest) -> Dict[str, Any]:
    days = req.days
    D = len(days)
    S = req.slots_per_day
    T = D * S

    classrooms = req.classrooms
    batches = {b.id: b for b in req.batches}
    subjects = {s.id: s for s in req.subjects}
    faculties = {f.id: f for f in req.faculties}

    # Build sessions fresh every call
    sessions = []
    for subj in req.subjects:
        for i in range(subj.classes_per_week):
            sessions.append({
                "session_id": f"{subj.id}__{i}_{time.time_ns()}",
                "subject_id": subj.id,
                "batch_id": subj.batch_id,
                "preferred_room_type": subj.preferred_room_type,
                "size": batches.get(subj.batch_id).size if subj.batch_id in batches else 0,
            })

    # Run greedy pre-fill
    greedy_assignments = greedy_prefill(req, sessions, S, D)
    used_sessions = {v["session_id"] for v in greedy_assignments.values()}
    remaining_sessions = [s for s in sessions if s["session_id"] not in used_sessions]

    # --- OR-Tools for remaining sessions ---
    model = cp_model.CpModel()
    x = {}

    for sess in remaining_sessions:
        for t in range(T):
            if t in greedy_assignments:  # skip pre-filled slots
                continue
            for r in classrooms:
                x[(sess["session_id"], t, r.id)] = model.NewBoolVar(
                    f"x_{sess['session_id']}_{t}_{r.id}"
                )

    # Each session must be scheduled once
    for sess in remaining_sessions:
        model.Add(
            sum(x[(sess["session_id"], t, r.id)] 
                for t in range(T) 
                for r in classrooms 
                if (sess["session_id"], t, r.id) in x) == 1
        )

    # Each room can only have 1 session at a time
    for t in range(T):
        for r in classrooms:
            model.Add(
                sum(x[(sess["session_id"], t, r.id)] 
                    for sess in remaining_sessions 
                    if (sess["session_id"], t, r.id) in x) <= 1
            )

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    status = solver.Solve(model)

    timetable = [[] for _ in range(T)]

    # Fill greedy assignments
    for t, v in greedy_assignments.items():
        timetable[t].append({
            "session_id": v["session_id"],
            "subject_id": v["subject_id"],
            "batch_id": v["batch_id"],
            "faculty_id": v["faculty_id"],
            "room_id": v["room_id"],
            "day": t // S,
            "slot": t % S,
            "source": v["source"]
        })

    # Fill OR-Tools results
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for sess in remaining_sessions:
            for t in range(T):
                for r in classrooms:
                    if (sess["session_id"], t, r.id) in x and solver.Value(x[(sess["session_id"], t, r.id)]) == 1:
                        timetable[t].append({
                            "session_id": sess["session_id"],
                            "subject_id": sess["subject_id"],
                            "batch_id": sess["batch_id"],
                            "faculty_id": None,
                            "room_id": r.id,
                            "day": t // S,
                            "slot": t % S,
                            "source": "ortools"
                        })

    # Build readable response
    readable = []
    for day_idx in range(D):
        row = {"day": days[day_idx], "slots": []}
        for slot_idx in range(S):
            tt = timeslot_index(day_idx, slot_idx, S)
            cells = timetable[tt]
            if cells:
                cell = cells[0]
                readable_cell = {
                    "subject": subjects[cell["subject_id"]].name if cell["subject_id"] in subjects else cell["subject_id"],
                    "batch": batches[cell["batch_id"]].name if cell["batch_id"] in batches else cell["batch_id"],
                    "faculty": faculties[cell["faculty_id"]].name if cell["faculty_id"] in faculties else cell["faculty_id"],
                    "room": next((r.name for r in classrooms if r.id == cell["room_id"]), cell["room_id"]),
                    "source": cell["source"]
                }
            else:
                readable_cell = None
            row["slots"].append(readable_cell)
        readable.append(row)

    return {
        "status": "ok",
        "method": "hybrid (greedy + ortools)",
        "timetable_matrix": readable,
        "pre_filled": len(greedy_assignments),
        "remaining_scheduled": len(remaining_sessions)
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
