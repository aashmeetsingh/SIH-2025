import express from "express";
import mongoose from "mongoose";
import cors from "cors";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import cookieParser from "cookie-parser";
import dotenv from "dotenv";
import timetableRoutes from "./routes/timetableRoutes.js";
import aiProxyRouter from "./routes/aiProxy.js";
dotenv.config();

const app = express();
app.use(express.json());
app.use(cookieParser());
app.use(cors({
  origin: "http://localhost:3000", // Next.js frontend
  credentials: true
}));

// MongoDB connection
mongoose.connect(process.env.MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true });

// User Schema
const userSchema = new mongoose.Schema({
  username: String,
  password: String,
  role: String // "admin" | "hod" | "faculty" | "student"
});
const User = mongoose.model("User", userSchema);

// Auth Middleware
const authMiddleware = (roles = []) => {
  return (req, res, next) => {
    const token = req.cookies.token;
    if (!token) return res.status(401).json({ message: "Unauthorized" });
    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      if (roles.length && !roles.includes(decoded.role)) {
        return res.status(403).json({ message: "Forbidden" });
      }
      req.user = decoded;
      next();
    } catch (err) {
      res.status(401).json({ message: "Invalid Token" });
    }
  };
};

// Routes
app.post("/api/auth/register", async (req, res) => {
  const { username, password, role } = req.body;
  const hashed = await bcrypt.hash(password, 10);
  const user = new User({ username, password: hashed, role });
  await user.save();
  res.json({ message: "User registered" });
});

app.post("/api/auth/login", async (req, res) => {
  const { username, password } = req.body;
  const user = await User.findOne({ username });
  if (!user) return res.status(400).json({ message: "User not found" });

  const valid = await bcrypt.compare(password, user.password);
  if (!valid) return res.status(400).json({ message: "Invalid credentials" });

  const token = jwt.sign(
    { id: user._id, role: user.role },
    process.env.JWT_SECRET,
    { expiresIn: "1d" }
  );

  res.cookie("token", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 24 * 60 * 60 * 1000
  });

  res.json({ role: user.role });
});

app.get("/api/auth/me", authMiddleware(), (req, res) => {
  res.json({ user: req.user });
});

app.post("/api/auth/logout", (req, res) => {
  res.clearCookie("token");
  res.json({ message: "Logged out" });
});

app.use("/api/ai", aiProxyRouter);
app.use("/api/timetable", timetableRoutes);

app.listen(5000, () => console.log("Server running on http://localhost:5000"));
