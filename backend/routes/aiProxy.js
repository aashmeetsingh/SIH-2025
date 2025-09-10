// backend/routes/aiProxy.js
import express from "express";
import axios from "axios";
const router = express.Router();

router.post("/generate", async (req, res) => {
  try {
    const pyRes = await axios.post("http://localhost:8000/generate_timetable", req.body, { timeout: 60000 });
    res.json(pyRes.data);
  } catch (err) {
    console.error("AI error:", err.message);
    res.status(500).json({ error: "AI service error", detail: err.message });
  }
});

export default router;
