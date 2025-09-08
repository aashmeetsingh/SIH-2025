export async function login(username: string, password: string) {
  const res = await fetch("http://localhost:5000/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include", // important for cookies
    body: JSON.stringify({ username, password })
  });
  if (!res.ok) throw new Error("Login failed");
  return res.json();
}

export async function getMe() {
  const res = await fetch("http://localhost:5000/api/auth/me", {
    credentials: "include"
  });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

export async function logout() {
  await fetch("http://localhost:5000/api/auth/logout", {
    method: "POST",
    credentials: "include"
  });
}
