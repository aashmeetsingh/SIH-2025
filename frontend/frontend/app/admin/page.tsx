"use client";
import { useState } from "react";
import axios from "axios";

export default function AdminDashboard() {
  const [timetable, setTimetable] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const generateTimetable = async () => {
    try {
      setLoading(true);
      const payload = {
        days: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        slots_per_day: 6,
        max_classes_per_day: 3,
        classrooms: [
          { id: "room1", name: "Room101", capacity: 40 },
          { id: "room2", name: "Room102", capacity: 50 },
          { id: "room3", name: "Lab201", capacity: 30, type: "lab" },
          { id: "room4", name: "Auditorium", capacity: 100 }
        ],
        batches: [
          { id: "b1", name: "Batch A", size: 35 },
          { id: "b2", name: "Batch B", size: 28 },
          { id: "b3", name: "Batch C", size: 50 },
          { id: "b4", name: "Batch D", size: 25 }
        ],
        subjects: [
          { id: "sub1", name: "Math", batch_id: "b1", classes_per_week: 5 },
          { id: "sub2", name: "Physics", batch_id: "b1", classes_per_week: 3 },
          { id: "sub3", name: "Chemistry", batch_id: "b2", classes_per_week: 4 },
          { id: "sub4", name: "Biology", batch_id: "b2", classes_per_week: 3 },
          { id: "sub5", name: "Computer Science", batch_id: "b3", classes_per_week: 5 },
          { id: "sub6", name: "English", batch_id: "b3", classes_per_week: 3 },
          { id: "sub7", name: "History", batch_id: "b1", classes_per_week: 2 },
          { id: "sub8", name: "Economics", batch_id: "b2", classes_per_week: 2 },
          { id: "sub9", name: "Art", batch_id: "b4", classes_per_week: 3 },
          { id: "sub10", name: "PE", batch_id: "b4", classes_per_week: 4 }
        ],
        faculties: [
          { id: "f1", name: "Dr. Sharma", can_teach: ["sub1", "sub7"] },
          { id: "f2", name: "Dr. Verma", can_teach: ["sub2", "sub3"] },
          { id: "f3", name: "Prof. Iyer", can_teach: ["sub4", "sub6", "sub10"] },
          { id: "f4", name: "Dr. Mehta", can_teach: ["sub5"] },
          { id: "f5", name: "Ms. Kapoor", can_teach: ["sub8", "sub6"] },
          { id: "f6", name: "Mr. Singh", can_teach: ["sub9", "sub10"] }
        ],
        fixed_slots: [
          // Alternating Maths and History for Batch A
          { day: 0, slot: 3, subject_id: "sub1", faculty_id: "f1", room_id: "room1", batch_id: "b1" }, // Mon Math
          { day: 1, slot: 3, subject_id: "sub7", faculty_id: "f1", room_id: "room1", batch_id: "b1" }, // Tue History
          { day: 2, slot: 3, subject_id: "sub1", faculty_id: "f1", room_id: "room1", batch_id: "b1" }, // Wed Math
          { day: 3, slot: 3, subject_id: "sub7", faculty_id: "f1", room_id: "room1", batch_id: "b1" }, // Thu History
          { day: 4, slot: 3, subject_id: "sub1", faculty_id: "f1", room_id: "room1", batch_id: "b1" }, // Fri Math

          // Lab fixed slots for Chemistry (Batch B)
          { day: 0, slot: 2, subject_id: "sub3", faculty_id: "f2", room_id: "room3", batch_id: "b2" },
          { day: 2, slot: 2, subject_id: "sub3", faculty_id: "f2", room_id: "room3", batch_id: "b2" },

          // Auditorium for Computer Science (Batch C)
          { day: 1, slot: 0, subject_id: "sub5", faculty_id: "f4", room_id: "room4", batch_id: "b3" },
          { day: 3, slot: 0, subject_id: "sub5", faculty_id: "f4", room_id: "room4", batch_id: "b3" },

          // PE classes for Batch D
          { day: 0, slot: 5, subject_id: "sub10", faculty_id: "f3", room_id: "room2", batch_id: "b4" },
          { day: 2, slot: 5, subject_id: "sub10", faculty_id: "f3", room_id: "room2", batch_id: "b4" },
          { day: 4, slot: 5, subject_id: "sub10", faculty_id: "f3", room_id: "room2", batch_id: "b4" }
        ]
      };


      const res = await axios.post("http://localhost:8000/generate_timetable", payload);
      setTimetable(res.data.timetable_matrix);
    } catch (err) {
      console.error("Error generating timetable:", err);
    } finally {
      setLoading(false);
    }
  };

 return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-4">Admin Dashboard</h1>
      <button
        onClick={generateTimetable}
        className="px-4 py-2 bg-blue-500 text-white rounded"
      >
        Generate Timetable
      </button>

      {loading && <p className="mt-4">Generating timetable...</p>}

      {timetable && (
        <pre className="mt-6 bg-gray-900 text-green-300 p-4 rounded overflow-x-auto">
          {JSON.stringify(timetable, null, 2)}
        </pre>
      )}
    </div>
  );
}