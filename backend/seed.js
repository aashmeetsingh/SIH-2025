import mongoose from "mongoose";
import bcrypt from "bcryptjs";
import dotenv from "dotenv";

dotenv.config();

const MONGO_URI = process.env.MONGO_URI || "mongodb://127.0.0.1:27017/SIH";

// User schema
const userSchema = new mongoose.Schema({
  username: String,
  password: String,
  role: String
});
const User = mongoose.model("User", userSchema);

async function seedUsers() {
  try {
    await mongoose.connect(MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true });
    console.log("Connected to MongoDB");

    // Clear old users (optional)
    await User.deleteMany({});
    console.log(" Old users removed");

    // Define test users
    const users = [
      { username: "admin1", password: "admin123", role: "admin" },
      { username: "hod1", password: "hod123", role: "hod" },
      { username: "faculty1", password: "faculty123", role: "faculty" },
      { username: "student1", password: "student123", role: "student" }
    ];

    // Hash passwords
    for (let user of users) {
      const hashed = await bcrypt.hash(user.password, 10);
      user.password = hashed;
    }

    // Insert users
    await User.insertMany(users);
    console.log(" Users seeded successfully!");

    mongoose.connection.close();
  } catch (err) {
    console.error(" Error seeding users:", err);
    mongoose.connection.close();
  }
}

seedUsers();
