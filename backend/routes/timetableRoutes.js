import express from "express";
import axios from "axios";

const router = express.Router();

// POST /api/timetable/generate
router.post("/generate", async (req, res) => {
  try {
    // Send request to Python AI service
    const response = await axios.post("http://localhost:8000/generate_timetable", req.body);
    res.json(response.data);
  } catch (err) {
    console.error("AI Service Error:", err.message);
    res.status(500).json({ error: "Failed to generate timetable" });
  }
});

export default router;
