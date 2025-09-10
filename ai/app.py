# ai_service/app.py
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from ortools.sat.python import cp_model
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="EduSched AI Service (Optimized)")

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
    days: List[str] = Field(default_factory=lambda: ["Mon","Tue","Wed","Thu","Fri"])
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

# ---------- Scheduler ----------

@app.post("/generate_timetable")
def generate_timetable(req: ScheduleRequest) -> Dict[str, Any]:
    days = req.days
    D = len(days)
    S = req.slots_per_day
    T = D * S  # total timeslots

    classrooms = req.classrooms
    batches = {b.id: b for b in req.batches}
    subjects = {s.id: s for s in req.subjects}
    faculties = {f.id: f for f in req.faculties}
    fixed_slots = req.fixed_slots

    # Build sessions
    sessions = []
    for subj in req.subjects:
        for i in range(subj.classes_per_week):
            sessions.append({
                "session_id": f"{subj.id}__{i}",
                "subject_id": subj.id,
                "batch_id": subj.batch_id,
                "preferred_room_type": subj.preferred_room_type,
                "size": batches.get(subj.batch_id).size if subj.batch_id in batches else 0,
            })

    num_sessions = len(sessions)
    room_ids = [r.id for r in classrooms]
    faculty_ids = [f.id for f in req.faculties]

    # Quick maps
    room_index = {r.id: idx for idx, r in enumerate(classrooms)}
    faculty_index = {fid: idx for idx, fid in enumerate(faculty_ids)}
    session_index = {s["session_id"]: idx for idx, s in enumerate(sessions)}

    model = cp_model.CpModel()
    assign = {}

    # Create variables
    for si, s in enumerate(sessions):
        possible_facs = [f for f in req.faculties if s["subject_id"] in f.can_teach]
        if not possible_facs: continue
        possible_rooms = [r for r in classrooms if r.capacity >= s["size"] and (not s["preferred_room_type"] or r.type == s["preferred_room_type"])]
        if not possible_rooms: continue
        for t in range(T):
            for r in possible_rooms:
                for f in possible_facs:
                    if f.unavailable_slots and t in f.unavailable_slots: continue
                    var = model.NewBoolVar(f"assign_s{si}_t{t}_r{room_index[r.id]}_f{faculty_index[f.id]}")
                    assign[(si, t, room_index[r.id], faculty_index[f.id])] = var

    # Each session assigned at most once
    for si in range(num_sessions):
        vars_for_session = [v for (sidx, *_), v in assign.items() if sidx == si]
        if vars_for_session:
            model.Add(sum(vars_for_session) <= 1)

    # No conflicts: faculty, room, batch
    for fid_idx, fid in enumerate(faculty_ids):
        for t in range(T):
            vars_fac_t = [v for (sidx, tt, rdx, fidx), v in assign.items() if tt == t and fidx == fid_idx]
            if vars_fac_t:
                model.Add(sum(vars_fac_t) <= 1)

    for ridx, rid in enumerate(room_ids):
        for t in range(T):
            vars_room_t = [v for (sidx, tt, rdx, fidx), v in assign.items() if tt == t and rdx == ridx]
            if vars_room_t:
                model.Add(sum(vars_room_t) <= 1)

    for batch_id in batches.keys():
        for t in range(T):
            vars_batch_t = [v for (sidx, tt, rdx, fidx), v in assign.items() if tt == t and sessions[sidx]["batch_id"] == batch_id]
            if vars_batch_t:
                model.Add(sum(vars_batch_t) <= 1)

    # Max classes per day
    max_per_day = req.max_classes_per_day
    for fid_idx, fid in enumerate(faculty_ids):
        for day in range(D):
            slots_idx = range(day * S, (day+1)*S)
            vars_fac_day = [v for (sidx, tt, rdx, fidx), v in assign.items() if fidx == fid_idx and tt in slots_idx]
            if vars_fac_day:
                model.Add(sum(vars_fac_day) <= max_per_day)
    for batch_id in batches.keys():
        for day in range(D):
            slots_idx = range(day * S, (day+1)*S)
            vars_batch_day = [v for (sidx, tt, rdx, fidx), v in assign.items() if tt in slots_idx and sessions[sidx]["batch_id"] == batch_id]
            if vars_batch_day:
                model.Add(sum(vars_batch_day) <= max_per_day)

    # Fixed slots
    fixed_session_assigned = set()
    for fs in fixed_slots:
        t = timeslot_index(fs.day, fs.slot, S)
        candidate_sessions = [(si, s) for si, s in enumerate(sessions)
                              if s["subject_id"].lower() == fs.subject_id.lower() and s["batch_id"] == fs.batch_id and si not in fixed_session_assigned]
        if not candidate_sessions: continue
        si = candidate_sessions[0][0]
        forced_vars = []
        for (sidx, tt, rdx, fidx), var in assign.items():
            if sidx != si or tt != t: continue
            if fs.room_id is not None and room_ids[rdx] != fs.room_id: continue
            if fs.faculty_id is not None and faculty_ids[fidx] != fs.faculty_id: continue
            forced_vars.append(var)
        if forced_vars:
            model.Add(sum(forced_vars) == 1)
            fixed_session_assigned.add(si)

    # Objective: maximize scheduled sessions + slot utilization - balance faculty load
    scheduled_vars = []
    for si in range(num_sessions):
        vars_for_si = [v for (sidx, *_), v in assign.items() if sidx == si]
        if vars_for_si:
            sv = model.NewBoolVar(f"scheduled_si{si}")
            model.Add(sum(vars_for_si) == 1).OnlyEnforceIf(sv)
            model.Add(sum(vars_for_si) <= 0).OnlyEnforceIf(sv.Not())
            scheduled_vars.append(sv)

    fac_load = []
    for fidx, fid in enumerate(faculty_ids):
        vars_for_f = [v for (sidx, tt, rdx, ffidx), v in assign.items() if ffidx == fidx]
        if vars_for_f:
            load = model.NewIntVar(0, num_sessions, f"load_f{fidx}")
            model.Add(load == sum(vars_for_f))
            fac_load.append(load)
        else:
            fac_load.append(model.NewIntVar(0, 0, f"load_f{fidx}"))

    max_load = model.NewIntVar(0, num_sessions, "max_load")
    model.AddMaxEquality(max_load, fac_load)

    # Track slot utilization
    slot_used = {}
    for batch_id in batches.keys():
        for t in range(T):
            vars_batch_t = [v for (sidx, tt, rdx, fidx), v in assign.items() if tt == t and sessions[sidx]["batch_id"] == batch_id]
            if vars_batch_t:
                su = model.NewBoolVar(f"slot_used_{batch_id}_t{t}")
                model.AddMaxEquality(su, vars_batch_t)
                slot_used[(batch_id, t)] = su

    BIG, MEDIUM = 1000, 10
    objective_terms = [sum(scheduled_vars) * BIG - max_load]
    objective_terms += [su * MEDIUM for su in slot_used.values()]
    model.Maximize(sum(objective_terms))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    solver.parameters.num_search_workers = 8
    result = solver.Solve(model)

    if result in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        timetable = [[] for _ in range(T)]
        scheduled_session_ids = set()
        unscheduled = []

        for (sidx, tt, rdx, fidx), var in assign.items():
            if solver.Value(var) == 1:
                scheduled_session_ids.add(sidx)
                timetable[tt].append({
                    "session_id": sessions[sidx]["session_id"],
                    "subject_id": sessions[sidx]["subject_id"],
                    "batch_id": sessions[sidx]["batch_id"],
                    "room_id": room_ids[rdx],
                    "faculty_id": faculty_ids[fidx],
                    "day": tt // S,
                    "slot": tt % S
                })

        for si, s in enumerate(sessions):
            if si not in scheduled_session_ids:
                unscheduled.append({"session_id": s["session_id"], "subject_id": s["subject_id"], "batch_id": s["batch_id"]})

        readable = []
        for day_idx in range(D):
            row = {"day": days[day_idx], "slots": []}
            for slot_idx in range(S):
                tt = timeslot_index(day_idx, slot_idx, S)
                cells = timetable[tt]
                if cells:
                    cell = cells[0]
                    readable_cell = {
                        "subject": subjects[cell["subject_id"]].name if subjects[cell["subject_id"]].name else cell["subject_id"],
                        "batch": batches[cell["batch_id"]].name if cell["batch_id"] in batches else cell["batch_id"],
                        "faculty": faculties[cell["faculty_id"]].name if cell["faculty_id"] in faculties else cell["faculty_id"],
                        "room": next((r.name for r in classrooms if r.id == cell["room_id"]), cell["room_id"])
                    }
                else:
                    readable_cell = None
                row["slots"].append(readable_cell)
            readable.append(row)

        faculty_loads = {fid: solver.Value(fac_load[fidx]) for fidx, fid in enumerate(faculty_ids)}
        return {
            "status": "ok",
            "scheduled_count": int(sum(solver.Value(sv) for sv in scheduled_vars)),
            "timetable_matrix": readable,
            "unscheduled": unscheduled,
            "faculty_loads": faculty_loads
        }

    return {"status": "infeasible", "message": "No feasible schedule found"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
