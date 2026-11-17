import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL, getToken } from "../api/http";
import { AuthProvider } from "../auth";
import LoginPage from "./Login";

// The decorative chart needs a real canvas.
vi.mock("../components/PriceChart", () => ({ default: () => <div /> }));

const fetchMock = vi.fn();
const USER = { id: "u1", name: "Ada", email: "ada@example.com", role: "Trader", status: "Active" };

function json(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

function renderLogin() {
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage mode="signin" />} />
          <Route path="/" element={<p>Home page</p>} />
          <Route path="/dashboard" element={<p>Dashboard page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function signIn(email: string, password: string) {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("sign in page", () => {
  it("signs in through POST /auth/login and stores the token", async () => {
    fetchMock.mockReturnValue(json(200, { user: USER, access_token: "token-123", token_type: "bearer" }));
    renderLogin();

    await signIn("Ada@Example.com", "correct-horse-1");

    await waitFor(() => expect(screen.queryByRole("button", { name: "Sign in" })).toBeNull());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_URL}/auth/login`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ email: "ada@example.com", password: "correct-horse-1" });
    expect(getToken()).toBe("token-123");
  });

  it("shows a message when the email or password is wrong", async () => {
    fetchMock.mockReturnValue(json(401, { detail: "Invalid email or password" }));
    renderLogin();

    await signIn("ada@example.com", "wrong-password");

    expect(await screen.findByText("Email or password is incorrect, or the account is disabled.")).toBeTruthy();
    expect(getToken()).toBeNull();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
  });

  it("checks the email format before calling the API", async () => {
    renderLogin();

    await signIn("not-an-email", "whatever-password");

    expect(await screen.findByText("Enter a valid email address.")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("restores the session from a stored token with GET /auth/me", async () => {
    localStorage.setItem("epoch.token", "stored-token");
    fetchMock.mockReturnValue(json(200, USER));
    renderLogin();

    expect(await screen.findByText("Dashboard page")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_URL}/auth/me`);
    expect(init.headers.Authorization).toBe("Bearer stored-token");
  });
});
